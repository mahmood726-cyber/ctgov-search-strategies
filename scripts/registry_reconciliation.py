#!/usr/bin/env python3
"""
Registry-Paper Reconciliation Engine
TruthCert TC-TRIALREG Integration for Trial Registry Integrity

This module provides:
- Multi-registry search (CT.gov, WHO ICTRP simulation)
- Registry-paper reconciliation with field comparison
- TruthCert validators for integrity checking
- Corruption detection (endpoint switching, sample size mismatch, etc.)
- Audit ledger with cryptographic bundle hashes

Author: Mahmood Ahmad
Version: 4.0
License: MIT
"""

import requests
import json
import hashlib
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import re


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class RegistrySource(Enum):
    CTGOV = "ClinicalTrials.gov"
    ICTRP = "WHO ICTRP"
    EUCTR = "EU Clinical Trials Register"
    ISRCTN = "ISRCTN Registry"


class CorruptionType(Enum):
    ENDPOINT_SWITCHING = "endpoint_switching"
    SAMPLE_SIZE_MISMATCH = "sample_size_mismatch"
    TIMEPOINT_MISMATCH = "timepoint_mismatch"
    STATUS_MISREAD = "status_misread"
    RETRACTED_PAPER = "retracted_paper"
    DUPLICATE_PUBLICATION = "duplicate_publication"
    RESULTS_DISCREPANCY = "results_discrepancy"


class ValidationStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    UNKNOWN = "UNKNOWN"


# TruthCert TC-TRIALREG field types
TC_FIELD_TYPES = {
    "primary_outcome": "FACT",
    "secondary_outcome": "FACT",
    "sample_size": "FACT",
    "follow_up_duration": "FACT",
    "study_status": "FACT",
    "completion_date": "FACT",
    "results_posted": "FACT",
    "phase": "FACT",
    "allocation": "FACT",
    "masking": "FACT"
}

# Agreement threshold for Gate B5
AGREEMENT_THRESHOLD = 0.80


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class RegistryRecord:
    """A record from a trial registry"""
    nct_id: str
    registry: RegistrySource
    title: str
    status: str
    phase: Optional[str] = None
    enrollment: Optional[int] = None
    primary_outcome: Optional[str] = None
    secondary_outcomes: List[str] = field(default_factory=list)
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    results_posted: bool = False
    last_update: Optional[str] = None
    raw_data: Dict = field(default_factory=dict)


@dataclass
class PaperData:
    """Extracted data from a published paper"""
    doi: Optional[str] = None
    pmid: Optional[str] = None
    title: str = ""
    nct_ids: List[str] = field(default_factory=list)
    reported_sample_size: Optional[int] = None
    reported_primary_outcome: Optional[str] = None
    reported_secondary_outcomes: List[str] = field(default_factory=list)
    reported_follow_up: Optional[str] = None
    is_retracted: bool = False
    retraction_date: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of a single validation check"""
    validator_id: str
    validator_name: str
    status: ValidationStatus
    confidence: float
    message: str
    details: Dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))


@dataclass
class CorruptionFlag:
    """A detected data corruption"""
    corruption_type: CorruptionType
    severity: str  # "HIGH", "MEDIUM", "LOW"
    field_name: str
    registry_value: Any
    paper_value: Any
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))


@dataclass
class ReconciliationReport:
    """Full reconciliation report for a trial"""
    nct_id: str
    registry_records: List[RegistryRecord]
    paper_data: Optional[PaperData]
    validations: List[ValidationResult]
    corruptions: List[CorruptionFlag]
    overall_status: str  # "VERIFIED", "DISCREPANCY", "FAILED"
    agreement_score: float
    bundle_hash: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

    def __post_init__(self):
        if not self.bundle_hash:
            self.bundle_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of report for integrity"""
        def enum_serializer(obj):
            if isinstance(obj, Enum):
                return obj.value
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        content = json.dumps({
            "nct_id": self.nct_id,
            "validations": [asdict(v) for v in self.validations],
            "corruptions": [asdict(c) for c in self.corruptions],
            "overall_status": self.overall_status,
            "agreement_score": self.agreement_score,
            "timestamp": self.timestamp
        }, sort_keys=True, default=enum_serializer)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class AuditEntry:
    """Entry in the immutable audit ledger"""
    entry_id: str
    action: str
    nct_id: str
    result: str
    bundle_hash: str
    timestamp: str
    previous_hash: str = ""

    def compute_chain_hash(self) -> str:
        """Compute hash for ledger chain"""
        content = f"{self.previous_hash}:{self.entry_id}:{self.action}:{self.nct_id}:{self.result}:{self.timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# =============================================================================
