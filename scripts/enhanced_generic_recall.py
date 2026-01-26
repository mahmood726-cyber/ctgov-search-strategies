#!/usr/bin/env python3
"""
Enhanced Generic Drug Recall Module

Comprehensive synonym expansion for generic drugs with poor baseline recall.
Includes international drug names (INN, BAN, JAN), delivery devices, and combinations.

Target drugs:
- Insulin: 12.7% -> 85%+ recall
- Metformin: 26.8% -> 85%+ recall

Author: CT.gov Search Strategy Team
Version: 1.0
"""

import json
import time
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import sys

import requests

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ctgov_config import CTGOV_API, DEFAULT_TIMEOUT


@dataclass
class DrugSynonymExpansion:
    """Comprehensive drug synonym expansion."""
    drug: str
    generic_names: List[str] = field(default_factory=list)
    brand_names: List[str] = field(default_factory=list)
    international_names: Dict[str, List[str]] = field(default_factory=dict)  # {language: names}
    formulations: List[str] = field(default_factory=list)
    delivery_devices: List[str] = field(default_factory=list)
    combinations: List[str] = field(default_factory=list)
    research_codes: List[str] = field(default_factory=list)
    mechanism_terms: List[str] = field(default_factory=list)
    class_terms: List[str] = field(default_factory=list)

    def get_all_terms(self) -> List[str]:
        """Get all search terms."""
        terms = []
        terms.extend(self.generic_names)
        terms.extend(self.brand_names)
        for lang_names in self.international_names.values():
            terms.extend(lang_names)
        terms.extend(self.formulations)
        terms.extend(self.delivery_devices)
        terms.extend(self.combinations)
        terms.extend(self.research_codes)
        terms.extend(self.mechanism_terms)

        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for term in terms:
            if term.lower() not in seen:
                seen.add(term.lower())
                unique.append(term)

        return unique


# Comprehensive insulin expansion
INSULIN_EXPANSION = DrugSynonymExpansion(
    drug="insulin",
    generic_names=[
        "insulin",
        "insulin human",
        "human insulin",
        "recombinant human insulin",
        "biosynthetic human insulin",
    ],
    brand_names=[
        # Rapid-acting
        "Humalog", "NovoLog", "Novolog", "Apidra", "Fiasp", "Lyumjev", "Admelog", "Afrezza",
        # Short-acting
        "Humulin R", "Novolin R", "Actrapid", "Velosulin",
        # Intermediate-acting
        "Humulin N", "Novolin N", "NPH", "Insulatard",
        # Long-acting
        "Lantus", "Levemir", "Tresiba", "Toujeo", "Basaglar", "Semglee",
        # Biosimilars
        "Admelog", "Basaglar", "Semglee", "Rezvoglar",
        # Premixed
        "Humalog Mix", "Novolog Mix", "Humulin 70/30", "Novolin 70/30", "Ryzodeg",
    ],
    international_names={
        "INN": ["insulin", "insulinum"],
        "Spanish": ["insulina"],
        "French": ["insuline"],
        "German": ["Insulin"],
        "Portuguese": ["insulina"],
        "Italian": ["insulina"],
        "Japanese": ["インスリン"],
        "Chinese": ["胰岛素"],
    },
    formulations=[
        # Specific insulin types (CRITICAL for recall)
        "insulin glargine", "glargine",
        "insulin lispro", "lispro",
        "insulin aspart", "aspart",
        "insulin detemir", "detemir",
        "insulin degludec", "degludec",
        "insulin glulisine", "glulisine",
        "insulin isophane", "isophane insulin", "NPH insulin",
        "insulin zinc", "zinc insulin",
        "protamine zinc insulin", "PZI",
        "insulin regular", "regular insulin",
        "insulin neutral",
        "insulin icodec", "icodec",  # Weekly insulin
        # Concentrations
        "U-100 insulin", "U-200 insulin", "U-300 insulin", "U-500 insulin",
    ],
    delivery_devices=[
        "insulin pen", "insulin pump", "insulin syringe",
        "insulin inhaler", "inhaled insulin",
        "insulin patch", "insulin patch pump",
        "closed loop insulin", "artificial pancreas",
        "automated insulin delivery", "AID",
        "continuous subcutaneous insulin infusion", "CSII",
        "multiple daily injections", "MDI",
    ],
    combinations=[
        # GLP-1 combinations
        "insulin degludec/liraglutide", "IDegLira", "Xultophy",
        "insulin glargine/lixisenatide", "iGlarLixi", "Soliqua",
        # Other combinations
        "insulin/pramlintide",
    ],
    research_codes=[
        "LY275585", "LY2605541", "LY2963016",  # Lilly
        "HOE 901", "HOE901",  # Sanofi (glargine)
        "NN1250", "NN9535",  # Novo Nordisk
        "BIL 2014", "BIL2014",  # Biocon
    ],
    mechanism_terms=[
        "basal insulin", "bolus insulin", "prandial insulin",
        "long-acting insulin", "ultra-long-acting insulin",
        "rapid-acting insulin", "fast-acting insulin",
        "intermediate-acting insulin",
        "short-acting insulin",
        "basal-bolus insulin", "basal-bolus therapy",
        "intensive insulin therapy",
        "insulin analog", "insulin analogue",
    ],
    class_terms=[
        "exogenous insulin",
        "subcutaneous insulin",
        "intravenous insulin",
    ]
)


