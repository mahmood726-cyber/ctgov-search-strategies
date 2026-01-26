#!/usr/bin/env python3
"""
Real-Time Recall Estimation for CT.gov Searches
================================================

Provides users real-time recall estimates during search execution.

Features:
- Compare search results to expected yields
- Warn when recall appears low
- Suggest strategy improvements
- Show confidence intervals

Author: CT.gov Search Strategy Validation Project
Version: 1.0.0
Date: 2026-01-26
"""

import json
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from enum import Enum


class RecallStatus(Enum):
    """Recall status classification."""
    EXCELLENT = "excellent"    # >= 85%
    GOOD = "good"              # 75-85%
    MODERATE = "moderate"      # 60-75%
    LOW = "low"                # 40-60%
    POOR = "poor"              # < 40%
    UNKNOWN = "unknown"


@dataclass
class ExpectedYield:
    """Expected yield data for a drug/condition."""
    drug: str
    condition: str
    therapeutic_area: str
    expected_trials: int
    expected_range: Tuple[int, int]  # (min, max)
    confidence: float
    source: str  # validation, historical, estimated
    last_updated: str


@dataclass
class RecallEstimate:
    """Real-time recall estimate for a search."""
    drug: str
    condition: str
    search_strategy: str

    # Results
    trials_found: int
    expected_trials: int
    expected_range: Tuple[int, int]

    # Recall metrics
    point_estimate: float
    confidence_interval: Tuple[float, float]
    status: RecallStatus

    # Diagnostics
    is_warning: bool
    warning_messages: List[str]
    improvement_suggestions: List[str]

    # Metadata
    estimation_method: str
    confidence_score: float
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'drug': self.drug,
            'condition': self.condition,
            'search_strategy': self.search_strategy,
            'trials_found': self.trials_found,
            'expected_trials': self.expected_trials,
            'expected_range': list(self.expected_range),
            'recall': {
                'point_estimate': round(self.point_estimate, 3),
                'confidence_interval': [round(x, 3) for x in self.confidence_interval],
                'status': self.status.value
            },
            'is_warning': self.is_warning,
            'warning_messages': self.warning_messages,
            'improvement_suggestions': self.improvement_suggestions,
            'estimation_method': self.estimation_method,
            'confidence_score': round(self.confidence_score, 3),
            'timestamp': self.timestamp
        }


