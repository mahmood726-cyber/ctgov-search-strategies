#!/usr/bin/env python3
"""
Maximum Recall Strategy - Push to highest possible recall
Uses every available search approach
"""

import json
import time
import concurrent.futures
import threading
from typing import Dict, Set, List
from urllib.parse import quote
from datetime import datetime
from pathlib import Path

from ctgov_config import DEFAULT_TIMEOUT
from ctgov_utils import build_params, fetch_nct_ids, get_session

MAX_WORKERS = 15
TIMEOUT = DEFAULT_TIMEOUT

cache = {}
cache_lock = threading.Lock()

# Extensive condition expansions
EXPANSIONS = {
    "stroke": [
        "stroke", "cerebrovascular stroke", "cerebral stroke", "cerebrovascular accident",
        "CVA", "ischemic stroke", "hemorrhagic stroke", "acute ischemic stroke",
        "brain infarction", "cerebral infarction", "brain ischemia", "intracranial hemorrhage",
        "cerebral hemorrhage", "subarachnoid hemorrhage", "TIA", "transient ischemic attack",
        "cerebrovascular disease", "hemiplegia", "hemiparesis", "apoplexy",
        "brain attack", "cerebral ischemia", "intracerebral hemorrhage"
    ],
    "cancer": [
        "cancer", "neoplasm", "carcinoma", "malignancy", "tumor", "tumour",
        "malignant neoplasm", "adenocarcinoma", "sarcoma", "oncology",
        "urothelial cancer", "bladder cancer", "urothelial carcinoma",
        "stomach neoplasms", "colorectal neoplasms", "mesothelioma",
        "breast cancer", "lung cancer", "prostate cancer", "colon cancer",
        "lymphoma", "leukemia", "melanoma", "glioblastoma", "pancreatic cancer",
        "ovarian cancer", "cervical cancer", "renal cell carcinoma", "hepatocellular",
        "esophageal cancer", "gastric cancer", "colorectal cancer", "rectal cancer"
    ],
    "covid-19": [
        "covid-19", "covid19", "covid 19", "coronavirus", "SARS-CoV-2", "sars-cov-2",
        "coronavirus infection", "2019-nCoV", "SARS-CoV 2", "COVID", "corona virus",
        "novel coronavirus", "respiratory infection", "coronavirus disease",
        "coronavirus disease 2019", "severe acute respiratory syndrome coronavirus 2",
        "pandemic", "SARS coronavirus 2"
    ],
    "postoperative pain": [
        "postoperative pain", "post-operative pain", "post operative pain",
        "surgical pain", "postsurgical pain", "post-surgical pain",
        "acute pain", "pain management", "analgesia", "pain after surgery",
        "operative pain", "perioperative pain", "postop pain", "postoperative analgesia",
        "acute postoperative pain", "surgery pain", "procedural pain"
    ],
    "obesity": [
        "obesity", "obese", "overweight", "body mass index", "BMI",
        "weight loss", "bariatric", "morbid obesity", "adiposity",
        "metabolic syndrome", "weight management", "weight reduction"
    ]
}

def search(query: str) -> Set[str]:
    """Execute search"""
    with cache_lock:
        if query in cache:
            return cache[query]

    try:
        params = build_params(query)
        session = get_session("CTgov-MaxRecall/1.0")
        ncts, _ = fetch_nct_ids(session, params, timeout=TIMEOUT, page_size=1000)
        with cache_lock:
            cache[query] = ncts
        return ncts
    except:
        pass
    return set()

def search_parallel(queries: List[str]) -> Set[str]:
    """Search in parallel and combine results"""
    all_ncts = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(search, q) for q in queries]
        for f in concurrent.futures.as_completed(futures):
            try:
                all_ncts.update(f.result())
            except:
                pass
    return all_ncts

