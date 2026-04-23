#!/usr/bin/env python3
# sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files.
"""
Combined Search Strategy
- CT.gov direct search (enhanced multi-term)
- PubMed supplementary discovery
- WHO ICTRP cross-reference
- Maximum possible recall
"""

import requests
import json
import time
import re
import xml.etree.ElementTree as ET
from typing import Dict, Set, List
from urllib.parse import quote
from datetime import datetime
from pathlib import Path
import concurrent.futures

from ctgov_config import DEFAULT_PAGE_SIZE, DEFAULT_TIMEOUT
from ctgov_utils import build_params, fetch_nct_ids, get_session

# APIs
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
ICTRP_SEARCH = "https://trialsearch.who.int/TrialService.asmx/GetTrials"

session = requests.Session()
session.headers.update({'User-Agent': 'Combined-Search/1.0'})

# Condition expansions
EXPANSIONS = {
    "stroke": [
        "stroke", "cerebrovascular stroke", "cerebral stroke", "cerebrovascular accident",
        "CVA", "ischemic stroke", "hemorrhagic stroke", "acute ischemic stroke",
        "brain infarction", "cerebral infarction", "hemiplegia"
    ],
    "cancer": [
        "cancer", "neoplasm", "carcinoma", "malignancy", "tumor",
        "urothelial cancer", "bladder cancer", "urothelial carcinoma",
        "stomach neoplasms", "colorectal neoplasms", "mesothelioma",
        "breast cancer", "lung cancer", "prostate cancer"
    ],
    "covid-19": [
        "covid-19", "covid19", "coronavirus", "SARS-CoV-2",
        "coronavirus infection", "2019-nCoV", "SARS-CoV 2"
    ],
    "postoperative pain": [
        "postoperative pain", "post-operative pain", "surgical pain",
        "postsurgical pain", "acute pain", "analgesia", "erector spinae block"
    ],
    "obesity": [
        "obesity", "obese", "overweight", "body mass index",
        "weight loss", "bariatric", "morbid obesity"
    ]
}


def search_ctgov(query: str) -> Set[str]:
    """Search CT.gov API"""
    try:
        params = build_params(query)
        ctgov_session = get_session("Combined-Search/1.0")
        ncts, _ = fetch_nct_ids(
            ctgov_session,
            params,
            timeout=DEFAULT_TIMEOUT,
            page_size=DEFAULT_PAGE_SIZE,
        )
        return ncts
    except Exception:
        pass
    return set()


def search_ctgov_parallel(queries: List[str]) -> Set[str]:
    """Parallel CT.gov search"""
    all_ncts = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(search_ctgov, q) for q in queries]
        for f in concurrent.futures.as_completed(futures):
            try:
                all_ncts.update(f.result())
            except Exception:
                pass
    return all_ncts


def search_pubmed_ncts(condition: str) -> Set[str]:
    """Extract NCT IDs from PubMed articles"""
    # Search PubMed
    params = {
        "db": "pubmed",
        "term": f'"{condition}"[Title/Abstract] AND (NCT OR "clinical trial registration")',
        "retmax": 500,
        "retmode": "json"
    }

    try:
        resp = session.get(PUBMED_ESEARCH, params=params, timeout=30)
        if resp.status_code != 200:
            return set()

        data = resp.json()
        pmids = data.get("esearchresult", {}).get("idlist", [])

        if not pmids:
            return set()

        # Fetch articles
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(pmids[:200]),
            "retmode": "xml"
        }

        fetch_resp = session.get(PUBMED_EFETCH, params=fetch_params, timeout=60)
        if fetch_resp.status_code != 200:
            return set()

        # Parse XML for NCT IDs
        all_ncts = set()
        root = ET.fromstring(fetch_resp.content)

        for article in root.findall(".//PubmedArticle"):
            # Check abstract
            abstract = article.find(".//AbstractText")
            if abstract is not None and abstract.text:
                ncts = re.findall(r'NCT\d{8}', abstract.text, re.IGNORECASE)
                all_ncts.update(n.upper() for n in ncts)

            # Check DataBankList
            for accession in article.findall(".//AccessionNumber"):
                if accession.text and accession.text.upper().startswith("NCT"):
                    all_ncts.add(accession.text.upper())

        return all_ncts

    except Exception:
        return set()


