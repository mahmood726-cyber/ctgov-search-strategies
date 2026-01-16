#!/usr/bin/env python3
"""
Comprehensive Validation Dataset - 1000+ NCT IDs
Sources:
1. Cochrane Pairwise Dataset (155 NCT IDs)
2. JCPT 2020 Cardiovascular Review (117 NCT IDs)
3. AACT Database queries for multiple conditions:
   - Heart Failure RCTs
   - Cardiovascular Disease RCTs
   - Diabetes RCTs
   - Cancer RCTs
   - COVID-19 RCTs
"""

import psycopg2
import json
import os
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

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

# Additional landmark cardiovascular trials from ESC/AHA guidelines
LANDMARK_CV_TRIALS = [
    # Heart Failure Trials
    "NCT00634309",  # PARADIGM-HF (sacubitril/valsartan)
    "NCT03036124",  # DAPA-HF (dapagliflozin)
    "NCT03057977",  # EMPEROR-Reduced (empagliflozin)
    "NCT01035255",  # SHIFT (ivabradine)
    "NCT01920711",  # VICTORIA (vericiguat)
    # ACS Trials
    "NCT01156571",  # PLATO (ticagrelor)
    "NCT00391872",  # TRITON-TIMI 38 (prasugrel)
    "NCT01187134",  # PEGASUS-TIMI 54 (ticagrelor)
    # Anticoagulation Trials
    "NCT00262600",  # RE-LY (dabigatran)
    "NCT00403767",  # ROCKET-AF (rivaroxaban)
    "NCT00412984",  # ARISTOTLE (apixaban)
    "NCT01150474",  # ENGAGE AF-TIMI 48 (edoxaban)
    # Lipid Trials
    "NCT01764633",  # FOURIER (evolocumab)
    "NCT01663402",  # ODYSSEY OUTCOMES (alirocumab)
    # Diabetes CV Trials
    "NCT01243424",  # EMPA-REG OUTCOME
    "NCT01032629",  # LEADER (liraglutide)
    "NCT01720446",  # SUSTAIN-6 (semaglutide)
    "NCT01730534",  # DECLARE-TIMI 58 (dapagliflozin)
    "NCT01131676",  # CANVAS
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

def get_condition_rcts(conn, condition_terms, limit=200):
    """Get RCTs for specific condition terms"""
    cursor = conn.cursor()

    like_clauses = " OR ".join([f"LOWER(c.name) LIKE '%{term}%'" for term in condition_terms])

    query = f"""
        SELECT DISTINCT s.nct_id
        FROM studies s
        JOIN conditions c ON s.nct_id = c.nct_id
        JOIN designs d ON s.nct_id = d.nct_id
        WHERE ({like_clauses})
        AND d.allocation = 'RANDOMIZED'
        AND s.overall_status = 'COMPLETED'
        ORDER BY s.nct_id
        LIMIT {limit}
    """

    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    return set(r[0] for r in results)

def check_ncts_in_aact(conn, nct_ids):
    """Check which NCT IDs exist in AACT"""
    if not nct_ids:
        return set()
    cursor = conn.cursor()

    placeholders = ','.join(['%s'] * len(nct_ids))
    query = f"SELECT nct_id FROM studies WHERE nct_id IN ({placeholders})"

    cursor.execute(query, list(nct_ids))
    results = cursor.fetchall()
    cursor.close()

    return set(r[0] for r in results)

def search_ctgov_api(condition, fields=None):
    """Search CT.gov API for a condition"""
    ncts = set()

    # Search methods
    searches = [
        {"query.cond": condition, "query.term": "AREA[DesignAllocation]RANDOMIZED"},
        {"query.term": f"{condition} AND AREA[DesignAllocation]RANDOMIZED"},
    ]

    session = get_session("Comprehensive-Validation/1.0")
    for search in searches:
        try:
            params = dict(search)
            params["filter.overallStatus"] = "COMPLETED"
            found, _ = fetch_nct_ids(session, params, timeout=30, page_size=100)
            ncts.update(found)
        except:
            pass

    return ncts

def main():
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")

    print("=" * 70)
    print("  COMPREHENSIVE VALIDATION - 1000+ NCT IDs")
    print("=" * 70)

    conn = connect_aact()
    if not conn:
        return

    print("\nConnected to AACT database")

    # =========================================================================
    # SOURCE 1: Cochrane Pairwise
    # =========================================================================
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

    # =========================================================================
    # SOURCE 2: JCPT Cardiovascular
    # =========================================================================
    print("\n" + "-" * 70)
    print("  SOURCE 2: JCPT 2020 Cardiovascular Review")
    print("-" * 70)

    jcpt_ncts = set(JCPT_CARDIOVASCULAR)
    print(f"  JCPT NCT IDs: {len(jcpt_ncts)}")

    # =========================================================================
    # SOURCE 3: Landmark CV Trials
    # =========================================================================
    print("\n" + "-" * 70)
    print("  SOURCE 3: ESC/AHA Landmark Cardiovascular Trials")
    print("-" * 70)

    landmark_ncts = set(LANDMARK_CV_TRIALS)
    print(f"  Landmark NCT IDs: {len(landmark_ncts)}")

    # =========================================================================
    # SOURCE 4: AACT Condition-Based Queries
    # =========================================================================
    print("\n" + "-" * 70)
    print("  SOURCE 4: AACT Database Condition Queries")
    print("-" * 70)

    condition_queries = {
        "Heart Failure": ["heart failure", "cardiac failure", "cardiomyopathy"],
        "Myocardial Infarction": ["myocardial infarction", "heart attack", "acute coronary"],
        "Atrial Fibrillation": ["atrial fibrillation", "afib", "a-fib"],
        "Stroke": ["stroke", "cerebrovascular", "ischemic stroke"],
        "Hypertension": ["hypertension", "high blood pressure"],
        "Diabetes": ["diabetes mellitus", "type 2 diabetes", "type 1 diabetes"],
        "Cancer": ["cancer", "carcinoma", "neoplasm", "tumor", "lymphoma", "leukemia"],
        "COVID-19": ["covid-19", "sars-cov-2", "coronavirus"],
        "Obesity": ["obesity", "overweight", "weight loss"],
        "COPD": ["copd", "chronic obstructive pulmonary", "emphysema"],
    }

    aact_condition_ncts = {}
    for condition_name, terms in condition_queries.items():
        print(f"  Querying: {condition_name}...", end=" ", flush=True)
        ncts = get_condition_rcts(conn, terms, limit=150)
        aact_condition_ncts[condition_name] = ncts
        print(f"{len(ncts)} found")

    # =========================================================================
    # COMBINE ALL SOURCES
    # =========================================================================
    print("\n" + "=" * 70)
    print("  COMBINED DATASET")
    print("=" * 70)

    all_ncts = set()
    all_ncts.update(cochrane_ncts)
    all_ncts.update(jcpt_ncts)
    all_ncts.update(landmark_ncts)
    for ncts in aact_condition_ncts.values():
        all_ncts.update(ncts)

    print(f"\n  Total unique NCT IDs: {len(all_ncts)}")
    print(f"    - Cochrane: {len(cochrane_ncts)}")
    print(f"    - JCPT Cardio: {len(jcpt_ncts)}")
    print(f"    - Landmark CV: {len(landmark_ncts)}")
    for cond, ncts in aact_condition_ncts.items():
        print(f"    - AACT {cond}: {len(ncts)}")

    # =========================================================================
    # VALIDATION: AACT Database
    # =========================================================================
    print("\n" + "=" * 70)
    print("  VALIDATION: AACT Database")
    print("=" * 70)

    found_in_aact = check_ncts_in_aact(conn, all_ncts)
    aact_recall = len(found_in_aact) / len(all_ncts) * 100 if all_ncts else 0

    print(f"\n  Found in AACT: {len(found_in_aact)}/{len(all_ncts)}")
    print(f"  AACT Recall: {aact_recall:.1f}%")

    missing_from_aact = all_ncts - found_in_aact
    if missing_from_aact:
        print(f"\n  Missing from AACT ({len(missing_from_aact)}):")
        for nct in list(missing_from_aact)[:10]:
            print(f"    {nct}")

    # =========================================================================
    # VALIDATION: CT.gov API Comparison (Sample)
    # =========================================================================
    print("\n" + "=" * 70)
    print("  VALIDATION: CT.gov API Comparison (Sample Test)")
    print("=" * 70)

    # Test subset - curated gold standard (Cochrane + JCPT + Landmark)
    gold_standard = cochrane_ncts | jcpt_ncts | landmark_ncts
    print(f"\n  Gold Standard Size: {len(gold_standard)} NCT IDs")

    # Check AACT
    found_aact = check_ncts_in_aact(conn, gold_standard)
    aact_recall_gold = len(found_aact) / len(gold_standard) * 100 if gold_standard else 0

    print(f"\n  AACT Direct Lookup: {len(found_aact)}/{len(gold_standard)} ({aact_recall_gold:.1f}%)")

    # Check CT.gov API for subset
    print("\n  Testing CT.gov API condition searches...")
    test_conditions = ["heart failure", "myocardial infarction", "atrial fibrillation", "diabetes"]

    api_found = set()
    for cond in test_conditions:
        print(f"    Searching: {cond}...", end=" ", flush=True)
        found = search_ctgov_api(cond)
        overlap = found & gold_standard
        api_found.update(overlap)
        print(f"found {len(overlap)} matches")

    api_recall = len(api_found) / len(gold_standard) * 100 if gold_standard else 0
    print(f"\n  CT.gov API (4 conditions): {len(api_found)}/{len(gold_standard)} ({api_recall:.1f}%)")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("  FINAL SUMMARY")
    print("=" * 70)

    print(f"""
  COMPREHENSIVE DATASET:
    Total NCT IDs:          {len(all_ncts)}
    From Literature:        {len(cochrane_ncts | jcpt_ncts | landmark_ncts)}
    From AACT Queries:      {len(all_ncts) - len(cochrane_ncts | jcpt_ncts | landmark_ncts)}

  AACT DATABASE PERFORMANCE:
    Total Found:            {len(found_in_aact)}/{len(all_ncts)} ({aact_recall:.1f}%)
    Missing:                {len(missing_from_aact)}

  GOLD STANDARD TEST (n={len(gold_standard)}):
    AACT Recall:            {aact_recall_gold:.1f}%
    CT.gov API Recall:      {api_recall:.1f}%
    AACT Advantage:         +{aact_recall_gold - api_recall:.1f}%
""")

    # Save results
    output_file = output_dir / f"comprehensive_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    export = {
        "timestamp": datetime.now().isoformat(),
        "sources": {
            "cochrane": len(cochrane_ncts),
            "jcpt_cardiovascular": len(jcpt_ncts),
            "landmark_cv": len(landmark_ncts),
            "aact_conditions": {k: len(v) for k, v in aact_condition_ncts.items()}
        },
        "total_unique": len(all_ncts),
        "aact_found": len(found_in_aact),
        "aact_recall": aact_recall,
        "missing_from_aact": list(missing_from_aact),
        "gold_standard": {
            "size": len(gold_standard),
            "aact_recall": aact_recall_gold,
            "api_recall": api_recall,
            "aact_advantage": aact_recall_gold - api_recall
        },
        "all_nct_ids": list(all_ncts)
    }

    with open(output_file, 'w') as f:
        json.dump(export, f, indent=2, default=list)

    print(f"  Results saved: {output_file}")

    conn.close()

if __name__ == "__main__":
    main()
