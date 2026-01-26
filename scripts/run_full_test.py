#!/usr/bin/env python3
"""
Full Integration Test for TruthCert TC-TRIALREG Suite
Tests reconciliation engine and audit ledger with real NCT IDs
"""

import sys
import os
import json
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from registry_reconciliation import (
    ReconciliationEngine,
    PaperData,
    generate_markdown_report
)
from audit_ledger import (
    TruthCertAuditLedger,
    AuditAction,
    AuditResult
)


def main():
    print("=" * 60)
    print("TruthCert TC-TRIALREG Integration Test")
    print("=" * 60)
    print()

    # Test NCT IDs from Cochrane reviews
    test_ncts = [
        "NCT00400712",  # Stroke rehabilitation
        "NCT02717715",  # Stroke
        "NCT01735443",  #
        "NCT01881893",  #
        "NCT00643149",  #
        "NCT00542815",  #
        "NCT01285830",  # Diabetes
        "NCT00420836",  #
        "NCT00886613",  #
        "NCT02348489",  # Diabetes
    ]

    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    # Initialize engine and ledger
    engine = ReconciliationEngine()
    ledger = TruthCertAuditLedger(str(output_dir / "test_ledger.json"))

    print(f"Testing {len(test_ncts)} NCT IDs...")
    print("-" * 60)

    results = {
        "VERIFIED": 0,
        "DISCREPANCY": 0,
        "FAILED": 0
    }

    reports = []

    for i, nct_id in enumerate(test_ncts, 1):
        print(f"[{i}/{len(test_ncts)}] {nct_id}...", end=" ", flush=True)

        try:
            report = engine.reconcile(nct_id)
            results[report.overall_status] = results.get(report.overall_status, 0) + 1
            reports.append(report)

            # Log to audit ledger
            audit_result = {
                "VERIFIED": AuditResult.VERIFIED,
                "DISCREPANCY": AuditResult.DISCREPANCY,
                "FAILED": AuditResult.FAILED
            }.get(report.overall_status, AuditResult.WARNING)

            ledger.add_entry(
                action=AuditAction.RECONCILE,
                nct_id=nct_id,
                result=audit_result,
                bundle_hash=report.bundle_hash,
                metadata={
                    "agreement_score": report.agreement_score,
                    "corruption_count": len(report.corruptions),
                    "validation_count": len(report.validations)
                }
            )

            status_icon = {"VERIFIED": "[OK]", "DISCREPANCY": "[!]", "FAILED": "[X]"}
            print(f"{status_icon.get(report.overall_status, '[?]')} {report.overall_status} ({report.agreement_score:.0%})")

        except Exception as e:
            print(f"[X] ERROR: {e}")
            results["FAILED"] = results.get("FAILED", 0) + 1

    print("-" * 60)
    print()

    # Summary
    print("SUMMARY")
    print("=" * 60)
    print(f"  Verified:     {results.get('VERIFIED', 0)}")
    print(f"  Discrepancy:  {results.get('DISCREPANCY', 0)}")
    print(f"  Failed:       {results.get('FAILED', 0)}")
    print(f"  Total:        {len(test_ncts)}")
    print()

    # Audit ledger stats
    stats = ledger.get_stats()
    chain_valid, _ = ledger.verify_chain()
    print("AUDIT LEDGER")
    print("=" * 60)
    print(f"  Total Entries:   {stats.total_entries}")
    print(f"  Chain Valid:     {'Yes' if chain_valid else 'No'}")
    print(f"  Unique Trials:   {stats.unique_trials}")
    print()

    # Export reports
    print("EXPORTS")
    print("=" * 60)

    # JSON report
    json_path = output_dir / "full_test_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "test_results": results,
            "reports": [{
                "nct_id": r.nct_id,
                "status": r.overall_status,
                "agreement": r.agreement_score,
                "bundle_hash": r.bundle_hash,
                "corruptions": len(r.corruptions)
            } for r in reports]
        }, f, indent=2)
    print(f"  JSON:     {json_path}")

    # Markdown report
    md_path = output_dir / "full_test_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# TruthCert TC-TRIALREG Full Test Report\n\n")
        f.write(f"**Tested:** {len(test_ncts)} NCT IDs\n")
        f.write(f"**Verified:** {results.get('VERIFIED', 0)}\n")
        f.write(f"**Discrepancy:** {results.get('DISCREPANCY', 0)}\n")
        f.write(f"**Failed:** {results.get('FAILED', 0)}\n\n")
        f.write("---\n\n")
        for report in reports:
            f.write(generate_markdown_report(report))
            f.write("\n\n---\n\n")
    print(f"  Markdown: {md_path}")

    # HTML ledger export
    html_path = output_dir / "audit_ledger_report.html"
    ledger.export_html(str(html_path))
    print(f"  HTML:     {html_path}")

    print()
    print("=" * 60)
    print("Test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
