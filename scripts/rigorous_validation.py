#!/usr/bin/env python3
"""
Rigorous Validation of CT.gov Search Strategies
Tests strategies using PICO input only (no CT.gov metadata)

This is the world-class validation that avoids circularity.

Author: Mahmood Ahmad
Version: 1.0
"""

import json
import math
import time
import re
import csv
from datetime import datetime, timezone
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
from pathlib import Path
import requests

from drug_expander import DrugNameExpander, ConditionExpander


def wilson_ci(successes: int, n: int) -> Tuple[float, float]:
    """Wilson score 95% CI"""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    z = 1.96
    denom = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denom
    margin = z * math.sqrt((p * (1-p) + z**2 / (4*n)) / n) / denom
    return (max(0, center - margin), min(1, center + margin))


@dataclass
class PICO:
    """Patient/Population, Intervention, Comparator, Outcome"""
    population: str  # e.g., "Adults with type 2 diabetes"
    intervention: str  # e.g., "Metformin"
    comparator: str = ""  # e.g., "Placebo"
    outcome: str = ""  # e.g., "HbA1c"

    def extract_condition(self) -> str:
        """Extract the condition from population"""
        # Simple extraction - take main condition phrase
        pop = self.population.lower()

        # Common patterns
        patterns = [
            r"with (.+?)(?:\s+who|\s+and|\s*$)",
            r"patients? with (.+?)(?:\s+who|\s+and|\s*$)",
            r"adults? with (.+?)(?:\s+who|\s+and|\s*$)",
            r"children with (.+?)(?:\s+who|\s+and|\s*$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, pop)
            if match:
                return match.group(1).strip()

        return self.population


@dataclass
class GoldStandardReview:
    """A systematic review with known included trials"""
    review_id: str
    title: str
    pico: PICO
    included_nct_ids: Set[str]
    source: str = "cochrane"  # cochrane, meta-analysis, manual
    search_date: str = ""


@dataclass
class StrategyResult:
    """Results for one strategy on one review"""
    strategy: str
    review_id: str
    gold_standard_size: int
    found: int
    true_positives: int
    false_positives: int
    false_negatives: int
    recall: float
    precision: float
    f1: float
    ci_lower: float
    ci_upper: float


class RigorousValidator:
    """
    Validates CT.gov search strategies using PICO input only.
    No CT.gov metadata is used - simulates real systematic review search.
    """

    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "RigorousValidator/1.0"})
        self.drug_expander = DrugNameExpander()
        self.condition_expander = ConditionExpander()
        self.search_cache = {}

    def search_ctgov(self, params: Dict) -> Set[str]:
        """Run a CT.gov search and return NCT IDs"""
        cache_key = json.dumps(params, sort_keys=True)
        if cache_key in self.search_cache:
            return self.search_cache[cache_key]

        nct_ids = set()

        try:
            search_params = {"fields": "NCTId", "pageSize": 1000}
            search_params.update(params)

            response = self.session.get(self.BASE_URL, params=search_params, timeout=60)
            response.raise_for_status()
            data = response.json()

            for study in data.get("studies", []):
                nct_id = study.get("protocolSection", {}).get(
                    "identificationModule", {}
                ).get("nctId")
                if nct_id:
                    nct_ids.add(nct_id)

            self.search_cache[cache_key] = nct_ids
            time.sleep(0.3)

        except Exception as e:
            print(f"    Search error: {e}")

        return nct_ids

    # =========================================================================
    # SEARCH STRATEGIES (using PICO input only)
    # =========================================================================

    def strategy_r1_intervention_only(self, pico: PICO) -> Set[str]:
        """R1: Search by intervention name variants only"""
        nct_ids = set()

        # Expand intervention to all variants
        intervention_variants = self.drug_expander.expand(pico.intervention, use_api=False)

        for variant in intervention_variants:
            if len(variant) < 3:
                continue
            results = self.search_ctgov({"query.intr": variant})
            nct_ids.update(results)

        return nct_ids

    def strategy_r2_condition_only(self, pico: PICO) -> Set[str]:
        """R2: Search by condition variants only"""
        nct_ids = set()

        # Extract and expand condition
        condition = pico.extract_condition()
        condition_variants = self.condition_expander.expand(condition)

        for variant in condition_variants:
            if len(variant) < 3:
                continue
            results = self.search_ctgov({"query.cond": variant})
            nct_ids.update(results)

        return nct_ids

    def strategy_r3_intervention_condition(self, pico: PICO) -> Set[str]:
        """R3: Intervention + Condition combined"""
        nct_ids = set()

        intervention_variants = self.drug_expander.expand(pico.intervention, use_api=False)
        condition = pico.extract_condition()
        condition_variants = self.condition_expander.expand(condition)

        # Try combinations
        for drug in list(intervention_variants)[:5]:  # Limit to top 5
            if len(drug) < 3:
                continue

            # Drug alone
            results = self.search_ctgov({"query.intr": drug})
            nct_ids.update(results)

            # Drug + condition
            for cond in list(condition_variants)[:3]:  # Limit to top 3
                if len(cond) < 3:
                    continue
                results = self.search_ctgov({
                    "query.intr": drug,
                    "query.cond": cond
                })
                nct_ids.update(results)

        return nct_ids

    def strategy_r4_comprehensive(self, pico: PICO) -> Set[str]:
        """R4: Comprehensive search - union of all approaches"""
        nct_ids = set()

        # R1: Intervention
        nct_ids.update(self.strategy_r1_intervention_only(pico))

        # R2: Condition
        nct_ids.update(self.strategy_r2_condition_only(pico))

        # Also search general term field
        intervention_variants = self.drug_expander.expand(pico.intervention, use_api=False)
        for drug in list(intervention_variants)[:3]:
            results = self.search_ctgov({"query.term": drug})
            nct_ids.update(results)

        return nct_ids

    def strategy_r5_rct_filtered(self, pico: PICO) -> Set[str]:
        """R5: Intervention search with RCT filter"""
        nct_ids = set()

        intervention_variants = self.drug_expander.expand(pico.intervention, use_api=False)

        for drug in list(intervention_variants)[:5]:
            if len(drug) < 3:
                continue
            results = self.search_ctgov({
                "query.intr": drug,
                "query.term": "AREA[DesignAllocation]RANDOMIZED"
            })
            nct_ids.update(results)

        return nct_ids

    # =========================================================================
    # VALIDATION ENGINE
    # =========================================================================

    def validate_strategy(
        self,
        strategy_name: str,
        strategy_func,
        reviews: List[GoldStandardReview]
    ) -> List[StrategyResult]:
        """Validate a single strategy across all reviews"""
        results = []

        for i, review in enumerate(reviews):
            print(f"\r    [{i+1}/{len(reviews)}] {review.review_id}...", end="", flush=True)

            # Run strategy using only PICO (no CT.gov metadata)
            found = strategy_func(review.pico)

            # Compare to gold standard
            gold_standard = review.included_nct_ids

            tp = len(found & gold_standard)
            fp = len(found - gold_standard)
            fn = len(gold_standard - found)

            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

            ci_low, ci_high = wilson_ci(tp, tp + fn)

            results.append(StrategyResult(
                strategy=strategy_name,
                review_id=review.review_id,
                gold_standard_size=len(gold_standard),
                found=len(found),
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                recall=recall,
                precision=precision,
                f1=f1,
                ci_lower=ci_low,
                ci_upper=ci_high
            ))

        print()
        return results

    def run_validation(
        self,
        reviews: List[GoldStandardReview],
        output_dir: str
    ) -> Dict:
        """Run full validation across all strategies"""

        print("=" * 70)
        print("RIGOROUS VALIDATION - CT.gov Search Strategies")
        print("Using PICO input only (no CT.gov metadata)")
        print("=" * 70)
        print(f"\nGold standard: {len(reviews)} reviews")

        strategies = [
            ("R1-IntervOnly", self.strategy_r1_intervention_only),
            ("R2-CondOnly", self.strategy_r2_condition_only),
            ("R3-IntervCond", self.strategy_r3_intervention_condition),
            ("R4-Comprehensive", self.strategy_r4_comprehensive),
            ("R5-RCTFiltered", self.strategy_r5_rct_filtered),
        ]

        all_results = {}

        for strategy_name, strategy_func in strategies:
            print(f"\n{'='*60}")
            print(f"Testing: {strategy_name}")
            print('='*60)

            results = self.validate_strategy(strategy_name, strategy_func, reviews)
            all_results[strategy_name] = results

            # Calculate aggregate metrics
            total_tp = sum(r.true_positives for r in results)
            total_fn = sum(r.false_negatives for r in results)
            total_fp = sum(r.false_positives for r in results)

            agg_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
            agg_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
            ci_low, ci_high = wilson_ci(total_tp, total_tp + total_fn)

            print(f"\n  Aggregate Recall: {agg_recall:.1%} (95% CI: {ci_low:.1%} - {ci_high:.1%})")
            print(f"  Aggregate Precision: {agg_precision:.1%}")
            print(f"  Total TP: {total_tp}, FN: {total_fn}, FP: {total_fp}")

        # Generate reports
        self._generate_report(all_results, reviews, output_dir)

        return all_results

    def _generate_report(
        self,
        all_results: Dict,
        reviews: List[GoldStandardReview],
        output_dir: str
    ):
        """Generate validation report"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Calculate summary statistics
        summary = []
        for strategy_name, results in all_results.items():
            total_tp = sum(r.true_positives for r in results)
            total_fn = sum(r.false_negatives for r in results)
            total_fp = sum(r.false_positives for r in results)

            agg_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
            agg_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
            ci_low, ci_high = wilson_ci(total_tp, total_tp + total_fn)

            summary.append({
                "strategy": strategy_name,
                "recall": agg_recall,
                "precision": agg_precision,
                "ci_lower": ci_low,
                "ci_upper": ci_high,
                "total_tp": total_tp,
                "total_fn": total_fn,
                "total_fp": total_fp
            })

        # Markdown report
        lines = [
            "# Rigorous Validation Results",
            "",
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            f"**Gold Standard:** {len(reviews)} systematic reviews",
            f"**Method:** PICO-only search (no CT.gov metadata)",
            "",
            "## Summary Results",
            "",
            "| Strategy | Recall | 95% CI | Precision | TP | FN | FP |",
            "|----------|--------|--------|-----------|----|----|----| "
        ]

        for s in sorted(summary, key=lambda x: x['recall'], reverse=True):
            lines.append(
                f"| {s['strategy']} | {s['recall']:.1%} | "
                f"{s['ci_lower']:.1%}-{s['ci_upper']:.1%} | "
                f"{s['precision']:.1%} | {s['total_tp']} | {s['total_fn']} | {s['total_fp']} |"
            )

        best = max(summary, key=lambda x: x['recall'])
        target_met = best['recall'] >= 0.95

        lines.extend([
            "",
            "## Key Findings",
            "",
            f"**Best Strategy:** {best['strategy']}",
            f"**Best Recall:** {best['recall']:.1%} (95% CI: {best['ci_lower']:.1%} - {best['ci_upper']:.1%})",
            f"**Target (95%) Met:** {'YES' if target_met else 'NO'}",
            "",
            "## Methodology",
            "",
            "This validation uses **PICO input only** - no CT.gov metadata.",
            "Drug and condition names are expanded using external dictionaries.",
            "This simulates a real systematic review search scenario.",
            "",
            "## Interpretation",
            "",
            "- **R1-IntervOnly:** Search intervention variants in CT.gov intervention field",
            "- **R2-CondOnly:** Search condition variants in CT.gov condition field",
            "- **R3-IntervCond:** Combined intervention + condition search",
            "- **R4-Comprehensive:** Union of all search approaches",
            "- **R5-RCTFiltered:** Intervention search with RCT allocation filter",
            "",
            "---",
            "*Rigorous Validation Protocol v1.0*"
        ])

        report_path = output_path / "rigorous_validation_report.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"\nReport saved to {report_path}")

        # JSON export
        json_path = output_path / "rigorous_validation_results.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0",
                "methodology": "PICO-only search (no CT.gov metadata)",
                "gold_standard_size": len(reviews),
                "target_recall": 0.95,
                "target_met": target_met,
                "summary": summary,
                "detailed_results": {
                    strategy: [
                        {
                            "review_id": r.review_id,
                            "gold_standard_size": r.gold_standard_size,
                            "found": r.found,
                            "tp": r.true_positives,
                            "fp": r.false_positives,
                            "fn": r.false_negatives,
                            "recall": r.recall,
                            "precision": r.precision
                        }
                        for r in results
                    ]
                    for strategy, results in all_results.items()
                }
            }, f, indent=2)
        print(f"JSON saved to {json_path}")


# =============================================================================
# GOLD STANDARD BUILDERS
# =============================================================================

def build_sample_gold_standard() -> List[GoldStandardReview]:
    """
    Build a sample gold standard for testing.
    In production, this would load from Cochrane reviews.
    """

    # Sample reviews with known PICO and included trials
    # These are illustrative - real validation needs actual Cochrane data
    reviews = [
        GoldStandardReview(
            review_id="SAMPLE-001",
            title="Metformin for type 2 diabetes",
            pico=PICO(
                population="Adults with type 2 diabetes",
                intervention="Metformin",
                comparator="Placebo or sulfonylurea",
                outcome="HbA1c, mortality"
            ),
            included_nct_ids={
                "NCT00000620", "NCT01243424", "NCT00766857",
                "NCT00799643", "NCT02201004"
            },
            source="sample"
        ),
        GoldStandardReview(
            review_id="SAMPLE-002",
            title="SGLT2 inhibitors for heart failure",
            pico=PICO(
                population="Adults with heart failure",
                intervention="Empagliflozin",
                comparator="Placebo",
                outcome="Hospitalization, mortality"
            ),
            included_nct_ids={
                "NCT03057977", "NCT03057951", "NCT01131676",
                "NCT02653482"
            },
            source="sample"
        ),
        GoldStandardReview(
            review_id="SAMPLE-003",
            title="Pembrolizumab for lung cancer",
            pico=PICO(
                population="Adults with non-small cell lung cancer",
                intervention="Pembrolizumab",
                comparator="Chemotherapy",
                outcome="Overall survival, progression-free survival"
            ),
            included_nct_ids={
                "NCT02142738", "NCT02220894", "NCT02578680",
                "NCT02775435", "NCT03134872"
            },
            source="sample"
        ),
        GoldStandardReview(
            review_id="SAMPLE-004",
            title="SSRIs for depression",
            pico=PICO(
                population="Adults with major depressive disorder",
                intervention="Sertraline",
                comparator="Placebo",
                outcome="Depression scores, remission"
            ),
            included_nct_ids={
                "NCT00668525", "NCT00693849", "NCT01473381"
            },
            source="sample"
        ),
        GoldStandardReview(
            review_id="SAMPLE-005",
            title="TNF inhibitors for rheumatoid arthritis",
            pico=PICO(
                population="Adults with rheumatoid arthritis",
                intervention="Adalimumab",
                comparator="Methotrexate or placebo",
                outcome="ACR response, disease activity"
            ),
            included_nct_ids={
                "NCT00195702", "NCT00448383", "NCT00870467",
                "NCT01185288"
            },
            source="sample"
        ),
    ]

    return reviews


def load_gold_standard_from_file(path: str) -> List[GoldStandardReview]:
    """Load gold standard from JSON file"""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    reviews = []
    for item in data.get("reviews", []):
        reviews.append(GoldStandardReview(
            review_id=item.get("review_id", ""),
            title=item.get("title", ""),
            pico=PICO(
                population=item.get("pico", {}).get("population", ""),
                intervention=item.get("pico", {}).get("intervention", ""),
                comparator=item.get("pico", {}).get("comparator", ""),
                outcome=item.get("pico", {}).get("outcome", "")
            ),
            included_nct_ids=set(item.get("included_nct_ids", [])),
            source=item.get("source", "file")
        ))

    return reviews


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Rigorous CT.gov Search Validation")
    parser.add_argument("-g", "--gold-standard", help="Path to gold standard JSON")
    parser.add_argument("-o", "--output", default="output", help="Output directory")
    parser.add_argument("--sample", action="store_true", help="Use sample gold standard")

    args = parser.parse_args()

    # Load gold standard
    if args.sample or not args.gold_standard:
        print("Using sample gold standard (for demonstration)")
        reviews = build_sample_gold_standard()
    else:
        reviews = load_gold_standard_from_file(args.gold_standard)

    # Run validation
    validator = RigorousValidator()
    validator.run_validation(reviews, args.output)


if __name__ == "__main__":
    main()
