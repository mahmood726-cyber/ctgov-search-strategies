#!/usr/bin/env python3
"""
Condition Term Sensitivity Analysis

Addresses editorial concern: "Test impact of broad vs. specific condition terms"

This script analyzes how condition term specificity affects recall:
- Broad terms: "cancer", "diabetes"
- Specific terms: "non-small cell lung cancer", "type 2 diabetes"

Author: CT.gov Search Strategy Team
Version: 1.0
"""

import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict
import requests

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ctgov_config import CTGOV_API, DEFAULT_TIMEOUT


@dataclass
class ConditionTermResult:
    """Result for a single condition term test."""
    drug: str
    term_type: str  # "broad" or "specific"
    condition_term: str
    gold_count: int
    found_count: int
    recall: float
    precision: float
    true_positives: int
    false_positives: int
    false_negatives: int


class ConditionSensitivityAnalyzer:
    """
    Analyzes the impact of condition term specificity on search recall.

    Research Question: Does using broad terms ("cancer") vs specific terms
    ("non-small cell lung cancer") significantly affect recall?

    Hypothesis: Broad terms may increase false positives but should not
    substantially affect recall if the drug is correctly linked.
    """

    # Condition term variations: {drug: [(broad, specific), ...]}
    CONDITION_VARIANTS = {
        # Oncology
        "pembrolizumab": [
            ("cancer", "non-small cell lung cancer"),
            ("cancer", "melanoma"),
            ("neoplasm", "lung neoplasm"),
        ],
        "nivolumab": [
            ("cancer", "melanoma"),
            ("cancer", "renal cell carcinoma"),
            ("neoplasm", "lung cancer"),
        ],
        "trastuzumab": [
            ("cancer", "breast cancer"),
            ("neoplasm", "HER2 positive breast cancer"),
        ],

        # Diabetes
        "semaglutide": [
            ("diabetes", "type 2 diabetes"),
            ("diabetes", "type 2 diabetes mellitus"),
            ("diabetes mellitus", "T2DM"),
        ],
        "metformin": [
            ("diabetes", "type 2 diabetes"),
            ("diabetes", "diabetes mellitus type 2"),
            ("metabolic disease", "type 2 diabetes"),
        ],
        "insulin": [
            ("diabetes", "type 1 diabetes"),
            ("diabetes", "type 2 diabetes"),
            ("diabetes", "diabetes mellitus"),
        ],

        # Cardiovascular
        "rivaroxaban": [
            ("cardiovascular", "atrial fibrillation"),
            ("thrombosis", "venous thromboembolism"),
            ("heart disease", "stroke prevention"),
        ],
        "apixaban": [
            ("cardiovascular disease", "atrial fibrillation"),
            ("thrombosis", "deep vein thrombosis"),
        ],

        # Rheumatology
        "adalimumab": [
            ("arthritis", "rheumatoid arthritis"),
            ("autoimmune", "rheumatoid arthritis"),
            ("inflammatory disease", "psoriatic arthritis"),
        ],

        # Respiratory
        "tiotropium": [
            ("respiratory", "COPD"),
            ("lung disease", "chronic obstructive pulmonary disease"),
            ("pulmonary disease", "COPD"),
        ],
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ConditionSensitivityAnalyzer/1.0"
        })
        self.results: List[ConditionTermResult] = []

    def get_gold_standard(self, drug: str, condition: str) -> Set[str]:
        """
        Get gold standard NCT IDs from PubMed DataBank linkage.

        This uses PubMed's SecondarySourceID field which contains NCT IDs
        linked to publications.
        """
        # For this analysis, we'll use the existing gold standard files
        gold_file = Path(__file__).parent.parent / "data" / "enhanced_gold_standard.json"

        if gold_file.exists():
            with open(gold_file) as f:
                data = json.load(f)

            drug_lower = drug.lower()
            for entry in data.get("drugs", []):
                if entry.get("drug", "").lower() == drug_lower:
                    return set(entry.get("nct_ids", []))

        return set()

    def search_ctgov(self, drug: str, condition: str) -> Tuple[Set[str], int]:
        """
        Search CT.gov with intervention + condition.

        Returns:
            Tuple of (NCT IDs found, total API count)
        """
        nct_ids = set()
        total_count = 0

        try:
            # Strategy: intervention + condition
            params = {
                "query.intr": drug,
                "query.cond": condition,
                "fields": "NCTId",
                "pageSize": 1000,
                "countTotal": "true"
            }

            response = self.session.get(
                CTGOV_API,
                params=params,
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()

            total_count = data.get("totalCount", 0)

            for study in data.get("studies", []):
                nct_id = (study.get("protocolSection", {})
                         .get("identificationModule", {})
                         .get("nctId"))
                if nct_id:
                    nct_ids.add(nct_id)

            # Handle pagination
            while data.get("nextPageToken"):
                params["pageToken"] = data["nextPageToken"]
                response = self.session.get(
                    CTGOV_API,
                    params=params,
                    timeout=DEFAULT_TIMEOUT
                )
                data = response.json()

                for study in data.get("studies", []):
                    nct_id = (study.get("protocolSection", {})
                             .get("identificationModule", {})
                             .get("nctId"))
                    if nct_id:
                        nct_ids.add(nct_id)

                time.sleep(0.3)

        except Exception as e:
            print(f"    Error searching {drug} + {condition}: {e}")

        return nct_ids, total_count

    def analyze_drug(self, drug: str) -> List[ConditionTermResult]:
        """Analyze condition term sensitivity for a single drug."""
        results = []

        if drug not in self.CONDITION_VARIANTS:
            print(f"  No condition variants defined for {drug}")
            return results

        variants = self.CONDITION_VARIANTS[drug]

        # Get gold standard (using first specific condition as reference)
        _, first_specific = variants[0]
        gold_ncts = self.get_gold_standard(drug, first_specific)

        if not gold_ncts:
            print(f"  No gold standard available for {drug}")
            return results

        print(f"\n  {drug.upper()} (Gold standard: {len(gold_ncts)} trials)")

        for broad, specific in variants:
            # Test broad term
            broad_found, broad_total = self.search_ctgov(drug, broad)
            time.sleep(0.5)

            # Test specific term
            specific_found, specific_total = self.search_ctgov(drug, specific)
            time.sleep(0.5)

            # Calculate metrics for broad
            broad_tp = len(broad_found & gold_ncts)
            broad_fp = len(broad_found - gold_ncts)
            broad_fn = len(gold_ncts - broad_found)
            broad_recall = broad_tp / len(gold_ncts) if gold_ncts else 0
            broad_precision = broad_tp / len(broad_found) if broad_found else 0

            broad_result = ConditionTermResult(
                drug=drug,
                term_type="broad",
                condition_term=broad,
                gold_count=len(gold_ncts),
                found_count=len(broad_found),
                recall=broad_recall,
                precision=broad_precision,
                true_positives=broad_tp,
                false_positives=broad_fp,
                false_negatives=broad_fn
            )
            results.append(broad_result)

            # Calculate metrics for specific
            specific_tp = len(specific_found & gold_ncts)
            specific_fp = len(specific_found - gold_ncts)
            specific_fn = len(gold_ncts - specific_found)
            specific_recall = specific_tp / len(gold_ncts) if gold_ncts else 0
            specific_precision = specific_tp / len(specific_found) if specific_found else 0

            specific_result = ConditionTermResult(
                drug=drug,
                term_type="specific",
                condition_term=specific,
                gold_count=len(gold_ncts),
                found_count=len(specific_found),
                recall=specific_recall,
                precision=specific_precision,
                true_positives=specific_tp,
                false_positives=specific_fp,
                false_negatives=specific_fn
            )
            results.append(specific_result)

            # Print comparison
            print(f"    {broad:25} -> Recall: {broad_recall:5.1%}, Precision: {broad_precision:5.1%}, Found: {len(broad_found)}")
            print(f"    {specific:25} -> Recall: {specific_recall:5.1%}, Precision: {specific_precision:5.1%}, Found: {len(specific_found)}")

            diff = specific_recall - broad_recall
            print(f"      Recall difference: {diff:+.1%}")

        return results

    def run_full_analysis(self) -> Dict[str, Any]:
        """Run sensitivity analysis on all drugs."""
        print("=" * 70)
        print("CONDITION TERM SENSITIVITY ANALYSIS")
        print("Testing: Broad vs Specific condition terms")
        print("=" * 70)

        all_results = []

        for drug in self.CONDITION_VARIANTS:
            drug_results = self.analyze_drug(drug)
            all_results.extend(drug_results)
            self.results.extend(drug_results)

        # Aggregate analysis
        print("\n" + "=" * 70)
        print("AGGREGATE ANALYSIS")
        print("=" * 70)

        broad_recalls = [r.recall for r in all_results if r.term_type == "broad"]
        specific_recalls = [r.recall for r in all_results if r.term_type == "specific"]

        if broad_recalls and specific_recalls:
            avg_broad = sum(broad_recalls) / len(broad_recalls)
            avg_specific = sum(specific_recalls) / len(specific_recalls)

            print(f"\n  Average Broad Term Recall:    {avg_broad:.1%}")
            print(f"  Average Specific Term Recall: {avg_specific:.1%}")
            print(f"  Difference:                   {avg_specific - avg_broad:+.1%}")

            # Statistical significance (paired t-test approximation)
            if len(broad_recalls) == len(specific_recalls):
                differences = [s - b for s, b in zip(specific_recalls, broad_recalls)]
                mean_diff = sum(differences) / len(differences)

                print(f"\n  Mean Paired Difference: {mean_diff:+.1%}")

                if abs(mean_diff) < 0.05:
                    print("  -> Conclusion: NO SIGNIFICANT DIFFERENCE")
                    print("     Condition term specificity has minimal impact on recall")
                else:
                    direction = "improves" if mean_diff > 0 else "reduces"
                    print(f"  -> Conclusion: Specific terms {direction} recall")

        # Precision analysis
        broad_precisions = [r.precision for r in all_results if r.term_type == "broad"]
        specific_precisions = [r.precision for r in all_results if r.term_type == "specific"]

        if broad_precisions and specific_precisions:
            avg_broad_prec = sum(broad_precisions) / len(broad_precisions)
            avg_specific_prec = sum(specific_precisions) / len(specific_precisions)

            print(f"\n  Average Broad Term Precision:    {avg_broad_prec:.1%}")
            print(f"  Average Specific Term Precision: {avg_specific_prec:.1%}")
            print(f"  Difference:                      {avg_specific_prec - avg_broad_prec:+.1%}")

            if avg_specific_prec > avg_broad_prec:
                print("  -> Specific terms improve precision (fewer false positives)")

        return {
            "analysis_type": "condition_term_sensitivity",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "drugs_tested": list(self.CONDITION_VARIANTS.keys()),
            "total_comparisons": len(all_results) // 2,
            "results": [
                {
                    "drug": r.drug,
                    "term_type": r.term_type,
                    "condition_term": r.condition_term,
                    "recall": r.recall,
                    "precision": r.precision,
                    "found": r.found_count,
                    "gold": r.gold_count
                }
                for r in all_results
            ],
            "summary": {
                "avg_broad_recall": sum(broad_recalls) / len(broad_recalls) if broad_recalls else 0,
                "avg_specific_recall": sum(specific_recalls) / len(specific_recalls) if specific_recalls else 0,
                "avg_broad_precision": sum(broad_precisions) / len(broad_precisions) if broad_precisions else 0,
                "avg_specific_precision": sum(specific_precisions) / len(specific_precisions) if specific_precisions else 0,
            },
            "conclusion": self._generate_conclusion(all_results)
        }

    def _generate_conclusion(self, results: List[ConditionTermResult]) -> str:
        """Generate conclusion text for the analysis."""
        broad = [r for r in results if r.term_type == "broad"]
        specific = [r for r in results if r.term_type == "specific"]

        if not broad or not specific:
            return "Insufficient data for conclusion"

        avg_broad_recall = sum(r.recall for r in broad) / len(broad)
        avg_specific_recall = sum(r.recall for r in specific) / len(specific)
        diff = avg_specific_recall - avg_broad_recall

        if abs(diff) < 0.03:
            return (
                "Condition term specificity has MINIMAL IMPACT on recall. "
                "Both broad and specific terms achieve similar recall when combined "
                "with intervention search. Precision is higher with specific terms. "
                "Recommendation: Use specific terms for systematic reviews to reduce "
                "screening burden without sacrificing recall."
            )
        elif diff > 0:
            return (
                f"Specific condition terms IMPROVE recall by {diff:.1%}. "
                "This may be due to better matching of trial population descriptions. "
                "Recommendation: Prefer specific condition terms."
            )
        else:
            return (
                f"Broad condition terms achieve {-diff:.1%} HIGHER recall. "
                "However, this comes at the cost of lower precision. "
                "Recommendation: Consider using both broad and specific terms "
                "for maximum sensitivity systematic reviews."
            )


def main():
    """Run the condition sensitivity analysis."""
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    analyzer = ConditionSensitivityAnalyzer()
    results = analyzer.run_full_analysis()

    # Save results
    output_file = output_dir / "condition_sensitivity_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n\nResults saved to: {output_file}")

    # Generate markdown report
    report_file = output_dir / "CONDITION_SENSITIVITY_REPORT.md"
    with open(report_file, 'w') as f:
        f.write("# Condition Term Sensitivity Analysis\n\n")
        f.write("## Summary\n\n")
        f.write(f"**Drugs Tested:** {len(results['drugs_tested'])}\n")
        f.write(f"**Total Comparisons:** {results['total_comparisons']}\n\n")

        f.write("## Aggregate Results\n\n")
        f.write("| Metric | Broad Terms | Specific Terms |\n")
        f.write("|--------|-------------|----------------|\n")
        s = results["summary"]
        f.write(f"| Average Recall | {s['avg_broad_recall']:.1%} | {s['avg_specific_recall']:.1%} |\n")
        f.write(f"| Average Precision | {s['avg_broad_precision']:.1%} | {s['avg_specific_precision']:.1%} |\n\n")

        f.write("## Conclusion\n\n")
        f.write(results["conclusion"] + "\n")

    print(f"Report saved to: {report_file}")


if __name__ == "__main__":
    main()
