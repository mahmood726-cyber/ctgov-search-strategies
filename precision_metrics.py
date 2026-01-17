#!/usr/bin/env python3
"""
Precision Metrics and Screening Efficiency Module for CT.gov Search Strategies

This module provides comprehensive metrics calculation for systematic review
search strategy evaluation, including:
- Precision and recall calculations
- Number Needed to Screen (NNS) estimation
- F1 score and diagnostic accuracy metrics
- Screening workload analysis
- ROC data generation for strategy comparison

Based on Cochrane Handbook guidance and systematic review methodology.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, TypedDict, Union


class ScreeningBurdenDict(TypedDict, total=False):
    """TypedDict for screening burden comparison results."""
    strategy_id: str
    strategy_name: str
    total_retrieved: int
    relevant_found: int
    precision: float
    nns: float
    rank: int


class StrategyMetricsDict(TypedDict):
    """TypedDict for strategy metrics in report generation."""
    result: Any  # StrategyResult - using Any to avoid forward reference issues
    found_relevant: int
    precision: float
    recall: float
    f1: float
    nns: float


class ROCPointDict(TypedDict, total=False):
    """TypedDict for ROC curve data points."""
    strategy_id: str
    strategy_name: str
    fpr: float
    tpr: float
    sensitivity: float
    specificity: float


class ROCDataDict(TypedDict):
    """TypedDict for ROC data return value."""
    points: List[ROCPointDict]
    auc_estimates: Dict[str, float]


@dataclass
class StrategyResult:
    """Container for a search strategy's results."""
    strategy_id: str
    strategy_name: str
    total_retrieved: int
    relevant_found: int
    nct_ids_found: Set[str] = field(default_factory=set)
    execution_time: float = 0.0


class PrecisionCalculator:
    """
    Calculate precision and related metrics for search strategies.

    Precision measures the proportion of retrieved studies that are relevant,
    answering the question: "Of all the studies I retrieved, how many are actually relevant?"

    Example:
        >>> calc = PrecisionCalculator()
        >>> precision = calc.calculate_precision(relevant_found=50, total_retrieved=500)
        >>> print(f"Precision: {precision:.2%}")
        Precision: 10.00%
    """

    @staticmethod
    def calculate_precision(relevant_found: int, total_retrieved: int) -> float:
        """
        Calculate precision (positive predictive value).

        Precision = TP / (TP + FP) = Relevant Found / Total Retrieved

        Args:
            relevant_found: Number of relevant studies found (true positives)
            total_retrieved: Total number of studies retrieved by the search

        Returns:
            Precision as a float between 0.0 and 1.0

        Raises:
            ValueError: If inputs are negative or relevant_found > total_retrieved
        """
        if relevant_found < 0 or total_retrieved < 0:
            raise ValueError("Counts cannot be negative")
        if total_retrieved == 0:
            return 0.0
        if relevant_found > total_retrieved:
            raise ValueError("relevant_found cannot exceed total_retrieved")
        return relevant_found / total_retrieved

    @staticmethod
    def calculate_nns(total_retrieved: int, relevant_found: int) -> float:
        """
        Calculate Number Needed to Screen (NNS).

        NNS represents the average number of records that need to be screened
        to find one relevant study. Lower NNS indicates more efficient screening.

        NNS = Total Retrieved / Relevant Found = 1 / Precision

        Args:
            total_retrieved: Total number of studies retrieved by the search
            relevant_found: Number of relevant studies found

        Returns:
            NNS as a float (number of records to screen per relevant study found)
            Returns float('inf') if no relevant studies found

        Raises:
            ValueError: If inputs are negative
        """
        if relevant_found < 0 or total_retrieved < 0:
            raise ValueError("Counts cannot be negative")
        if relevant_found == 0:
            return float('inf')
        return total_retrieved / relevant_found

    @staticmethod
    def calculate_f1_score(precision: float, recall: float) -> float:
        """
        Calculate F1 score (harmonic mean of precision and recall).

        F1 balances precision and recall, useful when you want to find an
        optimal balance between finding all relevant studies (recall) and
        minimizing irrelevant results (precision).

        F1 = 2 * (precision * recall) / (precision + recall)

        Args:
            precision: Precision score (0.0 to 1.0)
            recall: Recall/sensitivity score (0.0 to 1.0)

        Returns:
            F1 score as a float between 0.0 and 1.0

        Raises:
            ValueError: If precision or recall are outside [0, 1]
        """
        if not (0 <= precision <= 1) or not (0 <= recall <= 1):
            raise ValueError("Precision and recall must be between 0 and 1")
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)

    @staticmethod
    def calculate_specificity(true_negatives: int, false_positives: int) -> float:
        """
        Calculate specificity (true negative rate).

        Specificity measures the proportion of actual negatives correctly identified.
        In search context: "Of all irrelevant studies, how many did we correctly exclude?"

        Specificity = TN / (TN + FP)

        Args:
            true_negatives: Number of irrelevant studies correctly not retrieved
            false_positives: Number of irrelevant studies incorrectly retrieved

        Returns:
            Specificity as a float between 0.0 and 1.0

        Raises:
            ValueError: If inputs are negative
        """
        if true_negatives < 0 or false_positives < 0:
            raise ValueError("Counts cannot be negative")
        total = true_negatives + false_positives
        if total == 0:
            return 0.0
        return true_negatives / total