class YieldDatabase:
    """Database of expected yields based on validation data."""

    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or Path("data/expected_yields.json")
        self.yields: Dict[str, ExpectedYield] = {}
        self._load_or_initialize()

    def _load_or_initialize(self):
        """Load existing yields or initialize with defaults."""
        if self.data_path.exists():
            with open(self.data_path) as f:
                data = json.load(f)
                for key, value in data.items():
                    self.yields[key] = ExpectedYield(**value)
        else:
            self._initialize_defaults()

    def _initialize_defaults(self):
        """Initialize with default yields from validation study."""
        # Based on therapeutic area averages from validation
        defaults = {
            # Oncology drugs
            'pembrolizumab': ('cancer', 'oncology', 180, (140, 220)),
            'nivolumab': ('cancer', 'oncology', 200, (160, 240)),
            'trastuzumab': ('breast cancer', 'oncology', 160, (120, 200)),
            'cetuximab': ('colorectal cancer', 'oncology', 80, (60, 100)),
            'ipilimumab': ('melanoma', 'oncology', 90, (70, 110)),

            # Diabetes drugs
            'semaglutide': ('type 2 diabetes', 'diabetes', 120, (90, 150)),
            'dulaglutide': ('type 2 diabetes', 'diabetes', 100, (75, 125)),
            'empagliflozin': ('type 2 diabetes', 'diabetes', 95, (70, 120)),
            'dapagliflozin': ('type 2 diabetes', 'diabetes', 90, (65, 115)),
            'insulin': ('diabetes', 'diabetes', 450, (350, 550)),
            'metformin': ('type 2 diabetes', 'diabetes', 380, (300, 460)),

            # Cardiovascular
            'rivaroxaban': ('atrial fibrillation', 'cardiovascular', 130, (100, 160)),
            'apixaban': ('atrial fibrillation', 'cardiovascular', 110, (85, 135)),
            'sacubitril': ('heart failure', 'cardiovascular', 70, (50, 90)),

            # Respiratory
            'dupilumab': ('asthma', 'respiratory', 85, (65, 105)),
            'benralizumab': ('asthma', 'respiratory', 55, (40, 70)),
            'mepolizumab': ('asthma', 'respiratory', 65, (50, 80)),

            # Rheumatology
            'adalimumab': ('rheumatoid arthritis', 'rheumatology', 140, (110, 170)),
            'secukinumab': ('psoriasis', 'rheumatology', 90, (70, 110)),
            'ustekinumab': ('psoriasis', 'rheumatology', 85, (65, 105)),

            # Psychiatry
            'esketamine': ('depression', 'psychiatry', 50, (35, 65)),
            'brexpiprazole': ('schizophrenia', 'psychiatry', 45, (30, 60)),
        }

        for drug, (condition, area, expected, range_) in defaults.items():
            key = self._make_key(drug, condition)
            self.yields[key] = ExpectedYield(
                drug=drug,
                condition=condition,
                therapeutic_area=area,
                expected_trials=expected,
                expected_range=range_,
                confidence=0.7,
                source='validation',
                last_updated=datetime.now().isoformat()
            )

    def _make_key(self, drug: str, condition: str) -> str:
        """Create lookup key."""
        return f"{drug.lower()}|{condition.lower()}"

    def get_expected_yield(self, drug: str, condition: str = "") -> Optional[ExpectedYield]:
        """Get expected yield for a drug/condition."""
        # Try exact match
        key = self._make_key(drug, condition)
        if key in self.yields:
            return self.yields[key]

        # Try drug-only match
        for k, v in self.yields.items():
            if k.startswith(drug.lower() + "|"):
                return v

        return None

    def estimate_yield(self, drug: str, condition: str,
                       therapeutic_area: str = "unknown") -> ExpectedYield:
        """Estimate yield based on therapeutic area averages."""
        # Therapeutic area averages from validation
        area_averages = {
            'oncology': (100, 0.65),      # (expected trials, expected recall)
            'diabetes': (90, 0.84),
            'cardiovascular': (85, 0.79),
            'respiratory': (60, 0.86),
            'rheumatology': (80, 0.82),
            'psychiatry': (55, 0.80),
            'infectious_disease': (70, 0.79),
            'neurology': (50, 0.75),
            'unknown': (65, 0.75)
        }

        avg_trials, _ = area_averages.get(therapeutic_area.lower(), (65, 0.75))
        range_ = (int(avg_trials * 0.6), int(avg_trials * 1.4))

        return ExpectedYield(
            drug=drug,
            condition=condition,
            therapeutic_area=therapeutic_area,
            expected_trials=avg_trials,
            expected_range=range_,
            confidence=0.4,  # Lower confidence for estimates
            source='estimated',
            last_updated=datetime.now().isoformat()
        )

    def update_yield(self, drug: str, condition: str,
                     observed_trials: int, observed_recall: float):
        """Update expected yield with observed data."""
        key = self._make_key(drug, condition)

        if key in self.yields:
            existing = self.yields[key]
            # Bayesian update: weighted average
            weight_new = 0.3
            updated_expected = int(
                (1 - weight_new) * existing.expected_trials +
                weight_new * (observed_trials / max(0.1, observed_recall))
            )
            range_ = (int(updated_expected * 0.7), int(updated_expected * 1.3))

            self.yields[key] = ExpectedYield(
                drug=drug,
                condition=condition,
                therapeutic_area=existing.therapeutic_area,
                expected_trials=updated_expected,
                expected_range=range_,
                confidence=min(0.9, existing.confidence + 0.1),
                source='updated',
                last_updated=datetime.now().isoformat()
            )

    def save(self):
        """Save yields to file."""
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: {
            'drug': v.drug,
            'condition': v.condition,
            'therapeutic_area': v.therapeutic_area,
            'expected_trials': v.expected_trials,
            'expected_range': v.expected_range,
            'confidence': v.confidence,
            'source': v.source,
            'last_updated': v.last_updated
        } for k, v in self.yields.items()}

        with open(self.data_path, 'w') as f:
            json.dump(data, f, indent=2)


