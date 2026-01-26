#!/usr/bin/env python3
"""
Prospective Cochrane Validation Framework
==========================================

Framework for partnering with Cochrane review teams for prospective validation.

Protocol:
1. Obtain PICO at protocol stage (before searching)
2. Run our strategies blindly
3. Compare to final included studies
4. Publish joint validation paper

Target: 10-20 prospective reviews across diverse topics

Author: CT.gov Search Strategy Validation Project
Version: 1.0.0
Date: 2026-01-26
"""

import json
import hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime, date
from enum import Enum
import uuid


class ReviewStatus(Enum):
    """Status of a prospective review."""
    REGISTERED = "registered"           # PICO received, not yet searched
    SEARCH_COMPLETE = "search_complete" # Our search executed
    REVIEW_ONGOING = "review_ongoing"   # Cochrane team screening
    REVIEW_COMPLETE = "review_complete" # Final included studies available
    VALIDATED = "validated"             # Validation analysis complete


class TherapeuticDomain(Enum):
    """Cochrane review groups / domains."""
    BREAST_CANCER = "breast_cancer"
    COLORECTAL_CANCER = "colorectal_cancer"
    LUNG_CANCER = "lung_cancer"
    HAEMATOLOGY = "haematology"
    DIABETES = "diabetes"
    CARDIOVASCULAR = "cardiovascular"
    HYPERTENSION = "hypertension"
    KIDNEY_TRANSPLANT = "kidney_transplant"
    RHEUMATOLOGY = "rheumatology"
    RESPIRATORY = "respiratory"
    MENTAL_HEALTH = "mental_health"
    INFECTIOUS_DISEASE = "infectious_disease"
    NEUROLOGY = "neurology"
    PAIN = "pain"
    HEPATOBILIARY = "hepatobiliary"
    OTHER = "other"


@dataclass
class PICOExtract:
    """PICO elements extracted from Cochrane protocol."""
    population: str
    intervention: str
    comparator: str
    outcomes: List[str]

    # Additional details
    intervention_drugs: List[str]
    intervention_classes: List[str]
    condition_terms: List[str]

    # Search parameters
    date_restrictions: Optional[str]
    study_design_filter: str  # RCT, controlled trials, etc.

    def to_dict(self) -> Dict[str, Any]:
        return {
            'population': self.population,
            'intervention': self.intervention,
            'comparator': self.comparator,
            'outcomes': self.outcomes,
            'intervention_drugs': self.intervention_drugs,
            'intervention_classes': self.intervention_classes,
            'condition_terms': self.condition_terms,
            'date_restrictions': self.date_restrictions,
            'study_design_filter': self.study_design_filter
        }


@dataclass
class BlindSearchResult:
    """Results of our blind search before seeing Cochrane results."""
    search_id: str
    timestamp: str
    strategy_used: str

    # Results
    nct_ids_found: Set[str]
    total_trials: int

    # Search parameters
    api_query: str
    filters_applied: Dict[str, str]

    # Audit
    api_version: str
    response_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'search_id': self.search_id,
            'timestamp': self.timestamp,
            'strategy_used': self.strategy_used,
            'nct_ids_found': list(self.nct_ids_found),
            'total_trials': self.total_trials,
            'api_query': self.api_query,
            'filters_applied': self.filters_applied,
            'api_version': self.api_version,
            'response_hash': self.response_hash
        }


@dataclass
class CochraneIncludedStudies:
    """Final included studies from Cochrane review."""
    review_doi: str
    review_title: str
    publication_date: str

    # Included studies
    included_nct_ids: Set[str]
    included_non_nct: List[str]  # Studies without NCT IDs
    total_included: int

    # Exclusion tracking
    excluded_nct_ids: Set[str]
    exclusion_reasons: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'review_doi': self.review_doi,
            'review_title': self.review_title,
            'publication_date': self.publication_date,
            'included_nct_ids': list(self.included_nct_ids),
            'included_non_nct': self.included_non_nct,
            'total_included': self.total_included,
            'excluded_nct_ids': list(self.excluded_nct_ids),
            'exclusion_reasons': self.exclusion_reasons
        }