class ScreeningEfficiencyAnalyzer:
    """
    Analyze screening workload and efficiency for systematic reviews.

    Provides tools to estimate time requirements and compare screening
    burden across different search strategies.

    Example:
        >>> analyzer = ScreeningEfficiencyAnalyzer()
        >>> hours = analyzer.estimate_screening_time(nns=50, time_per_abstract_minutes=2)
        >>> print(f"Expected screening time: {hours:.1f} hours per relevant study")
    """

    @staticmethod
    def estimate_screening_time(
        nns: float,
        time_per_abstract_minutes: float = 2.0
    ) -> float:
        """
        Estimate screening time based on NNS.

        Estimates hours needed to screen enough records to find one relevant study,
        based on Number Needed to Screen and average screening time per abstract.

        Args:
            nns: Number Needed to Screen (records per relevant study)
            time_per_abstract_minutes: Average time to screen one abstract (default: 2 min)

        Returns:
            Estimated hours to find one relevant study

        Note:
            Default screening time of 2 minutes per abstract is based on
            empirical estimates from systematic review literature.
        """
        if nns == float('inf'):
            return float('inf')
        if nns < 0 or time_per_abstract_minutes < 0:
            raise ValueError("NNS and time cannot be negative")
        return (nns * time_per_abstract_minutes) / 60.0

    @staticmethod
    def calculate_workload_reduction(
        strategy_a_count: int,
        strategy_b_count: int
    ) -> float:
        """
        Calculate percentage workload reduction between two strategies.

        Compares the number of records to screen between Strategy A (baseline)
        and Strategy B (alternative), expressing the reduction as a percentage.

        Args:
            strategy_a_count: Number of records from baseline strategy
            strategy_b_count: Number of records from alternative strategy

        Returns:
            Percentage reduction (positive = B requires less screening)
            Negative value means B requires more screening than A

        Example:
            >>> # Strategy A retrieves 1000, Strategy B retrieves 600
            >>> reduction = ScreeningEfficiencyAnalyzer.calculate_workload_reduction(1000, 600)
            >>> print(f"Workload reduction: {reduction:.1f}%")
            Workload reduction: 40.0%
        """
        if strategy_a_count < 0 or strategy_b_count < 0:
            raise ValueError("Counts cannot be negative")
        if strategy_a_count == 0:
            return 0.0
        return ((strategy_a_count - strategy_b_count) / strategy_a_count) * 100

    @staticmethod
    def compare_screening_burden(
        strategies_results: List[StrategyResult]
    ) -> List[ScreeningBurdenDict]:
        """
        Compare and rank strategies by screening burden.

        Analyzes multiple search strategies and ranks them by efficiency,
        considering both total retrieval and relevance.

        Args:
            strategies_results: List of StrategyResult objects to compare

        Returns:
            List of dicts sorted by NNS (most efficient first), containing:
            - strategy_id: Strategy identifier
            - strategy_name: Human-readable name
            - total_retrieved: Number of records retrieved
            - relevant_found: Number of relevant records found
            - precision: Precision score
            - nns: Number Needed to Screen
            - rank: Efficiency rank (1 = most efficient)

        Example:
            >>> results = [
            ...     StrategyResult("S1", "Condition Only", 1000, 50),
            ...     StrategyResult("S3", "RCT Filter", 300, 45)
            ... ]
            >>> ranked = ScreeningEfficiencyAnalyzer.compare_screening_burden(results)
            >>> for r in ranked:
            ...     print(f"{r['rank']}. {r['strategy_id']}: NNS={r['nns']:.1f}")
        """
        calc = PrecisionCalculator()
        burden_data: List[ScreeningBurdenDict] = []

        for result in strategies_results:
            precision = calc.calculate_precision(
                result.relevant_found,
                result.total_retrieved
            )
            nns = calc.calculate_nns(
                result.total_retrieved,
                result.relevant_found
            )

            burden_data.append({
                'strategy_id': result.strategy_id,
                'strategy_name': result.strategy_name,
                'total_retrieved': result.total_retrieved,
                'relevant_found': result.relevant_found,
                'precision': precision,
                'nns': nns
            })

        # Sort by NNS (lower is better), treating inf as very large
        def get_nns_for_sort(x: ScreeningBurdenDict) -> float:
            nns_val = x.get('nns', float('inf'))
            return nns_val if nns_val != float('inf') else float('inf')

        burden_data.sort(key=get_nns_for_sort)

        # Add ranks
        for i, item in enumerate(burden_data, 1):
            item['rank'] = i

        return burden_data


