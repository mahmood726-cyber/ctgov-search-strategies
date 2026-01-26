#!/usr/bin/env python3
"""
Gap Analysis - Why Are Trials Being Missed?
Analyzes the reasons for false negatives and tests improvements.

Author: Mahmood Ahmad
Version: 1.0
"""

import json
import time
import re
from datetime import datetime, timezone
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import requests

from drug_expander import DrugNameExpander, ConditionExpander


@dataclass
class MissedTrialAnalysis:
    """Analysis of why a trial was missed"""
    nct_id: str
    review_intervention: str  # What the review searched for
    ctgov_interventions: List[str]  # What CT.gov has registered
    review_condition: str  # What the review searched for
    ctgov_conditions: List[str]  # What CT.gov has registered
    match_possible: bool  # Could we have matched with better expansion?
    reason: str  # Why it was missed


class GapAnalyzer:
    """Analyzes why trials are missed and tests improvements"""

    CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "GapAnalyzer/1.0"})
        self.drug_expander = DrugNameExpander()
        self.condition_expander = ConditionExpander()

    def get_trial_details(self, nct_id: str) -> Optional[Dict]:
        """Get full trial details from CT.gov"""
        try:
            url = f"{self.CTGOV_API}/{nct_id}"
            params = {"fields": "NCTId,Condition,Keyword,InterventionName,BriefTitle"}
            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()
            protocol = data.get("protocolSection", {})

            interventions = []
            arms = protocol.get("armsInterventionsModule", {}).get("interventions", [])
            for arm in arms:
                name = arm.get("name", "")
                if name:
                    interventions.append(name.lower())

            return {
                "nct_id": nct_id,
                "conditions": [c.lower() for c in protocol.get("conditionsModule", {}).get("conditions", [])],
                "keywords": [k.lower() for k in protocol.get("conditionsModule", {}).get("keywords", [])],
                "interventions": interventions,
                "title": protocol.get("identificationModule", {}).get("briefTitle", "").lower()
            }

        except Exception as e:
            return None

    def analyze_missed_trial(
        self,
        nct_id: str,
        review_intervention: str,
        review_condition: str
    ) -> MissedTrialAnalysis:
        """Analyze why a specific trial was missed"""

        trial = self.get_trial_details(nct_id)
        time.sleep(0.3)

        if not trial:
            return MissedTrialAnalysis(
                nct_id=nct_id,
                review_intervention=review_intervention,
                ctgov_interventions=[],
                review_condition=review_condition,
                ctgov_conditions=[],
                match_possible=False,
                reason="Trial not found in CT.gov"
            )

        # Expand what we searched for
        searched_interventions = self.drug_expander.expand(review_intervention, use_api=False)
        searched_conditions = self.condition_expander.expand(review_condition)

        # Check if any CT.gov intervention matches our search
        intervention_match = False
        for ctgov_int in trial["interventions"]:
            for searched_int in searched_interventions:
                if searched_int in ctgov_int or ctgov_int in searched_int:
                    intervention_match = True
                    break
            # Also check title
            if any(s in trial["title"] for s in searched_interventions):
                intervention_match = True

        # Check if any CT.gov condition matches our search
        condition_match = False
        for ctgov_cond in trial["conditions"]:
            for searched_cond in searched_conditions:
                if searched_cond in ctgov_cond or ctgov_cond in searched_cond:
                    condition_match = True
                    break

        # Determine reason for miss
        if intervention_match and condition_match:
            reason = "UNKNOWN - should have been found"
            match_possible = True
        elif intervention_match and not condition_match:
            reason = f"Condition mismatch: searched '{review_condition}', CT.gov has {trial['conditions']}"
            match_possible = True  # Could improve condition expansion
        elif not intervention_match and condition_match:
            reason = f"Intervention mismatch: searched '{review_intervention}', CT.gov has {trial['interventions']}"
            match_possible = True  # Could improve drug expansion
        else:
            reason = f"Both mismatch: searched '{review_intervention}'/'{review_condition}', CT.gov has {trial['interventions']}/{trial['conditions']}"
            match_possible = True  # Could improve both

        return MissedTrialAnalysis(
            nct_id=nct_id,
            review_intervention=review_intervention,
            ctgov_interventions=trial["interventions"],
            review_condition=review_condition,
            ctgov_conditions=trial["conditions"],
            match_possible=match_possible,
            reason=reason
        )

    def run_gap_analysis(
        self,
        gold_standard_path: str,
        output_dir: str,
        max_reviews: int = 20
    ):
        """Run full gap analysis on missed trials"""

        print("=" * 70)
        print("GAP ANALYSIS - Why Are Trials Being Missed?")
        print("=" * 70)

        # Load gold standard
        with open(gold_standard_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        reviews = data.get("reviews", [])[:max_reviews]
        print(f"Analyzing {len(reviews)} reviews")

        # For each review, find which trials would be missed
        all_analyses = []
        intervention_mismatches = 0
        condition_mismatches = 0
        both_mismatches = 0
        fixable = 0
        total_missed = 0

        for i, review in enumerate(reviews):
            print(f"\n[{i+1}/{len(reviews)}] {review['pico']['intervention'][:30]}...")

            intervention = review["pico"]["intervention"]
            condition = review["pico"]["population"]
            nct_ids = review["included_nct_ids"]

            # Expand search terms
            intervention_variants = self.drug_expander.expand(intervention, use_api=False)
            condition_variants = self.condition_expander.expand(condition)

            # Check each trial
            for nct_id in nct_ids[:10]:  # Limit per review
                trial = self.get_trial_details(nct_id)
                if not trial:
                    continue

                # Check if we would find it
                found_by_intervention = False
                found_by_condition = False

                for ctgov_int in trial["interventions"]:
                    for searched_int in intervention_variants:
                        if searched_int in ctgov_int or ctgov_int in searched_int:
                            found_by_intervention = True
                            break

                for ctgov_cond in trial["conditions"]:
                    for searched_cond in condition_variants:
                        if searched_cond in ctgov_cond or ctgov_cond in searched_cond:
                            found_by_condition = True
                            break

                # If missed, analyze why
                if not (found_by_intervention or found_by_condition):
                    total_missed += 1

                    analysis = self.analyze_missed_trial(nct_id, intervention, condition)
                    all_analyses.append(analysis)

                    if "Intervention mismatch" in analysis.reason:
                        intervention_mismatches += 1
                    elif "Condition mismatch" in analysis.reason:
                        condition_mismatches += 1
                    elif "Both mismatch" in analysis.reason:
                        both_mismatches += 1

                    if analysis.match_possible:
                        fixable += 1

                    print(f"    MISSED {nct_id}: {analysis.reason[:60]}...")

        # Generate report
        print(f"\n{'='*70}")
        print("GAP ANALYSIS RESULTS")
        print('='*70)
        print(f"\nTotal missed trials analyzed: {total_missed}")
        print(f"  - Intervention mismatch: {intervention_mismatches} ({100*intervention_mismatches/max(1,total_missed):.0f}%)")
        print(f"  - Condition mismatch: {condition_mismatches} ({100*condition_mismatches/max(1,total_missed):.0f}%)")
        print(f"  - Both mismatch: {both_mismatches} ({100*both_mismatches/max(1,total_missed):.0f}%)")
        print(f"  - Potentially fixable: {fixable} ({100*fixable/max(1,total_missed):.0f}%)")

        # Save detailed analysis
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        with open(output_path / "gap_analysis.json", 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_missed": total_missed,
                "intervention_mismatches": intervention_mismatches,
                "condition_mismatches": condition_mismatches,
                "both_mismatches": both_mismatches,
                "fixable": fixable,
                "analyses": [
                    {
                        "nct_id": a.nct_id,
                        "review_intervention": a.review_intervention,
                        "ctgov_interventions": a.ctgov_interventions,
                        "review_condition": a.review_condition,
                        "ctgov_conditions": a.ctgov_conditions,
                        "match_possible": a.match_possible,
                        "reason": a.reason
                    }
                    for a in all_analyses
                ]
            }, f, indent=2)

        print(f"\nDetailed analysis saved to {output_path / 'gap_analysis.json'}")

        # Print improvement recommendations
        print(f"\n{'='*70}")
        print("IMPROVEMENT RECOMMENDATIONS")
        print('='*70)

        if intervention_mismatches > condition_mismatches:
            print("\n1. PRIORITY: Improve drug name expansion")
            print("   - Add more brand name variants")
            print("   - Include drug class terms (e.g., 'DPP-4 inhibitor')")
            print("   - Use RxNorm API for comprehensive mapping")
        else:
            print("\n1. PRIORITY: Improve condition expansion")
            print("   - Add MeSH tree expansion")
            print("   - Include ICD-10 mappings")
            print("   - Add more synonyms")

        print("\n2. Additional strategies to test:")
        print("   - Search by sponsor name")
        print("   - Search by PI name")
        print("   - Search title keywords")
        print("   - Use fuzzy matching")

        return all_analyses


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Gap Analysis")
    parser.add_argument("-g", "--gold-standard",
                       default="data/cochrane_gold_standard.json",
                       help="Path to gold standard")
    parser.add_argument("-o", "--output", default="output",
                       help="Output directory")
    parser.add_argument("-n", "--max-reviews", type=int, default=20,
                       help="Max reviews to analyze")

    args = parser.parse_args()

    analyzer = GapAnalyzer()
    analyzer.run_gap_analysis(
        args.gold_standard,
        args.output,
        args.max_reviews
    )


if __name__ == "__main__":
    main()