# REGISTRY SEARCH FUNCTIONS
# =============================================================================

class RegistrySearcher:
    """Multi-registry search interface"""

    CTGOV_API_BASE = "https://clinicaltrials.gov/api/v2/studies"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "TruthCert-TC-TRIALREG/4.0"
        })

    def search_ctgov(self, nct_id: str) -> Optional[RegistryRecord]:
        """Fetch a single study from ClinicalTrials.gov by NCT ID"""
        try:
            url = f"{self.CTGOV_API_BASE}/{nct_id}"
            response = self.session.get(url, timeout=30)

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            # Parse the response
            protocol = data.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            design_module = protocol.get("designModule", {})
            outcomes_module = protocol.get("outcomesModule", {})

            # Extract primary outcome
            primary_outcomes = outcomes_module.get("primaryOutcomes", [])
            primary_outcome = primary_outcomes[0].get("measure", "") if primary_outcomes else None

            # Extract secondary outcomes
            secondary_outcomes = [
                o.get("measure", "")
                for o in outcomes_module.get("secondaryOutcomes", [])
            ]

            # Extract enrollment
            enrollment_info = protocol.get("designModule", {}).get("enrollmentInfo", {})
            enrollment = enrollment_info.get("count")

            # Check if results posted
            has_results = data.get("hasResults", False)

            return RegistryRecord(
                nct_id=nct_id,
                registry=RegistrySource.CTGOV,
                title=id_module.get("briefTitle", ""),
                status=status_module.get("overallStatus", "UNKNOWN"),
                phase=design_module.get("phases", [None])[0] if design_module.get("phases") else None,
                enrollment=enrollment,
                primary_outcome=primary_outcome,
                secondary_outcomes=secondary_outcomes,
                start_date=status_module.get("startDateStruct", {}).get("date"),
                completion_date=status_module.get("completionDateStruct", {}).get("date"),
                results_posted=has_results,
                last_update=status_module.get("lastUpdatePostDateStruct", {}).get("date"),
                raw_data=data
            )

        except requests.RequestException as e:
            print(f"Error fetching {nct_id} from CT.gov: {e}")
            return None

    def search_ictrp(self, nct_id: str) -> Optional[RegistryRecord]:
        """
        Simulate WHO ICTRP search.
        In production, this would query the ICTRP API or web scraper.
        For now, returns simulated cross-registry data.
        """
        # Simulate ICTRP having most CT.gov trials with slight variations
        ctgov_record = self.search_ctgov(nct_id)
        if not ctgov_record:
            return None

        # Create ICTRP record (simulated cross-registry witness)
        return RegistryRecord(
            nct_id=nct_id,
            registry=RegistrySource.ICTRP,
            title=ctgov_record.title,
            status=ctgov_record.status,
            phase=ctgov_record.phase,
            enrollment=ctgov_record.enrollment,
            primary_outcome=ctgov_record.primary_outcome,
            secondary_outcomes=ctgov_record.secondary_outcomes,
            start_date=ctgov_record.start_date,
            completion_date=ctgov_record.completion_date,
            results_posted=ctgov_record.results_posted,
            last_update=ctgov_record.last_update,
            raw_data={"source": "ICTRP", "mirrored_from": "CT.gov"}
        )

    def search_all_registries(self, nct_id: str) -> List[RegistryRecord]:
        """Search multiple registries for the same trial"""
        records = []

        # Search CT.gov (primary)
        ctgov = self.search_ctgov(nct_id)
        if ctgov:
            records.append(ctgov)

        # Search ICTRP (secondary witness)
        ictrp = self.search_ictrp(nct_id)
        if ictrp:
            records.append(ictrp)

        return records


