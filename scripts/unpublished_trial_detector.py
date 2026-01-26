#!/usr/bin/env python3
"""
Unpublished Trial Detector
==========================

Identifies completed but unpublished clinical trials by comparing
registry records with publication databases.

Based on research showing:
- Only 13% of CT.gov trials have posted summary results
- 56% of systematic reviews miss potentially relevant registry-only trials
- Baudard et al. found 122 eligible trials in 47% of reviews that hadn't searched registries

Features:
- Registry completion status analysis
- PubMed/publication linkage checking
- Publication delay estimation
- Risk of publication bias flagging

Author: CT.gov Search Strategy Validation Project
Version: 1.0.0
Date: 2026-01-26
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict


class PublicationStatus(Enum):
    """Status of trial publication."""
    PUBLISHED = "published"           # Has linked publication(s)
    RESULTS_POSTED = "results_posted" # Results on registry only
    LIKELY_UNPUBLISHED = "likely_unpublished"  # Completed >2 years, no publications
    POSSIBLY_UNPUBLISHED = "possibly_unpublished"  # Completed 1-2 years
    TOO_RECENT = "too_recent"         # Completed <1 year
    ONGOING = "ongoing"               # Not yet completed
    UNKNOWN = "unknown"


class PublicationBiasRisk(Enum):
    """Risk level for publication bias."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class RegistryRecord:
    """A trial registry record for analysis."""
    nct_id: str
    title: str
    overall_status: str  # Completed, Recruiting, Terminated, etc.
    phase: Optional[str]
    enrollment: Optional[int]
    start_date: Optional[str]
    completion_date: Optional[str]  # Primary completion
    study_completion_date: Optional[str]  # Study completion
    sponsor: Optional[str]
    sponsor_type: Optional[str]  # Industry, NIH, Academic, etc.
    results_posted: bool
    results_date: Optional[str]
    has_publications: bool
    pubmed_ids: List[str]
    intervention: Optional[str]
    condition: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'nct_id': self.nct_id,
            'title': self.title,
            'overall_status': self.overall_status,
            'phase': self.phase,
            'enrollment': self.enrollment,
            'start_date': self.start_date,
            'completion_date': self.completion_date,
            'sponsor': self.sponsor,
            'sponsor_type': self.sponsor_type,
            'results_posted': self.results_posted,
            'has_publications': self.has_publications,
            'pubmed_ids': self.pubmed_ids
        }


@dataclass
class UnpublishedTrialAnalysis:
    """Analysis result for a single trial."""
    nct_id: str
    publication_status: PublicationStatus
    publication_bias_risk: PublicationBiasRisk

    # Time analysis
    days_since_completion: Optional[int]
    expected_publication_window: str  # e.g., "12-24 months"

    # Evidence
    has_registry_results: bool
    has_linked_publications: bool
    publication_count: int

    # Risk factors
    risk_factors: List[str]
    protective_factors: List[str]

    # Recommendations
    action_items: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'nct_id': self.nct_id,
            'publication_status': self.publication_status.value,
            'publication_bias_risk': self.publication_bias_risk.value,
            'days_since_completion': self.days_since_completion,
            'expected_publication_window': self.expected_publication_window,
            'has_registry_results': self.has_registry_results,
            'has_linked_publications': self.has_linked_publications,
            'publication_count': self.publication_count,
            'risk_factors': self.risk_factors,
            'protective_factors': self.protective_factors,
            'action_items': self.action_items
        }


@dataclass
class PublicationBiasReport:
    """Aggregate report on potential publication bias."""
    drug: str
    condition: str
    total_trials: int

    # Counts by status
    published: int
    results_only: int
    likely_unpublished: int
    possibly_unpublished: int
    too_recent: int
    ongoing: int

    # Risk assessment
    publication_rate: float
    estimated_missing_trials: int
    overall_bias_risk: PublicationBiasRisk

    # Detailed analyses
    trial_analyses: List[UnpublishedTrialAnalysis]

    # Recommendations
    systematic_review_implications: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'drug': self.drug,
            'condition': self.condition,
            'summary': {
                'total_trials': self.total_trials,
                'published': self.published,
                'results_only': self.results_only,
                'likely_unpublished': self.likely_unpublished,
                'possibly_unpublished': self.possibly_unpublished,
                'too_recent': self.too_recent,
                'ongoing': self.ongoing
            },
            'risk_assessment': {
                'publication_rate': round(self.publication_rate, 3),
                'estimated_missing_trials': self.estimated_missing_trials,
                'overall_bias_risk': self.overall_bias_risk.value
            },
            'implications': self.systematic_review_implications
        }