class ValidationMetrics:
    """
    Comprehensive validation metrics for search strategy evaluation.

    Provides full diagnostic accuracy metrics including sensitivity, specificity,
    likelihood ratios, and diagnostic odds ratio for rigorous search validation.

    Example:
        >>> metrics = ValidationMetrics()
        >>> results = metrics.full_metrics(tp=45, fp=255, fn=5, tn=9695)
        >>> print(f"Sensitivity: {results['sensitivity']:.2%}")
        >>> print(f"Specificity: {results['specificity']:.2%}")
    """

    @staticmethod
    def full_metrics(
        true_positives: int,
        false_positives: int,
        false_negatives: int,
        true_negatives: int
    ) -> Dict[str, float]:
        """
        Calculate comprehensive diagnostic accuracy metrics.

        Computes all standard diagnostic accuracy metrics from the 2x2 confusion matrix.

        Args:
            true_positives: Relevant studies correctly retrieved (TP)
            false_positives: Irrelevant studies incorrectly retrieved (FP)
            false_negatives: Relevant studies missed (FN)
            true_negatives: Irrelevant studies correctly not retrieved (TN)

        Returns:
            Dictionary containing:
            - sensitivity: TP / (TP + FN) - recall, true positive rate
            - specificity: TN / (TN + FP) - true negative rate
            - precision: TP / (TP + FP) - positive predictive value
            - npv: TN / (TN + FN) - negative predictive value
            - f1_score: Harmonic mean of precision and recall
            - accuracy: (TP + TN) / Total
            - nns: Number Needed to Screen
            - lr_positive: Positive likelihood ratio
            - lr_negative: Negative likelihood ratio
            - dor: Diagnostic Odds Ratio

        Raises:
            ValueError: If any count is negative
        """
        if any(x < 0 for x in [true_positives, false_positives, false_negatives, true_negatives]):
            raise ValueError("All counts must be non-negative")

        # Calculate totals
        total_relevant = true_positives + false_negatives
        total_irrelevant = true_negatives + false_positives
        total_retrieved = true_positives + false_positives
        total_not_retrieved = true_negatives + false_negatives
        total = total_relevant + total_irrelevant

        # Sensitivity (recall, TPR)
        sensitivity = true_positives / total_relevant if total_relevant > 0 else 0.0

        # Specificity (TNR)
        specificity = true_negatives / total_irrelevant if total_irrelevant > 0 else 0.0

        # Precision (PPV)
        precision = true_positives / total_retrieved if total_retrieved > 0 else 0.0

        # NPV
        npv = true_negatives / total_not_retrieved if total_not_retrieved > 0 else 0.0

        # F1 Score
        f1_score = 0.0
        if precision + sensitivity > 0:
            f1_score = 2 * (precision * sensitivity) / (precision + sensitivity)

        # Accuracy
        accuracy = (true_positives + true_negatives) / total if total > 0 else 0.0

        # NNS
        nns = total_retrieved / true_positives if true_positives > 0 else float('inf')

        # Likelihood ratios
        lr_positive = 0.0
        lr_negative = float('inf')
        if specificity < 1:
            lr_positive = sensitivity / (1 - specificity) if sensitivity > 0 else 0.0
        if specificity > 0:
            lr_negative = (1 - sensitivity) / specificity if sensitivity < 1 else 0.0

        # Diagnostic Odds Ratio
        dor = 0.0
        if false_positives > 0 and false_negatives > 0:
            dor = (true_positives * true_negatives) / (false_positives * false_negatives)
        elif true_positives > 0 and true_negatives > 0 and false_positives == 0 and false_negatives == 0:
            dor = float('inf')  # Perfect test

        return {
            'true_positives': true_positives,
            'false_positives': false_positives,
            'false_negatives': false_negatives,
            'true_negatives': true_negatives,
            'sensitivity': sensitivity,
            'specificity': specificity,
            'precision': precision,
            'npv': npv,
            'f1_score': f1_score,
            'accuracy': accuracy,
            'nns': nns,
            'lr_positive': lr_positive,
            'lr_negative': lr_negative,
            'dor': dor
        }

    @staticmethod
    def confusion_matrix_from_results(
        found_ncts: Set[str],
        known_ncts: Set[str],
        total_searched: int
    ) -> Dict[str, int]:
        """
        Construct confusion matrix from search results and known relevant set.

        Args:
            found_ncts: Set of NCT IDs retrieved by the search
            known_ncts: Set of NCT IDs known to be relevant (gold standard)
            total_searched: Total number of records in the database searched

        Returns:
            Dictionary with confusion matrix values:
            - true_positives: Relevant studies found
            - false_positives: Irrelevant studies retrieved
            - false_negatives: Relevant studies missed
            - true_negatives: Irrelevant studies correctly not retrieved

        Note:
            total_searched should represent the universe of records that could
            have been retrieved (e.g., total studies matching base criteria).
        """
        # Normalize NCT IDs
        found_set = {nct.upper().strip() for nct in found_ncts if nct}
        known_set = {nct.upper().strip() for nct in known_ncts if nct}

        true_positives = len(found_set & known_set)
        false_positives = len(found_set - known_set)
        false_negatives = len(known_set - found_set)

        # True negatives = total records - (TP + FP + FN)
        # Represents irrelevant records correctly not retrieved
        true_negatives = max(0, total_searched - (true_positives + false_positives + false_negatives))

        return {
            'true_positives': true_positives,
            'false_positives': false_positives,
            'false_negatives': false_negatives,
            'true_negatives': true_negatives
        }

    @staticmethod
    def calculate_diagnostic_odds_ratio(
        tp: int,
        fp: int,
        fn: int,
        tn: int
    ) -> float:
        """
        Calculate the Diagnostic Odds Ratio (DOR).

        DOR summarizes the discriminative ability of a search strategy.
        Higher DOR indicates better discrimination between relevant and irrelevant.

        DOR = (TP * TN) / (FP * FN)

        Args:
            tp: True positives
            fp: False positives
            fn: False negatives
            tn: True negatives

        Returns:
            DOR as a float (range: 0 to infinity)
            Returns inf for perfect tests (no errors)
            Returns 0 if tp=0 or tn=0

        Note:
            DOR is undefined when FP=0 or FN=0 (returns inf).
            DOR = 1 indicates no discriminative ability.
            DOR > 1 indicates good discrimination.
        """
        if any(x < 0 for x in [tp, fp, fn, tn]):
            raise ValueError("All counts must be non-negative")

        if fp == 0 or fn == 0:
            if tp > 0 and tn > 0:
                return float('inf')  # Perfect or near-perfect
            return 0.0

        return (tp * tn) / (fp * fn)

    @staticmethod
    def calculate_likelihood_ratios(
        sensitivity: float,
        specificity: float
    ) -> Tuple[float, float]:
        """
        Calculate positive and negative likelihood ratios.

        Likelihood ratios express how much a search result changes the odds
        of a study being relevant.

        LR+ = sensitivity / (1 - specificity)
        LR- = (1 - sensitivity) / specificity

        Args:
            sensitivity: True positive rate (0.0 to 1.0)
            specificity: True negative rate (0.0 to 1.0)

        Returns:
            Tuple of (LR+, LR-)

        Interpretation:
            LR+ > 10: Strong evidence for relevance if found
            LR+ 5-10: Moderate evidence for relevance
            LR- < 0.1: Strong evidence against relevance if not found
            LR- 0.1-0.2: Moderate evidence against relevance
        """
        if not (0 <= sensitivity <= 1) or not (0 <= specificity <= 1):
            raise ValueError("Sensitivity and specificity must be between 0 and 1")

        # LR+ = sensitivity / (1 - specificity)
        if specificity == 1:
            lr_positive = float('inf') if sensitivity > 0 else 0.0
        else:
            lr_positive = sensitivity / (1 - specificity)

        # LR- = (1 - sensitivity) / specificity
        if specificity == 0:
            lr_negative = float('inf')
        else:
            lr_negative = (1 - sensitivity) / specificity

        return (lr_positive, lr_negative)


