#!/usr/bin/env python3
"""
CT.gov Search Functions - Python Module
TruthCert TC-TRIALREG Enhanced
Version: 1.0.0

Evidence-based search functions for ClinicalTrials.gov API v2
Implements 10 validated search strategies with TruthCert verification
"""

import requests
import json
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from urllib.parse import urlencode, quote
import pandas as pd

# ============================================
# Configuration
# ============================================

CTGOV_API_BASE = "https://clinicaltrials.gov/api/v2/studies"

# Condition synonyms database (empirically validated)
CONDITION_SYNONYMS = {
    "diabetes": ["diabetes mellitus", "diabetic", "type 2 diabetes", "type 1 diabetes", "t2dm", "t1dm"],
    "hypertension": ["high blood pressure", "elevated blood pressure", "htn"],
    "depression": ["major depressive disorder", "mdd", "depressive disorder", "clinical depression"],
    "heart failure": ["cardiac failure", "chf", "congestive heart failure", "hf"],
    "stroke": ["cerebrovascular accident", "cva", "brain infarction", "ischemic stroke"],
    "breast cancer": ["breast neoplasm", "breast carcinoma", "mammary cancer"],
    "asthma": ["bronchial asthma", "asthmatic", "reactive airway disease"],
    "copd": ["chronic obstructive pulmonary disease", "emphysema", "chronic bronchitis"],
    "alzheimer": ["alzheimer disease", "alzheimer's disease", "ad", "dementia"],
    "parkinson": ["parkinson disease", "parkinson's disease", "pd", "parkinsonian"],
    "autism": ["autism spectrum disorder", "asd", "autistic disorder"],
    "covid-19": ["covid", "coronavirus", "sars-cov-2"],
    "cystic fibrosis": ["cf", "mucoviscidosis"],
    "psoriasis": ["plaque psoriasis"],
    "eczema": ["atopic dermatitis"]
}

# ============================================
# Data Classes
# ============================================

@dataclass
class SearchResult:
    """Result from a CT.gov API search"""
    success: bool
    total_count: int
    studies: List[Dict]
    time_sec: float
    url: str
    timestamp: str
    error: Optional[str] = None

@dataclass
class StrategyResult:
    """Result from running a search strategy"""
    strategy_id: str
    strategy_name: str
    expected_recall: float
    condition: str
    total_count: int
    time_sec: float
    url: str
    success: bool
    timestamp: str
    reduction_pct: float = 0.0

@dataclass
class ValidationResult:
    """Result from NCT ID validation"""
    nct_id: str
    valid: bool
    title: Optional[str] = None
    status: Optional[str] = None
    phase: Optional[str] = None
    study_type: Optional[str] = None
    error: Optional[str] = None

@dataclass
class TruthCertResult:
    """TruthCert validation result"""
    status: str  # SHIPPED or REJECTED
    scope_lock: Dict
    witness_results: List[Dict]
    agreement: float
    gate_b5_passed: bool
    timestamp: str

# ============================================
# Strategy Definitions
# ============================================

class Strategy:
    """Search strategy definition"""
    def __init__(self, id: str, name: str, expected_recall: float, build_fn):
        self.id = id
        self.name = name
        self.expected_recall = expected_recall
        self.build_fn = build_fn

    def build(self, condition: str) -> str:
        return self.build_fn(condition)

def _enc(s: str) -> str:
    """URL encode a string"""
    return quote(s, safe='')

STRATEGIES = {
    'S1': Strategy('S1', 'Condition Only (Maximum Recall)', 98.7,
                   lambda c: f"query.cond={_enc(c)}&countTotal=true&pageSize=100"),
    'S2': Strategy('S2', 'Interventional Studies', 98.7,
                   lambda c: f"query.cond={_enc(c)}&query.term={_enc('AREA[StudyType]INTERVENTIONAL')}&countTotal=true&pageSize=100"),
    'S3': Strategy('S3', 'Randomized Allocation Only', 98.7,
                   lambda c: f"query.cond={_enc(c)}&query.term={_enc('AREA[DesignAllocation]RANDOMIZED')}&countTotal=true&pageSize=100"),
    'S4': Strategy('S4', 'Phase 3/4 Studies', 45.5,
                   lambda c: f"query.cond={_enc(c)}&query.term={_enc('AREA[Phase](PHASE3 OR PHASE4)')}&countTotal=true&pageSize=100"),
    'S5': Strategy('S5', 'Has Posted Results', 63.6,
                   lambda c: f"query.cond={_enc(c)}&query.term={_enc('AREA[ResultsFirstPostDate]RANGE[MIN,MAX]')}&countTotal=true&pageSize=100"),
    'S6': Strategy('S6', 'Completed Status', 87.0,
                   lambda c: f"query.cond={_enc(c)}&filter.overallStatus=COMPLETED&countTotal=true&pageSize=100"),
    'S7': Strategy('S7', 'Interventional + Completed', 87.0,
                   lambda c: f"query.cond={_enc(c)}&query.term={_enc('AREA[StudyType]INTERVENTIONAL')}&filter.overallStatus=COMPLETED&countTotal=true&pageSize=100"),
    'S8': Strategy('S8', 'RCT + Phase 3/4 + Completed', 42.9,
                   lambda c: f"query.cond={_enc(c)}&query.term={_enc('AREA[DesignAllocation]RANDOMIZED AND AREA[Phase](PHASE3 OR PHASE4)')}&filter.overallStatus=COMPLETED&countTotal=true&pageSize=100"),
    'S9': Strategy('S9', 'Full-Text RCT Keywords', 79.2,
                   lambda c: f"query.term={_enc(c + ' AND randomized AND controlled')}&countTotal=true&pageSize=100"),
    'S10': Strategy('S10', 'Treatment RCTs Only', 89.6,
                    lambda c: f"query.cond={_enc(c)}&query.term={_enc('AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT')}&countTotal=true&pageSize=100"),
}

