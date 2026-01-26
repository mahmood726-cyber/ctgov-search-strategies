#!/usr/bin/env python3
"""
API Versioning and Response Archiving Module

Addresses editorial concern: "Archive API Responses"
- Timestamps all validation runs
- Archives raw API responses
- Documents API version used
- Enables full reproducibility

Author: CT.gov Search Strategy Team
Version: 1.0
"""

import json
import hashlib
import gzip
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import requests


@dataclass
class APICallRecord:
    """Record of a single API call for auditing."""
    timestamp: str
    api_version: str
    endpoint: str
    query_params: Dict[str, Any]
    response_status: int
    response_hash: str
    result_count: int
    execution_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class APIVersioningManager:
    """
    Manages API versioning, response archiving, and reproducibility.

    Features:
    - Archives all API responses with timestamps
    - Computes response hashes for integrity verification
    - Tracks API version changes over time
    - Enables exact reproduction of validation runs

    Usage:
        manager = APIVersioningManager("output/api_archive")

        # Record an API call
        manager.record_call(
            endpoint="https://clinicaltrials.gov/api/v2/studies",
            params={"query.intr": "semaglutide"},
            response=response_json,
            execution_time=1.23
        )

        # Get session manifest
        manifest = manager.get_session_manifest()
    """

    CTGOV_API_VERSION = "v2"
    CTGOV_API_BASE = "https://clinicaltrials.gov/api/v2"

    def __init__(self, archive_dir: str = "output/api_archive"):
        """Initialize the versioning manager."""
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        # Session tracking
        self.session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.archive_dir / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Call records for this session
        self.call_records: List[APICallRecord] = []

        # Initialize session manifest
        self._init_session_manifest()

    def _init_session_manifest(self) -> None:
        """Initialize session manifest with environment info."""
        import platform
        import sys

        self.manifest = {
            "session_id": self.session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "api_version": self.CTGOV_API_VERSION,
            "api_base_url": self.CTGOV_API_BASE,
            "environment": {
                "python_version": sys.version,
                "platform": platform.platform(),
                "machine": platform.machine(),
            },
            "dependencies": self._get_dependency_versions(),
            "calls": [],
            "summary": {
                "total_calls": 0,
                "total_results": 0,
                "unique_queries": 0,
            }
        }

    def _get_dependency_versions(self) -> Dict[str, str]:
        """Get versions of key dependencies."""
        versions = {}
        try:
            import requests
            versions["requests"] = requests.__version__
        except:
            pass
        try:
            import numpy
            versions["numpy"] = numpy.__version__
        except:
            pass
        try:
            import scipy
            versions["scipy"] = scipy.__version__
        except:
            pass
        return versions

    def _compute_hash(self, data: Any) -> str:
        """Compute SHA-256 hash of data for integrity verification."""
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

    def record_call(
        self,
        endpoint: str,
        params: Dict[str, Any],
        response: Dict[str, Any],
        execution_time: float,
        archive_response: bool = True
    ) -> APICallRecord:
        """
        Record an API call with full details.

        Args:
            endpoint: API endpoint URL
            params: Query parameters used
            response: Response JSON data
            execution_time: Time taken in seconds
            archive_response: Whether to archive full response

        Returns:
            APICallRecord with call details
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        response_hash = self._compute_hash(response)
        result_count = response.get("totalCount", len(response.get("studies", [])))

        record = APICallRecord(
            timestamp=timestamp,
            api_version=self.CTGOV_API_VERSION,
            endpoint=endpoint,
            query_params=params,
            response_status=200,  # Assuming success if we have response
            response_hash=response_hash,
            result_count=result_count,
            execution_ms=execution_time * 1000
        )

        self.call_records.append(record)
        self.manifest["calls"].append(record.to_dict())
        self.manifest["summary"]["total_calls"] += 1
        self.manifest["summary"]["total_results"] += result_count

        # Archive response if requested
        if archive_response:
            self._archive_response(record, response)

        return record

    def _archive_response(self, record: APICallRecord, response: Dict[str, Any]) -> None:
        """Archive API response with compression."""
        # Create filename from hash
        filename = f"{record.response_hash}_{record.timestamp.replace(':', '-')}.json.gz"
        filepath = self.session_dir / filename

        # Compress and save
        with gzip.open(filepath, 'wt', encoding='utf-8') as f:
            json.dump({
                "metadata": record.to_dict(),
                "response": response
            }, f, indent=2, default=str)

    def get_session_manifest(self) -> Dict[str, Any]:
        """Get the session manifest with all call records."""
        # Update unique queries count
        unique_queries = set()
        for record in self.call_records:
            query_key = json.dumps(record.query_params, sort_keys=True)
            unique_queries.add(query_key)
        self.manifest["summary"]["unique_queries"] = len(unique_queries)

        return self.manifest

    def save_session_manifest(self) -> Path:
        """Save the session manifest to disk."""
        manifest = self.get_session_manifest()
        manifest["finalized_at"] = datetime.now(timezone.utc).isoformat()

        manifest_path = self.session_dir / "manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, default=str)

        return manifest_path

    def verify_response_integrity(self, response_file: Path) -> bool:
        """Verify integrity of archived response."""
        with gzip.open(response_file, 'rt', encoding='utf-8') as f:
            data = json.load(f)

        stored_hash = data["metadata"]["response_hash"]
        computed_hash = self._compute_hash(data["response"])

        return stored_hash == computed_hash


class ReproducibleValidator:
    """
    Wrapper for validation runs that ensures reproducibility.

    Usage:
        with ReproducibleValidator("my_validation") as validator:
            results = validator.run_validation(drugs, gold_standard)
    """

    def __init__(self, name: str, archive_dir: str = "output/api_archive"):
        self.name = name
        self.archive_dir = archive_dir
        self.versioning = None

    def __enter__(self):
        self.versioning = APIVersioningManager(self.archive_dir)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.versioning:
            manifest_path = self.versioning.save_session_manifest()
            print(f"Session manifest saved: {manifest_path}")
        return False

    def search_with_archiving(
        self,
        session: requests.Session,
        url: str,
        params: Dict[str, Any],
        timeout: int = 60
    ) -> Dict[str, Any]:
        """Execute search and archive response."""
        import time

        start = time.time()
        response = session.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        execution_time = time.time() - start

        data = response.json()

        self.versioning.record_call(
            endpoint=url,
            params=params,
            response=data,
            execution_time=execution_time
        )

        return data


def create_validation_certificate(
    validation_name: str,
    results: Dict[str, Any],
    manifest_path: Path
) -> Dict[str, Any]:
    """
    Create a validation certificate for publication.

    This certificate provides cryptographic proof of validation integrity.
    """
    certificate = {
        "certificate_version": "1.0",
        "validation_name": validation_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "api_version": APIVersioningManager.CTGOV_API_VERSION,
        "manifest_path": str(manifest_path),
        "results_hash": hashlib.sha256(
            json.dumps(results, sort_keys=True, default=str).encode()
        ).hexdigest(),
        "verification_instructions": [
            "1. Load the manifest from manifest_path",
            "2. Verify each archived response hash matches",
            "3. Re-run validation using archived responses",
            "4. Compare results_hash with computed hash"
        ]
    }

    return certificate


if __name__ == "__main__":
    # Demo usage
    print("API Versioning Module Demo")
    print("=" * 50)

    manager = APIVersioningManager()

    # Simulate an API call
    sample_response = {
        "totalCount": 150,
        "studies": [{"nctId": "NCT00000001"}]
    }

    record = manager.record_call(
        endpoint="https://clinicaltrials.gov/api/v2/studies",
        params={"query.intr": "semaglutide"},
        response=sample_response,
        execution_time=0.5
    )

    print(f"Recorded call: {record.response_hash}")

    manifest_path = manager.save_session_manifest()
    print(f"Manifest saved: {manifest_path}")

    manifest = manager.get_session_manifest()
    print(f"\nSession Summary:")
    print(f"  API Version: {manifest['api_version']}")
    print(f"  Total Calls: {manifest['summary']['total_calls']}")
    print(f"  Total Results: {manifest['summary']['total_results']}")
