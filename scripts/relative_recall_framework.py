#!/usr/bin/env python3
"""
Relative Recall Framework
=========================

Formal implementation of relative recall methodology per RSM 2025 guidelines:
"A practical guide to evaluating sensitivity of literature search strings
for systematic reviews using relative recall"

Key concepts:
- Benchmark set construction
- Relative recall calculation
- Confidence interval estimation
- Search string optimization

Author: CT.gov Search Strategy Validation Project
Version: 1.0.0
Date: 2026-01-26
"""

import json
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime
from collections import defaultdict


@dataclass
class BenchmarkSet:
    """
    A collection of known-relevant studies used for validation.

    Per RSM guidelines, benchmark sets should be:
    - Representative of the topic
    - From diverse sources
    - Pre-defined before search validation
    """
    name: str
    description: str
    source: str  # e.g., "Cochrane reviews", "Prior systematic reviews", "Expert panel"

    # The benchmark records
    records: Set[str]  # Set of identifiers (NCT IDs, PMIDs, etc.)

    # Metadata
    creation_date: str
    therapeutic_area: str
    drug_or_intervention: str
    condition: str

    # Quality indicators
    is_prespecified: bool
    sources_searched: List[str]
    years_covered: str

    def __len__(self) -> int:
        return len(self.records)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'source': self.source,
            'record_count': len(self.records),
            'records': list(self.records),
            'creation_date': self.creation_date,
            'therapeutic_area': self.therapeutic_area,
            'drug_or_intervention': self.drug_or_intervention,
            'condition': self.condition,
            'is_prespecified': self.is_prespecified,
            'sources_searched': self.sources_searched,
            'years_covered': self.years_covered
        }


@dataclass
class SearchStringResult:
    """Results from executing a search string."""
    search_id: str
    search_string: str
    database: str

    # Results
    records_retrieved: Set[str]
    execution_date: str
    api_version: Optional[str]

    def __len__(self) -> int:
        return len(self.records_retrieved)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'search_id': self.search_id,
            'search_string': self.search_string,
            'database': self.database,
            'records_retrieved': len(self.records_retrieved),
            'execution_date': self.execution_date,
            'api_version': self.api_version
        }


@dataclass
class RelativeRecallResult:
    """
    Results of relative recall calculation.

    Relative Recall = Retrieved ∩ Benchmark / Benchmark
    """
    search_id: str
    benchmark_name: str

    # Core metrics
    relative_recall: float  # Sensitivity
    precision: float  # For information
    f1_score: float

    # Counts
    true_positives: int  # Retrieved and in benchmark
    false_negatives: int  # In benchmark but not retrieved
    retrieved_total: int  # Total retrieved
    benchmark_total: int  # Total in benchmark

    # Confidence interval (Wilson score)
    recall_ci_lower: float
    recall_ci_upper: float
    confidence_level: float

    # Missed records (for analysis)
    missed_records: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'search_id': self.search_id,
            'benchmark_name': self.benchmark_name,
            'relative_recall': round(self.relative_recall, 4),
            'precision': round(self.precision, 4),
            'f1_score': round(self.f1_score, 4),
            'counts': {
                'true_positives': self.true_positives,
                'false_negatives': self.false_negatives,
                'retrieved_total': self.retrieved_total,
                'benchmark_total': self.benchmark_total
            },
            'confidence_interval': {
                'lower': round(self.recall_ci_lower, 4),
                'upper': round(self.recall_ci_upper, 4),
                'level': self.confidence_level
            },
            'missed_records_count': len(self.missed_records)
        }


@dataclass
class SearchStringComparison:
    """Comparison of multiple search strings."""
    benchmark_name: str
    search_results: List[RelativeRecallResult]

    # Best performer
    best_search_id: str
    best_recall: float

    # Differences
    recall_differences: Dict[str, float]  # search_id -> difference from best

    def to_dict(self) -> Dict[str, Any]:
        return {
            'benchmark_name': self.benchmark_name,
            'search_results': [r.to_dict() for r in self.search_results],
            'best_search_id': self.best_search_id,
            'best_recall': round(self.best_recall, 4),
            'recall_differences': {k: round(v, 4) for k, v in self.recall_differences.items()}
        }


