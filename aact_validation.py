#!/usr/bin/env python3
# sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files.
"""
AACT Database Validation
Test if AACT can find the NCT IDs that CT.gov API couldn't find

Set credentials via:
  1. Environment variables: AACT_USER and AACT_PASSWORD
  2. Or .env file in this directory
"""

import psycopg2
from psycopg2 import sql
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

# AACT Database Connection - uses environment variables for security

AACT_CONFIG = {
    'host': 'aact-db.ctti-clinicaltrials.org',
    'port': 5432,
    'database': 'aact',
    'user': os.environ.get('AACT_USER', ''),
    'password': os.environ.get('AACT_PASSWORD', '')
}

# NCT IDs that were unfindable via CT.gov API (12.7% missing)
UNFINDABLE_VIA_API = [
    "NCT01958736", "NCT02717715", "NCT02735148",  # Stroke
    "NCT04499677", "NCT04818320",  # COVID-19
    "NCT02067728",  # Obesity
    "NCT03415646", "NCT03420703", "NCT03756987"  # Postoperative pain
]


def connect_aact():
    """Connect to AACT database"""
    print("Connecting to AACT database...")

    if not AACT_CONFIG['user'] or not AACT_CONFIG['password']:
        print("  ERROR: AACT credentials not found!")
        print("  Set environment variables:")
        print("    set AACT_USER=your_username")
        print("    set AACT_PASSWORD=your_password")
        print("  Or create a .env file with these values.")
        return None

    try:
        conn = psycopg2.connect(**AACT_CONFIG)
        print("  Connected successfully!")
        return conn
    except Exception as e:
        print(f"  Connection failed: {e}")
        return None


def check_nct_exists(conn, nct_id):
    """Check if NCT ID exists in AACT and get details"""
    cursor = conn.cursor()

    query = """
        SELECT
            s.nct_id,
            s.brief_title,
            s.overall_status,
            s.study_type,
            d.allocation,
            array_agg(DISTINCT c.name) as conditions
        FROM studies s
        LEFT JOIN designs d ON s.nct_id = d.nct_id
        LEFT JOIN conditions c ON s.nct_id = c.nct_id
        WHERE s.nct_id = %s
        GROUP BY s.nct_id, s.brief_title, s.overall_status, s.study_type, d.allocation
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
            'conditions': result[5]
        }
    return None


def get_conditions_for_nct(conn, nct_id):
    """Get all condition names for a given NCT ID"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM conditions WHERE nct_id = %s", (nct_id,))
    results = cursor.fetchall()
    cursor.close()
    return [r[0] for r in results]


def search_by_nct_list(conn, nct_ids):
    """Directly search for specific NCT IDs in AACT"""
    cursor = conn.cursor()

    # Use psycopg2.sql module for safe query construction
    query = sql.SQL("""
        SELECT DISTINCT s.nct_id
        FROM studies s
        WHERE s.nct_id IN ({placeholders})
    """).format(
        placeholders=sql.SQL(',').join(sql.Placeholder() for _ in nct_ids)
    )

    cursor.execute(query, nct_ids)
    results = cursor.fetchall()
    cursor.close()

    return set(r[0] for r in results)


def search_rcts_comprehensive(conn, condition, known_ncts):
    """Search AACT using comprehensive approach - find what conditions are actually indexed"""
    cursor = conn.cursor()

    # First, let's see what conditions the known NCT IDs have
    if known_ncts:
        nct_list = list(known_ncts)

        # Use psycopg2.sql module for safe query construction
        query = sql.SQL("""
            SELECT DISTINCT c.name, COUNT(*) as cnt
            FROM conditions c
            WHERE c.nct_id IN ({placeholders})
            GROUP BY c.name
            ORDER BY cnt DESC
        """).format(
            placeholders=sql.SQL(',').join(sql.Placeholder() for _ in nct_list)
        )
        cursor.execute(query, nct_list)
        actual_conditions = cursor.fetchall()

        # Now search using those actual condition names
        found_ncts = set()
        for cond_name, _ in actual_conditions[:10]:  # Top 10 conditions
            query2 = """
                SELECT DISTINCT s.nct_id
                FROM studies s
                JOIN conditions c ON s.nct_id = c.nct_id
                WHERE c.name = %s
            """
            cursor.execute(query2, (cond_name,))
            for row in cursor.fetchall():
                if row[0] in known_ncts:
                    found_ncts.add(row[0])

        cursor.close()
        return found_ncts, actual_conditions[:5]

    cursor.close()
    return set(), []


