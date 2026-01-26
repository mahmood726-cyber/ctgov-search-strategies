#!/usr/bin/env python3
"""
Ultra-Maximum Recall Strategy for CT.gov Search

This strategy pushes recall as high as possible by:
1. Searching ALL available CT.gov API fields
2. Using maximum term expansion
3. Including eligibility criteria search
4. Adding sponsor-based searches for industry drugs

Based on targeted improvement analysis findings.

Author: Mahmood Ahmad
Version: 1.0
"""

import json
import time
import re
import math
from typing import Set, Dict, List, Tuple, Optional
from pathlib import Path
from collections import defaultdict
import requests


def wilson_ci(successes: int, n: int) -> Tuple[float, float]:
    """Wilson score confidence interval for proportions"""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    z = 1.96
    denom = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denom
    margin = z * math.sqrt((p * (1-p) + z**2 / (4*n)) / n) / denom
    return (max(0, center - margin), min(1, center + margin))


# Ultra-comprehensive drug variants including problem drug expansions
ULTRA_DRUG_VARIANTS = {
    # =========================================================================
    # PROBLEM DRUGS - MAXIMUM EXPANSION
    # =========================================================================
    "insulin": {
        "names": [
            "insulin", "insulin glargine", "insulin lispro", "insulin aspart",
            "insulin detemir", "insulin degludec", "insulin regular", "insulin nph",
            "insulin isophane", "insulin glulisine", "insulin human", "insulin analog",
            "human insulin", "biosynthetic insulin", "recombinant insulin",
        ],
        "brands": [
            "lantus", "humalog", "novolog", "novorapid", "levemir", "tresiba",
            "toujeo", "basaglar", "admelog", "fiasp", "apidra", "humulin",
            "novolin", "afrezza", "semglee",
        ],
        "class": [
            "basal insulin", "bolus insulin", "prandial insulin",
            "long-acting insulin", "rapid-acting insulin", "short-acting insulin",
            "intermediate-acting insulin", "premixed insulin", "ultra-long-acting insulin",
        ],
        "combinations": [
            "insulin degludec liraglutide", "xultophy",
            "insulin glargine lixisenatide", "soliqua",
        ],
        "search_fields": ["BriefTitle", "InterventionName", "InterventionDescription",
                         "BriefSummary", "DetailedDescription", "ArmGroupDescription"],
    },
    "metformin": {
        "names": [
            "metformin", "metformin hydrochloride", "metformin hcl",
            "metformin er", "metformin xr",
        ],
        "brands": [
            "glucophage", "fortamet", "glumetza", "riomet",
        ],
        "class": ["biguanide"],
        "combinations": [
            "metformin sitagliptin", "janumet",
            "metformin glipizide", "metaglip",
            "metformin glyburide", "glucovance",
            "metformin pioglitazone", "actoplus met",
            "metformin saxagliptin", "kombiglyze",
            "metformin linagliptin", "jentadueto",
            "metformin alogliptin", "kazano",
            "metformin empagliflozin", "synjardy",
            "metformin dapagliflozin", "xigduo",
            "metformin canagliflozin", "invokamet",
            "metformin ertugliflozin", "segluromet",
            "metformin repaglinide", "prandimet",
        ],
        "search_fields": ["BriefTitle", "InterventionName", "InterventionDescription",
                         "BriefSummary", "DetailedDescription", "ArmGroupDescription",
                         "EligibilityCriteria"],
    },
    "adalimumab": {
        "names": ["adalimumab"],
        "brands": ["humira", "hadlima", "hyrimoz", "cyltezo", "amjevita",
                  "idacio", "hulio", "imraldi", "hefiya", "yuflyma", "hadlima"],
        "codes": ["d2e7", "abbott d2e7"],
        "class": ["anti-tnf", "tnf inhibitor", "tnf-alpha inhibitor",
                 "tumor necrosis factor inhibitor", "anti-tumor necrosis factor",
                 "tnf blocker", "anti-tnf-alpha"],
        "sponsor": "AbbVie",
        "search_fields": ["BriefTitle", "InterventionName", "InterventionDescription",
                         "BriefSummary", "DetailedDescription", "ArmGroupDescription"],
    },

    # =========================================================================
    # GLP-1 AGONISTS
    # =========================================================================
    "semaglutide": {
        "names": ["semaglutide"],
        "brands": ["ozempic", "wegovy", "rybelsus"],
        "codes": ["nn9535"],
        "class": ["glp-1", "glp-1 agonist", "glp-1 receptor agonist", "incretin"],
        "sponsor": "Novo Nordisk",
    },
    "liraglutide": {
        "names": ["liraglutide"],
        "brands": ["victoza", "saxenda"],
        "codes": ["nn2211"],
        "class": ["glp-1", "glp-1 agonist", "glp-1 receptor agonist", "incretin"],
        "sponsor": "Novo Nordisk",
    },

    # =========================================================================
    # SGLT2 INHIBITORS
    # =========================================================================
    "empagliflozin": {
        "names": ["empagliflozin"],
        "brands": ["jardiance"],
        "codes": ["bi 10773"],
        "class": ["sglt2", "sglt2 inhibitor", "sglt-2 inhibitor", "sodium-glucose"],
        "sponsor": "Boehringer Ingelheim",
    },
    "dapagliflozin": {
        "names": ["dapagliflozin"],
        "brands": ["farxiga", "forxiga"],
        "codes": ["bms-512148"],
        "class": ["sglt2", "sglt2 inhibitor", "sglt-2 inhibitor", "sodium-glucose"],
        "sponsor": "AstraZeneca",
    },

    # =========================================================================
    # DPP-4 INHIBITORS
    # =========================================================================
    "sitagliptin": {
        "names": ["sitagliptin"],
        "brands": ["januvia"],
        "codes": ["mk-0431"],
        "class": ["dpp-4", "dpp-4 inhibitor", "dipeptidyl peptidase"],
        "sponsor": "Merck",
    },

    # =========================================================================
    # CHECKPOINT INHIBITORS
    # =========================================================================
    "pembrolizumab": {
        "names": ["pembrolizumab"],
        "brands": ["keytruda"],
        "codes": ["mk-3475", "mk3475", "lambrolizumab"],
        "class": ["anti-pd-1", "pd-1 inhibitor", "pd-1 antibody", "checkpoint inhibitor",
                 "immune checkpoint"],
        "sponsor": "Merck",
        "combinations": ["pembrolizumab chemotherapy", "pembrolizumab lenvatinib",
                        "pembrolizumab axitinib"],
    },
    "nivolumab": {
        "names": ["nivolumab"],
        "brands": ["opdivo"],
        "codes": ["bms-936558", "mdx-1106", "ono-4538"],
        "class": ["anti-pd-1", "pd-1 inhibitor", "pd-1 antibody", "checkpoint inhibitor"],
        "sponsor": "Bristol-Myers Squibb",
        "combinations": ["nivolumab ipilimumab"],
    },
    "atezolizumab": {
        "names": ["atezolizumab"],
        "brands": ["tecentriq"],
        "codes": ["mpdl3280a", "rg7446"],
        "class": ["anti-pd-l1", "pd-l1 inhibitor", "pd-l1 antibody", "checkpoint inhibitor"],
        "sponsor": "Roche",
    },

    # =========================================================================
    # MONOCLONAL ANTIBODIES - ONCOLOGY
    # =========================================================================
    "trastuzumab": {
        "names": ["trastuzumab"],
        "brands": ["herceptin", "herzuma", "ogivri", "ontruzant", "trazimera", "kanjinti"],
        "class": ["anti-her2", "her2 antibody", "her-2 inhibitor"],
        "sponsor": "Roche",
        "combinations": ["trastuzumab pertuzumab", "trastuzumab emtansine", "t-dm1",
                        "trastuzumab deruxtecan", "enhertu"],
    },
    "bevacizumab": {
        "names": ["bevacizumab"],
        "brands": ["avastin", "mvasi", "zirabev"],
        "class": ["anti-vegf", "vegf inhibitor", "angiogenesis inhibitor"],
        "sponsor": "Roche",
    },
    "rituximab": {
        "names": ["rituximab"],
        "brands": ["rituxan", "mabthera", "truxima", "ruxience"],
        "class": ["anti-cd20", "cd20 antibody"],
        "sponsor": "Roche",
    },

    # =========================================================================
    # TNF INHIBITORS
    # =========================================================================
    "etanercept": {
        "names": ["etanercept"],
        "brands": ["enbrel", "erelzi", "eticovo"],
        "class": ["anti-tnf", "tnf inhibitor", "tnf receptor"],
        "sponsor": "Amgen",
    },
    "infliximab": {
        "names": ["infliximab"],
        "brands": ["remicade", "inflectra", "renflexis", "ixifi", "avsola"],
        "codes": ["ca2"],
        "class": ["anti-tnf", "tnf inhibitor", "tnf antibody"],
        "sponsor": "Janssen",
    },
    "tocilizumab": {
        "names": ["tocilizumab"],
        "brands": ["actemra", "roactemra"],
        "codes": ["mr16-1", "mra"],
        "class": ["anti-il-6", "il-6 inhibitor", "il-6 receptor antibody"],
        "sponsor": "Roche",
    },
    "secukinumab": {
        "names": ["secukinumab"],
        "brands": ["cosentyx"],
        "codes": ["ain457"],
        "class": ["anti-il-17", "il-17 inhibitor", "il-17a antibody"],
        "sponsor": "Novartis",
    },

    # =========================================================================
    # ANTIDEPRESSANTS
    # =========================================================================
    "escitalopram": {
        "names": ["escitalopram"],
        "brands": ["lexapro", "cipralex"],
        "class": ["ssri", "selective serotonin reuptake inhibitor", "antidepressant"],
    },
    "sertraline": {
        "names": ["sertraline"],
        "brands": ["zoloft"],
        "class": ["ssri", "selective serotonin reuptake inhibitor", "antidepressant"],
    },
    "duloxetine": {
        "names": ["duloxetine"],
        "brands": ["cymbalta"],
        "class": ["snri", "serotonin-norepinephrine reuptake inhibitor", "antidepressant"],
    },
    "quetiapine": {
        "names": ["quetiapine"],
        "brands": ["seroquel"],
        "class": ["atypical antipsychotic", "antipsychotic"],
    },

    # =========================================================================
    # CARDIOVASCULAR
    # =========================================================================
    "atorvastatin": {
        "names": ["atorvastatin"],
        "brands": ["lipitor"],
        "class": ["statin", "hmg-coa reductase inhibitor"],
    },
    "rosuvastatin": {
        "names": ["rosuvastatin"],
        "brands": ["crestor"],
        "class": ["statin", "hmg-coa reductase inhibitor"],
    },
    "apixaban": {
        "names": ["apixaban"],
        "brands": ["eliquis"],
        "class": ["doac", "anticoagulant", "factor xa inhibitor"],
        "sponsor": "Bristol-Myers Squibb",
    },
    "rivaroxaban": {
        "names": ["rivaroxaban"],
        "brands": ["xarelto"],
        "class": ["doac", "anticoagulant", "factor xa inhibitor"],
        "sponsor": "Bayer",
    },

    # =========================================================================
    # RESPIRATORY
    # =========================================================================
    "tiotropium": {
        "names": ["tiotropium"],
        "brands": ["spiriva"],
        "class": ["lama", "long-acting muscarinic antagonist", "anticholinergic"],
        "sponsor": "Boehringer Ingelheim",
    },
    "fluticasone": {
        "names": ["fluticasone", "fluticasone propionate", "fluticasone furoate"],
        "brands": ["flovent", "flonase", "advair", "breo", "arnuity", "trelegy"],
        "class": ["inhaled corticosteroid", "ics", "corticosteroid"],
    },
    "omalizumab": {
        "names": ["omalizumab"],
        "brands": ["xolair"],
        "class": ["anti-ige", "ige antibody"],
        "sponsor": "Novartis",
    },

    # =========================================================================
    # ANTIVIRALS
    # =========================================================================
    "sofosbuvir": {
        "names": ["sofosbuvir"],
        "brands": ["sovaldi", "harvoni", "epclusa", "vosevi"],
        "codes": ["gs-7977", "psi-7977"],
        "class": ["ns5b inhibitor", "hcv polymerase inhibitor", "direct-acting antiviral"],
        "sponsor": "Gilead",
    },
    "tenofovir": {
        "names": ["tenofovir", "tenofovir disoproxil", "tenofovir alafenamide", "tdf", "taf"],
        "brands": ["viread", "truvada", "descovy", "atripla", "complera", "stribild", "genvoya", "biktarvy"],
        "class": ["nrti", "nucleotide reverse transcriptase inhibitor", "antiretroviral"],
        "sponsor": "Gilead",
    },
    "remdesivir": {
        "names": ["remdesivir"],
        "brands": ["veklury"],
        "codes": ["gs-5734"],
        "class": ["antiviral", "rna polymerase inhibitor"],
        "sponsor": "Gilead",
    },
}