class UnpublishedTrialDetector:
    """
    Detector for unpublished clinical trials.

    Analyzes registry records to identify:
    1. Completed trials without publications
    2. Trials with registry results but no journal publication
    3. Long-delayed publications
    4. Potential publication bias patterns
    """

    # Publication timing thresholds (months)
    LIKELY_UNPUBLISHED_THRESHOLD = 24  # 2 years
    POSSIBLY_UNPUBLISHED_THRESHOLD = 12  # 1 year
    TOO_RECENT_THRESHOLD = 6  # 6 months

    # Expected publication windows by study type
    EXPECTED_WINDOWS = {
        'Phase 1': '18-36 months',
        'Phase 2': '18-30 months',
        'Phase 3': '12-24 months',
        'Phase 4': '12-24 months',
        'default': '12-24 months'
    }

    def __init__(self):
        self.today = datetime.now()

    def analyze_trial(self, record: RegistryRecord) -> UnpublishedTrialAnalysis:
        """Analyze a single trial for publication status."""
        # Determine basic publication status
        pub_status = self._determine_publication_status(record)

        # Calculate time since completion
        days_since = self._days_since_completion(record)

        # Assess risk factors
        risk_factors = self._identify_risk_factors(record, days_since)
        protective_factors = self._identify_protective_factors(record)

        # Determine overall publication bias risk
        bias_risk = self._assess_bias_risk(pub_status, risk_factors, protective_factors)

        # Generate action items
        action_items = self._generate_action_items(record, pub_status, bias_risk)

        # Get expected publication window
        expected_window = self.EXPECTED_WINDOWS.get(
            record.phase, self.EXPECTED_WINDOWS['default']
        )

        return UnpublishedTrialAnalysis(
            nct_id=record.nct_id,
            publication_status=pub_status,
            publication_bias_risk=bias_risk,
            days_since_completion=days_since,
            expected_publication_window=expected_window,
            has_registry_results=record.results_posted,
            has_linked_publications=record.has_publications,
            publication_count=len(record.pubmed_ids),
            risk_factors=risk_factors,
            protective_factors=protective_factors,
            action_items=action_items
        )

    def _determine_publication_status(self, record: RegistryRecord) -> PublicationStatus:
        """Determine the publication status of a trial."""
        # Check if has publications
        if record.has_publications and record.pubmed_ids:
            return PublicationStatus.PUBLISHED

        # Check if results posted on registry
        if record.results_posted:
            return PublicationStatus.RESULTS_POSTED

        # Check completion status
        if record.overall_status not in ['Completed', 'Terminated']:
            return PublicationStatus.ONGOING

        # Analyze time since completion
        days_since = self._days_since_completion(record)

        if days_since is None:
            return PublicationStatus.UNKNOWN

        months_since = days_since / 30

        if months_since < self.TOO_RECENT_THRESHOLD:
            return PublicationStatus.TOO_RECENT
        elif months_since < self.POSSIBLY_UNPUBLISHED_THRESHOLD:
            return PublicationStatus.POSSIBLY_UNPUBLISHED
        else:
            return PublicationStatus.LIKELY_UNPUBLISHED

    def _days_since_completion(self, record: RegistryRecord) -> Optional[int]:
        """Calculate days since trial completion."""
        completion_date = record.completion_date or record.study_completion_date

        if not completion_date:
            return None

        try:
            # Parse various date formats
            for fmt in ['%Y-%m-%d', '%Y-%m', '%B %Y', '%Y']:
                try:
                    completion = datetime.strptime(completion_date, fmt)
                    return (self.today - completion).days
                except ValueError:
                    continue

            return None
        except Exception:
            return None

    def _identify_risk_factors(self, record: RegistryRecord,
                              days_since: Optional[int]) -> List[str]:
        """Identify risk factors for non-publication."""
        risk_factors = []

        # Long delay
        if days_since and days_since > 365 * 2:
            risk_factors.append(f"Long delay: {days_since // 365} years since completion")

        # Small sample size
        if record.enrollment and record.enrollment < 50:
            risk_factors.append(f"Small sample size: n={record.enrollment}")

        # Early termination
        if record.overall_status == 'Terminated':
            risk_factors.append("Study was terminated early")

        # No results posted
        if not record.results_posted and days_since and days_since > 365:
            risk_factors.append("No results posted to registry >1 year post-completion")

        # Industry sponsor without results
        if record.sponsor_type == 'Industry' and not record.results_posted:
            if days_since and days_since > 365:
                risk_factors.append("Industry sponsor with delayed results posting")

        # Phase 1 (lower publication rates)
        if record.phase == 'Phase 1':
            risk_factors.append("Phase 1 studies have historically lower publication rates")

        return risk_factors

    def _identify_protective_factors(self, record: RegistryRecord) -> List[str]:
        """Identify factors that reduce non-publication risk."""
        protective = []

        # Results posted
        if record.results_posted:
            protective.append("Results posted to registry")

        # Large sample size
        if record.enrollment and record.enrollment > 500:
            protective.append(f"Large sample size: n={record.enrollment}")

        # Phase 3 (higher publication pressure)
        if record.phase == 'Phase 3':
            protective.append("Phase 3 trials have high publication rates")

        # NIH funded
        if record.sponsor_type == 'NIH':
            protective.append("NIH-funded (higher reporting requirements)")

        # Has linked publications
        if record.has_publications:
            protective.append(f"Has {len(record.pubmed_ids)} linked publication(s)")

        return protective

    def _assess_bias_risk(self, pub_status: PublicationStatus,
                         risk_factors: List[str],
                         protective_factors: List[str]) -> PublicationBiasRisk:
        """Assess overall publication bias risk."""
        if pub_status == PublicationStatus.PUBLISHED:
            return PublicationBiasRisk.LOW

        if pub_status == PublicationStatus.RESULTS_POSTED:
            return PublicationBiasRisk.LOW

        if pub_status in [PublicationStatus.TOO_RECENT, PublicationStatus.ONGOING]:
            return PublicationBiasRisk.LOW

        # Score based on factors
        risk_score = len(risk_factors)
        protective_score = len(protective_factors)

        net_risk = risk_score - protective_score

        if pub_status == PublicationStatus.LIKELY_UNPUBLISHED:
            if net_risk >= 3:
                return PublicationBiasRisk.VERY_HIGH
            elif net_risk >= 1:
                return PublicationBiasRisk.HIGH
            else:
                return PublicationBiasRisk.MODERATE

        if pub_status == PublicationStatus.POSSIBLY_UNPUBLISHED:
            if net_risk >= 2:
                return PublicationBiasRisk.MODERATE
            else:
                return PublicationBiasRisk.LOW

        return PublicationBiasRisk.MODERATE

    def _generate_action_items(self, record: RegistryRecord,
                              pub_status: PublicationStatus,
                              bias_risk: PublicationBiasRisk) -> List[str]:
        """Generate action items for systematic reviewers."""
        actions = []

        if pub_status == PublicationStatus.LIKELY_UNPUBLISHED:
            actions.append(f"Contact investigators for {record.nct_id} to request unpublished data")
            actions.append("Check conference proceedings for preliminary results")

            if record.results_posted:
                actions.append("Extract data from registry results if journal publication unavailable")

        elif pub_status == PublicationStatus.POSSIBLY_UNPUBLISHED:
            actions.append(f"Monitor {record.nct_id} for upcoming publication")
            actions.append("Set up PubMed alert for trial ID")

        elif pub_status == PublicationStatus.RESULTS_POSTED:
            actions.append("Assess whether registry results are sufficient for inclusion")
            actions.append("Document any differences between registry and published results")

        if bias_risk in [PublicationBiasRisk.HIGH, PublicationBiasRisk.VERY_HIGH]:
            actions.append("Flag for sensitivity analysis excluding this trial")
            actions.append("Document potential publication bias in systematic review")

        return actions

    def generate_bias_report(self, drug: str, condition: str,
                            records: List[RegistryRecord]) -> PublicationBiasReport:
        """Generate aggregate publication bias report."""
        analyses = [self.analyze_trial(r) for r in records]

        # Count by status
        status_counts = defaultdict(int)
        for analysis in analyses:
            status_counts[analysis.publication_status] += 1

        # Calculate metrics
        completed_trials = sum(1 for r in records
                              if r.overall_status in ['Completed', 'Terminated'])
        published = status_counts[PublicationStatus.PUBLISHED]

        publication_rate = published / max(1, completed_trials)

        # Estimate missing trials
        likely_missing = status_counts[PublicationStatus.LIKELY_UNPUBLISHED]
        possibly_missing = status_counts[PublicationStatus.POSSIBLY_UNPUBLISHED]
        estimated_missing = likely_missing + int(possibly_missing * 0.5)

        # Overall bias risk
        if publication_rate < 0.5 and likely_missing > 5:
            overall_risk = PublicationBiasRisk.VERY_HIGH
        elif publication_rate < 0.6 or likely_missing > 3:
            overall_risk = PublicationBiasRisk.HIGH
        elif publication_rate < 0.75 or likely_missing > 1:
            overall_risk = PublicationBiasRisk.MODERATE
        else:
            overall_risk = PublicationBiasRisk.LOW

        # Generate implications
        implications = self._generate_implications(
            publication_rate, likely_missing, overall_risk
        )

        return PublicationBiasReport(
            drug=drug,
            condition=condition,
            total_trials=len(records),
            published=published,
            results_only=status_counts[PublicationStatus.RESULTS_POSTED],
            likely_unpublished=likely_missing,
            possibly_unpublished=possibly_missing,
            too_recent=status_counts[PublicationStatus.TOO_RECENT],
            ongoing=status_counts[PublicationStatus.ONGOING],
            publication_rate=publication_rate,
            estimated_missing_trials=estimated_missing,
            overall_bias_risk=overall_risk,
            trial_analyses=analyses,
            systematic_review_implications=implications
        )

    def _generate_implications(self, pub_rate: float, likely_missing: int,
                              risk: PublicationBiasRisk) -> List[str]:
        """Generate implications for systematic review."""
        implications = []

        if risk == PublicationBiasRisk.VERY_HIGH:
            implications.append(
                "CRITICAL: Very high risk of publication bias. Results may overestimate "
                "treatment effects. Consider contacting trialists for unpublished data."
            )
        elif risk == PublicationBiasRisk.HIGH:
            implications.append(
                "HIGH RISK: Publication bias likely affects conclusions. Conduct "
                "sensitivity analyses excluding potentially biased trials."
            )
        elif risk == PublicationBiasRisk.MODERATE:
            implications.append(
                "MODERATE RISK: Some publication bias possible. Report this limitation "
                "and interpret results with caution."
            )
        else:
            implications.append(
                "LOW RISK: Most completed trials appear published. Publication bias "
                "unlikely to substantially affect conclusions."
            )

        if likely_missing > 0:
            implications.append(
                f"Approximately {likely_missing} completed trial(s) remain unpublished "
                f"after expected publication window."
            )

        if pub_rate < 0.7:
            implications.append(
                f"Publication rate ({pub_rate:.0%}) is below the 70% benchmark. "
                "Consider searching FDA/EMA databases for regulatory submissions."
            )

        implications.append(
            "RECOMMENDATION: Report this analysis in the Risk of Bias assessment "
            "per Cochrane Chapter 13 guidance."
        )

        return implications

    def format_report(self, report: PublicationBiasReport) -> str:
        """Format report as readable text."""
        lines = [
            "=" * 70,
            "UNPUBLISHED TRIAL DETECTION REPORT",
            "=" * 70,
            f"Drug: {report.drug}",
            f"Condition: {report.condition}",
            f"Analysis Date: {datetime.now().strftime('%Y-%m-%d')}",
            "",
            "SUMMARY",
            "-" * 50,
            f"Total trials analyzed: {report.total_trials}",
            f"  Published: {report.published}",
            f"  Results posted (registry only): {report.results_only}",
            f"  Likely unpublished: {report.likely_unpublished}",
            f"  Possibly unpublished: {report.possibly_unpublished}",
            f"  Too recent to assess: {report.too_recent}",
            f"  Ongoing: {report.ongoing}",
            "",
            f"Publication rate: {report.publication_rate:.1%}",
            f"Estimated missing trials: {report.estimated_missing_trials}",
            f"Overall bias risk: {report.overall_bias_risk.value.upper()}",
            "",
            "IMPLICATIONS FOR SYSTEMATIC REVIEW",
            "-" * 50,
        ]

        for impl in report.systematic_review_implications:
            lines.append(f"• {impl}")

        # High-risk trials
        high_risk_trials = [a for a in report.trial_analyses
                          if a.publication_bias_risk in
                          [PublicationBiasRisk.HIGH, PublicationBiasRisk.VERY_HIGH]]

        if high_risk_trials:
            lines.extend([
                "",
                "HIGH-RISK TRIALS REQUIRING ATTENTION",
                "-" * 50,
            ])
            for trial in high_risk_trials[:10]:
                lines.extend([
                    f"\n{trial.nct_id}",
                    f"  Status: {trial.publication_status.value}",
                    f"  Risk: {trial.publication_bias_risk.value}",
                    f"  Days since completion: {trial.days_since_completion or 'Unknown'}",
                ])
                if trial.action_items:
                    lines.append("  Actions:")
                    for action in trial.action_items[:2]:
                        lines.append(f"    - {action}")

        return "\n".join(lines)


