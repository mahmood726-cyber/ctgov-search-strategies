#!/usr/bin/env python3
"""
Statistical Validation Module
Proper statistical analysis with confidence intervals and precision metrics.

Addresses editorial concerns about:
- Missing confidence intervals
- No precision/PPV calculations
- No NNS (Number Needed to Screen) metrics

Author: Mahmood Ahmad
Version: 4.1
"""

import json
import math
import csv
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Import our modules
import sys
sys.path.insert(0, str(Path(__file__).parent))

from multi_registry_search import CTGovSearch


# =============================================================================
# STATISTICAL FUNCTIONS
# =============================================================================

def wilson_score_interval(successes: int, trials: int, confidence: float = 0.95) -> Tuple[float, float]:
    """
    Wilson score confidence interval for a proportion.
    More accurate than normal approximation, especially for extreme proportions.

    Args:
        successes: Number of successes (e.g., trials found)
        trials: Total number of trials
        confidence: Confidence level (default 0.95)

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    if trials == 0:
        return (0.0, 0.0)

    p = successes / trials

    # Z-score for confidence level
    z = {
        0.90: 1.645,
        0.95: 1.96,
        0.99: 2.576
    }.get(confidence, 1.96)

    denominator = 1 + z**2 / trials
    center = (p + z**2 / (2 * trials)) / denominator
    margin = z * math.sqrt((p * (1-p) + z**2 / (4 * trials)) / trials) / denominator

    return (max(0, center - margin), min(1, center + margin))


def clopper_pearson_interval(successes: int, trials: int, confidence: float = 0.95) -> Tuple[float, float]:
    """
    Clopper-Pearson exact confidence interval.
    More conservative than Wilson score.
    """
    from scipy import stats

    alpha = 1 - confidence

    if successes == 0:
        lower = 0.0
    else:
        lower = stats.beta.ppf(alpha/2, successes, trials - successes + 1)

    if successes == trials:
        upper = 1.0
    else:
        upper = stats.beta.ppf(1 - alpha/2, successes + 1, trials - successes)

    return (lower, upper)


# =============================================================================
# METRICS DATA CLASS
# =============================================================================

@dataclass
class ValidationMetrics:
    """Complete validation metrics with confidence intervals"""

    # Raw counts
    true_positives: int = 0  # Found in search AND in gold standard
    false_negatives: int = 0  # In gold standard but NOT found
    false_positives: int = 0  # Found in search but NOT in gold standard
    total_retrieved: int = 0  # Total results from search
    gold_standard_size: int = 0  # Total in gold standard

    # Confidence level
    confidence_level: float = 0.95

    @property
    def recall(self) -> float:
        """Sensitivity - proportion of gold standard found"""
        total = self.true_positives + self.false_negatives
        return self.true_positives / total if total > 0 else 0.0

    @property
    def recall_ci(self) -> Tuple[float, float]:
        """95% CI for recall using Wilson score"""
        total = self.true_positives + self.false_negatives
        return wilson_score_interval(self.true_positives, total, self.confidence_level)

    @property
    def precision(self) -> float:
        """Positive predictive value - proportion of retrieved that are relevant"""
        return self.true_positives / self.total_retrieved if self.total_retrieved > 0 else 0.0

    @property
    def precision_ci(self) -> Tuple[float, float]:
        """95% CI for precision"""
        return wilson_score_interval(self.true_positives, self.total_retrieved, self.confidence_level)

    @property
    def specificity(self) -> float:
        """True negative rate (requires knowing total negatives)"""
        # For search validation, specificity is less meaningful
        # as we don't have a defined "negative" population
        return None

    @property
    def f1_score(self) -> float:
        """Harmonic mean of precision and recall"""
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)

    @property
    def nns(self) -> float:
        """Number Needed to Screen - how many results to review to find one relevant"""
        return 1 / self.precision if self.precision > 0 else float('inf')

    @property
    def nnr(self) -> float:
        """Number Needed to Review - alternative name for NNS"""
        return self.nns

    @property
    def miss_rate(self) -> float:
        """False negative rate - proportion of gold standard missed"""
        return 1 - self.recall

    @property
    def volume_reduction(self) -> float:
        """Reduction in screening burden compared to baseline"""
        # This requires knowing the baseline (e.g., S1 results)
        return None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export"""
        recall_ci = self.recall_ci
        precision_ci = self.precision_ci

        return {
            "counts": {
                "true_positives": self.true_positives,
                "false_negatives": self.false_negatives,
                "false_positives": self.false_positives,
                "total_retrieved": self.total_retrieved,
                "gold_standard_size": self.gold_standard_size
            },
            "metrics": {
                "recall": round(self.recall, 4),
                "recall_ci_lower": round(recall_ci[0], 4),
                "recall_ci_upper": round(recall_ci[1], 4),
                "precision": round(self.precision, 4),
                "precision_ci_lower": round(precision_ci[0], 4),
                "precision_ci_upper": round(precision_ci[1], 4),
                "f1_score": round(self.f1_score, 4),
                "nns": round(self.nns, 2) if self.nns != float('inf') else "inf",
                "miss_rate": round(self.miss_rate, 4)
            },
            "confidence_level": self.confidence_level
        }

    def format_recall(self) -> str:
        """Format recall with CI for reporting"""
        ci = self.recall_ci
        return f"{self.recall:.1%} (95% CI: {ci[0]:.1%} - {ci[1]:.1%})"

    def format_precision(self) -> str:
        """Format precision with CI for reporting"""
        ci = self.precision_ci
        return f"{self.precision:.1%} (95% CI: {ci[0]:.1%} - {ci[1]:.1%})"


