#!/usr/bin/env python3
"""
Strategy Optimizer for CT.gov Search
Tries many different rules-based strategies to maximize recall.

Goal: Achieve 95%+ recall through optimal search strategy combination.

Author: Mahmood Ahmad
Version: 5.0 - TruthCert Rules-Based Optimization
"""

import json
import math
import time
import re
from datetime import datetime, timezone
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
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


@dataclass
class StrategyResult:
    name: str
    description: str
    found: int
    tested: int
    recall: float
    ci_lower: float
    ci_upper: float


class CTGovOptimizer:
    """
    Optimizes CT.gov search strategies using rules-based approaches.

    TruthCert Rules-Based Strategies:
    1. Direct NCT ID lookup (baseline - should be 100%)
    2. All conditions search (not just first)
    3. Keyword extraction from title
    4. MeSH term expansion
    5. Intervention/drug name search
    6. Combined multi-field search
    7. Fuzzy condition matching
    8. Hierarchical condition search
    """

    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

    # MeSH broader terms mapping (rules-based hierarchy)
    MESH_BROADER = {
        "type 2 diabetes mellitus": ["diabetes mellitus", "diabetes", "metabolic diseases"],
        "type 1 diabetes mellitus": ["diabetes mellitus", "diabetes", "metabolic diseases"],
        "gestational diabetes": ["diabetes mellitus", "pregnancy complications"],
        "breast neoplasms": ["breast cancer", "cancer", "neoplasms"],
        "lung neoplasms": ["lung cancer", "cancer", "neoplasms"],
        "myocardial infarction": ["heart attack", "coronary disease", "heart diseases"],
        "heart failure": ["cardiac failure", "heart diseases", "cardiovascular diseases"],
        "stroke": ["cerebrovascular disorders", "brain diseases"],
        "ischemic stroke": ["stroke", "cerebrovascular disorders"],
        "hemorrhagic stroke": ["stroke", "cerebrovascular disorders"],
        "major depressive disorder": ["depression", "depressive disorder", "mood disorders"],
        "bipolar disorder": ["mood disorders", "mental disorders"],
        "asthma": ["respiratory tract diseases", "lung diseases"],
        "copd": ["chronic obstructive pulmonary disease", "lung diseases"],
        "rheumatoid arthritis": ["arthritis", "joint diseases", "autoimmune diseases"],
        "osteoarthritis": ["arthritis", "joint diseases"],
        "hiv infections": ["hiv", "aids", "virus diseases"],
        "parkinson disease": ["parkinsons", "movement disorders", "neurodegenerative diseases"],
        "alzheimer disease": ["dementia", "neurodegenerative diseases"],
        "hypertension": ["high blood pressure", "cardiovascular diseases"],
        "atrial fibrillation": ["arrhythmia", "heart diseases"],
    }

    # Common synonyms (rules-based)
    SYNONYMS = {
        "diabetes mellitus": ["diabetes", "dm", "diabetic"],
        "myocardial infarction": ["heart attack", "mi", "ami", "stemi", "nstemi"],
        "cerebrovascular accident": ["stroke", "cva", "brain attack"],
        "neoplasm": ["cancer", "tumor", "tumour", "malignancy"],
        "hypertension": ["high blood pressure", "htn", "elevated bp"],
        "copd": ["chronic obstructive pulmonary disease", "emphysema", "chronic bronchitis"],
        "hiv": ["human immunodeficiency virus", "aids", "hiv/aids"],
        "heart failure": ["cardiac failure", "chf", "congestive heart failure", "hf"],
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "StrategyOptimizer/5.0"})
        self.cache = {}

    def get_trial_details(self, nct_id: str) -> Optional[Dict]:
        """Get full trial details from CT.gov"""
        cache_key = f"details:{nct_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            url = f"{self.BASE_URL}/{nct_id}"
            params = {"fields": "NCTId,Condition,Keyword,InterventionName,BriefTitle,OfficialTitle"}
            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            protocol = data.get("protocolSection", {})

            result = {
                "nct_id": nct_id,
                "conditions": protocol.get("conditionsModule", {}).get("conditions", []),
                "keywords": protocol.get("conditionsModule", {}).get("keywords", []),
                "interventions": [],
                "brief_title": protocol.get("identificationModule", {}).get("briefTitle", ""),
                "official_title": protocol.get("identificationModule", {}).get("officialTitle", ""),
            }

            # Extract intervention names
            arms = protocol.get("armsInterventionsModule", {}).get("interventions", [])
            for arm in arms:
                name = arm.get("name", "")
                if name:
                    result["interventions"].append(name)

            self.cache[cache_key] = result
            return result

        except Exception as e:
            return None

    def search(self, params: Dict) -> Set[str]:
        """Run a CT.gov search and return NCT IDs"""
        cache_key = json.dumps(params, sort_keys=True)
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            search_params = {"fields": "NCTId", "pageSize": 1000}
            search_params.update(params)

            response = self.session.get(self.BASE_URL, params=search_params, timeout=60)
            response.raise_for_status()
            data = response.json()

            nct_ids = set()
            for study in data.get("studies", []):
                nct_id = study.get("protocolSection", {}).get(
                    "identificationModule", {}
                ).get("nctId")
                if nct_id:
                    nct_ids.add(nct_id)

            self.cache[cache_key] = nct_ids
            time.sleep(0.3)
            return nct_ids

        except Exception:
            return set()

    def extract_keywords_from_title(self, title: str) -> List[str]:
        """Extract searchable keywords from title (rules-based)"""
        # Remove common words
        stopwords = {
            "a", "an", "the", "of", "in", "for", "to", "and", "or", "with",
            "on", "at", "by", "from", "as", "is", "was", "are", "were", "be",
            "been", "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "randomized", "controlled", "trial", "study", "phase", "double",
            "blind", "placebo", "open", "label", "multicenter", "multi-center",
            "single", "center", "pilot", "feasibility", "efficacy", "safety",
            "versus", "vs", "compared", "comparing", "effect", "effects",
            "patients", "patient", "subjects", "participants", "adults", "children"
        }

        # Extract words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', title.lower())

        # Filter and return significant words
        keywords = [w for w in words if w not in stopwords]

        # Return top 3 most specific keywords (longer = more specific)
        keywords.sort(key=len, reverse=True)
        return keywords[:3]

    def get_broader_terms(self, condition: str) -> List[str]:
        """Get broader MeSH/hierarchical terms (rules-based)"""
        condition_lower = condition.lower()
        broader = []

        # Check direct mapping
        for key, terms in self.MESH_BROADER.items():
            if key in condition_lower or condition_lower in key:
                broader.extend(terms)

        # Add synonyms
        for key, syns in self.SYNONYMS.items():
            if key in condition_lower:
                broader.extend(syns)
            for syn in syns:
                if syn in condition_lower:
                    broader.append(key)
                    broader.extend([s for s in syns if s != syn])

        return list(set(broader))

    def normalize_condition(self, condition: str) -> str:
        """Normalize condition text (rules-based)"""
        # Remove special characters
        normalized = re.sub(r'[^\w\s]', ' ', condition)
        # Remove extra spaces
        normalized = ' '.join(normalized.split())
        # Truncate very long conditions (API limit)
        if len(normalized) > 100:
            normalized = normalized[:100]
        return normalized

    # =========================================================================
    # STRATEGY IMPLEMENTATIONS
    # =========================================================================

    def strategy_direct_lookup(self, nct_id: str) -> bool:
        """S0: Direct NCT ID lookup - baseline (should be 100%)"""
        try:
            url = f"{self.BASE_URL}/{nct_id}"
            response = self.session.get(url, params={"fields": "NCTId"}, timeout=30)
            return response.status_code == 200
        except:
            return False

    def strategy_first_condition(self, nct_id: str, details: Dict) -> bool:
        """S1: Search by first condition only (original approach)"""
        conditions = details.get("conditions", [])
        if not conditions:
            return False

        condition = self.normalize_condition(conditions[0])
        results = self.search({"query.cond": condition})
        return nct_id in results

    def strategy_all_conditions(self, nct_id: str, details: Dict) -> bool:
        """S2: Search by ANY condition (OR logic)"""
        conditions = details.get("conditions", [])
        if not conditions:
            return False

        for condition in conditions[:5]:  # Limit to first 5
            condition = self.normalize_condition(condition)
            results = self.search({"query.cond": condition})
            if nct_id in results:
                return True
        return False

    def strategy_condition_keywords(self, nct_id: str, details: Dict) -> bool:
        """S3: Search by condition + keywords combined"""
        conditions = details.get("conditions", [])
        keywords = details.get("keywords", [])

        if conditions:
            condition = self.normalize_condition(conditions[0])
            # Try condition alone
            if nct_id in self.search({"query.cond": condition}):
                return True

            # Try condition + keywords
            for kw in keywords[:3]:
                results = self.search({
                    "query.cond": condition,
                    "query.term": kw
                })
                if nct_id in results:
                    return True

        return False

    def strategy_intervention_search(self, nct_id: str, details: Dict) -> bool:
        """S4: Search by intervention/drug name"""
        interventions = details.get("interventions", [])
        conditions = details.get("conditions", [])

        for intervention in interventions[:3]:
            # Clean intervention name
            intervention = self.normalize_condition(intervention)
            if len(intervention) < 3:
                continue

            # Search by intervention
            results = self.search({"query.intr": intervention})
            if nct_id in results:
                return True

            # Search intervention + condition
            if conditions:
                condition = self.normalize_condition(conditions[0])
                results = self.search({
                    "query.intr": intervention,
                    "query.cond": condition
                })
                if nct_id in results:
                    return True

        return False

    def strategy_title_keywords(self, nct_id: str, details: Dict) -> bool:
        """S5: Search by keywords extracted from title"""
        title = details.get("brief_title", "") or details.get("official_title", "")
        if not title:
            return False

        keywords = self.extract_keywords_from_title(title)

        for kw in keywords:
            results = self.search({"query.term": kw})
            if nct_id in results:
                return True

        return False

    def strategy_broader_terms(self, nct_id: str, details: Dict) -> bool:
        """S6: Search using broader MeSH hierarchy terms"""
        conditions = details.get("conditions", [])
        if not conditions:
            return False

        condition = conditions[0]
        broader_terms = self.get_broader_terms(condition)

        for term in broader_terms[:5]:
            results = self.search({"query.cond": term})
            if nct_id in results:
                return True

        return False

    def strategy_general_search(self, nct_id: str, details: Dict) -> bool:
        """S7: General text search (searches all fields)"""
        conditions = details.get("conditions", [])
        if not conditions:
            return False

        # Use general query which searches all fields
        condition = self.normalize_condition(conditions[0])
        results = self.search({"query.term": condition})
        return nct_id in results

    def strategy_combined_or(self, nct_id: str, details: Dict) -> bool:
        """S8: Combined OR search across multiple fields"""
        conditions = details.get("conditions", [])
        keywords = details.get("keywords", [])
        interventions = details.get("interventions", [])

        # Build combined search terms
        search_terms = []

        if conditions:
            search_terms.append(self.normalize_condition(conditions[0]))
        if keywords:
            search_terms.extend([k for k in keywords[:2]])
        if interventions:
            search_terms.extend([self.normalize_condition(i) for i in interventions[:2]])

        # Try each term with general query
        for term in search_terms[:5]:
            if len(term) < 3:
                continue
            results = self.search({"query.term": term})
            if nct_id in results:
                return True

        return False

    def strategy_exact_condition_match(self, nct_id: str, details: Dict) -> bool:
        """S9: Exact condition match with quotes"""
        conditions = details.get("conditions", [])
        if not conditions:
            return False

        # Try exact phrase match
        condition = self.normalize_condition(conditions[0])
        # CT.gov API uses quotes for exact match
        results = self.search({"query.cond": f'"{condition}"'})
        return nct_id in results

    def strategy_condition_synonyms(self, nct_id: str, details: Dict) -> bool:
        """S10: Search using condition synonyms"""
        conditions = details.get("conditions", [])
        if not conditions:
            return False

        condition = conditions[0].lower()

        # Get synonyms
        synonyms = []
        for key, syns in self.SYNONYMS.items():
            if key in condition:
                synonyms.extend(syns)

        for syn in synonyms[:5]:
            results = self.search({"query.cond": syn})
            if nct_id in results:
                return True

        return False

    def strategy_nct_in_term(self, nct_id: str, details: Dict) -> bool:
        """S11: Direct NCT ID in term search"""
        results = self.search({"query.term": nct_id})
        return nct_id in results

    def strategy_any_match(self, nct_id: str, details: Dict) -> bool:
        """COMBINED: Returns True if ANY strategy finds the trial"""
        strategies = [
            self.strategy_first_condition,
            self.strategy_all_conditions,
            self.strategy_condition_keywords,
            self.strategy_intervention_search,
            self.strategy_title_keywords,
            self.strategy_broader_terms,
            self.strategy_general_search,
            self.strategy_combined_or,
            self.strategy_condition_synonyms,
        ]

        for strategy in strategies:
            try:
                if strategy(nct_id, details):
                    return True
            except:
                continue

        return False

    # =========================================================================
    # VALIDATION RUNNER
    # =========================================================================

    def validate_strategies(
        self,
        gold_standard_path: str,
        output_dir: str,
        max_trials: int = 100,
        min_year: int = None
    ) -> List[StrategyResult]:
        """Run all strategies and compare recall"""

        print("=" * 70)
        print("CT.gov Strategy Optimizer - TruthCert Rules-Based v5.0")
        print("=" * 70)

        # Load gold standard
        print("\nLoading gold standard...")
        trials = []

        with open(gold_standard_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for trial in data.get("trials", []):
                nct_id = trial.get("nct_id", "")
                year = trial.get("year", 0)
                if nct_id:
                    if min_year and year and year < min_year:
                        continue
                    trials.append(nct_id)

        trials = trials[:max_trials]
        print(f"Testing {len(trials)} NCT IDs" + (f" (post-{min_year})" if min_year else ""))

        # Define strategies to test
        strategies = [
            ("S0-Direct", "Direct NCT ID lookup", self.strategy_direct_lookup),
            ("S1-FirstCond", "First condition search", self.strategy_first_condition),
            ("S2-AllCond", "All conditions (OR)", self.strategy_all_conditions),
            ("S3-CondKW", "Condition + keywords", self.strategy_condition_keywords),
            ("S4-Interv", "Intervention search", self.strategy_intervention_search),
            ("S5-TitleKW", "Title keywords", self.strategy_title_keywords),
            ("S6-Broader", "Broader MeSH terms", self.strategy_broader_terms),
            ("S7-General", "General text search", self.strategy_general_search),
            ("S8-Combined", "Combined OR fields", self.strategy_combined_or),
            ("S10-Synonyms", "Condition synonyms", self.strategy_condition_synonyms),
            ("S11-NCTTerm", "NCT ID in term", self.strategy_nct_in_term),
            ("COMBINED", "ANY strategy match", self.strategy_any_match),
        ]

        results = []

        for name, description, strategy_func in strategies:
            print(f"\n{'='*60}")
            print(f"Testing: {name} - {description}")
            print('='*60)

            found = 0
            tested = 0

            for i, nct_id in enumerate(trials):
                print(f"\r  [{i+1}/{len(trials)}] {nct_id}...", end="", flush=True)

                # Get trial details (cached)
                if name == "S0-Direct":
                    # Direct lookup doesn't need details
                    details = {}
                else:
                    details = self.get_trial_details(nct_id)
                    if not details:
                        continue
                    time.sleep(0.2)

                tested += 1

                try:
                    if name == "S0-Direct":
                        is_found = strategy_func(nct_id)
                    else:
                        is_found = strategy_func(nct_id, details)

                    if is_found:
                        found += 1
                except Exception as e:
                    pass

            print()

            recall = found / tested if tested > 0 else 0
            ci_low, ci_high = wilson_ci(found, tested)

            result = StrategyResult(
                name=name,
                description=description,
                found=found,
                tested=tested,
                recall=recall,
                ci_lower=ci_low,
                ci_upper=ci_high
            )
            results.append(result)

            print(f"  Recall: {recall:.1%} (95% CI: {ci_low:.1%} - {ci_high:.1%})")
            print(f"  Found: {found}/{tested}")

        # Generate report
        self._generate_report(results, output_dir, min_year)

        return results

    def _generate_report(self, results: List[StrategyResult], output_dir: str, min_year: int):
        """Generate optimization report"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        year_info = f" (publications {min_year}+)" if min_year else ""

        lines = [
            "# CT.gov Search Strategy Optimization Report",
            "",
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            f"**Method:** TruthCert Rules-Based Optimization v5.0{year_info}",
            "",
            "## Strategy Comparison",
            "",
            "| Strategy | Description | Recall | 95% CI | Found/Tested |",
            "|----------|-------------|--------|--------|--------------|"
        ]

        for r in results:
            lines.append(
                f"| {r.name} | {r.description} | {r.recall:.1%} | "
                f"{r.ci_lower:.1%}-{r.ci_upper:.1%} | {r.found}/{r.tested} |"
            )

        # Find best strategy
        best = max(results, key=lambda x: x.recall)
        target_met = best.recall >= 0.95

        lines.extend([
            "",
            "## Key Findings",
            "",
            f"**Best Strategy:** {best.name} ({best.description})",
            f"**Best Recall:** {best.recall:.1%} (95% CI: {best.ci_lower:.1%} - {best.ci_upper:.1%})",
            "",
            f"**Target (95%) Met:** {'YES' if target_met else 'NO'}",
            "",
            "## Strategy Descriptions",
            "",
            "| Strategy | Rules-Based Approach |",
            "|----------|---------------------|",
            "| S0-Direct | Direct NCT ID API lookup |",
            "| S1-FirstCond | Search using first listed condition |",
            "| S2-AllCond | Search using ANY of the listed conditions |",
            "| S3-CondKW | Combine condition with registered keywords |",
            "| S4-Interv | Search by intervention/drug name |",
            "| S5-TitleKW | Extract and search keywords from title |",
            "| S6-Broader | Use MeSH hierarchy for broader terms |",
            "| S7-General | Full-text search across all fields |",
            "| S8-Combined | OR search across multiple field types |",
            "| S10-Synonyms | Use synonym dictionary for conditions |",
            "| S11-NCTTerm | Search NCT ID directly in term field |",
            "| COMBINED | Union of ALL strategies (theoretical max) |",
            "",
            "---",
            "*Generated by TruthCert Rules-Based Optimizer v5.0*"
        ])

        report_path = output_path / "strategy_optimization_report.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"\nReport saved to {report_path}")

        # JSON export
        json_path = output_path / "strategy_optimization_results.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "5.0",
                "min_year": min_year,
                "target_recall": 0.95,
                "target_met": target_met,
                "best_strategy": best.name,
                "best_recall": best.recall,
                "results": [
                    {
                        "strategy": r.name,
                        "description": r.description,
                        "found": r.found,
                        "tested": r.tested,
                        "recall": r.recall,
                        "ci_95_lower": r.ci_lower,
                        "ci_95_upper": r.ci_upper
                    }
                    for r in results
                ]
            }, f, indent=2)
        print(f"JSON saved to {json_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CT.gov Strategy Optimizer")
    parser.add_argument("gold_standard", help="Path to gold standard JSON")
    parser.add_argument("-o", "--output", default="output", help="Output directory")
    parser.add_argument("-n", "--max-trials", type=int, default=50, help="Max trials to test")
    parser.add_argument("-y", "--min-year", type=int, help="Minimum publication year")

    args = parser.parse_args()

    optimizer = CTGovOptimizer()
    optimizer.validate_strategies(
        args.gold_standard,
        args.output,
        args.max_trials,
        args.min_year
    )


if __name__ == "__main__":
    main()