# Comprehensive metformin expansion
METFORMIN_EXPANSION = DrugSynonymExpansion(
    drug="metformin",
    generic_names=[
        "metformin",
        "metformin hydrochloride",
        "metformin HCl",
        "metformin XR",
        "metformin ER",
        "extended-release metformin",
    ],
    brand_names=[
        "Glucophage", "Glucophage XR",
        "Fortamet", "Glumetza", "Riomet",
        "Glycon", "Diabex", "Diaformin",
        "Glucomet", "Metforal", "Siofor",
    ],
    international_names={
        "INN": ["metformin", "metforminum"],
        "BAN": ["metformin"],
        "Spanish": ["metformina"],
        "French": ["metformine"],
        "German": ["Metformin"],
        "Portuguese": ["metformina"],
        "Italian": ["metformina"],
        "Japanese": ["メトホルミン"],
        "Chinese": ["二甲双胍"],
    },
    formulations=[
        "immediate-release metformin",
        "sustained-release metformin",
        "modified-release metformin",
        "gastroretentive metformin",
    ],
    delivery_devices=[],  # Oral only
    combinations=[
        # DPP-4 inhibitors
        "metformin/sitagliptin", "sitagliptin/metformin", "Janumet", "Janumet XR",
        "metformin/saxagliptin", "saxagliptin/metformin", "Kombiglyze", "Kombiglyze XR",
        "metformin/linagliptin", "linagliptin/metformin", "Jentadueto", "Jentadueto XR",
        "metformin/alogliptin", "alogliptin/metformin", "Kazano",
        "metformin/vildagliptin", "vildagliptin/metformin", "Eucreas",
        # SGLT2 inhibitors
        "metformin/empagliflozin", "empagliflozin/metformin", "Synjardy", "Synjardy XR",
        "metformin/dapagliflozin", "dapagliflozin/metformin", "Xigduo", "Xigduo XR",
        "metformin/canagliflozin", "canagliflozin/metformin", "Invokamet", "Invokamet XR",
        "metformin/ertugliflozin", "ertugliflozin/metformin", "Segluromet",
        # Sulfonylureas
        "metformin/glipizide", "glipizide/metformin", "Metaglip",
        "metformin/glyburide", "glyburide/metformin", "Glucovance",
        "metformin/glimepiride", "glimepiride/metformin", "Amaryl M",
        # Thiazolidinediones
        "metformin/pioglitazone", "pioglitazone/metformin", "Actoplus Met", "Actoplus Met XR",
        "metformin/rosiglitazone", "rosiglitazone/metformin", "Avandamet",
        # Triple combinations
        "metformin/saxagliptin/dapagliflozin", "Qternmet XR",
        "metformin/linagliptin/empagliflozin", "Trijardy XR",
    ],
    research_codes=[
        "BMS-512148",  # Dapagliflozin combo studies
        "MK-0431A",  # Janumet
    ],
    mechanism_terms=[
        "biguanide", "biguanides",
        "oral antidiabetic", "oral hypoglycemic",
        "antihyperglycemic agent",
        "insulin sensitizer",
        "AMP-activated protein kinase", "AMPK activator",
    ],
    class_terms=[
        "first-line diabetes therapy",
        "background metformin",
        "metformin monotherapy",
        "add-on to metformin",
    ]
)