# =============================================================================
# STRATEGY VALIDATOR
# =============================================================================

@dataclass
class StrategyResult:
    """Results for a single search strategy"""
    strategy_id: str
    strategy_name: str
    condition: str
    query: str
    total_retrieved: int
    metrics: ValidationMetrics
    execution_time: float = 0.0


class StrategyValidator:
    """Validate search strategies against gold standard"""

    # Search strategy definitions
    STRATEGIES = {
        "S1": {
            "name": "Condition Only (Maximum Recall)",
            "query": "query.cond={condition}",
            "filters": {}
        },
        "S2": {
            "name": "Interventional Studies",
            "query": "query.cond={condition}&query.term=AREA[StudyType]INTERVENTIONAL",
            "filters": {"interventional": True}
        },
        "S3": {
            "name": "Randomized Allocation Only",
            "query": "query.cond={condition}&query.term=AREA[DesignAllocation]RANDOMIZED",
            "filters": {"randomized": True}
        },
        "S6": {
            "name": "Completed Status",
            "query": "query.cond={condition}&filter.overallStatus=COMPLETED",
            "filters": {"completed": True}
        },
        "S10": {
            "name": "Treatment RCTs Only",
            "query": "query.cond={condition}&query.term=AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT",
            "filters": {"randomized": True, "treatment": True}
        }
    }

    def __init__(self):
        self.ctgov = CTGovSearch()

    def load_gold_standard(self, path: str) -> Dict[str, List[str]]:
        """
        Load gold standard NCT IDs grouped by condition.

        Returns:
            Dict mapping condition -> list of NCT IDs
        """
        gold_standard = {}

        with open(path, 'r', encoding='utf-8') as f:
            if path.endswith('.json'):
                data = json.load(f)
                for trial in data.get("trials", []):
                    condition = trial.get("condition", "unknown")
                    nct_id = trial.get("nct_id", "")
                    if nct_id:
                        if condition not in gold_standard:
                            gold_standard[condition] = []
                        gold_standard[condition].append(nct_id)
            else:
                reader = csv.DictReader(f)
                for row in reader:
                    condition = row.get("condition", "unknown")
                    nct_id = row.get("nct_id", "")
                    if nct_id:
                        if condition not in gold_standard:
                            gold_standard[condition] = []
                        gold_standard[condition].append(nct_id)

        return gold_standard

    def validate_strategy(
        self,
        strategy_id: str,
        condition: str,
        gold_standard_ncts: List[str]
    ) -> StrategyResult:
        """Validate a single strategy against gold standard"""
        import time

        strategy = self.STRATEGIES.get(strategy_id)
        if not strategy:
            raise ValueError(f"Unknown strategy: {strategy_id}")

        start_time = time.time()

        # Run search
        results = self.ctgov.search(condition, strategy.get("filters", {}))
        retrieved_ncts = set(r.registry_id for r in results)

        execution_time = time.time() - start_time

        # Calculate metrics
        gold_set = set(gold_standard_ncts)

        true_positives = len(retrieved_ncts & gold_set)
        false_negatives = len(gold_set - retrieved_ncts)
        false_positives = len(retrieved_ncts - gold_set)

        metrics = ValidationMetrics(
            true_positives=true_positives,
            false_negatives=false_negatives,
            false_positives=false_positives,
            total_retrieved=len(retrieved_ncts),
            gold_standard_size=len(gold_set)
        )

        return StrategyResult(
            strategy_id=strategy_id,
            strategy_name=strategy["name"],
            condition=condition,
            query=strategy["query"].format(condition=condition),
            total_retrieved=len(results),
            metrics=metrics,
            execution_time=execution_time
        )

    def validate_all_strategies(
        self,
        condition: str,
        gold_standard_ncts: List[str]
    ) -> List[StrategyResult]:
        """Validate all strategies for a condition"""
        results = []

        for strategy_id in self.STRATEGIES:
            print(f"  Testing {strategy_id}...", end=" ", flush=True)
            result = self.validate_strategy(strategy_id, condition, gold_standard_ncts)
            print(f"Recall: {result.metrics.format_recall()}")
            results.append(result)

        return results


