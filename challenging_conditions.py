#!/usr/bin/env python3
"""
Analyze and improve recall for challenging conditions:
- stroke (42.9%)
- postoperative pain (0%)
- cancer (14.3%)
- covid-19 (16.7%)
"""

import json
import time
from typing import Dict, Set, List
from urllib.parse import quote
from datetime import datetime
from pathlib import Path

from ctgov_config import CTGOV_API, DEFAULT_TIMEOUT
from ctgov_utils import build_params, fetch_nct_ids, get_session

TIMEOUT = DEFAULT_TIMEOUT

session = get_session("CTgov-Challenge/1.0")

# Extended search strategies for challenging conditions
CHALLENGE_STRATEGIES = {
    # Basic searches
    "cond": "query.cond={c}",
    "term": "query.term={c}",
    "intr": "query.intr={c}",
    "title": "query.titles={c}",

    # Combined searches
    "cond_or_term": "query.cond={c}&query.term={c}",
    "all_fields": "query.term={c}",  # searches all text fields

    # Relaxed filters
    "no_filter": "query.term={c}",
    "broad": "query.cond={c}",

    # Specific field searches
    "brief_title": "query.term=AREA[BriefTitle]{c}",
    "official_title": "query.term=AREA[OfficialTitle]{c}",
    "description": "query.term=AREA[BriefSummary]{c}",
    "keywords": "query.term=AREA[Keyword]{c}",
    "mesh": "query.term=AREA[ConditionMeshTerm]{c}",
    "mesh_ancestor": "query.term=AREA[ConditionAncestorTerm]{c}",
}

# Synonyms and related terms for challenging conditions
CONDITION_SYNONYMS = {
    "stroke": [
        "stroke", "cerebrovascular accident", "CVA", "cerebral infarction",
        "ischemic stroke", "hemorrhagic stroke", "brain infarction",
        "cerebrovascular disease", "apoplexy", "transient ischemic attack", "TIA"
    ],
    "postoperative pain": [
        "postoperative pain", "post-operative pain", "post operative pain",
        "surgical pain", "postsurgical pain", "post-surgical pain",
        "pain after surgery", "acute postoperative pain", "postop pain"
    ],
    "cancer": [
        "cancer", "neoplasm", "malignancy", "tumor", "tumour", "carcinoma",
        "oncology", "malignant", "metastatic", "adenocarcinoma"
    ],
    "covid-19": [
        "covid-19", "covid19", "coronavirus", "SARS-CoV-2", "COVID",
        "corona virus", "2019-nCoV", "novel coronavirus", "pandemic"
    ]
}


def search_single(query: str) -> Set[str]:
    """Execute a single search and return NCT IDs"""
    try:
        params = build_params(query)
        ncts, _ = fetch_nct_ids(session, params, timeout=TIMEOUT, page_size=1000)
        return ncts
    except Exception as e:
        print(f"    Error: {e}")
    return set()


