#!/usr/bin/env python3
"""
Missed Trial Analyzer
Diagnoses WHY trials are missed by CT.gov search strategies.
This is critical for understanding the 25% gap.

Author: Mahmood Ahmad
Version: 1.0
"""

import json
import time
import re
from typing import Set, Dict, List, Tuple
from pathlib import Path
from collections import defaultdict
import requests


class MissedTrialAnalyzer:
    """Analyzes why trials are missed by search strategies"""

    CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"

    # Fields to check for drug mentions
    FIELDS_TO_CHECK = [
        "BriefTitle",
        "OfficialTitle",
        "BriefSummary",
        "DetailedDescription",
        "Condition",
        "Keyword",
        "InterventionName",
        "InterventionDescription",
        "InterventionOtherName",
        "ArmGroupLabel",
        "ArmGroupDescription",
        "ArmGroupInterventionName",
        "PrimaryOutcomeMeasure",
        "SecondaryOutcomeMeasure",
        "EligibilityCriteria",
        "LeadSponsorName",
        "CollaboratorName",
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "MissedTrialAnalyzer/1.0"})

    def load_results(self, results_file: str) -> List[Dict]:
        """Load previous validation results"""
        with open(results_file) as f:
            data = json.load(f)
        return data.get("results_by_drug", [])

    def get_full_trial_record(self, nct_id: str) -> Dict:
        """Fetch complete trial record from CT.gov API"""
        try:
            url = f"{self.CTGOV_API}/{nct_id}"
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"    Error fetching {nct_id}: {e}")
        return {}

    def extract_all_text(self, trial: Dict) -> Dict[str, str]:
        """Extract all text fields from trial record"""
        text_fields = {}

        protocol = trial.get("protocolSection", {})

        # Identification
        id_module = protocol.get("identificationModule", {})
        text_fields["BriefTitle"] = id_module.get("briefTitle", "")
        text_fields["OfficialTitle"] = id_module.get("officialTitle", "")
        text_fields["Acronym"] = id_module.get("acronym", "")

        # Description
        desc_module = protocol.get("descriptionModule", {})
        text_fields["BriefSummary"] = desc_module.get("briefSummary", "")
        text_fields["DetailedDescription"] = desc_module.get("detailedDescription", "")

        # Conditions
        cond_module = protocol.get("conditionsModule", {})
        text_fields["Condition"] = " ".join(cond_module.get("conditions", []))
        text_fields["Keyword"] = " ".join(cond_module.get("keywords", []))

        # Interventions
        arms_module = protocol.get("armsInterventionsModule", {})
        interventions = arms_module.get("interventions", [])

        intervention_names = []
        intervention_descs = []
        other_names = []

        for intv in interventions:
            intervention_names.append(intv.get("name", ""))
            intervention_descs.append(intv.get("description", ""))
            other_names.extend(intv.get("otherNames", []))

        text_fields["InterventionName"] = " ".join(intervention_names)
        text_fields["InterventionDescription"] = " ".join(intervention_descs)
        text_fields["InterventionOtherName"] = " ".join(other_names)

        # Arms
        arms = arms_module.get("armGroups", [])
        arm_labels = []
        arm_descs = []
        arm_interventions = []

        for arm in arms:
            arm_labels.append(arm.get("label", ""))
            arm_descs.append(arm.get("description", ""))
            arm_interventions.extend(arm.get("interventionNames", []))

        text_fields["ArmGroupLabel"] = " ".join(arm_labels)
        text_fields["ArmGroupDescription"] = " ".join(arm_descs)
        text_fields["ArmGroupInterventionName"] = " ".join(arm_interventions)

        # Outcomes
        outcomes_module = protocol.get("outcomesModule", {})
        primary = outcomes_module.get("primaryOutcomes", [])
        secondary = outcomes_module.get("secondaryOutcomes", [])

        text_fields["PrimaryOutcomeMeasure"] = " ".join(
            [o.get("measure", "") + " " + o.get("description", "") for o in primary]
        )
        text_fields["SecondaryOutcomeMeasure"] = " ".join(
            [o.get("measure", "") + " " + o.get("description", "") for o in secondary]
        )

        # Eligibility
        elig_module = protocol.get("eligibilityModule", {})
        text_fields["EligibilityCriteria"] = elig_module.get("eligibilityCriteria", "")

        # Sponsors
        sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
        lead_sponsor = sponsor_module.get("leadSponsor", {})
        text_fields["LeadSponsorName"] = lead_sponsor.get("name", "")

        collaborators = sponsor_module.get("collaborators", [])
        text_fields["CollaboratorName"] = " ".join([c.get("name", "") for c in collaborators])

        return text_fields

    def find_drug_mentions(self, text_fields: Dict[str, str], drug: str) -> List[str]:
        """Find which fields contain the drug name"""
        drug_lower = drug.lower()
        found_in = []

        for field_name, text in text_fields.items():
            if text and drug_lower in text.lower():
                found_in.append(field_name)

        return found_in

    def determine_drug_role(self, text_fields: Dict[str, str], drug: str) -> str:
        """Determine if drug is primary intervention, comparator, or other"""
        drug_lower = drug.lower()

        # Check intervention name (primary role indicator)
        if drug_lower in text_fields.get("InterventionName", "").lower():
            return "PRIMARY_INTERVENTION"

        # Check arm descriptions for comparator indicators
        arm_desc = text_fields.get("ArmGroupDescription", "").lower()
        if drug_lower in arm_desc:
            if any(word in arm_desc for word in ["comparator", "control", "standard", "versus", "vs"]):
                return "COMPARATOR"
            return "ARM_INTERVENTION"

        # Check title only
        if drug_lower in text_fields.get("BriefTitle", "").lower():
            return "TITLE_ONLY"
        if drug_lower in text_fields.get("OfficialTitle", "").lower():
            return "OFFICIAL_TITLE_ONLY"

        # Check description only
        if drug_lower in text_fields.get("BriefSummary", "").lower():
            return "SUMMARY_ONLY"
        if drug_lower in text_fields.get("DetailedDescription", "").lower():
            return "DESCRIPTION_ONLY"

        # Check eligibility
        if drug_lower in text_fields.get("EligibilityCriteria", "").lower():
            return "ELIGIBILITY_CRITERIA"

        # Check outcomes
        if drug_lower in text_fields.get("PrimaryOutcomeMeasure", "").lower():
            return "OUTCOME_MEASURE"

        return "NOT_FOUND"

    def check_alternative_names(self, text_fields: Dict[str, str], drug: str) -> List[str]:
        """Check if alternative drug names are present"""

        # Common alternative name patterns
        DRUG_VARIANTS = {
            "semaglutide": ["ozempic", "wegovy", "rybelsus", "nn9535"],
            "pembrolizumab": ["keytruda", "mk-3475", "mk3475", "lambrolizumab", "anti-pd-1", "anti-pd1"],
            "nivolumab": ["opdivo", "bms-936558", "mdx1106", "anti-pd-1"],
            "trastuzumab": ["herceptin", "anti-her2", "anti-her-2"],
            "adalimumab": ["humira", "anti-tnf", "d2e7"],
            "rituximab": ["rituxan", "mabthera", "anti-cd20"],
            "bevacizumab": ["avastin", "anti-vegf"],
            "infliximab": ["remicade", "anti-tnf"],
            "etanercept": ["enbrel", "tnf receptor"],
            "metformin": ["glucophage", "fortamet", "glumetza"],
            "insulin": ["insulin glargine", "lantus", "insulin lispro", "humalog", "insulin aspart", "novolog"],
        }

        all_text = " ".join(text_fields.values()).lower()
        found_variants = []

        variants = DRUG_VARIANTS.get(drug.lower(), [])
        for variant in variants:
            if variant in all_text:
                found_variants.append(variant)

        return found_variants

    def analyze_drug(self, drug: str, gold_ncts: Set[str], found_ncts: Set[str],
                     sample_size: int = 50) -> Dict:
        """Analyze missed trials for a specific drug"""

        missed = gold_ncts - found_ncts
        found = gold_ncts & found_ncts

        if not missed:
            return {"drug": drug, "missed_count": 0, "analysis": "All trials found"}

        print(f"\n  Analyzing {len(missed)} missed trials for {drug}...")

        # Sample missed trials
        sample = list(missed)[:sample_size]

        # Analysis accumulators
        field_locations = defaultdict(int)
        drug_roles = defaultdict(int)
        alternative_names_found = defaultdict(int)
        not_found_in_record = 0

        for i, nct_id in enumerate(sample):
            if i % 10 == 0:
                print(f"    Processing {i+1}/{len(sample)}...")

            trial = self.get_full_trial_record(nct_id)
            if not trial:
                continue

            text_fields = self.extract_all_text(trial)

            # Find where drug appears
            locations = self.find_drug_mentions(text_fields, drug)
            for loc in locations:
                field_locations[loc] += 1

            if not locations:
                not_found_in_record += 1

                # Check for alternative names
                variants = self.check_alternative_names(text_fields, drug)
                for v in variants:
                    alternative_names_found[v] += 1

            # Determine drug role
            role = self.determine_drug_role(text_fields, drug)
            drug_roles[role] += 1

            time.sleep(0.1)

        return {
            "drug": drug,
            "missed_count": len(missed),
            "sample_size": len(sample),
            "field_locations": dict(field_locations),
            "drug_roles": dict(drug_roles),
            "alternative_names_found": dict(alternative_names_found),
            "not_found_in_record": not_found_in_record,
            "found_count": len(found),
            "gold_count": len(gold_ncts),
        }

    def run_full_analysis(self, results_file: str, output_dir: str):
        """Run analysis on all drugs from previous validation"""

        print("=" * 80)
        print("MISSED TRIAL ANALYSIS")
        print("Diagnosing WHY trials are missed by CT.gov search strategies")
        print("=" * 80)

        results = self.load_results(results_file)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        analyses = []

        # Aggregate statistics
        total_field_locations = defaultdict(int)
        total_drug_roles = defaultdict(int)
        total_alternative_names = defaultdict(int)
        total_not_found = 0
        total_missed = 0

        for r in results:
            drug = r.get("drug")
            gold = r.get("gold", 0)

            # Get found count from S4_Combined
            s4 = r.get("S4_Combined", {})
            found_count = s4.get("tp", 0)

            missed_count = gold - found_count

            if missed_count < 5:
                print(f"\n{drug}: Only {missed_count} missed, skipping detailed analysis")
                continue

            # We need to reconstruct the NCT ID sets
            # For this analysis, we'll sample from API
            print(f"\n{'='*60}")
            print(f"DRUG: {drug}")
            print(f"Gold: {gold}, Found: {found_count}, Missed: {missed_count}")

            # Get gold standard NCTs from PubMed
            from test_new_strategies import StrategyTester
            tester = StrategyTester()
            condition = r.get("condition", "")

            gold_ncts = tester.strategy_pubmed_si_extraction(drug, condition, max_results=200)

            # Get found NCTs
            found_ncts, _ = set(), {}
            try:
                params = {"query.intr": drug, "fields": "NCTId", "pageSize": 1000}
                response = self.session.get(self.CTGOV_API, params=params, timeout=60)
                for study in response.json().get("studies", []):
                    nct_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
                    if nct_id:
                        found_ncts.add(nct_id)
            except:
                pass

            # AREA search
            for query in [f'AREA[BriefTitle]{drug}', f'AREA[OfficialTitle]{drug}']:
                try:
                    params = {"query.term": query, "fields": "NCTId", "pageSize": 1000}
                    response = self.session.get(self.CTGOV_API, params=params, timeout=60)
                    for study in response.json().get("studies", []):
                        nct_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
                        if nct_id:
                            found_ncts.add(nct_id)
                except:
                    pass

            # Analyze
            analysis = self.analyze_drug(drug, gold_ncts, found_ncts, sample_size=30)
            analyses.append(analysis)

            # Accumulate totals
            for field, count in analysis.get("field_locations", {}).items():
                total_field_locations[field] += count
            for role, count in analysis.get("drug_roles", {}).items():
                total_drug_roles[role] += count
            for name, count in analysis.get("alternative_names_found", {}).items():
                total_alternative_names[name] += count
            total_not_found += analysis.get("not_found_in_record", 0)
            total_missed += analysis.get("missed_count", 0)

            # Print drug-specific findings
            print(f"\n  Field Locations (where drug found in missed trials):")
            for field, count in sorted(analysis.get("field_locations", {}).items(),
                                      key=lambda x: -x[1])[:5]:
                print(f"    {field}: {count}")

            print(f"\n  Drug Roles:")
            for role, count in sorted(analysis.get("drug_roles", {}).items(),
                                     key=lambda x: -x[1]):
                print(f"    {role}: {count}")

            if analysis.get("alternative_names_found"):
                print(f"\n  Alternative Names Found:")
                for name, count in analysis.get("alternative_names_found", {}).items():
                    print(f"    {name}: {count}")

            print(f"\n  Not found in record at all: {analysis.get('not_found_in_record', 0)}")

        # Summary
        print("\n" + "=" * 80)
        print("OVERALL ANALYSIS SUMMARY")
        print("=" * 80)

        print("\n1. WHERE ARE DRUGS MENTIONED IN MISSED TRIALS?")
        print("-" * 40)
        for field, count in sorted(total_field_locations.items(), key=lambda x: -x[1]):
            pct = count / sum(total_field_locations.values()) * 100 if total_field_locations else 0
            print(f"  {field:30} {count:5} ({pct:5.1f}%)")

        print("\n2. WHAT ROLE DOES THE DRUG PLAY?")
        print("-" * 40)
        for role, count in sorted(total_drug_roles.items(), key=lambda x: -x[1]):
            pct = count / sum(total_drug_roles.values()) * 100 if total_drug_roles else 0
            print(f"  {role:30} {count:5} ({pct:5.1f}%)")

        print("\n3. ALTERNATIVE NAMES FOUND")
        print("-" * 40)
        for name, count in sorted(total_alternative_names.items(), key=lambda x: -x[1]):
            print(f"  {name:30} {count:5}")

        print(f"\n4. NOT FOUND IN RECORD AT ALL: {total_not_found}")

        # Save results
        with open(output_path / "missed_trial_analysis.json", 'w') as f:
            json.dump({
                "summary": {
                    "total_missed_analyzed": total_missed,
                    "field_locations": dict(total_field_locations),
                    "drug_roles": dict(total_drug_roles),
                    "alternative_names_found": dict(total_alternative_names),
                    "not_found_in_record": total_not_found,
                },
                "by_drug": analyses
            }, f, indent=2)

        # Generate recommendations
        self._generate_recommendations(total_field_locations, total_drug_roles,
                                       total_alternative_names, total_not_found, output_path)

        print(f"\nResults saved to {output_path}")

    def _generate_recommendations(self, field_locations, drug_roles, alt_names, not_found, output_path):
        """Generate actionable recommendations based on analysis"""

        with open(output_path / "RECOMMENDATIONS.md", 'w') as f:
            f.write("# Recommendations to Improve Recall\n\n")
            f.write("Based on missed trial analysis\n\n")

            f.write("## Key Findings\n\n")

            # Field location recommendations
            f.write("### 1. Fields to Add to Search\n\n")
            non_searched = ["BriefSummary", "DetailedDescription", "ArmGroupDescription",
                           "EligibilityCriteria", "PrimaryOutcomeMeasure"]
            for field in non_searched:
                if field in field_locations:
                    f.write(f"- **{field}**: {field_locations[field]} missed trials mention drug here\n")

            f.write("\n### 2. Drug Role Analysis\n\n")
            if "COMPARATOR" in drug_roles:
                f.write(f"- **Comparator arms**: {drug_roles['COMPARATOR']} trials have drug as comparator\n")
            if "ARM_INTERVENTION" in drug_roles:
                f.write(f"- **Arm-level only**: {drug_roles['ARM_INTERVENTION']} trials list drug in arms but not interventions\n")

            f.write("\n### 3. Alternative Name Expansion\n\n")
            if alt_names:
                f.write("Add these alternative names to search:\n")
                for name, count in sorted(alt_names.items(), key=lambda x: -x[1]):
                    f.write(f"- `{name}`: found in {count} missed trials\n")

            f.write("\n### 4. Recommended New Strategies\n\n")
            f.write("Based on analysis, implement:\n\n")
            f.write("1. **AACT full-text search** - Search BriefSummary, DetailedDescription\n")
            f.write("2. **Arm description search** - Search ArmGroupDescription field\n")
            f.write("3. **Research code expansion** - Add research codes to drug variants\n")
            f.write("4. **Eligibility criteria search** - Some trials mention drug in eligibility\n")


def main():
    import sys

    results_file = sys.argv[1] if len(sys.argv) > 1 else "output/strategy_comparison_final.json"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "output/missed_analysis"

    analyzer = MissedTrialAnalyzer()
    analyzer.run_full_analysis(results_file, output_dir)


if __name__ == "__main__":
    main()
