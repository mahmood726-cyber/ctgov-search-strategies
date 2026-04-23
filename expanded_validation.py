#!/usr/bin/env python3
# sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files.
"""
Expanded Validation Dataset
Sources:
1. Cochrane Pairwise (160 NCT IDs)
2. JCPT Cardiovascular Review (117 NCT IDs)
3. AACT Heart Failure RCTs (query database)
4. AACT Cardiovascular RCTs (query database)
"""

import psycopg2
import json
import os
from pathlib import Path
from datetime import datetime

from ctgov_utils import fetch_nct_ids, get_session

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

# JCPT 2020 Cardiovascular Trials
JCPT_CARDIOVASCULAR = [
    "NCT04213183", "NCT03706664", "NCT03268031", "NCT04131530", "NCT03784209",
    "NCT03877614", "NCT03976297", "NCT04138771", "NCT04222439", "NCT03574454",
    "NCT04126265", "NCT03746561", "NCT04213430", "NCT04087824", "NCT04186104",
    "NCT03790930", "NCT04022512", "NCT04260321", "NCT04227795", "NCT02943824",
    "NCT03917017", "NCT04040114", "NCT04271657", "NCT04273451", "NCT03908645",
    "NCT04071678", "NCT04268251", "NCT04136236", "NCT04214782", "NCT04255615",
    "NCT03980470", "NCT03700268", "NCT04079478", "NCT04203264", "NCT04215211",
    "NCT04217018", "NCT04217044", "NCT04215224", "NCT03622281", "NCT04232462",
    "NCT02330679", "NCT02931500", "NCT03969056", "NCT00330109", "NCT03787784",
    "NCT02932176", "NCT03530098", "NCT03706534", "NCT04099147", "NCT03899623",
    "NCT03960710", "NCT04022018", "NCT04242043", "NCT03936413", "NCT03974828",
    "NCT04121988", "NCT04216901", "NCT03949218", "NCT03682783", "NCT03973437",
    "NCT03847688", "NCT03911323", "NCT03874702", "NCT04219306", "NCT04060706",
    "NCT03708978", "NCT03317691", "NCT04206098", "NCT03623971", "NCT03621462",
    "NCT03761771", "NCT03398551", "NCT03611387", "NCT03766737", "NCT03903042",
    "NCT04191980", "NCT04040374", "NCT04270032", "NCT03452774", "NCT04270799",
    "NCT03572699", "NCT04156880", "NCT01448161", "NCT04192175", "NCT04053959",
    "NCT04256551", "NCT04154228", "NCT03882476", "NCT03602989", "NCT04273477",
    "NCT03487952", "NCT04014010", "NCT03499145", "NCT04268719", "NCT03724123",
    "NCT03637712", "NCT04132401", "NCT02934971", "NCT02805621", "NCT04074772",
    "NCT03731936", "NCT03849040", "NCT03759756", "NCT04239638", "NCT04193475",
    "NCT03887598", "NCT03887611", "NCT04036903", "NCT03397524", "NCT02801877",
    "NCT03872102", "NCT02599259", "NCT04242108", "NCT02176226", "NCT03927066",
    "NCT04189029", "NCT03851497"
]


def connect_aact():
    """Connect to AACT database"""
    if not AACT_CONFIG['user'] or not AACT_CONFIG['password']:
        print("  ERROR: AACT credentials not found!")
        return None
    try:
        conn = psycopg2.connect(**AACT_CONFIG)
        return conn
    except Exception as e:
        print(f"  Connection failed: {e}")
        return None