@dataclass
class ValidationMetrics:
    """Validation metrics for a single review."""
    # Core metrics
    recall: float  # TP / (TP + FN)
    precision: float  # TP / (TP + FP)
    f1_score: float
    nns: float  # Number needed to screen

    # Confidence intervals (Wilson score)
    recall_ci: Tuple[float, float]
    precision_ci: Tuple[float, float]

    # Counts
    true_positives: int
    false_positives: int
    false_negatives: int

    # Details
    missed_studies: List[str]  # NCT IDs we missed
    correctly_found: List[str]  # NCT IDs correctly identified

    def to_dict(self) -> Dict[str, Any]:
        return {
            'recall': round(self.recall, 4),
            'precision': round(self.precision, 4),
            'f1_score': round(self.f1_score, 4),
            'nns': round(self.nns, 2),
            'recall_ci': [round(x, 4) for x in self.recall_ci],
            'precision_ci': [round(x, 4) for x in self.precision_ci],
            'true_positives': self.true_positives,
            'false_positives': self.false_positives,
            'false_negatives': self.false_negatives,
            'missed_studies': self.missed_studies,
            'correctly_found': self.correctly_found
        }


@dataclass
class ProspectiveReview:
    """A single prospective validation review."""
    review_id: str
    cochrane_protocol_doi: str
    cochrane_review_group: str
    therapeutic_domain: TherapeuticDomain

    # PICO
    pico: PICOExtract

    # Timeline
    registration_date: str
    search_date: Optional[str]
    review_completion_date: Optional[str]
    validation_date: Optional[str]

    # Status
    status: ReviewStatus

    # Results
    blind_search: Optional[BlindSearchResult]
    cochrane_included: Optional[CochraneIncludedStudies]
    validation_metrics: Optional[ValidationMetrics]

    # Notes
    notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'review_id': self.review_id,
            'cochrane_protocol_doi': self.cochrane_protocol_doi,
            'cochrane_review_group': self.cochrane_review_group,
            'therapeutic_domain': self.therapeutic_domain.value,
            'pico': self.pico.to_dict() if self.pico else None,
            'registration_date': self.registration_date,
            'search_date': self.search_date,
            'review_completion_date': self.review_completion_date,
            'validation_date': self.validation_date,
            'status': self.status.value,
            'blind_search': self.blind_search.to_dict() if self.blind_search else None,
            'cochrane_included': self.cochrane_included.to_dict() if self.cochrane_included else None,
            'validation_metrics': self.validation_metrics.to_dict() if self.validation_metrics else None,
            'notes': self.notes
        }