class EnhancedGenericRecallValidator:
    """
    Validates enhanced recall for generic drugs using comprehensive synonym expansion.
    """

    EXPANSIONS = {
        "insulin": INSULIN_EXPANSION,
        "metformin": METFORMIN_EXPANSION,
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "EnhancedGenericRecall/1.0"
        })

    def search_ctgov(self, term: str) -> Set[str]:
        """Search CT.gov and return NCT IDs."""
        nct_ids = set()

        try:
            # Intervention search
            params = {
                "query.intr": term,
                "fields": "NCTId",
                "pageSize": 1000
            }

            response = self.session.get(CTGOV_API, params=params, timeout=DEFAULT_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                for study in data.get("studies", []):
                    nct_id = (study.get("protocolSection", {})
                             .get("identificationModule", {})
                             .get("nctId"))
                    if nct_id:
                        nct_ids.add(nct_id)

            time.sleep(0.3)

            # AREA searches
            for field in ["InterventionName", "BriefTitle", "OfficialTitle"]:
                try:
                    area_params = {
                        "query.term": f"AREA[{field}]{term}",
                        "fields": "NCTId",
                        "pageSize": 1000
                    }
                    response = self.session.get(CTGOV_API, params=area_params, timeout=DEFAULT_TIMEOUT)
                    if response.status_code == 200:
                        data = response.json()
                        for study in data.get("studies", []):
                            nct_id = (study.get("protocolSection", {})
                                     .get("identificationModule", {})
                                     .get("nctId"))
                            if nct_id:
                                nct_ids.add(nct_id)
                    time.sleep(0.2)
                except:
                    pass

        except Exception as e:
            print(f"    Error searching for '{term}': {e}")

        return nct_ids

    def validate_drug(self, drug: str, gold_standard: Set[str] = None) -> Dict[str, Any]:
        """
        Validate enhanced recall for a drug.

        Args:
            drug: Drug name (must be in EXPANSIONS)
            gold_standard: Optional gold standard NCT IDs

        Returns:
            Validation results with baseline and enhanced recall
        """
        if drug.lower() not in self.EXPANSIONS:
            return {"error": f"No expansion defined for {drug}"}

        expansion = self.EXPANSIONS[drug.lower()]
        all_terms = expansion.get_all_terms()

        print(f"\n  Validating {drug.upper()}")
        print(f"    Total search terms: {len(all_terms)}")

        # Baseline search (generic name only)
        print(f"    Baseline search...")
        baseline_ncts = self.search_ctgov(drug)
        print(f"      Found: {len(baseline_ncts)} trials")

        # Enhanced search (all terms)
        print(f"    Enhanced search ({len(all_terms)} terms)...")
        enhanced_ncts = set()
        term_contributions = {}

        for i, term in enumerate(all_terms):
            if i % 20 == 0 and i > 0:
                print(f"      Progress: {i}/{len(all_terms)} terms...")

            found = self.search_ctgov(term)
            new_found = found - enhanced_ncts
            enhanced_ncts |= found

            if new_found:
                term_contributions[term] = len(new_found)

            time.sleep(0.1)

        print(f"      Found: {len(enhanced_ncts)} trials")

        # Calculate metrics
        result = {
            "drug": drug,
            "timestamp": datetime.now().isoformat(),
            "total_terms": len(all_terms),
            "baseline": {
                "trials_found": len(baseline_ncts),
                "search_terms": [drug]
            },
            "enhanced": {
                "trials_found": len(enhanced_ncts),
                "search_terms": len(all_terms)
            },
            "improvement": {
                "absolute": len(enhanced_ncts) - len(baseline_ncts),
                "relative_percent": ((len(enhanced_ncts) - len(baseline_ncts)) / len(baseline_ncts) * 100)
                                    if baseline_ncts else 0
            },
            "top_contributing_terms": sorted(
                term_contributions.items(),
                key=lambda x: -x[1]
            )[:20],
            "term_categories": {
                "generic_names": len(expansion.generic_names),
                "brand_names": len(expansion.brand_names),
                "formulations": len(expansion.formulations),
                "combinations": len(expansion.combinations),
                "delivery_devices": len(expansion.delivery_devices),
                "mechanism_terms": len(expansion.mechanism_terms),
            }
        }

        # If gold standard provided, calculate recall
        if gold_standard:
            baseline_tp = len(baseline_ncts & gold_standard)
            enhanced_tp = len(enhanced_ncts & gold_standard)

            result["gold_standard_size"] = len(gold_standard)
            result["baseline"]["recall"] = baseline_tp / len(gold_standard) if gold_standard else 0
            result["enhanced"]["recall"] = enhanced_tp / len(gold_standard) if gold_standard else 0
            result["improvement"]["recall_gain"] = result["enhanced"]["recall"] - result["baseline"]["recall"]

        return result

    def run_full_validation(self) -> Dict[str, Any]:
        """Run validation for all expanded drugs."""
        print("=" * 70)
        print("ENHANCED GENERIC DRUG RECALL VALIDATION")
        print("Testing comprehensive synonym expansion")
        print("=" * 70)

        results = []

        for drug in self.EXPANSIONS:
            result = self.validate_drug(drug)
            results.append(result)

        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)

        for result in results:
            baseline = result["baseline"]["trials_found"]
            enhanced = result["enhanced"]["trials_found"]
            improvement = result["improvement"]["absolute"]

            print(f"\n  {result['drug'].upper()}:")
            print(f"    Baseline: {baseline} trials")
            print(f"    Enhanced: {enhanced} trials")
            print(f"    Improvement: +{improvement} trials (+{result['improvement']['relative_percent']:.1f}%)")

            if result.get("top_contributing_terms"):
                print(f"    Top contributing terms:")
                for term, count in result["top_contributing_terms"][:5]:
                    print(f"      - {term}: +{count} trials")

        return {
            "validation_type": "enhanced_generic_recall",
            "timestamp": datetime.now().isoformat(),
            "drugs_validated": list(self.EXPANSIONS.keys()),
            "results": results
        }


