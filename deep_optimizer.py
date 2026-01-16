#!/usr/bin/env python3
"""
Deep CT.gov Optimizer - Exhaustive multi-strategy combinations
Focus on top-performing strategies with larger combinations
"""

import json
import time
import concurrent.futures
import threading
import itertools
from typing import Dict, Set, List, Tuple
from urllib.parse import quote
from datetime import datetime
from pathlib import Path

from ctgov_config import DEFAULT_TIMEOUT
from ctgov_utils import build_params, fetch_nct_ids, get_session

MAX_WORKERS = 10
TIMEOUT = DEFAULT_TIMEOUT

# Top-performing strategies from phase 1
TOP_STRATEGIES = {
    "S3": ("Randomized", "query.cond={c}&query.term=AREA[DesignAllocation]RANDOMIZED"),
    "S5": ("HasResults", "query.cond={c}&query.term=AREA[ResultsFirstPostDate]RANGE[MIN,MAX]"),
    "S6": ("Completed", "query.cond={c}&filter.overallStatus=COMPLETED"),
    "S10": ("TreatmentRCT", "query.cond={c}&query.term=AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT"),
    "S2": ("Interventional", "query.cond={c}&query.term=AREA[StudyType]INTERVENTIONAL"),
    "P23": ("Phase2_3", "query.cond={c}&query.term=AREA[Phase](PHASE2 OR PHASE3)"),
    "P234": ("Phase2_3_4", "query.cond={c}&query.term=AREA[Phase](PHASE2 OR PHASE3 OR PHASE4)"),
    "ST4": ("CompOrTerm", "query.cond={c}&query.term=AREA[OverallStatus](COMPLETED OR TERMINATED)"),
    "PU1": ("Treatment", "query.cond={c}&query.term=AREA[DesignPrimaryPurpose]TREATMENT"),
    "PU4": ("TreatOrPrev", "query.cond={c}&query.term=AREA[DesignPrimaryPurpose](TREATMENT OR PREVENTION)"),
    "AL2": ("AnyAlloc", "query.cond={c}&query.term=AREA[DesignAllocation](RANDOMIZED OR NON_RANDOMIZED)"),
    "I1": ("Drug", "query.cond={c}&query.term=AREA[InterventionType]DRUG"),
    "I5": ("DrugOrBio", "query.cond={c}&query.term=AREA[InterventionType](DRUG OR BIOLOGICAL)"),
    "M4": ("AnyBlind", "query.cond={c}&query.term=AREA[DesignMasking](DOUBLE OR SINGLE OR TRIPLE)"),
    "C_RCT_COMP": ("RCT+Comp", "query.cond={c}&query.term=AREA[DesignAllocation]RANDOMIZED&filter.overallStatus=COMPLETED"),
    "C_RCT_RES": ("RCT+Results", "query.cond={c}&query.term=AREA[DesignAllocation]RANDOMIZED AND AREA[ResultsFirstPostDate]RANGE[MIN,MAX]"),
    "C_INT_RCT": ("Int+RCT", "query.cond={c}&query.term=AREA[StudyType]INTERVENTIONAL AND AREA[DesignAllocation]RANDOMIZED"),
    "C_DRUG_RCT": ("Drug+RCT", "query.cond={c}&query.term=AREA[InterventionType]DRUG AND AREA[DesignAllocation]RANDOMIZED"),
}

cache = {}
cache_lock = threading.Lock()

def search_strategy(condition: str, strategy_id: str) -> Set[str]:
    """Search and return NCT IDs"""
    cache_key = f"{condition}:{strategy_id}"
    with cache_lock:
        if cache_key in cache:
            return cache[cache_key]

    if strategy_id not in TOP_STRATEGIES:
        return set()

    _, query_template = TOP_STRATEGIES[strategy_id]
    query = query_template.replace("{c}", quote(condition))
    try:
        params = build_params(query)
        session = get_session("CTgov-Deep/1.0")
        ncts, _ = fetch_nct_ids(session, params, timeout=TIMEOUT, page_size=1000)
        with cache_lock:
            cache[cache_key] = ncts
        return ncts
    except:
        pass
    return set()

def search_all_strategies(condition: str) -> Dict[str, Set[str]]:
    """Search all strategies in parallel"""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(search_strategy, condition, sid): sid for sid in TOP_STRATEGIES}
        for f in concurrent.futures.as_completed(futures):
            sid = futures[f]
            try:
                results[sid] = f.result()
            except:
                results[sid] = set()
    return results

def evaluate_combo(combo: Tuple[str, ...], all_results: Dict[str, Dict[str, Set[str]]],
                   condition_groups: Dict[str, Set[str]]) -> Tuple[float, int, int, Dict[str, float]]:
    """Evaluate a combination across all conditions"""
    total_found = 0
    total_known = 0
    per_condition = {}

    for condition, known_ncts in condition_groups.items():
        strategy_results = all_results.get(condition, {})
        combined = set()
        for sid in combo:
            if sid in strategy_results:
                combined.update(strategy_results[sid])

        found = len(combined & known_ncts)
        total_found += found
        total_known += len(known_ncts)
        per_condition[condition] = found / len(known_ncts) * 100 if known_ncts else 0

    overall_recall = total_found / total_known * 100 if total_known > 0 else 0
    return overall_recall, total_found, total_known, per_condition

