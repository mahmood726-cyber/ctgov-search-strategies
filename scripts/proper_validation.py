#!/usr/bin/env python3
"""
Proper Validation of Search Strategies
Tests whether CT.gov searches find trials that were independently identified.

The key insight: We need to verify if a search strategy finds trials
that we KNOW exist (from independent sources like PubMed publications),
not just count what the search returns.

Author: Mahmood Ahmad
Version: 4.1
"""

import json
import csv
import time
import math
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass, field
from pathlib import Path
import requests


# =============================================================================
# WILSON SCORE CI
# =============================================================================

def wilson_score_interval(successes: int, trials: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Wilson score confidence interval for a proportion"""
    if trials == 0:
        return (0.0, 0.0)

    p = successes / trials
    z = 1.96 if confidence == 0.95 else 2.576

    denominator = 1 + z**2 / trials
    center = (p + z**2 / (2 * trials)) / denominator
    margin = z * math.sqrt((p * (1-p) + z**2 / (4 * trials)) / trials) / denominator

    return (max(0, center - margin), min(1, center + margin))


# =============================================================================
# CT.GOV VALIDATION
# =============================================================================

class CTGovValidator:
    """
    Validates search strategies by checking if known NCT IDs appear in search results.

    Proper validation approach:
    1. Start with independently identified NCT IDs (from PubMed publications)
    2. For each NCT ID, get its registered condition from CT.gov
    3. Run each search strategy for that condition
    4. Check if the NCT ID appears in the results
    5. Calculate recall = found / total known NCT IDs
    """

    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ValidationSuite/4.1"
        })

    def get_trial_condition(self, nct_id: str) -> Optional[str]:
        """Get the primary condition for an NCT ID"""
        try:
            url = f"{self.BASE_URL}/{nct_id}"
            params = {"fields": "NCTId,Condition"}

            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            conditions = data.get("protocolSection", {}).get(
                "conditionsModule", {}
            ).get("conditions", [])

            return conditions[0] if conditions else None

        except Exception:
            return None

    def search_by_condition(self, condition: str, strategy: str = "S1") -> Set[str]:
        """
        Run a search strategy and return set of NCT IDs found.

        Strategies:
        - S1: Condition only (baseline)
        - S2: Interventional studies
        - S3: Randomized allocation
        - S6: Completed status
        - S10: Treatment RCTs
        """
        params = {
            "query.cond": condition,
            "fields": "NCTId",
            "pageSize": 1000
        }

        # Add strategy-specific filters
        if strategy == "S2":
            params["query.term"] = "AREA[StudyType]INTERVENTIONAL"
        elif strategy == "S3":
            params["query.term"] = "AREA[DesignAllocation]RANDOMIZED"
        elif strategy == "S6":
            params["filter.overallStatus"] = "COMPLETED"
        elif strategy == "S10":
            params["query.term"] = "AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT"

        nct_ids = set()

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()

            for study in data.get("studies", []):
                nct_id = study.get("protocolSection", {}).get(
                    "identificationModule", {}
                ).get("nctId")
                if nct_id:
                    nct_ids.add(nct_id)

        except Exception as e:
            print(f"Search error: {e}")

        return nct_ids

    def validate_strategy(
        self,
        nct_ids: List[str],
        strategy: str = "S1"
    ) -> Dict:
        """
        Validate a strategy against a list of known NCT IDs.

        For each NCT ID:
        1. Get its registered condition
        2. Search CT.gov for that condition using the strategy
        3. Check if the NCT ID is in the results
        """
        results = {
            "strategy": strategy,
            "total_tested": 0,
            "found": 0,
            "not_found": 0,
            "invalid": 0,
            "details": []
        }

        # Cache search results to avoid repeated searches
        search_cache = {}

        for i, nct_id in enumerate(nct_ids):
            print(f"\r  [{i+1}/{len(nct_ids)}] Testing {nct_id}...", end="", flush=True)

            # Get condition for this trial
            condition = self.get_trial_condition(nct_id)

            if not condition:
                results["invalid"] += 1
                results["details"].append({
                    "nct_id": nct_id,
                    "status": "invalid",
                    "reason": "Not found in CT.gov or no condition"
                })
                time.sleep(0.3)
                continue

            results["total_tested"] += 1

            # Check cache or run search
            cache_key = f"{condition}:{strategy}"
            if cache_key not in search_cache:
                search_results = self.search_by_condition(condition, strategy)
                search_cache[cache_key] = search_results
                time.sleep(0.5)  # Rate limiting
            else:
                search_results = search_cache[cache_key]

            # Check if NCT ID was found
            if nct_id in search_results:
                results["found"] += 1
                results["details"].append({
                    "nct_id": nct_id,
                    "condition": condition,
                    "status": "found"
                })
            else:
                results["not_found"] += 1
                results["details"].append({
                    "nct_id": nct_id,
                    "condition": condition,
                    "status": "not_found",
                    "search_returned": len(search_results)
                })

        print()  # New line after progress

        # Calculate metrics
        if results["total_tested"] > 0:
            recall = results["found"] / results["total_tested"]
            ci_low, ci_high = wilson_score_interval(
                results["found"],
                results["total_tested"]
            )

            results["metrics"] = {
                "recall": round(recall, 4),
                "recall_pct": f"{recall:.1%}",
                "ci_95_lower": round(ci_low, 4),
                "ci_95_upper": round(ci_high, 4),
                "ci_95_formatted": f"{ci_low:.1%} - {ci_high:.1%}"
            }

        return results


# =============================================================================
# MAIN VALIDATION RUNNER
# =============================================================================

def run_full_validation(gold_standard_path: str, output_dir: str, max_trials: int = 100, min_year: int = None):
    """Run complete validation suite

    Args:
        gold_standard_path: Path to gold standard CSV/JSON
        output_dir: Output directory
        max_trials: Maximum trials to test
        min_year: Minimum publication year filter (e.g., 2015 for post-2015 only)
    """

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    validator = CTGovValidator()

    # Load gold standard
    print("Loading gold standard...")
    nct_ids = []
    year_filter_msg = ""

    if gold_standard_path.endswith('.json'):
        with open(gold_standard_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            total_before_filter = len(data.get("trials", []))
            for trial in data.get("trials", []):
                nct_id = trial.get("nct_id", "")
                year = trial.get("year", 0)
                if nct_id:
                    # Apply year filter if specified
                    if min_year and year and year < min_year:
                        continue
                    nct_ids.append(nct_id)
            if min_year:
                year_filter_msg = f" (filtered from {total_before_filter} to {len(nct_ids)} post-{min_year})"
    else:
        with open(gold_standard_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                nct_id = row.get("nct_id", "")
                year = int(row.get("year", 0)) if row.get("year", "").isdigit() else 0
                if nct_id:
                    if min_year and year and year < min_year:
                        continue
                    nct_ids.append(nct_id)

    # Limit for testing
    nct_ids = nct_ids[:max_trials]
    print(f"Testing {len(nct_ids)} NCT IDs{year_filter_msg}")

    # Test all strategies
    strategies = ["S1", "S2", "S3", "S6", "S10"]
    all_results = []

    for strategy in strategies:
        print(f"\n{'='*60}")
        print(f"Testing Strategy {strategy}")
        print('='*60)

        result = validator.validate_strategy(nct_ids, strategy)
        all_results.append(result)

        # Print summary
        if "metrics" in result:
            print(f"\nResults for {strategy}:")
            print(f"  Recall: {result['metrics']['recall_pct']}")
            print(f"  95% CI: {result['metrics']['ci_95_formatted']}")
            print(f"  Found: {result['found']}/{result['total_tested']}")
            print(f"  Invalid NCTs: {result['invalid']}")

    # Generate summary report
    print(f"\n{'='*60}")
    print("VALIDATION SUMMARY")
    print('='*60)

    year_info = f" (publications {min_year}+)" if min_year else ""
    summary_lines = [
        "# CT.gov Search Strategy Validation",
        "",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        f"**Gold Standard:** {len(nct_ids)} independently-identified NCT IDs{year_info}",
        f"**Method:** For each NCT ID, retrieve its condition from CT.gov, run search, check if NCT appears in results",
        "",
        "## Results with 95% Confidence Intervals",
        "",
        "| Strategy | Recall | 95% CI | Found/Total |",
        "|----------|--------|--------|-------------|"
    ]

    for result in all_results:
        if "metrics" in result:
            m = result["metrics"]
            summary_lines.append(
                f"| {result['strategy']} | {m['recall_pct']} | {m['ci_95_formatted']} | "
                f"{result['found']}/{result['total_tested']} |"
            )

    summary_lines.extend([
        "",
        "## Interpretation",
        "",
        "- **S1 (Condition Only):** Baseline - should have highest recall",
        "- **S2 (Interventional):** Excludes observational studies",
        "- **S3 (Randomized):** True RCTs only",
        "- **S6 (Completed):** Finished studies",
        "- **S10 (Treatment RCTs):** Most restrictive",
        "",
        "## Key Finding",
        "",
        "Using an independent gold standard (NCT IDs from published papers in PubMed),",
        "we can measure TRUE recall rather than circular validation.",
        "",
        "---",
        "*Generated by CT.gov Trial Registry Integrity Suite v4.1*"
    ])

    summary = "\n".join(summary_lines)

    # Save outputs
    summary_path = output_path / "proper_validation_report.md"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary)
    print(f"\nSummary saved to {summary_path}")

    json_path = output_path / "proper_validation_results.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gold_standard_size": len(nct_ids),
            "strategies": all_results
        }, f, indent=2)
    print(f"JSON saved to {json_path}")

    return all_results


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Proper Validation of CT.gov Search Strategies")
    parser.add_argument("gold_standard", help="Path to gold standard CSV/JSON")
    parser.add_argument("-o", "--output", default="output",
                       help="Output directory")
    parser.add_argument("-n", "--max-trials", type=int, default=50,
                       help="Maximum trials to test (for speed)")
    parser.add_argument("-y", "--min-year", type=int, default=None,
                       help="Minimum publication year (e.g., 2015 for post-2015 RCTs)")

    args = parser.parse_args()

    run_full_validation(
        args.gold_standard,
        args.output,
        args.max_trials,
        args.min_year
    )


if __name__ == "__main__":
    main()
