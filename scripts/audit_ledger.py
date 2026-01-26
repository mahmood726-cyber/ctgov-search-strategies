#!/usr/bin/env python3
"""
TruthCert TC-TRIALREG Audit Ledger System
Immutable audit trail for registry integrity verification

This module provides:
- Persistent audit ledger with cryptographic chain
- Chain integrity verification
- Report generation (JSON, Markdown, HTML)
- Summary statistics and analytics
- Export and backup capabilities

Author: Mahmood Ahmad
Version: 4.0
License: MIT
"""

import json
import hashlib
import os
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any
from pathlib import Path
from enum import Enum


# =============================================================================
# DATA CLASSES
# =============================================================================

class AuditAction(Enum):
    """Types of audit actions"""
    SEARCH = "SEARCH"
    VALIDATE = "VALIDATE"
    RECONCILE = "RECONCILE"
    CERTIFY = "CERTIFY"
    EXPORT = "EXPORT"


class AuditResult(Enum):
    """Audit action results"""
    SUCCESS = "SUCCESS"
    VERIFIED = "VERIFIED"
    DISCREPANCY = "DISCREPANCY"
    FAILED = "FAILED"
    WARNING = "WARNING"


@dataclass
class AuditEntry:
    """Single entry in the audit ledger"""
    entry_id: str
    action: AuditAction
    nct_id: str
    result: AuditResult
    bundle_hash: str
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    previous_hash: str = ""
    chain_hash: str = ""

    def compute_chain_hash(self) -> str:
        """Compute hash for ledger chain integrity"""
        content = json.dumps({
            "previous_hash": self.previous_hash,
            "entry_id": self.entry_id,
            "action": self.action.value,
            "nct_id": self.nct_id,
            "result": self.result.value,
            "bundle_hash": self.bundle_hash,
            "timestamp": self.timestamp
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "entry_id": self.entry_id,
            "action": self.action.value,
            "nct_id": self.nct_id,
            "result": self.result.value,
            "bundle_hash": self.bundle_hash,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "previous_hash": self.previous_hash,
            "chain_hash": self.chain_hash
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'AuditEntry':
        """Create AuditEntry from dictionary"""
        return cls(
            entry_id=data["entry_id"],
            action=AuditAction(data["action"]),
            nct_id=data["nct_id"],
            result=AuditResult(data["result"]),
            bundle_hash=data["bundle_hash"],
            timestamp=data["timestamp"],
            metadata=data.get("metadata", {}),
            previous_hash=data.get("previous_hash", ""),
            chain_hash=data.get("chain_hash", "")
        )


@dataclass
class LedgerStats:
    """Statistics about the audit ledger"""
    total_entries: int
    verified_count: int
    discrepancy_count: int
    failed_count: int
    unique_trials: int
    first_entry: Optional[str]
    last_entry: Optional[str]
    chain_valid: bool


# =============================================================================
# AUDIT LEDGER CLASS
# =============================================================================

class TruthCertAuditLedger:
    """
    Immutable audit ledger for TruthCert TC-TRIALREG verifications.

    Features:
    - Append-only ledger with cryptographic chain
    - Persistent storage to JSON file
    - Chain integrity verification
    - Statistics and analytics
    """

    GENESIS_HASH = "TC-GENESIS-000"

    def __init__(self, ledger_path: Optional[str] = None):
        """
        Initialize audit ledger.

        Args:
            ledger_path: Path to ledger JSON file. If None, uses in-memory only.
        """
        self.ledger_path = Path(ledger_path) if ledger_path else None
        self.entries: List[AuditEntry] = []
        self._entry_counter = 0

        if self.ledger_path and self.ledger_path.exists():
            self._load_ledger()

    def _load_ledger(self):
        """Load ledger from file"""
        try:
            with open(self.ledger_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.entries = [AuditEntry.from_dict(e) for e in data.get("entries", [])]
                self._entry_counter = data.get("counter", len(self.entries))
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not load ledger: {e}")
            self.entries = []

    def _save_ledger(self):
        """Save ledger to file"""
        if not self.ledger_path:
            return

        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "4.0",
            "protocol": "TC-TRIALREG",
            "counter": self._entry_counter,
            "entries": [e.to_dict() for e in self.entries],
            "last_saved": datetime.now(timezone.utc).isoformat()
        }

        with open(self.ledger_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def add_entry(
        self,
        action: AuditAction,
        nct_id: str,
        result: AuditResult,
        bundle_hash: str,
        metadata: Optional[Dict] = None
    ) -> AuditEntry:
        """
        Add a new entry to the ledger.

        Args:
            action: The audit action performed
            nct_id: NCT identifier
            result: Result of the action
            bundle_hash: Hash of the verification bundle
            metadata: Optional additional metadata

        Returns:
            The created AuditEntry
        """
        self._entry_counter += 1
        entry_id = f"TC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{self._entry_counter:04d}"

        # Get previous hash for chain
        previous_hash = self.entries[-1].chain_hash if self.entries else self.GENESIS_HASH

        entry = AuditEntry(
            entry_id=entry_id,
            action=action,
            nct_id=nct_id,
            result=result,
            bundle_hash=bundle_hash,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
            previous_hash=previous_hash
        )

        # Compute and set chain hash
        entry.chain_hash = entry.compute_chain_hash()

        self.entries.append(entry)
        self._save_ledger()

        return entry

    def verify_chain(self) -> tuple[bool, Optional[int]]:
        """
        Verify the integrity of the ledger chain.

        Returns:
            Tuple of (is_valid, first_invalid_index)
        """
        for i, entry in enumerate(self.entries):
            # Check previous hash
            if i == 0:
                expected_prev = self.GENESIS_HASH
            else:
                expected_prev = self.entries[i - 1].chain_hash

            if entry.previous_hash != expected_prev:
                return False, i

            # Verify chain hash
            computed = entry.compute_chain_hash()
            if entry.chain_hash != computed:
                return False, i

        return True, None

    def get_stats(self) -> LedgerStats:
        """Get statistics about the ledger"""
        verified = sum(1 for e in self.entries if e.result == AuditResult.VERIFIED)
        discrepancy = sum(1 for e in self.entries if e.result == AuditResult.DISCREPANCY)
        failed = sum(1 for e in self.entries if e.result == AuditResult.FAILED)
        unique_trials = len(set(e.nct_id for e in self.entries))

        chain_valid, _ = self.verify_chain()

        return LedgerStats(
            total_entries=len(self.entries),
            verified_count=verified,
            discrepancy_count=discrepancy,
            failed_count=failed,
            unique_trials=unique_trials,
            first_entry=self.entries[0].timestamp if self.entries else None,
            last_entry=self.entries[-1].timestamp if self.entries else None,
            chain_valid=chain_valid
        )

    def get_entries_for_trial(self, nct_id: str) -> List[AuditEntry]:
        """Get all entries for a specific trial"""
        return [e for e in self.entries if e.nct_id == nct_id]

    def get_entries_by_result(self, result: AuditResult) -> List[AuditEntry]:
        """Get all entries with a specific result"""
        return [e for e in self.entries if e.result == result]

    def get_recent_entries(self, limit: int = 10) -> List[AuditEntry]:
        """Get most recent entries"""
        return self.entries[-limit:]

    def export_json(self, path: str):
        """Export ledger to JSON file"""
        chain_valid, _ = self.verify_chain()
        data = {
            "version": "4.0",
            "protocol": "TC-TRIALREG",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "chain_valid": chain_valid,
            "stats": asdict(self.get_stats()),
            "entries": [e.to_dict() for e in self.entries]
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def export_markdown(self, path: str):
        """Export ledger as markdown report"""
        stats = self.get_stats()
        chain_valid, invalid_idx = self.verify_chain()

        lines = [
            "# TruthCert TC-TRIALREG Audit Ledger Report",
            "",
            f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
            f"**Protocol:** TC-TRIALREG v4.0",
            "",
            "---",
            "",
            "## Summary Statistics",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Entries | {stats.total_entries} |",
            f"| Verified | {stats.verified_count} |",
            f"| Discrepancies | {stats.discrepancy_count} |",
            f"| Failed | {stats.failed_count} |",
            f"| Unique Trials | {stats.unique_trials} |",
            f"| Chain Valid | {'Yes' if chain_valid else f'No (invalid at #{invalid_idx})'} |",
            "",
            "---",
            "",
            "## Audit Entries",
            "",
            "| Entry ID | Action | NCT ID | Result | Timestamp |",
            "|----------|--------|--------|--------|-----------|"
        ]

        for entry in self.entries:
            result_icon = {
                "VERIFIED": "V",
                "DISCREPANCY": "!",
                "FAILED": "X",
                "SUCCESS": "S",
                "WARNING": "W"
            }.get(entry.result.value, "?")

            lines.append(
                f"| {entry.entry_id} | {entry.action.value} | {entry.nct_id} | "
                f"{result_icon} {entry.result.value} | {entry.timestamp[:19]} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## Chain Verification",
            "",
            f"Genesis Hash: `{self.GENESIS_HASH}`",
            ""
        ])

        if self.entries:
            lines.append(f"Last Chain Hash: `{self.entries[-1].chain_hash}`")

        lines.extend([
            "",
            "---",
            "",
            "*Report generated by TruthCert TC-TRIALREG Audit Ledger v4.0*"
        ])

        with open(path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

    def export_html(self, path: str):
        """Export ledger as HTML report"""
        stats = self.get_stats()
        chain_valid, _ = self.verify_chain()

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TruthCert TC-TRIALREG Audit Ledger</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); color: white; padding: 30px; border-radius: 12px 12px 0 0; }}
        .header h1 {{ margin-bottom: 10px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; padding: 20px; background: white; }}
        .stat-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
        .stat-card .value {{ font-size: 2em; font-weight: bold; color: #1e3a5f; }}
        .stat-card .label {{ color: #666; font-size: 0.9em; }}
        .chain-status {{ padding: 15px 20px; background: {'#d4edda' if chain_valid else '#f8d7da'}; color: {'#155724' if chain_valid else '#721c24'}; }}
        .entries {{ background: white; padding: 20px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        .result-VERIFIED {{ color: #28a745; }}
        .result-DISCREPANCY {{ color: #ffc107; }}
        .result-FAILED {{ color: #dc3545; }}
        .result-SUCCESS {{ color: #28a745; }}
        .result-WARNING {{ color: #ffc107; }}
        .footer {{ padding: 20px; text-align: center; color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>TruthCert TC-TRIALREG Audit Ledger</h1>
            <p>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="value">{stats.total_entries}</div>
                <div class="label">Total Entries</div>
            </div>
            <div class="stat-card">
                <div class="value">{stats.verified_count}</div>
                <div class="label">Verified</div>
            </div>
            <div class="stat-card">
                <div class="value">{stats.discrepancy_count}</div>
                <div class="label">Discrepancies</div>
            </div>
            <div class="stat-card">
                <div class="value">{stats.failed_count}</div>
                <div class="label">Failed</div>
            </div>
            <div class="stat-card">
                <div class="value">{stats.unique_trials}</div>
                <div class="label">Unique Trials</div>
            </div>
        </div>

        <div class="chain-status">
            <strong>Chain Integrity:</strong> {'VALID - All hashes verified' if chain_valid else 'INVALID - Chain broken'}
        </div>

        <div class="entries">
            <h2 style="margin-bottom: 15px;">Audit Entries</h2>
            <table>
                <thead>
                    <tr>
                        <th>Entry ID</th>
                        <th>Action</th>
                        <th>NCT ID</th>
                        <th>Result</th>
                        <th>Bundle Hash</th>
                        <th>Timestamp</th>
                    </tr>
                </thead>
                <tbody>
"""

        for entry in self.entries:
            html += f"""                    <tr>
                        <td><code>{entry.entry_id}</code></td>
                        <td>{entry.action.value}</td>
                        <td><a href="https://clinicaltrials.gov/study/{entry.nct_id}" target="_blank">{entry.nct_id}</a></td>
                        <td class="result-{entry.result.value}">{entry.result.value}</td>
                        <td><code>{entry.bundle_hash[:8]}...</code></td>
                        <td>{entry.timestamp[:19]}</td>
                    </tr>
"""

        html += """                </tbody>
            </table>
        </div>

        <div class="footer">
            <p>TruthCert TC-TRIALREG Audit Ledger v4.0</p>
            <p>Protocol: Multi-witness verification with cryptographic chain</p>
        </div>
    </div>
</body>
</html>"""

        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="TruthCert TC-TRIALREG Audit Ledger Manager"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show ledger statistics")
    stats_parser.add_argument("-l", "--ledger", required=True, help="Path to ledger file")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify ledger chain integrity")
    verify_parser.add_argument("-l", "--ledger", required=True, help="Path to ledger file")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export ledger to file")
    export_parser.add_argument("-l", "--ledger", required=True, help="Path to ledger file")
    export_parser.add_argument("-o", "--output", required=True, help="Output file path")
    export_parser.add_argument("-f", "--format", choices=["json", "markdown", "html"],
                               default="json", help="Export format")

    # List command
    list_parser = subparsers.add_parser("list", help="List ledger entries")
    list_parser.add_argument("-l", "--ledger", required=True, help="Path to ledger file")
    list_parser.add_argument("-n", "--limit", type=int, default=10, help="Number of entries")
    list_parser.add_argument("--nct", help="Filter by NCT ID")
    list_parser.add_argument("--result", choices=["VERIFIED", "DISCREPANCY", "FAILED"],
                            help="Filter by result")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    ledger = TruthCertAuditLedger(args.ledger)

    if args.command == "stats":
        stats = ledger.get_stats()
        print("TruthCert TC-TRIALREG Audit Ledger Statistics")
        print("=" * 45)
        print(f"Total Entries:    {stats.total_entries}")
        print(f"Verified:         {stats.verified_count}")
        print(f"Discrepancies:    {stats.discrepancy_count}")
        print(f"Failed:           {stats.failed_count}")
        print(f"Unique Trials:    {stats.unique_trials}")
        print(f"Chain Valid:      {'Yes' if stats.chain_valid else 'No'}")
        if stats.first_entry:
            print(f"First Entry:      {stats.first_entry[:19]}")
            print(f"Last Entry:       {stats.last_entry[:19]}")

    elif args.command == "verify":
        valid, invalid_idx = ledger.verify_chain()
        if valid:
            print("Chain integrity: VALID")
            print(f"All {len(ledger.entries)} entries verified successfully.")
        else:
            print("Chain integrity: INVALID")
            print(f"Chain broken at entry index {invalid_idx}")
            if invalid_idx is not None:
                entry = ledger.entries[invalid_idx]
                print(f"Entry ID: {entry.entry_id}")
                print(f"NCT ID: {entry.nct_id}")

    elif args.command == "export":
        if args.format == "json":
            ledger.export_json(args.output)
        elif args.format == "markdown":
            ledger.export_markdown(args.output)
        elif args.format == "html":
            ledger.export_html(args.output)
        print(f"Ledger exported to {args.output}")

    elif args.command == "list":
        if args.nct:
            entries = ledger.get_entries_for_trial(args.nct)
        elif args.result:
            entries = ledger.get_entries_by_result(AuditResult(args.result))
        else:
            entries = ledger.get_recent_entries(args.limit)

        print(f"{'Entry ID':<30} {'Action':<12} {'NCT ID':<15} {'Result':<12}")
        print("-" * 70)
        for entry in entries:
            print(f"{entry.entry_id:<30} {entry.action.value:<12} {entry.nct_id:<15} {entry.result.value:<12}")


if __name__ == "__main__":
    main()
