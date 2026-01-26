#!/usr/bin/env python3
"""
Enhanced Search Strategy
Addresses the class-to-specific mapping problem identified in gap analysis.

Key insight: Cochrane reviews use generic terms, CT.gov uses specific drugs.
Solution: Expand drug classes to individual drugs.

Author: Mahmood Ahmad
Version: 2.0
"""

import json
import time
import re
from datetime import datetime, timezone
from typing import List, Dict, Set, Tuple
from pathlib import Path
import requests

from drug_expander import DrugNameExpander, ConditionExpander


class DrugClassExpander:
    """
    Expands drug class terms to specific drugs.
    This addresses the main gap identified in analysis.
    """

    # Drug class to specific drugs mapping
    DRUG_CLASSES = {
        # Diabetes drugs
        "dpp-4 inhibitor": [
            "sitagliptin", "linagliptin", "saxagliptin", "alogliptin", "vildagliptin",
            "januvia", "tradjenta", "onglyza", "nesina", "galvus"
        ],
        "dpp4 inhibitor": [
            "sitagliptin", "linagliptin", "saxagliptin", "alogliptin", "vildagliptin"
        ],
        "sglt2 inhibitor": [
            "empagliflozin", "dapagliflozin", "canagliflozin", "ertugliflozin",
            "jardiance", "farxiga", "invokana", "steglatro"
        ],
        "glp-1 agonist": [
            "semaglutide", "liraglutide", "dulaglutide", "exenatide", "tirzepatide",
            "ozempic", "wegovy", "victoza", "trulicity", "byetta", "mounjaro"
        ],
        "glp1 agonist": [
            "semaglutide", "liraglutide", "dulaglutide", "exenatide", "tirzepatide"
        ],
        "thiazolidinedione": [
            "pioglitazone", "rosiglitazone", "actos", "avandia"
        ],
        "sulfonylurea": [
            "glipizide", "glyburide", "glimepiride", "gliclazide",
            "glucotrol", "diabeta", "amaryl"
        ],
        "biguanide": ["metformin", "glucophage"],
        "insulin": [
            "insulin glargine", "insulin lispro", "insulin aspart", "insulin detemir",
            "insulin degludec", "lantus", "humalog", "novolog", "levemir", "tresiba"
        ],

        # Cardiovascular
        "ace inhibitor": [
            "lisinopril", "enalapril", "ramipril", "captopril", "benazepril",
            "prinivil", "zestril", "vasotec", "altace", "capoten"
        ],
        "arb": [
            "losartan", "valsartan", "irbesartan", "olmesartan", "telmisartan",
            "cozaar", "diovan", "avapro", "benicar", "micardis"
        ],
        "angiotensin receptor blocker": [
            "losartan", "valsartan", "irbesartan", "olmesartan", "telmisartan"
        ],
        "beta blocker": [
            "metoprolol", "carvedilol", "bisoprolol", "atenolol", "propranolol",
            "lopressor", "toprol", "coreg", "zebeta", "tenormin", "inderal"
        ],
        "calcium channel blocker": [
            "amlodipine", "diltiazem", "verapamil", "nifedipine",
            "norvasc", "cardizem", "calan", "procardia"
        ],
        "statin": [
            "atorvastatin", "rosuvastatin", "simvastatin", "pravastatin", "lovastatin",
            "lipitor", "crestor", "zocor", "pravachol", "mevacor"
        ],
        "anticoagulant": [
            "warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban",
            "coumadin", "eliquis", "xarelto", "pradaxa", "savaysa", "heparin", "enoxaparin"
        ],
        "antiplatelet": [
            "aspirin", "clopidogrel", "ticagrelor", "prasugrel",
            "plavix", "brilinta", "effient"
        ],
        "diuretic": [
            "furosemide", "hydrochlorothiazide", "spironolactone", "chlorthalidone",
            "lasix", "hctz", "aldactone"
        ],

        # Psychiatry
        "ssri": [
            "sertraline", "fluoxetine", "escitalopram", "citalopram", "paroxetine",
            "zoloft", "prozac", "lexapro", "celexa", "paxil"
        ],
        "snri": [
            "venlafaxine", "duloxetine", "desvenlafaxine",
            "effexor", "cymbalta", "pristiq"
        ],
        "antidepressant": [
            "sertraline", "fluoxetine", "escitalopram", "venlafaxine", "duloxetine",
            "bupropion", "mirtazapine", "trazodone"
        ],
        "antipsychotic": [
            "risperidone", "olanzapine", "quetiapine", "aripiprazole", "clozapine",
            "risperdal", "zyprexa", "seroquel", "abilify", "clozaril"
        ],

        # Respiratory
        "inhaled corticosteroid": [
            "fluticasone", "budesonide", "beclomethasone", "mometasone",
            "flovent", "pulmicort", "qvar", "asmanex"
        ],
        "laba": [
            "salmeterol", "formoterol", "vilanterol",
            "serevent", "foradil"
        ],
        "lama": [
            "tiotropium", "umeclidinium", "glycopyrrolate",
            "spiriva", "incruse"
        ],
        "bronchodilator": [
            "albuterol", "salbutamol", "ipratropium", "tiotropium",
            "ventolin", "proventil", "atrovent", "spiriva"
        ],

        # Rheumatology
        "tnf inhibitor": [
            "adalimumab", "infliximab", "etanercept", "certolizumab", "golimumab",
            "humira", "remicade", "enbrel", "cimzia", "simponi"
        ],
        "anti-tnf": [
            "adalimumab", "infliximab", "etanercept", "certolizumab", "golimumab"
        ],
        "dmard": [
            "methotrexate", "sulfasalazine", "hydroxychloroquine", "leflunomide",
            "rheumatrex", "azulfidine", "plaquenil", "arava"
        ],
        "janus kinase inhibitor": [
            "tofacitinib", "baricitinib", "upadacitinib",
            "xeljanz", "olumiant", "rinvoq"
        ],
        "jak inhibitor": [
            "tofacitinib", "baricitinib", "upadacitinib"
        ],

        # Oncology
        "pd-1 inhibitor": [
            "pembrolizumab", "nivolumab", "cemiplimab",
            "keytruda", "opdivo", "libtayo"
        ],
        "pd-l1 inhibitor": [
            "atezolizumab", "durvalumab", "avelumab",
            "tecentriq", "imfinzi", "bavencio"
        ],
        "checkpoint inhibitor": [
            "pembrolizumab", "nivolumab", "ipilimumab", "atezolizumab",
            "keytruda", "opdivo", "yervoy", "tecentriq"
        ],
        "vegf inhibitor": [
            "bevacizumab", "ramucirumab", "aflibercept",
            "avastin", "cyramza", "eylea"
        ],
        "her2 inhibitor": [
            "trastuzumab", "pertuzumab", "lapatinib", "neratinib",
            "herceptin", "perjeta", "tykerb", "nerlynx"
        ],
        "chemotherapy": [
            "paclitaxel", "docetaxel", "carboplatin", "cisplatin", "doxorubicin",
            "cyclophosphamide", "fluorouracil", "gemcitabine"
        ],

        # Generic terms
        "pharmacotherapy": [],  # Too generic - needs context
        "drug therapy": [],
        "hormone therapy": [
            "estrogen", "progesterone", "testosterone", "tamoxifen", "letrozole",
            "anastrozole", "exemestane"
        ],
        "exercise": ["physical activity", "aerobic exercise", "resistance training", "walking program"],
        "psychotherapy": ["cognitive behavioral therapy", "cbt", "counseling"],
        "cognitive behavioral therapy": ["cbt", "cognitive therapy", "behavioral therapy"],
        "acupuncture": ["electroacupuncture", "traditional acupuncture", "sham acupuncture"],
    }

    def expand_class(self, term: str) -> Set[str]:
        """Expand a drug class term to specific drugs"""
        term_lower = term.lower().strip()
        expanded = {term_lower}

        # Direct lookup
        if term_lower in self.DRUG_CLASSES:
            expanded.update(self.DRUG_CLASSES[term_lower])

        # Partial match
        for class_name, drugs in self.DRUG_CLASSES.items():
            if class_name in term_lower or term_lower in class_name:
                expanded.update(drugs)

        return expanded