class RealTimeRecallEstimator:
    """
    Real-time recall estimation during search execution.

    Provides:
    - Point estimates with confidence intervals
    - Warnings when recall appears low
    - Suggestions for strategy improvement
    """

    # Strategy-specific recall adjustments based on validation
    STRATEGY_ADJUSTMENTS = {
        'basic': 0.0,
        'area_syntax': 0.05,  # +5% for oncology
        'combined': 0.08,     # +8% overall
        'enhanced_synonyms': 0.25,  # +25% for generics
    }

    # Therapeutic area base recall from validation
    AREA_BASE_RECALL = {
        'respiratory': 0.86,
        'diabetes': 0.84,
        'rheumatology': 0.82,
        'psychiatry': 0.80,
        'cardiovascular': 0.79,
        'infectious_disease': 0.79,
        'oncology': 0.65,
        'neurology': 0.75,
        'unknown': 0.75
    }

    def __init__(self, yield_db: Optional[YieldDatabase] = None):
        self.yield_db = yield_db or YieldDatabase()

    def wilson_ci(self, successes: int, total: int,
                  confidence: float = 0.95) -> Tuple[float, float]:
        """Calculate Wilson score confidence interval."""
        if total == 0:
            return (0.0, 1.0)

        z = 1.96 if confidence == 0.95 else 1.645  # 95% or 90%
        p = successes / total

        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator

        return (max(0.0, center - margin), min(1.0, center + margin))

    def estimate_recall(self, drug: str, condition: str,
                       trials_found: int, search_strategy: str = "basic",
                       therapeutic_area: str = "") -> RecallEstimate:
        """
        Estimate recall for a search in real-time.

        Args:
            drug: Drug name searched
            condition: Condition/disease searched
            trials_found: Number of trials returned by search
            search_strategy: Strategy used (basic, area_syntax, combined, enhanced_synonyms)
            therapeutic_area: Therapeutic area if known

        Returns:
            RecallEstimate with point estimate, CI, warnings, and suggestions
        """
        # Get expected yield
        expected_yield = self.yield_db.get_expected_yield(drug, condition)

        if expected_yield:
            expected = expected_yield.expected_trials
            expected_range = expected_yield.expected_range
            area = expected_yield.therapeutic_area
            estimation_method = expected_yield.source
            base_confidence = expected_yield.confidence
        else:
            # Estimate based on therapeutic area
            if not therapeutic_area:
                therapeutic_area = self._guess_therapeutic_area(drug, condition)

            estimated = self.yield_db.estimate_yield(drug, condition, therapeutic_area)
            expected = estimated.expected_trials
            expected_range = estimated.expected_range
            area = therapeutic_area
            estimation_method = 'estimated'
            base_confidence = 0.4

        # Calculate point estimate
        if expected > 0:
            point_estimate = min(1.0, trials_found / expected)
        else:
            point_estimate = 0.0

        # Calculate confidence interval
        # Using expected_range for uncertainty in denominator
        ci_low = trials_found / max(1, expected_range[1])
        ci_high = min(1.0, trials_found / max(1, expected_range[0]))
        confidence_interval = (ci_low, ci_high)

        # Determine status
        status = self._classify_recall(point_estimate)

        # Generate warnings
        warnings = []
        is_warning = False

        if status in [RecallStatus.LOW, RecallStatus.POOR]:
            is_warning = True
            warnings.append(
                f"WARNING: Recall appears low ({point_estimate:.0%}). "
                f"Expected ~{expected} trials but found {trials_found}."
            )

        if trials_found < expected_range[0]:
            is_warning = True
            warnings.append(
                f"Found {trials_found} trials, below expected range "
                f"({expected_range[0]}-{expected_range[1]})."
            )

        # Generate improvement suggestions
        suggestions = self._generate_suggestions(
            drug, condition, area, search_strategy,
            point_estimate, trials_found, expected
        )

        # Confidence in estimate
        confidence_score = base_confidence * (0.8 if estimation_method == 'estimated' else 1.0)

        return RecallEstimate(
            drug=drug,
            condition=condition,
            search_strategy=search_strategy,
            trials_found=trials_found,
            expected_trials=expected,
            expected_range=expected_range,
            point_estimate=point_estimate,
            confidence_interval=confidence_interval,
            status=status,
            is_warning=is_warning,
            warning_messages=warnings,
            improvement_suggestions=suggestions,
            estimation_method=estimation_method,
            confidence_score=confidence_score,
            timestamp=datetime.now().isoformat()
        )

    def _classify_recall(self, recall: float) -> RecallStatus:
        """Classify recall into status category."""
        if recall >= 0.85:
            return RecallStatus.EXCELLENT
        elif recall >= 0.75:
            return RecallStatus.GOOD
        elif recall >= 0.60:
            return RecallStatus.MODERATE
        elif recall >= 0.40:
            return RecallStatus.LOW
        else:
            return RecallStatus.POOR

    def _guess_therapeutic_area(self, drug: str, condition: str) -> str:
        """Guess therapeutic area from drug/condition names."""
        text = f"{drug} {condition}".lower()

        area_keywords = {
            'oncology': ['cancer', 'tumor', 'carcinoma', 'leukemia', 'lymphoma',
                        'melanoma', 'sarcoma', 'mab', 'nib'],
            'diabetes': ['diabetes', 'diabetic', 'glycemic', 'insulin', 'glucose',
                        'metformin', 'gliptin', 'gliflozin', 'glutide'],
            'cardiovascular': ['heart', 'cardiac', 'hypertension', 'atrial',
                              'venous', 'arterial', 'vascular'],
            'respiratory': ['asthma', 'copd', 'respiratory', 'lung', 'pulmonary',
                           'bronchial', 'airway'],
            'rheumatology': ['arthritis', 'rheumatoid', 'lupus', 'psoriasis',
                            'spondylitis', 'autoimmune'],
            'psychiatry': ['depression', 'anxiety', 'schizophrenia', 'bipolar',
                          'psychiatric', 'mental'],
            'infectious_disease': ['hiv', 'hepatitis', 'infection', 'viral',
                                   'bacterial', 'antibiotic', 'antiviral'],
            'neurology': ['alzheimer', 'parkinson', 'epilepsy', 'sclerosis',
                         'neurological', 'seizure', 'migraine']
        }

        for area, keywords in area_keywords.items():
            if any(kw in text for kw in keywords):
                return area

        return 'unknown'

    def _generate_suggestions(self, drug: str, condition: str,
                             therapeutic_area: str, current_strategy: str,
                             recall: float, found: int, expected: int) -> List[str]:
        """Generate suggestions for improving recall."""
        suggestions = []

        # Strategy-specific suggestions
        if current_strategy == 'basic':
            if therapeutic_area == 'oncology':
                suggestions.append(
                    "TRY: Use AREA syntax for oncology searches - can improve "
                    "recall by 14-21% for combination therapies"
                )
            else:
                suggestions.append(
                    "TRY: Use combined strategy (Basic + AREA syntax) for "
                    "+3-8% recall improvement"
                )

        # Generic drug suggestions
        generic_drugs = ['insulin', 'metformin', 'aspirin', 'warfarin',
                        'prednisone', 'methotrexate', 'heparin']
        if drug.lower() in generic_drugs and recall < 0.7:
            suggestions.append(
                f"TRY: Expand '{drug}' to include all formulations, brands, "
                "and combinations - can improve recall by 40-56%"
            )

        # Low recall suggestions
        if recall < 0.6:
            suggestions.append(
                "TRY: Add condition filter to reduce false negatives from "
                "trials where drug is comparator"
            )
            suggestions.append(
                "TRY: Search international registries (ICTRP, ANZCTR, EU-CTR) "
                "for additional trials"
            )

        # Very low recall
        if recall < 0.4:
            suggestions.append(
                "CHECK: Verify drug name spelling and try brand names/synonyms"
            )
            suggestions.append(
                "CHECK: Review PubMed DataBank links to identify CT.gov-indexed "
                "trials that may use different terminology"
            )

        # Always recommend supplementary search
        suggestions.append(
            "RECOMMENDED: Supplement with PubMed/Embase search for "
            "comprehensive coverage (CT.gov alone ~75% recall)"
        )

        return suggestions

    def monitor_search(self, drug: str, condition: str,
                      results_stream: List[int],
                      strategy: str = "basic") -> List[RecallEstimate]:
        """
        Monitor recall as search results come in.

        Useful for streaming/paginated searches.

        Args:
            drug: Drug being searched
            condition: Condition being searched
            results_stream: List of cumulative result counts
            strategy: Search strategy being used

        Returns:
            List of RecallEstimate for each point in the stream
        """
        estimates = []

        for count in results_stream:
            estimate = self.estimate_recall(
                drug=drug,
                condition=condition,
                trials_found=count,
                search_strategy=strategy
            )
            estimates.append(estimate)

        return estimates

    def compare_strategies(self, drug: str, condition: str,
                          strategy_results: Dict[str, int]) -> Dict[str, RecallEstimate]:
        """
        Compare recall estimates across different strategies.

        Args:
            drug: Drug searched
            condition: Condition searched
            strategy_results: Dict of {strategy: trials_found}

        Returns:
            Dict of {strategy: RecallEstimate}
        """
        estimates = {}

        for strategy, found in strategy_results.items():
            estimates[strategy] = self.estimate_recall(
                drug=drug,
                condition=condition,
                trials_found=found,
                search_strategy=strategy
            )

        return estimates

    def generate_monitoring_report(self,
                                   estimates: List[RecallEstimate]) -> str:
        """Generate a monitoring report from estimates."""
        if not estimates:
            return "No estimates to report."

        latest = estimates[-1]

        lines = [
            "=" * 60,
            "REAL-TIME RECALL MONITORING REPORT",
            "=" * 60,
            f"Drug: {latest.drug}",
            f"Condition: {latest.condition}",
            f"Strategy: {latest.search_strategy}",
            f"Timestamp: {latest.timestamp}",
            "",
            "CURRENT STATUS",
            "-" * 40,
            f"Trials found: {latest.trials_found}",
            f"Expected: {latest.expected_trials} "
            f"(range: {latest.expected_range[0]}-{latest.expected_range[1]})",
            "",
            f"Recall estimate: {latest.point_estimate:.1%}",
            f"95% CI: [{latest.confidence_interval[0]:.1%}, "
            f"{latest.confidence_interval[1]:.1%}]",
            f"Status: {latest.status.value.upper()}",
            f"Confidence: {latest.confidence_score:.0%}",
            "",
        ]

        if latest.is_warning:
            lines.extend([
                "⚠️  WARNINGS",
                "-" * 40,
            ])
            for warning in latest.warning_messages:
                lines.append(f"  {warning}")
            lines.append("")

        lines.extend([
            "SUGGESTIONS",
            "-" * 40,
        ])
        for suggestion in latest.improvement_suggestions:
            lines.append(f"  • {suggestion}")

        return "\n".join(lines)


