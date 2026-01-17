#!/usr/bin/env python3
"""
CT.gov Search Strategy Optimizer - 1000 Scenario Analysis
Tests exhaustive combinations to maximize recall
"""

import json
import time
import concurrent.futures
import itertools
import random
import threading
from typing import List, Dict, Set, Tuple
from urllib.parse import quote
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

from ctgov_config import DEFAULT_TIMEOUT
from ctgov_utils import build_params, fetch_nct_ids, get_session

MAX_WORKERS = 8
TIMEOUT = DEFAULT_TIMEOUT

# Extended base strategies with variations
BASE_STRATEGIES = {
    # Core strategies
    "S1": ("Condition", "query.cond={c}"),
    "S2": ("Interventional", "query.cond={c}&query.term=AREA[StudyType]INTERVENTIONAL"),
    "S3": ("Randomized", "query.cond={c}&query.term=AREA[DesignAllocation]RANDOMIZED"),
    "S4": ("Phase3_4", "query.cond={c}&query.term=AREA[Phase](PHASE3 OR PHASE4)"),
    "S5": ("HasResults", "query.cond={c}&query.term=AREA[ResultsFirstPostDate]RANGE[MIN,MAX]"),
    "S6": ("Completed", "query.cond={c}&filter.overallStatus=COMPLETED"),
    "S10": ("TreatmentRCT", "query.cond={c}&query.term=AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT"),

    # Phase variations
    "P1": ("Phase1", "query.cond={c}&query.term=AREA[Phase]PHASE1"),
    "P2": ("Phase2", "query.cond={c}&query.term=AREA[Phase]PHASE2"),
    "P3": ("Phase3", "query.cond={c}&query.term=AREA[Phase]PHASE3"),
    "P4": ("Phase4", "query.cond={c}&query.term=AREA[Phase]PHASE4"),
    "P23": ("Phase2_3", "query.cond={c}&query.term=AREA[Phase](PHASE2 OR PHASE3)"),
    "P234": ("Phase2_3_4", "query.cond={c}&query.term=AREA[Phase](PHASE2 OR PHASE3 OR PHASE4)"),

    # Status variations
    "ST1": ("Recruiting", "query.cond={c}&filter.overallStatus=RECRUITING"),
    "ST2": ("Active", "query.cond={c}&filter.overallStatus=ACTIVE_NOT_RECRUITING"),
    "ST3": ("Terminated", "query.cond={c}&filter.overallStatus=TERMINATED"),
    "ST4": ("CompletedOrTerm", "query.cond={c}&query.term=AREA[OverallStatus](COMPLETED OR TERMINATED)"),

    # Purpose variations
    "PU1": ("Treatment", "query.cond={c}&query.term=AREA[DesignPrimaryPurpose]TREATMENT"),
    "PU2": ("Prevention", "query.cond={c}&query.term=AREA[DesignPrimaryPurpose]PREVENTION"),
    "PU3": ("Diagnostic", "query.cond={c}&query.term=AREA[DesignPrimaryPurpose]DIAGNOSTIC"),
    "PU4": ("TreatOrPrev", "query.cond={c}&query.term=AREA[DesignPrimaryPurpose](TREATMENT OR PREVENTION)"),

    # Allocation variations
    "AL1": ("NonRandom", "query.cond={c}&query.term=AREA[DesignAllocation]NON_RANDOMIZED"),
    "AL2": ("AnyAlloc", "query.cond={c}&query.term=AREA[DesignAllocation](RANDOMIZED OR NON_RANDOMIZED)"),

    # Masking variations
    "M1": ("DoubleBlind", "query.cond={c}&query.term=AREA[DesignMasking]DOUBLE"),
    "M2": ("SingleBlind", "query.cond={c}&query.term=AREA[DesignMasking]SINGLE"),
    "M3": ("OpenLabel", "query.cond={c}&query.term=AREA[DesignMasking]NONE"),
    "M4": ("AnyBlind", "query.cond={c}&query.term=AREA[DesignMasking](DOUBLE OR SINGLE OR TRIPLE)"),

    # Intervention type
    "I1": ("Drug", "query.cond={c}&query.term=AREA[InterventionType]DRUG"),
    "I2": ("Device", "query.cond={c}&query.term=AREA[InterventionType]DEVICE"),
    "I3": ("Biological", "query.cond={c}&query.term=AREA[InterventionType]BIOLOGICAL"),
    "I4": ("Procedure", "query.cond={c}&query.term=AREA[InterventionType]PROCEDURE"),
    "I5": ("DrugOrBio", "query.cond={c}&query.term=AREA[InterventionType](DRUG OR BIOLOGICAL)"),

    # Results posted
    "R1": ("ResultsYes", "query.cond={c}&filter.resultsFirstPostDate=true"),

    # Enrollment size (using term search)
    "E1": ("Large100", "query.cond={c}&query.term=AREA[EnrollmentCount]RANGE[100,MAX]"),
    "E2": ("Large500", "query.cond={c}&query.term=AREA[EnrollmentCount]RANGE[500,MAX]"),

    # Sponsor type
    "SP1": ("Industry", "query.cond={c}&query.term=AREA[LeadSponsorClass]INDUSTRY"),
    "SP2": ("NIH", "query.cond={c}&query.term=AREA[LeadSponsorClass]NIH"),
    "SP3": ("Academic", "query.cond={c}&query.term=AREA[LeadSponsorClass](NETWORK OR OTHER)"),

    # Compound strategies
    "C_RCT_COMP": ("RCT+Completed", "query.cond={c}&query.term=AREA[DesignAllocation]RANDOMIZED&filter.overallStatus=COMPLETED"),
    "C_RCT_RES": ("RCT+Results", "query.cond={c}&query.term=AREA[DesignAllocation]RANDOMIZED AND AREA[ResultsFirstPostDate]RANGE[MIN,MAX]"),
    "C_INT_RCT": ("Interv+RCT", "query.cond={c}&query.term=AREA[StudyType]INTERVENTIONAL AND AREA[DesignAllocation]RANDOMIZED"),
    "C_DB_RCT": ("DoubleBlind+RCT", "query.cond={c}&query.term=AREA[DesignAllocation]RANDOMIZED AND AREA[DesignMasking]DOUBLE"),
    "C_TREAT_DB": ("Treatment+DB", "query.cond={c}&query.term=AREA[DesignPrimaryPurpose]TREATMENT AND AREA[DesignMasking]DOUBLE"),
    "C_DRUG_RCT": ("Drug+RCT", "query.cond={c}&query.term=AREA[InterventionType]DRUG AND AREA[DesignAllocation]RANDOMIZED"),
    "C_P34_RCT": ("Phase34+RCT", "query.cond={c}&query.term=AREA[Phase](PHASE3 OR PHASE4) AND AREA[DesignAllocation]RANDOMIZED"),
    "C_LARGE_RCT": ("Large+RCT", "query.cond={c}&query.term=AREA[DesignAllocation]RANDOMIZED AND AREA[EnrollmentCount]RANGE[100,MAX]"),
}

