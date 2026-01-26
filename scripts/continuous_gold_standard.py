#!/usr/bin/env python3
"""
Continuous Gold Standard Updates
================================

Automated pipeline to expand and maintain the gold standard over time.

Features:
- Weekly PubMed scan for new NCT-linked publications
- Automatic trial record extraction
- Gold standard version control
- Temporal recall tracking

Author: CT.gov Search Strategy Validation Project
Version: 1.0.0
Date: 2026-01-26
"""

import json
import hashlib
import gzip
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime, timedelta
from collections import defaultdict
import re


@dataclass
class TrialRecord:
    """A single trial record in the gold standard."""
    nct_id: str
    drug: str
    condition: str
    therapeutic_area: str

    # Source information
    pubmed_ids: List[str]
    first_published: str
    last_updated: str

    # Metadata
    title: Optional[str]
    phase: Optional[str]
    enrollment: Optional[int]
    status: Optional[str]

    # Validation
    validated: bool
    validation_source: str  # pubmed_databank, cochrane, manual

    def to_dict(self) -> Dict[str, Any]:
        return {
            'nct_id': self.nct_id,
            'drug': self.drug,
            'condition': self.condition,
            'therapeutic_area': self.therapeutic_area,
            'pubmed_ids': self.pubmed_ids,
            'first_published': self.first_published,
            'last_updated': self.last_updated,
            'title': self.title,
            'phase': self.phase,
            'enrollment': self.enrollment,
            'status': self.status,
            'validated': self.validated,
            'validation_source': self.validation_source
        }


@dataclass
class GoldStandardVersion:
    """A versioned snapshot of the gold standard."""
    version: str
    timestamp: str
    description: str

    # Statistics
    total_trials: int
    total_drugs: int
    total_therapeutic_areas: int
    trials_by_area: Dict[str, int]

    # Changes from previous version
    trials_added: int
    trials_removed: int
    trials_modified: int

    # Integrity
    checksum: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': self.version,
            'timestamp': self.timestamp,
            'description': self.description,
            'total_trials': self.total_trials,
            'total_drugs': self.total_drugs,
            'total_therapeutic_areas': self.total_therapeutic_areas,
            'trials_by_area': self.trials_by_area,
            'trials_added': self.trials_added,
            'trials_removed': self.trials_removed,
            'trials_modified': self.trials_modified,
            'checksum': self.checksum
        }


@dataclass
class RecallTrend:
    """Temporal tracking of recall performance."""
    drug: str
    therapeutic_area: str

    # Time series data
    timestamps: List[str]
    recall_values: List[float]
    gold_standard_sizes: List[int]

    # Statistics
    current_recall: float
    recall_trend: str  # improving, stable, declining
    volatility: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'drug': self.drug,
            'therapeutic_area': self.therapeutic_area,
            'timestamps': self.timestamps,
            'recall_values': self.recall_values,
            'gold_standard_sizes': self.gold_standard_sizes,
            'current_recall': round(self.current_recall, 4),
            'recall_trend': self.recall_trend,
            'volatility': round(self.volatility, 4)
        }


class PubMedScanner:
    """
    Scan PubMed for new NCT-linked publications.

    Uses PubMed E-utilities to find publications with trial registration numbers.
    """

    # NCT ID pattern
    NCT_PATTERN = re.compile(r'NCT\d{8}')

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def build_search_query(self, drug: str, condition: str,
                          days_back: int = 7) -> str:
        """Build PubMed search query for NCT-linked publications."""
        date_range = f"({days_back}[Publication Date : relative])"

        # DataBank filter for clinical trials
        databank_filter = '("clinicaltrials.gov"[si])'

        # Drug and condition
        drug_term = f'"{drug}"[Title/Abstract]'
        condition_term = f'"{condition}"[Title/Abstract]'

        query = f"{date_range} AND {databank_filter} AND {drug_term}"
        if condition:
            query += f" AND {condition_term}"

        return query

    def extract_nct_ids_from_pubmed(self, pubmed_data: Dict) -> Set[str]:
        """Extract NCT IDs from PubMed record data."""
        nct_ids = set()

        # Check DataBank/AccessionNumberList
        if 'databank_list' in pubmed_data:
            for db in pubmed_data['databank_list']:
                if db.get('databank_name') == 'ClinicalTrials.gov':
                    for acc in db.get('accession_number_list', []):
                        if self.NCT_PATTERN.match(acc):
                            nct_ids.add(acc)

        # Check abstract for NCT IDs
        abstract = pubmed_data.get('abstract', '')
        nct_ids.update(self.NCT_PATTERN.findall(abstract))

        return nct_ids

    def scan_for_new_trials(self, drug: str, condition: str,
                           days_back: int = 7) -> List[Dict]:
        """
        Scan PubMed for new NCT-linked publications.

        Note: This is a mock implementation. Real implementation would
        call PubMed E-utilities API.

        Returns:
            List of {nct_id, pubmed_id, title, date} dicts
        """
        # Mock implementation
        return []