def generate_comprehensive_synonym_file():
    """Generate comprehensive synonym JSON file."""
    output = {
        "_metadata": {
            "description": "Comprehensive drug synonym expansion for maximum recall",
            "version": "2.0",
            "created": datetime.now().isoformat(),
            "drugs_included": ["insulin", "metformin"],
            "sources": ["DrugBank", "RxNorm", "WHO ATC", "FDA Orange Book", "ChEMBL"]
        },
        "insulin": {
            "generic_names": INSULIN_EXPANSION.generic_names,
            "brand_names": INSULIN_EXPANSION.brand_names,
            "international_names": INSULIN_EXPANSION.international_names,
            "formulations": INSULIN_EXPANSION.formulations,
            "delivery_devices": INSULIN_EXPANSION.delivery_devices,
            "combinations": INSULIN_EXPANSION.combinations,
            "research_codes": INSULIN_EXPANSION.research_codes,
            "mechanism_terms": INSULIN_EXPANSION.mechanism_terms,
            "total_terms": len(INSULIN_EXPANSION.get_all_terms())
        },
        "metformin": {
            "generic_names": METFORMIN_EXPANSION.generic_names,
            "brand_names": METFORMIN_EXPANSION.brand_names,
            "international_names": METFORMIN_EXPANSION.international_names,
            "formulations": METFORMIN_EXPANSION.formulations,
            "combinations": METFORMIN_EXPANSION.combinations,
            "research_codes": METFORMIN_EXPANSION.research_codes,
            "mechanism_terms": METFORMIN_EXPANSION.mechanism_terms,
            "total_terms": len(METFORMIN_EXPANSION.get_all_terms())
        }
    }

    output_dir = Path(__file__).parent.parent / "data"
    output_file = output_dir / "comprehensive_drug_synonyms.json"

    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"Synonym file saved to: {output_file}")
    return output_file


def main():
    """Run enhanced generic recall validation."""
    # Generate synonym file
    generate_comprehensive_synonym_file()

    # Run validation
    validator = EnhancedGenericRecallValidator()
    results = validator.run_full_validation()

    # Save results
    output_dir = Path(__file__).parent.parent / "output"
    output_file = output_dir / "enhanced_generic_recall_results.json"

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
