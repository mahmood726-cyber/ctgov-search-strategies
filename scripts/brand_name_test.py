#!/usr/bin/env python3
"""
Brand Name Expansion Test
Tests if adding brand names improves recall over generic names alone.

Author: Mahmood Ahmad
Version: 1.0
"""

import json
import time
import re
from typing import Set, Dict, List, Tuple
import requests


class BrandNameTester:
    """Tests brand name expansion impact on recall"""

    CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"
    PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    # Drug to brand name mappings (comprehensive)
    BRAND_NAMES = {
        # GLP-1 agonists
        "semaglutide": ["ozempic", "wegovy", "rybelsus"],
        "liraglutide": ["victoza", "saxenda"],
        "dulaglutide": ["trulicity"],
        "tirzepatide": ["mounjaro", "zepbound"],

        # SGLT2 inhibitors
        "empagliflozin": ["jardiance"],
        "dapagliflozin": ["farxiga", "forxiga"],
        "canagliflozin": ["invokana"],

        # DPP-4 inhibitors
        "sitagliptin": ["januvia"],
        "linagliptin": ["tradjenta"],
        "saxagliptin": ["onglyza"],

        # Statins
        "atorvastatin": ["lipitor"],
        "rosuvastatin": ["crestor"],
        "simvastatin": ["zocor"],

        # ACE inhibitors / ARBs
        "lisinopril": ["prinivil", "zestril"],
        "losartan": ["cozaar"],
        "valsartan": ["diovan"],

        # Beta blockers
        "metoprolol": ["lopressor", "toprol"],
        "carvedilol": ["coreg"],

        # Anticoagulants
        "apixaban": ["eliquis"],
        "rivaroxaban": ["xarelto"],
        "dabigatran": ["pradaxa"],
        "warfarin": ["coumadin"],

        # Antidepressants
        "sertraline": ["zoloft"],
        "fluoxetine": ["prozac"],
        "escitalopram": ["lexapro"],
        "duloxetine": ["cymbalta"],
        "venlafaxine": ["effexor"],

        # Antipsychotics
        "quetiapine": ["seroquel"],
        "aripiprazole": ["abilify"],
        "olanzapine": ["zyprexa"],

        # Respiratory
        "tiotropium": ["spiriva"],
        "fluticasone": ["flovent", "flonase"],
        "budesonide": ["pulmicort"],
        "montelukast": ["singulair"],

        # Biologics - Rheumatology
        "adalimumab": ["humira"],
        "etanercept": ["enbrel"],
        "infliximab": ["remicade"],
        "tocilizumab": ["actemra"],
        "tofacitinib": ["xeljanz"],
        "baricitinib": ["olumiant"],

        # Oncology
        "pembrolizumab": ["keytruda"],
        "nivolumab": ["opdivo"],
        "trastuzumab": ["herceptin"],
        "bevacizumab": ["avastin"],
        "rituximab": ["rituxan"],

        # Infectious disease
        "sofosbuvir": ["sovaldi"],
        "remdesivir": ["veklury"],
        "oseltamivir": ["tamiflu"],

        # GI
        "omeprazole": ["prilosec"],
        "pantoprazole": ["protonix"],
        "esomeprazole": ["nexium"],

        # Pain
        "pregabalin": ["lyrica"],
        "gabapentin": ["neurontin"],
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "BrandNameTester/1.0"})

    def get_gold_standard(self, drug: str, condition: str, max_results: int = 200) -> Set[str]:
        """Get NCT IDs from PubMed as gold standard"""
        nct_ids = set()

        query = f'"{drug}"[Title/Abstract] AND ({condition})[Title/Abstract] AND (randomized controlled trial[pt] OR clinical trial[pt])'

        try:
            # Search PubMed
            url = f"{self.PUBMED_API}/esearch.fcgi"
            params = {"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"}
            response = self.session.get(url, params=params, timeout=30)
            pmids = response.json().get("esearchresult", {}).get("idlist", [])
            time.sleep(0.35)

            # Fetch details
            if pmids:
                url = f"{self.PUBMED_API}/efetch.fcgi"
                params = {"db": "pubmed", "id": ",".join(pmids[:100]), "retmode": "xml"}
                response = self.session.get(url, params=params, timeout=60)
                nct_ids = set(re.findall(r'NCT\d{8}', response.text))
                time.sleep(0.35)

        except Exception as e:
            print(f"    Error: {e}")

        return nct_ids

    def search_ctgov(self, terms: List[str]) -> Set[str]:
        """Search CT.gov with multiple terms (OR logic)"""
        nct_ids = set()

        for term in terms:
            try:
                params = {
                    "query.intr": term,
                    "fields": "NCTId",
                    "pageSize": 1000
                }
                response = self.session.get(self.CTGOV_API, params=params, timeout=60)
                response.raise_for_status()

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

    def validate_nct_exists(self, nct_ids: Set[str]) -> Set[str]:
        """Filter to only NCT IDs that exist in CT.gov"""
        valid = set()
        for nct_id in list(nct_ids)[:100]:  # Limit
            try:
                url = f"{self.CTGOV_API}/{nct_id}"
                response = self.session.get(url, params={"fields": "NCTId"}, timeout=10)
                if response.status_code == 200:
                    valid.add(nct_id)
                time.sleep(0.1)
            except:
                pass
        return valid

    def test_drug(self, drug: str, condition: str) -> Dict:
        """Test a single drug with and without brand names"""

        print(f"\n  Testing {drug}...")

        # Get gold standard
        gold = self.get_gold_standard(drug, condition)
        gold = self.validate_nct_exists(gold)

        if len(gold) < 10:
            return {"drug": drug, "skipped": True, "reason": f"Only {len(gold)} valid trials"}

        print(f"    Gold standard: {len(gold)} trials")

        # Search with generic name only
        generic_results = self.search_ctgov([drug])
        generic_tp = len(generic_results & gold)
        generic_recall = generic_tp / len(gold)
        print(f"    Generic only: {generic_recall:.1%} ({generic_tp}/{len(gold)})")

        # Search with generic + brand names
        brand_names = self.BRAND_NAMES.get(drug, [])
        if brand_names:
            all_terms = [drug] + brand_names
            expanded_results = self.search_ctgov(all_terms)
            expanded_tp = len(expanded_results & gold)
            expanded_recall = expanded_tp / len(gold)
            print(f"    With brands ({', '.join(brand_names)}): {expanded_recall:.1%} ({expanded_tp}/{len(gold)})")

            improvement = expanded_recall - generic_recall
            new_finds = expanded_results - generic_results
            new_tp = len(new_finds & gold)
            print(f"    Improvement: +{improvement:.1%} ({new_tp} new true positives)")
        else:
            expanded_recall = generic_recall
            improvement = 0
            new_tp = 0

        return {
            "drug": drug,
            "condition": condition,
            "gold_standard": len(gold),
            "generic_recall": generic_recall,
            "expanded_recall": expanded_recall,
            "improvement": improvement,
            "new_true_positives": new_tp,
            "brand_names": brand_names
        }

    def run_test(self, drugs_to_test: List[Tuple[str, str]]):
        """Run brand name expansion test"""

        print("=" * 70)
        print("BRAND NAME EXPANSION TEST")
        print("Does adding brand names improve recall?")
        print("=" * 70)

        results = []

        for drug, condition in drugs_to_test:
            result = self.test_drug(drug, condition)
            if not result.get("skipped"):
                results.append(result)

        # Summary
        print("\n" + "=" * 70)
        print("RESULTS SUMMARY")
        print("=" * 70)

        print("\n| Drug | Generic | +Brands | Improvement | New TPs |")
        print("|------|---------|---------|-------------|---------|")

        total_improvement = 0
        total_new_tp = 0
        drugs_improved = 0

        for r in sorted(results, key=lambda x: x["improvement"], reverse=True):
            imp_str = f"+{r['improvement']:.1%}" if r['improvement'] > 0 else f"{r['improvement']:.1%}"
            print(f"| {r['drug'][:15]} | {r['generic_recall']:.1%} | {r['expanded_recall']:.1%} | {imp_str} | {r['new_true_positives']} |")
            total_improvement += r['improvement']
            total_new_tp += r['new_true_positives']
            if r['improvement'] > 0.005:  # >0.5% improvement
                drugs_improved += 1

        avg_improvement = total_improvement / len(results) if results else 0

        print(f"\n  Drugs tested: {len(results)}")
        print(f"  Drugs with >0.5% improvement: {drugs_improved}")
        print(f"  Average improvement: +{avg_improvement:.2%}")
        print(f"  Total new true positives: {total_new_tp}")

        # Verdict
        print("\n" + "=" * 70)
        print("VERDICT")
        print("=" * 70)

        if avg_improvement > 0.02:  # >2% average improvement
            print("\n  WORTH IT: Brand name expansion provides meaningful improvement")
        elif avg_improvement > 0.005:  # >0.5% average improvement
            print("\n  MARGINAL: Small improvement, may be worth it for high-stakes searches")
        else:
            print("\n  NOT WORTH IT: Brand names don't significantly improve recall")
            print("  CT.gov already normalizes to generic names in intervention field")

        return results


def main():
    # Test a representative sample of drugs
    drugs_to_test = [
        # High-recall drugs
        ("semaglutide", "diabetes OR obesity"),
        ("empagliflozin", "diabetes OR heart failure"),
        ("escitalopram", "depression OR anxiety"),
        ("tiotropium", "COPD"),
        ("tocilizumab", "arthritis"),

        # Medium-recall drugs
        ("adalimumab", "arthritis OR psoriasis"),
        ("atorvastatin", "cardiovascular"),
        ("venlafaxine", "depression"),

        # Lower-recall drugs
        ("pembrolizumab", "cancer"),
        ("rituximab", "lymphoma"),

        # Common drugs
        ("sertraline", "depression"),
        ("lisinopril", "hypertension"),
        ("omeprazole", "GERD"),
        ("gabapentin", "pain"),
    ]

    tester = BrandNameTester()
    tester.run_test(drugs_to_test)


if __name__ == "__main__":
    main()