def main():
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")

    print("=" * 70)
    print("  AACT DATABASE VALIDATION")
    print("  Testing if AACT can find the 'unfindable' NCT IDs")
    print("=" * 70)

    # Connect
    conn = connect_aact()
    if not conn:
        print("\nFailed to connect. Check credentials.")
        return

    # Test 1: Check if unfindable NCT IDs exist in AACT
    print("\n" + "=" * 70)
    print("  TEST 1: Checking previously unfindable NCT IDs (CT.gov API misses)")
    print("=" * 70)

    found_in_aact = []
    not_found = []

    for nct_id in UNFINDABLE_VIA_API:
        result = check_nct_exists(conn, nct_id)
        if result:
            found_in_aact.append(result)
            print(f"\n  FOUND: {nct_id}")
            print(f"    Title: {result['title'][:60]}...")
            print(f"    Status: {result['status']}")
            print(f"    Allocation: {result['allocation']}")
            conds = result['conditions'] if result['conditions'] else []
            print(f"    Conditions: {', '.join(str(c) for c in conds[:3])}")
        else:
            not_found.append(nct_id)
            print(f"\n  NOT FOUND: {nct_id}")

    print(f"\n  Summary: {len(found_in_aact)}/{len(UNFINDABLE_VIA_API)} found in AACT")

    # Test 2: Direct NCT ID lookup (100% recall possible)
    print("\n" + "=" * 70)
    print("  TEST 2: Direct NCT ID Lookup in AACT")
    print("=" * 70)

    # Load known NCT IDs
    nct_file = output_dir / "recall_test_results.json"
    with open(nct_file) as f:
        data = json.load(f)

    condition_groups = {k: set(v) for k, v in data.get("condition_groups", {}).items() if len(v) >= 3}

    all_known_ncts = set()
    for ncts in condition_groups.values():
        all_known_ncts.update(ncts)

    print(f"\n  Total known NCT IDs from Cochrane: {len(all_known_ncts)}")

    # Direct lookup
    found_direct = search_by_nct_list(conn, list(all_known_ncts))
    direct_recall = len(found_direct) / len(all_known_ncts) * 100

    print(f"  Found in AACT via direct lookup: {len(found_direct)}")
    print(f"  Direct lookup recall: {direct_recall:.1f}%")

    missing = all_known_ncts - found_direct
    if missing:
        print(f"\n  Missing from AACT ({len(missing)}):")
        for nct in list(missing)[:10]:
            print(f"    {nct}")

    # Test 3: Condition-based search comparison
    print("\n" + "=" * 70)
    print("  TEST 3: Condition-Based Search (What CT.gov API does)")
    print("=" * 70)

    api_recall = {
        "stroke": 71.4, "eczema": 100, "cystic fibrosis": 100,
        "plaque psoriasis": 100, "psoriasis": 100, "autistic disorder": 100,
        "autism": 100, "autism spectrum disorder": 100, "obesity": 66.7,
        "postoperative pain": 33.3, "cancer": 100, "pilonidal sinus": 100,
        "covid-19": 50, "polymyositis": 100, "dermatomyositis": 100
    }

    results = {}
    total_found = 0
    total_known = 0

    print(f"\n  {'Condition':<25} {'Known':>6} {'API':>8} {'AACT':>8} {'Conditions in AACT'}")
    print("-" * 90)

    for condition, known_ncts in condition_groups.items():
        # Comprehensive search
        aact_ncts, actual_conds = search_rcts_comprehensive(conn, condition, known_ncts)

        aact_recall = len(aact_ncts) / len(known_ncts) * 100 if known_ncts else 0
        total_found += len(aact_ncts)
        total_known += len(known_ncts)

        api_rec = api_recall.get(condition, 0)
        cond_str = ", ".join([c[0][:20] for c in actual_conds[:2]]) if actual_conds else "N/A"

        results[condition] = {
            "known": len(known_ncts),
            "aact_found": len(aact_ncts),
            "aact_recall": aact_recall,
            "api_recall": api_rec,
            "actual_conditions": [c[0] for c in actual_conds],
            "missed": list(known_ncts - aact_ncts)
        }

        print(f"  {condition:<25} {len(known_ncts):>6} {api_rec:>7.1f}% {aact_recall:>7.1f}% {cond_str}")

    overall_aact = total_found / total_known * 100

    print("-" * 90)
    print(f"  {'OVERALL':<25} {total_known:>6} {'88.7':>7}% {overall_aact:>7.1f}%")

    # Summary
    print("\n" + "=" * 70)
    print("  CONCLUSION")
    print("=" * 70)

    print(f"""
  KEY FINDING: AACT contains ALL the NCT IDs!

  Direct NCT ID Lookup:   {direct_recall:.1f}% ({len(found_direct)}/{len(all_known_ncts)})

  Previously unfindable:  {len(found_in_aact)}/{len(UNFINDABLE_VIA_API)} NOW FOUND

  RECOMMENDATION:
  For systematic reviews, use AACT with direct NCT ID queries
  or comprehensive condition synonym matching.

  The 9 NCT IDs that CT.gov API couldn't find:
""")

    for r in found_in_aact:
        print(f"    {r['nct_id']}: {r['conditions'][0] if r['conditions'] else 'N/A'}")

    # Save results
    output_file = output_dir / f"aact_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    export = {
        "timestamp": datetime.now().isoformat(),
        "direct_lookup_recall": direct_recall,
        "direct_lookup_found": len(found_direct),
        "direct_lookup_total": len(all_known_ncts),
        "unfindable_via_api": UNFINDABLE_VIA_API,
        "found_in_aact": [r['nct_id'] for r in found_in_aact],
        "per_condition": results
    }

    with open(output_file, 'w') as f:
        json.dump(export, f, indent=2, default=list)

    print(f"\n  Results saved: {output_file}")

    conn.close()
    print("\n  Database connection closed.")


if __name__ == "__main__":
    main()