def get_cardiovascular_rcts(conn, limit=500):
    """Get cardiovascular RCTs from AACT"""
    cursor = conn.cursor()

    query = f"""
        SELECT DISTINCT s.nct_id
        FROM studies s
        JOIN conditions c ON s.nct_id = c.nct_id
        JOIN designs d ON s.nct_id = d.nct_id
        WHERE (
            LOWER(c.name) LIKE '%%heart failure%%'
            OR LOWER(c.name) LIKE '%%cardiovascular%%'
            OR LOWER(c.name) LIKE '%%myocardial infarction%%'
            OR LOWER(c.name) LIKE '%%coronary artery disease%%'
            OR LOWER(c.name) LIKE '%%atrial fibrillation%%'
            OR LOWER(c.name) LIKE '%%hypertension%%'
            OR LOWER(c.name) LIKE '%%stroke%%'
            OR LOWER(c.name) LIKE '%%cardiac%%'
        )
        AND d.allocation = 'RANDOMIZED'
        AND s.overall_status = 'COMPLETED'
        ORDER BY s.nct_id
        LIMIT {limit}
    """

    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    return [r[0] for r in results]


def check_ncts_in_aact(conn, nct_ids):
    """Check which NCT IDs exist in AACT"""
    cursor = conn.cursor()

    placeholders = ','.join(['%s'] * len(nct_ids))
    query = f"""
        SELECT nct_id FROM studies WHERE nct_id IN ({placeholders})
    """

    cursor.execute(query, list(nct_ids))
    results = cursor.fetchall()
    cursor.close()

    return set(r[0] for r in results)


def check_ncts_on_ctgov_api(nct_ids, batch_size=50):
    """Check which NCT IDs are findable via CT.gov API"""
    found = set()
    session = get_session("Expanded-Validation/1.0")

    for i in range(0, len(nct_ids), batch_size):
        batch = list(nct_ids)[i:i + batch_size]
        nct_filter = " OR ".join([f'AREA[NCTId]{nct}' for nct in batch])
        try:
            ncts, _ = fetch_nct_ids(
                session, {"query.term": nct_filter}, timeout=30, page_size=100
            )
            found.update(ncts)
        except Exception:
            pass

    return found


def search_condition_ctgov_api(condition):
    """Search CT.gov API for a condition"""
    try:
        session = get_session("Expanded-Validation/1.0")
        ncts, _ = fetch_nct_ids(
            session,
            {"query.cond": condition, "query.term": "AREA[DesignAllocation]RANDOMIZED"},
            timeout=30,
            page_size=1000,
        )
        return ncts
    except Exception:
        pass

    return set()