def search_europe_pmc_ncts(condition: str) -> Set[str]:
    """Extract NCT IDs from Europe PMC"""
    params = {
        "query": f'"{condition}" AND NCT',
        "format": "json",
        "pageSize": 500,
        "resultType": "lite"
    }

    try:
        resp = session.get(EUROPE_PMC, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("resultList", {}).get("result", [])

            all_ncts = set()
            for result in results:
                abstract = result.get("abstractText", "")
                if abstract:
                    ncts = re.findall(r'NCT\d{8}', abstract, re.IGNORECASE)
                    all_ncts.update(n.upper() for n in ncts)
            return all_ncts
    except Exception:
        pass
    return set()


def enhanced_ctgov_search(condition: str) -> Set[str]:
    """Enhanced CT.gov multi-term search"""
    queries = []
    condition_lower = condition.lower()
    terms = EXPANSIONS.get(condition_lower, [condition])

    for term in terms:
        queries.append(f"query.cond={quote(term)}")
        queries.append(f"query.term={quote(term)}")
        queries.append(f"query.cond={quote(term)}&query.term=AREA[DesignAllocation]RANDOMIZED")

    return search_ctgov_parallel(queries)


def combined_search(condition: str) -> Dict:
    """Combined multi-source search"""
    results = {
        "ctgov": set(),
        "pubmed": set(),
        "europepmc": set(),
        "combined": set()
    }

    # 1. CT.gov enhanced search (primary)
    results["ctgov"] = enhanced_ctgov_search(condition)

    # 2. PubMed supplementary
    results["pubmed"] = search_pubmed_ncts(condition)

    # 3. Europe PMC supplementary
    results["europepmc"] = search_europe_pmc_ncts(condition)

    # Combine all
    results["combined"] = results["ctgov"] | results["pubmed"] | results["europepmc"]

    return results


def test_combined():
    """Test combined approach"""
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")

    print("=" * 70)
    print("  COMBINED MULTI-SOURCE SEARCH")
    print("=" * 70)

    # Load data
    nct_file = output_dir / "recall_test_results.json"
    with open(nct_file) as f:
        data = json.load(f)

    condition_groups = {k: set(v) for k, v in data.get("condition_groups", {}).items() if len(v) >= 3}

    print(f"\nTesting {len(condition_groups)} conditions")

    all_results = {}
    total_found = 0
    total_known = 0
    total_ctgov_found = 0

    for condition, known_ncts in condition_groups.items():
        print(f"\n  {condition}...", end=" ", flush=True)

        start = time.time()
        results = combined_search(condition)
        elapsed = time.time() - start

        # Calculate recalls
        ctgov_overlap = results["ctgov"] & known_ncts
        combined_overlap = results["combined"] & known_ncts

        ctgov_recall = len(ctgov_overlap) / len(known_ncts) * 100
        combined_recall = len(combined_overlap) / len(known_ncts) * 100

        total_found += len(combined_overlap)
        total_ctgov_found += len(ctgov_overlap)
        total_known += len(known_ncts)

        # Check if PubMed/Europe PMC added anything
        pubmed_only = (results["pubmed"] | results["europepmc"]) - results["ctgov"]
        new_from_lit = pubmed_only & known_ncts

        all_results[condition] = {
            "known": len(known_ncts),
            "ctgov_found": len(ctgov_overlap),
            "ctgov_recall": ctgov_recall,
            "combined_found": len(combined_overlap),
            "combined_recall": combined_recall,
            "new_from_literature": len(new_from_lit),
            "missed": list(known_ncts - results["combined"])
        }

        gain = combined_recall - ctgov_recall
        gain_str = f"+{gain:.1f}%" if gain > 0 else ""
        print(f"CT.gov: {ctgov_recall:.1f}% | Combined: {combined_recall:.1f}% {gain_str} | {elapsed:.1f}s")

    overall_recall = total_found / total_known * 100
    ctgov_overall = total_ctgov_found / total_known * 100 if total_known else 0

    # Summary
    print("\n" + "=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)

    print(f"\n  {'Condition':<25} {'CT.gov':>8} {'Combined':>10} {'New':>6}")
    print("-" * 55)

    for cond, r in sorted(all_results.items(), key=lambda x: x[1]["combined_recall"], reverse=True):
        new_str = f"+{r['new_from_literature']}" if r['new_from_literature'] > 0 else "0"
        print(f"  {cond:<25} {r['ctgov_recall']:>7.1f}% {r['combined_recall']:>9.1f}% {new_str:>6}")

    print("-" * 55)
    print(f"  {'OVERALL':<25} {ctgov_overall:>7.1f}% {overall_recall:>9.1f}%")

    # Did we find any new ones?
    total_new = sum(r["new_from_literature"] for r in all_results.values())
    print(f"\n  New NCT IDs from PubMed/Europe PMC: {total_new}")

    # Still missing
    still_missing = []
    for cond, r in all_results.items():
        if r["missed"]:
            for nct in r["missed"]:
                still_missing.append((cond, nct))

    if still_missing:
        print(f"\n  Still missing ({len(still_missing)} NCT IDs):")
        for cond, nct in still_missing:
            print(f"    {cond}: {nct}")

    # Save
    output_file = output_dir / f"combined_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    export = {
        "timestamp": datetime.now().isoformat(),
        "overall_recall": overall_recall,
        "total_found": total_found,
        "total_known": total_known,
        "new_from_literature": total_new,
        "per_condition": all_results
    }

    with open(output_file, 'w') as f:
        json.dump(export, f, indent=2, default=list)

    print(f"\n  Results saved: {output_file}")


if __name__ == "__main__":
    test_combined()
