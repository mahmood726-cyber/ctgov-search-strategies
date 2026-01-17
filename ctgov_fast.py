#!/usr/bin/env python3
"""
Fast CT.gov Search with Combination Strategies
- Parallel execution for speed
- Combination strategies for improved recall
- Compact output
"""

import json
import time
import concurrent.futures
import threading
from typing import List, Dict, Set, Tuple
from urllib.parse import quote
from datetime import datetime
from pathlib import Path

from ctgov_config import DEFAULT_PAGE_SIZE, DEFAULT_TIMEOUT
from ctgov_utils import build_params, fetch_nct_ids, get_session

MAX_WORKERS = 5
TIMEOUT = DEFAULT_TIMEOUT

# Base strategies
STRATEGIES = {
    "S1": ("Condition", lambda c: f"query.cond={quote(c)}"),
    "S2": ("Interventional", lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[StudyType]INTERVENTIONAL')}"),
    "S3": ("Randomized", lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED')}"),
    "S4": ("Phase3/4", lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[Phase](PHASE3 OR PHASE4)')}"),
    "S5": ("HasResults", lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[ResultsFirstPostDate]RANGE[MIN,MAX]')}"),
    "S6": ("Completed", lambda c: f"query.cond={quote(c)}&filter.overallStatus=COMPLETED"),
    "S10": ("TreatmentRCT", lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT')}"),
}

# Combination strategies
COMBOS = {
    "C1": ("S3+S10", ["S3", "S10"]),
    "C2": ("S3+S5", ["S3", "S5"]),
    "C3": ("S3+S6", ["S3", "S6"]),
    "C4": ("AllRCT", ["S3", "S5", "S6", "S10"]),
}

cache = {}
cache_lock = threading.Lock()


def search(condition: str, strategy_id: str) -> Tuple[int, List[str], float]:
    """Search and return (count, nct_ids, time)"""
    cache_key = f"{condition}:{strategy_id}"
    with cache_lock:
        if cache_key in cache:
            return cache[cache_key]

    if strategy_id not in STRATEGIES:
        return (0, [], 0)

    _, query_fn = STRATEGIES[strategy_id]
    try:
        start = time.time()
        params = build_params(query_fn(condition))
        session = get_session("CTgov-Fast/2.0")
        ncts, total = fetch_nct_ids(
            session, params, timeout=TIMEOUT, page_size=DEFAULT_PAGE_SIZE
        )
        elapsed = time.time() - start
        result = (total, sorted(ncts), elapsed)
        with cache_lock:
            cache[cache_key] = result
        return result
    except Exception:
        pass
    return (0, [], 0)


def search_parallel(condition: str) -> Dict:
    """Search all base strategies in parallel"""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(search, condition, sid): sid for sid in STRATEGIES}
        for f in concurrent.futures.as_completed(futures):
            sid = futures[f]
            try:
                results[sid] = f.result()
            except Exception:
                results[sid] = (0, [], 0)
    return results


def search_combo(condition: str, combo_id: str, base_results: Dict) -> Tuple[int, Set[str]]:
    """Combine results from multiple strategies"""
    if combo_id not in COMBOS:
        return (0, set())

    _, strategies = COMBOS[combo_id]
    all_ncts = set()
    for sid in strategies:
        if sid in base_results:
            _, ncts, _ = base_results[sid]
            all_ncts.update(ncts)
    return (len(all_ncts), all_ncts)


def calc_recall(found_ncts: Set[str], known_ncts: Set[str]) -> float:
    """Calculate recall percentage"""
    if not known_ncts:
        return 0
    return len(found_ncts & known_ncts) / len(known_ncts) * 100


def analyze_condition(condition: str, known_ncts: Set[str]) -> Dict:
    """Full analysis for one condition"""
    start = time.time()

    # Base strategies in parallel
    base_results = search_parallel(condition)

    # Calculate recall for base strategies
    recalls = {}
    for sid, (count, ncts, t) in base_results.items():
        recall = calc_recall(set(ncts), known_ncts)
        recalls[sid] = {"count": count, "recall": recall, "time": t}

    # Combination strategies
    for cid, (name, _) in COMBOS.items():
        count, ncts = search_combo(condition, cid, base_results)
        recall = calc_recall(ncts, known_ncts)
        recalls[cid] = {"count": count, "recall": recall, "name": name}

    elapsed = time.time() - start

    # Find best
    best_id = max(recalls, key=lambda x: recalls[x]["recall"])
    best_recall = recalls[best_id]["recall"]

    return {
        "condition": condition,
        "known": len(known_ncts),
        "best_strategy": best_id,
        "best_recall": best_recall,
        "all_recalls": recalls,
        "total_time": elapsed
    }


def print_results(results: Dict):
    """Print compact results"""
    print(f"\n{results['condition'].upper()} ({results['known']} known)")
    print("-" * 60)
    print(f"{'ID':<6} {'Strategy':<12} {'Count':>8} {'Recall':>8}")
    print("-" * 60)

    sorted_r = sorted(results["all_recalls"].items(), key=lambda x: x[1]["recall"], reverse=True)
    for sid, data in sorted_r:
        name = STRATEGIES.get(sid, COMBOS.get(sid, ("?", [])))[0]
        if isinstance(name, list):
            name = COMBOS[sid][0]
        print(f"{sid:<6} {name:<12} {data['count']:>8,} {data['recall']:>7.1f}%")

    print("-" * 60)
    print(f"BEST: {results['best_strategy']} = {results['best_recall']:.1f}% | Time: {results['total_time']:.1f}s")


def main():
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")

    # Load known NCT IDs
    nct_file = output_dir / "recall_test_results.json"
    if not nct_file.exists():
        print("No recall data found. Run validate_and_recall.py first.")
        return

    with open(nct_file) as f:
        data = json.load(f)

    condition_groups = {k: set(v) for k, v in data.get("condition_groups", {}).items() if len(v) >= 3}
    print(f"Loaded {len(condition_groups)} conditions with 3+ known studies\n")

    print("=" * 60)
    print("FAST COMBINATION STRATEGY ANALYSIS")
    print("=" * 60)

    all_results = []
    strategy_totals = {}

    for condition, known_ncts in list(condition_groups.items())[:15]:
        results = analyze_condition(condition, known_ncts)
        all_results.append(results)
        print_results(results)

        # Aggregate
        for sid, data in results["all_recalls"].items():
            if sid not in strategy_totals:
                strategy_totals[sid] = {"total_found": 0, "total_known": 0, "recalls": []}
            found = int(data["recall"] * results["known"] / 100)
            strategy_totals[sid]["total_found"] += found
            strategy_totals[sid]["total_known"] += results["known"]
            strategy_totals[sid]["recalls"].append(data["recall"])

    # Summary
    print("\n" + "=" * 60)
    print("OVERALL SUMMARY")
    print("=" * 60)
    print(f"{'ID':<6} {'Avg Recall':>10} {'Overall':>10} {'Found':>8}")
    print("-" * 40)

    sorted_s = sorted(
        strategy_totals.items(),
        key=lambda x: sum(x[1]["recalls"]) / len(x[1]["recalls"]) if x[1]["recalls"] else 0,
        reverse=True
    )

    for sid, data in sorted_s:
        avg = sum(data["recalls"]) / len(data["recalls"]) if data["recalls"] else 0
        overall = data["total_found"] / data["total_known"] * 100 if data["total_known"] > 0 else 0
        print(f"{sid:<6} {avg:>9.1f}% {overall:>9.1f}% {data['total_found']:>8}")

    print("-" * 40)

    # Winner
    winner = sorted_s[0]
    print(f"\nWINNER: {winner[0]} with {sum(winner[1]['recalls']) / len(winner[1]['recalls']):.1f}% avg recall")

    # Save
    out_file = output_dir / f"fast_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    export = {
        "timestamp": datetime.now().isoformat(),
        "conditions": len(condition_groups),
        "results": [{k: v for k, v in r.items() if k != "all_recalls"} for r in all_results],
        "summary": {
            sid: {"avg_recall": sum(d["recalls"]) / len(d["recalls"]) if d["recalls"] else 0}
            for sid, d in strategy_totals.items()
        }
    }
    with open(out_file, 'w') as f:
        json.dump(export, f, indent=2)
    print(f"\nSaved: {out_file}")


if __name__ == "__main__":
    main()
