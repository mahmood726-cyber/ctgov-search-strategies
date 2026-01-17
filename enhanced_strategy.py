#!/usr/bin/env python3
"""
Enhanced CT.gov Search Strategy
- Multi-term condition expansion
- Specific term searches for maximum recall
- Final optimized approach
"""

import json
import time
import concurrent.futures
import threading
from typing import Dict, Set, List, Tuple
from urllib.parse import quote
from datetime import datetime
from pathlib import Path

from ctgov_config import DEFAULT_TIMEOUT
from ctgov_utils import build_params, fetch_nct_ids, get_session

MAX_WORKERS = 10
TIMEOUT = DEFAULT_TIMEOUT

cache = {}
cache_lock = threading.Lock()

# Condition term expansions for comprehensive coverage
CONDITION_EXPANSIONS = {
    "stroke": [
        "stroke", "cerebrovascular stroke", "cerebral stroke",
        "cerebrovascular accident", "CVA", "ischemic stroke",
        "hemorrhagic stroke", "acute ischemic stroke", "brain infarction",
        "cerebral infarction", "brain ischemia", "intracranial hemorrhage"
    ],
    "cancer": [
        "cancer", "neoplasm", "carcinoma", "malignancy", "tumor",
        "malignant neoplasm", "adenocarcinoma", "sarcoma",
        "urothelial cancer", "bladder cancer", "urothelial carcinoma",
        "stomach neoplasms", "colorectal neoplasms", "mesothelioma",
        "breast cancer", "lung cancer", "prostate cancer", "colon cancer",
        "lymphoma", "leukemia", "melanoma", "glioblastoma", "pancreatic cancer"
    ],
    "covid-19": [
        "covid-19", "covid19", "coronavirus", "SARS-CoV-2",
        "coronavirus infection", "2019-nCoV", "SARS-CoV 2",
        "COVID", "novel coronavirus", "respiratory infection"
    ],
    "postoperative pain": [
        "postoperative pain", "post-operative pain", "surgical pain",
        "postsurgical pain", "acute pain", "pain management",
        "analgesia", "pain after surgery", "operative pain"
    ],
    "obesity": [
        "obesity", "obese", "overweight", "body mass index",
        "weight loss", "bariatric", "morbid obesity"
    ],
    "diabetes": [
        "diabetes", "diabetes mellitus", "type 2 diabetes",
        "type 1 diabetes", "diabetic", "hyperglycemia"
    ],
    "hypertension": [
        "hypertension", "high blood pressure", "elevated blood pressure",
        "arterial hypertension"
    ]
}

# Core search strategies
CORE_STRATEGIES = {
    "S3": "query.term=AREA[DesignAllocation]RANDOMIZED",
    "S5": "query.term=AREA[ResultsFirstPostDate]RANGE[MIN,MAX]",
    "S10": "query.term=AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT",
    "C_RCT_COMP": "query.term=AREA[DesignAllocation]RANDOMIZED&filter.overallStatus=COMPLETED",
}


def search_single(query: str) -> Set[str]:
    """Execute search and return NCT IDs"""
    with cache_lock:
        if query in cache:
            return cache[query]

    try:
        params = build_params(query)
        session = get_session("CTgov-Enhanced/1.0")
        ncts, _ = fetch_nct_ids(session, params, timeout=TIMEOUT, page_size=1000)
        with cache_lock:
            cache[query] = ncts
        return ncts
    except Exception:
        pass
    return set()


def search_parallel(queries: List[str]) -> Dict[str, Set[str]]:
    """Search multiple queries in parallel"""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(search_single, q): q for q in queries}
        for f in concurrent.futures.as_completed(futures):
            q = futures[f]
            try:
                results[q] = f.result()
            except Exception:
                results[q] = set()
    return results