class GoldStandardManager:
    """
    Manage the gold standard database with version control.

    Features:
    - Add/update/remove trials
    - Version snapshots with checksums
    - Import from various sources
    - Export for validation
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/gold_standard")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.trials: Dict[str, TrialRecord] = {}
        self.versions: List[GoldStandardVersion] = []
        self.current_version = "0.0.0"

        self._load_data()

    def _load_data(self):
        """Load existing gold standard data."""
        # Load trials
        trials_file = self.data_dir / "trials.json"
        if trials_file.exists():
            with open(trials_file) as f:
                data = json.load(f)
                for nct_id, trial_data in data.items():
                    self.trials[nct_id] = TrialRecord(**trial_data)

        # Load version history
        versions_file = self.data_dir / "versions.json"
        if versions_file.exists():
            with open(versions_file) as f:
                version_data = json.load(f)
                self.versions = [GoldStandardVersion(**v) for v in version_data]
                if self.versions:
                    self.current_version = self.versions[-1].version

    def _save_data(self):
        """Save gold standard data."""
        # Save trials
        trials_data = {nct_id: trial.to_dict() for nct_id, trial in self.trials.items()}
        with open(self.data_dir / "trials.json", 'w') as f:
            json.dump(trials_data, f, indent=2)

        # Save versions
        versions_data = [v.to_dict() for v in self.versions]
        with open(self.data_dir / "versions.json", 'w') as f:
            json.dump(versions_data, f, indent=2)

    def _compute_checksum(self) -> str:
        """Compute checksum of current gold standard."""
        # Sort trials for deterministic hash
        sorted_ncts = sorted(self.trials.keys())
        data_str = json.dumps([self.trials[nct].to_dict() for nct in sorted_ncts])
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]

    def add_trial(self, nct_id: str, drug: str, condition: str,
                 therapeutic_area: str, pubmed_ids: List[str],
                 title: Optional[str] = None, phase: Optional[str] = None,
                 validation_source: str = "pubmed_databank") -> bool:
        """Add a trial to the gold standard."""
        if nct_id in self.trials:
            # Update existing
            trial = self.trials[nct_id]
            trial.pubmed_ids = list(set(trial.pubmed_ids + pubmed_ids))
            trial.last_updated = datetime.now().isoformat()
            return False  # Not new
        else:
            # Add new
            self.trials[nct_id] = TrialRecord(
                nct_id=nct_id,
                drug=drug,
                condition=condition,
                therapeutic_area=therapeutic_area,
                pubmed_ids=pubmed_ids,
                first_published=datetime.now().isoformat(),
                last_updated=datetime.now().isoformat(),
                title=title,
                phase=phase,
                enrollment=None,
                status=None,
                validated=True,
                validation_source=validation_source
            )
            return True  # New trial

    def remove_trial(self, nct_id: str) -> bool:
        """Remove a trial from the gold standard."""
        if nct_id in self.trials:
            del self.trials[nct_id]
            return True
        return False

    def get_trials_for_drug(self, drug: str) -> List[TrialRecord]:
        """Get all trials for a specific drug."""
        return [t for t in self.trials.values() if t.drug.lower() == drug.lower()]

    def get_trials_for_area(self, area: str) -> List[TrialRecord]:
        """Get all trials for a therapeutic area."""
        return [t for t in self.trials.values()
                if t.therapeutic_area.lower() == area.lower()]

    def get_nct_ids_for_drug(self, drug: str) -> Set[str]:
        """Get NCT IDs for a drug (for validation)."""
        return {t.nct_id for t in self.get_trials_for_drug(drug)}

    def create_version(self, description: str) -> GoldStandardVersion:
        """Create a new version snapshot."""
        # Compute statistics
        trials_by_area = defaultdict(int)
        drugs = set()
        for trial in self.trials.values():
            trials_by_area[trial.therapeutic_area] += 1
            drugs.add(trial.drug)

        # Compute changes from previous version
        added, removed, modified = 0, 0, 0
        if self.versions:
            # Load previous version for comparison
            prev_checksum = self.versions[-1].checksum
            # (In full implementation, would compare actual trial sets)

        # Increment version
        major, minor, patch = self.current_version.split('.')
        new_version = f"{major}.{int(minor)+1}.0"

        version = GoldStandardVersion(
            version=new_version,
            timestamp=datetime.now().isoformat(),
            description=description,
            total_trials=len(self.trials),
            total_drugs=len(drugs),
            total_therapeutic_areas=len(trials_by_area),
            trials_by_area=dict(trials_by_area),
            trials_added=added,
            trials_removed=removed,
            trials_modified=modified,
            checksum=self._compute_checksum()
        )

        self.versions.append(version)
        self.current_version = new_version
        self._save_data()

        # Archive the version
        self._archive_version(version)

        return version

    def _archive_version(self, version: GoldStandardVersion):
        """Archive a version snapshot."""
        archive_dir = self.data_dir / "archives"
        archive_dir.mkdir(exist_ok=True)

        archive_data = {
            'version': version.to_dict(),
            'trials': {nct: t.to_dict() for nct, t in self.trials.items()}
        }

        archive_path = archive_dir / f"v{version.version}.json.gz"
        with gzip.open(archive_path, 'wt', encoding='utf-8') as f:
            json.dump(archive_data, f)

    def export_for_validation(self, output_path: Path):
        """Export gold standard for validation pipeline."""
        export_data = {
            'version': self.current_version,
            'timestamp': datetime.now().isoformat(),
            'by_drug': defaultdict(list)
        }

        for trial in self.trials.values():
            export_data['by_drug'][trial.drug].append({
                'nct_id': trial.nct_id,
                'condition': trial.condition,
                'therapeutic_area': trial.therapeutic_area
            })

        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)


class RecallTracker:
    """
    Track recall performance over time.

    Enables:
    - Temporal analysis of recall changes
    - Detection of degradation
    - Trend analysis
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/recall_tracking")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.trends: Dict[str, RecallTrend] = {}
        self._load_data()

    def _load_data(self):
        """Load existing trend data."""
        trends_file = self.data_dir / "trends.json"
        if trends_file.exists():
            with open(trends_file) as f:
                data = json.load(f)
                for key, trend_data in data.items():
                    self.trends[key] = RecallTrend(**trend_data)

    def _save_data(self):
        """Save trend data."""
        data = {key: trend.to_dict() for key, trend in self.trends.items()}
        with open(self.data_dir / "trends.json", 'w') as f:
            json.dump(data, f, indent=2)

    def _make_key(self, drug: str, therapeutic_area: str) -> str:
        return f"{drug.lower()}|{therapeutic_area.lower()}"

    def record_recall(self, drug: str, therapeutic_area: str,
                     recall: float, gold_standard_size: int):
        """Record a recall measurement."""
        key = self._make_key(drug, therapeutic_area)

        if key not in self.trends:
            self.trends[key] = RecallTrend(
                drug=drug,
                therapeutic_area=therapeutic_area,
                timestamps=[],
                recall_values=[],
                gold_standard_sizes=[],
                current_recall=0.0,
                recall_trend="stable",
                volatility=0.0
            )

        trend = self.trends[key]
        trend.timestamps.append(datetime.now().isoformat())
        trend.recall_values.append(recall)
        trend.gold_standard_sizes.append(gold_standard_size)
        trend.current_recall = recall

        # Calculate trend and volatility
        if len(trend.recall_values) >= 3:
            recent = trend.recall_values[-3:]
            if recent[-1] > recent[0] + 0.05:
                trend.recall_trend = "improving"
            elif recent[-1] < recent[0] - 0.05:
                trend.recall_trend = "declining"
            else:
                trend.recall_trend = "stable"

            # Volatility as standard deviation of recent values
            mean = sum(recent) / len(recent)
            variance = sum((x - mean) ** 2 for x in recent) / len(recent)
            trend.volatility = variance ** 0.5

        self._save_data()

    def get_trend(self, drug: str, therapeutic_area: str) -> Optional[RecallTrend]:
        """Get trend for a drug/area combination."""
        key = self._make_key(drug, therapeutic_area)
        return self.trends.get(key)

    def get_declining_drugs(self, threshold: float = 0.05) -> List[RecallTrend]:
        """Get drugs with declining recall."""
        declining = []
        for trend in self.trends.values():
            if trend.recall_trend == "declining":
                declining.append(trend)
            elif len(trend.recall_values) >= 2:
                if trend.recall_values[-1] < trend.recall_values[0] - threshold:
                    declining.append(trend)
        return declining

    def generate_report(self) -> str:
        """Generate recall tracking report."""
        lines = [
            "=" * 60,
            "RECALL TRACKING REPORT",
            "=" * 60,
            f"Generated: {datetime.now().isoformat()}",
            f"Total drugs tracked: {len(self.trends)}",
            "",
        ]

        # Summary by trend
        improving = [t for t in self.trends.values() if t.recall_trend == "improving"]
        stable = [t for t in self.trends.values() if t.recall_trend == "stable"]
        declining = [t for t in self.trends.values() if t.recall_trend == "declining"]

        lines.extend([
            "TREND SUMMARY",
            "-" * 40,
            f"Improving: {len(improving)}",
            f"Stable: {len(stable)}",
            f"Declining: {len(declining)}",
            "",
        ])

        if declining:
            lines.extend([
                "⚠️  DECLINING DRUGS (ATTENTION NEEDED)",
                "-" * 40,
            ])
            for trend in declining:
                lines.append(
                    f"  {trend.drug} ({trend.therapeutic_area}): "
                    f"{trend.recall_values[0]:.1%} → {trend.current_recall:.1%}"
                )
            lines.append("")

        # Top performers
        by_recall = sorted(self.trends.values(),
                          key=lambda t: t.current_recall, reverse=True)

        lines.extend([
            "TOP PERFORMERS",
            "-" * 40,
        ])
        for trend in by_recall[:5]:
            lines.append(
                f"  {trend.drug}: {trend.current_recall:.1%} "
                f"(gold standard: {trend.gold_standard_sizes[-1] if trend.gold_standard_sizes else 'N/A'})"
            )

        return "\n".join(lines)