# ============================================
# Core Search Functions
# ============================================

def search_ctgov(query_string: str, max_results: int = 100, retry_count: int = 3) -> SearchResult:
    """
    Search ClinicalTrials.gov API

    Args:
        query_string: The query string to append to the API URL
        max_results: Maximum number of results to return (default: 100)
        retry_count: Number of retries on failure (default: 3)

    Returns:
        SearchResult with totalCount, studies, time, and url
    """
    url = f"{CTGOV_API_BASE}?{query_string}"
    start_time = time.time()

    for attempt in range(retry_count):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            time_sec = round(time.time() - start_time, 2)

            return SearchResult(
                success=True,
                total_count=data.get('totalCount', 0),
                studies=data.get('studies', []),
                time_sec=time_sec,
                url=url,
                timestamp=datetime.now().isoformat()
            )
        except Exception as e:
            if attempt == retry_count - 1:
                return SearchResult(
                    success=False,
                    total_count=0,
                    studies=[],
                    time_sec=0,
                    url=url,
                    timestamp=datetime.now().isoformat(),
                    error=str(e)
                )
            time.sleep(2 ** attempt)  # Exponential backoff

def run_strategy(condition: str, strategy_id: str) -> StrategyResult:
    """
    Run a specific search strategy

    Args:
        condition: The medical condition to search
        strategy_id: The strategy ID (S1-S10)

    Returns:
        StrategyResult with strategy results and metadata
    """
    if strategy_id not in STRATEGIES:
        raise ValueError(f"Invalid strategy ID: {strategy_id}. Valid options: S1-S10")

    strategy = STRATEGIES[strategy_id]
    query_string = strategy.build(condition)
    result = search_ctgov(query_string)

    return StrategyResult(
        strategy_id=strategy_id,
        strategy_name=strategy.name,
        expected_recall=strategy.expected_recall,
        condition=condition,
        total_count=result.total_count,
        time_sec=result.time_sec,
        url=result.url,
        success=result.success,
        timestamp=result.timestamp
    )

def run_all_strategies(condition: str, strategies: List[str] = None) -> pd.DataFrame:
    """
    Run all 10 search strategies for a condition

    Args:
        condition: The medical condition to search
        strategies: List of strategy IDs to run (default: all)

    Returns:
        DataFrame with all strategy results
    """
    if strategies is None:
        strategies = list(STRATEGIES.keys())

    print(f"Running {len(strategies)} strategies for condition: {condition}")

    results = []
    baseline = 0

    for sid in strategies:
        print(f"  Running {sid}...")
        res = run_strategy(condition, sid)

        if sid == 'S1':
            baseline = res.total_count

        results.append(asdict(res))

    df = pd.DataFrame(results)

    # Calculate reduction from baseline
    if baseline > 0:
        df['reduction_pct'] = round((1 - df['total_count'] / baseline) * 100, 1)
    else:
        df['reduction_pct'] = 0

    return df

# ============================================
# NCT ID Validation Functions
# ============================================