# =============================================================================
# TRUTHCERT VALIDATORS
# =============================================================================

class TruthCertValidator:
    """TruthCert TC-TRIALREG validators for registry integrity"""

    @staticmethod
    def v_reg_endpoint(registry: RegistryRecord, paper: PaperData) -> ValidationResult:
        """V-REG-ENDPOINT: Check primary outcome consistency"""
        if not paper.reported_primary_outcome or not registry.primary_outcome:
            return ValidationResult(
                validator_id="V-REG-ENDPOINT",
                validator_name="Primary Outcome Validation",
                status=ValidationStatus.UNKNOWN,
                confidence=0.0,
                message="Insufficient data to validate primary outcome",
                details={"registry": registry.primary_outcome, "paper": paper.reported_primary_outcome}
            )

        # Normalize and compare
        reg_outcome = registry.primary_outcome.lower().strip()
        paper_outcome = paper.reported_primary_outcome.lower().strip()

        # Check for exact or fuzzy match
        if reg_outcome == paper_outcome:
            return ValidationResult(
                validator_id="V-REG-ENDPOINT",
                validator_name="Primary Outcome Validation",
                status=ValidationStatus.PASS,
                confidence=1.0,
                message="Primary outcome matches exactly",
                details={"registry": registry.primary_outcome, "paper": paper.reported_primary_outcome}
            )

        # Check for partial match (endpoint switching detection)
        if any(word in paper_outcome for word in reg_outcome.split()[:3]):
            return ValidationResult(
                validator_id="V-REG-ENDPOINT",
                validator_name="Primary Outcome Validation",
                status=ValidationStatus.WARNING,
                confidence=0.6,
                message="Partial primary outcome match - potential endpoint modification",
                details={"registry": registry.primary_outcome, "paper": paper.reported_primary_outcome}
            )

        return ValidationResult(
            validator_id="V-REG-ENDPOINT",
            validator_name="Primary Outcome Validation",
            status=ValidationStatus.FAIL,
            confidence=0.9,
            message="PRIMARY OUTCOME MISMATCH - Possible endpoint switching",
            details={"registry": registry.primary_outcome, "paper": paper.reported_primary_outcome}
        )

    @staticmethod
    def v_reg_samplesize(registry: RegistryRecord, paper: PaperData) -> ValidationResult:
        """V-REG-SAMPLESIZE: Check sample size consistency"""
        if paper.reported_sample_size is None or registry.enrollment is None:
            return ValidationResult(
                validator_id="V-REG-SAMPLESIZE",
                validator_name="Sample Size Validation",
                status=ValidationStatus.UNKNOWN,
                confidence=0.0,
                message="Insufficient data to validate sample size",
                details={"registry": registry.enrollment, "paper": paper.reported_sample_size}
            )

        reg_n = registry.enrollment
        paper_n = paper.reported_sample_size

        # Calculate percentage difference
        if reg_n > 0:
            diff_pct = abs(paper_n - reg_n) / reg_n * 100
        else:
            diff_pct = 100 if paper_n > 0 else 0

        if diff_pct <= 5:
            return ValidationResult(
                validator_id="V-REG-SAMPLESIZE",
                validator_name="Sample Size Validation",
                status=ValidationStatus.PASS,
                confidence=0.95,
                message=f"Sample size matches within 5% (registry: {reg_n}, paper: {paper_n})",
                details={"registry": reg_n, "paper": paper_n, "difference_pct": diff_pct}
            )
        elif diff_pct <= 15:
            return ValidationResult(
                validator_id="V-REG-SAMPLESIZE",
                validator_name="Sample Size Validation",
                status=ValidationStatus.WARNING,
                confidence=0.7,
                message=f"Sample size differs by {diff_pct:.1f}% - may indicate protocol deviation",
                details={"registry": reg_n, "paper": paper_n, "difference_pct": diff_pct}
            )
        else:
            return ValidationResult(
                validator_id="V-REG-SAMPLESIZE",
                validator_name="Sample Size Validation",
                status=ValidationStatus.FAIL,
                confidence=0.9,
                message=f"SAMPLE SIZE MISMATCH - {diff_pct:.1f}% difference",
                details={"registry": reg_n, "paper": paper_n, "difference_pct": diff_pct}
            )

    @staticmethod
    def v_reg_timepoint(registry: RegistryRecord, paper: PaperData) -> ValidationResult:
        """V-REG-TIMEPOINT: Check follow-up duration consistency"""
        if not paper.reported_follow_up:
            return ValidationResult(
                validator_id="V-REG-TIMEPOINT",
                validator_name="Timepoint Validation",
                status=ValidationStatus.UNKNOWN,
                confidence=0.0,
                message="No follow-up duration reported in paper"
            )

        # Extract timepoint from registry primary outcome if available
        reg_timepoint = None
        if registry.primary_outcome:
            # Look for patterns like "at 12 weeks", "at 6 months"
            match = re.search(r'at\s+(\d+)\s*(weeks?|months?|years?)',
                            registry.primary_outcome, re.IGNORECASE)
            if match:
                reg_timepoint = f"{match.group(1)} {match.group(2)}"

        if not reg_timepoint:
            return ValidationResult(
                validator_id="V-REG-TIMEPOINT",
                validator_name="Timepoint Validation",
                status=ValidationStatus.UNKNOWN,
                confidence=0.0,
                message="No timepoint found in registry outcome definition",
                details={"paper_follow_up": paper.reported_follow_up}
            )

        # Compare timepoints
        if reg_timepoint.lower() in paper.reported_follow_up.lower():
            return ValidationResult(
                validator_id="V-REG-TIMEPOINT",
                validator_name="Timepoint Validation",
                status=ValidationStatus.PASS,
                confidence=0.85,
                message=f"Follow-up timepoint matches ({reg_timepoint})",
                details={"registry": reg_timepoint, "paper": paper.reported_follow_up}
            )

        return ValidationResult(
            validator_id="V-REG-TIMEPOINT",
            validator_name="Timepoint Validation",
            status=ValidationStatus.WARNING,
            confidence=0.6,
            message="Follow-up timepoint may differ",
            details={"registry": reg_timepoint, "paper": paper.reported_follow_up}
        )

    @staticmethod
    def v_reg_status(registry: RegistryRecord) -> ValidationResult:
        """V-REG-STATUS: Check study completion status"""
        if registry.status == "COMPLETED":
            return ValidationResult(
                validator_id="V-REG-STATUS",
                validator_name="Status Validation",
                status=ValidationStatus.PASS,
                confidence=0.95,
                message="Study marked as COMPLETED in registry"
            )
        elif registry.status in ["TERMINATED", "WITHDRAWN", "SUSPENDED"]:
            return ValidationResult(
                validator_id="V-REG-STATUS",
                validator_name="Status Validation",
                status=ValidationStatus.WARNING,
                confidence=0.8,
                message=f"Study status is {registry.status} - verify if paper reports this",
                details={"registry_status": registry.status}
            )
        else:
            return ValidationResult(
                validator_id="V-REG-STATUS",
                validator_name="Status Validation",
                status=ValidationStatus.WARNING,
                confidence=0.5,
                message=f"Study status is {registry.status} - may not be finalized",
                details={"registry_status": registry.status}
            )

    @staticmethod
    def v_reg_retract(paper: PaperData) -> ValidationResult:
        """V-REG-RETRACT: Check for paper retraction"""
        if paper.is_retracted:
            return ValidationResult(
                validator_id="V-REG-RETRACT",
                validator_name="Retraction Check",
                status=ValidationStatus.FAIL,
                confidence=1.0,
                message=f"PAPER RETRACTED on {paper.retraction_date or 'unknown date'}",
                details={"retraction_date": paper.retraction_date, "doi": paper.doi}
            )

        return ValidationResult(
            validator_id="V-REG-RETRACT",
            validator_name="Retraction Check",
            status=ValidationStatus.PASS,
            confidence=0.95,
            message="No retraction found"
        )

    @staticmethod
    def v_reg_duplicate(paper: PaperData, all_papers: List[PaperData]) -> ValidationResult:
        """V-REG-DUPLICATE: Check for duplicate publications"""
        if len(all_papers) <= 1:
            return ValidationResult(
                validator_id="V-REG-DUPLICATE",
                validator_name="Duplicate Check",
                status=ValidationStatus.PASS,
                confidence=0.9,
                message="No duplicate publications detected"
            )

        # Check if same NCT ID appears in multiple papers
        nct_counts = {}
        for p in all_papers:
            for nct in p.nct_ids:
                nct_counts[nct] = nct_counts.get(nct, 0) + 1

        duplicates = [nct for nct, count in nct_counts.items() if count > 1]

        if duplicates:
            return ValidationResult(
                validator_id="V-REG-DUPLICATE",
                validator_name="Duplicate Check",
                status=ValidationStatus.WARNING,
                confidence=0.7,
                message=f"Potential duplicate publications for NCT IDs: {', '.join(duplicates)}",
                details={"duplicate_ncts": duplicates}
            )

        return ValidationResult(
            validator_id="V-REG-DUPLICATE",
            validator_name="Duplicate Check",
            status=ValidationStatus.PASS,
            confidence=0.85,
            message="No duplicate publications detected"
        )

    @staticmethod
    def v_reg_results(registry: RegistryRecord) -> ValidationResult:
        """V-REG-RESULTS: Check if results are posted"""
        if registry.results_posted:
            return ValidationResult(
                validator_id="V-REG-RESULTS",
                validator_name="Results Availability",
                status=ValidationStatus.PASS,
                confidence=0.95,
                message="Results posted on registry"
            )

        return ValidationResult(
            validator_id="V-REG-RESULTS",
            validator_name="Results Availability",
            status=ValidationStatus.WARNING,
            confidence=0.6,
            message="No results posted on registry - verify against paper"
        )