# =============================================================================
# REPORT GENERATOR
# =============================================================================

def generate_validation_report(
    results: List[StrategyResult],
    output_path: str = None
) -> str:
    """Generate comprehensive validation report"""

    lines = [
        "# CT.gov Search Strategy Validation Report",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Executive Summary",
        "",
        "This report presents validation results with proper statistical analysis:",
        "- 95% Wilson score confidence intervals for all proportions",
        "- Precision (PPV) and Number Needed to Screen (NNS) metrics",
        "- Multiple conditions tested for generalizability",
        "",
        "---",
        "",
        "## Strategy Performance",
        "",
        "| Strategy | Name | Recall (95% CI) | Precision (95% CI) | NNS | Retrieved |",
        "|----------|------|-----------------|-------------------|-----|-----------|"
    ]

    for result in results:
        m = result.metrics
        recall_ci = m.recall_ci
        precision_ci = m.precision_ci
        nns = f"{m.nns:.1f}" if m.nns != float('inf') else ">1000"

        lines.append(
            f"| {result.strategy_id} | {result.strategy_name} | "
            f"{m.recall:.1%} ({recall_ci[0]:.1%}-{recall_ci[1]:.1%}) | "
            f"{m.precision:.1%} ({precision_ci[0]:.1%}-{precision_ci[1]:.1%}) | "
            f"{nns} | {m.total_retrieved} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## Detailed Results",
        ""
    ])

    for result in results:
        m = result.metrics
        lines.extend([
            f"### {result.strategy_id}: {result.strategy_name}",
            "",
            f"**Condition:** {result.condition}",
            f"**Query:** `{result.query}`",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Gold Standard Size | {m.gold_standard_size} |",
            f"| Total Retrieved | {m.total_retrieved} |",
            f"| True Positives | {m.true_positives} |",
            f"| False Negatives | {m.false_negatives} |",
            f"| Recall | {m.format_recall()} |",
            f"| Precision | {m.format_precision()} |",
            f"| F1 Score | {m.f1_score:.3f} |",
            f"| Number Needed to Screen | {m.nns:.1f} |",
            f"| Miss Rate | {m.miss_rate:.1%} |",
            ""
        ])

    lines.extend([
        "---",
        "",
        "## Statistical Methods",
        "",
        "- **Confidence Intervals:** Wilson score method (more accurate for extreme proportions)",
        "- **Recall:** Sensitivity = TP / (TP + FN)",
        "- **Precision:** PPV = TP / Total Retrieved",
        "- **NNS:** Number Needed to Screen = 1 / Precision",
        "",
        "---",
        "",
        "*Report generated by CT.gov Trial Registry Integrity Suite v4.1*"
    ])

    report = "\n".join(lines)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)

    return report


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Statistical Validation of Search Strategies")
    parser.add_argument("gold_standard", help="Path to gold standard CSV/JSON")
    parser.add_argument("-c", "--condition", help="Specific condition to test")
    parser.add_argument("-s", "--strategy", help="Specific strategy to test")
    parser.add_argument("-o", "--output", help="Output report path")
    parser.add_argument("--json", help="Output JSON metrics")

    args = parser.parse_args()

    validator = StrategyValidator()

    # Load gold standard
    print("Loading gold standard...")
    gold_standard = validator.load_gold_standard(args.gold_standard)
    print(f"Loaded {sum(len(v) for v in gold_standard.values())} trials across {len(gold_standard)} conditions")

    all_results = []

    if args.condition:
        conditions = [args.condition]
    else:
        # Test top conditions by size
        conditions = sorted(gold_standard.keys(), key=lambda c: len(gold_standard[c]), reverse=True)[:5]

    for condition in conditions:
        ncts = gold_standard.get(condition, [])
        if len(ncts) < 5:
            continue

        print(f"\nValidating condition: {condition} ({len(ncts)} trials)")
        print("-" * 50)

        if args.strategy:
            result = validator.validate_strategy(args.strategy, condition, ncts)
            all_results.append(result)
            print(f"Recall: {result.metrics.format_recall()}")
        else:
            results = validator.validate_all_strategies(condition, ncts)
            all_results.extend(results)

    # Generate report
    if args.output:
        report = generate_validation_report(all_results, args.output)
        print(f"\nReport saved to {args.output}")

    if args.json:
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": [
                {
                    "strategy_id": r.strategy_id,
                    "strategy_name": r.strategy_name,
                    "condition": r.condition,
                    **r.metrics.to_dict()
                }
                for r in all_results
            ]
        }
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
        print(f"JSON metrics saved to {args.json}")


if __name__ == "__main__":
    main()