def validate_nct_id(nct_id: str) -> ValidationResult:
    """
    Validate a single NCT ID

    Args:
        nct_id: The NCT ID to validate (e.g., "NCT00000001")

    Returns:
        ValidationResult with validation result and study details
    """
    import re
    if not re.match(r'^NCT\d+$', nct_id, re.IGNORECASE):
        return ValidationResult(nct_id=nct_id, valid=False, error="Invalid NCT ID format")

    url = f"{CTGOV_API_BASE}?query.id={nct_id}&pageSize=1"

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get('studies'):
            study = data['studies'][0]
            protocol = study.get('protocolSection', {})
            id_module = protocol.get('identificationModule', {})
            status_module = protocol.get('statusModule', {})
            design_module = protocol.get('designModule', {})

            return ValidationResult(
                nct_id=nct_id,
                valid=True,
                title=id_module.get('briefTitle'),
                status=status_module.get('overallStatus'),
                phase=', '.join(design_module.get('phases', ['N/A'])),
                study_type=design_module.get('studyType')
            )
        else:
            return ValidationResult(nct_id=nct_id, valid=False, error="NCT ID not found")

    except Exception as e:
        return ValidationResult(nct_id=nct_id, valid=False, error=str(e))

def validate_nct_ids(nct_ids: List[str], progress: bool = True) -> pd.DataFrame:
    """
    Validate multiple NCT IDs

    Args:
        nct_ids: List of NCT IDs
        progress: Show progress (default: True)

    Returns:
        DataFrame with validation results
    """
    if progress:
        print(f"Validating {len(nct_ids)} NCT IDs...")

    results = []
    for nct_id in nct_ids:
        if progress:
            print(f"  Checking {nct_id}...")
        res = validate_nct_id(nct_id)
        results.append(asdict(res))
        time.sleep(0.5)  # Rate limiting

    df = pd.DataFrame(results)

    if progress:
        valid_count = df['valid'].sum()
        print(f"Validation complete: {valid_count} valid, {len(df) - valid_count} invalid")

    return df

# ============================================
# TruthCert TC-TRIALREG Functions
# ============================================

def create_scope_lock(condition: str, synonyms: List[str] = None) -> Dict:
    """
    Create a TruthCert scope lock for a search

    Args:
        condition: The medical condition
        synonyms: List of synonyms (optional)

    Returns:
        Scope lock dictionary
    """
    if synonyms is None:
        synonyms = CONDITION_SYNONYMS.get(condition.lower(), [])

    scope_data = {
        'condition': condition,
        'synonyms': synonyms,
        'source_type': 'ClinicalTrials.gov',
        'api_version': 'v2',
        'timestamp': datetime.now().isoformat()
    }

    scope_data['hash'] = hashlib.sha256(
        json.dumps(scope_data, sort_keys=True).encode()
    ).hexdigest()

    return scope_data

def truthcert_validate(condition: str, witness_strategies: List[str] = None) -> TruthCertResult:
    """
    Run TruthCert multi-witness validation

    Args:
        condition: The medical condition
        witness_strategies: List of strategy IDs (minimum 3)

    Returns:
        TruthCertResult with status (SHIPPED/REJECTED)
    """
    if witness_strategies is None:
        witness_strategies = ['S1', 'S3', 'S10']

    if len(witness_strategies) < 3:
        raise ValueError("TruthCert requires minimum 3 witnesses")

    print("=== TruthCert TC-TRIALREG Validation ===")
    print(f"Scope Lock: condition = '{condition}'")
    print(f"Witnesses: {', '.join(witness_strategies)}")

    # Create scope lock
    scope_lock = create_scope_lock(condition)

    # Run witnesses
    witness_results = []
    for sid in witness_strategies:
        print(f"  Running witness {sid}...")
        res = run_strategy(condition, sid)
        witness_results.append(asdict(res))

    # Check agreement (Gate B5)
    counts = [w['total_count'] for w in witness_results]
    mean_count = sum(counts) / len(counts)
    max_diff = max(counts) - min(counts)
    agreement = 1 - (max_diff / mean_count) if mean_count > 0 else 0

    print(f"  Witness counts: {', '.join(map(str, counts))}")
    print(f"  Agreement: {agreement * 100:.1f}%")

    # Determine status
    if agreement >= 0.80:
        status = "SHIPPED"
        print("  Gate B5: PASSED")
    else:
        status = "REJECTED"
        print("  Gate B5: FAILED")

    print(f"=== TruthCert Status: {status} ===")

    return TruthCertResult(
        status=status,
        scope_lock=scope_lock,
        witness_results=witness_results,
        agreement=round(agreement * 100, 1),
        gate_b5_passed=agreement >= 0.80,
        timestamp=datetime.now().isoformat()
    )

