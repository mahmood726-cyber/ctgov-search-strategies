#!/usr/bin/env python3
# sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files.
"""
AACT Full Validation - Test ALL Cochrane NCT IDs
Tests every NCT ID extracted from Cochrane systematic reviews
"""

import psycopg2
import json
import os
from pathlib import Path
from datetime import datetime

# Load .env file if present
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

# AACT Database Connection
AACT_CONFIG = {
    'host': 'aact-db.ctti-clinicaltrials.org',
    'port': 5432,
    'database': 'aact',
    'user': os.environ.get('AACT_USER', ''),
    'password': os.environ.get('AACT_PASSWORD', '')
}


def connect_aact():
    """Connect to AACT database"""
    print("Connecting to AACT database...")

    if not AACT_CONFIG['user'] or not AACT_CONFIG['password']:
        print("  ERROR: AACT credentials not found!")
        return None

    try:
        conn = psycopg2.connect(**AACT_CONFIG)
        print("  Connected successfully!")
        return conn
    except Exception as e:
        print(f"  Connection failed: {e}")
        return None


def get_nct_details(conn, nct_id):
    """Get details for a single NCT ID"""
    cursor = conn.cursor()

    query = """
        SELECT
            s.nct_id,
            s.brief_title,
            s.overall_status,
            s.study_type,
            d.allocation
        FROM studies s
        LEFT JOIN designs d ON s.nct_id = d.nct_id
        WHERE s.nct_id = %s
    """

    cursor.execute(query, (nct_id,))
    result = cursor.fetchone()
    cursor.close()

    if result:
        return {
            'nct_id': result[0],
            'title': result[1],
            'status': result[2],
            'study_type': result[3],
            'allocation': result[4],
            'found': True
        }
    return {'nct_id': nct_id, 'found': False}


def batch_check_ncts(conn, nct_ids):
    """Check multiple NCT IDs at once"""
    cursor = conn.cursor()

    placeholders = ','.join(['%s'] * len(nct_ids))
    query = f"""
        SELECT
            s.nct_id,
            s.brief_title,
            s.overall_status,
            s.study_type,
            d.allocation
        FROM studies s
        LEFT JOIN designs d ON s.nct_id = d.nct_id
        WHERE s.nct_id IN ({placeholders})
    """

    cursor.execute(query, list(nct_ids))
    results = cursor.fetchall()
    cursor.close()

    found_dict = {}
    for r in results:
        found_dict[r[0]] = {
            'nct_id': r[0],
            'title': r[1],
            'status': r[2],
            'study_type': r[3],
            'allocation': r[4],
            'found': True
        }

    return found_dict


