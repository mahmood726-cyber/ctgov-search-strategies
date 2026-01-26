"""
AACT Database Validator - Enhanced Module

Provides comprehensive validation of NCT IDs and search strategies against
the AACT (Aggregate Analysis of ClinicalTrials.gov) PostgreSQL database.

Builds on aact_validation.py with added features:
- Batch validation with caching
- Strategy validation metrics
- Integration with expanded_nct_dataset
- Multiple connection modes (DB, API, cache)

Usage:
    from tests.validation_data import AACTValidator

    validator = AACTValidator()
    results = validator.validate_nct_ids(["NCT00000001", "NCT00000002"])
    print(f"Valid: {sum(1 for r in results if r.exists)}")
"""

import os
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Tuple
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ValidationSource(Enum):
    """Source of validation."""
    AACT_DATABASE = "aact_database"
    CTGOV_API = "clinicaltrials_gov_api"
    LOCAL_DATASET = "local_dataset"
    CACHE = "cached"


@dataclass
class ValidatedStudy:
    """Validated study with metadata."""
    nct_id: str
    exists: bool
    source: ValidationSource
    title: str = ""
    status: str = ""
    phase: str = ""
    conditions: List[str] = field(default_factory=list)
    study_type: str = ""
    enrollment: int = 0
    allocation: str = ""
    validation_time: float = 0.0
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nct_id": self.nct_id,
            "exists": self.exists,
            "source": self.source.value,
            "title": self.title,
            "status": self.status,
            "phase": self.phase,
            "conditions": self.conditions,
            "study_type": self.study_type,
            "enrollment": self.enrollment,
            "error": self.error,
        }


@dataclass
class ValidationSummary:
    """Summary of batch validation."""
    total: int
    valid: int
    invalid: int
    errors: int
    valid_rate: float
    validation_time: float
    by_source: Dict[str, int] = field(default_factory=dict)
    invalid_ids: List[str] = field(default_factory=list)
    error_ids: List[str] = field(default_factory=list)