# =============================================================================
# RECONCILIATION ENGINE
# =============================================================================

class ReconciliationEngine:
    """Engine for registry-paper reconciliation with TruthCert verification"""

    def __init__(self):
        self.searcher = RegistrySearcher()
        self.validator = TruthCertValidator()
        self.audit_ledger: List[AuditEntry] = []

    def reconcile(self, nct_id: str, paper: Optional[PaperData] = None) -> ReconciliationReport:
        """
        Perform full reconciliation for a trial.

        Args:
            nct_id: The NCT identifier
            paper: Optional paper data for registry-paper comparison

        Returns:
            ReconciliationReport with all validations and detected corruptions
        """
        # Step 1: Fetch from all registries (multi-witness)
        registry_records = self.searcher.search_all_registries(nct_id)

        if not registry_records:
            return ReconciliationReport(
                nct_id=nct_id,
                registry_records=[],
                paper_data=paper,
                validations=[ValidationResult(
                    validator_id="V-REG-FETCH",
                    validator_name="Registry Fetch",
                    status=ValidationStatus.FAIL,
                    confidence=1.0,
                    message=f"NCT ID {nct_id} not found in any registry"
                )],
                corruptions=[],
                overall_status="FAILED",
                agreement_score=0.0
            )

        primary_record = registry_records[0]  # CT.gov is primary
        validations = []
        corruptions = []

        # Step 2: Run TruthCert validators
        if paper:
            # V-REG-ENDPOINT
            endpoint_result = self.validator.v_reg_endpoint(primary_record, paper)
            validations.append(endpoint_result)
            if endpoint_result.status == ValidationStatus.FAIL:
                corruptions.append(CorruptionFlag(
                    corruption_type=CorruptionType.ENDPOINT_SWITCHING,
                    severity="HIGH",
                    field_name="primary_outcome",
                    registry_value=primary_record.primary_outcome,
                    paper_value=paper.reported_primary_outcome,
                    message="Primary outcome in paper does not match registry"
                ))

            # V-REG-SAMPLESIZE
            samplesize_result = self.validator.v_reg_samplesize(primary_record, paper)
            validations.append(samplesize_result)
            if samplesize_result.status == ValidationStatus.FAIL:
                corruptions.append(CorruptionFlag(
                    corruption_type=CorruptionType.SAMPLE_SIZE_MISMATCH,
                    severity="MEDIUM",
                    field_name="enrollment",
                    registry_value=primary_record.enrollment,
                    paper_value=paper.reported_sample_size,
                    message="Sample size in paper differs significantly from registry"
                ))

            # V-REG-TIMEPOINT
            timepoint_result = self.validator.v_reg_timepoint(primary_record, paper)
            validations.append(timepoint_result)
            if timepoint_result.status == ValidationStatus.FAIL:
                corruptions.append(CorruptionFlag(
                    corruption_type=CorruptionType.TIMEPOINT_MISMATCH,
                    severity="MEDIUM",
                    field_name="follow_up",
                    registry_value="See registry outcome",
                    paper_value=paper.reported_follow_up,
                    message="Follow-up timepoint does not match"
                ))

            # V-REG-RETRACT
            retract_result = self.validator.v_reg_retract(paper)
            validations.append(retract_result)
            if retract_result.status == ValidationStatus.FAIL:
                corruptions.append(CorruptionFlag(
                    corruption_type=CorruptionType.RETRACTED_PAPER,
                    severity="HIGH",
                    field_name="retraction",
                    registry_value="N/A",
                    paper_value="RETRACTED",
                    message="Paper has been retracted"
                ))

        # V-REG-STATUS (always run)
        status_result = self.validator.v_reg_status(primary_record)
        validations.append(status_result)

        # V-REG-RESULTS (always run)
        results_result = self.validator.v_reg_results(primary_record)
        validations.append(results_result)

        # Step 3: Calculate agreement score (Gate B5)
        pass_count = sum(1 for v in validations if v.status == ValidationStatus.PASS)
        total_validations = len([v for v in validations if v.status != ValidationStatus.UNKNOWN])
        agreement_score = pass_count / total_validations if total_validations > 0 else 0.0

        # Step 4: Determine overall status
        if any(c.severity == "HIGH" for c in corruptions):
            overall_status = "FAILED"
        elif agreement_score >= AGREEMENT_THRESHOLD:
            overall_status = "VERIFIED"
        else:
            overall_status = "DISCREPANCY"

        # Create report
        report = ReconciliationReport(
            nct_id=nct_id,
            registry_records=registry_records,
            paper_data=paper,
            validations=validations,
            corruptions=corruptions,
            overall_status=overall_status,
            agreement_score=agreement_score
        )

        # Step 5: Log to audit ledger
        self._log_to_ledger(nct_id, overall_status, report.bundle_hash)

        return report

    def _log_to_ledger(self, nct_id: str, result: str, bundle_hash: str):
        """Add entry to immutable audit ledger"""
        entry_id = f"TC-{int(time.time())}-{len(self.audit_ledger):04d}"
        previous_hash = self.audit_ledger[-1].compute_chain_hash() if self.audit_ledger else "GENESIS"

        entry = AuditEntry(
            entry_id=entry_id,
            action="RECONCILE",
            nct_id=nct_id,
            result=result,
            bundle_hash=bundle_hash,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            previous_hash=previous_hash
        )

        self.audit_ledger.append(entry)

    def batch_reconcile(self, nct_ids: List[str], papers: Optional[Dict[str, PaperData]] = None) -> List[ReconciliationReport]:
        """Reconcile multiple trials"""
        reports = []
        for nct_id in nct_ids:
            paper = papers.get(nct_id) if papers else None
            report = self.reconcile(nct_id, paper)
            reports.append(report)
            time.sleep(0.5)  # Rate limiting
        return reports

    def export_audit_ledger(self) -> Dict:
        """Export audit ledger as JSON"""
        return {
            "ledger": [asdict(entry) for entry in self.audit_ledger],
            "chain_valid": self._verify_chain(),
            "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

    def _verify_chain(self) -> bool:
        """Verify integrity of audit ledger chain"""
        for i, entry in enumerate(self.audit_ledger):
            if i == 0:
                if entry.previous_hash != "GENESIS":
                    return False
            else:
                expected_prev = self.audit_ledger[i-1].compute_chain_hash()
                if entry.previous_hash != expected_prev:
                    return False
        return True


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_markdown_report(report: ReconciliationReport) -> str:
    """Generate markdown report from reconciliation"""
    lines = [
        f"# TruthCert TC-TRIALREG Reconciliation Report",
        f"## NCT ID: {report.nct_id}",
        f"",
        f"**Status:** {report.overall_status}",
        f"**Agreement Score:** {report.agreement_score:.1%}",
        f"**Bundle Hash:** `{report.bundle_hash}`",
        f"**Generated:** {report.timestamp}",
        f"",
        f"---",
        f"",
        f"## Registry Records",
        f""
    ]

    for rec in report.registry_records:
        lines.extend([
            f"### {rec.registry.value}",
            f"- **Title:** {rec.title}",
            f"- **Status:** {rec.status}",
            f"- **Phase:** {rec.phase or 'Not specified'}",
            f"- **Enrollment:** {rec.enrollment or 'Not specified'}",
            f"- **Results Posted:** {'Yes' if rec.results_posted else 'No'}",
            f""
        ])

    lines.extend([
        f"---",
        f"",
        f"## Validation Results",
        f"",
        f"| Validator | Status | Confidence | Message |",
        f"|-----------|--------|------------|---------|"
    ])

    for v in report.validations:
        status_icon = {"PASS": "✓", "FAIL": "✗", "WARNING": "⚠", "UNKNOWN": "?"}[v.status.value]
        lines.append(f"| {v.validator_id} | {status_icon} {v.status.value} | {v.confidence:.0%} | {v.message} |")

    if report.corruptions:
        lines.extend([
            f"",
            f"---",
            f"",
            f"## ⚠ Detected Corruptions",
            f""
        ])

        for c in report.corruptions:
            lines.extend([
                f"### {c.corruption_type.value.upper()}",
                f"- **Severity:** {c.severity}",
                f"- **Field:** {c.field_name}",
                f"- **Registry Value:** {c.registry_value}",
                f"- **Paper Value:** {c.paper_value}",
                f"- **Message:** {c.message}",
                f""
            ])

    lines.extend([
        f"---",
        f"",
        f"*Report generated by TruthCert TC-TRIALREG v4.0*"
    ])

    return "\n".join(lines)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="TruthCert TC-TRIALREG Registry Reconciliation Engine"
    )
    parser.add_argument("nct_ids", nargs="+", help="NCT IDs to reconcile")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json",
                       help="Output format (default: json)")
    parser.add_argument("--paper-sample-size", type=int,
                       help="Reported sample size from paper")
    parser.add_argument("--paper-outcome",
                       help="Reported primary outcome from paper")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Verbose output")

    args = parser.parse_args()

    engine = ReconciliationEngine()

    # Create paper data if provided
    paper = None
    if args.paper_sample_size or args.paper_outcome:
        paper = PaperData(
            reported_sample_size=args.paper_sample_size,
            reported_primary_outcome=args.paper_outcome,
            nct_ids=args.nct_ids
        )

    # Run reconciliation
    reports = []
    for nct_id in args.nct_ids:
        if args.verbose:
            print(f"Reconciling {nct_id}...")

        report = engine.reconcile(nct_id, paper)
        reports.append(report)

        if args.verbose:
            print(f"  Status: {report.overall_status}")
            print(f"  Agreement: {report.agreement_score:.1%}")
            print(f"  Corruptions: {len(report.corruptions)}")

    # Output results
    if args.format == "markdown":
        output = "\n\n".join(generate_markdown_report(r) for r in reports)
    else:
        output = json.dumps({
            "reports": [asdict(r) for r in reports],
            "audit_ledger": engine.export_audit_ledger()
        }, indent=2, default=str)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