cache = {}
cache_lock = threading.Lock()


@dataclass
class ScenarioResult:
    scenario_id: int
    strategy_combo: Tuple[str, ...]
    combo_name: str
    recall: float
    found: int
    known: int
    unique_ncts: int


def search_strategy(condition: str, strategy_id: str) -> Set[str]:
    """Search and return NCT IDs"""
    cache_key = f"{condition}:{strategy_id}"
    with cache_lock:
        if cache_key in cache:
            return cache[cache_key]

    if strategy_id not in BASE_STRATEGIES:
        return set()

    _, query_template = BASE_STRATEGIES[strategy_id]
    query = query_template.replace("{c}", quote(condition))
    try:
        params = build_params(query)
        session = get_session("CTgov-Optimizer/1.0")
        ncts, _ = fetch_nct_ids(session, params, timeout=TIMEOUT, page_size=1000)
        with cache_lock:
            cache[cache_key] = ncts
        return ncts
    except Exception:
        pass
    return set()


def search_parallel_batch(condition: str, strategy_ids: List[str]) -> Dict[str, Set[str]]:
    """Search multiple strategies in parallel"""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(search_strategy, condition, sid): sid for sid in strategy_ids}
        for f in concurrent.futures.as_completed(futures):
            sid = futures[f]
            try:
                results[sid] = f.result()
            except Exception:
                results[sid] = set()
    return results


def evaluate_combo(combo: Tuple[str, ...], strategy_results: Dict[str, Set[str]], known_ncts: Set[str]) -> ScenarioResult:
    """Evaluate a combination of strategies"""
    combined = set()
    for sid in combo:
        if sid in strategy_results:
            combined.update(strategy_results[sid])

    found = len(combined & known_ncts)
    recall = found / len(known_ncts) * 100 if known_ncts else 0

    combo_name = "+".join(combo)
    return ScenarioResult(
        scenario_id=0,
        strategy_combo=combo,
        combo_name=combo_name,
        recall=recall,
        found=found,
        known=len(known_ncts),
        unique_ncts=len(combined)
    )