def main():
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")

    print("=" * 70)
    print("  AACT FULL VALIDATION - ALL COCHRANE NCT IDs")
    print("=" * 70)

    # Connect
    conn = connect_aact()
    if not conn:
        return

    # Load ALL NCT IDs from Cochrane
    nct_file = output_dir / "recall_test_results.json"
    with open(nct_file) as f:
        data = json.load(f)

    condition_groups = data.get("condition_groups", {})

    # Collect ALL unique NCT IDs
    all_ncts = set()
    for condition, ncts in condition_groups.items():
        all_ncts.update(ncts)

    print(f"\n  Total unique NCT IDs from Cochrane reviews: {len(all_ncts)}")
    print(f"  Total conditions: {len(condition_groups)}")

    # Batch check all NCT IDs
    print("\n  Checking all NCT IDs in AACT...")
    found_dict = batch_check_ncts(conn, all_ncts)

    found_count = len(found_dict)
    missing_count = len(all_ncts) - found_count

    print(f"\n  Found in AACT: {found_count}")
    print(f"  Missing from AACT: {missing_count}")
    print(f"  RECALL: {found_count / len(all_ncts) * 100:.1f}%")

    # Identify missing NCT IDs
    missing_ncts = all_ncts - set(found_dict.keys())

    if missing_ncts:
        print(f"\n  Missing NCT IDs ({len(missing_ncts)}):")
        for nct in sorted(missing_ncts):
            # Find which condition it belongs to
            for cond, ncts in condition_groups.items():
                if nct in ncts:
                    print(f"    {nct} ({cond})")
                    break

    # Per-condition analysis
    print("\n" + "=" * 70)
    print("  PER-CONDITION RECALL")
    print("=" * 70)

    print(f"\n  {'Condition':<35} {'Known':>6} {'Found':>6} {'Recall':>8}")
    print("-" * 60)

    condition_results = {}
    perfect_conditions = 0
    imperfect_conditions = []

    for condition in sorted(condition_groups.keys()):
        known_ncts = set(condition_groups[condition])
        found_ncts = known_ncts & set(found_dict.keys())
        recall = len(found_ncts) / len(known_ncts) * 100 if known_ncts else 0

        condition_results[condition] = {
            'known': len(known_ncts),
            'found': len(found_ncts),
            'recall': recall,
            'missing': list(known_ncts - found_ncts)
        }

        status = "OK" if recall == 100 else "MISS"
        print(f"  {condition:<35} {len(known_ncts):>6} {len(found_ncts):>6} {recall:>7.1f}%  {status}")

        if recall == 100:
            perfect_conditions += 1
        else:
            imperfect_conditions.append((condition, recall, list(known_ncts - found_ncts)))

    print("-" * 60)
    print(f"  {'TOTAL':<35} {len(all_ncts):>6} {found_count:>6} {found_count / len(all_ncts) * 100:>7.1f}%")

    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)

    print(f"""
  TOTAL NCT IDs:           {len(all_ncts)}
  Found in AACT:           {found_count}
  Missing from AACT:       {missing_count}

  OVERALL RECALL:          {found_count / len(all_ncts) * 100:.1f}%

  Conditions with 100%:    {perfect_conditions}/{len(condition_groups)}
  Conditions with <100%:   {len(imperfect_conditions)}
""")

    if imperfect_conditions:
        print("  Conditions with missing NCT IDs:")
        for cond, recall, missing in imperfect_conditions:
            print(f"    {cond}: {recall:.1f}% - missing {missing}")

    # Analyze the found studies
    print("\n" + "=" * 70)
    print("  STUDY CHARACTERISTICS (Found in AACT)")
    print("=" * 70)

    # Count by allocation
    allocations = {}
    statuses = {}
    study_types = {}

    for nct_id, details in found_dict.items():
        alloc = details.get('allocation') or 'Unknown'
        status = details.get('status') or 'Unknown'
        stype = details.get('study_type') or 'Unknown'

        allocations[alloc] = allocations.get(alloc, 0) + 1
        statuses[status] = statuses.get(status, 0) + 1
        study_types[stype] = study_types.get(stype, 0) + 1

    print("\n  By Allocation:")
    for alloc, count in sorted(allocations.items(), key=lambda x: -x[1]):
        print(f"    {alloc}: {count} ({count / found_count * 100:.1f}%)")

    print("\n  By Status:")
    for status, count in sorted(statuses.items(), key=lambda x: -x[1])[:10]:
        print(f"    {status}: {count} ({count / found_count * 100:.1f}%)")

    print("\n  By Study Type:")
    for stype, count in sorted(study_types.items(), key=lambda x: -x[1]):
        print(f"    {stype}: {count} ({count / found_count * 100:.1f}%)")

    # Save results
    output_file = output_dir / f"aact_full_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    export = {
        "timestamp": datetime.now().isoformat(),
        "total_ncts": len(all_ncts),
        "found_in_aact": found_count,
        "missing_from_aact": missing_count,
        "overall_recall": found_count / len(all_ncts) * 100,
        "conditions_total": len(condition_groups),
        "conditions_100_recall": perfect_conditions,
        "missing_ncts": list(missing_ncts),
        "per_condition": condition_results,
        "allocations": allocations,
        "statuses": statuses,
        "study_types": study_types
    }

    with open(output_file, 'w') as f:
        json.dump(export, f, indent=2, default=list)

    print(f"\n  Results saved: {output_file}")

    conn.close()
    print("\n  Database connection closed.")


if __name__ == "__main__":
    main()