def enhanced_search(condition: str, use_rct_filter: bool = True) -> Set[str]:
    """
    Enhanced search combining:
    1. Main condition term
    2. Expanded synonyms
    3. RCT filters (if requested)
    """
    all_ncts = set()

    # Get expanded terms
    condition_lower = condition.lower()
    terms = CONDITION_EXPANSIONS.get(condition_lower, [condition])
    if condition_lower not in terms:
        terms.append(condition)

    # Build queries
    queries = []

    # Condition searches (all terms)
    for term in terms:
        queries.append(f"query.cond={quote(term)}")

    # Term searches (full text)
    for term in terms:
        queries.append(f"query.term={quote(term)}")

    # Execute in parallel
    results = search_parallel(queries)
    for ncts in results.values():
        all_ncts.update(ncts)

    # If RCT filter requested, also search with RCT constraints
    if use_rct_filter:
        for term in terms[:3]:  # Top 3 terms with RCT filters
            for strat_name, strat_query in CORE_STRATEGIES.items():
                query = f"query.cond={quote(term)}&{strat_query}"
                queries.append(query)

        rct_results = search_parallel(queries)
        for ncts in rct_results.values():
            all_ncts.update(ncts)

    return all_ncts


def test_enhanced_strategy():
    """Test the enhanced strategy against known NCT IDs"""
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")

    print("=" * 70)
    print("  ENHANCED CT.gov SEARCH STRATEGY TEST")
    print("=" * 70)

    # Load known NCT IDs
    nct_file = output_dir / "recall_test_results.json"
    with open(nct_file) as f:
        data = json.load(f)

    condition_groups = {k: set(v) for k, v in data.get("condition_groups", {}).items() if len(v) >= 3}

    print(f"\nTesting {len(condition_groups)} conditions")

    results = []
    total_found = 0
    total_known = 0

    for condition, known_ncts in condition_groups.items():
        print(f"\n  {condition}...", end=" ", flush=True)

        start = time.time()
        found = enhanced_search(condition, use_rct_filter=True)
        elapsed = time.time() - start

        overlap = found & known_ncts
        recall = len(overlap) / len(known_ncts) * 100

        total_found += len(overlap)
        total_known += len(known_ncts)

        results.append({
            "condition": condition,
            "known": len(known_ncts),
            "found": len(overlap),
            "recall": recall,
            "time": elapsed
        })

        status = "OK" if recall >= 80 else "LOW" if recall >= 50 else "POOR"
        print(f"{recall:.1f}% ({len(overlap)}/{len(known_ncts)}) [{status}] {elapsed:.1f}s")

    # Summary
    overall_recall = total_found / total_known * 100

    print("\n" + "=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)

    # Sort by recall
    results.sort(key=lambda x: x["recall"], reverse=True)

    print(f"\n  {'Condition':<25} {'Recall':>8} {'Found':>8}")
    print("-" * 50)
    for r in results:
        print(f"  {r['condition']:<25} {r['recall']:>7.1f}% {r['found']:>5}/{r['known']}")

    print("-" * 50)
    print(f"  {'OVERALL':<25} {overall_recall:>7.1f}% {total_found:>5}/{total_known}")

    # Comparison with previous best
    print("\n  Previous best (C2): 74.65%")
    print(f"  Enhanced strategy: {overall_recall:.2f}%")
    print(f"  Improvement: +{overall_recall - 74.65:.2f}%")

    # Conditions still below 80%
    low_recall = [r for r in results if r["recall"] < 80]
    if low_recall:
        print("\n  Conditions still below 80% recall:")
        for r in low_recall:
            print(f"    - {r['condition']}: {r['recall']:.1f}%")

    # Save results
    output_file = output_dir / f"enhanced_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    export = {
        "timestamp": datetime.now().isoformat(),
        "overall_recall": overall_recall,
        "total_found": total_found,
        "total_known": total_known,
        "improvement_over_c2": overall_recall - 74.65,
        "per_condition": results
    }

    with open(output_file, 'w') as f:
        json.dump(export, f, indent=2)

    print(f"\n  Results saved: {output_file}")

    return export


if __name__ == "__main__":
    test_enhanced_strategy()
