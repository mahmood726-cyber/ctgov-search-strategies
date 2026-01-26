#!/usr/bin/env python3
"""
Cross-Registry Trial Deduplication
==================================

Advanced deduplication algorithm using registry IDs for cross-registry
matching of clinical trials.

Based on ISPOR 2025 research showing registry-ID-based matching identifies
5x more duplicates than automated methods alone.

Features:
- Multi-registry ID pattern matching (NCT, ISRCTN, EudraCT, ACTRN, etc.)
- Title similarity matching with fuzzy logic
- Author/sponsor matching
- Secondary ID cross-referencing
- Deduplication audit trail

Author: CT.gov Search Strategy Validation Project
Version: 1.0.0
Date: 2026-01-26
"""

import json
import re
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime
from collections import defaultdict
import difflib


@dataclass
class TrialRecord:
    """A trial record from any registry."""
    source_registry: str
    primary_id: str
    secondary_ids: List[str]
    title: str
    sponsor: Optional[str]
    intervention: Optional[str]
    condition: Optional[str]
    status: Optional[str]
    start_date: Optional[str]
    enrollment: Optional[int]
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_registry': self.source_registry,
            'primary_id': self.primary_id,
            'secondary_ids': self.secondary_ids,
            'title': self.title,
            'sponsor': self.sponsor,
            'intervention': self.intervention,
            'condition': self.condition,
            'status': self.status,
            'start_date': self.start_date,
            'enrollment': self.enrollment
        }


@dataclass
class DuplicateMatch:
    """A matched duplicate pair."""
    record1: TrialRecord
    record2: TrialRecord
    match_type: str  # 'registry_id', 'secondary_id', 'title_similarity', 'combined'
    confidence: float
    matching_ids: List[str]
    title_similarity: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'record1_id': record1.primary_id,
            'record1_registry': record1.source_registry,
            'record2_id': record2.primary_id,
            'record2_registry': record2.source_registry,
            'match_type': self.match_type,
            'confidence': round(self.confidence, 3),
            'matching_ids': self.matching_ids,
            'title_similarity': round(self.title_similarity, 3)
        }


@dataclass
class DeduplicationResult:
    """Results of deduplication process."""
    total_input: int
    total_unique: int
    total_duplicates: int
    duplicate_groups: List[List[TrialRecord]]
    unique_records: List[TrialRecord]
    matches: List[DuplicateMatch]

    # Statistics
    by_match_type: Dict[str, int]
    by_registry_pair: Dict[str, int]

    # Audit
    timestamp: str
    algorithm_version: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'summary': {
                'total_input': self.total_input,
                'total_unique': self.total_unique,
                'total_duplicates': self.total_duplicates,
                'deduplication_rate': round(self.total_duplicates / max(1, self.total_input), 3)
            },
            'by_match_type': self.by_match_type,
            'by_registry_pair': self.by_registry_pair,
            'audit': {
                'timestamp': self.timestamp,
                'algorithm_version': self.algorithm_version
            }
        }