def create_ledger_entry(validation_result: TruthCertResult) -> Dict:
    """
    Create TruthCert audit log entry

    Args:
        validation_result: Result from truthcert_validate

    Returns:
        Formatted ledger entry dictionary
    """
    entry_data = asdict(validation_result)
    return {
        'bundle_id': hashlib.sha256(json.dumps(entry_data, sort_keys=True).encode()).hexdigest(),
        'lane': 'verification',
        'policy_anchor': {
            'scope_lock_ref': validation_result.scope_lock['hash'],
            'validator_version': 'validators-2026-01-v3',
            'thresholds': {'fact_agreement': 0.80}
        },
        'gate_outcomes': {
            'B5_semantic_agreement': validation_result.gate_b5_passed
        },
        'terminal_state': validation_result.status,
        'timestamp': validation_result.timestamp
    }

# ============================================
# Synonym Functions
# ============================================

def get_synonyms(condition: str) -> List[str]:
    """
    Get synonyms for a condition

    Args:
        condition: The medical condition

    Returns:
        List of synonyms including the condition itself
    """
    synonyms = CONDITION_SYNONYMS.get(condition.lower(), [])
    if not synonyms:
        print(f"No synonyms found for '{condition}'. Using condition only.")
        return [condition]
    return [condition] + synonyms

# ============================================
# Reporting Functions
# ============================================

def generate_strategy_report(condition: str, output_file: str = None) -> Dict:
    """
    Generate strategy comparison report

    Args:
        condition: The medical condition
        output_file: Optional file path to save report (JSON)

    Returns:
        Report dictionary
    """
    print(f"Generating strategy report for: {condition}")

    # Run all strategies
    results_df = run_all_strategies(condition)

    # Get baseline
    baseline = results_df[results_df['strategy_id'] == 'S1']['total_count'].values[0]

    report = {
        'condition': condition,
        'timestamp': datetime.now().isoformat(),
        'baseline_count': int(baseline),
        'strategy_results': results_df.to_dict('records'),
        'recommendations': {
            'max_sensitivity': 'S1, S2, or S3 (98.7% recall)',
            'balanced': 'S10 (89.6% recall, 60% reduction)',
            'focused': 'S8 (42.9% recall, 90% reduction)'
        },
        'synonyms': get_synonyms(condition),
        'registry_urls': {
            'ctgov': f"https://clinicaltrials.gov/search?cond={quote(condition)}",
            'ictrp': f"https://trialsearch.who.int/Default.aspx?SearchAll={quote(condition)}"
        }
    }

    if output_file:
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to: {output_file}")

    return report

def print_strategy_summary(results_df: pd.DataFrame):
    """
    Print strategy summary table

    Args:
        results_df: DataFrame from run_all_strategies
    """
    print("\n=== CT.gov Search Strategy Comparison ===\n")

    summary = results_df[['strategy_id', 'strategy_name', 'total_count',
                          'expected_recall', 'reduction_pct', 'time_sec']].copy()

    summary['total_count'] = summary['total_count'].apply(lambda x: f"{x:,}")
    summary['expected_recall'] = summary['expected_recall'].apply(lambda x: f"{x}%")
    summary['reduction_pct'] = summary['reduction_pct'].apply(lambda x: f"{x}%")
    summary['time_sec'] = summary['time_sec'].apply(lambda x: f"{x}s")

    print(summary.to_string(index=False))

    print("\n=== Recommendations ===")
    print("- Maximum sensitivity: Use S1, S2, or S3 (98.7% recall)")
    print("- Balanced approach: Use S10 (89.6% recall, ~60% reduction)")
    print("- Focused search: Use S8 (42.9% recall, ~90% reduction)")
    print("- ALWAYS: Also search WHO ICTRP and document search date\n")

# ============================================
# Main / Example Usage
# ============================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='CT.gov Search Strategy Tester')
    parser.add_argument('condition', help='Medical condition to search')
    parser.add_argument('--strategy', '-s', default=None, help='Strategy ID (S1-S10), or "all"')
    parser.add_argument('--validate-nct', '-n', nargs='+', help='NCT IDs to validate')
    parser.add_argument('--truthcert', '-t', action='store_true', help='Run TruthCert validation')
    parser.add_argument('--output', '-o', help='Output file for report (JSON)')

    args = parser.parse_args()

    if args.validate_nct:
        df = validate_nct_ids(args.validate_nct)
        print(df.to_string(index=False))
    elif args.truthcert:
        result = truthcert_validate(args.condition)
        print(f"\nFinal Status: {result.status}")
    elif args.strategy and args.strategy.upper() != 'ALL':
        result = run_strategy(args.condition, args.strategy.upper())
        print(f"\n{result.strategy_name}")
        print(f"Total count: {result.total_count:,}")
        print(f"Expected recall: {result.expected_recall}%")
        print(f"Time: {result.time_sec}s")
    else:
        results_df = run_all_strategies(args.condition)
        print_strategy_summary(results_df)

        if args.output:
            generate_strategy_report(args.condition, args.output)