def generate_precision_report(
    condition: str,
    strategies_results: List[StrategyResult],
    known_ncts: Set[str],
    total_database_size: Optional[int] = None
) -> str:
    """
    Generate a comprehensive markdown precision report.

    Creates a formatted report comparing multiple search strategies
    for a given condition, including precision, recall, NNS, and
    efficiency metrics.

    Args:
        condition: Medical condition being searched
        strategies_results: List of StrategyResult objects
        known_ncts: Set of known relevant NCT IDs (gold standard)
        total_database_size: Optional total records in database for specificity calculation

    Returns:
        Markdown-formatted report string

    Example:
        >>> results = [StrategyResult("S1", "Condition Only", 1000, set(), 0)]
        >>> known = {"NCT00000001", "NCT00000002"}
        >>> report = generate_precision_report("diabetes", results, known)
        >>> print(report)
    """
    calc = PrecisionCalculator()
    analyzer = ScreeningEfficiencyAnalyzer()
    validator = ValidationMetrics()

    lines = []
    lines.append(f"# Precision Metrics Report: {condition.title()}")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Gold Standard Size:** {len(known_ncts)} NCT IDs")
    if total_database_size:
        lines.append(f"**Database Size:** {total_database_size:,} records")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Strategy comparison table
    lines.append("## Strategy Comparison")
    lines.append("")
    lines.append("| Strategy | Retrieved | Relevant | Precision | Recall | F1 | NNS |")
    lines.append("|----------|-----------|----------|-----------|--------|-----|-----|")

    strategy_metrics: List[StrategyMetricsDict] = []
    for result in strategies_results:
        # Calculate overlap with known relevant
        found_relevant = len(result.nct_ids_found & known_ncts) if result.nct_ids_found else result.relevant_found

        precision = calc.calculate_precision(found_relevant, result.total_retrieved)
        recall = found_relevant / len(known_ncts) if known_ncts else 0.0
        f1 = calc.calculate_f1_score(precision, recall)
        nns = calc.calculate_nns(result.total_retrieved, found_relevant)

        strategy_metrics.append({
            'result': result,
            'found_relevant': found_relevant,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'nns': nns
        })

        nns_str = f"{nns:.1f}" if nns != float('inf') else "inf"
        lines.append(
            f"| {result.strategy_id} | {result.total_retrieved:,} | "
            f"{found_relevant} | {precision:.2%} | {recall:.2%} | "
            f"{f1:.3f} | {nns_str} |"
        )

    lines.append("")

    # Screening efficiency section
    lines.append("## Screening Efficiency Analysis")
    lines.append("")
    lines.append("*Estimated time to screen enough records to find one relevant study*")
    lines.append("*(assuming 2 minutes per abstract)*")
    lines.append("")
    lines.append("| Strategy | NNS | Hours per Relevant | Workload vs S1 |")
    lines.append("|----------|-----|-------------------|----------------|")

    baseline_count = strategies_results[0].total_retrieved if strategies_results else 0

    for sm in strategy_metrics:
        hours = analyzer.estimate_screening_time(sm['nns'])
        hours_str = f"{hours:.1f}" if hours != float('inf') else "inf"

        reduction = analyzer.calculate_workload_reduction(
            baseline_count,
            sm['result'].total_retrieved
        )
        reduction_str = f"{reduction:+.1f}%" if baseline_count > 0 else "N/A"

        nns_display = f"{sm['nns']:.1f}" if sm['nns'] != float('inf') else "inf"
        lines.append(
            f"| {sm['result'].strategy_id} | {nns_display} | "
            f"{hours_str} | {reduction_str} |"
        )

    lines.append("")

    # Best strategy recommendation
    lines.append("## Recommendations")
    lines.append("")

    # Find best by different criteria - using typed helper functions
    def get_recall(x: StrategyMetricsDict) -> float:
        return x['recall']

    def get_precision(x: StrategyMetricsDict) -> float:
        return x['precision']

    def get_f1(x: StrategyMetricsDict) -> float:
        return x['f1']

    def get_nns(x: StrategyMetricsDict) -> float:
        nns_val = x['nns']
        return nns_val if nns_val != float('inf') else float('inf')

    best_recall = max(strategy_metrics, key=get_recall)
    best_precision = max(strategy_metrics, key=get_precision)
    best_f1 = max(strategy_metrics, key=get_f1)
    best_nns = min(strategy_metrics, key=get_nns)

    lines.append(f"- **Highest Recall (Sensitivity):** {best_recall['result'].strategy_id} "
                 f"({best_recall['recall']:.1%})")
    lines.append(f"- **Highest Precision:** {best_precision['result'].strategy_id} "
                 f"({best_precision['precision']:.1%})")
    lines.append(f"- **Best F1 Score:** {best_f1['result'].strategy_id} "
                 f"({best_f1['f1']:.3f})")
    lines.append(f"- **Most Efficient (Lowest NNS):** {best_nns['result'].strategy_id} "
                 f"(NNS={best_nns['nns']:.1f})")
    lines.append("")

    # Full metrics for best strategy if total_database_size provided
    if total_database_size and strategy_metrics:
        lines.append(f"## Detailed Metrics for Best F1 Strategy ({best_f1['result'].strategy_id})")
        lines.append("")

        tp = best_f1['found_relevant']
        fp = best_f1['result'].total_retrieved - tp
        fn = len(known_ncts) - tp
        tn = total_database_size - (tp + fp + fn)

        full = validator.full_metrics(tp, fp, fn, tn)

        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Sensitivity | {full['sensitivity']:.4f} |")
        lines.append(f"| Specificity | {full['specificity']:.4f} |")
        lines.append(f"| Precision (PPV) | {full['precision']:.4f} |")
        lines.append(f"| NPV | {full['npv']:.4f} |")
        lines.append(f"| Accuracy | {full['accuracy']:.4f} |")
        lines.append(f"| LR+ | {full['lr_positive']:.2f} |")
        lines.append(f"| LR- | {full['lr_negative']:.4f} |")
        lines.append(f"| DOR | {full['dor']:.2f} |")
        lines.append("")

    lines.append("---")
    lines.append("*Report generated by precision_metrics.py*")

    return "\n".join(lines)