class RegistryIDMatcher:
    """
    Extract and match registry IDs across different formats.

    Supports:
    - NCT (ClinicalTrials.gov)
    - ISRCTN (ISRCTN Registry)
    - EudraCT (EU Clinical Trials Register)
    - ACTRN (ANZCTR)
    - ChiCTR (Chinese Clinical Trial Registry)
    - CTRI (Clinical Trials Registry - India)
    - DRKS (German Clinical Trials Register)
    - IRCT (Iranian Registry of Clinical Trials)
    - JPRN (Japan registries: UMIN, jRCT)
    - KCT (Korean Clinical Trials Registry)
    - NTR (Netherlands Trial Register)
    - PACTR (Pan African Clinical Trials Registry)
    - SLCTR (Sri Lanka Clinical Trials Registry)
    - TCTR (Thai Clinical Trials Registry)
    """

    REGISTRY_PATTERNS = {
        'NCT': {
            'pattern': r'NCT\d{8}',
            'registry': 'ClinicalTrials.gov',
            'normalize': lambda x: x.upper()
        },
        'ISRCTN': {
            'pattern': r'ISRCTN\d{8}',
            'registry': 'ISRCTN Registry',
            'normalize': lambda x: x.upper()
        },
        'EudraCT': {
            'pattern': r'\d{4}-\d{6}-\d{2}',
            'registry': 'EU Clinical Trials Register',
            'normalize': lambda x: x
        },
        'ACTRN': {
            'pattern': r'ACTRN\d{14}',
            'registry': 'ANZCTR',
            'normalize': lambda x: x.upper()
        },
        'ChiCTR': {
            'pattern': r'ChiCTR[-]?\d+',
            'registry': 'Chinese Clinical Trial Registry',
            'normalize': lambda x: x.upper().replace('-', '')
        },
        'CTRI': {
            'pattern': r'CTRI/\d{4}/\d+/\d+',
            'registry': 'CTRI India',
            'normalize': lambda x: x.upper()
        },
        'DRKS': {
            'pattern': r'DRKS\d{8}',
            'registry': 'German Clinical Trials Register',
            'normalize': lambda x: x.upper()
        },
        'IRCT': {
            'pattern': r'IRCT\d+N\d+',
            'registry': 'Iranian Registry of Clinical Trials',
            'normalize': lambda x: x.upper()
        },
        'UMIN': {
            'pattern': r'UMIN\d{9}',
            'registry': 'UMIN Japan',
            'normalize': lambda x: x.upper()
        },
        'jRCT': {
            'pattern': r'jRCT[s]?\d+',
            'registry': 'jRCT Japan',
            'normalize': lambda x: x.lower()
        },
        'KCT': {
            'pattern': r'KCT\d{7}',
            'registry': 'Korean Clinical Trials Registry',
            'normalize': lambda x: x.upper()
        },
        'NTR': {
            'pattern': r'NTR\d+',
            'registry': 'Netherlands Trial Register',
            'normalize': lambda x: x.upper()
        },
        'PACTR': {
            'pattern': r'PACTR\d+',
            'registry': 'Pan African Clinical Trials Registry',
            'normalize': lambda x: x.upper()
        },
        'TCTR': {
            'pattern': r'TCTR\d+',
            'registry': 'Thai Clinical Trials Registry',
            'normalize': lambda x: x.upper()
        }
    }

    def __init__(self):
        # Compile all patterns
        self.compiled_patterns = {
            name: re.compile(config['pattern'], re.IGNORECASE)
            for name, config in self.REGISTRY_PATTERNS.items()
        }

    def extract_all_ids(self, text: str) -> Dict[str, List[str]]:
        """Extract all registry IDs from text."""
        results = defaultdict(list)

        for name, pattern in self.compiled_patterns.items():
            matches = pattern.findall(text)
            normalizer = self.REGISTRY_PATTERNS[name]['normalize']
            results[name] = [normalizer(m) for m in matches]

        return dict(results)

    def normalize_id(self, registry_type: str, id_value: str) -> str:
        """Normalize a registry ID to canonical form."""
        if registry_type in self.REGISTRY_PATTERNS:
            return self.REGISTRY_PATTERNS[registry_type]['normalize'](id_value)
        return id_value.upper()

    def identify_registry_type(self, id_value: str) -> Optional[str]:
        """Identify which registry type an ID belongs to."""
        for name, pattern in self.compiled_patterns.items():
            if pattern.match(id_value):
                return name
        return None


class TitleMatcher:
    """
    Match trials by title similarity.

    Uses multiple algorithms:
    - Exact match (normalized)
    - Levenshtein ratio
    - Token-based Jaccard similarity
    """

    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        if not title:
            return ""

        # Lowercase
        title = title.lower()

        # Remove common prefixes
        prefixes = ['a ', 'an ', 'the ', 'study of ', 'trial of ',
                   'efficacy and safety of ', 'safety and efficacy of ']
        for prefix in prefixes:
            if title.startswith(prefix):
                title = title[len(prefix):]

        # Remove punctuation and extra whitespace
        title = re.sub(r'[^\w\s]', ' ', title)
        title = re.sub(r'\s+', ' ', title).strip()

        return title

    def calculate_similarity(self, title1: str, title2: str) -> float:
        """Calculate title similarity score."""
        norm1 = self.normalize_title(title1)
        norm2 = self.normalize_title(title2)

        if not norm1 or not norm2:
            return 0.0

        # Exact match
        if norm1 == norm2:
            return 1.0

        # Levenshtein ratio
        levenshtein = difflib.SequenceMatcher(None, norm1, norm2).ratio()

        # Token-based Jaccard
        tokens1 = set(norm1.split())
        tokens2 = set(norm2.split())
        if tokens1 or tokens2:
            jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)
        else:
            jaccard = 0.0

        # Weighted average
        return 0.6 * levenshtein + 0.4 * jaccard

    def is_match(self, title1: str, title2: str) -> Tuple[bool, float]:
        """Check if two titles match above threshold."""
        similarity = self.calculate_similarity(title1, title2)
        return similarity >= self.threshold, similarity