def main():
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")

    print("=" * 70)
    print("  EXPANDED VALIDATION - Multiple Sources")
    print("=" * 70)

    conn = connect_aact()
    if not conn:
        return

    print("\nConnected to AACT database")

    # Source 1: Cochrane Pairwise
    print("\n" + "-" * 70)
    print("  SOURCE 1: Cochrane Pairwise Dataset")
    print("-" * 70)

    cochrane_file = output_dir / "recall_test_results.json"
    cochrane_ncts = set()
    if cochrane_file.exists():
        with open(cochrane_file) as f:
            data = json.load(f)
        for ncts in data.get("condition_groups", {}).values():
            cochrane_ncts.update(ncts)
    print(f"  Cochrane NCT IDs: {len(cochrane_ncts)}")

    # Source 2: JCPT Cardiovascular
    print("\n" + "-" * 70)
    print("  SOURCE 2: JCPT 2020 Cardiovascular Review")
    print("-" * 70)

    jcpt_ncts = set(JCPT_CARDIOVASCULAR)
    print(f"  JCPT NCT IDs: {len(jcpt_ncts)}")

    # Source 3: AACT Cardiovascular RCTs (random sample)
    print("\n" + "-" * 70)
    print("  SOURCE 3: AACT Cardiovascular RCTs (completed)")
    print("-" * 70)

    aact_cardio = get_cardiovascular_rcts(conn, limit=500)
    print(f"  AACT Cardiovascular NCT IDs: {len(aact_cardio)}")

    # Combine all sources
    print("\n" + "=" * 70)
    print("  COMBINED DATASET")
    print("=" * 70)

    all_ncts = cochrane_ncts | jcpt_ncts | set(aact_cardio)
    print(f"\n  Total unique NCT IDs: {len(all_ncts)}")
    print(f"    - Cochrane: {len(cochrane_ncts)}")
    print(f"    - JCPT Cardio: {len(jcpt_ncts)}")
    print(f"    - AACT Cardio: {len(aact_cardio)}")
    print(f"    - Overlap removed: {len(cochrane_ncts) + len(jcpt_ncts) + len(aact_cardio) - len(all_ncts)}")

    # Validation: Check all in AACT
    print("\n" + "=" * 70)
    print("  VALIDATION: AACT Database")
    print("=" * 70)

    found_in_aact = check_ncts_in_aact(conn, all_ncts)
    aact_recall = len(found_in_aact) / len(all_ncts) * 100

    print(f"\n  Found in AACT: {len(found_in_aact)}/{len(all_ncts)}")
    print(f"  AACT Recall: {aact_recall:.1f}%")

    missing_from_aact = all_ncts - found_in_aact
    if missing_from_aact:
        print(f"\n  Missing from AACT ({len(missing_from_aact)}):")
        for nct in list(missing_from_aact)[:10]:
            print(f"    {nct}")

    # Validation: Check CT.gov API for a subset
    print("\n" + "=" * 70)
    print("  VALIDATION: CT.gov API Comparison")
    print("=" * 70)

    # Test subset (Cochrane + JCPT only - known gold standard)
    test_set = cochrane_ncts | jcpt_ncts
    print(f"\n  Testing {len(test_set)} NCT IDs (Cochrane + JCPT)")

    # Check AACT
    found_aact = check_ncts_in_aact(conn, test_set)
    aact_recall_test = len(found_aact) / len(test_set) * 100

    print(f"\n  AACT Direct Lookup: {len(found_aact)}/{len(test_set)} ({aact_recall_test:.1f}%)")

    # Check CT.gov API (condition search)
    print("\n  Testing CT.gov API condition search...")
    conditions_to_test = ["heart failure", "cardiovascular disease", "atrial fibrillation", "stroke"]

    api_found = set()
    for cond in conditions_to_test:
        print(f"    Searching: {cond}...", end=" ", flush=True)
        found = search_condition_ctgov_api(cond)
        overlap = found & test_set
        api_found.update(overlap)
        print(f"found {len(overlap)} matches")

    api_recall = len(api_found) / len(test_set) * 100 if test_set else 0
    print(f"\n  CT.gov API Condition Search: {len(api_found)}/{len(test_set)} ({api_recall:.1f}%)")

    # Summary
    print("\n" + "=" * 70)
    print("  FINAL SUMMARY")
    print("=" * 70)

    print(f"""
  Dataset Size:           {len(all_ncts)} NCT IDs

  AACT Database:
    - Found:              {len(found_in_aact)} ({len(found_in_aact) / len(all_ncts) * 100:.1f}%)
    - Missing:            {len(missing_from_aact)}

  For Gold Standard (Cochrane + JCPT, n={len(test_set)}):
    - AACT Recall:        {aact_recall_test:.1f}%
    - CT.gov API Recall:  {api_recall:.1f}%
    - AACT Advantage:     +{aact_recall_test - api_recall:.1f}%
""")

    # Save results
    output_file = output_dir / f"expanded_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    export = {
        "timestamp": datetime.now().isoformat(),
        "sources": {
            "cochrane": len(cochrane_ncts),
            "jcpt_cardiovascular": len(jcpt_ncts),
            "aact_cardiovascular": len(aact_cardio)
        },
        "total_unique": len(all_ncts),
        "aact_found": len(found_in_aact),
        "aact_recall": aact_recall,
        "missing_from_aact": list(missing_from_aact),
        "gold_standard_test": {
            "size": len(test_set),
            "aact_recall": aact_recall_test,
            "api_recall": api_recall
        }
    }

    with open(output_file, 'w') as f:
        json.dump(export, f, indent=2, default=list)

    print(f"  Results saved: {output_file}")

    conn.close()


if __name__ == "__main__":
    main()