def export_metrics_csv(
    metrics_list: List[Dict[str, Union[str, int, float]]],
    filepath: str
) -> None:
    """
    Export metrics to CSV file.

    Args:
        metrics_list: List of metric dictionaries to export
        filepath: Output file path

    Example:
        >>> metrics = [
        ...     {'strategy_id': 'S1', 'precision': 0.05, 'recall': 0.95},
        ...     {'strategy_id': 'S3', 'precision': 0.15, 'recall': 0.90}
        ... ]
        >>> export_metrics_csv(metrics, 'output/metrics.csv')
    """
    if not metrics_list:
        return

    # Get all unique keys
    fieldnames = []
    for m in metrics_list:
        for key in m.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(metrics_list)


def create_roc_data(
    strategies_results: List[StrategyResult],
    known_ncts: Set[str],
    total_database_size: int
) -> ROCDataDict:
    """
    Create ROC curve data for plotting strategy performance.

    Generates (1-specificity, sensitivity) coordinates for each strategy,
    suitable for ROC curve visualization.

    Args:
        strategies_results: List of StrategyResult objects
        known_ncts: Set of known relevant NCT IDs
        total_database_size: Total records in database

    Returns:
        Dictionary with:
        - 'points': List of dicts with strategy_id, fpr (1-specificity), tpr (sensitivity)
        - 'auc_estimates': Dict mapping strategy_id to rough AUC estimate

    Example:
        >>> roc = create_roc_data(results, known, 10000)
        >>> for point in roc['points']:
        ...     print(f"{point['strategy_id']}: FPR={point['fpr']:.3f}, TPR={point['tpr']:.3f}")
    """
    points: List[ROCPointDict] = []
    auc_estimates: Dict[str, float] = {}

    # Add origin point (0, 0)
    points.append({
        'strategy_id': 'origin',
        'fpr': 0.0,
        'tpr': 0.0
    })

    for result in strategies_results:
        # Calculate confusion matrix
        found_relevant = len(result.nct_ids_found & known_ncts) if result.nct_ids_found else result.relevant_found

        tp = found_relevant
        fp = result.total_retrieved - tp
        fn = len(known_ncts) - tp
        tn = max(0, total_database_size - (tp + fp + fn))

        # Calculate sensitivity and specificity
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

        fpr = 1 - specificity  # False positive rate
        tpr = sensitivity  # True positive rate

        points.append({
            'strategy_id': result.strategy_id,
            'strategy_name': result.strategy_name,
            'fpr': fpr,
            'tpr': tpr,
            'sensitivity': sensitivity,
            'specificity': specificity
        })

        # Simple AUC estimate (trapezoidal approximation from origin)
        # This is a rough estimate - for accurate AUC, multiple thresholds needed
        auc_estimates[result.strategy_id] = 0.5 + (tpr - fpr) / 2

    # Add upper right corner (1, 1)
    points.append({
        'strategy_id': 'chance',
        'fpr': 1.0,
        'tpr': 1.0
    })

    # Sort by FPR for plotting
    def roc_sort_key(x: ROCPointDict) -> Tuple[float, float]:
        return (x.get('fpr', 0.0), -x.get('tpr', 0.0))

    points.sort(key=roc_sort_key)

    return {
        'points': points,
        'auc_estimates': auc_estimates
    }