class CrossRegistryDeduplicator:
    """
    Main deduplication engine for cross-registry trial matching.

    Algorithm:
    1. Index all records by registry IDs
    2. Match by primary registry ID
    3. Match by secondary/cross-referenced IDs
    4. Match by title similarity (for remaining)
    5. Combine evidence for confidence scoring
    """

    ALGORITHM_VERSION = "1.0.0"

    def __init__(self,
                 title_threshold: float = 0.85,
                 min_confidence: float = 0.7):
        self.id_matcher = RegistryIDMatcher()
        self.title_matcher = TitleMatcher(threshold=title_threshold)
        self.min_confidence = min_confidence

    def deduplicate(self, records: List[TrialRecord]) -> DeduplicationResult:
        """
        Deduplicate a list of trial records.

        Returns complete deduplication results with audit trail.
        """
        if not records:
            return self._empty_result()

        # Step 1: Build ID index
        id_index = self._build_id_index(records)

        # Step 2: Find matches by registry ID
        id_matches = self._find_id_matches(records, id_index)

        # Step 3: Find matches by secondary IDs
        secondary_matches = self._find_secondary_id_matches(records, id_index)

        # Step 4: Find title-based matches for unmatched records
        matched_ids = {m.record1.primary_id for m in id_matches + secondary_matches}
        matched_ids.update({m.record2.primary_id for m in id_matches + secondary_matches})
        unmatched = [r for r in records if r.primary_id not in matched_ids]
        title_matches = self._find_title_matches(unmatched)

        # Step 5: Combine all matches
        all_matches = id_matches + secondary_matches + title_matches

        # Step 6: Build duplicate groups
        duplicate_groups = self._build_duplicate_groups(records, all_matches)

        # Step 7: Identify unique records (one per group)
        unique_records = [group[0] for group in duplicate_groups]

        # Calculate statistics
        by_match_type = defaultdict(int)
        by_registry_pair = defaultdict(int)

        for match in all_matches:
            by_match_type[match.match_type] += 1
            pair = tuple(sorted([match.record1.source_registry,
                                match.record2.source_registry]))
            by_registry_pair[f"{pair[0]} - {pair[1]}"] += 1

        return DeduplicationResult(
            total_input=len(records),
            total_unique=len(unique_records),
            total_duplicates=len(records) - len(unique_records),
            duplicate_groups=duplicate_groups,
            unique_records=unique_records,
            matches=all_matches,
            by_match_type=dict(by_match_type),
            by_registry_pair=dict(by_registry_pair),
            timestamp=datetime.now().isoformat(),
            algorithm_version=self.ALGORITHM_VERSION
        )

    def _build_id_index(self, records: List[TrialRecord]) -> Dict[str, List[int]]:
        """Build index mapping registry IDs to record indices."""
        index = defaultdict(list)

        for i, record in enumerate(records):
            # Index primary ID
            id_type = self.id_matcher.identify_registry_type(record.primary_id)
            if id_type:
                normalized = self.id_matcher.normalize_id(id_type, record.primary_id)
                index[normalized].append(i)

            # Index secondary IDs
            for sec_id in record.secondary_ids:
                id_type = self.id_matcher.identify_registry_type(sec_id)
                if id_type:
                    normalized = self.id_matcher.normalize_id(id_type, sec_id)
                    index[normalized].append(i)

        return dict(index)

    def _find_id_matches(self, records: List[TrialRecord],
                        id_index: Dict[str, List[int]]) -> List[DuplicateMatch]:
        """Find matches where trials share the same registry ID."""
        matches = []
        seen_pairs = set()

        for reg_id, indices in id_index.items():
            if len(indices) > 1:
                # Multiple records share this ID
                for i in range(len(indices)):
                    for j in range(i + 1, len(indices)):
                        idx1, idx2 = indices[i], indices[j]
                        pair_key = tuple(sorted([records[idx1].primary_id,
                                                records[idx2].primary_id]))

                        if pair_key not in seen_pairs:
                            seen_pairs.add(pair_key)

                            title_sim = self.title_matcher.calculate_similarity(
                                records[idx1].title, records[idx2].title
                            )

                            matches.append(DuplicateMatch(
                                record1=records[idx1],
                                record2=records[idx2],
                                match_type='registry_id',
                                confidence=0.99,  # Very high for ID match
                                matching_ids=[reg_id],
                                title_similarity=title_sim
                            ))

        return matches

    def _find_secondary_id_matches(self, records: List[TrialRecord],
                                   id_index: Dict[str, List[int]]) -> List[DuplicateMatch]:
        """Find matches through secondary/cross-referenced IDs."""
        matches = []
        seen_pairs = set()

        for i, record1 in enumerate(records):
            # Check if record1's secondary IDs appear in other records
            for sec_id in record1.secondary_ids:
                id_type = self.id_matcher.identify_registry_type(sec_id)
                if not id_type:
                    continue

                normalized = self.id_matcher.normalize_id(id_type, sec_id)

                # Find records where this is the primary ID
                for j, record2 in enumerate(records):
                    if i == j:
                        continue

                    record2_primary_norm = self.id_matcher.normalize_id(
                        self.id_matcher.identify_registry_type(record2.primary_id) or '',
                        record2.primary_id
                    )

                    if normalized == record2_primary_norm:
                        pair_key = tuple(sorted([record1.primary_id, record2.primary_id]))

                        if pair_key not in seen_pairs:
                            seen_pairs.add(pair_key)

                            title_sim = self.title_matcher.calculate_similarity(
                                record1.title, record2.title
                            )

                            matches.append(DuplicateMatch(
                                record1=record1,
                                record2=record2,
                                match_type='secondary_id',
                                confidence=0.95,
                                matching_ids=[normalized],
                                title_similarity=title_sim
                            ))

        return matches

    def _find_title_matches(self, records: List[TrialRecord]) -> List[DuplicateMatch]:
        """Find matches based on title similarity."""
        matches = []
        seen_pairs = set()

        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                is_match, similarity = self.title_matcher.is_match(
                    records[i].title, records[j].title
                )

                if is_match:
                    pair_key = tuple(sorted([records[i].primary_id,
                                           records[j].primary_id]))

                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)

                        # Adjust confidence based on other factors
                        confidence = similarity * 0.8

                        # Boost if same sponsor
                        if (records[i].sponsor and records[j].sponsor and
                            records[i].sponsor.lower() == records[j].sponsor.lower()):
                            confidence = min(0.95, confidence + 0.1)

                        # Boost if similar enrollment
                        if records[i].enrollment and records[j].enrollment:
                            enroll_ratio = min(records[i].enrollment, records[j].enrollment) / \
                                          max(records[i].enrollment, records[j].enrollment)
                            if enroll_ratio > 0.8:
                                confidence = min(0.95, confidence + 0.05)

                        if confidence >= self.min_confidence:
                            matches.append(DuplicateMatch(
                                record1=records[i],
                                record2=records[j],
                                match_type='title_similarity',
                                confidence=confidence,
                                matching_ids=[],
                                title_similarity=similarity
                            ))

        return matches

    def _build_duplicate_groups(self, records: List[TrialRecord],
                               matches: List[DuplicateMatch]) -> List[List[TrialRecord]]:
        """Build groups of duplicate records using union-find."""
        # Initialize each record in its own group
        parent = {r.primary_id: r.primary_id for r in records}
        record_map = {r.primary_id: r for r in records}

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # Union matched records
        for match in matches:
            union(match.record1.primary_id, match.record2.primary_id)

        # Build groups
        groups = defaultdict(list)
        for record in records:
            root = find(record.primary_id)
            groups[root].append(record)

        return list(groups.values())

    def _empty_result(self) -> DeduplicationResult:
        """Return empty result for no input."""
        return DeduplicationResult(
            total_input=0,
            total_unique=0,
            total_duplicates=0,
            duplicate_groups=[],
            unique_records=[],
            matches=[],
            by_match_type={},
            by_registry_pair={},
            timestamp=datetime.now().isoformat(),
            algorithm_version=self.ALGORITHM_VERSION
        )

    def generate_report(self, result: DeduplicationResult) -> str:
        """Generate human-readable deduplication report."""
        lines = [
            "=" * 60,
            "CROSS-REGISTRY DEDUPLICATION REPORT",
            "=" * 60,
            f"Algorithm Version: {result.algorithm_version}",
            f"Timestamp: {result.timestamp}",
            "",
            "SUMMARY",
            "-" * 40,
            f"Total input records: {result.total_input}",
            f"Unique records: {result.total_unique}",
            f"Duplicates identified: {result.total_duplicates}",
            f"Deduplication rate: {result.total_duplicates / max(1, result.total_input):.1%}",
            "",
        ]

        if result.by_match_type:
            lines.extend([
                "MATCHES BY TYPE",
                "-" * 40,
            ])
            for match_type, count in sorted(result.by_match_type.items()):
                lines.append(f"  {match_type}: {count}")
            lines.append("")

        if result.by_registry_pair:
            lines.extend([
                "MATCHES BY REGISTRY PAIR",
                "-" * 40,
            ])
            for pair, count in sorted(result.by_registry_pair.items(),
                                     key=lambda x: -x[1]):
                lines.append(f"  {pair}: {count}")
            lines.append("")

        # Sample matches
        if result.matches[:5]:
            lines.extend([
                "SAMPLE MATCHES (first 5)",
                "-" * 40,
            ])
            for match in result.matches[:5]:
                lines.extend([
                    f"  {match.record1.primary_id} ({match.record1.source_registry})",
                    f"    <-> {match.record2.primary_id} ({match.record2.source_registry})",
                    f"    Type: {match.match_type}, Confidence: {match.confidence:.2f}",
                    ""
                ])

        return "\n".join(lines)


