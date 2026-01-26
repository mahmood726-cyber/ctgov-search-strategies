"""
Extract NCT IDs from Cochrane Pairwise70 study-information files.

This script scans all *-study-information.csv files in the CochraneDataExtractor
data folder and extracts NCT IDs from the notes/registration fields.

Output:
- List of unique NCT IDs with metadata
- Statistics on NCT ID coverage by year
- JSON file with all extracted NCT IDs and their sources
"""

import os
import re
import csv
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Paths
COCHRANE_DATA_PATH = r"C:\Users\user\OneDrive - NHS\Documents\CochraneDataExtractor\data\pairwise"
OUTPUT_PATH = r"C:\Users\user\Downloads\ctgov-search-strategies\tests\validation_data"

# NCT ID pattern: NCT followed by 8+ digits
NCT_PATTERN = re.compile(r'\bNCT\s*(\d{7,11})\b', re.IGNORECASE)

# Other trial registry patterns
ISRCTN_PATTERN = re.compile(r'\bISRCTN\s*(\d+)\b', re.IGNORECASE)
EUCTR_PATTERN = re.compile(r'\b(EUCTR|EudraCT)[:\s-]*(\d{4}-\d{6}-\d{2})\b', re.IGNORECASE)
ACTRN_PATTERN = re.compile(r'\bACTRN(\d{14}[a-z]?)\b', re.IGNORECASE)
CHICTR_PATTERN = re.compile(r'\bChiCTR[-:]?(\d+)\b', re.IGNORECASE)
DRKS_PATTERN = re.compile(r'\bDRKS(\d+)\b', re.IGNORECASE)


def extract_nct_ids(text):
    """Extract all NCT IDs from text."""
    if not text or not isinstance(text, str):
        return []
    # Normalize: NCT 12345678 -> NCT12345678
    matches = NCT_PATTERN.findall(text)
    return [f"NCT{m.zfill(8)}" for m in matches]


def extract_all_registry_ids(text):
    """Extract all trial registry IDs from text."""
    if not text or not isinstance(text, str):
        return {}

    result = {
        'nct': [],
        'isrctn': [],
        'euctr': [],
        'actrn': [],
        'chictr': [],
        'drks': []
    }

    # NCT IDs
    for m in NCT_PATTERN.findall(text):
        result['nct'].append(f"NCT{m.zfill(8)}")

    # ISRCTN
    for m in ISRCTN_PATTERN.findall(text):
        result['isrctn'].append(f"ISRCTN{m}")

    # EudraCT
    for m in EUCTR_PATTERN.findall(text):
        if isinstance(m, tuple):
            result['euctr'].append(m[1])
        else:
            result['euctr'].append(m)

    # ANZCTR
    for m in ACTRN_PATTERN.findall(text):
        result['actrn'].append(f"ACTRN{m}")

    # ChiCTR
    for m in CHICTR_PATTERN.findall(text):
        result['chictr'].append(f"ChiCTR{m}")

    # DRKS
    for m in DRKS_PATTERN.findall(text):
        result['drks'].append(f"DRKS{m}")

    return result


def extract_year_from_study(study_name):
    """Extract year from study name like 'Smith 2015'."""
    match = re.search(r'\b(19\d{2}|20\d{2})\b', str(study_name))
    if match:
        return int(match.group(1))
    return None


