#!/usr/bin/env python3
"""
ESC Cardiology Guidelines - Comprehensive RCT Search Strategy
Finds all RCTs relevant to ESC guideline meta-analyses

ESC Guidelines Coverage:
1. Heart Failure (2021/2023)
2. Atrial Fibrillation (2024)
3. Acute Coronary Syndromes (2023)
4. Chronic Coronary Syndromes (2024)
5. Cardiovascular Prevention (2021)
6. Valvular Heart Disease (2021)
7. Ventricular Arrhythmias (2022)
8. Pulmonary Hypertension (2022)
9. Cardiomyopathies (2023)
10. Peripheral Arterial Disease (2024)
"""

import psycopg2
import json
import os
from pathlib import Path
from datetime import datetime

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

# ============================================================================
# ESC LANDMARK TRIALS - NCT IDs from ESC Guidelines Meta-Analyses
# ============================================================================

ESC_LANDMARK_TRIALS = {
    # Heart Failure Guidelines (2021/2023)
    "Heart Failure": {
        "description": "ESC 2021/2023 Heart Failure Guidelines",
        "landmark_trials": [
            # SGLT2 Inhibitors
            "NCT03036124",  # DAPA-HF
            "NCT03057977",  # EMPEROR-Reduced
            "NCT03619213",  # EMPEROR-Preserved
            "NCT03521934",  # EMPEROR-Reduced (alt)
            "NCT03057951",  # EMPEROR-Preserved (alt)
            # ARNI
            "NCT01035255",  # PARADIGM-HF
            "NCT02924727",  # PARAGON-HF
            # Beta-Blockers
            "NCT00000560",  # BEST
            "NCT00000516",  # SOLVD
            # Ivabradine
            "NCT00407446",  # SHIFT
            # Vericiguat
            "NCT02861534",  # VICTORIA
            # MRA
            "NCT00000609",  # RALES (Aldactone)
            "NCT00232180",  # EMPHASIS-HF
            # Device Therapy
            "NCT00000607",  # REMATCH
            "NCT00271154",  # CARE-HF
            # Iron
            "NCT03037931",  # AFFIRM-AHF
            "NCT03036462",  # IRONMAN
        ],
        "search_terms": [
            "heart failure", "cardiac failure", "cardiomyopathy",
            "left ventricular dysfunction", "HFrEF", "HFpEF", "HFmrEF",
            "systolic heart failure", "diastolic heart failure",
            "congestive heart failure", "acute heart failure"
        ]
    },

    # Atrial Fibrillation Guidelines (2024)
    "Atrial Fibrillation": {
        "description": "ESC 2024 Atrial Fibrillation Guidelines",
        "landmark_trials": [
            # Rate vs Rhythm
            "NCT00004488",  # AFFIRM
            "NCT00106912",  # AF-CHF
            "NCT01288352",  # EAST-AFNET 4
            # DOACs
            "NCT00262600",  # RE-LY (dabigatran)
            "NCT00403767",  # ROCKET-AF (rivaroxaban)
            "NCT00412984",  # ARISTOTLE (apixaban)
            "NCT01150474",  # ENGAGE AF-TIMI 48 (edoxaban)
            # Ablation
            "NCT00911508",  # CASTLE-AF
            "NCT00794053",  # CABANA
            "NCT01420393",  # AATAC
            "NCT02039622",  # CAPTAF
            # LAA Closure
            "NCT00129545",  # PROTECT-AF
            "NCT01182441",  # PREVAIL
        ],
        "search_terms": [
            "atrial fibrillation", "AF", "AFib", "a-fib",
            "atrial flutter", "paroxysmal atrial fibrillation",
            "persistent atrial fibrillation", "permanent atrial fibrillation"
        ]
    },

    # Acute Coronary Syndromes Guidelines (2023)
    "Acute Coronary Syndromes": {
        "description": "ESC 2023 ACS Guidelines",
        "landmark_trials": [
            # Antiplatelet
            "NCT00391872",  # TRITON-TIMI 38 (prasugrel)
            "NCT00528411",  # PLATO (ticagrelor)
            "NCT01187134",  # PEGASUS-TIMI 54
            "NCT02548650",  # TWILIGHT
            "NCT03234114",  # TICO
            # Revascularization
            "NCT01305993",  # COMPLETE
            "NCT02079636",  # CULPRIT-SHOCK
            # Lipid
            "NCT01764633",  # FOURIER
            "NCT01663402",  # ODYSSEY OUTCOMES
            # Anti-ischemic
            "NCT00469729",  # OASIS 5
            "NCT00127517",  # OASIS 6
            # Timing
            "NCT00428961",  # ACUITY
            "NCT00610532",  # TIMACS
        ],
        "search_terms": [
            "acute coronary syndrome", "ACS", "myocardial infarction",
            "STEMI", "NSTEMI", "unstable angina", "heart attack",
            "non-ST elevation", "ST elevation"
        ]
    },

    # Chronic Coronary Syndromes Guidelines (2024)
    "Chronic Coronary Syndromes": {
        "description": "ESC 2024 Chronic Coronary Syndromes Guidelines",
        "landmark_trials": [
            # Revascularization
            "NCT00086450",  # COURAGE
            "NCT01471522",  # ISCHEMIA
            "NCT01205776",  # FAME 2
            # Medical Therapy
            "NCT00327795",  # BEAUTIFUL
            "NCT01281774",  # SIGNIFY
            # Secondary Prevention
            "NCT00064207",  # TNT
            "NCT00318890",  # SEARCH
            # Anti-ischemic
            "NCT00126360",  # CAMELOT
        ],
        "search_terms": [
            "chronic coronary syndrome", "stable angina", "coronary artery disease",
            "ischemic heart disease", "stable CAD", "chronic stable angina",
            "effort angina", "stable coronary disease"
        ]
    },

    # Cardiovascular Prevention Guidelines (2021)
    "CV Prevention": {
        "description": "ESC 2021 CV Prevention Guidelines",
        "landmark_trials": [
            # Statin Trials
            "NCT00000479",  # 4S
            "NCT00000500",  # CARE
            "NCT00000506",  # LIPID
            # PCSK9
            "NCT01764633",  # FOURIER
            "NCT01663402",  # ODYSSEY OUTCOMES
            # Antiplatelet
            "NCT00501059",  # ARRIVE
            "NCT02110537",  # ASCEND
            "NCT00501098",  # ASPREE
            # Hypertension
            "NCT00000542",  # ALLHAT
            "NCT00206882",  # SPRINT
            "NCT00968708",  # HOPE-3
        ],
        "search_terms": [
            "cardiovascular prevention", "primary prevention",
            "secondary prevention", "risk reduction", "atherosclerosis",
            "hyperlipidemia", "dyslipidemia"
        ]
    },

    # Valvular Heart Disease Guidelines (2021)
    "Valvular Heart Disease": {
        "description": "ESC 2021 Valvular Heart Disease Guidelines",
        "landmark_trials": [
            # TAVI
            "NCT00530894",  # PARTNER A
            "NCT00688207",  # PARTNER B
            "NCT01314313",  # PARTNER 2
            "NCT02675114",  # PARTNER 3
            "NCT01057173",  # CoreValve High Risk
            "NCT01240902",  # SURTAVI
            # Mitral
            "NCT01626079",  # COAPT
            "NCT02371512",  # MITRA-FR
        ],
        "search_terms": [
            "aortic stenosis", "aortic regurgitation", "mitral regurgitation",
            "mitral stenosis", "valvular heart disease", "TAVI", "TAVR",
            "transcatheter aortic valve", "mitral valve repair"
        ]
    },

    # Ventricular Arrhythmias Guidelines (2022)
    "Ventricular Arrhythmias": {
        "description": "ESC 2022 Ventricular Arrhythmias Guidelines",
        "landmark_trials": [
            # ICD
            "NCT00000558",  # MADIT
            "NCT00000609",  # SCD-HeFT
            "NCT00004488",  # AVID
            "NCT00271154",  # COMPANION
            # Ablation
            "NCT01045070",  # VANISH
            "NCT02130765",  # STAR
        ],
        "search_terms": [
            "ventricular tachycardia", "ventricular fibrillation",
            "sudden cardiac death", "VT", "VF", "ICD",
            "implantable cardioverter defibrillator", "arrhythmia"
        ]
    },

    # Pulmonary Hypertension Guidelines (2022)
    "Pulmonary Hypertension": {
        "description": "ESC 2022 Pulmonary Hypertension Guidelines",
        "landmark_trials": [
            # "NCT00113829",  # BREATHE-1 (pre-2005, not in registry)
            "NCT00149487",  # SUPER-1
            "NCT01106014",  # SERAPHIN
            "NCT01106742",  # GRIPHON
            "NCT02631980",  # AMBITION
            "NCT00367770",  # BREATHE-5 (alternative bosentan trial)
            "NCT00070590",  # Bosentan in PAH (alternative)
        ],
        "search_terms": [
            "pulmonary hypertension", "pulmonary arterial hypertension",
            "PAH", "CTEPH", "right heart failure"
        ]
    },

    # Cardiomyopathies Guidelines (2023)
    "Cardiomyopathies": {
        "description": "ESC 2023 Cardiomyopathies Guidelines",
        "landmark_trials": [
            # HCM
            "NCT04349072",  # EXPLORER-HCM
            "NCT03470545",  # VALOR-HCM
            # TTR Amyloid
            "NCT01927757",  # ATTR-ACT
            "NCT03759379",  # APOLLO-B
        ],
        "search_terms": [
            "cardiomyopathy", "hypertrophic cardiomyopathy", "HCM",
            "dilated cardiomyopathy", "DCM", "restrictive cardiomyopathy",
            "arrhythmogenic cardiomyopathy", "cardiac amyloidosis"
        ]
    },

    # Peripheral Arterial Disease Guidelines (2024)
    "Peripheral Arterial Disease": {
        "description": "ESC 2024 Peripheral Arterial Disease Guidelines",
        "landmark_trials": [
            "NCT02504216",  # VOYAGER PAD
            "NCT01145079",  # COMPASS (vascular arm)
            "NCT02312102",  # EUCLID
        ],
        "search_terms": [
            "peripheral arterial disease", "PAD", "peripheral vascular disease",
            "claudication", "critical limb ischemia", "lower extremity artery disease"
        ]
    },
}


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