class RelativeRecallCalculator:
    """
    Calculator for relative recall per RSM guidelines.

    Implements:
    - Point estimate calculation
    - Wilson score confidence intervals
    - McNemar's test for paired comparison
    - Benchmark set management
    """

    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level
        self.z_score = self._get_z_score(confidence_level)
        self.benchmarks: Dict[str, BenchmarkSet] = {}
        self.search_results: Dict[str, SearchStringResult] = {}

    def _get_z_score(self, confidence: float) -> float:
        """Get z-score for confidence level."""
        z_scores = {
            0.90: 1.645,
            0.95: 1.96,
            0.99: 2.576
        }
        return z_scores.get(confidence, 1.96)

    def add_benchmark(self, benchmark: BenchmarkSet):
        """Add a benchmark set for validation."""
        self.benchmarks[benchmark.name] = benchmark

    def add_search_result(self, result: SearchStringResult):
        """Add a search result for evaluation."""
        self.search_results[result.search_id] = result

    def calculate_relative_recall(self, search_id: str,
                                  benchmark_name: str) -> RelativeRecallResult:
        """
        Calculate relative recall for a search against a benchmark.

        Relative Recall = |Retrieved ∩ Benchmark| / |Benchmark|
        """
        if search_id not in self.search_results:
            raise ValueError(f"Search result '{search_id}' not found")
        if benchmark_name not in self.benchmarks:
            raise ValueError(f"Benchmark '{benchmark_name}' not found")

        search = self.search_results[search_id]
        benchmark = self.benchmarks[benchmark_name]

        # Calculate overlap
        retrieved = search.records_retrieved
        expected = benchmark.records

        true_positives = retrieved & expected
        false_negatives = expected - retrieved

        tp = len(true_positives)
        fn = len(false_negatives)
        total_retrieved = len(retrieved)
        total_benchmark = len(expected)

        # Calculate metrics
        recall = tp / total_benchmark if total_benchmark > 0 else 0.0
        precision = tp / total_retrieved if total_retrieved > 0 else 0.0
        f1 = 2 * recall * precision / (recall + precision) if (recall + precision) > 0 else 0.0

        # Wilson score confidence interval
        ci_lower, ci_upper = self._wilson_ci(tp, total_benchmark)

        return RelativeRecallResult(
            search_id=search_id,
            benchmark_name=benchmark_name,
            relative_recall=recall,
            precision=precision,
            f1_score=f1,
            true_positives=tp,
            false_negatives=fn,
            retrieved_total=total_retrieved,
            benchmark_total=total_benchmark,
            recall_ci_lower=ci_lower,
            recall_ci_upper=ci_upper,
            confidence_level=self.confidence_level,
            missed_records=list(false_negatives)
        )

    def _wilson_ci(self, successes: int, total: int) -> Tuple[float, float]:
        """Calculate Wilson score confidence interval."""
        if total == 0:
            return (0.0, 1.0)

        z = self.z_score
        p = successes / total

        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator

        return (max(0.0, center - margin), min(1.0, center + margin))

    def compare_searches(self, search_ids: List[str],
                        benchmark_name: str) -> SearchStringComparison:
        """Compare multiple search strings against a benchmark."""
        results = []
        for search_id in search_ids:
            result = self.calculate_relative_recall(search_id, benchmark_name)
            results.append(result)

        # Find best performer
        best_result = max(results, key=lambda r: r.relative_recall)

        # Calculate differences from best
        differences = {
            r.search_id: best_result.relative_recall - r.relative_recall
            for r in results
        }

        return SearchStringComparison(
            benchmark_name=benchmark_name,
            search_results=results,
            best_search_id=best_result.search_id,
            best_recall=best_result.relative_recall,
            recall_differences=differences
        )

    def mcnemar_test(self, search1_id: str, search2_id: str,
                    benchmark_name: str) -> Dict[str, Any]:
        """
        Perform McNemar's test for paired comparison.

        Tests whether two search strategies have significantly different recall.
        """
        if benchmark_name not in self.benchmarks:
            raise ValueError(f"Benchmark '{benchmark_name}' not found")

        benchmark = self.benchmarks[benchmark_name]
        search1 = self.search_results[search1_id]
        search2 = self.search_results[search2_id]

        # Calculate contingency table
        found_by_1 = search1.records_retrieved & benchmark.records
        found_by_2 = search2.records_retrieved & benchmark.records

        # a: found by both
        # b: found by 1 only
        # c: found by 2 only
        # d: found by neither

        a = len(found_by_1 & found_by_2)
        b = len(found_by_1 - found_by_2)
        c = len(found_by_2 - found_by_1)
        d = len(benchmark.records - found_by_1 - found_by_2)

        # McNemar's test statistic (with continuity correction)
        if b + c == 0:
            chi_squared = 0.0
            p_value = 1.0
        else:
            chi_squared = (abs(b - c) - 1)**2 / (b + c)
            # Approximate p-value (chi-squared distribution, df=1)
            # Using simple approximation
            if chi_squared < 3.841:  # Critical value at 0.05
                p_value = 0.1  # Approximate
            elif chi_squared < 6.635:  # Critical value at 0.01
                p_value = 0.05
            else:
                p_value = 0.01

        return {
            'search1_id': search1_id,
            'search2_id': search2_id,
            'contingency_table': {
                'both': a,
                'search1_only': b,
                'search2_only': c,
                'neither': d
            },
            'chi_squared': round(chi_squared, 4),
            'p_value': p_value,
            'significant_difference': p_value < 0.05
        }

    def analyze_missed_records(self, result: RelativeRecallResult,
                              benchmark: BenchmarkSet) -> Dict[str, Any]:
        """Analyze why records were missed."""
        missed = result.missed_records

        analysis = {
            'total_missed': len(missed),
            'missed_records': missed[:20],  # First 20
            'recommendations': []
        }

        if len(missed) > 0:
            analysis['recommendations'].append(
                f"Investigate {len(missed)} missed records to identify "
                "systematic gaps in search strategy"
            )

        if result.relative_recall < 0.9:
            analysis['recommendations'].append(
                "Consider expanding synonym list or using broader terms"
            )

        if result.relative_recall < 0.8:
            analysis['recommendations'].append(
                "Review AREA syntax usage for improved field coverage"
            )

        return analysis


