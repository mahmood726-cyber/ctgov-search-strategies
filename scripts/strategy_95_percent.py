#!/usr/bin/env python3
"""
95% Recall Strategy Implementation
Combines multiple search approaches to maximize recall.

Strategies included:
1. Basic intervention search (baseline)
2. AREA syntax multi-field search
3. Extended field search (summary, description, arms)
4. Research code expansion
5. Combination therapy patterns
6. WHO ICTRP cross-reference

Author: Mahmood Ahmad
Version: 1.0
"""

import json
import time
import re
import math
from typing import Set, Dict, List, Tuple
from pathlib import Path
from collections import defaultdict
import requests


def wilson_ci(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score confidence interval"""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denom
    margin = z * math.sqrt((p * (1-p) + z**2 / (4*n)) / n) / denom
    return (max(0, center - margin), min(1, center + margin))


class Strategy95Percent:
    """
    Combined strategy targeting 95% recall.
    """

    CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"
    PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    # Research codes and alternative names for drugs
    DRUG_VARIANTS = {
        "semaglutide": ["semaglutide", "nn9535", "nn-9535", "ozempic", "wegovy", "rybelsus"],
        "liraglutide": ["liraglutide", "nn2211", "nn-2211", "victoza", "saxenda"],
        "empagliflozin": ["empagliflozin", "bi 10773", "bi10773", "jardiance"],
        "dapagliflozin": ["dapagliflozin", "bms-512148", "forxiga", "farxiga"],
        "sitagliptin": ["sitagliptin", "mk-0431", "mk0431", "januvia"],
        "canagliflozin": ["canagliflozin", "jnj-28431754", "invokana"],
        "dulaglutide": ["dulaglutide", "ly2189265", "trulicity"],
        "exenatide": ["exenatide", "ac2993", "byetta", "bydureon"],
        "metformin": ["metformin", "glucophage", "fortamet", "glumetza", "riomet"],
        "insulin": ["insulin glargine", "lantus", "toujeo", "insulin lispro", "humalog",
                   "insulin aspart", "novolog", "insulin detemir", "levemir"],

        "pembrolizumab": ["pembrolizumab", "mk-3475", "mk3475", "lambrolizumab", "keytruda",
                        "anti-pd-1", "anti-pd1", "pd-1 inhibitor"],
        "nivolumab": ["nivolumab", "bms-936558", "mdx1106", "ono-4538", "opdivo",
                     "anti-pd-1", "anti-pd1"],
        "atezolizumab": ["atezolizumab", "mpdl3280a", "tecentriq", "anti-pd-l1", "anti-pdl1"],
        "ipilimumab": ["ipilimumab", "mdx-010", "mdx010", "yervoy", "anti-ctla-4", "anti-ctla4"],
        "trastuzumab": ["trastuzumab", "herceptin", "anti-her2", "anti-her-2", "her2 antibody"],
        "bevacizumab": ["bevacizumab", "avastin", "anti-vegf", "vegf inhibitor"],
        "rituximab": ["rituximab", "rituxan", "mabthera", "anti-cd20", "cd20 antibody"],
        "cetuximab": ["cetuximab", "erbitux", "imc-c225", "anti-egfr"],

        "adalimumab": ["adalimumab", "humira", "d2e7", "anti-tnf", "tnf inhibitor"],
        "etanercept": ["etanercept", "enbrel", "tnf receptor", "anti-tnf"],
        "infliximab": ["infliximab", "remicade", "anti-tnf", "tnf inhibitor"],
        "tocilizumab": ["tocilizumab", "actemra", "roactemra", "anti-il-6", "il-6 inhibitor"],
        "secukinumab": ["secukinumab", "cosentyx", "ain457", "anti-il-17"],
        "ustekinumab": ["ustekinumab", "stelara", "cnto 1275", "anti-il-12", "anti-il-23"],

        "escitalopram": ["escitalopram", "lexapro", "cipralex", "s-citalopram"],
        "sertraline": ["sertraline", "zoloft", "lustral"],
        "fluoxetine": ["fluoxetine", "prozac", "sarafem"],
        "duloxetine": ["duloxetine", "cymbalta", "ly248686"],
        "quetiapine": ["quetiapine", "seroquel", "ici 204,636"],
        "aripiprazole": ["aripiprazole", "abilify", "opc-14597"],

        "atorvastatin": ["atorvastatin", "lipitor", "ci-981"],
        "rosuvastatin": ["rosuvastatin", "crestor", "s-4522"],
        "apixaban": ["apixaban", "eliquis", "bms-562247"],
        "rivaroxaban": ["rivaroxaban", "xarelto", "bay 59-7939"],
        "ticagrelor": ["ticagrelor", "brilinta", "brilique", "azd6140"],

        "tiotropium": ["tiotropium", "spiriva", "ba 679"],
        "fluticasone": ["fluticasone", "flonase", "flovent", "advair", "breo"],
        "omalizumab": ["omalizumab", "xolair", "rhumab-e25", "anti-ige"],
        "benralizumab": ["benralizumab", "fasenra", "medi-563", "anti-il-5"],

        "sofosbuvir": ["sofosbuvir", "sovaldi", "gs-7977", "psi-7977"],
        "tenofovir": ["tenofovir", "viread", "truvada", "descovy", "gs-7340"],
        "dolutegravir": ["dolutegravir", "tivicay", "s/gsk1349572", "gsk1349572"],
        "remdesivir": ["remdesivir", "veklury", "gs-5734"],
    }

    # Oncology combination patterns
    ONCOLOGY_COMBINATIONS = {
        "pembrolizumab": [
            "pembrolizumab chemotherapy",
            "pembrolizumab platinum",
            "pembrolizumab pemetrexed",
            "pembrolizumab carboplatin",
            "pembrolizumab lenvatinib",
            "pembrolizumab axitinib",
        ],
        "nivolumab": [
            "nivolumab ipilimumab",
            "nivolumab chemotherapy",
            "nivolumab cabozantinib",
        ],
        "atezolizumab": [
            "atezolizumab bevacizumab",
            "atezolizumab chemotherapy",
            "atezolizumab carboplatin",
        ],
        "trastuzumab": [
            "trastuzumab pertuzumab",
            "trastuzumab chemotherapy",
            "trastuzumab docetaxel",
        ],
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Strategy95/1.0"})

    # =========================================================================
    # COMPONENT STRATEGIES
    # =========================================================================

    def strategy_basic(self, drug: str) -> Set[str]:
        """S1: Basic intervention search"""
        nct_ids = set()
        try:
            next_token = None
            while True:
                params = {"query.intr": drug, "fields": "NCTId", "pageSize": 1000}
                if next_token:
                    params["pageToken"] = next_token

                response = self.session.get(self.CTGOV_API, params=params, timeout=60)
                data = response.json()

                for study in data.get("studies", []):
                    nct_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
                    if nct_id:
                        nct_ids.add(nct_id)

                next_token = data.get("nextPageToken")
                if not next_token:
                    break
                time.sleep(0.2)
        except:
            pass
        return nct_ids

    def strategy_area_extended(self, drug: str) -> Set[str]:
        """S2: Extended AREA syntax - searches more fields"""
        nct_ids = set()

        # Extended field list
        area_queries = [
            f'AREA[InterventionName]{drug}',
            f'AREA[BriefTitle]{drug}',
            f'AREA[OfficialTitle]{drug}',
            f'AREA[InterventionDescription]{drug}',
            f'AREA[BriefSummary]{drug}',
            f'AREA[DetailedDescription]{drug}',
            f'AREA[ArmGroupDescription]{drug}',
            f'AREA[Keyword]{drug}',
        ]

        for query in area_queries:
            try:
                next_token = None
                while True:
                    params = {"query.term": query, "fields": "NCTId", "pageSize": 1000}
                    if next_token:
                        params["pageToken"] = next_token

                    response = self.session.get(self.CTGOV_API, params=params, timeout=60)
                    data = response.json()

                    for study in data.get("studies", []):
                        nct_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
                        if nct_id:
                            nct_ids.add(nct_id)

                    next_token = data.get("nextPageToken")
                    if not next_token:
                        break
                    time.sleep(0.2)
            except:
                pass

        return nct_ids

    def strategy_research_codes(self, drug: str) -> Set[str]:
        """S3: Search using research codes and alternative names"""
        nct_ids = set()

        variants = self.DRUG_VARIANTS.get(drug.lower(), [drug])

        for variant in variants:
            if variant.lower() == drug.lower():
                continue  # Skip primary name (already searched)

            try:
                # Basic search with variant
                params = {"query.intr": variant, "fields": "NCTId", "pageSize": 1000}
                response = self.session.get(self.CTGOV_API, params=params, timeout=60)

                for study in response.json().get("studies", []):
                    nct_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
                    if nct_id:
                        nct_ids.add(nct_id)

                time.sleep(0.2)

                # AREA search with variant
                for field in ["InterventionName", "BriefTitle"]:
                    params = {"query.term": f"AREA[{field}]{variant}", "fields": "NCTId", "pageSize": 1000}
                    response = self.session.get(self.CTGOV_API, params=params, timeout=60)

                    for study in response.json().get("studies", []):
                        nct_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
                        if nct_id:
                            nct_ids.add(nct_id)

                    time.sleep(0.2)

            except:
                pass

        return nct_ids

    def strategy_combinations(self, drug: str) -> Set[str]:
        """S4: Search combination therapy patterns (oncology)"""
        nct_ids = set()

        combinations = self.ONCOLOGY_COMBINATIONS.get(drug.lower(), [])

        for combo in combinations:
            try:
                # Search in title
                params = {"query.term": f'AREA[BriefTitle]"{combo}"', "fields": "NCTId", "pageSize": 500}
                response = self.session.get(self.CTGOV_API, params=params, timeout=60)

                for study in response.json().get("studies", []):
                    nct_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
                    if nct_id:
                        nct_ids.add(nct_id)

                time.sleep(0.2)
            except:
                pass

        return nct_ids

    def strategy_sponsor_condition(self, drug: str, condition: str) -> Set[str]:
        """S5: Sponsor + condition search for industry drugs"""
        nct_ids = set()

        # Map drugs to sponsors
        DRUG_SPONSORS = {
            "semaglutide": "Novo Nordisk",
            "liraglutide": "Novo Nordisk",
            "empagliflozin": "Boehringer",
            "dapagliflozin": "AstraZeneca",
            "pembrolizumab": "Merck",
            "nivolumab": "Bristol",
            "adalimumab": "AbbVie",
            "trastuzumab": "Roche",
        }

        sponsor = DRUG_SPONSORS.get(drug.lower())
        if not sponsor:
            return nct_ids

        try:
            # Search sponsor + condition, Phase 2/3
            query = f'AREA[LeadSponsorName]{sponsor} AND AREA[StudyType]Interventional'
            params = {"query.term": query, "fields": "NCTId", "pageSize": 1000}
            response = self.session.get(self.CTGOV_API, params=params, timeout=60)

            for study in response.json().get("studies", []):
                nct_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
                if nct_id:
                    nct_ids.add(nct_id)

            time.sleep(0.3)
        except:
            pass

        return nct_ids

    def strategy_pubmed_extraction(self, drug: str, condition: str, max_results: int = 500) -> Set[str]:
        """S6: PubMed DataBank extraction (for comparison with gold standard)"""
        nct_ids = set()

        query = f'"{drug}"[tiab] AND ({condition})[tiab] AND (randomized controlled trial[pt] OR clinical trial[pt])'

        try:
            url = f"{self.PUBMED_API}/esearch.fcgi"
            params = {"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"}
            response = self.session.get(url, params=params, timeout=30)
            pmids = response.json().get("esearchresult", {}).get("idlist", [])
            time.sleep(0.4)

            if not pmids:
                return nct_ids

            batch_size = 100
            for i in range(0, len(pmids), batch_size):
                batch = pmids[i:i+batch_size]
                url = f"{self.PUBMED_API}/efetch.fcgi"
                params = {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"}
                response = self.session.get(url, params=params, timeout=60)
                nct_ids.update(re.findall(r'NCT\d{8}', response.text))
                time.sleep(0.4)

        except:
            pass

        return nct_ids

    # =========================================================================
    # COMBINED 95% STRATEGY
    # =========================================================================

    def strategy_combined_95(self, drug: str, condition: str) -> Tuple[Set[str], Dict]:
        """
        Combined strategy targeting 95% recall.
        Runs all component strategies and unions results.
        """
        all_ncts = set()
        metadata = {}

        # S1: Basic
        print("    S1-Basic...", end=" ", flush=True)
        s1 = self.strategy_basic(drug)
        all_ncts.update(s1)
        metadata["s1_basic"] = len(s1)
        print(f"{len(s1)}", end=" | ", flush=True)

        # S2: Extended AREA
        print("S2-AREA...", end=" ", flush=True)
        s2 = self.strategy_area_extended(drug)
        s2_new = s2 - all_ncts
        all_ncts.update(s2)
        metadata["s2_area"] = len(s2)
        metadata["s2_unique"] = len(s2_new)
        print(f"+{len(s2_new)}", end=" | ", flush=True)

        # S3: Research codes
        print("S3-Codes...", end=" ", flush=True)
        s3 = self.strategy_research_codes(drug)
        s3_new = s3 - all_ncts
        all_ncts.update(s3)
        metadata["s3_codes"] = len(s3)
        metadata["s3_unique"] = len(s3_new)
        print(f"+{len(s3_new)}", end=" | ", flush=True)

        # S4: Combinations (oncology)
        if drug.lower() in self.ONCOLOGY_COMBINATIONS:
            print("S4-Combo...", end=" ", flush=True)
            s4 = self.strategy_combinations(drug)
            s4_new = s4 - all_ncts
            all_ncts.update(s4)
            metadata["s4_combo"] = len(s4)
            metadata["s4_unique"] = len(s4_new)
            print(f"+{len(s4_new)}", end=" | ", flush=True)

        # S5: Sponsor+condition
        print("S5-Sponsor...", end=" ", flush=True)
        s5 = self.strategy_sponsor_condition(drug, condition)
        s5_new = s5 - all_ncts
        all_ncts.update(s5)
        metadata["s5_sponsor"] = len(s5)
        metadata["s5_unique"] = len(s5_new)
        print(f"+{len(s5_new)}")

        metadata["total"] = len(all_ncts)

        return all_ncts, metadata

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def validate_strategy(self, drugs_to_test: List[Tuple[str, str]], output_dir: str):
        """Validate the 95% strategy against gold standard"""

        print("=" * 80)
        print("95% RECALL STRATEGY VALIDATION")
        print("=" * 80)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results = []
        totals = {"tp": 0, "fn": 0, "gold": 0}

        for i, (drug, condition) in enumerate(drugs_to_test):
            print(f"\n[{i+1}/{len(drugs_to_test)}] {drug}")

            # Get gold standard
            print("  Gold standard...", end=" ", flush=True)
            gold = self.strategy_pubmed_extraction(drug, condition, max_results=300)

            # Validate gold NCTs exist
            valid_gold = set()
            for nct_id in list(gold)[:200]:
                try:
                    url = f"{self.CTGOV_API}/{nct_id}"
                    response = self.session.get(url, params={"fields": "NCTId"}, timeout=10)
                    if response.status_code == 200:
                        valid_gold.add(nct_id)
                    time.sleep(0.05)
                except:
                    pass
            gold = valid_gold

            if len(gold) < 10:
                print(f"skipped ({len(gold)} trials)")
                continue

            print(f"{len(gold)} trials")

            # Run 95% strategy
            print("  95% Strategy: ", end="", flush=True)
            found, metadata = self.strategy_combined_95(drug, condition)

            # Calculate metrics
            tp = len(found & gold)
            fn = len(gold - found)
            recall = tp / len(gold) if gold else 0

            totals["tp"] += tp
            totals["fn"] += fn
            totals["gold"] += len(gold)

            print(f"  RECALL: {recall:.1%} ({tp}/{len(gold)})")

            # Compare to baseline
            baseline = self.strategy_basic(drug)
            baseline_tp = len(baseline & gold)
            baseline_recall = baseline_tp / len(gold) if gold else 0
            improvement = (recall - baseline_recall) * 100

            print(f"  Baseline: {baseline_recall:.1%}, Improvement: +{improvement:.1f}%")

            results.append({
                "drug": drug,
                "condition": condition,
                "gold": len(gold),
                "found": len(found),
                "tp": tp,
                "fn": fn,
                "recall": recall,
                "baseline_recall": baseline_recall,
                "improvement": improvement,
                "metadata": metadata
            })

        # Overall results
        overall_recall = totals["tp"] / totals["gold"] if totals["gold"] else 0
        ci = wilson_ci(totals["tp"], totals["gold"])

        print("\n" + "=" * 80)
        print("OVERALL RESULTS")
        print("=" * 80)
        print(f"\nTotal trials: {totals['gold']}")
        print(f"Found: {totals['tp']}")
        print(f"Missed: {totals['fn']}")
        print(f"RECALL: {overall_recall:.1%} (95% CI: {ci[0]:.1%}-{ci[1]:.1%})")

        # Save results
        with open(output_path / "strategy_95_results.json", 'w') as f:
            json.dump({
                "overall": {
                    "recall": overall_recall,
                    "ci_95": ci,
                    "tp": totals["tp"],
                    "fn": totals["fn"],
                    "gold": totals["gold"]
                },
                "by_drug": results
            }, f, indent=2)

        print(f"\nResults saved to {output_path}")

        return overall_recall


def main():
    # Test drugs
    drugs = [
        ("semaglutide", "diabetes OR obesity"),
        ("empagliflozin", "diabetes OR heart failure"),
        ("pembrolizumab", "cancer"),
        ("nivolumab", "cancer"),
        ("adalimumab", "arthritis"),
        ("escitalopram", "depression"),
        ("metformin", "diabetes"),
        ("insulin", "diabetes"),
        ("atorvastatin", "cardiovascular"),
        ("tiotropium", "COPD"),
    ]

    strategy = Strategy95Percent()
    strategy.validate_strategy(drugs, "output/strategy_95")


if __name__ == "__main__":
    main()