def max_recall_search(condition: str) -> Set[str]:
    """Maximum recall search using all methods"""
    queries = []
    condition_lower = condition.lower()
    terms = EXPANSIONS.get(condition_lower, [condition])

    # Method 1: Condition field searches
    for term in terms:
        queries.append(f"query.cond={quote(term)}")

    # Method 2: Full text searches
    for term in terms:
        queries.append(f"query.term={quote(term)}")

    # Method 3: Title searches
    for term in terms[:10]:
        queries.append(f"query.titles={quote(term)}")

    # Method 4: Intervention searches
    for term in terms[:5]:
        queries.append(f"query.intr={quote(term)}")

    # Method 5: RCT-filtered condition searches
    for term in terms[:8]:
        queries.append(f"query.cond={quote(term)}&query.term=AREA[DesignAllocation]RANDOMIZED")

    # Method 6: Completed study searches
    for term in terms[:8]:
        queries.append(f"query.cond={quote(term)}&filter.overallStatus=COMPLETED")

    # Method 7: Results posted searches
    for term in terms[:8]:
        queries.append(f"query.cond={quote(term)}&query.term=AREA[ResultsFirstPostDate]RANGE[MIN,MAX]")

    # Method 8: Specific field AREA searches
    for term in terms[:5]:
        queries.append(f"query.term=AREA[BriefTitle]{quote(term)}")
        queries.append(f"query.term=AREA[Keyword]{quote(term)}")

    # Method 9: OR queries for multiple terms
    if len(terms) > 3:
        or_terms = " OR ".join([f'"{t}"' for t in terms[:5]])
        queries.append(f"query.cond={quote(or_terms)}")
        queries.append(f"query.term={quote(or_terms)}")

    return search_parallel(queries)

def test_max_recall():
    """Test maximum recall strategy"""
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")

    print("=" * 70)
    print("  MAXIMUM RECALL STRATEGY TEST")
    print("=" * 70)

    nct_file = output_dir / "recall_test_results.json"
    with open(nct_file) as f:
        data = json.load(f)

    condition_groups = {k: set(v) for k, v in data.get("condition_groups", {}).items() if len(v) >= 3}

    print(f"\nTesting {len(condition_groups)} conditions with aggressive search")

    results = []
    total_found = 0
    total_known = 0

    for condition, known_ncts in condition_groups.items():
        print(f"\n  {condition}...", end=" ", flush=True)

        start = time.time()
        found = max_recall_search(condition)
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
            "time": elapsed,
            "missed": list(known_ncts - overlap)
        })

        status = "PERFECT" if recall == 100 else "OK" if recall >= 80 else "LOW"
        print(f"{recall:.1f}% ({len(overlap)}/{len(known_ncts)}) [{status}] {elapsed:.1f}s")

    overall_recall = total_found / total_known * 100

    print("\n" + "=" * 70)
    print("  FINAL RESULTS")
    print("=" * 70)

    results.sort(key=lambda x: x["recall"], reverse=True)

    print(f"\n  {'Condition':<25} {'Recall':>8} {'Found':>8}")
    print("-" * 50)
    for r in results:
        marker = "*" if r["recall"] == 100 else " "
        print(f"{marker} {r['condition']:<25} {r['recall']:>7.1f}% {r['found']:>5}/{r['known']}")

    print("-" * 50)
    print(f"  {'OVERALL':<25} {overall_recall:>7.2f}% {total_found:>5}/{total_known}")

    # Improvement tracking
    print(f"\n  Progress:")
    print(f"    Original S3:     63.38%")
    print(f"    C2 combo:        74.65%")
    print(f"    Enhanced:        88.73%")
    print(f"    MAX RECALL:      {overall_recall:.2f}%")
    print(f"    Total gain:      +{overall_recall - 63.38:.2f}%")

    # List any still missing
    still_missing = [(r["condition"], r["missed"]) for r in results if r["missed"]]
    if still_missing:
        print(f"\n  Still missing ({total_known - total_found} NCT IDs):")
        for cond, missed in still_missing:
            print(f"    {cond}: {missed}")

    # Save
    output_file = output_dir / f"max_recall_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    export = {
        "timestamp": datetime.now().isoformat(),
        "overall_recall": overall_recall,
        "total_found": total_found,
        "total_known": total_known,
        "per_condition": results,
        "improvement": {
            "over_s3": overall_recall - 63.38,
            "over_c2": overall_recall - 74.65,
            "over_enhanced": overall_recall - 88.73
        }
    }

    with open(output_file, 'w') as f:
        json.dump(export, f, indent=2, default=list)

    print(f"\n  Results saved: {output_file}")

    return export

if __name__ == "__main__":
    test_max_recall()