class BenchmarkSetBuilder:
    """
    Builder for constructing benchmark sets from various sources.

    Supports:
    - Cochrane review extraction
    - Prior systematic review compilation
    - Expert panel curation
    - Registry-publication linkage
    """

    def __init__(self):
        self.records: Set[str] = set()
        self.sources_used: List[str] = []

    def add_from_cochrane_review(self, review_doi: str, nct_ids: List[str]):
        """Add records from a Cochrane review."""
        self.records.update(nct_ids)
        self.sources_used.append(f"Cochrane: {review_doi}")

    def add_from_systematic_review(self, review_citation: str, nct_ids: List[str]):
        """Add records from a systematic review."""
        self.records.update(nct_ids)
        self.sources_used.append(f"Systematic Review: {review_citation}")

    def add_from_pubmed_databank(self, drug: str, condition: str,
                                 nct_ids: List[str]):
        """Add records from PubMed DataBank linkages."""
        self.records.update(nct_ids)
        self.sources_used.append(f"PubMed DataBank: {drug}/{condition}")

    def add_manual_records(self, nct_ids: List[str], source_description: str):
        """Add manually curated records."""
        self.records.update(nct_ids)
        self.sources_used.append(f"Manual: {source_description}")

    def build(self, name: str, therapeutic_area: str,
             drug: str, condition: str,
             years_covered: str = "All years",
             is_prespecified: bool = True) -> BenchmarkSet:
        """Build the final benchmark set."""
        return BenchmarkSet(
            name=name,
            description=f"Benchmark set for {drug} in {condition}",
            source="; ".join(self.sources_used),
            records=self.records.copy(),
            creation_date=datetime.now().isoformat(),
            therapeutic_area=therapeutic_area,
            drug_or_intervention=drug,
            condition=condition,
            is_prespecified=is_prespecified,
            sources_searched=self.sources_used.copy(),
            years_covered=years_covered
        )

    def reset(self):
        """Reset builder for new benchmark."""
        self.records = set()
        self.sources_used = []