def search_condition_rcts(conn, search_terms, limit=500):
    """Search AACT for RCTs matching condition terms"""
    cursor = conn.cursor()

    like_clauses = " OR ".join([f"LOWER(c.name) LIKE '%{term.lower()}%'" for term in search_terms])

    query = f"""
        SELECT DISTINCT s.nct_id, s.brief_title, s.overall_status, d.allocation
        FROM studies s
        JOIN conditions c ON s.nct_id = c.nct_id
        JOIN designs d ON s.nct_id = d.nct_id
        WHERE ({like_clauses})
        AND d.allocation = 'RANDOMIZED'
        ORDER BY s.nct_id
        LIMIT {limit}
    """

    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    return [{"nct_id": r[0], "title": r[1], "status": r[2], "allocation": r[3]} for r in results]


def verify_landmark_trials(conn, nct_ids):
    """Verify landmark trials exist in AACT"""
    if not nct_ids:
        return [], []

    cursor = conn.cursor()
    placeholders = ','.join(['%s'] * len(nct_ids))
    query = f"""
        SELECT s.nct_id, s.brief_title, s.overall_status, d.allocation
        FROM studies s
        LEFT JOIN designs d ON s.nct_id = d.nct_id
        WHERE s.nct_id IN ({placeholders})
    """

    cursor.execute(query, list(nct_ids))
    results = cursor.fetchall()
    cursor.close()

    found = {r[0]: {"nct_id": r[0], "title": r[1], "status": r[2], "allocation": r[3]} for r in results}
    found_list = list(found.keys())
    missing_list = [nct for nct in nct_ids if nct not in found]

    return found_list, missing_list


