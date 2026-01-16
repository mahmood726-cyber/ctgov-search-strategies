#!/usr/bin/env python3
"""
Multi-Source NCT ID Discovery
- PubMed API (E-utilities)
- PubMed Central
- Europe PMC
- CrossRef
- CT.gov Results linkage
"""

import requests
import json
import time
import re
import xml.etree.ElementTree as ET
from typing import Dict, Set, List, Tuple
from urllib.parse import quote
from datetime import datetime
from pathlib import Path

from ctgov_config import CTGOV_API

# API endpoints
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_ELINK = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

session = requests.Session()
session.headers.update({'User-Agent': 'NCT-MultiSource/1.0'})

def search_pubmed_for_condition(condition: str, max_results: int = 1000) -> List[str]:
    """Search PubMed for articles about a condition and extract NCT IDs"""
    print(f"    Searching PubMed for '{condition}'...")

    # Search PubMed
    params = {
        "db": "pubmed",
        "term": f'"{condition}"[Title/Abstract] AND (randomized[Title/Abstract] OR "clinical trial"[Publication Type])',
        "retmax": max_results,
        "retmode": "json",
        "usehistory": "y"
    }

    try:
        resp = session.get(PUBMED_ESEARCH, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            pmids = data.get("esearchresult", {}).get("idlist", [])
            print(f"      Found {len(pmids)} PubMed articles")
            return pmids
    except Exception as e:
        print(f"      Error: {e}")

    return []

def get_nct_ids_from_pubmed_articles(pmids: List[str], batch_size: int = 100) -> Set[str]:
    """Fetch PubMed articles and extract NCT IDs from abstracts and metadata"""
    all_ncts = set()

    if not pmids:
        return all_ncts

    # Process in batches
    for i in range(0, len(pmids), batch_size):
        batch = pmids[i:i+batch_size]

        params = {
            "db": "pubmed",
            "id": ",".join(batch),
            "retmode": "xml"
        }

        try:
            resp = session.get(PUBMED_EFETCH, params=params, timeout=60)
            if resp.status_code == 200:
                # Parse XML and extract NCT IDs
                root = ET.fromstring(resp.content)

                for article in root.findall(".//PubmedArticle"):
                    # Check abstract
                    abstract = article.find(".//AbstractText")
                    if abstract is not None and abstract.text:
                        ncts = re.findall(r'NCT\d{8}', abstract.text, re.IGNORECASE)
                        all_ncts.update(n.upper() for n in ncts)

                    # Check DataBankList for registry numbers
                    for accession in article.findall(".//AccessionNumber"):
                        if accession.text and accession.text.upper().startswith("NCT"):
                            all_ncts.add(accession.text.upper())

                    # Check article IDs
                    for artid in article.findall(".//ArticleId"):
                        if artid.text and "NCT" in artid.text.upper():
                            ncts = re.findall(r'NCT\d{8}', artid.text, re.IGNORECASE)
                            all_ncts.update(n.upper() for n in ncts)

            time.sleep(0.35)  # NCBI rate limit

        except Exception as e:
            print(f"      Batch error: {e}")

    return all_ncts

def search_europe_pmc(condition: str, max_results: int = 1000) -> Set[str]:
    """Search Europe PMC for NCT IDs"""
    print(f"    Searching Europe PMC for '{condition}'...")

    all_ncts = set()

    params = {
        "query": f'"{condition}" AND (NCT OR "clinical trial")',
        "format": "json",
        "pageSize": min(max_results, 1000),
        "resultType": "core"
    }

    try:
        resp = session.get(EUROPE_PMC, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("resultList", {}).get("result", [])
            print(f"      Found {len(results)} Europe PMC articles")

            for result in results:
                # Check abstract
                abstract = result.get("abstractText", "")
                if abstract:
                    ncts = re.findall(r'NCT\d{8}', abstract, re.IGNORECASE)
                    all_ncts.update(n.upper() for n in ncts)

                # Check full text references
                for ref in result.get("fullTextRefList", {}).get("fullTextRef", []):
                    if "NCT" in str(ref):
                        ncts = re.findall(r'NCT\d{8}', str(ref), re.IGNORECASE)
                        all_ncts.update(n.upper() for n in ncts)

    except Exception as e:
        print(f"      Error: {e}")

    return all_ncts

def search_pubmed_nct_linkage(condition: str) -> Set[str]:
    """Use PubMed's direct NCT linkage database"""
    print(f"    Checking PubMed-CT.gov linkage for '{condition}'...")

    # First search for clinical trials in PubMed
    params = {
        "db": "pubmed",
        "term": f'"{condition}"[Title/Abstract] AND "clinical trial"[Publication Type]',
        "retmax": 500,
        "retmode": "json"
    }

    all_ncts = set()

    try:
        resp = session.get(PUBMED_ESEARCH, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            pmids = data.get("esearchresult", {}).get("idlist", [])

            if pmids:
                # Use elink to find linked clinical trials
                link_params = {
                    "dbfrom": "pubmed",
                    "db": "clinicaltrials",
                    "id": ",".join(pmids[:100]),  # Limit batch
                    "retmode": "json"
                }

                link_resp = session.get(PUBMED_ELINK, params=link_params, timeout=30)
                if link_resp.status_code == 200:
                    link_data = link_resp.json()

                    # Extract linked NCT IDs
                    linksets = link_data.get("linksets", [])
                    for linkset in linksets:
                        for linksetdb in linkset.get("linksetdbs", []):
                            if linksetdb.get("dbto") == "clinicaltrials":
                                links = linksetdb.get("links", [])
                                all_ncts.update(resolve_clinicaltrials_links(links))

    except Exception as e:
        print(f"      Error: {e}")

    return all_ncts


def resolve_clinicaltrials_links(links: List[str]) -> Set[str]:
    """Resolve PubMed clinicaltrials link IDs to NCT IDs when possible."""
    ncts = set()
    numeric_ids = []

    for link in links:
        link_str = str(link).strip()
        if not link_str:
            continue
        if link_str.upper().startswith("NCT"):
            ncts.add(link_str.upper())
        elif link_str.isdigit():
            numeric_ids.append(link_str)

    if not numeric_ids:
        return ncts

    try:
        params = {
            "db": "clinicaltrials",
            "id": ",".join(numeric_ids[:200]),
            "retmode": "json",
        }
        resp = session.get(PUBMED_ESUMMARY, params=params, timeout=30)
        if resp.status_code != 200:
            return ncts

        data = resp.json().get("result", {})
        for key, value in data.items():
            if not isinstance(value, dict):
                continue
            nct_id = value.get("nct_id") or value.get("nctid")
            if nct_id:
                ncts.add(nct_id.upper())
    except Exception as e:
        print(f"      Linkage resolve error: {e}")

    return ncts

def search_ctgov_publications(nct_id: str) -> List[str]:
    """Check if a CT.gov study has linked publications"""
    url = f"{CTGOV_API}/{nct_id}"

    try:
        resp = session.get(url, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            refs = data.get("protocolSection", {}).get("referencesModule", {}).get("references", [])
            pmids = []
            for ref in refs:
                pmid = ref.get("pmid")
                if pmid:
                    pmids.append(pmid)
            return pmids
    except:
        pass

    return []

def reverse_search_from_nct(nct_id: str) -> Dict:
    """Given an NCT ID, find what search terms would find it via PubMed"""
    print(f"    Reverse searching {nct_id}...")

    # Search PubMed for the NCT ID directly
    params = {
        "db": "pubmed",
        "term": nct_id,
        "retmax": 50,
        "retmode": "json"
    }

    result = {
        "nct_id": nct_id,
        "pubmed_hits": 0,
        "pmids": [],
        "findable_via_pubmed": False
    }

    try:
        resp = session.get(PUBMED_ESEARCH, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            pmids = data.get("esearchresult", {}).get("idlist", [])
            result["pubmed_hits"] = len(pmids)
            result["pmids"] = pmids
            result["findable_via_pubmed"] = len(pmids) > 0

    except Exception as e:
        result["error"] = str(e)

    return result

def comprehensive_search(condition: str) -> Tuple[Set[str], Dict]:
    """Comprehensive multi-source search for a condition"""
    print(f"\n  Comprehensive search for: {condition}")
    print("  " + "-" * 50)

    all_ncts = set()
    stats = {
        "pubmed_articles": 0,
        "pubmed_ncts": 0,
        "europe_pmc_ncts": 0,
        "total_unique": 0
    }

    # 1. PubMed search
    pmids = search_pubmed_for_condition(condition)
    stats["pubmed_articles"] = len(pmids)

    pubmed_ncts = get_nct_ids_from_pubmed_articles(pmids)
    stats["pubmed_ncts"] = len(pubmed_ncts)
    all_ncts.update(pubmed_ncts)
    print(f"      Extracted {len(pubmed_ncts)} NCT IDs from PubMed")

    # 2. Europe PMC search
    epmc_ncts = search_europe_pmc(condition)
    stats["europe_pmc_ncts"] = len(epmc_ncts)
    all_ncts.update(epmc_ncts)
    print(f"      Found {len(epmc_ncts)} NCT IDs from Europe PMC")

    stats["total_unique"] = len(all_ncts)
    print(f"    Total unique NCT IDs: {len(all_ncts)}")

    return all_ncts, stats

def test_multi_source():
    """Test multi-source approach for finding missing NCT IDs"""
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")

    print("=" * 70)
    print("  MULTI-SOURCE NCT ID DISCOVERY")
    print("=" * 70)

    # Load known NCT IDs
    nct_file = output_dir / "recall_test_results.json"
    with open(nct_file) as f:
        data = json.load(f)

    condition_groups = {k: set(v) for k, v in data.get("condition_groups", {}).items() if len(v) >= 3}

    # Missing NCT IDs from our previous analysis
    missing_ncts = {
        "obesity": ["NCT02067728"],
        "covid-19": ["NCT04499677", "NCT04818320"],
        "stroke": ["NCT01958736", "NCT02717715", "NCT02735148"],
        "postoperative pain": ["NCT03415646", "NCT03420703", "NCT03756987"]
    }

    print("\n  Checking if missing NCT IDs are findable via PubMed...")
    print("=" * 70)

    for condition, ncts in missing_ncts.items():
        print(f"\n  {condition.upper()}")
        for nct in ncts:
            result = reverse_search_from_nct(nct)
            status = "FOUND" if result["findable_via_pubmed"] else "NOT FOUND"
            print(f"    {nct}: {status} in PubMed ({result['pubmed_hits']} articles)")

    # Now test comprehensive search for problem conditions
    print("\n" + "=" * 70)
    print("  COMPREHENSIVE MULTI-SOURCE SEARCH")
    print("=" * 70)

    results = {}
    total_found = 0
    total_known = 0

    for condition, known_ncts in condition_groups.items():
        # Run comprehensive search
        found_ncts, stats = comprehensive_search(condition)

        # Calculate recall
        overlap = found_ncts & known_ncts
        recall = len(overlap) / len(known_ncts) * 100 if known_ncts else 0

        total_found += len(overlap)
        total_known += len(known_ncts)

        results[condition] = {
            "known": len(known_ncts),
            "found": len(overlap),
            "recall": recall,
            "stats": stats,
            "missed": list(known_ncts - found_ncts)
        }

        status = "OK" if recall >= 80 else "LOW"
        print(f"    Recall: {recall:.1f}% ({len(overlap)}/{len(known_ncts)}) [{status}]")

    overall_recall = total_found / total_known * 100

    # Summary
    print("\n" + "=" * 70)
    print("  MULTI-SOURCE RESULTS SUMMARY")
    print("=" * 70)

    print(f"\n  {'Condition':<25} {'CT.gov':>10} {'Multi-Src':>10} {'Gain':>8}")
    print("-" * 60)

    # Compare with CT.gov-only results (88.7%)
    ctgov_only = {
        "stroke": 71.4, "eczema": 100, "cystic fibrosis": 100,
        "plaque psoriasis": 100, "psoriasis": 100, "autistic disorder": 100,
        "autism": 100, "autism spectrum disorder": 100, "obesity": 66.7,
        "postoperative pain": 33.3, "cancer": 100, "pilonidal sinus": 100,
        "covid-19": 50, "polymyositis": 100, "dermatomyositis": 100
    }

    for cond, r in results.items():
        ctgov = ctgov_only.get(cond)
        if ctgov is None:
            ctgov_str = "N/A"
            gain_str = "N/A"
        else:
            gain = r["recall"] - ctgov
            ctgov_str = f"{ctgov:>5.1f}%"
            gain_str = f"+{gain:.1f}%" if gain > 0 else f"{gain:.1f}%"
        print(f"  {cond:<25} {ctgov_str:>9} {r['recall']:>9.1f}% {gain_str:>8}")

    ctgov_total_known = 0
    ctgov_total_found = 0
    for cond, r in results.items():
        ctgov = ctgov_only.get(cond)
        if ctgov is None:
            continue
        ctgov_total_known += r["known"]
        ctgov_total_found += int(round(ctgov * r["known"] / 100))

    ctgov_overall = (
        ctgov_total_found / ctgov_total_known * 100
        if ctgov_total_known
        else None
    )

    print("-" * 60)
    ctgov_overall_str = f"{ctgov_overall:.1f}%" if ctgov_overall is not None else "N/A"
    print(f"  {'OVERALL':<25} {ctgov_overall_str:>10} {overall_recall:>9.1f}%")

    # Save results
    output_file = output_dir / f"multi_source_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    export = {
        "timestamp": datetime.now().isoformat(),
        "overall_recall": overall_recall,
        "total_found": total_found,
        "total_known": total_known,
        "per_condition": {k: {**v, "missed": v["missed"]} for k, v in results.items()}
    }

    with open(output_file, 'w') as f:
        json.dump(export, f, indent=2, default=list)

    print(f"\n  Results saved: {output_file}")

    return results

if __name__ == "__main__":
    test_multi_source()
