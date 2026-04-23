# sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files.
"""
Validate NCT IDs against ClinicalTrials.gov API.

Tests extracted NCT IDs to determine CT.gov API recall rate
and identifies which NCT IDs are findable through the API.
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Paths
VALIDATION_DATA_PATH = r"C:\Users\user\Downloads\ctgov-search-strategies\tests\validation_data"
OUTPUT_PATH = VALIDATION_DATA_PATH

# CT.gov API endpoint
CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"


def validate_nct_id(nct_id):
    """Check if an NCT ID exists on ClinicalTrials.gov."""
    try:
        # Clean NCT ID
        nct_id = nct_id.strip().upper()
        if not nct_id.startswith('NCT'):
            nct_id = f"NCT{nct_id}"

        # Query the API
        params = {
            'query.id': nct_id,
            'fields': 'NCTId,BriefTitle,OverallStatus,StudyType,Phase,Condition',
            'pageSize': 1
        }

        response = requests.get(CTGOV_API, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            studies = data.get('studies', [])

            if studies:
                study = studies[0]
                protocol = study.get('protocolSection', {})
                id_module = protocol.get('identificationModule', {})
                design_module = protocol.get('designModule', {})
                status_module = protocol.get('statusModule', {})
                conditions = protocol.get('conditionsModule', {})

                return {
                    'found': True,
                    'nct_id': id_module.get('nctId', nct_id),
                    'title': id_module.get('briefTitle', ''),
                    'status': status_module.get('overallStatus', ''),
                    'study_type': design_module.get('studyType', ''),
                    'phases': design_module.get('phases', []),
                    'conditions': conditions.get('conditions', [])
                }
            else:
                return {'found': False, 'nct_id': nct_id, 'reason': 'not_found'}
        else:
            return {'found': False, 'nct_id': nct_id, 'reason': f'api_error_{response.status_code}'}

    except requests.Timeout:
        return {'found': False, 'nct_id': nct_id, 'reason': 'timeout'}
    except Exception as e:
        return {'found': False, 'nct_id': nct_id, 'reason': str(e)}


def batch_validate(nct_ids, batch_size=50, delay=0.3):
    """Validate a batch of NCT IDs with rate limiting."""
    results = {
        'found': [],
        'not_found': [],
        'errors': [],
        'by_condition': defaultdict(list),
        'by_status': defaultdict(int),
        'by_phase': defaultdict(int),
        'by_study_type': defaultdict(int)
    }

    total = len(nct_ids)
    print(f"Validating {total} NCT IDs...")

    for i, nct_id in enumerate(nct_ids):
        if i > 0 and i % 100 == 0:
            print(f"  Progress: {i}/{total} ({100*i/total:.1f}%)")

        result = validate_nct_id(nct_id)

        if result['found']:
            results['found'].append(result)

            # Categorize by condition
            for condition in result.get('conditions', []):
                results['by_condition'][condition.lower()].append(nct_id)

            # Count by status
            status = result.get('status', 'Unknown')
            results['by_status'][status] += 1

            # Count by phase
            phases = result.get('phases', [])
            for phase in phases:
                results['by_phase'][phase] += 1

            # Count by study type
            study_type = result.get('study_type', 'Unknown')
            results['by_study_type'][study_type] += 1

        else:
            if 'error' in result.get('reason', '').lower():
                results['errors'].append(result)
            else:
                results['not_found'].append(result)

        time.sleep(delay)

    return results


def categorize_conditions(conditions_dict):
    """Categorize conditions into medical specialties."""
    categories = {
        'oncology': ['cancer', 'carcinoma', 'tumor', 'leukemia', 'lymphoma', 'melanoma', 'neoplasm'],
        'cardiology': ['heart', 'cardiac', 'cardiovascular', 'hypertension', 'atrial', 'coronary', 'stroke'],
        'neurology': ['alzheimer', 'parkinson', 'epilepsy', 'multiple sclerosis', 'dementia', 'migraine'],
        'psychiatry': ['depression', 'anxiety', 'schizophrenia', 'bipolar', 'ptsd', 'mental'],
        'endocrinology': ['diabetes', 'thyroid', 'insulin', 'metabolic', 'obesity'],
        'infectious': ['hiv', 'aids', 'hepatitis', 'covid', 'tuberculosis', 'infection', 'virus'],
        'respiratory': ['asthma', 'copd', 'pulmonary', 'lung', 'respiratory'],
        'rheumatology': ['arthritis', 'rheumatoid', 'lupus', 'fibromyalgia'],
        'gastroenterology': ['crohn', 'ulcerative', 'ibs', 'liver', 'cirrhosis'],
        'nephrology': ['kidney', 'renal', 'dialysis'],
        'pediatrics': ['infant', 'child', 'neonatal', 'pediatric'],
        'obstetrics': ['pregnancy', 'prenatal', 'maternal', 'gestational']
    }

    categorized = defaultdict(list)

    for condition, nct_ids in conditions_dict.items():
        condition_lower = condition.lower()
        matched = False

        for category, keywords in categories.items():
            if any(kw in condition_lower for kw in keywords):
                categorized[category].extend(nct_ids)
                matched = True
                break

        if not matched:
            categorized['other'].extend(nct_ids)

    # Deduplicate
    for category in categorized:
        categorized[category] = list(set(categorized[category]))

    return dict(categorized)


def main():
    print("=" * 60)
    print("NCT ID Validation Against ClinicalTrials.gov API")
    print("=" * 60)
    print()

    # Load extracted NCT IDs
    validation_file = Path(VALIDATION_DATA_PATH) / 'cochrane_validation_ncts.json'

    if not validation_file.exists():
        print(f"Error: Validation file not found: {validation_file}")
        print("Please run extract_nct_from_cochrane.py first.")
        return

    with open(validation_file) as f:
        data = json.load(f)

    nct_ids = data['nct_ids']
    print(f"Loaded {len(nct_ids)} NCT IDs from Cochrane extraction")

    # Limit for testing (remove for full validation)
    sample_size = min(200, len(nct_ids))  # Test with 200 first
    test_ncts = nct_ids[:sample_size]

    print(f"\nValidating sample of {sample_size} NCT IDs...")
    print("(Use full dataset for complete validation)")
    print()

    # Run validation
    results = batch_validate(test_ncts)

    # Calculate statistics
    found_count = len(results['found'])
    not_found_count = len(results['not_found'])
    error_count = len(results['errors'])
    total_tested = found_count + not_found_count + error_count

    recall_rate = 100 * found_count / total_tested if total_tested > 0 else 0
    miss_rate = 100 - recall_rate

    print()
    print("=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)
    print(f"Total tested: {total_tested}")
    print(f"Found on CT.gov: {found_count} ({recall_rate:.1f}%)")
    print(f"Not found: {not_found_count} ({100*not_found_count/total_tested:.1f}%)")
    print(f"Errors: {error_count}")
    print()
    print(f"API RECALL RATE: {recall_rate:.1f}%")
    print(f"API MISS RATE: {miss_rate:.1f}%")
    print()

    # Study type breakdown
    print("By Study Type:")
    for study_type, count in sorted(results['by_study_type'].items(), key=lambda x: -x[1]):
        print(f"  {study_type}: {count}")
    print()

    # Phase breakdown
    print("By Phase:")
    for phase, count in sorted(results['by_phase'].items(), key=lambda x: -x[1]):
        print(f"  {phase}: {count}")
    print()

    # Status breakdown
    print("By Status:")
    for status, count in sorted(results['by_status'].items(), key=lambda x: -x[1]):
        print(f"  {status}: {count}")
    print()

    # Categorize by medical specialty
    categorized = categorize_conditions(results['by_condition'])
    print("By Medical Category:")
    for category, ncts in sorted(categorized.items(), key=lambda x: -len(x[1])):
        print(f"  {category}: {len(ncts)} NCT IDs")
    print()

    # Save results
    output_dir = Path(OUTPUT_PATH)

    validation_results = {
        'validation_date': datetime.now().isoformat(),
        'sample_size': sample_size,
        'statistics': {
            'total_tested': total_tested,
            'found': found_count,
            'not_found': not_found_count,
            'errors': error_count,
            'recall_rate': recall_rate,
            'miss_rate': miss_rate
        },
        'found_nct_ids': [r['nct_id'] for r in results['found']],
        'not_found_nct_ids': [r['nct_id'] for r in results['not_found']],
        'by_category': categorized,
        'by_status': dict(results['by_status']),
        'by_phase': dict(results['by_phase']),
        'by_study_type': dict(results['by_study_type']),
        'detailed_results': results['found'][:50]  # Sample of detailed results
    }

    with open(output_dir / 'ctgov_validation_results.json', 'w') as f:
        json.dump(validation_results, f, indent=2)
    print(f"Results saved to: {output_dir / 'ctgov_validation_results.json'}")

    # Sample of not found NCT IDs
    if results['not_found']:
        print()
        print("Sample of NCT IDs NOT found on CT.gov:")
        for r in results['not_found'][:10]:
            print(f"  {r['nct_id']}")


if __name__ == '__main__':
    main()
