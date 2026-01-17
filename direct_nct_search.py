#!/usr/bin/env python3
"""
Direct NCT ID search analysis - understand why searches miss known studies
"""

import json
from typing import Set, Dict, List
from urllib.parse import quote
from pathlib import Path

from ctgov_config import CTGOV_API, DEFAULT_TIMEOUT
from ctgov_utils import build_params, fetch_nct_ids, get_session

session = get_session("CTgov-Direct/1.0")
TIMEOUT = DEFAULT_TIMEOUT


def get_nct_conditions(nct_id: str) -> List[str]:
    """Get conditions for a specific NCT ID"""
    url = f"{CTGOV_API}/{nct_id}"
    try:
        resp = session.get(url, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            conds = data.get("protocolSection", {}).get("conditionsModule", {}).get("conditions", [])
            return conds
    except Exception:
        pass
    return []


def search_and_count(query: str) -> int:
    """Search and return total count"""
    try:
        params = build_params(query)
        params["countTotal"] = "true"
        params["pageSize"] = 1
        resp = session.get(CTGOV_API, params=params, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("totalCount", 0)
    except Exception as e:
        print(f"Error: {e}")
    return 0


def search_ncts(query: str) -> Set[str]:
    """Search and return NCT IDs (up to 1000)"""
    try:
        params = build_params(query)
        ncts, _ = fetch_nct_ids(session, params, timeout=TIMEOUT, page_size=1000)
        return ncts
    except Exception:
        pass
    return set()


def analyze_nct_searchability(nct_ids: List[str], condition_term: str):
    """Analyze how to find specific NCT IDs"""
    print(f"\n{'=' * 70}")
    print(f"  SEARCHABILITY ANALYSIS: {condition_term}")
    print(f"{'=' * 70}")

    # First check total results for condition search
    count = search_and_count(f"query.cond={quote(condition_term)}")
    print(f"\n  Total results for query.cond='{condition_term}': {count:,}")

    # Get the actual conditions each NCT ID is indexed under
    print(f"\n  Analyzing {len(nct_ids)} NCT IDs...")

    indexed_conditions = {}
    for nct in nct_ids:
        conds = get_nct_conditions(nct)
        indexed_conditions[nct] = conds
        print(f"    {nct}: {conds}")

    # Find common condition terms
    all_cond_terms = set()
    for conds in indexed_conditions.values():
        all_cond_terms.update(conds)

    print(f"\n  All unique condition terms found: {len(all_cond_terms)}")
    for c in sorted(all_cond_terms):
        print(f"    - {c}")

    # Try searching by each actual condition term
    print("\n  Testing searches by actual condition terms...")
    nct_set = set(n.upper() for n in nct_ids)

    best_term = None
    best_recall = 0

    for cond_term in all_cond_terms:
        found = search_ncts(f"query.cond={quote(cond_term)}")
        overlap = found & nct_set
        recall = len(overlap) / len(nct_set) * 100 if nct_set else 0

        if overlap:
            print(f"    '{cond_term}': {recall:.1f}% ({len(overlap)}/{len(nct_set)})")

        if recall > best_recall:
            best_recall = recall
            best_term = cond_term

    # Try combining terms with OR
    print("\n  Testing OR combinations...")
    combined = set()
    for cond_term in all_cond_terms:
        found = search_ncts(f"query.cond={quote(cond_term)}")
        combined.update(found)

    final_overlap = combined & nct_set
    final_recall = len(final_overlap) / len(nct_set) * 100
    print(f"  Combined all terms: {final_recall:.1f}% ({len(final_overlap)}/{len(nct_set)})")

    # Check which are still missing
    still_missing = nct_set - combined
    if still_missing:
        print(f"\n  Still missing {len(still_missing)} NCT IDs:")
        for nct in still_missing:
            print(f"    {nct}")
            # Try direct NCT search
            found_direct = search_ncts(f"query.term={nct}")
            if nct in found_direct:
                print("      -> Found via direct NCT search!")

    return {
        "condition": condition_term,
        "known": len(nct_ids),
        "best_term": best_term,
        "best_recall": best_recall,
        "combined_recall": final_recall,
        "missing": len(still_missing)
    }


def run_analysis():
    """Run full analysis"""
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")
    nct_file = output_dir / "recall_test_results.json"

    with open(nct_file) as f:
        data = json.load(f)

    condition_groups = data.get("condition_groups", {})

    # Focus on problem conditions
    problems = {
        "stroke": condition_groups.get("stroke", []),
        "postoperative pain": condition_groups.get("postoperative pain", []),
        "cancer": condition_groups.get("cancer", []),
        "covid-19": condition_groups.get("covid-19", [])
    }

    results = {}
    for cond, ncts in problems.items():
        if ncts:
            results[cond] = analyze_nct_searchability(ncts, cond)

    # Summary
    print(f"\n{'=' * 70}")
    print("  FINAL SUMMARY")
    print(f"{'=' * 70}")

    for cond, r in results.items():
        print(f"\n  {cond}:")
        print(f"    Best specific term: '{r['best_term']}' -> {r['best_recall']:.1f}%")
        print(f"    Combined all terms: {r['combined_recall']:.1f}%")
        print(f"    Still unreachable: {r['missing']}")

    # Recommendations
    print(f"\n{'=' * 70}")
    print("  RECOMMENDATIONS")
    print(f"{'=' * 70}")
    print("""
  1. STROKE: Search by specific terms like 'Cerebrovascular Stroke',
     'Cerebrovascular Accident' instead of generic 'stroke'

  2. CANCER: Must search specific cancer types (e.g., 'Urothelial Cancer',
     'Bladder Cancer', 'Stomach Neoplasms') - generic 'cancer' misses most

  3. COVID-19: Use 'SARS-CoV-2' or '2019-nCoV' in addition to 'COVID-19'

  4. POSTOPERATIVE PAIN: Results indexed under specific procedures, not
     the generic pain term

  KEY INSIGHT: The CT.gov API returns studies indexed under EXACT
  condition terms. Systematic reviewers must use specific condition
  vocabulary, not generic terms.
    """)


if __name__ == "__main__":
    run_analysis()