def generate_all_combinations(strategies: List[str], max_combo_size: int = 4) -> List[Tuple[str, ...]]:
    """Generate all possible strategy combinations"""
    combos = []
    for size in range(1, max_combo_size + 1):
        for combo in itertools.combinations(strategies, size):
            combos.append(combo)
    return combos


def run_optimization(output_dir: Path, max_scenarios: int = 1000):
    """Run 1000 scenario optimization"""
    print("=" * 70)
    print("  CT.gov SEARCH STRATEGY OPTIMIZER - 1000 SCENARIOS")
    print("=" * 70)

    # Load known NCT IDs
    nct_file = output_dir / "recall_test_results.json"
    if not nct_file.exists():
        print("ERROR: No recall data found. Run validate_and_recall.py first.")
        return

    with open(nct_file) as f:
        data = json.load(f)

    condition_groups = {k: set(v) for k, v in data.get("condition_groups", {}).items() if len(v) >= 3}
    all_known_ncts = set()
    for ncts in condition_groups.values():
        all_known_ncts.update(ncts)

    print(f"\nLoaded {len(condition_groups)} conditions with {len(all_known_ncts)} total known NCT IDs")
    print(f"Testing {len(BASE_STRATEGIES)} base strategies")

    # Generate scenarios (combinations)
    all_strategy_ids = list(BASE_STRATEGIES.keys())

    # Generate systematic combinations
    print("\nGenerating strategy combinations...")
    all_combos = []

    # Singles
    for sid in all_strategy_ids:
        all_combos.append((sid,))

    # Pairs - all pairs
    for combo in itertools.combinations(all_strategy_ids, 2):
        all_combos.append(combo)

    # Triples - sample to keep manageable
    triple_combos = list(itertools.combinations(all_strategy_ids, 3))
    if len(triple_combos) > 300:
        random.seed(42)
        triple_combos = random.sample(triple_combos, 300)
    all_combos.extend(triple_combos)

    # Quads - sample
    quad_combos = list(itertools.combinations(all_strategy_ids, 4))
    if len(quad_combos) > 200:
        random.seed(42)
        quad_combos = random.sample(quad_combos, 200)
    all_combos.extend(quad_combos)

    # Limit to max_scenarios
    if len(all_combos) > max_scenarios:
        # Keep all singles and pairs, sample rest
        singles_pairs = [c for c in all_combos if len(c) <= 2]
        rest = [c for c in all_combos if len(c) > 2]
        random.seed(42)
        remaining_slots = max(0, max_scenarios - len(singles_pairs))
        if remaining_slots > 0 and len(rest) > remaining_slots:
            rest = random.sample(rest, remaining_slots)
        all_combos = singles_pairs + rest
        all_combos = all_combos[:max_scenarios]  # Final cap

    print(f"Testing {len(all_combos)} scenario combinations")

    # Search all base strategies for all conditions
    print("\nPhase 1: Searching all strategies across conditions...")
    all_results = {}  # condition -> {strategy_id -> set of NCTs}

    start_time = time.time()
    for i, (condition, known_ncts) in enumerate(condition_groups.items()):
        print(f"  [{i + 1}/{len(condition_groups)}] {condition}...", end=" ", flush=True)
        results = search_parallel_batch(condition, all_strategy_ids)
        all_results[condition] = results

        # Quick stats
        total_found = set()
        for ncts in results.values():
            total_found.update(ncts)
        overlap = len(total_found & known_ncts)
        print(f"found {overlap}/{len(known_ncts)}")

    search_time = time.time() - start_time
    print(f"\nSearch completed in {search_time:.1f}s")

    # Phase 2: Evaluate all combinations
    print(f"\nPhase 2: Evaluating {len(all_combos)} scenarios...")

    scenario_results = []

    for scenario_id, combo in enumerate(all_combos):
        if scenario_id % 100 == 0:
            print(f"  Progress: {scenario_id}/{len(all_combos)}")

        # Aggregate across all conditions
        total_found = 0
        total_known = 0

        for condition, known_ncts in condition_groups.items():
            strategy_results = all_results.get(condition, {})
            result = evaluate_combo(combo, strategy_results, known_ncts)
            total_found += result.found
            total_known += result.known

        overall_recall = total_found / total_known * 100 if total_known > 0 else 0

        scenario_results.append(ScenarioResult(
            scenario_id=scenario_id,
            strategy_combo=combo,
            combo_name="+".join(combo),
            recall=overall_recall,
            found=total_found,
            known=total_known,
            unique_ncts=0  # Not tracked for overall
        ))

    # Sort by recall
    scenario_results.sort(key=lambda x: x.recall, reverse=True)

    # Display top 50
    print("\n" + "=" * 70)
    print("  TOP 50 SCENARIOS BY RECALL")
    print("=" * 70)
    print(f"{'Rank':<6} {'Recall':>8} {'Found':>8} {'Scenario'}")
    print("-" * 70)

    for i, result in enumerate(scenario_results[:50]):
        combo_str = result.combo_name[:45] + "..." if len(result.combo_name) > 45 else result.combo_name
        print(f"{i + 1:<6} {result.recall:>7.2f}% {result.found:>8} {combo_str}")

    # Analysis by combo size
    print("\n" + "=" * 70)
    print("  BEST BY COMBINATION SIZE")
    print("=" * 70)

    for size in range(1, 5):
        size_results = [r for r in scenario_results if len(r.strategy_combo) == size]
        if size_results:
            best = size_results[0]
            print(f"\nSize {size} (best of {len(size_results)}):")
            print(f"  {best.combo_name}")
            print(f"  Recall: {best.recall:.2f}% | Found: {best.found}/{best.known}")

    # Find most impactful strategies
    print("\n" + "=" * 70)
    print("  STRATEGY IMPACT ANALYSIS")
    print("=" * 70)

    strategy_impact = {}
    for sid in all_strategy_ids:
        with_strategy = [r.recall for r in scenario_results if sid in r.strategy_combo]
        without_strategy = [r.recall for r in scenario_results if sid not in r.strategy_combo]

        avg_with = sum(with_strategy) / len(with_strategy) if with_strategy else 0
        avg_without = sum(without_strategy) / len(without_strategy) if without_strategy else 0
        impact = avg_with - avg_without

        strategy_impact[sid] = {
            "name": BASE_STRATEGIES[sid][0],
            "avg_recall_when_included": avg_with,
            "impact": impact,
            "in_top_10": sum(1 for r in scenario_results[:10] if sid in r.strategy_combo)
        }

    # Sort by impact
    sorted_impact = sorted(strategy_impact.items(), key=lambda x: x[1]["impact"], reverse=True)

    print(f"\n{'Strategy':<12} {'Name':<15} {'Impact':>8} {'In Top10':>10}")
    print("-" * 50)
    for sid, data in sorted_impact[:15]:
        print(f"{sid:<12} {data['name'][:15]:<15} {data['impact']:>+7.2f}% {data['in_top_10']:>10}")

    # Winner
    winner = scenario_results[0]
    print("\n" + "=" * 70)
    print("  WINNER")
    print("=" * 70)
    print(f"\n  Scenario: {winner.combo_name}")
    print(f"  Recall: {winner.recall:.2f}%")
    print(f"  Found: {winner.found}/{winner.known} NCT IDs")
    print(f"  Improvement over S3 alone: +{winner.recall - 63.2:.2f}%")

    # Generate API query for winner
    print("\n  API Queries:")
    for sid in winner.strategy_combo:
        name, query = BASE_STRATEGIES[sid]
        print(f"    {sid}: {query[:60]}...")

    # Save results
    output_file = output_dir / f"optimization_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    export_data = {
        "timestamp": datetime.now().isoformat(),
        "total_scenarios": len(all_combos),
        "conditions_tested": len(condition_groups),
        "total_known_ncts": len(all_known_ncts),
        "search_time_seconds": search_time,
        "winner": {
            "strategies": list(winner.strategy_combo),
            "combo_name": winner.combo_name,
            "recall": winner.recall,
            "found": winner.found,
            "known": winner.known
        },
        "top_50": [
            {
                "rank": i + 1,
                "strategies": list(r.strategy_combo),
                "recall": r.recall,
                "found": r.found
            }
            for i, r in enumerate(scenario_results[:50])
        ],
        "strategy_impact": {
            sid: {
                "name": data["name"],
                "impact": data["impact"],
                "in_top_10": data["in_top_10"]
            }
            for sid, data in sorted_impact
        },
        "base_strategies": {
            sid: {"name": name, "query": query}
            for sid, (name, query) in BASE_STRATEGIES.items()
        }
    }

    with open(output_file, 'w') as f:
        json.dump(export_data, f, indent=2)

    print(f"\n  Results saved: {output_file}")

    return export_data


if __name__ == "__main__":
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")
    output_dir.mkdir(exist_ok=True)
    run_optimization(output_dir, max_scenarios=1000)