class UltraMaximumRecallStrategy:
    """Ultra-maximum recall search strategy for CT.gov"""

    CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"
    PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    # All searchable AREA fields
    ALL_SEARCH_FIELDS = [
        "BriefTitle",
        "OfficialTitle",
        "InterventionName",
        "InterventionDescription",
        "InterventionOtherName",
        "BriefSummary",
        "DetailedDescription",
        "ArmGroupDescription",
        "ArmGroupLabel",
        "EligibilityCriteria",
        "OutcomeMeasure",
        "Keyword",
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "UltraMaxRecall/1.0"})

    def get_gold_standard(self, drug: str, condition: str, max_results: int = 500) -> Set[str]:
        """Get gold standard NCT IDs from PubMed DataBank linkage"""
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
        except Exception:
            pass

        # Validate NCT IDs exist
        valid = set()
        for nct_id in list(nct_ids)[:400]:
            try:
                url = f"{self.CTGOV_API}/{nct_id}"
                response = self.session.get(url, params={"fields": "NCTId"}, timeout=10)
                if response.status_code == 200:
                    valid.add(nct_id)
                time.sleep(0.05)
            except Exception:
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
        except Exception:
            pass
        return nct_ids

    def ultra_search_drug(self, drug: str) -> Set[str]:
        """Ultra-comprehensive search for a drug"""
        nct_ids = set()
        variants = ULTRA_DRUG_VARIANTS.get(drug, {"names": [drug]})

        # Collect all search terms
        all_terms = set()
        all_terms.update(variants.get("names", []))
        all_terms.update(variants.get("brands", []))
        all_terms.update(variants.get("codes", []))
        all_terms.update(variants.get("class", []))
        all_terms.update(variants.get("combinations", []))

        # Get custom search fields or use all
        search_fields = variants.get("search_fields", self.ALL_SEARCH_FIELDS)

        # Strategy 1: Intervention search
        for term in all_terms:
            results = self.search_ctgov({"query.intr": term})
            nct_ids.update(results)
            time.sleep(0.1)

        # Strategy 2: AREA field searches
        for term in all_terms:
            for field in search_fields:
                results = self.search_ctgov({"query.term": f"AREA[{field}]{term}"})
                nct_ids.update(results)
            time.sleep(0.1)

        # Strategy 3: Sponsor search (if applicable)
        sponsor = variants.get("sponsor")
        if sponsor:
            results = self.search_ctgov({
                "query.spons": sponsor,
                "query.term": "AREA[StudyType]Interventional"
            })
            nct_ids.update(results)

        return nct_ids

    def validate_drugs(self, drugs: List[Dict], output_dir: str):
        """Validate ultra-maximum strategy on multiple drugs"""
        print("=" * 80)
        print("ULTRA-MAXIMUM RECALL STRATEGY VALIDATION")
        print("=" * 80)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results = []
        total_gold = 0
        total_found = 0

        for i, drug_info in enumerate(drugs, 1):
            drug = drug_info["drug"]
            condition = drug_info["condition"]

            print(f"\n[{i}/{len(drugs)}] {drug}")

            # Get gold standard
            gold = self.get_gold_standard(drug, condition)
            if len(gold) < 10:
                print(f"  Skipped - only {len(gold)} gold standard trials")
                continue

            # Run ultra search
            print(f"  Gold: {len(gold)} | Ultra: ", end="", flush=True)
            found = self.ultra_search_drug(drug)
            print(f"{len(found)} trials")

            # Calculate metrics
            tp = len(found & gold)
            fn = len(gold - found)
            recall = tp / len(gold) if gold else 0

            # Wilson CI
            ci_low, ci_high = wilson_ci(tp, len(gold))

            results.append({
                "drug": drug,
                "condition": condition,
                "gold": len(gold),
                "found": len(found),
                "tp": tp,
                "fn": fn,
                "recall": recall,
                "recall_ci_low": ci_low,
                "recall_ci_high": ci_high,
            })

            total_gold += len(gold)
            total_found += tp

            print(f"  Recall: {recall:.1%} ({tp}/{len(gold)}) [95% CI: {ci_low:.1%}-{ci_high:.1%}]")

        # Summary
        print("\n" + "=" * 80)
        print("ULTRA-MAXIMUM RECALL SUMMARY")
        print("=" * 80)

        if total_gold > 0:
            overall_recall = total_found / total_gold
            ci_low, ci_high = wilson_ci(total_found, total_gold)

            print(f"\nDrugs tested: {len(results)}")
            print(f"Total trials: {total_gold}")
            print(f"Found: {total_found}")
            print(f"Missed: {total_gold - total_found}")
            print(f"\nOVERALL RECALL: {overall_recall:.1%} (95% CI: {ci_low:.1%}-{ci_high:.1%})")

            # Best/worst performers
            sorted_results = sorted(results, key=lambda x: x["recall"], reverse=True)
            print(f"\nBEST PERFORMERS:")
            for r in sorted_results[:5]:
                print(f"  {r['drug']}: {r['recall']:.1%}")

            print(f"\nNEEDS IMPROVEMENT:")
            for r in sorted_results[-5:]:
                print(f"  {r['drug']}: {r['recall']:.1%} (missed {r['fn']})")

        # Save results
        with open(output_path / "ultra_maximum_results.json", 'w') as f:
            json.dump({
                "overall_recall": overall_recall if total_gold > 0 else 0,
                "overall_ci_low": ci_low if total_gold > 0 else 0,
                "overall_ci_high": ci_high if total_gold > 0 else 0,
                "total_gold": total_gold,
                "total_found": total_found,
                "results": results
            }, f, indent=2)

        print(f"\nResults saved to {output_path}")