class ProspectiveValidationFramework:
    """
    Framework for prospective validation with Cochrane review teams.

    Workflow:
    1. Register review: Receive PICO from Cochrane protocol
    2. Execute blind search: Run our strategies without seeing Cochrane results
    3. Archive results: Store timestamped, hashed search results
    4. Receive Cochrane results: Get final included studies after review completion
    5. Validate: Compare our results to Cochrane gold standard
    6. Report: Generate validation report
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/prospective_validation")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.reviews: Dict[str, ProspectiveReview] = {}
        self._load_reviews()

    def _load_reviews(self):
        """Load existing reviews from storage."""
        reviews_file = self.data_dir / "reviews.json"
        if reviews_file.exists():
            with open(reviews_file) as f:
                data = json.load(f)
                for review_id, review_data in data.items():
                    # Reconstruct review object
                    self.reviews[review_id] = self._deserialize_review(review_data)

    def _save_reviews(self):
        """Save reviews to storage."""
        data = {rid: r.to_dict() for rid, r in self.reviews.items()}
        with open(self.data_dir / "reviews.json", 'w') as f:
            json.dump(data, f, indent=2)

    def _deserialize_review(self, data: Dict) -> ProspectiveReview:
        """Deserialize review from JSON data."""
        pico = PICOExtract(**data['pico']) if data.get('pico') else None

        blind_search = None
        if data.get('blind_search'):
            bs = data['blind_search']
            blind_search = BlindSearchResult(
                search_id=bs['search_id'],
                timestamp=bs['timestamp'],
                strategy_used=bs['strategy_used'],
                nct_ids_found=set(bs['nct_ids_found']),
                total_trials=bs['total_trials'],
                api_query=bs['api_query'],
                filters_applied=bs['filters_applied'],
                api_version=bs['api_version'],
                response_hash=bs['response_hash']
            )

        cochrane_included = None
        if data.get('cochrane_included'):
            ci = data['cochrane_included']
            cochrane_included = CochraneIncludedStudies(
                review_doi=ci['review_doi'],
                review_title=ci['review_title'],
                publication_date=ci['publication_date'],
                included_nct_ids=set(ci['included_nct_ids']),
                included_non_nct=ci['included_non_nct'],
                total_included=ci['total_included'],
                excluded_nct_ids=set(ci['excluded_nct_ids']),
                exclusion_reasons=ci['exclusion_reasons']
            )

        validation_metrics = None
        if data.get('validation_metrics'):
            vm = data['validation_metrics']
            validation_metrics = ValidationMetrics(
                recall=vm['recall'],
                precision=vm['precision'],
                f1_score=vm['f1_score'],
                nns=vm['nns'],
                recall_ci=tuple(vm['recall_ci']),
                precision_ci=tuple(vm['precision_ci']),
                true_positives=vm['true_positives'],
                false_positives=vm['false_positives'],
                false_negatives=vm['false_negatives'],
                missed_studies=vm['missed_studies'],
                correctly_found=vm['correctly_found']
            )

        return ProspectiveReview(
            review_id=data['review_id'],
            cochrane_protocol_doi=data['cochrane_protocol_doi'],
            cochrane_review_group=data['cochrane_review_group'],
            therapeutic_domain=TherapeuticDomain(data['therapeutic_domain']),
            pico=pico,
            registration_date=data['registration_date'],
            search_date=data.get('search_date'),
            review_completion_date=data.get('review_completion_date'),
            validation_date=data.get('validation_date'),
            status=ReviewStatus(data['status']),
            blind_search=blind_search,
            cochrane_included=cochrane_included,
            validation_metrics=validation_metrics,
            notes=data.get('notes', [])
        )

    def register_review(self, protocol_doi: str, review_group: str,
                       domain: TherapeuticDomain, pico: PICOExtract) -> str:
        """
        Register a new prospective review.

        Args:
            protocol_doi: DOI of Cochrane protocol
            review_group: Cochrane review group name
            domain: Therapeutic domain
            pico: PICO elements extracted from protocol

        Returns:
            review_id: Unique identifier for tracking
        """
        review_id = f"PRV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        review = ProspectiveReview(
            review_id=review_id,
            cochrane_protocol_doi=protocol_doi,
            cochrane_review_group=review_group,
            therapeutic_domain=domain,
            pico=pico,
            registration_date=datetime.now().isoformat(),
            search_date=None,
            review_completion_date=None,
            validation_date=None,
            status=ReviewStatus.REGISTERED,
            blind_search=None,
            cochrane_included=None,
            validation_metrics=None,
            notes=[f"Registered on {datetime.now().date()}"]
        )

        self.reviews[review_id] = review
        self._save_reviews()

        return review_id

    def execute_blind_search(self, review_id: str,
                            nct_ids: Set[str], api_query: str,
                            strategy: str = "combined") -> BlindSearchResult:
        """
        Execute and record blind search results.

        This must be done BEFORE receiving Cochrane's final results.
        Results are timestamped and hashed for audit trail.
        """
        if review_id not in self.reviews:
            raise ValueError(f"Review {review_id} not found")

        review = self.reviews[review_id]
        if review.status != ReviewStatus.REGISTERED:
            raise ValueError(f"Review {review_id} already searched")

        # Create hash of results for audit
        results_str = json.dumps(sorted(nct_ids))
        response_hash = hashlib.sha256(results_str.encode()).hexdigest()

        blind_search = BlindSearchResult(
            search_id=f"BS-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now().isoformat(),
            strategy_used=strategy,
            nct_ids_found=nct_ids,
            total_trials=len(nct_ids),
            api_query=api_query,
            filters_applied={'study_type': 'interventional'},
            api_version='v2',
            response_hash=response_hash
        )

        review.blind_search = blind_search
        review.search_date = datetime.now().isoformat()
        review.status = ReviewStatus.SEARCH_COMPLETE
        review.notes.append(f"Blind search executed: {len(nct_ids)} trials found")

        # Archive the raw results
        archive_path = self.data_dir / "archives" / review_id
        archive_path.mkdir(parents=True, exist_ok=True)

        with open(archive_path / f"{blind_search.search_id}.json", 'w') as f:
            json.dump(blind_search.to_dict(), f, indent=2)

        self._save_reviews()
        return blind_search

    def record_cochrane_results(self, review_id: str,
                                review_doi: str, review_title: str,
                                included_nct_ids: Set[str],
                                included_non_nct: List[str] = None,
                                excluded_nct_ids: Set[str] = None,
                                exclusion_reasons: Dict[str, str] = None):
        """
        Record final included studies from Cochrane review.

        Called after Cochrane review is published.
        """
        if review_id not in self.reviews:
            raise ValueError(f"Review {review_id} not found")

        review = self.reviews[review_id]
        if review.status not in [ReviewStatus.SEARCH_COMPLETE, ReviewStatus.REVIEW_ONGOING]:
            raise ValueError(f"Review {review_id} not ready for Cochrane results")

        cochrane_results = CochraneIncludedStudies(
            review_doi=review_doi,
            review_title=review_title,
            publication_date=datetime.now().isoformat(),
            included_nct_ids=included_nct_ids,
            included_non_nct=included_non_nct or [],
            total_included=len(included_nct_ids) + len(included_non_nct or []),
            excluded_nct_ids=excluded_nct_ids or set(),
            exclusion_reasons=exclusion_reasons or {}
        )

        review.cochrane_included = cochrane_results
        review.review_completion_date = datetime.now().isoformat()
        review.status = ReviewStatus.REVIEW_COMPLETE
        review.notes.append(f"Cochrane results received: {len(included_nct_ids)} NCT-linked included")

        self._save_reviews()

    def validate(self, review_id: str) -> ValidationMetrics:
        """
        Perform validation analysis.

        Compares our blind search to Cochrane gold standard.
        """
        import math

        if review_id not in self.reviews:
            raise ValueError(f"Review {review_id} not found")

        review = self.reviews[review_id]
        if review.status != ReviewStatus.REVIEW_COMPLETE:
            raise ValueError(f"Review {review_id} not ready for validation")

        if not review.blind_search or not review.cochrane_included:
            raise ValueError(f"Review {review_id} missing search or Cochrane results")

        # Calculate metrics
        our_results = review.blind_search.nct_ids_found
        gold_standard = review.cochrane_included.included_nct_ids

        true_positives = our_results & gold_standard
        false_positives = our_results - gold_standard
        false_negatives = gold_standard - our_results

        tp = len(true_positives)
        fp = len(false_positives)
        fn = len(false_negatives)

        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        f1 = 2 * recall * precision / (recall + precision) if (recall + precision) > 0 else 0.0
        nns = 1 / precision if precision > 0 else float('inf')

        # Wilson score confidence intervals
        def wilson_ci(successes, total, z=1.96):
            if total == 0:
                return (0.0, 1.0)
            p = successes / total
            denom = 1 + z**2 / total
            center = (p + z**2 / (2 * total)) / denom
            margin = z * math.sqrt((p * (1-p) + z**2 / (4*total)) / total) / denom
            return (max(0, center - margin), min(1, center + margin))

        recall_ci = wilson_ci(tp, tp + fn)
        precision_ci = wilson_ci(tp, tp + fp)

        metrics = ValidationMetrics(
            recall=recall,
            precision=precision,
            f1_score=f1,
            nns=nns,
            recall_ci=recall_ci,
            precision_ci=precision_ci,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            missed_studies=list(false_negatives),
            correctly_found=list(true_positives)
        )

        review.validation_metrics = metrics
        review.validation_date = datetime.now().isoformat()
        review.status = ReviewStatus.VALIDATED
        review.notes.append(f"Validation complete: {recall:.1%} recall, {precision:.1%} precision")

        self._save_reviews()
        return metrics

    def get_summary_statistics(self) -> Dict[str, Any]:
        """Get summary statistics across all validated reviews."""
        validated = [r for r in self.reviews.values()
                     if r.status == ReviewStatus.VALIDATED]

        if not validated:
            return {'n_validated': 0, 'message': 'No validated reviews yet'}

        recalls = [r.validation_metrics.recall for r in validated]
        precisions = [r.validation_metrics.precision for r in validated]

        # By domain
        domain_recalls = {}
        for r in validated:
            domain = r.therapeutic_domain.value
            if domain not in domain_recalls:
                domain_recalls[domain] = []
            domain_recalls[domain].append(r.validation_metrics.recall)

        return {
            'n_registered': len(self.reviews),
            'n_validated': len(validated),
            'n_pending': len([r for r in self.reviews.values()
                            if r.status in [ReviewStatus.REGISTERED,
                                          ReviewStatus.SEARCH_COMPLETE,
                                          ReviewStatus.REVIEW_ONGOING]]),
            'overall_recall': {
                'mean': sum(recalls) / len(recalls),
                'min': min(recalls),
                'max': max(recalls),
                'median': sorted(recalls)[len(recalls)//2]
            },
            'overall_precision': {
                'mean': sum(precisions) / len(precisions),
                'min': min(precisions),
                'max': max(precisions)
            },
            'by_domain': {
                domain: {
                    'n': len(vals),
                    'mean_recall': sum(vals) / len(vals)
                }
                for domain, vals in domain_recalls.items()
            }
        }

    def generate_report(self, review_id: str) -> str:
        """Generate validation report for a single review."""
        if review_id not in self.reviews:
            return f"Review {review_id} not found"

        review = self.reviews[review_id]

        lines = [
            "=" * 70,
            "PROSPECTIVE VALIDATION REPORT",
            "=" * 70,
            f"Review ID: {review.review_id}",
            f"Protocol DOI: {review.cochrane_protocol_doi}",
            f"Review Group: {review.cochrane_review_group}",
            f"Therapeutic Domain: {review.therapeutic_domain.value}",
            f"Status: {review.status.value}",
            "",
            "TIMELINE",
            "-" * 40,
            f"Registered: {review.registration_date}",
            f"Search executed: {review.search_date or 'Pending'}",
            f"Review completed: {review.review_completion_date or 'Pending'}",
            f"Validated: {review.validation_date or 'Pending'}",
            "",
        ]

        if review.pico:
            lines.extend([
                "PICO ELEMENTS",
                "-" * 40,
                f"Population: {review.pico.population}",
                f"Intervention: {review.pico.intervention}",
                f"Comparator: {review.pico.comparator}",
                f"Drugs: {', '.join(review.pico.intervention_drugs)}",
                "",
            ])

        if review.blind_search:
            lines.extend([
                "OUR SEARCH (BLIND)",
                "-" * 40,
                f"Strategy: {review.blind_search.strategy_used}",
                f"Trials found: {review.blind_search.total_trials}",
                f"Search hash: {review.blind_search.response_hash[:16]}...",
                "",
            ])

        if review.cochrane_included:
            lines.extend([
                "COCHRANE RESULTS (GOLD STANDARD)",
                "-" * 40,
                f"Review DOI: {review.cochrane_included.review_doi}",
                f"NCT-linked included: {len(review.cochrane_included.included_nct_ids)}",
                f"Non-NCT included: {len(review.cochrane_included.included_non_nct)}",
                f"Total included: {review.cochrane_included.total_included}",
                "",
            ])

        if review.validation_metrics:
            vm = review.validation_metrics
            lines.extend([
                "VALIDATION RESULTS",
                "-" * 40,
                f"Recall: {vm.recall:.1%} (95% CI: {vm.recall_ci[0]:.1%}-{vm.recall_ci[1]:.1%})",
                f"Precision: {vm.precision:.1%} (95% CI: {vm.precision_ci[0]:.1%}-{vm.precision_ci[1]:.1%})",
                f"F1 Score: {vm.f1_score:.3f}",
                f"NNS: {vm.nns:.1f}",
                "",
                f"True Positives: {vm.true_positives}",
                f"False Positives: {vm.false_positives}",
                f"False Negatives: {vm.false_negatives}",
                "",
            ])

            if vm.missed_studies:
                lines.append("Missed studies (first 10):")
                for nct in vm.missed_studies[:10]:
                    lines.append(f"  - {nct}")
                if len(vm.missed_studies) > 10:
                    lines.append(f"  ... and {len(vm.missed_studies) - 10} more")

        lines.extend([
            "",
            "NOTES",
            "-" * 40,
        ])
        for note in review.notes:
            lines.append(f"  • {note}")

        return "\n".join(lines)

    def generate_master_report(self) -> str:
        """Generate master report across all reviews."""
        stats = self.get_summary_statistics()

        lines = [
            "=" * 70,
            "PROSPECTIVE VALIDATION MASTER REPORT",
            "=" * 70,
            f"Generated: {datetime.now().isoformat()}",
            "",
            "OVERVIEW",
            "-" * 40,
            f"Total registered: {stats['n_registered']}",
            f"Validated: {stats['n_validated']}",
            f"Pending: {stats['n_pending']}",
            "",
        ]

        if stats['n_validated'] > 0:
            lines.extend([
                "OVERALL PERFORMANCE",
                "-" * 40,
                f"Mean recall: {stats['overall_recall']['mean']:.1%}",
                f"Recall range: {stats['overall_recall']['min']:.1%} - {stats['overall_recall']['max']:.1%}",
                f"Mean precision: {stats['overall_precision']['mean']:.1%}",
                "",
                "BY THERAPEUTIC DOMAIN",
                "-" * 40,
            ])

            for domain, data in stats['by_domain'].items():
                lines.append(f"  {domain}: n={data['n']}, mean recall={data['mean_recall']:.1%}")

        lines.extend([
            "",
            "INDIVIDUAL REVIEWS",
            "-" * 40,
        ])

        for review_id, review in self.reviews.items():
            status_emoji = {
                ReviewStatus.REGISTERED: "📝",
                ReviewStatus.SEARCH_COMPLETE: "🔍",
                ReviewStatus.REVIEW_ONGOING: "⏳",
                ReviewStatus.REVIEW_COMPLETE: "📊",
                ReviewStatus.VALIDATED: "✅"
            }.get(review.status, "❓")

            recall_str = ""
            if review.validation_metrics:
                recall_str = f" | Recall: {review.validation_metrics.recall:.1%}"

            lines.append(f"  {status_emoji} {review_id}: {review.therapeutic_domain.value}{recall_str}")

        return "\n".join(lines)


def main():
    """Demo of prospective validation framework."""
    print("Prospective Cochrane Validation Framework Demo")
    print("=" * 50)

    framework = ProspectiveValidationFramework()

    # Example: Register a new review
    pico = PICOExtract(
        population="Adults with advanced non-small cell lung cancer",
        intervention="Pembrolizumab monotherapy or combination",
        comparator="Chemotherapy or placebo",
        outcomes=["Overall survival", "Progression-free survival", "Adverse events"],
        intervention_drugs=["pembrolizumab"],
        intervention_classes=["PD-1 inhibitor", "immune checkpoint inhibitor"],
        condition_terms=["non-small cell lung cancer", "NSCLC", "lung cancer"],
        date_restrictions=None,
        study_design_filter="RCT"
    )

    review_id = framework.register_review(
        protocol_doi="10.1002/14651858.CDxxxxxx",
        review_group="Cochrane Lung Cancer",
        domain=TherapeuticDomain.LUNG_CANCER,
        pico=pico
    )

    print(f"Registered review: {review_id}")

    # Simulate blind search
    mock_nct_ids = {f"NCT{i:08d}" for i in range(1000, 1150)}  # 150 trials found

    framework.execute_blind_search(
        review_id=review_id,
        nct_ids=mock_nct_ids,
        api_query='AREA[InterventionName]pembrolizumab',
        strategy='combined'
    )

    print("Blind search executed")

    # Simulate Cochrane results
    cochrane_included = {f"NCT{i:08d}" for i in range(1000, 1120)}  # 120 included
    cochrane_included.add("NCT00999999")  # One we missed

    framework.record_cochrane_results(
        review_id=review_id,
        review_doi="10.1002/14651858.CDxxxxxx.pub2",
        review_title="Pembrolizumab for advanced NSCLC",
        included_nct_ids=cochrane_included
    )

    print("Cochrane results recorded")

    # Validate
    metrics = framework.validate(review_id)
    print(f"\nValidation Results:")
    print(f"  Recall: {metrics.recall:.1%}")
    print(f"  Precision: {metrics.precision:.1%}")
    print(f"  Missed: {len(metrics.missed_studies)} studies")

    # Generate report
    report = framework.generate_report(review_id)
    print(f"\n{report}")

    # Save master report
    master_report = framework.generate_master_report()
    output_path = Path("output/prospective_validation_report.txt")
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w') as f:
        f.write(master_report)

    print(f"\nMaster report saved to {output_path}")


if __name__ == "__main__":
    main()