class ContinuousUpdatePipeline:
    """
    Automated pipeline for continuous gold standard updates.

    Runs weekly to:
    1. Scan PubMed for new NCT-linked publications
    2. Add new trials to gold standard
    3. Re-run validation
    4. Track recall trends
    5. Alert on degradation
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data")
        self.scanner = PubMedScanner()
        self.gold_standard = GoldStandardManager(self.data_dir / "gold_standard")
        self.recall_tracker = RecallTracker(self.data_dir / "recall_tracking")

        # Configuration
        self.drugs_to_track = [
            ('semaglutide', 'type 2 diabetes', 'diabetes'),
            ('pembrolizumab', 'cancer', 'oncology'),
            ('adalimumab', 'rheumatoid arthritis', 'rheumatology'),
            ('dupilumab', 'asthma', 'respiratory'),
            ('apixaban', 'atrial fibrillation', 'cardiovascular')
        ]

    def run_weekly_update(self) -> Dict[str, Any]:
        """
        Run the weekly update pipeline.

        Returns:
            Summary of updates performed
        """
        summary = {
            'timestamp': datetime.now().isoformat(),
            'new_trials': 0,
            'updated_trials': 0,
            'drugs_scanned': len(self.drugs_to_track),
            'alerts': []
        }

        # Scan each drug
        for drug, condition, area in self.drugs_to_track:
            new_publications = self.scanner.scan_for_new_trials(drug, condition, days_back=7)

            for pub in new_publications:
                is_new = self.gold_standard.add_trial(
                    nct_id=pub['nct_id'],
                    drug=drug,
                    condition=condition,
                    therapeutic_area=area,
                    pubmed_ids=[pub['pubmed_id']],
                    title=pub.get('title')
                )

                if is_new:
                    summary['new_trials'] += 1
                else:
                    summary['updated_trials'] += 1

        # Create new version if changes were made
        if summary['new_trials'] > 0 or summary['updated_trials'] > 0:
            version = self.gold_standard.create_version(
                f"Weekly update: +{summary['new_trials']} new, "
                f"{summary['updated_trials']} updated"
            )
            summary['new_version'] = version.version

        # Check for declining recall
        declining = self.recall_tracker.get_declining_drugs()
        if declining:
            summary['alerts'].append({
                'type': 'declining_recall',
                'drugs': [t.drug for t in declining]
            })

        return summary

    def run_validation_cycle(self) -> Dict[str, Any]:
        """
        Run a full validation cycle and record recall.

        Note: This is a simplified implementation. Full implementation
        would execute actual CT.gov searches and compare to gold standard.
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'drugs_validated': 0,
            'average_recall': 0.0,
            'by_drug': {}
        }

        total_recall = 0.0

        for drug, condition, area in self.drugs_to_track:
            gold_ncts = self.gold_standard.get_nct_ids_for_drug(drug)

            if not gold_ncts:
                continue

            # Mock validation (real implementation would search CT.gov)
            mock_recall = 0.75 + (hash(drug) % 20) / 100  # Simulate variation

            self.recall_tracker.record_recall(
                drug=drug,
                therapeutic_area=area,
                recall=mock_recall,
                gold_standard_size=len(gold_ncts)
            )

            results['by_drug'][drug] = {
                'recall': mock_recall,
                'gold_standard_size': len(gold_ncts)
            }
            total_recall += mock_recall
            results['drugs_validated'] += 1

        if results['drugs_validated'] > 0:
            results['average_recall'] = total_recall / results['drugs_validated']

        return results


