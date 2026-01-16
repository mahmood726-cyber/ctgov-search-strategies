#!/usr/bin/env python3
"""
NCT ID Validation and Recall Testing
Validates extracted NCT IDs exist on CT.gov and tests recall of search strategies
"""

import time
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ctgov_config import CTGOV_API, DEFAULT_RATE_LIMIT, DEFAULT_TIMEOUT
from ctgov_terms import normalize_condition
from ctgov_utils import (
    build_params,
    fetch_matching_nct_ids,
    fetch_total_count,
    get_session,
)

# Configuration
RATE_LIMIT = DEFAULT_RATE_LIMIT
TIMEOUT = DEFAULT_TIMEOUT

# Search strategies
STRATEGIES = {
    "S1": {
        "name": "Condition Only (Maximum Recall)",
        "build_query": lambda c: f"query.cond={quote(c)}"
    },
    "S2": {
        "name": "Interventional Studies",
        "build_query": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[StudyType]INTERVENTIONAL')}"
    },
    "S3": {
        "name": "Randomized Allocation Only",
        "build_query": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED')}"
    },
    "S4": {
        "name": "Phase 3/4 Studies",
        "build_query": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[Phase](PHASE3 OR PHASE4)')}"
    },
    "S5": {
        "name": "Has Posted Results",
        "build_query": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[ResultsFirstPostDate]RANGE[MIN,MAX]')}"
    },
    "S6": {
        "name": "Completed Status",
        "build_query": lambda c: f"query.cond={quote(c)}&filter.overallStatus=COMPLETED"
    },
    "S7": {
        "name": "Interventional + Completed",
        "build_query": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[StudyType]INTERVENTIONAL')}&filter.overallStatus=COMPLETED"
    },
    "S8": {
        "name": "RCT + Phase 3/4 + Completed",
        "build_query": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED AND AREA[Phase](PHASE3 OR PHASE4)')}&filter.overallStatus=COMPLETED"
    },
    "S9": {
        "name": "Full-Text RCT Keywords",
        "build_query": lambda c: f"query.term={quote(c + ' AND randomized AND controlled')}"
    },
    "S10": {
        "name": "Treatment RCTs Only",
        "build_query": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT')}"
    }
}

