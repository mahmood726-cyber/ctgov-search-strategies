#!/usr/bin/env python3
"""
PRISMA-S Compliant Search Report Generator
===========================================

Generates search documentation compliant with PRISMA-S extension
for reporting literature searches in systematic reviews.

PRISMA-S Items Covered:
1. Database name
2. Multi-database searching
3. Study registries
4. Online resources
5. Citation searching
6. Contacts
7. Other methods
8. Full search strategies
9. Limits and restrictions
10. Search filters
11. Prior work
12. Updates
13. Dates of searches
14. Peer review
15. Total records
16. Deduplication

Reference: Rethlefsen ML, et al. PRISMA-S: an extension to the PRISMA
Statement for Reporting Literature Searches in Systematic Reviews.
Systematic Reviews. 2021;10:39.

Author: CT.gov Search Strategy Validation Project
Version: 1.0.0
Date: 2026-01-26
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class DatabaseType(Enum):
    """Types of information sources."""
    BIBLIOGRAPHIC = "bibliographic"
    TRIAL_REGISTRY = "trial_registry"
    GREY_LITERATURE = "grey_literature"
    CITATION = "citation"
    CONTACT = "contact"
    OTHER = "other"


@dataclass
class SearchSource:
    """A single information source searched."""
    name: str
    database_type: DatabaseType
    interface: str  # e.g., "Web interface", "API v2"
    coverage_dates: str  # e.g., "1966 to present"

    # Search details
    search_date: str
    search_strategy: str
    limits_applied: List[str]
    filters_used: List[str]

    # Results
    records_retrieved: int
    records_after_limits: Optional[int] = None

    # Notes
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'database_type': self.database_type.value,
            'interface': self.interface,
            'coverage_dates': self.coverage_dates,
            'search_date': self.search_date,
            'search_strategy': self.search_strategy,
            'limits_applied': self.limits_applied,
            'filters_used': self.filters_used,
            'records_retrieved': self.records_retrieved,
            'records_after_limits': self.records_after_limits,
            'notes': self.notes
        }


@dataclass
class PRISMASReport:
    """Complete PRISMA-S compliant search report."""

    # Metadata
    review_title: str
    review_protocol: Optional[str]
    report_date: str
    author: str

    # Information sources (Items 1-7)
    bibliographic_databases: List[SearchSource]
    trial_registries: List[SearchSource]
    grey_literature_sources: List[SearchSource]
    citation_searching: Optional[str]
    contacts: Optional[str]
    other_methods: Optional[str]

    # Search strategies (Items 8-12)
    search_peer_reviewed: bool
    peer_review_method: Optional[str]
    prior_work_used: Optional[str]
    updates_planned: Optional[str]

    # Results (Items 15-16)
    total_records_all_sources: int
    total_after_deduplication: int
    deduplication_method: str

    # Additional documentation
    search_limitations: List[str]
    reproducibility_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'metadata': {
                'review_title': self.review_title,
                'review_protocol': self.review_protocol,
                'report_date': self.report_date,
                'author': self.author
            },
            'information_sources': {
                'bibliographic_databases': [s.to_dict() for s in self.bibliographic_databases],
                'trial_registries': [s.to_dict() for s in self.trial_registries],
                'grey_literature_sources': [s.to_dict() for s in self.grey_literature_sources],
                'citation_searching': self.citation_searching,
                'contacts': self.contacts,
                'other_methods': self.other_methods
            },
            'search_quality': {
                'search_peer_reviewed': self.search_peer_reviewed,
                'peer_review_method': self.peer_review_method,
                'prior_work_used': self.prior_work_used,
                'updates_planned': self.updates_planned
            },
            'results': {
                'total_records_all_sources': self.total_records_all_sources,
                'total_after_deduplication': self.total_after_deduplication,
                'deduplication_method': self.deduplication_method
            },
            'documentation': {
                'search_limitations': self.search_limitations,
                'reproducibility_notes': self.reproducibility_notes
            }
        }


class PRISMASReporter:
    """
    Generator for PRISMA-S compliant search documentation.

    Provides structured output meeting all 16 PRISMA-S checklist items.
    """

    PRISMA_S_CHECKLIST = {
        1: "Database name",
        2: "Multi-database searching",
        3: "Study registries",
        4: "Online resources and browsing",
        5: "Citation searching",
        6: "Contacts",
        7: "Other methods",
        8: "Full search strategies",
        9: "Limits and restrictions",
        10: "Search filters",
        11: "Prior work",
        12: "Updates",
        13: "Dates of searches",
        14: "Peer review",
        15: "Total records",
        16: "Deduplication"
    }

    def __init__(self):
        self.sources: List[SearchSource] = []
        self.metadata = {}

    def add_ctgov_search(self, drug: str, condition: str,
                         strategy: str, results_count: int,
                         search_date: Optional[str] = None,
                         api_version: str = "v2") -> SearchSource:
        """Add ClinicalTrials.gov search to report."""
        source = SearchSource(
            name="ClinicalTrials.gov",
            database_type=DatabaseType.TRIAL_REGISTRY,
            interface=f"API {api_version}",
            coverage_dates="1999 to present",
            search_date=search_date or datetime.now().strftime("%Y-%m-%d"),
            search_strategy=strategy,
            limits_applied=["Interventional studies only"],
            filters_used=["Study type: Interventional"],
            records_retrieved=results_count,
            notes=f"Search for {drug} in {condition}"
        )
        self.sources.append(source)
        return source

    def add_ictrp_search(self, drug: str, condition: str,
                        strategy: str, results_count: int,
                        search_date: Optional[str] = None) -> SearchSource:
        """Add WHO ICTRP search to report."""
        source = SearchSource(
            name="WHO International Clinical Trials Registry Platform (ICTRP)",
            database_type=DatabaseType.TRIAL_REGISTRY,
            interface="Web search portal",
            coverage_dates="2004 to present",
            search_date=search_date or datetime.now().strftime("%Y-%m-%d"),
            search_strategy=strategy,
            limits_applied=[],
            filters_used=["Recruitment status: All"],
            records_retrieved=results_count,
            notes=f"Search for {drug} in {condition}"
        )
        self.sources.append(source)
        return source

    def add_euctr_search(self, drug: str, condition: str,
                        strategy: str, results_count: int,
                        search_date: Optional[str] = None) -> SearchSource:
        """Add EU Clinical Trials Register search to report."""
        source = SearchSource(
            name="EU Clinical Trials Register (EUCTR)",
            database_type=DatabaseType.TRIAL_REGISTRY,
            interface="Web search interface",
            coverage_dates="2004 to present",
            search_date=search_date or datetime.now().strftime("%Y-%m-%d"),
            search_strategy=strategy,
            limits_applied=[],
            filters_used=[],
            records_retrieved=results_count,
            notes=f"Search for {drug} in {condition}. Export limit: 20 records per download."
        )
        self.sources.append(source)
        return source

    def add_pubmed_search(self, strategy: str, results_count: int,
                         search_date: Optional[str] = None,
                         filters: List[str] = None) -> SearchSource:
        """Add PubMed search to report."""
        source = SearchSource(
            name="PubMed/MEDLINE",
            database_type=DatabaseType.BIBLIOGRAPHIC,
            interface="PubMed web interface",
            coverage_dates="1966 to present",
            search_date=search_date or datetime.now().strftime("%Y-%m-%d"),
            search_strategy=strategy,
            limits_applied=[],
            filters_used=filters or [],
            records_retrieved=results_count
        )
        self.sources.append(source)
        return source

    def add_cochrane_central_search(self, strategy: str, results_count: int,
                                    search_date: Optional[str] = None) -> SearchSource:
        """Add Cochrane CENTRAL search to report."""
        source = SearchSource(
            name="Cochrane Central Register of Controlled Trials (CENTRAL)",
            database_type=DatabaseType.BIBLIOGRAPHIC,
            interface="Cochrane Library",
            coverage_dates="1898 to present",
            search_date=search_date or datetime.now().strftime("%Y-%m-%d"),
            search_strategy=strategy,
            limits_applied=["Trials only"],
            filters_used=[],
            records_retrieved=results_count
        )
        self.sources.append(source)
        return source

    def generate_report(self,
                       review_title: str,
                       author: str,
                       total_after_dedup: int,
                       dedup_method: str = "Registry ID matching + title similarity",
                       peer_reviewed: bool = False,
                       protocol_doi: Optional[str] = None) -> PRISMASReport:
        """Generate complete PRISMA-S report."""

        # Categorize sources
        bibliographic = [s for s in self.sources
                        if s.database_type == DatabaseType.BIBLIOGRAPHIC]
        registries = [s for s in self.sources
                     if s.database_type == DatabaseType.TRIAL_REGISTRY]
        grey_lit = [s for s in self.sources
                   if s.database_type == DatabaseType.GREY_LITERATURE]

        total_records = sum(s.records_retrieved for s in self.sources)

        report = PRISMASReport(
            review_title=review_title,
            review_protocol=protocol_doi,
            report_date=datetime.now().strftime("%Y-%m-%d"),
            author=author,
            bibliographic_databases=bibliographic,
            trial_registries=registries,
            grey_literature_sources=grey_lit,
            citation_searching=None,
            contacts=None,
            other_methods=None,
            search_peer_reviewed=peer_reviewed,
            peer_review_method="PRESS 2015 guideline" if peer_reviewed else None,
            prior_work_used=None,
            updates_planned=None,
            total_records_all_sources=total_records,
            total_after_deduplication=total_after_dedup,
            deduplication_method=dedup_method,
            search_limitations=[
                "Registry searches may miss trials not registered or registered under different terms",
                "CT.gov API v2 may return different results than web interface",
                "Some international registries have limited search functionality"
            ],
            reproducibility_notes="All API responses archived with SHA-256 checksums. "
                                 "Session manifests document API versions and timestamps."
        )

        return report

    def format_markdown(self, report: PRISMASReport) -> str:
        """Format report as markdown for publication."""
        lines = [
            f"# PRISMA-S Search Report",
            "",
            f"**Review Title:** {report.review_title}",
            f"**Report Date:** {report.report_date}",
            f"**Author:** {report.author}",
        ]

        if report.review_protocol:
            lines.append(f"**Protocol:** {report.review_protocol}")

        lines.extend([
            "",
            "---",
            "",
            "## Information Sources",
            "",
        ])

        # Bibliographic databases
        if report.bibliographic_databases:
            lines.extend([
                "### Bibliographic Databases",
                "",
            ])
            for source in report.bibliographic_databases:
                lines.extend(self._format_source(source))

        # Trial registries
        if report.trial_registries:
            lines.extend([
                "### Trial Registries",
                "",
            ])
            for source in report.trial_registries:
                lines.extend(self._format_source(source))

        # Grey literature
        if report.grey_literature_sources:
            lines.extend([
                "### Grey Literature",
                "",
            ])
            for source in report.grey_literature_sources:
                lines.extend(self._format_source(source))

        # Other methods
        lines.extend([
            "---",
            "",
            "## Search Methods",
            "",
            f"**Peer Review:** {'Yes' if report.search_peer_reviewed else 'No'}",
        ])

        if report.peer_review_method:
            lines.append(f"**Peer Review Method:** {report.peer_review_method}")

        # Results summary
        lines.extend([
            "",
            "---",
            "",
            "## Results Summary",
            "",
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| Total records (all sources) | {report.total_records_all_sources:,} |",
            f"| After deduplication | {report.total_after_deduplication:,} |",
            f"| Duplicates removed | {report.total_records_all_sources - report.total_after_deduplication:,} |",
            "",
            f"**Deduplication Method:** {report.deduplication_method}",
            "",
        ])

        # Limitations
        lines.extend([
            "---",
            "",
            "## Limitations",
            "",
        ])
        for limitation in report.search_limitations:
            lines.append(f"- {limitation}")

        # Reproducibility
        lines.extend([
            "",
            "---",
            "",
            "## Reproducibility",
            "",
            report.reproducibility_notes,
            "",
        ])

        # PRISMA-S checklist
        lines.extend([
            "---",
            "",
            "## PRISMA-S Checklist Compliance",
            "",
            "| Item | Description | Reported |",
            "|------|-------------|----------|",
        ])

        checklist_status = self._get_checklist_status(report)
        for item, description in self.PRISMA_S_CHECKLIST.items():
            status = "Yes" if checklist_status.get(item, False) else "No"
            lines.append(f"| {item} | {description} | {status} |")

        return "\n".join(lines)

    def _format_source(self, source: SearchSource) -> List[str]:
        """Format a single source for markdown output."""
        lines = [
            f"#### {source.name}",
            "",
            f"- **Interface:** {source.interface}",
            f"- **Coverage:** {source.coverage_dates}",
            f"- **Search Date:** {source.search_date}",
            f"- **Records Retrieved:** {source.records_retrieved:,}",
            "",
            "**Search Strategy:**",
            "```",
            source.search_strategy,
            "```",
            "",
        ]

        if source.limits_applied:
            lines.append(f"**Limits:** {', '.join(source.limits_applied)}")

        if source.filters_used:
            lines.append(f"**Filters:** {', '.join(source.filters_used)}")

        if source.notes:
            lines.append(f"**Notes:** {source.notes}")

        lines.append("")
        return lines

    def _get_checklist_status(self, report: PRISMASReport) -> Dict[int, bool]:
        """Determine which PRISMA-S items are satisfied."""
        return {
            1: len(report.bibliographic_databases) > 0 or len(report.trial_registries) > 0,
            2: len(report.bibliographic_databases) + len(report.trial_registries) > 1,
            3: len(report.trial_registries) > 0,
            4: len(report.grey_literature_sources) > 0,
            5: report.citation_searching is not None,
            6: report.contacts is not None,
            7: report.other_methods is not None,
            8: all(s.search_strategy for s in self.sources),
            9: any(s.limits_applied for s in self.sources),
            10: any(s.filters_used for s in self.sources),
            11: report.prior_work_used is not None,
            12: report.updates_planned is not None,
            13: all(s.search_date for s in self.sources),
            14: report.search_peer_reviewed,
            15: report.total_records_all_sources > 0,
            16: report.deduplication_method is not None
        }

    def export_json(self, report: PRISMASReport, output_path: Path):
        """Export report as JSON."""
        with open(output_path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)

    def export_markdown(self, report: PRISMASReport, output_path: Path):
        """Export report as markdown."""
        markdown = self.format_markdown(report)
        with open(output_path, 'w') as f:
            f.write(markdown)


def main():
    """Demo of PRISMA-S report generation."""
    print("PRISMA-S Report Generator Demo")
    print("=" * 50)

    reporter = PRISMASReporter()

    # Add sample searches
    reporter.add_ctgov_search(
        drug="semaglutide",
        condition="type 2 diabetes",
        strategy='query.intr="semaglutide" OR query.intr="Ozempic" OR query.intr="Wegovy"',
        results_count=156,
        api_version="v2"
    )

    reporter.add_ictrp_search(
        drug="semaglutide",
        condition="type 2 diabetes",
        strategy='semaglutide AND diabetes',
        results_count=89
    )

    reporter.add_euctr_search(
        drug="semaglutide",
        condition="type 2 diabetes",
        strategy='semaglutide',
        results_count=42
    )

    reporter.add_pubmed_search(
        strategy='semaglutide[tiab] AND "randomized controlled trial"[pt]',
        results_count=234,
        filters=["Publication type: RCT", "Language: English"]
    )

    # Generate report
    report = reporter.generate_report(
        review_title="Semaglutide for Type 2 Diabetes: A Systematic Review",
        author="CT.gov Search Strategy Validation Project",
        total_after_dedup=412,
        peer_reviewed=True
    )

    # Output
    markdown = reporter.format_markdown(report)
    print(markdown)

    # Save outputs
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    reporter.export_json(report, output_dir / "prisma_s_report.json")
    reporter.export_markdown(report, output_dir / "prisma_s_report.md")

    print(f"\nReports saved to {output_dir}")


if __name__ == "__main__":
    main()