def main():
    """Demo of continuous gold standard updates."""
    print("Continuous Gold Standard Updates Demo")
    print("=" * 50)

    # Initialize pipeline
    pipeline = ContinuousUpdatePipeline()

    # Show current gold standard status
    gs = pipeline.gold_standard
    print(f"\nCurrent Gold Standard:")
    print(f"  Version: {gs.current_version}")
    print(f"  Total trials: {len(gs.trials)}")

    # Simulate adding some trials
    print("\nAdding sample trials...")
    sample_trials = [
        ('NCT04567890', 'semaglutide', 'type 2 diabetes', 'diabetes', ['12345678']),
        ('NCT04567891', 'semaglutide', 'obesity', 'diabetes', ['12345679']),
        ('NCT04567892', 'pembrolizumab', 'lung cancer', 'oncology', ['12345680']),
        ('NCT04567893', 'pembrolizumab', 'melanoma', 'oncology', ['12345681']),
        ('NCT04567894', 'adalimumab', 'rheumatoid arthritis', 'rheumatology', ['12345682']),
    ]

    for nct_id, drug, condition, area, pmids in sample_trials:
        is_new = gs.add_trial(nct_id, drug, condition, area, pmids)
        status = "added" if is_new else "updated"
        print(f"  {nct_id}: {status}")

    # Create version
    version = gs.create_version("Demo: Initial sample data")
    print(f"\nCreated version: {version.version}")
    print(f"  Total trials: {version.total_trials}")
    print(f"  Checksum: {version.checksum}")

    # Run validation cycle
    print("\nRunning validation cycle...")
    validation_results = pipeline.run_validation_cycle()
    print(f"  Drugs validated: {validation_results['drugs_validated']}")
    print(f"  Average recall: {validation_results['average_recall']:.1%}")

    # Generate recall report
    print("\n" + pipeline.recall_tracker.generate_report())

    # Export for validation
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    gs.export_for_validation(output_dir / "gold_standard_export.json")
    print(f"\nGold standard exported to {output_dir / 'gold_standard_export.json'}")


if __name__ == "__main__":
    main()