def validate_single_nct(nct_id: str) -> Dict:
    """Validate a single NCT ID exists on CT.gov and get study details"""
    nct_id = nct_id.strip().upper()

    if not nct_id.startswith("NCT") or len(nct_id) != 11:
        return {"nct_id": nct_id, "exists": False, "error": "Invalid format"}

    url = f"{CTGOV_API}/{nct_id}"

    try:
        session = get_session("CTgov-Validate/1.0")
        response = session.get(url, timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            # Extract key fields
            protocol = data.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            design_module = protocol.get("designModule", {})
            conditions_module = protocol.get("conditionsModule", {})

            return {
                "nct_id": nct_id,
                "exists": True,
                "title": id_module.get("briefTitle", ""),
                "status": status_module.get("overallStatus", ""),
                "study_type": design_module.get("studyType", ""),
                "phase": design_module.get("phases", []),
                "allocation": design_module.get("designInfo", {}).get("allocation", ""),
                "conditions": conditions_module.get("conditions", []),
                "error": None
            }
        elif response.status_code == 404:
            return {"nct_id": nct_id, "exists": False, "error": "Not found"}
        else:
            return {"nct_id": nct_id, "exists": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"nct_id": nct_id, "exists": False, "error": str(e)}

def validate_all_ncts(nct_ids: List[str]) -> Tuple[List[Dict], Dict]:
    """Validate all NCT IDs and return results with summary"""
    results = []
    valid_count = 0
    invalid_count = 0
    error_count = 0

    print(f"\nValidating {len(nct_ids)} NCT IDs against CT.gov...")
    print("=" * 60)

    for i, nct_id in enumerate(nct_ids, 1):
        result = validate_single_nct(nct_id)
        results.append(result)

        if result.get("exists"):
            valid_count += 1
        elif result.get("error") == "Not found":
            invalid_count += 1
        else:
            error_count += 1

        if i % 20 == 0:
            print(f"  Validated {i}/{len(nct_ids)} - Valid: {valid_count}, Invalid: {invalid_count}, Errors: {error_count}")

        time.sleep(RATE_LIMIT)

    summary = {
        "total": len(nct_ids),
        "valid": valid_count,
        "invalid": invalid_count,
        "errors": error_count,
        "validation_rate": valid_count / len(nct_ids) * 100 if nct_ids else 0
    }

    return results, summary

def get_condition_from_nct(validated_results: List[Dict]) -> Dict[str, List[str]]:
    """Group NCT IDs by their primary condition for recall testing"""
    condition_groups = {}

    for result in validated_results:
        if not result.get("exists"):
            continue

        conditions = result.get("conditions", [])
        if not conditions:
            continue

        # Use first condition as primary
        primary = conditions[0]
        normalized = normalize_condition(primary)
        if not normalized:
            continue

        if normalized not in condition_groups:
            condition_groups[normalized] = []
        condition_groups[normalized].append(result["nct_id"])

    return condition_groups

def search_ctgov(query: str, known_nct_ids: List[str]) -> Tuple[int, List[str]]:
    """Search CT.gov and return total count plus matched known NCT IDs."""
    try:
        params = build_params(query)
        session = get_session("CTgov-Validate/1.0")
        total = fetch_total_count(session, params, timeout=TIMEOUT)
        matched = fetch_matching_nct_ids(
            session, params, known_nct_ids, timeout=TIMEOUT
        )
        return total, sorted(matched)
    except Exception as e:
        print(f"    Search error: {e}")
        return 0, []

def calculate_recall(condition: str, known_nct_ids: List[str], strategy_id: str) -> Dict:
    """Calculate recall for a strategy against known NCT IDs"""
    if strategy_id not in STRATEGIES:
        return {"error": f"Unknown strategy: {strategy_id}"}

    strategy = STRATEGIES[strategy_id]
    query = strategy["build_query"](condition)

    total_count, found_nct_ids = search_ctgov(query, known_nct_ids)

    known_set = set(nct.upper() for nct in known_nct_ids)
    found_set = set(found_nct_ids)

    retrieved = known_set.intersection(found_set)
    missed = known_set - found_set

    recall = len(retrieved) / len(known_set) * 100 if known_set else 0

    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy["name"],
        "condition": condition,
        "total_results": total_count,
        "known_relevant": len(known_set),
        "retrieved": len(retrieved),
        "missed": len(missed),
        "recall_percent": recall,
        "retrieved_ids": list(retrieved),
        "missed_ids": list(missed)
    }

def test_recall_all_strategies(condition: str, known_nct_ids: List[str]) -> List[Dict]:
    """Test all strategies for recall against known NCT IDs"""
    results = []

    print(f"\n  Testing recall for '{condition}' ({len(known_nct_ids)} known studies)")

    for strategy_id in STRATEGIES:
        result = calculate_recall(condition, known_nct_ids, strategy_id)
        results.append(result)

        recall = result.get("recall_percent", 0)
        retrieved = result.get("retrieved", 0)
        total = result.get("total_results", 0)

        print(f"    {strategy_id}: Recall={recall:.1f}% ({retrieved}/{len(known_nct_ids)}) | Total={total:,}")

        time.sleep(RATE_LIMIT)

    return results