def main():
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")

    print("=" * 70)
    print("  ESC CARDIOLOGY GUIDELINES - COMPREHENSIVE RCT SEARCH")
    print("=" * 70)

    conn = connect_aact()
    if not conn:
        return

    print("\nConnected to AACT database\n")

    # Results storage
    all_landmark_trials = set()
    all_condition_rcts = set()
    guideline_results = {}

    # Process each ESC guideline area
    for guideline_name, guideline_data in ESC_LANDMARK_TRIALS.items():
        print("-" * 70)
        print(f"  {guideline_name.upper()}")
        print(f"  {guideline_data['description']}")
        print("-" * 70)

        # 1. Verify landmark trials
        landmark_ncts = guideline_data['landmark_trials']
        found, missing = verify_landmark_trials(conn, landmark_ncts)

        print("\n  Landmark Trials:")
        print(f"    Defined: {len(landmark_ncts)}")
        print(f"    Found in AACT: {len(found)}")
        if missing:
            print(f"    Missing: {missing[:5]}{'...' if len(missing) > 5 else ''}")

        all_landmark_trials.update(found)

        # 2. Search for condition-based RCTs
        search_terms = guideline_data['search_terms']
        condition_rcts = search_condition_rcts(conn, search_terms, limit=300)
        condition_ncts = set(r['nct_id'] for r in condition_rcts)

        print(f"\n  Condition-Based Search ({len(search_terms)} terms):")
        print(f"    RCTs found: {len(condition_rcts)}")

        # Count statuses
        status_counts = {}
        for rct in condition_rcts:
            status = rct.get('status', 'Unknown')
            status_counts[status] = status_counts.get(status, 0) + 1

        print("    Status breakdown:")
        for status, count in sorted(status_counts.items(), key=lambda x: -x[1])[:4]:
            print(f"      {status}: {count}")

        all_condition_rcts.update(condition_ncts)

        # Store results
        guideline_results[guideline_name] = {
            "description": guideline_data['description'],
            "landmark_defined": len(landmark_ncts),
            "landmark_found": len(found),
            "landmark_ncts": found,
            "landmark_missing": missing,
            "condition_rcts": len(condition_rcts),
            "condition_ncts": list(condition_ncts)[:100],  # Limit for JSON
            "search_terms": search_terms
        }

        print()

    # =========================================================================
    # OVERALL SUMMARY
    # =========================================================================
    print("=" * 70)
    print("  OVERALL SUMMARY")
    print("=" * 70)

    total_unique = all_landmark_trials | all_condition_rcts

    print(f"""
  ESC GUIDELINES COVERAGE:
    Guidelines processed:     {len(ESC_LANDMARK_TRIALS)}

  LANDMARK TRIALS:
    Total defined:            {sum(len(g['landmark_trials']) for g in ESC_LANDMARK_TRIALS.values())}
    Unique found in AACT:     {len(all_landmark_trials)}

  CONDITION-BASED RCTs:
    Total found:              {len(all_condition_rcts)}

  COMBINED DATASET:
    Total unique NCT IDs:     {len(total_unique)}
""")

    # Per-guideline summary table
    print("  Per-Guideline Summary:")
    print(f"  {'Guideline':<30} {'Landmark':>10} {'Condition':>10} {'Total':>10}")
    print("-" * 65)

    for name, data in guideline_results.items():
        total = len(set(data['landmark_ncts']) | set(data['condition_ncts']))
        print(f"  {name:<30} {data['landmark_found']:>10} {data['condition_rcts']:>10} {total:>10}")

    print("-" * 65)
    print(f"  {'TOTAL (deduplicated)':<30} {len(all_landmark_trials):>10} {len(all_condition_rcts):>10} {len(total_unique):>10}")

    # Save results
    output_file = output_dir / f"esc_cardiology_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    export = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "guidelines_processed": len(ESC_LANDMARK_TRIALS),
            "landmark_trials_found": len(all_landmark_trials),
            "condition_rcts_found": len(all_condition_rcts),
            "total_unique_ncts": len(total_unique)
        },
        "per_guideline": guideline_results,
        "all_landmark_ncts": list(all_landmark_trials),
        "all_nct_ids": list(total_unique)
    }

    with open(output_file, 'w') as f:
        json.dump(export, f, indent=2)

    print(f"\n  Results saved: {output_file}")

    conn.close()
    print("\n  Database connection closed.")


if __name__ == "__main__":
    main()