if __name__ == "__main__":
    """Example usage demonstrating all module capabilities."""

    print("=" * 70)
    print("  Precision Metrics Module - Demo")
    print("=" * 70)

    # Initialize calculators
    calc = PrecisionCalculator()
    analyzer = ScreeningEfficiencyAnalyzer()
    validator = ValidationMetrics()

    # Example scenario: Systematic review search for "heart failure"
    print("\n" + "-" * 70)
    print("  Example: Heart Failure Systematic Review Search")
    print("-" * 70)

    # Gold standard: 50 known relevant RCTs
    known_relevant = {f"NCT{str(i).zfill(8)}" for i in range(1, 51)}

    # Simulate strategy results
    strategies = [
        StrategyResult(
            strategy_id="S1",
            strategy_name="Condition Only",
            total_retrieved=1000,
            relevant_found=48,
            nct_ids_found={f"NCT{str(i).zfill(8)}" for i in range(1, 49)} |
                          {f"NCT{str(i).zfill(8)}" for i in range(100, 1052)}
        ),
        StrategyResult(
            strategy_id="S3",
            strategy_name="RCT Filter",
            total_retrieved=300,
            relevant_found=45,
            nct_ids_found={f"NCT{str(i).zfill(8)}" for i in range(1, 46)} |
                          {f"NCT{str(i).zfill(8)}" for i in range(100, 355)}
        ),
        StrategyResult(
            strategy_id="S7",
            strategy_name="Completed Interventional",
            total_retrieved=200,
            relevant_found=40,
            nct_ids_found={f"NCT{str(i).zfill(8)}" for i in range(1, 41)} |
                          {f"NCT{str(i).zfill(8)}" for i in range(100, 260)}
        ),
    ]

    # 1. Basic precision metrics
    print("\n1. PRECISION CALCULATIONS")
    print("-" * 40)

    for strat in strategies:
        precision = calc.calculate_precision(strat.relevant_found, strat.total_retrieved)
        nns = calc.calculate_nns(strat.total_retrieved, strat.relevant_found)
        recall = strat.relevant_found / len(known_relevant)
        f1 = calc.calculate_f1_score(precision, recall)

        print(f"\n  {strat.strategy_id} - {strat.strategy_name}:")
        print(f"    Retrieved: {strat.total_retrieved:,}")
        print(f"    Relevant Found: {strat.relevant_found}")
        print(f"    Precision: {precision:.2%}")
        print(f"    Recall: {recall:.2%}")
        print(f"    F1 Score: {f1:.3f}")
        print(f"    NNS: {nns:.1f}")

    # 2. Screening efficiency
    print("\n" + "-" * 70)
    print("2. SCREENING EFFICIENCY ANALYSIS")
    print("-" * 40)

    ranked = analyzer.compare_screening_burden(strategies)
    print("\n  Strategies ranked by screening efficiency (NNS):\n")
    print(f"  {'Rank':<5} {'Strategy':<10} {'NNS':>8} {'Precision':>10}")
    print(f"  {'-' * 35}")

    for r in ranked:
        print(f"  {r['rank']:<5} {r['strategy_id']:<10} {r['nns']:>8.1f} {r['precision']:>10.2%}")

    # Time estimates
    print("\n  Estimated screening time (2 min/abstract):")
    for r in ranked:
        nns_value = r.get('nns', float('inf'))
        hours = analyzer.estimate_screening_time(nns_value)
        print(f"    {r['strategy_id']}: {hours:.1f} hours per relevant study found")

    # Workload reduction
    print("\n  Workload reduction vs S1 (baseline):")
    baseline = strategies[0].total_retrieved
    for strat in strategies[1:]:
        reduction = analyzer.calculate_workload_reduction(baseline, strat.total_retrieved)
        print(f"    {strat.strategy_id}: {reduction:.1f}% fewer records to screen")

    # 3. Full validation metrics
    print("\n" + "-" * 70)
    print("3. FULL DIAGNOSTIC METRICS (S3 Example)")
    print("-" * 40)

    # For S3: TP=45, FP=255, FN=5, TN estimated from database size
    total_db = 10000  # Hypothetical database size
    tp, fp, fn = 45, 255, 5
    tn = total_db - tp - fp - fn

    full_metrics = validator.full_metrics(tp, fp, fn, tn)

    print("\n  Confusion Matrix:")
    print(f"    True Positives:  {tp:,}")
    print(f"    False Positives: {fp:,}")
    print(f"    False Negatives: {fn}")
    print(f"    True Negatives:  {tn:,}")

    print("\n  Diagnostic Metrics:")
    print(f"    Sensitivity:  {full_metrics['sensitivity']:.4f}")
    print(f"    Specificity:  {full_metrics['specificity']:.4f}")
    print(f"    Precision:    {full_metrics['precision']:.4f}")
    print(f"    NPV:          {full_metrics['npv']:.4f}")
    print(f"    F1 Score:     {full_metrics['f1_score']:.4f}")
    print(f"    Accuracy:     {full_metrics['accuracy']:.4f}")

    print("\n  Likelihood Ratios:")
    print(f"    LR+: {full_metrics['lr_positive']:.2f}")
    print(f"    LR-: {full_metrics['lr_negative']:.4f}")
    print(f"    DOR: {full_metrics['dor']:.2f}")

    # 4. Generate report
    print("\n" + "-" * 70)
    print("4. GENERATING MARKDOWN REPORT")
    print("-" * 40)

    report = generate_precision_report(
        condition="heart failure",
        strategies_results=strategies,
        known_ncts=known_relevant,
        total_database_size=total_db
    )

    print("\n  Report preview (first 30 lines):")
    for i, line in enumerate(report.split('\n')[:30]):
        print(f"  {line}")
    print("  ...")

    # 5. ROC data
    print("\n" + "-" * 70)
    print("5. ROC CURVE DATA")
    print("-" * 40)

    roc_data = create_roc_data(strategies, known_relevant, total_db)

    print("\n  ROC Points (for plotting):")
    print(f"  {'Strategy':<25} {'FPR':>8} {'TPR':>8}")
    print(f"  {'-' * 43}")

    for point in roc_data['points']:
        strategy_name = point.get('strategy_name')
        strategy_id = point.get('strategy_id', '')
        name = (strategy_name if strategy_name else strategy_id)[:25]
        fpr_value = point.get('fpr', 0.0)
        tpr_value = point.get('tpr', 0.0)
        print(f"  {name:<25} {fpr_value:>8.4f} {tpr_value:>8.4f}")

    print("\n  AUC Estimates:")
    for strat_id, auc in roc_data['auc_estimates'].items():
        print(f"    {strat_id}: {auc:.3f}")

    print("\n" + "=" * 70)
    print("  Demo complete!")
    print("=" * 70)