def lookup_nct(nct_id: str) -> Dict:
    """Get details for a specific NCT ID"""
    url = f"{CTGOV_API}/{nct_id}"
    try:
        resp = session.get(url, timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


def analyze_nct_details(nct_id: str) -> Dict:
    """Extract searchable fields from an NCT record"""
    data = lookup_nct(nct_id)
    if not data:
        return {"error": "Not found"}

    proto = data.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    desc = proto.get("descriptionModule", {})
    cond = proto.get("conditionsModule", {})
    design = proto.get("designModule", {})
    status = proto.get("statusModule", {})

    return {
        "nct_id": nct_id,
        "brief_title": ident.get("briefTitle", ""),
        "official_title": ident.get("officialTitle", ""),
        "conditions": cond.get("conditions", []),
        "keywords": cond.get("keywords", []),
        "brief_summary": desc.get("briefSummary", "")[:200] + "..." if desc.get("briefSummary") else "",
        "study_type": design.get("studyType", ""),
        "allocation": design.get("designInfo", {}).get("allocation", ""),
        "overall_status": status.get("overallStatus", "")
    }


def run_challenge_analysis():
    """Analyze challenging conditions"""
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")

    print("=" * 70)
    print("  CHALLENGING CONDITIONS ANALYSIS")
    print("=" * 70)

    # Load known NCT IDs
    nct_file = output_dir / "recall_test_results.json"
    with open(nct_file) as f:
        data = json.load(f)

    condition_groups = data.get("condition_groups", {})

    # Focus on challenging conditions
    challenging = {
        "stroke": set(condition_groups.get("stroke", [])),
        "postoperative pain": set(condition_groups.get("postoperative pain", [])),
        "cancer": set(condition_groups.get("cancer", [])),
        "covid-19": set(condition_groups.get("covid-19", []))
    }

    all_results = {}

    for condition, known_ncts in challenging.items():
        if not known_ncts:
            print(f"\nSkipping {condition} - no known NCT IDs")
            continue

        print(f"\n{'=' * 70}")
        print(f"  {condition.upper()} ({len(known_ncts)} known NCT IDs)")
        print(f"{'=' * 70}")

        # First, analyze the NCT records to understand how they're indexed
        print("\n  Analyzing NCT record details...")
        for nct in list(known_ncts)[:3]:  # Sample 3
            details = analyze_nct_details(nct)
            if "error" not in details:
                print(f"\n  {nct}:")
                print(f"    Title: {details['brief_title'][:60]}...")
                print(f"    Conditions: {details['conditions'][:3]}")
                print(f"    Keywords: {details['keywords'][:3]}")
                print(f"    Allocation: {details['allocation']}")

        # Test different search strategies
        print("\n  Testing search strategies...")
        strategy_results = {}

        for strat_name, query_template in CHALLENGE_STRATEGIES.items():
            query = query_template.replace("{c}", quote(condition))
            found = search_single(query)
            overlap = found & known_ncts
            recall = len(overlap) / len(known_ncts) * 100
            strategy_results[strat_name] = {
                "found": len(found),
                "overlap": len(overlap),
                "recall": recall
            }
            print(f"    {strat_name}: {recall:.1f}% ({len(overlap)}/{len(known_ncts)})")

        # Test synonyms
        print("\n  Testing synonyms...")
        synonyms = CONDITION_SYNONYMS.get(condition, [condition])
        combined_ncts = set()

        for synonym in synonyms:
            query = f"query.cond={quote(synonym)}"
            found = search_single(query)
            combined_ncts.update(found)
            overlap = found & known_ncts
            if overlap:
                print(f"    '{synonym}': found {len(overlap)} matches")

        # Combined synonym search
        combined_overlap = combined_ncts & known_ncts
        combined_recall = len(combined_overlap) / len(known_ncts) * 100
        print(f"\n  Combined synonyms: {combined_recall:.1f}% ({len(combined_overlap)}/{len(known_ncts)})")

        # Try OR syntax with synonyms (max 5)
        top_synonyms = synonyms[:5]
        or_query = " OR ".join([f'"{s}"' for s in top_synonyms])
        query = f"query.term={quote(or_query)}"
        or_found = search_single(query)
        or_overlap = or_found & known_ncts
        or_recall = len(or_overlap) / len(known_ncts) * 100
        print(f"  OR query: {or_recall:.1f}% ({len(or_overlap)}/{len(known_ncts)})")

        # Direct NCT ID lookup to find actual indexing
        print("\n  Checking actual indexing of missing NCT IDs...")
        missing = known_ncts - combined_ncts
        for nct in list(missing)[:5]:
            details = analyze_nct_details(nct)
            if "error" not in details:
                print(f"\n    {nct} (MISSED):")
                print(f"      Conditions: {details['conditions']}")
                print(f"      Title: {details['brief_title'][:50]}...")

        all_results[condition] = {
            "known": len(known_ncts),
            "best_single": max(strategy_results.items(), key=lambda x: x[1]["recall"]),
            "combined_synonyms_recall": combined_recall,
            "or_query_recall": or_recall,
            "missing_count": len(missing)
        }

    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)

    for condition, results in all_results.items():
        print(f"\n  {condition}:")
        print(f"    Best single strategy: {results['best_single'][0]} ({results['best_single'][1]['recall']:.1f}%)")
        print(f"    Combined synonyms: {results['combined_synonyms_recall']:.1f}%")
        print(f"    OR query: {results['or_query_recall']:.1f}%")
        print(f"    Still missing: {results['missing_count']} NCT IDs")

    # Save results
    output_file = output_dir / f"challenge_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    print(f"\n  Results saved: {output_file}")

    return all_results


if __name__ == "__main__":
    run_challenge_analysis()