def main():
    # Paths
    base_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies")
    data_dir = base_dir / "data"
    output_dir = base_dir / "output"
    output_dir.mkdir(exist_ok=True)

    print("=" * 70)
    print("CT.gov NCT ID Validation and Recall Testing")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Load NCT IDs
    nct_file = data_dir / "nct_ids_list.txt"
    if not nct_file.exists():
        print(f"ERROR: NCT ID file not found: {nct_file}")
        return

    with open(nct_file, 'r') as f:
        raw_ncts = [line.strip() for line in f if line.strip()]
    nct_ids = list(dict.fromkeys(raw_ncts))

    print(f"\nLoaded {len(nct_ids)} NCT IDs from Cochrane reviews")

    # Step 1: Validate all NCT IDs
    print("\n" + "=" * 70)
    print("STEP 1: Validating NCT IDs on CT.gov")
    print("=" * 70)

    validated_results, validation_summary = validate_all_ncts(nct_ids)

    print(f"\nValidation Summary:")
    print(f"  Total: {validation_summary['total']}")
    print(f"  Valid: {validation_summary['valid']} ({validation_summary['validation_rate']:.1f}%)")
    print(f"  Not Found: {validation_summary['invalid']}")
    print(f"  Errors: {validation_summary['errors']}")

    # Save validation results
    validation_file = output_dir / "nct_validation_results.json"
    with open(validation_file, 'w') as f:
        json.dump({
            "summary": validation_summary,
            "results": validated_results,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)
    print(f"\nSaved validation results: {validation_file}")

    # Get valid NCT IDs
    valid_ncts = [r for r in validated_results if r.get("exists")]

    if not valid_ncts:
        print("ERROR: No valid NCT IDs found. Cannot proceed with recall testing.")
        return

    # Step 2: Group by condition
    print("\n" + "=" * 70)
    print("STEP 2: Grouping Studies by Condition")
    print("=" * 70)

    condition_groups = get_condition_from_nct(valid_ncts)

    print(f"\nCondition groups found:")
    for condition, ncts in sorted(condition_groups.items(), key=lambda x: -len(x[1])):
        print(f"  {condition}: {len(ncts)} studies")

    # Step 3: Test recall for each condition with sufficient studies
    print("\n" + "=" * 70)
    print("STEP 3: Testing Recall by Strategy")
    print("=" * 70)

    MIN_STUDIES = 3  # Minimum studies for meaningful recall
    all_recall_results = []

    for condition, ncts in sorted(condition_groups.items(), key=lambda x: -len(x[1])):
        if len(ncts) < MIN_STUDIES:
            print(f"\n  Skipping '{condition}' (only {len(ncts)} studies, need {MIN_STUDIES}+)")
            continue

        recall_results = test_recall_all_strategies(condition, ncts)
        all_recall_results.extend(recall_results)

    # Step 4: Summary statistics
    print("\n" + "=" * 70)
    print("STEP 4: Overall Recall Summary")
    print("=" * 70)

    # Aggregate by strategy
    strategy_aggregates = {}
    for result in all_recall_results:
        sid = result["strategy_id"]
        if sid not in strategy_aggregates:
            strategy_aggregates[sid] = {
                "name": result["strategy_name"],
                "recalls": [],
                "total_known": 0,
                "total_retrieved": 0
            }
        strategy_aggregates[sid]["recalls"].append(result["recall_percent"])
        strategy_aggregates[sid]["total_known"] += result["known_relevant"]
        strategy_aggregates[sid]["total_retrieved"] += result["retrieved"]

    print("\nAverage Recall by Strategy:")
    print("-" * 60)
    print(f"{'Strategy':<6} {'Name':<35} {'Avg Recall':>10} {'Overall':>10}")
    print("-" * 60)

    for sid in sorted(strategy_aggregates.keys()):
        agg = strategy_aggregates[sid]
        avg_recall = sum(agg["recalls"]) / len(agg["recalls"]) if agg["recalls"] else 0
        overall_recall = agg["total_retrieved"] / agg["total_known"] * 100 if agg["total_known"] > 0 else 0
        print(f"{sid:<6} {agg['name']:<35} {avg_recall:>9.1f}% {overall_recall:>9.1f}%")

    # Save all results
    recall_file = output_dir / "recall_test_results.json"
    with open(recall_file, 'w') as f:
        json.dump({
            "condition_groups": {k: v for k, v in condition_groups.items()},
            "strategy_aggregates": strategy_aggregates,
            "detailed_results": all_recall_results,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)
    print(f"\nSaved recall results: {recall_file}")

    # Generate CSV summary
    csv_file = output_dir / "recall_summary.csv"
    with open(csv_file, 'w') as f:
        f.write("strategy_id,strategy_name,condition,total_results,known_relevant,retrieved,missed,recall_percent\n")
        for r in all_recall_results:
            f.write(f"{r['strategy_id']},{r['strategy_name']},{r['condition']},{r['total_results']},{r['known_relevant']},{r['retrieved']},{r['missed']},{r['recall_percent']:.1f}\n")
    print(f"Saved recall CSV: {csv_file}")

    print("\n" + "=" * 70)
    print("VALIDATION AND RECALL TESTING COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
