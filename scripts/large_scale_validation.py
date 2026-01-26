#!/usr/bin/env python3
"""
Large-Scale Validation - 10,000+ Trials
Tests if 95% recall is maintainable at scale for specific drug searches.

Author: Mahmood Ahmad
Version: 3.0
"""

import json
import math
import time
import re
from datetime import datetime, timezone
from typing import List, Dict, Set, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests


def wilson_ci(successes: int, n: int) -> Tuple[float, float]:
    """Wilson score 95% CI"""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    z = 1.96
    denom = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denom
    margin = z * math.sqrt((p * (1-p) + z**2 / (4*n)) / n) / denom
    return (max(0, center - margin), min(1, center + margin))


class LargeScaleValidator:
    """
    Large-scale validation of CT.gov search strategies.
    Builds gold standard from PubMed and validates at scale.
    """

    PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"

    # Specific drugs to test (high-volume drugs with many trials)
    DRUGS_TO_TEST = [
        # Diabetes
        ("metformin", "diabetes"),
        ("insulin", "diabetes"),
        ("semaglutide", "diabetes OR obesity"),
        ("liraglutide", "diabetes OR obesity"),
        ("empagliflozin", "diabetes OR heart failure"),
        ("dapagliflozin", "diabetes OR heart failure"),
        ("sitagliptin", "diabetes"),
        ("canagliflozin", "diabetes"),
        ("pioglitazone", "diabetes"),
        ("glipizide", "diabetes"),

        # Cardiovascular
        ("atorvastatin", "cardiovascular OR cholesterol"),
        ("rosuvastatin", "cardiovascular OR cholesterol"),
        ("lisinopril", "hypertension OR heart failure"),
        ("losartan", "hypertension"),
        ("metoprolol", "hypertension OR heart failure"),
        ("amlodipine", "hypertension"),
        ("warfarin", "atrial fibrillation OR thrombosis"),
        ("apixaban", "atrial fibrillation OR thrombosis"),
        ("rivaroxaban", "atrial fibrillation OR thrombosis"),
        ("clopidogrel", "cardiovascular"),

        # Oncology
        ("pembrolizumab", "cancer"),
        ("nivolumab", "cancer"),
        ("trastuzumab", "breast cancer"),
        ("bevacizumab", "cancer"),
        ("rituximab", "lymphoma OR leukemia"),
        ("paclitaxel", "cancer"),
        ("docetaxel", "cancer"),
        ("carboplatin", "cancer"),

        # Rheumatology/Immunology
        ("adalimumab", "arthritis OR psoriasis OR crohn"),
        ("etanercept", "arthritis OR psoriasis"),
        ("infliximab", "arthritis OR crohn"),
        ("tocilizumab", "arthritis"),
        ("tofacitinib", "arthritis"),
        ("baricitinib", "arthritis"),
        ("methotrexate", "arthritis OR cancer"),

        # Psychiatry
        ("sertraline", "depression OR anxiety"),
        ("fluoxetine", "depression"),
        ("escitalopram", "depression OR anxiety"),
        ("venlafaxine", "depression"),
        ("duloxetine", "depression OR pain"),
        ("quetiapine", "schizophrenia OR bipolar"),
        ("aripiprazole", "schizophrenia OR bipolar"),

        # Respiratory
        ("fluticasone", "asthma OR COPD"),
        ("budesonide", "asthma OR COPD"),
        ("tiotropium", "COPD"),
        ("montelukast", "asthma"),

        # Infectious Disease
        ("remdesivir", "COVID OR virus"),
        ("oseltamivir", "influenza"),
        ("tenofovir", "HIV OR hepatitis"),
        ("sofosbuvir", "hepatitis"),

        # Other
        ("omeprazole", "GERD OR ulcer"),
        ("pantoprazole", "GERD OR ulcer"),
        ("gabapentin", "pain OR epilepsy"),
        ("pregabalin", "pain OR epilepsy"),
        ("levothyroxine", "thyroid"),
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "LargeScaleValidator/3.0"})

    def get_nct_ids_from_pubmed(self, drug: str, condition: str, max_results: int = 500) -> Set[str]:
        """Get NCT IDs from PubMed publications mentioning the drug"""
        nct_ids = set()

        # Search PubMed for RCTs with this drug
        query = f'"{drug}"[Title/Abstract] AND ({condition})[Title/Abstract] AND (randomized controlled trial[pt] OR clinical trial[pt])'

        try:
            # Search
            url = f"{self.PUBMED_API}/esearch.fcgi"
            params = {
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json"
            }
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            pmids = response.json().get("esearchresult", {}).get("idlist", [])
            time.sleep(0.35)

            # Fetch details in batches
            batch_size = 50
            for i in range(0, len(pmids), batch_size):
                batch = pmids[i:i+batch_size]
                url = f"{self.PUBMED_API}/efetch.fcgi"
                params = {
                    "db": "pubmed",
                    "id": ",".join(batch),
                    "retmode": "xml"
                }
                response = self.session.get(url, params=params, timeout=60)

                # Extract NCT IDs
                found = set(re.findall(r'NCT\d{8}', response.text))
                nct_ids.update(found)
                time.sleep(0.35)

        except Exception as e:
            pass

        return nct_ids

    def validate_nct_exists(self, nct_id: str) -> bool:
        """Check if NCT ID exists in CT.gov"""
        try:
            url = f"{self.CTGOV_API}/{nct_id}"
            response = self.session.get(url, params={"fields": "NCTId"}, timeout=10)
            return response.status_code == 200
        except:
            return False

    def search_ctgov(self, drug: str) -> Set[str]:
        """Search CT.gov by drug name"""
        nct_ids = set()
        try:
            params = {
                "query.intr": drug,
                "fields": "NCTId",
                "pageSize": 1000
            }
            response = self.session.get(self.CTGOV_API, params=params, timeout=60)
            response.raise_for_status()

            for study in response.json().get("studies", []):
                nct_id = study.get("protocolSection", {}).get(
                    "identificationModule", {}
                ).get("nctId")
                if nct_id:
                    nct_ids.add(nct_id)

            time.sleep(0.3)
        except:
            pass

        return nct_ids

    def run_large_scale_validation(self, output_dir: str, target_trials: int = 10000):
        """Run large-scale validation"""

        print("=" * 70)
        print(f"LARGE-SCALE VALIDATION - Target: {target_trials} trials")
        print("=" * 70)

        all_results = []
        total_gold = 0
        total_found = 0
        total_tp = 0
        total_fn = 0

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for i, (drug, condition) in enumerate(self.DRUGS_TO_TEST):
            if total_gold >= target_trials:
                break

            print(f"\n[{i+1}/{len(self.DRUGS_TO_TEST)}] {drug} ({condition[:30]})")

            # Get gold standard from PubMed
            print("  Fetching from PubMed...", end=" ", flush=True)
            gold_ncts = self.get_nct_ids_from_pubmed(drug, condition, max_results=300)

            # Validate NCT IDs exist
            valid_ncts = set()
            for nct in list(gold_ncts)[:200]:  # Limit validation
                if self.validate_nct_exists(nct):
                    valid_ncts.add(nct)
                time.sleep(0.1)

            if len(valid_ncts) < 5:
                print(f"skipped (only {len(valid_ncts)} valid trials)")
                continue

            print(f"{len(valid_ncts)} trials")

            # Search CT.gov
            print("  Searching CT.gov...", end=" ", flush=True)
            found = self.search_ctgov(drug)
            print(f"{len(found)} results")

            # Calculate metrics
            tp = len(found & valid_ncts)
            fn = len(valid_ncts - found)
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0

            total_gold += len(valid_ncts)
            total_tp += tp
            total_fn += fn

            print(f"  Recall: {recall:.1%} ({tp}/{tp+fn})")

            all_results.append({
                "drug": drug,
                "condition": condition,
                "gold_standard": len(valid_ncts),
                "found": len(found),
                "tp": tp,
                "fn": fn,
                "recall": recall
            })

            # Save progress
            if i % 10 == 0:
                self._save_progress(all_results, total_tp, total_fn, output_path)

        # Final results
        final_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
        ci_low, ci_high = wilson_ci(total_tp, total_tp + total_fn)

        print(f"\n{'='*70}")
        print("LARGE-SCALE VALIDATION RESULTS")
        print('='*70)
        print(f"\n  Total trials tested: {total_tp + total_fn}")
        print(f"  True positives: {total_tp}")
        print(f"  False negatives: {total_fn}")
        print(f"\n  RECALL: {final_recall:.2%}")
        print(f"  95% CI: {ci_low:.2%} - {ci_high:.2%}")
        print(f"\n  TARGET (95%): {'ACHIEVED' if final_recall >= 0.95 else 'NOT ACHIEVED'}")

        # Save final results
        self._save_final_results(all_results, total_tp, total_fn, final_recall, ci_low, ci_high, output_path)

        return final_recall, ci_low, ci_high

    def _save_progress(self, results, tp, fn, output_path):
        """Save progress to file"""
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        with open(output_path / "validation_progress.json", 'w') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_trials": tp + fn,
                "recall": recall,
                "results": results
            }, f, indent=2)

    def _save_final_results(self, results, tp, fn, recall, ci_low, ci_high, output_path):
        """Save final results"""
        with open(output_path / "large_scale_validation_results.json", 'w') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "3.0",
                "total_trials": tp + fn,
                "true_positives": tp,
                "false_negatives": fn,
                "recall": recall,
                "ci_95_lower": ci_low,
                "ci_95_upper": ci_high,
                "target_met": recall >= 0.95,
                "drugs_tested": len(results),
                "results_by_drug": results
            }, f, indent=2)

        # Also save markdown report
        with open(output_path / "large_scale_validation_report.md", 'w') as f:
            f.write("# Large-Scale Validation Results\n\n")
            f.write(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n")
            f.write(f"**Total Trials:** {tp + fn}\n")
            f.write(f"**Recall:** {recall:.2%} (95% CI: {ci_low:.2%} - {ci_high:.2%})\n")
            f.write(f"**Target (95%):** {'ACHIEVED' if recall >= 0.95 else 'NOT ACHIEVED'}\n\n")
            f.write("## Results by Drug\n\n")
            f.write("| Drug | Condition | Gold | TP | FN | Recall |\n")
            f.write("|------|-----------|------|----|----|--------|\n")
            for r in sorted(results, key=lambda x: x['recall'], reverse=True):
                f.write(f"| {r['drug']} | {r['condition'][:20]} | {r['gold_standard']} | {r['tp']} | {r['fn']} | {r['recall']:.1%} |\n")

        print(f"\nResults saved to {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Large-Scale Validation")
    parser.add_argument("-o", "--output", default="output")
    parser.add_argument("-n", "--target", type=int, default=10000,
                       help="Target number of trials")

    args = parser.parse_args()

    validator = LargeScaleValidator()
    validator.run_large_scale_validation(args.output, args.target)


if __name__ == "__main__":
    main()