def main():
    """Demo of cross-registry deduplication."""
    print("Cross-Registry Deduplication Demo")
    print("=" * 50)

    # Create sample records
    records = [
        TrialRecord(
            source_registry="ClinicalTrials.gov",
            primary_id="NCT04567890",
            secondary_ids=["2020-001234-56"],
            title="A Study of Semaglutide in Type 2 Diabetes",
            sponsor="Novo Nordisk",
            intervention="semaglutide",
            condition="type 2 diabetes",
            status="Completed",
            start_date="2020-01-15",
            enrollment=500
        ),
        TrialRecord(
            source_registry="EUCTR",
            primary_id="2020-001234-56",
            secondary_ids=["NCT04567890"],
            title="Study of Semaglutide in Patients with Type 2 Diabetes",
            sponsor="Novo Nordisk A/S",
            intervention="semaglutide",
            condition="diabetes mellitus type 2",
            status="Completed",
            start_date="2020-01-01",
            enrollment=500
        ),
        TrialRecord(
            source_registry="ISRCTN",
            primary_id="ISRCTN12345678",
            secondary_ids=[],
            title="Randomized Trial of Semaglutide for Type 2 Diabetes",
            sponsor="Novo Nordisk",
            intervention="semaglutide",
            condition="type 2 diabetes",
            status="Completed",
            start_date="2020-02-01",
            enrollment=480
        ),
        TrialRecord(
            source_registry="ClinicalTrials.gov",
            primary_id="NCT04999999",
            secondary_ids=[],
            title="Pembrolizumab in Advanced Melanoma",
            sponsor="Merck",
            intervention="pembrolizumab",
            condition="melanoma",
            status="Active",
            start_date="2021-06-01",
            enrollment=300
        )
    ]

    # Run deduplication
    deduplicator = CrossRegistryDeduplicator()
    result = deduplicator.deduplicate(records)

    # Print report
    report = deduplicator.generate_report(result)
    print(report)

    # Save output
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "deduplication_result.json", 'w') as f:
        json.dump(result.to_dict(), f, indent=2)

    print(f"\nResults saved to {output_dir / 'deduplication_result.json'}")


if __name__ == "__main__":
    main()
