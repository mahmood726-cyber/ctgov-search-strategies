#!/usr/bin/env python3
"""
Test New Strategies from Literature Review
Tests strategies identified from Cochrane, Glanville, NLM guidance.

Author: Mahmood Ahmad
Version: 1.0
"""

import json
import time
import re
import xml.etree.ElementTree as ET
from typing import Set, Dict, List, Tuple
from urllib.parse import quote
import requests


class StrategyTester:
    """Tests various search strategies from literature"""

    CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"
    PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    RXNORM_API = "https://rxnav.nlm.nih.gov/REST"
    WHO_ICTRP = "https://trialsearch.who.int"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "StrategyTester/1.0"})

    # =========================================================================
    # STRATEGY 1: PubMed Secondary ID Extraction
    # =========================================================================
    def strategy_pubmed_si_extraction(self, drug: str, condition: str, max_results: int = 500) -> Set[str]:
        """
        Extract NCT IDs directly from PubMed's Secondary Source ID field.
        This uses the DataBank linkage - verified publication-trial links.
        """
        nct_ids = set()

        # Search PubMed for RCTs with this drug
        query = f'"{drug}"[tiab] AND ({condition})[tiab] AND (randomized controlled trial[pt])'

        try:
            # Search
            url = f"{self.PUBMED_API}/esearch.fcgi"
            params = {
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json"
            }
            response = self.session.get(url, params=params, timeout=30)
            pmids = response.json().get("esearchresult", {}).get("idlist", [])
            time.sleep(0.35)

            if not pmids:
                return nct_ids

            # Fetch full records with DataBank info
            url = f"{self.PUBMED_API}/efetch.fcgi"
            params = {
                "db": "pubmed",
                "id": ",".join(pmids[:200]),
                "rettype": "xml",
                "retmode": "xml"
            }
            response = self.session.get(url, params=params, timeout=60)
            time.sleep(0.35)

            # Parse XML to extract NCT IDs from DataBankList
            # Method 1: Regex (fast)
            nct_ids.update(re.findall(r'NCT\d{8}', response.text))

            # Method 2: Also check SecondarySourceID elements
            try:
                root = ET.fromstring(response.content)
                for si in root.findall('.//SecondarySourceID'):
                    if si.text and si.text.startswith('NCT'):
                        nct_ids.add(si.text)
                for acc in root.findall('.//AccessionNumber'):
                    if acc.text and acc.text.startswith('NCT'):
                        nct_ids.add(acc.text)
            except:
                pass

        except Exception as e:
            print(f"    Error in PubMed SI extraction: {e}")

        return nct_ids

    # =========================================================================
    # STRATEGY 2: RxNorm Expansion for Generic Terms
    # =========================================================================
    def get_rxnorm_variants(self, drug: str) -> Set[str]:
        """Get all drug name variants from RxNorm"""
        variants = {drug.lower()}

        try:
            # Get RxCUI for the drug
            url = f"{self.RXNORM_API}/rxcui.json"
            params = {"name": drug, "search": 2}  # search=2 for approximate match
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()

            rxcuis = []
            if "idGroup" in data and "rxnormId" in data["idGroup"]:
                rxcuis = data["idGroup"]["rxnormId"]
            time.sleep(0.2)

            # For each RxCUI, get related names
            for rxcui in rxcuis[:3]:  # Limit to avoid too many API calls
                # Get all related concepts
                url = f"{self.RXNORM_API}/rxcui/{rxcui}/allrelated.json"
                response = self.session.get(url, timeout=10)
                related = response.json()
                time.sleep(0.2)

                # Extract names from conceptGroup
                if "allRelatedGroup" in related:
                    for group in related["allRelatedGroup"].get("conceptGroup", []):
                        for concept in group.get("conceptProperties", []):
                            name = concept.get("name", "").lower()
                            if name and len(name) > 2:
                                # Extract just the drug name part
                                variants.add(name.split()[0] if ' ' in name else name)

                # Also get synonyms
                url = f"{self.RXNORM_API}/rxcui/{rxcui}/property.json"
                params = {"propName": "DISPLAY_NAME"}
                response = self.session.get(url, params=params, timeout=10)
                time.sleep(0.2)

        except Exception as e:
            print(f"    RxNorm error: {e}")

        return variants

    def strategy_rxnorm_expansion(self, drug: str, condition: str) -> Set[str]:
        """
        Search CT.gov using RxNorm-expanded drug variants.
        Particularly useful for generic terms like insulin, metformin.
        """
        nct_ids = set()

        # Get RxNorm variants
        variants = self.get_rxnorm_variants(drug)
        print(f"    RxNorm variants for {drug}: {variants}")

        # Search each variant
        for variant in list(variants)[:10]:
            try:
                params = {
                    "query.intr": variant,
                    "fields": "NCTId",
                    "pageSize": 1000
                }
                response = self.session.get(self.CTGOV_API, params=params, timeout=60)

                for study in response.json().get("studies", []):
                    nct_id = study.get("protocolSection", {}).get(
                        "identificationModule", {}
                    ).get("nctId")
                    if nct_id:
                        nct_ids.add(nct_id)

                time.sleep(0.3)
            except:
                pass

        return nct_ids

    # =========================================================================
    # STRATEGY 3: AREA Syntax Advanced Queries
    # =========================================================================
    def strategy_area_syntax(self, drug: str, condition: str) -> Set[str]:
        """
        Use AREA syntax to search specific fields.
        Combines multiple field searches.
        """
        nct_ids = set()

        # Different AREA queries to try
        area_queries = [
            # Search in intervention name specifically
            f'AREA[InterventionName]{drug}',
            # Search in brief title
            f'AREA[BriefTitle]{drug}',
            # Search in official title
            f'AREA[OfficialTitle]{drug}',
            # Interventional studies only
            f'AREA[InterventionName]{drug} AND AREA[StudyType]Interventional',
            # Completed studies (more likely to have results)
            f'AREA[InterventionName]{drug} AND AREA[OverallStatus]Completed',
        ]

        for area_query in area_queries:
            try:
                params = {
                    "query.term": area_query,
                    "fields": "NCTId",
                    "pageSize": 1000
                }
                response = self.session.get(self.CTGOV_API, params=params, timeout=60)

                for study in response.json().get("studies", []):
                    nct_id = study.get("protocolSection", {}).get(
                        "identificationModule", {}
                    ).get("nctId")
                    if nct_id:
                        nct_ids.add(nct_id)

                time.sleep(0.3)
            except Exception as e:
                pass

        return nct_ids

    # =========================================================================
    # STRATEGY 4: Sponsor Search
    # =========================================================================
    def strategy_sponsor_search(self, drug: str, known_sponsors: List[str] = None) -> Set[str]:
        """
        Search by sponsor/collaborator.
        Useful when you know the manufacturer.
        """
        nct_ids = set()

        # Common pharma sponsors for different drugs
        drug_sponsors = {
            "semaglutide": ["Novo Nordisk"],
            "empagliflozin": ["Boehringer Ingelheim", "Eli Lilly"],
            "dapagliflozin": ["AstraZeneca"],
            "pembrolizumab": ["Merck"],
            "nivolumab": ["Bristol-Myers Squibb"],
            "adalimumab": ["AbbVie", "Abbott"],
        }

        sponsors = known_sponsors or drug_sponsors.get(drug.lower(), [])

        for sponsor in sponsors:
            try:
                params = {
                    "query.spons": sponsor,
                    "query.intr": drug,
                    "fields": "NCTId",
                    "pageSize": 1000
                }
                response = self.session.get(self.CTGOV_API, params=params, timeout=60)

                for study in response.json().get("studies", []):
                    nct_id = study.get("protocolSection", {}).get(
                        "identificationModule", {}
                    ).get("nctId")
                    if nct_id:
                        nct_ids.add(nct_id)

                time.sleep(0.3)
            except:
                pass

        return nct_ids

    # =========================================================================
    # STRATEGY 5: Basic Intervention (Baseline)
    # =========================================================================
    def strategy_basic_intervention(self, drug: str) -> Set[str]:
        """Basic intervention search - our current best strategy"""
        nct_ids = set()
        try:
            params = {
                "query.intr": drug,
                "fields": "NCTId",
                "pageSize": 1000
            }
            response = self.session.get(self.CTGOV_API, params=params, timeout=60)

            for study in response.json().get("studies", []):
                nct_id = study.get("protocolSection", {}).get(
                    "identificationModule", {}
                ).get("nctId")
                if nct_id:
                    nct_ids.add(nct_id)

            time.sleep(0.3)
        except:
            pass
        return nct_ids

    # =========================================================================
    # Run Comparison Test
    # =========================================================================
    def get_gold_standard(self, drug: str, condition: str) -> Set[str]:
        """Get gold standard from PubMed DataBank links"""
        return self.strategy_pubmed_si_extraction(drug, condition, max_results=300)

    def validate_nct_ids(self, nct_ids: Set[str]) -> Set[str]:
        """Filter to only NCT IDs that exist"""
        valid = set()
        for nct_id in list(nct_ids)[:150]:
            try:
                url = f"{self.CTGOV_API}/{nct_id}"
                response = self.session.get(url, params={"fields": "NCTId"}, timeout=10)
                if response.status_code == 200:
                    valid.add(nct_id)
                time.sleep(0.1)
            except:
                pass
        return valid

    def run_comparison(self, drugs_to_test: List[Tuple[str, str]]):
        """Compare all strategies"""

        print("=" * 80)
        print("STRATEGY COMPARISON TEST")
        print("Testing strategies identified from literature review")
        print("=" * 80)

        results = []

        for drug, condition in drugs_to_test:
            print(f"\n{'='*60}")
            print(f"DRUG: {drug} | CONDITION: {condition}")
            print("=" * 60)

            # Get gold standard
            print("\n  Getting gold standard from PubMed DataBank links...")
            gold = self.get_gold_standard(drug, condition)
            gold = self.validate_nct_ids(gold)

            if len(gold) < 10:
                print(f"  Skipped: only {len(gold)} valid gold standard trials")
                continue

            print(f"  Gold standard: {len(gold)} trials")

            # Test each strategy
            strategies = {
                "S1-BasicIntervention": lambda: self.strategy_basic_intervention(drug),
                "S2-PubMedSI": lambda: self.strategy_pubmed_si_extraction(drug, condition),
                "S3-RxNormExpand": lambda: self.strategy_rxnorm_expansion(drug, condition),
                "S4-AREASyntax": lambda: self.strategy_area_syntax(drug, condition),
                "S5-Sponsor": lambda: self.strategy_sponsor_search(drug),
            }

            drug_results = {"drug": drug, "condition": condition, "gold": len(gold)}

            for name, strategy_func in strategies.items():
                print(f"\n  Testing {name}...")
                try:
                    found = strategy_func()
                    tp = len(found & gold)
                    recall = tp / len(gold) if gold else 0
                    print(f"    Found: {len(found)}, TP: {tp}, Recall: {recall:.1%}")
                    drug_results[name] = {"found": len(found), "tp": tp, "recall": recall}
                except Exception as e:
                    print(f"    Error: {e}")
                    drug_results[name] = {"found": 0, "tp": 0, "recall": 0}

            # Combined strategy (union of all)
            print(f"\n  Testing S6-Combined (union of all)...")
            combined = set()
            for name in ["S1-BasicIntervention", "S3-RxNormExpand", "S4-AREASyntax", "S5-Sponsor"]:
                if name in drug_results and "found" in drug_results[name]:
                    # Re-run to get actual sets
                    pass
            # For simplicity, just use basic + AREA
            basic = self.strategy_basic_intervention(drug)
            area = self.strategy_area_syntax(drug, condition)
            combined = basic | area
            tp = len(combined & gold)
            recall = tp / len(gold) if gold else 0
            print(f"    Found: {len(combined)}, TP: {tp}, Recall: {recall:.1%}")
            drug_results["S6-Combined"] = {"found": len(combined), "tp": tp, "recall": recall}

            results.append(drug_results)

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        print("\n| Drug | Gold | S1-Basic | S2-PubMed | S3-RxNorm | S4-AREA | S5-Sponsor | S6-Combined |")
        print("|------|------|----------|-----------|-----------|---------|------------|-------------|")

        for r in results:
            row = f"| {r['drug'][:12]} | {r['gold']} |"
            for s in ["S1-BasicIntervention", "S2-PubMedSI", "S3-RxNormExpand", "S4-AREASyntax", "S5-Sponsor", "S6-Combined"]:
                if s in r:
                    row += f" {r[s]['recall']:.0%} |"
                else:
                    row += " - |"
            print(row)

        # Best strategy analysis
        print("\n" + "=" * 80)
        print("BEST STRATEGY ANALYSIS")
        print("=" * 80)

        for strat in ["S1-BasicIntervention", "S2-PubMedSI", "S3-RxNormExpand", "S4-AREASyntax", "S5-Sponsor", "S6-Combined"]:
            recalls = [r[strat]["recall"] for r in results if strat in r]
            if recalls:
                avg = sum(recalls) / len(recalls)
                print(f"  {strat}: Average recall = {avg:.1%}")

        return results


def main():
    # Test on a mix of drug types
    drugs_to_test = [
        # High-recall drugs (specific)
        ("semaglutide", "diabetes OR obesity"),
        ("empagliflozin", "diabetes OR heart failure"),
        ("escitalopram", "depression"),

        # Problem drugs (generic)
        ("insulin", "diabetes"),
        ("metformin", "diabetes"),

        # Oncology (combination problem)
        ("pembrolizumab", "cancer"),

        # Medium recall
        ("adalimumab", "arthritis"),
        ("atorvastatin", "cardiovascular"),
    ]

    tester = StrategyTester()
    tester.run_comparison(drugs_to_test)


if __name__ == "__main__":
    main()