def generate_validation_report(calculator: RelativeRecallCalculator,
                              comparison: SearchStringComparison) -> str:
    """Generate formatted validation report."""
    lines = [
        "=" * 70,
        "RELATIVE RECALL VALIDATION REPORT",
        "=" * 70,
        f"Benchmark: {comparison.benchmark_name}",
        f"Date: {datetime.now().strftime('%Y-%m-%d')}",
        f"Confidence Level: {calculator.confidence_level:.0%}",
        "",
        "SEARCH STRING COMPARISON",
        "-" * 50,
    ]

    # Sort by recall
    sorted_results = sorted(comparison.search_results,
                           key=lambda r: r.relative_recall, reverse=True)

    for result in sorted_results:
        is_best = result.search_id == comparison.best_search_id
        marker = " ⭐ BEST" if is_best else ""

        lines.extend([
            f"\n{result.search_id}{marker}",
            f"  Relative Recall: {result.relative_recall:.1%} "
            f"(95% CI: {result.recall_ci_lower:.1%}-{result.recall_ci_upper:.1%})",
            f"  Precision: {result.precision:.1%}",
            f"  F1 Score: {result.f1_score:.3f}",
            f"  Retrieved: {result.retrieved_total} | "
            f"Benchmark: {result.benchmark_total} | "
            f"Overlap: {result.true_positives}",
            f"  Missed: {result.false_negatives} records",
        ])

        if comparison.recall_differences[result.search_id] > 0:
            lines.append(
                f"  Gap from best: -{comparison.recall_differences[result.search_id]:.1%}"
            )

    # Summary statistics
    recalls = [r.relative_recall for r in comparison.search_results]

    lines.extend([
        "",
        "SUMMARY STATISTICS",
        "-" * 50,
        f"Best recall: {max(recalls):.1%}",
        f"Worst recall: {min(recalls):.1%}",
        f"Range: {max(recalls) - min(recalls):.1%}",
        f"Mean recall: {sum(recalls) / len(recalls):.1%}",
    ])

    # Recommendations
    lines.extend([
        "",
        "RECOMMENDATIONS",
        "-" * 50,
    ])

    if max(recalls) >= 0.95:
        lines.append("✓ Excellent: Best search achieves >95% relative recall")
    elif max(recalls) >= 0.90:
        lines.append("○ Good: Best search achieves 90-95% relative recall")
        lines.append("  Consider minor expansions to improve further")
    elif max(recalls) >= 0.80:
        lines.append("△ Moderate: Best search achieves 80-90% relative recall")
        lines.append("  Review missed records and expand search strategy")
    else:
        lines.append("✗ Low: Best search below 80% relative recall")
        lines.append("  Major revision of search strategy recommended")

    return "\n".join(lines)


def main():
    """Demo of relative recall framework."""
    print("Relative Recall Framework Demo")
    print("=" * 50)

    # Build benchmark set
    builder = BenchmarkSetBuilder()
    builder.add_from_pubmed_databank(
        drug="semaglutide",
        condition="type 2 diabetes",
        nct_ids=[f"NCT{i:08d}" for i in range(1000, 1100)]  # 100 trials
    )

    benchmark = builder.build(
        name="Semaglutide T2D Benchmark",
        therapeutic_area="diabetes",
        drug="semaglutide",
        condition="type 2 diabetes",
        years_covered="2015-2025"
    )

    # Create search results (simulated)
    search_basic = SearchStringResult(
        search_id="S1-Basic",
        search_string='query.intr="semaglutide"',
        database="ClinicalTrials.gov",
        records_retrieved={f"NCT{i:08d}" for i in range(1000, 1075)},  # 75 found
        execution_date=datetime.now().isoformat(),
        api_version="v2"
    )

    search_area = SearchStringResult(
        search_id="S2-AREA",
        search_string='AREA[InterventionName]semaglutide OR AREA[BriefTitle]semaglutide',
        database="ClinicalTrials.gov",
        records_retrieved={f"NCT{i:08d}" for i in range(1000, 1085)},  # 85 found
        execution_date=datetime.now().isoformat(),
        api_version="v2"
    )

    search_combined = SearchStringResult(
        search_id="S3-Combined",
        search_string='query.intr="semaglutide" OR query.intr="Ozempic" OR query.intr="Wegovy"',
        database="ClinicalTrials.gov",
        records_retrieved={f"NCT{i:08d}" for i in range(1000, 1092)},  # 92 found
        execution_date=datetime.now().isoformat(),
        api_version="v2"
    )

    # Calculate relative recall
    calculator = RelativeRecallCalculator(confidence_level=0.95)
    calculator.add_benchmark(benchmark)
    calculator.add_search_result(search_basic)
    calculator.add_search_result(search_area)
    calculator.add_search_result(search_combined)

    # Compare searches
    comparison = calculator.compare_searches(
        search_ids=["S1-Basic", "S2-AREA", "S3-Combined"],
        benchmark_name="Semaglutide T2D Benchmark"
    )

    # Generate report
    report = generate_validation_report(calculator, comparison)
    print(report)

    # McNemar test
    mcnemar = calculator.mcnemar_test("S1-Basic", "S3-Combined",
                                      "Semaglutide T2D Benchmark")
    print("\nMcNemar's Test (Basic vs Combined):")
    print(f"  Chi-squared: {mcnemar['chi_squared']}")
    print(f"  Significant difference: {mcnemar['significant_difference']}")

    # Save outputs
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "relative_recall_results.json", 'w') as f:
        json.dump({
            'benchmark': benchmark.to_dict(),
            'comparison': comparison.to_dict(),
            'mcnemar_test': mcnemar
        }, f, indent=2)

    print(f"\nResults saved to {output_dir / 'relative_recall_results.json'}")


if __name__ == "__main__":
    main()