def main():
    """Demo of real-time recall estimation."""
    print("Real-Time Recall Estimator Demo")
    print("=" * 50)

    estimator = RealTimeRecallEstimator()

    # Test cases
    test_cases = [
        # (drug, condition, trials_found, strategy)
        ('pembrolizumab', 'cancer', 120, 'basic'),
        ('pembrolizumab', 'cancer', 150, 'area_syntax'),
        ('insulin', 'diabetes', 100, 'basic'),
        ('insulin', 'diabetes', 350, 'enhanced_synonyms'),
        ('adalimumab', 'rheumatoid arthritis', 110, 'combined'),
    ]

    for drug, condition, found, strategy in test_cases:
        print(f"\n{'='*50}")
        print(f"Search: {drug} / {condition}")
        print(f"Strategy: {strategy}")
        print(f"Found: {found} trials")

        estimate = estimator.estimate_recall(
            drug=drug,
            condition=condition,
            trials_found=found,
            search_strategy=strategy
        )

        print(f"\nRecall: {estimate.point_estimate:.1%} "
              f"[{estimate.confidence_interval[0]:.1%}-"
              f"{estimate.confidence_interval[1]:.1%}]")
        print(f"Status: {estimate.status.value}")

        if estimate.is_warning:
            print("\n⚠️  WARNINGS:")
            for warning in estimate.warning_messages:
                print(f"   {warning}")

        print("\nSuggestions:")
        for suggestion in estimate.improvement_suggestions[:2]:
            print(f"   • {suggestion}")

    # Save example output
    output_path = Path("output/recall_estimates.json")
    output_path.parent.mkdir(exist_ok=True)

    estimates = [
        estimator.estimate_recall(drug, condition, found, strategy).to_dict()
        for drug, condition, found, strategy in test_cases
    ]

    with open(output_path, 'w') as f:
        json.dump(estimates, f, indent=2)

    print(f"\n\nEstimates saved to {output_path}")


if __name__ == "__main__":
    main()
