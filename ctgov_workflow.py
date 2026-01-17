#!/usr/bin/env python3
"""
CT.gov Search Strategy Workflow Tool
Comprehensive automated workflow for clinical trial searching
Combines: Strategy testing, Recall validation, Multi-registry search, Synonym expansion

Author: CT.gov Search Strategy Project
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import quote
from ctgov_config import CTGOV_API, DEFAULT_RATE_LIMIT, DEFAULT_TIMEOUT, DEFAULT_USER_AGENT
from ctgov_terms import load_synonyms
from ctgov_utils import get_session

# Configuration
RATE_LIMIT = DEFAULT_RATE_LIMIT
TIMEOUT = DEFAULT_TIMEOUT

# Import local modules
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

# Search Strategies - Based on empirical validation
STRATEGIES = {
    "S1": {
        "name": "Condition Only (Maximum Recall)",
        "desc": "Cochrane recommended - no filters",
        "recall": 48.2,  # Empirical average
        "build_query": lambda c, i=None: f"query.cond={quote(c)}"
    },
    "S2": {
        "name": "Interventional Studies",
        "desc": "All interventional study types",
        "recall": 53.9,
        "build_query": lambda c, i=None: f"query.cond={quote(c)}&query.term={quote('AREA[StudyType]INTERVENTIONAL')}"
    },
    "S3": {
        "name": "Randomized Allocation Only",
        "desc": "True RCTs - excludes single-arm (BEST RECALL)",
        "recall": 63.2,
        "build_query": lambda c, i=None: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED')}"
    },
    "S4": {
        "name": "Phase 3/4 Studies",
        "desc": "Later phase trials only",
        "recall": 34.4,
        "build_query": lambda c, i=None: f"query.cond={quote(c)}&query.term={quote('AREA[Phase](PHASE3 OR PHASE4)')}"
    },
    "S5": {
        "name": "Has Posted Results",
        "desc": "Studies with results on CT.gov",
        "recall": 55.5,
        "build_query": lambda c, i=None: f"query.cond={quote(c)}&query.term={quote('AREA[ResultsFirstPostDate]RANGE[MIN,MAX]')}"
    },
    "S6": {
        "name": "Completed Status",
        "desc": "Completed trials only",
        "recall": 51.7,
        "build_query": lambda c, i=None: f"query.cond={quote(c)}&filter.overallStatus=COMPLETED"
    },
    "S7": {
        "name": "Interventional + Completed",
        "desc": "Completed interventional studies",
        "recall": 56.8,
        "build_query": lambda c, i=None: f"query.cond={quote(c)}&query.term={quote('AREA[StudyType]INTERVENTIONAL')}&filter.overallStatus=COMPLETED"
    },
    "S8": {
        "name": "RCT + Phase 3/4 + Completed",
        "desc": "Highest quality subset (Low recall)",
        "recall": 33.8,
        "build_query": lambda c, i=None: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED AND AREA[Phase](PHASE3 OR PHASE4)')}&filter.overallStatus=COMPLETED"
    },
    "S9": {
        "name": "Full-Text RCT Keywords",
        "desc": "Text: condition AND randomized AND controlled",
        "recall": 51.6,
        "build_query": lambda c, i=None: f"query.term={quote(c + ' AND randomized AND controlled')}"
    },
    "S10": {
        "name": "Treatment RCTs Only",
        "desc": "Randomized + Treatment purpose (HIGH RECALL)",
        "recall": 60.0,
        "build_query": lambda c, i=None: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT')}"
    }
}


class CTgovWorkflow:
    """Comprehensive CT.gov search workflow"""

    def __init__(
        self,
        output_dir: Optional[str] = None,
        synonyms_path: Optional[str] = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ):
        self.session = get_session(user_agent=user_agent)
        self.session.headers.update({"Accept": "application/json"})
        self.output_dir = Path(output_dir) if output_dir else Path("output")
        self.output_dir.mkdir(exist_ok=True)
        self.synonyms = load_synonyms(synonyms_path)

    def search(self, condition: str, strategy: str = "S3",
               intervention: Optional[str] = None, page_size: int = 100) -> Dict:
        """Execute a single search"""
        if strategy not in STRATEGIES:
            return {"error": f"Unknown strategy: {strategy}"}

        strat = STRATEGIES[strategy]
        query = strat["build_query"](condition, intervention)
        url = f"{CTGOV_API}?{query}&countTotal=true&pageSize={page_size}"

        try:
            start = time.time()
            response = self.session.get(url, timeout=TIMEOUT)
            elapsed = time.time() - start

            if response.status_code == 200:
                data = response.json()
                return {
                    "strategy_id": strategy,
                    "strategy_name": strat["name"],
                    "condition": condition,
                    "total_count": data.get("totalCount", 0),
                    "returned": len(data.get("studies", [])),
                    "expected_recall": strat["recall"],
                    "url": url,
                    "time_sec": round(elapsed, 2)
                }
            return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def compare_strategies(self, condition: str, intervention: Optional[str] = None) -> Dict:
        """Compare all strategies for a condition"""
        results = {}
        baseline = None

        print(f"\nComparing strategies for: {condition}")
        print("-" * 60)

        for strategy_id in STRATEGIES:
            result = self.search(condition, strategy_id, intervention)
            results[strategy_id] = result

            if strategy_id == "S1":
                baseline = result.get("total_count", 0)

            if "error" not in result:
                count = result["total_count"]
                pct = (count / baseline * 100) if baseline else 0
                print(f"  {strategy_id}: {count:>8,} ({pct:>5.1f}%) - {STRATEGIES[strategy_id]['name'][:35]}")
            else:
                print(f"  {strategy_id}: ERROR - {result['error']}")

            time.sleep(RATE_LIMIT)

        return {
            "condition": condition,
            "baseline_count": baseline,
            "strategies": results,
            "timestamp": datetime.now().isoformat()
        }

    def expand_with_synonyms(self, condition: str) -> Dict:
        """Search with synonym expansion"""
        condition_lower = condition.lower()
        synonyms = self.synonyms.get(condition_lower, [])
        all_terms = list(set([condition] + synonyms))

        if len(all_terms) == 1:
            return self.search(condition, "S3")

        # Build OR query
        or_query = " OR ".join([f'"{t}"' for t in all_terms])
        query = f"query.cond={quote(or_query)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED')}"
        url = f"{CTGOV_API}?{query}&countTotal=true&pageSize=1"

        try:
            response = self.session.get(url, timeout=TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                return {
                    "condition": condition,
                    "synonyms_used": all_terms,
                    "synonym_count": len(all_terms),
                    "total_count": data.get("totalCount", 0),
                    "strategy": "S3 with synonyms"
                }
            return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def validate_nct_id(self, nct_id: str) -> Dict:
        """Validate a single NCT ID"""
        nct_id = nct_id.strip().upper()
        url = f"{CTGOV_API}/{nct_id}"

        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                protocol = data.get("protocolSection", {})
                id_module = protocol.get("identificationModule", {})
                return {
                    "nct_id": nct_id,
                    "exists": True,
                    "title": id_module.get("briefTitle", "")
                }
            return {"nct_id": nct_id, "exists": False}
        except Exception as e:
            return {"nct_id": nct_id, "error": str(e)}

    def generate_multi_registry_urls(self, condition: str) -> Dict:
        """Generate search URLs for multiple registries"""
        encoded = quote(condition)
        return {
            "ClinicalTrials.gov": f"https://clinicaltrials.gov/search?cond={encoded}",
            "WHO ICTRP": f"https://trialsearch.who.int/Default.aspx?SearchAll={encoded}",
            "ISRCTN": f"https://www.isrctn.com/search?q={encoded}",
            "EUCTR": f"https://www.clinicaltrialsregister.eu/ctr-search/search?query={encoded}",
            "ANZCTR": f"https://www.anzctr.org.au/TrialSearch.aspx#&&searchTxt={encoded}",
            "DRKS": f"https://drks.de/search/de?query={encoded}"
        }

    def full_workflow(self, condition: str, export: bool = True) -> Dict:
        """Run complete workflow for a condition"""
        print("\n" + "=" * 70)
        print(f"CT.GOV FULL SEARCH WORKFLOW: {condition.upper()}")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        results = {
            "condition": condition,
            "timestamp": datetime.now().isoformat(),
            "workflow_version": "1.0"
        }

        # Step 1: Strategy comparison
        print("\n[1/4] COMPARING SEARCH STRATEGIES")
        comparison = self.compare_strategies(condition)
        results["strategy_comparison"] = comparison

        # Step 2: Synonym expansion
        print("\n[2/4] SYNONYM EXPANSION")
        expanded = self.expand_with_synonyms(condition)
        results["synonym_expansion"] = expanded
        if "synonyms_used" in expanded:
            print(f"  Terms used: {', '.join(expanded['synonyms_used'][:5])}")
            print(f"  Total with synonyms: {expanded.get('total_count', 'N/A'):,}")

        # Step 3: Multi-registry URLs
        print("\n[3/4] MULTI-REGISTRY SEARCH URLS")
        registry_urls = self.generate_multi_registry_urls(condition)
        results["registry_urls"] = registry_urls
        for name, url in list(registry_urls.items())[:3]:
            print(f"  {name}: {url[:60]}...")

        # Step 4: Recommendations
        print("\n[4/4] RECOMMENDATIONS")
        results["recommendations"] = self.generate_recommendations(comparison)
        for rec in results["recommendations"]:
            print(f"  - {rec}")

        # Export if requested
        if export:
            filename = f"workflow_{condition.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            output_path = self.output_dir / filename
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n  Exported: {output_path}")

        return results

    def generate_recommendations(self, comparison: Dict) -> List[str]:
        """Generate search recommendations based on results"""
        recommendations = []

        strategies = comparison.get("strategies", {})
        baseline = comparison.get("baseline_count", 0)

        if baseline > 50000:
            recommendations.append("Large result set - consider using S3 (Randomized) or S10 (Treatment RCTs) to focus")
        elif baseline < 100:
            recommendations.append("Small result set - use S1 (Condition Only) to maximize recall")
        else:
            recommendations.append("For systematic reviews: Start with S3 (highest recall at 63.2%)")

        # Check S3 vs S1
        s3_count = strategies.get("S3", {}).get("total_count", 0)
        s1_count = strategies.get("S1", {}).get("total_count", 0)
        if s3_count > 0 and s1_count > 0:
            reduction = (1 - s3_count / s1_count) * 100
            recommendations.append(f"S3 reduces results by {reduction:.0f}% while improving recall")

        # Check completed
        s6_count = strategies.get("S6", {}).get("total_count", 0)
        if s6_count > 0 and s1_count > 0:
            completed_pct = s6_count / s1_count * 100
            recommendations.append(f"{completed_pct:.0f}% of studies are completed (S6)")

        recommendations.append("Always search WHO ICTRP in addition to CT.gov")
        recommendations.append("Document search strategy with date for reproducibility")

        return recommendations


def main():
    parser = argparse.ArgumentParser(
        description="CT.gov Search Strategy Workflow Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ctgov_workflow.py search diabetes
  python ctgov_workflow.py compare "breast cancer"
  python ctgov_workflow.py workflow "cystic fibrosis"
  python ctgov_workflow.py validate NCT03702452
        """
    )
    parser.add_argument("--synonyms", help="Path to JSON synonyms file")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search CT.gov")
    search_parser.add_argument("condition", help="Condition to search")
    search_parser.add_argument("-s", "--strategy", default="S3", help="Strategy (S1-S10, default: S3)")
    search_parser.add_argument("-i", "--intervention", help="Optional intervention filter")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare all strategies")
    compare_parser.add_argument("condition", help="Condition to search")

    # Workflow command
    workflow_parser = subparsers.add_parser("workflow", help="Run full workflow")
    workflow_parser.add_argument("condition", help="Condition to search")
    workflow_parser.add_argument("-o", "--output", help="Output directory")
    workflow_parser.add_argument("--no-export", action="store_true", help="Skip writing JSON output")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate NCT ID")
    validate_parser.add_argument("nct_id", help="NCT ID to validate")

    # Strategies command
    subparsers.add_parser("strategies", help="List available strategies")

    args = parser.parse_args()

    workflow = CTgovWorkflow(
        args.output if hasattr(args, "output") and args.output else "output",
        synonyms_path=args.synonyms,
    )

    if args.command == "search":
        result = workflow.search(args.condition, args.strategy, args.intervention)
        print(json.dumps(result, indent=2))

    elif args.command == "compare":
        result = workflow.compare_strategies(args.condition)
        print(f"\nBaseline (S1): {result['baseline_count']:,} studies")

    elif args.command == "workflow":
        workflow.full_workflow(args.condition, export=not args.no_export)

    elif args.command == "validate":
        result = workflow.validate_nct_id(args.nct_id)
        print(json.dumps(result, indent=2))

    elif args.command == "strategies":
        print("\nAvailable Search Strategies:")
        print("-" * 70)
        for sid, strat in STRATEGIES.items():
            print(f"  {sid}: {strat['name']}")
            print(f"      {strat['desc']}")
            print(f"      Empirical recall: {strat['recall']:.1f}%")
            print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