class AACTValidator:
    """
    Enhanced AACT database validator with multiple connection modes.

    Supports:
    - Direct PostgreSQL connection to AACT
    - ClinicalTrials.gov API fallback
    - Local dataset validation
    - Result caching

    Example:
        validator = AACTValidator()

        # Validate NCT IDs
        results = validator.validate_nct_ids(nct_list)

        # Get summary
        summary = validator.get_validation_summary(results)
        print(f"Valid: {summary.valid}/{summary.total}")
    """

    # AACT connection defaults
    DEFAULT_HOST = "aact-db.ctti-clinicaltrials.org"
    DEFAULT_PORT = 5432
    DEFAULT_DATABASE = "aact"

    def __init__(
        self,
        user: str = None,
        password: str = None,
        use_api_fallback: bool = True,
        use_local_dataset: bool = True,
        cache_results: bool = True,
    ):
        """
        Initialize validator.

        Args:
            user: AACT username (or AACT_USER env var)
            password: AACT password (or AACT_PASSWORD env var)
            use_api_fallback: Fall back to CT.gov API if DB unavailable
            use_local_dataset: Use local validation dataset
            cache_results: Cache validation results
        """
        self.user = user or os.environ.get("AACT_USER")
        self.password = password or os.environ.get("AACT_PASSWORD")
        self.use_api_fallback = use_api_fallback
        self.use_local_dataset = use_local_dataset
        self.cache_results = cache_results

        self._connection = None
        self._cache: Dict[str, ValidatedStudy] = {}
        self._local_ncts: Optional[Set[str]] = None

        # Try to load local dataset
        if use_local_dataset:
            self._load_local_dataset()

    def _load_local_dataset(self):
        """Load NCT IDs from local expanded dataset."""
        try:
            from .expanded_nct_dataset import get_all_nct_ids
            self._local_ncts = set(get_all_nct_ids())
            logger.info(f"Loaded {len(self._local_ncts)} NCT IDs from local dataset")
        except ImportError:
            logger.warning("Could not load local dataset")
            self._local_ncts = set()

    def _get_db_connection(self):
        """Get or create database connection."""
        if not self.user or not self.password:
            return None

        try:
            import psycopg2
        except ImportError:
            logger.warning("psycopg2 not available")
            return None

        if self._connection is None or self._connection.closed:
            try:
                self._connection = psycopg2.connect(
                    host=self.DEFAULT_HOST,
                    port=self.DEFAULT_PORT,
                    database=self.DEFAULT_DATABASE,
                    user=self.user,
                    password=self.password,
                )
            except Exception as e:
                logger.error(f"Database connection failed: {e}")
                return None

        return self._connection

    def close(self):
        """Close database connection."""
        if self._connection and not self._connection.closed:
            self._connection.close()
            self._connection = None

    def validate_nct_id(self, nct_id: str) -> ValidatedStudy:
        """
        Validate a single NCT ID.

        Tries in order:
        1. Cache
        2. AACT database
        3. CT.gov API
        4. Local dataset

        Args:
            nct_id: NCT ID to validate

        Returns:
            ValidatedStudy result
        """
        nct_id = nct_id.strip().upper()
        start_time = time.time()

        # Check cache
        if nct_id in self._cache:
            cached = self._cache[nct_id]
            cached.source = ValidationSource.CACHE
            return cached

        # Try AACT database
        result = self._validate_via_aact(nct_id)
        if result and result.exists:
            result.validation_time = time.time() - start_time
            if self.cache_results:
                self._cache[nct_id] = result
            return result

        # Try CT.gov API
        if self.use_api_fallback:
            result = self._validate_via_api(nct_id)
            if result and result.exists:
                result.validation_time = time.time() - start_time
                if self.cache_results:
                    self._cache[nct_id] = result
                return result

        # Try local dataset
        if self.use_local_dataset and self._local_ncts:
            if nct_id in self._local_ncts:
                result = ValidatedStudy(
                    nct_id=nct_id,
                    exists=True,
                    source=ValidationSource.LOCAL_DATASET,
                    validation_time=time.time() - start_time,
                )
                if self.cache_results:
                    self._cache[nct_id] = result
                return result

        # Not found
        result = ValidatedStudy(
            nct_id=nct_id,
            exists=False,
            source=ValidationSource.LOCAL_DATASET,
            validation_time=time.time() - start_time,
        )
        return result

    def _validate_via_aact(self, nct_id: str) -> Optional[ValidatedStudy]:
        """Validate via AACT database."""
        conn = self._get_db_connection()
        if not conn:
            return None

        try:
            import psycopg2.extras
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            cursor.execute("""
                SELECT s.nct_id, s.brief_title, s.overall_status,
                       s.phase, s.study_type, s.enrollment,
                       d.allocation
                FROM ctgov.studies s
                LEFT JOIN ctgov.designs d ON s.nct_id = d.nct_id
                WHERE s.nct_id = %s
            """, (nct_id,))

            row = cursor.fetchone()

            if row:
                # Get conditions
                cursor.execute(
                    "SELECT name FROM ctgov.conditions WHERE nct_id = %s",
                    (nct_id,)
                )
                conditions = [r["name"] for r in cursor.fetchall()]

                cursor.close()
                return ValidatedStudy(
                    nct_id=nct_id,
                    exists=True,
                    source=ValidationSource.AACT_DATABASE,
                    title=row["brief_title"] or "",
                    status=row["overall_status"] or "",
                    phase=row["phase"] or "",
                    study_type=row["study_type"] or "",
                    enrollment=row["enrollment"] or 0,
                    allocation=row["allocation"] or "",
                    conditions=conditions,
                )

            cursor.close()
            return ValidatedStudy(
                nct_id=nct_id,
                exists=False,
                source=ValidationSource.AACT_DATABASE,
            )

        except Exception as e:
            logger.error(f"AACT query error: {e}")
            return None

    def _validate_via_api(self, nct_id: str) -> Optional[ValidatedStudy]:
        """Validate via ClinicalTrials.gov API."""
        try:
            import requests
        except ImportError:
            return None

        try:
            url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"
            response = requests.get(url, timeout=30)

            if response.status_code == 200:
                data = response.json()
                protocol = data.get("protocolSection", {})
                ident = protocol.get("identificationModule", {})
                status_mod = protocol.get("statusModule", {})
                design_mod = protocol.get("designModule", {})
                conditions_mod = protocol.get("conditionsModule", {})

                return ValidatedStudy(
                    nct_id=nct_id,
                    exists=True,
                    source=ValidationSource.CTGOV_API,
                    title=ident.get("briefTitle", ""),
                    status=status_mod.get("overallStatus", ""),
                    phase=design_mod.get("phases", [""])[0] if design_mod.get("phases") else "",
                    study_type=design_mod.get("studyType", ""),
                    conditions=conditions_mod.get("conditions", []),
                )

            elif response.status_code == 404:
                return ValidatedStudy(
                    nct_id=nct_id,
                    exists=False,
                    source=ValidationSource.CTGOV_API,
                )

        except Exception as e:
            logger.error(f"API error for {nct_id}: {e}")

        return None

    def validate_nct_ids(self, nct_ids: List[str]) -> List[ValidatedStudy]:
        """
        Validate multiple NCT IDs.

        Uses batch database queries when possible for efficiency.

        Args:
            nct_ids: List of NCT IDs

        Returns:
            List of ValidatedStudy results
        """
        nct_ids = [nct.strip().upper() for nct in nct_ids]
        results = []

        # Check cache first
        uncached = []
        for nct_id in nct_ids:
            if nct_id in self._cache:
                results.append(self._cache[nct_id])
            else:
                uncached.append(nct_id)

        if not uncached:
            return results

        # Try batch AACT query
        conn = self._get_db_connection()
        if conn:
            try:
                batch_results = self._batch_validate_aact(uncached)
                for nct_id in uncached:
                    if nct_id in batch_results:
                        results.append(batch_results[nct_id])
                        if self.cache_results:
                            self._cache[nct_id] = batch_results[nct_id]
                    else:
                        # Not in AACT, try other sources
                        result = self.validate_nct_id(nct_id)
                        results.append(result)
            except Exception as e:
                logger.error(f"Batch validation error: {e}")
                # Fall back to individual validation
                for nct_id in uncached:
                    results.append(self.validate_nct_id(nct_id))
        else:
            # No DB connection, validate individually
            for nct_id in uncached:
                results.append(self.validate_nct_id(nct_id))

        return results

    def _batch_validate_aact(self, nct_ids: List[str]) -> Dict[str, ValidatedStudy]:
        """Batch validate via AACT."""
        conn = self._get_db_connection()
        if not conn:
            return {}

        try:
            import psycopg2.extras
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            cursor.execute("""
                SELECT s.nct_id, s.brief_title, s.overall_status,
                       s.phase, s.study_type, s.enrollment
                FROM ctgov.studies s
                WHERE s.nct_id = ANY(%s)
            """, (nct_ids,))

            results = {}
            for row in cursor.fetchall():
                nct_id = row["nct_id"]
                results[nct_id] = ValidatedStudy(
                    nct_id=nct_id,
                    exists=True,
                    source=ValidationSource.AACT_DATABASE,
                    title=row["brief_title"] or "",
                    status=row["overall_status"] or "",
                    phase=row["phase"] or "",
                    study_type=row["study_type"] or "",
                    enrollment=row["enrollment"] or 0,
                )

            cursor.close()
            return results

        except Exception as e:
            logger.error(f"Batch AACT error: {e}")
            return {}

    def get_validation_summary(self, results: List[ValidatedStudy]) -> ValidationSummary:
        """
        Generate summary statistics from validation results.

        Args:
            results: List of ValidatedStudy results

        Returns:
            ValidationSummary with statistics
        """
        total = len(results)
        valid = sum(1 for r in results if r.exists)
        invalid = sum(1 for r in results if not r.exists and not r.error)
        errors = sum(1 for r in results if r.error)

        by_source = {}
        for r in results:
            if r.exists:
                source = r.source.value
                by_source[source] = by_source.get(source, 0) + 1

        total_time = sum(r.validation_time for r in results)

        return ValidationSummary(
            total=total,
            valid=valid,
            invalid=invalid,
            errors=errors,
            valid_rate=valid / total if total > 0 else 0.0,
            validation_time=total_time,
            by_source=by_source,
            invalid_ids=[r.nct_id for r in results if not r.exists and not r.error],
            error_ids=[r.nct_id for r in results if r.error],
        )

    def validate_against_expanded_dataset(self) -> ValidationSummary:
        """
        Validate all NCT IDs from the expanded local dataset.

        Returns:
            ValidationSummary for the entire dataset
        """
        try:
            from .expanded_nct_dataset import get_all_nct_ids
            all_ids = get_all_nct_ids()
        except ImportError:
            logger.error("Could not import expanded dataset")
            return ValidationSummary(
                total=0, valid=0, invalid=0, errors=1,
                valid_rate=0.0, validation_time=0.0
            )

        logger.info(f"Validating {len(all_ids)} NCT IDs from expanded dataset")
        results = self.validate_nct_ids(all_ids)
        return self.get_validation_summary(results)

    def export_results(
        self,
        results: List[ValidatedStudy],
        output_path: str,
        format: str = "json"
    ) -> str:
        """
        Export validation results.

        Args:
            results: List of ValidatedStudy results
            output_path: Output file path
            format: Output format ("json" or "csv")

        Returns:
            Path to output file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            data = {
                "timestamp": datetime.now().isoformat(),
                "summary": self.get_validation_summary(results).__dict__,
                "results": [r.to_dict() for r in results],
            }
            with open(output_path, "w") as f:
                json.dump(data, f, indent=2)

        elif format == "csv":
            import csv
            with open(output_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "nct_id", "exists", "source", "title", "status", "phase"
                ])
                writer.writeheader()
                for r in results:
                    writer.writerow({
                        "nct_id": r.nct_id,
                        "exists": r.exists,
                        "source": r.source.value,
                        "title": r.title[:100] if r.title else "",
                        "status": r.status,
                        "phase": r.phase,
                    })

        return str(output_path)


# Convenience functions
def quick_validate(nct_ids: List[str]) -> Tuple[int, int]:
    """
    Quick validation without detailed results.

    Args:
        nct_ids: List of NCT IDs

    Returns:
        Tuple of (valid_count, total_count)
    """
    validator = AACTValidator()
    results = validator.validate_nct_ids(nct_ids)
    validator.close()

    valid = sum(1 for r in results if r.exists)
    return valid, len(results)


def validate_expanded_dataset() -> Dict[str, Any]:
    """
    Validate the entire expanded dataset.

    Returns:
        Dictionary with validation summary
    """
    validator = AACTValidator()
    summary = validator.validate_against_expanded_dataset()
    validator.close()

    return {
        "total": summary.total,
        "valid": summary.valid,
        "valid_rate": f"{summary.valid_rate:.1%}",
        "by_source": summary.by_source,
        "invalid_ids": summary.invalid_ids[:20],
    }


if __name__ == "__main__":
    # Quick test
    print("AACT Validator Test")
    print("=" * 50)

    validator = AACTValidator()

    # Test with sample NCT IDs
    test_ids = [
        "NCT00000001",
        "NCT00000149",
        "NCT03702452",
        "NCT99999999",  # Invalid
    ]

    print(f"\nValidating {len(test_ids)} NCT IDs...")
    results = validator.validate_nct_ids(test_ids)

    for r in results:
        status = "VALID" if r.exists else "INVALID"
        print(f"  {r.nct_id}: {status} ({r.source.value})")

    summary = validator.get_validation_summary(results)
    print(f"\nSummary: {summary.valid}/{summary.total} valid ({summary.valid_rate:.0%})")

    validator.close()