def main():
    strategy = UltraMaximumRecallStrategy()

    # Test on all drugs with expanded problem drug coverage
    drugs = [
        # GLP-1 agonists
        {"drug": "semaglutide", "condition": "diabetes OR obesity"},
        {"drug": "liraglutide", "condition": "diabetes OR obesity"},

        # SGLT2 inhibitors
        {"drug": "empagliflozin", "condition": "diabetes OR heart failure"},
        {"drug": "dapagliflozin", "condition": "diabetes OR heart failure"},

        # DPP-4 inhibitors
        {"drug": "sitagliptin", "condition": "diabetes"},

        # Problem drugs
        {"drug": "metformin", "condition": "diabetes OR pcos OR cancer"},
        {"drug": "insulin", "condition": "diabetes"},

        # Checkpoint inhibitors
        {"drug": "pembrolizumab", "condition": "cancer OR melanoma OR lung"},
        {"drug": "nivolumab", "condition": "cancer OR melanoma OR lung"},
        {"drug": "atezolizumab", "condition": "cancer OR lung"},

        # Other oncology
        {"drug": "trastuzumab", "condition": "breast cancer OR her2"},
        {"drug": "bevacizumab", "condition": "cancer"},
        {"drug": "rituximab", "condition": "lymphoma OR leukemia OR arthritis"},

        # TNF inhibitors (problem area)
        {"drug": "adalimumab", "condition": "arthritis OR psoriasis OR crohn"},
        {"drug": "etanercept", "condition": "arthritis OR psoriasis"},
        {"drug": "infliximab", "condition": "arthritis OR crohn OR colitis"},
        {"drug": "tocilizumab", "condition": "arthritis OR covid"},
        {"drug": "secukinumab", "condition": "psoriasis OR arthritis"},

        # Antidepressants
        {"drug": "escitalopram", "condition": "depression OR anxiety"},
        {"drug": "sertraline", "condition": "depression OR anxiety"},
        {"drug": "duloxetine", "condition": "depression OR pain OR fibromyalgia"},
        {"drug": "quetiapine", "condition": "bipolar OR schizophrenia OR depression"},

        # Cardiovascular
        {"drug": "atorvastatin", "condition": "hyperlipidemia OR cardiovascular"},
        {"drug": "rosuvastatin", "condition": "hyperlipidemia OR cardiovascular"},
        {"drug": "apixaban", "condition": "atrial fibrillation OR thrombosis"},
        {"drug": "rivaroxaban", "condition": "atrial fibrillation OR thrombosis"},

        # Respiratory
        {"drug": "tiotropium", "condition": "copd OR asthma"},
        {"drug": "fluticasone", "condition": "asthma OR copd"},
        {"drug": "omalizumab", "condition": "asthma"},

        # Antivirals
        {"drug": "sofosbuvir", "condition": "hepatitis c OR hcv"},
        {"drug": "tenofovir", "condition": "hiv OR hepatitis b OR hbv"},
        {"drug": "remdesivir", "condition": "covid OR coronavirus"},
    ]

    strategy.validate_drugs(drugs, "output/ultra_maximum")


if __name__ == "__main__":
    main()