def run_deep_optimization():
    """Run deep optimization with focus on larger combinations"""
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")

    print("=" * 70)
    print("  DEEP CT.gov OPTIMIZER - EXHAUSTIVE COMBINATIONS")
    print("=" * 70)

    # Load data
    nct_file = output_dir / "recall_test_results.json"
    if not nct_file.exists():
        print("ERROR: No data file found")
        return

    with open(nct_file) as f:
        data = json.load(f)

    condition_groups = {k: set(v) for k, v in data.get("condition_groups", {}).items() if len(v) >= 3}

    print(f"\nLoaded {len(condition_groups)} conditions")
    print(f"Testing {len(TOP_STRATEGIES)} top strategies")

    # Phase 1: Search all strategies
    print("\nPhase 1: Searching strategies...")
    all_results = {}
    for i, (condition, known_ncts) in enumerate(condition_groups.items()):
        print(f"  [{i+1}/{len(condition_groups)}] {condition}...", end=" ", flush=True)
        results = search_all_strategies(condition)
        all_results[condition] = results

        combined = set()
        for ncts in results.values():
            combined.update(ncts)
        print(f"found {len(combined & known_ncts)}/{len(known_ncts)}")

    # Phase 2: Generate ALL combinations up to size 6
    print("\nPhase 2: Generating combinations...")
    strategy_ids = list(TOP_STRATEGIES.keys())

    all_combos = []
    for size in range(1, 7):  # 1 to 6
        combos = list(itertools.combinations(strategy_ids, size))
        all_combos.extend(combos)
        print(f"  Size {size}: {len(combos)} combinations")

    print(f"  Total: {len(all_combos)} combinations")

    # Phase 3: Evaluate all combinations
    print("\nPhase 3: Evaluating combinations...")
    results = []

    for i, combo in enumerate(all_combos):
        if i % 500 == 0:
            print(f"  Progress: {i}/{len(all_combos)}")

        recall, found, known, per_cond = evaluate_combo(combo, all_results, condition_groups)
        results.append({
            "combo": combo,
            "name": "+".join(combo),
            "size": len(combo),
            "recall": recall,
            "found": found,
            "known": known,
            "per_condition": per_cond
        })

    # Sort by recall
    results.sort(key=lambda x: x["recall"], reverse=True)

    # Display results
    print("\n" + "=" * 70)
    print("  TOP 30 COMBINATIONS")
    print("=" * 70)
    print(f"{'Rank':<5} {'Size':>4} {'Recall':>8} {'Found':>7} {'Combination'}")
    print("-" * 70)

    for i, r in enumerate(results[:30]):
        combo_str = r["name"][:40] + "..." if len(r["name"]) > 40 else r["name"]
        print(f"{i+1:<5} {r['size']:>4} {r['recall']:>7.2f}% {r['found']:>7} {combo_str}")

    # Best by size
    print("\n" + "=" * 70)
    print("  BEST BY COMBINATION SIZE")
    print("=" * 70)

    for size in range(1, 7):
        size_results = [r for r in results if r["size"] == size]
        if size_results:
            best = size_results[0]
            print(f"\nSize {size}: {best['name']}")
            print(f"  Recall: {best['recall']:.2f}% | Found: {best['found']}/{best['known']}")

    # Perfect conditions analysis
    print("\n" + "=" * 70)
    print("  100% RECALL CONDITIONS")
    print("=" * 70)

    winner = results[0]
    for cond, recall in winner["per_condition"].items():
        if recall == 100.0:
            print(f"  {cond}: 100%")

    # Problematic conditions
    print("\n" + "=" * 70)
    print("  CHALLENGING CONDITIONS (< 50% recall)")
    print("=" * 70)

    for cond, recall in winner["per_condition"].items():
        if recall < 50:
            known = len(condition_groups[cond])
            print(f"  {cond}: {recall:.1f}% ({int(recall*known/100)}/{known})")

    # Winner summary
    print("\n" + "=" * 70)
    print("  WINNER")
    print("=" * 70)
    print(f"\n  Combination: {winner['name']}")
    print(f"  Size: {winner['size']} strategies")
    print(f"  Recall: {winner['recall']:.2f}%")
    print(f"  Found: {winner['found']}/{winner['known']} NCT IDs")
    print(f"  Improvement over S3: +{winner['recall'] - 63.38:.2f}%")

    # API queries
    print("\n  API Queries to combine:")
    for sid in winner["combo"]:
        name, query = TOP_STRATEGIES[sid]
        print(f"    {sid} ({name}): {query[:50]}...")

    # Marginal gains analysis
    print("\n" + "=" * 70)
    print("  MARGINAL GAINS ANALYSIS")
    print("=" * 70)

    # Compare best of each size
    best_by_size = {}
    for size in range(1, 7):
        size_results = [r for r in results if r["size"] == size]
        if size_results:
            best_by_size[size] = size_results[0]

    prev_recall = 0
    for size in range(1, 7):
        if size in best_by_size:
            r = best_by_size[size]
            gain = r["recall"] - prev_recall
            print(f"  Size {size}: {r['recall']:.2f}% (+{gain:.2f}%)")
            prev_recall = r["recall"]

    # Save results
    output_file = output_dir / f"deep_optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    export = {
        "timestamp": datetime.now().isoformat(),
        "strategies_tested": len(TOP_STRATEGIES),
        "total_combinations": len(all_combos),
        "conditions": len(condition_groups),
        "winner": {
            "strategies": list(winner["combo"]),
            "name": winner["name"],
            "recall": winner["recall"],
            "found": winner["found"],
            "known": winner["known"],
            "per_condition": winner["per_condition"]
        },
        "best_by_size": {
            str(size): {
                "strategies": list(r["combo"]),
                "recall": r["recall"]
            }
            for size, r in best_by_size.items()
        },
        "top_100": [
            {
                "rank": i + 1,
                "strategies": list(r["combo"]),
                "recall": r["recall"],
                "found": r["found"]
            }
            for i, r in enumerate(results[:100])
        ]
    }

    with open(output_file, 'w') as f:
        json.dump(export, f, indent=2)

    print(f"\n  Results saved: {output_file}")

    return export

if __name__ == "__main__":
    run_deep_optimization()