class EnhancedValidator:
    """
    Enhanced validation using improved drug class expansion.
    """

    CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "EnhancedValidator/2.0"})
        self.drug_expander = DrugNameExpander()
        self.condition_expander = ConditionExpander()
        self.class_expander = DrugClassExpander()
        self.cache = {}

    def search(self, params: Dict) -> Set[str]:
        """Search CT.gov"""
        cache_key = json.dumps(params, sort_keys=True)
        if cache_key in self.cache:
            return self.cache[cache_key]

        nct_ids = set()
        try:
            search_params = {"fields": "NCTId", "pageSize": 1000}
            search_params.update(params)
            response = self.session.get(self.CTGOV_API, params=search_params, timeout=60)
            response.raise_for_status()

            for study in response.json().get("studies", []):
                nct_id = study.get("protocolSection", {}).get(
                    "identificationModule", {}
                ).get("nctId")
                if nct_id:
                    nct_ids.add(nct_id)

            self.cache[cache_key] = nct_ids
            time.sleep(0.3)
        except:
            pass

        return nct_ids

    def enhanced_search(self, intervention: str, condition: str) -> Set[str]:
        """
        Enhanced search with drug class expansion.
        This is the key improvement over basic search.
        """
        nct_ids = set()

        # 1. Expand intervention to drug names
        intervention_terms = self.drug_expander.expand(intervention, use_api=False)

        # 2. CRITICAL: Expand drug classes to specific drugs
        class_expanded = self.class_expander.expand_class(intervention)
        for drug in class_expanded:
            intervention_terms.update(self.drug_expander.expand(drug, use_api=False))

        # 3. Expand condition
        condition_terms = self.condition_expander.expand(condition)

        # 4. Search all combinations
        for drug in list(intervention_terms)[:15]:  # Limit
            if len(drug) < 3:
                continue

            # Intervention only
            results = self.search({"query.intr": drug})
            nct_ids.update(results)

            # Intervention + condition
            for cond in list(condition_terms)[:5]:
                if len(cond) < 3:
                    continue
                results = self.search({
                    "query.intr": drug,
                    "query.cond": cond
                })
                nct_ids.update(results)

        # 5. Also search condition with RCT filter
        for cond in list(condition_terms)[:5]:
            results = self.search({
                "query.cond": cond,
                "query.term": "AREA[DesignAllocation]RANDOMIZED"
            })
            nct_ids.update(results)

        return nct_ids

    def validate(self, gold_standard_path: str, output_dir: str, max_reviews: int = 20):
        """Run enhanced validation"""

        print("=" * 70)
        print("ENHANCED VALIDATION - With Drug Class Expansion")
        print("=" * 70)

        with open(gold_standard_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        reviews = data.get("reviews", [])[:max_reviews]
        total_gold = sum(len(r["included_nct_ids"]) for r in reviews)

        print(f"\nGold standard: {len(reviews)} reviews, {total_gold} trials")

        total_tp = 0
        total_fn = 0
        total_fp = 0

        for i, review in enumerate(reviews):
            intervention = review["pico"]["intervention"]
            condition = review["pico"]["population"]
            gold_ncts = set(review["included_nct_ids"])

            print(f"\n[{i+1}/{len(reviews)}] {intervention[:40]}...")

            # Run enhanced search
            found = self.enhanced_search(intervention, condition)

            tp = len(found & gold_ncts)
            fn = len(gold_ncts - found)
            fp = len(found - gold_ncts)

            total_tp += tp
            total_fn += fn
            total_fp += fp

            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            print(f"    Recall: {recall:.1%} ({tp}/{tp+fn})")

        # Final results
        final_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
        final_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0

        print(f"\n{'='*70}")
        print("ENHANCED VALIDATION RESULTS")
        print('='*70)
        print(f"\n  Recall: {final_recall:.1%} ({total_tp}/{total_tp + total_fn})")
        print(f"  Precision: {final_precision:.2%}")
        print(f"  TP: {total_tp}, FN: {total_fn}, FP: {total_fp}")

        # Wilson CI
        import math
        n = total_tp + total_fn
        p = final_recall
        z = 1.96
        denom = 1 + z**2 / n
        center = (p + z**2 / (2*n)) / denom
        margin = z * math.sqrt((p * (1-p) + z**2 / (4*n)) / n) / denom
        ci_low = max(0, center - margin)
        ci_high = min(1, center + margin)

        print(f"  95% CI: {ci_low:.1%} - {ci_high:.1%}")

        # Save results
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        with open(output_path / "enhanced_validation_results.json", 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "2.0",
                "method": "Enhanced with drug class expansion",
                "reviews": len(reviews),
                "total_gold": total_gold,
                "recall": final_recall,
                "precision": final_precision,
                "ci_95_lower": ci_low,
                "ci_95_upper": ci_high,
                "tp": total_tp,
                "fn": total_fn,
                "fp": total_fp
            }, f, indent=2)

        print(f"\nResults saved to {output_path / 'enhanced_validation_results.json'}")

        return final_recall


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced Validation")
    parser.add_argument("-g", "--gold-standard",
                       default="data/cochrane_gold_standard.json")
    parser.add_argument("-o", "--output", default="output")
    parser.add_argument("-n", "--max-reviews", type=int, default=20)

    args = parser.parse_args()

    validator = EnhancedValidator()
    validator.validate(args.gold_standard, args.output, args.max_reviews)


if __name__ == "__main__":
    main()