def process_study_information_files():
    """Process all study-information CSV files and extract NCT IDs."""

    results = {
        'nct_ids': {},  # NCT ID -> {source, study, year, review_doi}
        'other_registries': defaultdict(list),  # registry type -> list of IDs
        'reviews_processed': 0,
        'studies_processed': 0,
        'studies_with_nct': 0,
        'studies_without_registration': 0,
        'nct_by_year': defaultdict(list),
        'errors': []
    }

    # Find all study-information.csv files
    data_path = Path(COCHRANE_DATA_PATH)
    study_info_files = list(data_path.glob("*-study-information.csv"))

    print(f"Found {len(study_info_files)} study-information.csv files")

    for csv_file in study_info_files:
        results['reviews_processed'] += 1

        # Extract review DOI from filename
        filename = csv_file.stem
        doi_match = re.search(r'10_1002_14651858_([A-Z]{2}\d+)(?:_pub\d+)?', filename)
        review_id = doi_match.group(1) if doi_match else filename

        try:
            with open(csv_file, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    results['studies_processed'] += 1

                    study_name = row.get('Study', '')
                    year = extract_year_from_study(study_name)

                    # Check multiple columns for registration info
                    search_fields = [
                        row.get('Char: Notes', ''),
                        row.get('ID: CRS', ''),
                        row.get('Data source', ''),
                        str(row)  # Search entire row as fallback
                    ]

                    combined_text = ' '.join(str(f) for f in search_fields if f)

                    # Extract all registry IDs
                    registry_ids = extract_all_registry_ids(combined_text)

                    # Process NCT IDs
                    nct_ids = registry_ids['nct']
                    if nct_ids:
                        results['studies_with_nct'] += 1
                        for nct_id in nct_ids:
                            if nct_id not in results['nct_ids']:
                                results['nct_ids'][nct_id] = {
                                    'source_reviews': [],
                                    'source_studies': [],
                                    'year': year
                                }
                            results['nct_ids'][nct_id]['source_reviews'].append(review_id)
                            results['nct_ids'][nct_id]['source_studies'].append(study_name)

                            if year:
                                results['nct_by_year'][year].append(nct_id)

                    # Process other registries
                    for registry, ids in registry_ids.items():
                        if registry != 'nct' and ids:
                            for reg_id in ids:
                                results['other_registries'][registry].append({
                                    'id': reg_id,
                                    'review': review_id,
                                    'study': study_name,
                                    'year': year
                                })

                    # Check if no registration at all
                    if not any(ids for ids in registry_ids.values()):
                        results['studies_without_registration'] += 1

        except Exception as e:
            results['errors'].append(f"{csv_file.name}: {str(e)}")
            print(f"Error processing {csv_file.name}: {e}")

    return results


def generate_validation_dataset(results, min_year=2005):
    """Generate validation dataset filtered by year."""

    # Filter NCT IDs by year (CT.gov mandatory after 2007, useful after 2005)
    validation_ncts = {}

    for nct_id, data in results['nct_ids'].items():
        year = data.get('year')
        # Include if year >= min_year OR if year is unknown (might be recent)
        if year is None or year >= min_year:
            validation_ncts[nct_id] = data

    return validation_ncts


def main():
    print("=" * 60)
    print("NCT ID Extraction from Cochrane Pairwise70 Dataset")
    print("=" * 60)
    print()

    # Process all files
    results = process_study_information_files()

    # Print statistics
    print()
    print("=" * 60)
    print("EXTRACTION RESULTS")
    print("=" * 60)
    print(f"Reviews processed: {results['reviews_processed']}")
    print(f"Studies processed: {results['studies_processed']}")
    print(f"Studies with NCT ID: {results['studies_with_nct']}")
    print(f"Studies without any registration: {results['studies_without_registration']}")
    print(f"Unique NCT IDs found: {len(results['nct_ids'])}")
    print()

    # Registry breakdown
    print("Other trial registries found:")
    for registry, ids in results['other_registries'].items():
        unique_ids = len(set(item['id'] for item in ids))
        print(f"  {registry.upper()}: {unique_ids} unique IDs")
    print()

    # Year distribution
    print("NCT IDs by publication year:")
    year_counts = {}
    for year, ncts in sorted(results['nct_by_year'].items()):
        unique_ncts = len(set(ncts))
        year_counts[year] = unique_ncts
        if year >= 2000:
            print(f"  {year}: {unique_ncts} NCT IDs")
    print()

    # Filter for validation
    validation_ncts = generate_validation_dataset(results, min_year=2005)
    print(f"NCT IDs from 2005 onwards (for validation): {len(validation_ncts)}")

    # Further filter for 2010+ (more reliable)
    ncts_2010_plus = generate_validation_dataset(results, min_year=2010)
    print(f"NCT IDs from 2010 onwards (high confidence): {len(ncts_2010_plus)}")

    # Save results
    output_dir = Path(OUTPUT_PATH)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save full results
    full_output = {
        'extraction_date': datetime.now().isoformat(),
        'source': 'Cochrane Pairwise70 Dataset',
        'statistics': {
            'reviews_processed': results['reviews_processed'],
            'studies_processed': results['studies_processed'],
            'studies_with_nct': results['studies_with_nct'],
            'unique_nct_ids': len(results['nct_ids']),
            'nct_ids_2005_plus': len(validation_ncts),
            'nct_ids_2010_plus': len(ncts_2010_plus)
        },
        'nct_ids': results['nct_ids'],
        'other_registries': {k: v for k, v in results['other_registries'].items()},
        'nct_by_year': {str(k): len(set(v)) for k, v in results['nct_by_year'].items()},
        'errors': results['errors']
    }

    with open(output_dir / 'cochrane_nct_extraction.json', 'w') as f:
        json.dump(full_output, f, indent=2)
    print(f"\nFull results saved to: {output_dir / 'cochrane_nct_extraction.json'}")

    # Save validation dataset (2010+)
    validation_output = {
        'source': 'Cochrane Pairwise70 Dataset - Studies from 2010+',
        'extraction_date': datetime.now().isoformat(),
        'description': 'NCT IDs extracted from Cochrane systematic reviews, filtered for 2010+ (high confidence CT.gov coverage)',
        'total_nct_ids': len(ncts_2010_plus),
        'nct_ids': list(ncts_2010_plus.keys())
    }

    with open(output_dir / 'cochrane_validation_ncts.json', 'w') as f:
        json.dump(validation_output, f, indent=2)
    print(f"Validation dataset saved to: {output_dir / 'cochrane_validation_ncts.json'}")

    # Save as Python module for easy import
    py_output = f'''"""
Validated NCT IDs extracted from Cochrane Pairwise70 Dataset.

Extraction date: {datetime.now().strftime('%Y-%m-%d')}
Source: 501 Cochrane systematic reviews
Total unique NCT IDs: {len(ncts_2010_plus)} (from studies 2010+)

These NCT IDs are from RCTs included in Cochrane reviews, providing
a gold-standard validation dataset for search strategy testing.
"""

# NCT IDs from Cochrane reviews (2010+ studies for high CT.gov coverage)
COCHRANE_NCT_IDS = {sorted(ncts_2010_plus.keys())}

# NCT IDs grouped by medical category (to be populated)
NCT_BY_CONDITION = {{}}

def get_all_nct_ids():
    """Return all validated NCT IDs."""
    return COCHRANE_NCT_IDS.copy()

def get_nct_count():
    """Return count of validated NCT IDs."""
    return len(COCHRANE_NCT_IDS)
'''

    with open(output_dir / 'cochrane_nct_ids.py', 'w') as f:
        f.write(py_output)
    print(f"Python module saved to: {output_dir / 'cochrane_nct_ids.py'}")

    # Print sample NCT IDs
    print()
    print("Sample NCT IDs found:")
    sample_ncts = list(ncts_2010_plus.keys())[:20]
    for nct_id in sample_ncts:
        data = ncts_2010_plus[nct_id]
        print(f"  {nct_id} - Year: {data.get('year', 'N/A')}, Review: {data['source_reviews'][0]}")

    if results['errors']:
        print()
        print(f"Errors encountered: {len(results['errors'])}")
        for err in results['errors'][:5]:
            print(f"  {err}")


if __name__ == '__main__':
    main()