def main():
    """Demo of unpublished trial detection."""
    print("Unpublished Trial Detector Demo")
    print("=" * 50)

    # Sample registry records
    records = [
        RegistryRecord(
            nct_id="NCT04000001",
            title="Semaglutide vs Placebo in Type 2 Diabetes",
            overall_status="Completed",
            phase="Phase 3",
            enrollment=500,
            start_date="2019-01-01",
            completion_date="2021-06-01",
            study_completion_date="2021-08-01",
            sponsor="Novo Nordisk",
            sponsor_type="Industry",
            results_posted=True,
            results_date="2022-01-15",
            has_publications=True,
            pubmed_ids=["35000001", "35000002"],
            intervention="semaglutide",
            condition="type 2 diabetes"
        ),
        RegistryRecord(
            nct_id="NCT04000002",
            title="Semaglutide for Weight Loss",
            overall_status="Completed",
            phase="Phase 3",
            enrollment=300,
            start_date="2018-06-01",
            completion_date="2020-12-01",
            study_completion_date="2021-02-01",
            sponsor="Academic Institution",
            sponsor_type="Other",
            results_posted=False,
            results_date=None,
            has_publications=False,
            pubmed_ids=[],
            intervention="semaglutide",
            condition="obesity"
        ),
        RegistryRecord(
            nct_id="NCT04000003",
            title="Semaglutide in Heart Failure",
            overall_status="Terminated",
            phase="Phase 2",
            enrollment=45,
            start_date="2019-03-01",
            completion_date="2020-09-01",
            study_completion_date="2020-10-01",
            sponsor="Pharma Inc",
            sponsor_type="Industry",
            results_posted=False,
            results_date=None,
            has_publications=False,
            pubmed_ids=[],
            intervention="semaglutide",
            condition="heart failure"
        ),
        RegistryRecord(
            nct_id="NCT04000004",
            title="Semaglutide Long-term Safety",
            overall_status="Recruiting",
            phase="Phase 4",
            enrollment=1000,
            start_date="2023-01-01",
            completion_date=None,
            study_completion_date=None,
            sponsor="Novo Nordisk",
            sponsor_type="Industry",
            results_posted=False,
            results_date=None,
            has_publications=False,
            pubmed_ids=[],
            intervention="semaglutide",
            condition="type 2 diabetes"
        )
    ]

    # Run analysis
    detector = UnpublishedTrialDetector()
    report = detector.generate_bias_report("semaglutide", "diabetes/obesity", records)

    # Print report
    formatted = detector.format_report(report)
    print(formatted)

    # Save output
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "publication_bias_report.json", 'w') as f:
        json.dump(report.to_dict(), f, indent=2)

    print(f"\nReport saved to {output_dir / 'publication_bias_report.json'}")


if __name__ == "__main__":
    main()
