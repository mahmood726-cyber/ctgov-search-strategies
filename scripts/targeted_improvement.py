#!/usr/bin/env python3
"""
Targeted Improvement for Problem Drugs
Focuses on the drugs with lowest recall: insulin, metformin, adalimumab

Analyzes missed trials and implements targeted fixes.

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


def wilson_ci(successes: int, n: int) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    z = 1.96
    denom = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denom
    margin = z * math.sqrt((p * (1-p) + z**2 / (4*n)) / n) / denom
    return (max(0, center - margin), min(1, center + margin))


class TargetedImprovement:
    """Targeted improvement for problem drugs"""

    CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"
    PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "TargetedImprove/1.0"})

    def get_gold_standard(self, drug: str, condition: str, max_results: int = 500) -> Set[str]:
        """Get gold standard from PubMed"""
        nct_ids = set()
        query = f'"{drug}"[tiab] AND ({condition})[tiab] AND (randomized controlled trial[pt] OR clinical trial[pt])'

        try:
            url = f"{self.PUBMED_API}/esearch.fcgi"
            params = {"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"}
            response = self.session.get(url, params=params, timeout=30)
            pmids = response.json().get("esearchresult", {}).get("idlist", [])
            time.sleep(0.4)

            if pmids:
                for i in range(0, len(pmids), 100):
                    batch = pmids[i:i+100]
                    url = f"{self.PUBMED_API}/efetch.fcgi"
                    params = {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"}
                    response = self.session.get(url, params=params, timeout=60)
                    nct_ids.update(re.findall(r'NCT\d{8}', response.text))
                    time.sleep(0.4)
        except:
            pass

        # Validate
        valid = set()
        for nct_id in list(nct_ids)[:400]:
            try:
                url = f"{self.CTGOV_API}/{nct_id}"
                response = self.session.get(url, params={"fields": "NCTId"}, timeout=10)
                if response.status_code == 200:
                    valid.add(nct_id)
                time.sleep(0.05)
            except:
                pass
        return valid

    def search_ctgov(self, params: Dict) -> Set[str]:
        """Search CT.gov with pagination"""
        nct_ids = set()
        try:
            next_token = None
            while True:
                req_params = {**params, "fields": "NCTId", "pageSize": 1000}
                if next_token:
                    req_params["pageToken"] = next_token
                response = self.session.get(self.CTGOV_API, params=req_params, timeout=60)
                data = response.json()
                for study in data.get("studies", []):
                    nct_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
                    if nct_id:
                        nct_ids.add(nct_id)
                next_token = data.get("nextPageToken")
                if not next_token:
                    break
                time.sleep(0.15)
        except:
            pass
        return nct_ids

    def analyze_missed_trial(self, nct_id: str, drug: str) -> Dict:
        """Analyze why a trial was missed"""
        try:
            url = f"{self.CTGOV_API}/{nct_id}"
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                return {"error": "not found"}

            data = response.json()
            protocol = data.get("protocolSection", {})

            # Extract all text
            id_module = protocol.get("identificationModule", {})
            desc_module = protocol.get("descriptionModule", {})
            arms_module = protocol.get("armsInterventionsModule", {})
            elig_module = protocol.get("eligibilityModule", {})

            brief_title = id_module.get("briefTitle", "").lower()
            official_title = id_module.get("officialTitle", "").lower()
            brief_summary = desc_module.get("briefSummary", "").lower()
            detailed_desc = desc_module.get("detailedDescription", "").lower()

            interventions = arms_module.get("interventions", [])
            intervention_names = " ".join([i.get("name", "") for i in interventions]).lower()
            intervention_descs = " ".join([i.get("description", "") for i in interventions]).lower()
            other_names = " ".join([" ".join(i.get("otherNames", [])) for i in interventions]).lower()

            arms = arms_module.get("armGroups", [])
            arm_labels = " ".join([a.get("label", "") for a in arms]).lower()
            arm_descs = " ".join([a.get("description", "") for a in arms]).lower()

            eligibility = elig_module.get("eligibilityCriteria", "").lower()

            drug_lower = drug.lower()

            # Check where drug is found
            locations = []
            if drug_lower in brief_title:
                locations.append("brief_title")
            if drug_lower in official_title:
                locations.append("official_title")
            if drug_lower in intervention_names:
                locations.append("intervention_name")
            if drug_lower in intervention_descs:
                locations.append("intervention_desc")
            if drug_lower in other_names:
                locations.append("other_names")
            if drug_lower in brief_summary:
                locations.append("brief_summary")
            if drug_lower in detailed_desc:
                locations.append("detailed_desc")
            if drug_lower in arm_labels:
                locations.append("arm_labels")
            if drug_lower in arm_descs:
                locations.append("arm_descs")
            if drug_lower in eligibility:
                locations.append("eligibility")

            # Check for variants
            all_text = f"{brief_title} {official_title} {intervention_names} {intervention_descs} {other_names} {brief_summary} {arm_descs}"

            return {
                "nct_id": nct_id,
                "locations": locations,
                "drug_found": len(locations) > 0,
                "brief_title": brief_title[:200],
                "intervention_names": intervention_names[:200],
            }
        except Exception as e:
            return {"error": str(e)}

    # =========================================================================
    # INSULIN SPECIFIC STRATEGIES
    # =========================================================================

    def insulin_comprehensive(self) -> Set[str]:
        """Comprehensive insulin search"""
        nct_ids = set()

        # All insulin types
        insulin_terms = [
            # Generic formulations
            "insulin glargine", "insulin lispro", "insulin aspart",
            "insulin detemir", "insulin degludec", "insulin regular",
            "insulin nph", "insulin isophane", "insulin glulisine",
            "insulin human", "insulin analogue", "insulin analog",
            "human insulin", "biosynthetic insulin",

            # Brand names
            "lantus", "humalog", "novolog", "novorapid", "levemir",
            "tresiba", "toujeo", "basaglar", "admelog", "fiasp",
            "apidra", "humulin", "novolin", "afrezza",

            # Categories
            "basal insulin", "bolus insulin", "prandial insulin",
            "long-acting insulin", "rapid-acting insulin", "short-acting insulin",
            "intermediate-acting insulin", "premixed insulin",
            "ultra-long-acting insulin", "insulin pump",

            # Combinations
            "insulin degludec liraglutide", "xultophy",
            "insulin glargine lixisenatide", "soliqua",
        ]

        for term in insulin_terms:
            print(f"    Searching: {term[:30]}...", end=" ", flush=True)
            results = self.search_ctgov({"query.intr": term})
            new = results - nct_ids
            nct_ids.update(results)
            if new:
                print(f"+{len(new)}", end="", flush=True)
            print()

            # Also search AREA fields
            for field in ["BriefTitle", "InterventionName"]:
                results = self.search_ctgov({"query.term": f"AREA[{field}]{term}"})
                new = results - nct_ids
                nct_ids.update(results)

            time.sleep(0.1)

        return nct_ids

    # =========================================================================
    # METFORMIN SPECIFIC STRATEGIES
    # =========================================================================

    def metformin_comprehensive(self) -> Set[str]:
        """Comprehensive metformin search"""
        nct_ids = set()

        metformin_terms = [
            # Names
            "metformin", "glucophage", "fortamet", "glumetza", "riomet",
            "metformin hydrochloride", "metformin hcl", "metformin er",
            "metformin xr",

            # Combinations (very common)
            "metformin sitagliptin", "janumet",
            "metformin glipizide", "metaglip",
            "metformin glyburide", "glucovance",
            "metformin pioglitazone", "actoplus met",
            "metformin rosiglitazone", "avandamet",
            "metformin saxagliptin", "kombiglyze",
            "metformin linagliptin", "jentadueto",
            "metformin alogliptin", "kazano",
            "metformin empagliflozin", "synjardy",
            "metformin dapagliflozin", "xigduo",
            "metformin canagliflozin", "invokamet",
            "metformin ertugliflozin", "segluromet",
            "metformin repaglinide", "prandimet",

            # Class
            "biguanide",
        ]

        for term in metformin_terms:
            print(f"    Searching: {term[:30]}...", end=" ", flush=True)
            results = self.search_ctgov({"query.intr": term})
            new = results - nct_ids
            nct_ids.update(results)
            if new:
                print(f"+{len(new)}", end="", flush=True)
            print()

            for field in ["BriefTitle", "InterventionName"]:
                results = self.search_ctgov({"query.term": f"AREA[{field}]{term}"})
                nct_ids.update(results)

            time.sleep(0.1)

        return nct_ids

    # =========================================================================
    # ADALIMUMAB SPECIFIC STRATEGIES
    # =========================================================================

    def adalimumab_comprehensive(self) -> Set[str]:
        """Comprehensive adalimumab search"""
        nct_ids = set()

        adalimumab_terms = [
            # Names
            "adalimumab", "humira",

            # Biosimilars
            "hadlima", "hyrimoz", "cyltezo", "amjevita",
            "idacio", "hulio", "imraldi", "hefiya",

            # Codes
            "d2e7", "abbott d2e7",

            # Class
            "anti-tnf", "tnf inhibitor", "tnf-alpha inhibitor",
            "tumor necrosis factor inhibitor",
            "anti-tumor necrosis factor",
        ]

        for term in adalimumab_terms:
            print(f"    Searching: {term[:30]}...", end=" ", flush=True)
            results = self.search_ctgov({"query.intr": term})
            new = results - nct_ids
            nct_ids.update(results)
            if new:
                print(f"+{len(new)}", end="", flush=True)
            print()

            for field in ["BriefTitle", "InterventionName", "InterventionDescription"]:
                results = self.search_ctgov({"query.term": f"AREA[{field}]{term}"})
                nct_ids.update(results)

            time.sleep(0.1)

        # Sponsor search
        results = self.search_ctgov({"query.spons": "AbbVie", "query.term": "AREA[StudyType]Interventional"})
        nct_ids.update(results)

        return nct_ids

    def run_targeted_improvement(self, output_dir: str):
        """Run targeted improvement for problem drugs"""

        print("=" * 80)
        print("TARGETED IMPROVEMENT FOR PROBLEM DRUGS")
        print("=" * 80)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results = []

        # Test each problem drug
        problem_drugs = [
            ("insulin", "diabetes", self.insulin_comprehensive),
            ("metformin", "diabetes", self.metformin_comprehensive),
            ("adalimumab", "arthritis OR psoriasis", self.adalimumab_comprehensive),
        ]

        for drug, condition, strategy_func in problem_drugs:
            print(f"\n{'='*60}")
            print(f"DRUG: {drug}")
            print("=" * 60)

            # Get gold standard
            print("\n  Getting gold standard...")
            gold = self.get_gold_standard(drug, condition, max_results=500)
            print(f"  Gold standard: {len(gold)} trials")

            if len(gold) < 10:
                print("  Skipped - too few trials")
                continue

            # Run comprehensive search
            print(f"\n  Running comprehensive {drug} search...")
            found = strategy_func()
            print(f"  Total found: {len(found)} trials")

            # Calculate metrics
            tp = len(found & gold)
            fn = len(gold - found)
            recall = tp / len(gold)

            print(f"\n  RECALL: {recall:.1%} ({tp}/{len(gold)})")
            print(f"  MISSED: {fn} trials")

            # Analyze missed trials
            missed = gold - found
            if missed:
                print(f"\n  Analyzing {min(20, len(missed))} missed trials...")
                missed_analysis = []
                for nct_id in list(missed)[:20]:
                    analysis = self.analyze_missed_trial(nct_id, drug)
                    missed_analysis.append(analysis)
                    if analysis.get("drug_found"):
                        print(f"    {nct_id}: Found in {analysis['locations']}")
                    else:
                        print(f"    {nct_id}: Drug NOT found in record")
                    time.sleep(0.1)

            results.append({
                "drug": drug,
                "condition": condition,
                "gold": len(gold),
                "found": len(found),
                "tp": tp,
                "fn": fn,
                "recall": recall,
            })

        # Summary
        print("\n" + "=" * 80)
        print("TARGETED IMPROVEMENT SUMMARY")
        print("=" * 80)

        for r in results:
            print(f"\n{r['drug']}:")
            print(f"  Recall: {r['recall']:.1%}")
            print(f"  Found: {r['tp']}/{r['gold']}")
            print(f"  Missed: {r['fn']}")

        # Save results
        with open(output_path / "targeted_improvement_results.json", 'w') as f:
            json.dump({"results": results}, f, indent=2)

        print(f"\nResults saved to {output_path}")


def main():
    improver = TargetedImprovement()
    improver.run_targeted_improvement("output/targeted_improvement")


if __name__ == "__main__":
    main()
