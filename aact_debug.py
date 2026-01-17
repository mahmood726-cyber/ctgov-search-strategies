#!/usr/bin/env python3
"""
AACT Database Debug - Investigate why cardiovascular queries return 0
"""

import psycopg2
import os
from pathlib import Path

# Load .env file
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

AACT_CONFIG = {
    'host': 'aact-db.ctti-clinicaltrials.org',
    'port': 5432,
    'database': 'aact',
    'user': os.environ.get('AACT_USER', ''),
    'password': os.environ.get('AACT_PASSWORD', '')
}


def main():
    print("=" * 70)
    print("  AACT DATABASE DEBUG")
    print("=" * 70)

    conn = psycopg2.connect(**AACT_CONFIG)
    cursor = conn.cursor()

    # Test 1: Check total studies
    print("\n1. TOTAL STUDIES IN DATABASE")
    cursor.execute("SELECT COUNT(*) FROM studies")
    print(f"   Total studies: {cursor.fetchone()[0]:,}")

    # Test 2: Check conditions table
    print("\n2. CONDITIONS TABLE")
    cursor.execute("SELECT COUNT(*) FROM conditions")
    print(f"   Total conditions: {cursor.fetchone()[0]:,}")

    # Test 3: Check designs table
    print("\n3. DESIGNS TABLE")
    cursor.execute("SELECT COUNT(*) FROM designs")
    print(f"   Total designs: {cursor.fetchone()[0]:,}")

    # Test 4: Check allocation values
    print("\n4. ALLOCATION VALUES IN DESIGNS")
    cursor.execute("""
        SELECT allocation, COUNT(*) as cnt
        FROM designs
        GROUP BY allocation
        ORDER BY cnt DESC
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]:,}")

    # Test 5: Check condition name samples with 'heart'
    print("\n5. CONDITIONS CONTAINING 'heart' (sample)")
    cursor.execute("""
        SELECT DISTINCT name
        FROM conditions
        WHERE LOWER(name) LIKE '%heart%'
        LIMIT 20
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}")

    # Test 6: Count heart failure conditions
    print("\n6. HEART FAILURE CONDITION COUNT")
    cursor.execute("""
        SELECT COUNT(DISTINCT nct_id)
        FROM conditions
        WHERE LOWER(name) LIKE '%heart failure%'
    """)
    print(f"   Studies with 'heart failure' condition: {cursor.fetchone()[0]:,}")

    # Test 7: Simple join test
    print("\n7. SIMPLE JOIN TEST (studies + conditions)")
    cursor.execute("""
        SELECT COUNT(DISTINCT s.nct_id)
        FROM studies s
        JOIN conditions c ON s.nct_id = c.nct_id
        WHERE LOWER(c.name) LIKE '%heart failure%'
    """)
    print(f"   Studies with heart failure (join): {cursor.fetchone()[0]:,}")

    # Test 8: Triple join test
    print("\n8. TRIPLE JOIN TEST (studies + conditions + designs)")
    cursor.execute("""
        SELECT COUNT(DISTINCT s.nct_id)
        FROM studies s
        JOIN conditions c ON s.nct_id = c.nct_id
        JOIN designs d ON s.nct_id = d.nct_id
        WHERE LOWER(c.name) LIKE '%heart failure%'
    """)
    print(f"   Heart failure with designs: {cursor.fetchone()[0]:,}")

    # Test 9: Check if allocation is case-sensitive
    print("\n9. RANDOMIZED ALLOCATION VARIATIONS")
    cursor.execute("""
        SELECT allocation, COUNT(*)
        FROM designs
        WHERE LOWER(allocation) LIKE '%random%'
        GROUP BY allocation
    """)
    for row in cursor.fetchall():
        print(f"   '{row[0]}': {row[1]:,}")

    # Test 10: Final working query
    print("\n10. HEART FAILURE RANDOMIZED TRIALS")
    cursor.execute("""
        SELECT COUNT(DISTINCT s.nct_id)
        FROM studies s
        JOIN conditions c ON s.nct_id = c.nct_id
        JOIN designs d ON s.nct_id = d.nct_id
        WHERE LOWER(c.name) LIKE '%heart failure%'
        AND LOWER(d.allocation) LIKE '%random%'
    """)
    print(f"   Heart failure RCTs (case-insensitive): {cursor.fetchone()[0]:,}")

    # Test 11: Sample NCT IDs
    print("\n11. SAMPLE HEART FAILURE RCTS")
    cursor.execute("""
        SELECT DISTINCT s.nct_id, s.brief_title, d.allocation
        FROM studies s
        JOIN conditions c ON s.nct_id = c.nct_id
        JOIN designs d ON s.nct_id = d.nct_id
        WHERE LOWER(c.name) LIKE '%heart failure%'
        AND LOWER(d.allocation) LIKE '%random%'
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[2]}")
        print(f"      {row[1][:60]}...")

    cursor.close()
    conn.close()
    print("\n  Debug complete.")


if __name__ == "__main__":
    main()
