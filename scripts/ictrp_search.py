#!/usr/bin/env python3
"""
WHO ICTRP Search Integration
Searches the WHO International Clinical Trials Registry Platform
Combines with CT.gov for comprehensive trial registry searching
"""

import requests
import time
import sys
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ctgov_config import CTGOV_API
import json
from pathlib import Path

# ICTRP API Configuration
ICTRP_SEARCH_URL = "https://trialsearch.who.int/Trial2.aspx"
ICTRP_EXPORT_URL = "https://trialsearch.who.int/Default.aspx"

# Rate limiting
RATE_LIMIT = 0.5

class ICTRPSearcher:
    """WHO ICTRP trial registry searcher"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CTgov-Strategy-Tool/1.0 (Research)'
        })

    def search_ictrp_web(self, condition: str, max_results: int = 100) -> Dict:
        """
        Search ICTRP via web interface
        Note: ICTRP doesn't have a public API, so we use web scraping
        """
        try:
            # ICTRP search parameters
            params = {
                'SearchAll': condition,
                'ExportType': 'xml'
            }

            # Note: This is a simplified version - ICTRP requires session handling
            # For production, would need to handle ASP.NET ViewState/EventValidation

            return {
                "source": "ICTRP",
                "query": condition,
                "status": "limited",
                "note": "ICTRP web scraping requires session handling. Use direct registry searches.",
                "alternative_registries": self.get_registry_list()
            }
        except Exception as e:
            return {
                "source": "ICTRP",
                "query": condition,
                "error": str(e)
            }

    def get_registry_list(self) -> List[Dict]:
        """List of registries indexed by ICTRP"""
        return [
            {"name": "ClinicalTrials.gov", "code": "NCT", "api": True, "url": "https://clinicaltrials.gov"},
            {"name": "EU Clinical Trials Register", "code": "EUCTR", "api": True, "url": "https://www.clinicaltrialsregister.eu"},
            {"name": "ISRCTN", "code": "ISRCTN", "api": True, "url": "https://www.isrctn.com"},
            {"name": "Australian New Zealand CTR", "code": "ACTRN", "api": False, "url": "https://www.anzctr.org.au"},
            {"name": "Chinese CTR", "code": "ChiCTR", "api": False, "url": "https://www.chictr.org.cn"},
            {"name": "German Clinical Trials Register", "code": "DRKS", "api": False, "url": "https://www.drks.de"},
            {"name": "Iranian Registry of Clinical Trials", "code": "IRCT", "api": False, "url": "https://en.irct.ir"},
            {"name": "Japan Primary Registries Network", "code": "JPRN", "api": False, "url": "https://rctportal.niph.go.jp"},
            {"name": "Pan African Clinical Trials", "code": "PACTR", "api": False, "url": "https://pactr.samrc.ac.za"},
            {"name": "Sri Lanka Clinical Trials", "code": "SLCTR", "api": False, "url": "https://slctr.lk"},
            {"name": "Thai Clinical Trials", "code": "TCTR", "api": False, "url": "https://www.thaiclinicaltrials.org"},
            {"name": "Netherlands Trial Register", "code": "NTR", "api": False, "url": "https://trialsearch.who.int"},
            {"name": "Brazilian Clinical Trials", "code": "ReBec", "api": False, "url": "https://ensaiosclinicos.gov.br"},
            {"name": "Cuban Public Registry", "code": "RPCEC", "api": False, "url": "https://registroclinico.sld.cu"},
            {"name": "Peruvian Clinical Trials", "code": "REPEC", "api": False, "url": "https://ensayosclinicos-repec.ins.gob.pe"},
            {"name": "Clinical Trials Registry - India", "code": "CTRI", "api": False, "url": "https://ctri.nic.in"},
        ]

    def search_isrctn(self, condition: str) -> Dict:
        """Search ISRCTN registry (has API)"""
        try:
            url = f"https://www.isrctn.com/api/query/format/json?q={quote(condition)}&pageSize=100"
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                data = response.json()
                total = data.get('totalCount', 0)
                trials = data.get('results', [])

                return {
                    "source": "ISRCTN",
                    "query": condition,
                    "total_count": total,
                    "returned": len(trials),
                    "trials": [
                        {
                            "id": t.get('isrctn'),
                            "title": t.get('title'),
                            "status": t.get('recruitmentStatus'),
                            "condition": t.get('condition')
                        }
                        for t in trials[:50]  # Limit for memory
                    ]
                }
            else:
                return {
                    "source": "ISRCTN",
                    "query": condition,
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "source": "ISRCTN",
                "query": condition,
                "error": str(e)
            }

    def search_euctr(self, condition: str) -> Dict:
        """Search EU Clinical Trials Register"""
        try:
            # EUCTR uses a different search interface
            url = f"https://www.clinicaltrialsregister.eu/ctr-search/search?query={quote(condition)}"

            return {
                "source": "EUCTR",
                "query": condition,
                "search_url": url,
                "note": "EUCTR requires manual search or specialized scraping"
            }
        except Exception as e:
            return {
                "source": "EUCTR",
                "query": condition,
                "error": str(e)
            }


class MultiRegistrySearcher:
    """Search across multiple trial registries"""

    def __init__(self):
        self.ctgov_api = CTGOV_API
        self.ictrp = ICTRPSearcher()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CTgov-Strategy-Tool/1.0 (Research)'
        })

    def search_ctgov(self, condition: str, strategy: str = "S3") -> Dict:
        """Search CT.gov with specified strategy"""
        strategies = {
            "S1": lambda c: f"query.cond={quote(c)}",
            "S3": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED')}",
            "S10": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT')}"
        }

        query_builder = strategies.get(strategy, strategies["S3"])
        query = query_builder(condition)

        url = f"{self.ctgov_api}?{query}&countTotal=true&pageSize=100"

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return {
                    "source": "ClinicalTrials.gov",
                    "strategy": strategy,
                    "query": condition,
                    "total_count": data.get("totalCount", 0),
                    "studies": len(data.get("studies", []))
                }
            return {"source": "ClinicalTrials.gov", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"source": "ClinicalTrials.gov", "error": str(e)}

    def search_all_registries(self, condition: str) -> Dict:
        """Search across all available registries"""
        results = {
            "condition": condition,
            "timestamp": datetime.now().isoformat(),
            "registries": {}
        }

        # CT.gov (primary)
        print(f"  Searching ClinicalTrials.gov...")
        results["registries"]["ctgov"] = self.search_ctgov(condition, "S3")
        time.sleep(RATE_LIMIT)

        # ISRCTN
        print(f"  Searching ISRCTN...")
        results["registries"]["isrctn"] = self.ictrp.search_isrctn(condition)
        time.sleep(RATE_LIMIT)

        # EUCTR (search URL only)
        results["registries"]["euctr"] = self.ictrp.search_euctr(condition)

        # ICTRP aggregate
        results["registries"]["ictrp"] = self.ictrp.search_ictrp_web(condition)

        # Calculate totals
        total = 0
        for reg, data in results["registries"].items():
            if "total_count" in data:
                total += data["total_count"]
        results["total_estimated"] = total

        return results

    def generate_search_urls(self, condition: str) -> Dict:
        """Generate search URLs for all registries"""
        encoded = quote(condition)
        return {
            "ClinicalTrials.gov": f"https://clinicaltrials.gov/search?cond={encoded}",
            "ISRCTN": f"https://www.isrctn.com/search?q={encoded}",
            "EUCTR": f"https://www.clinicaltrialsregister.eu/ctr-search/search?query={encoded}",
            "WHO ICTRP": f"https://trialsearch.who.int/Default.aspx?SearchAll={encoded}",
            "ANZCTR": f"https://www.anzctr.org.au/TrialSearch.aspx#&&searchTxt={encoded}",
            "ChiCTR": f"https://www.chictr.org.cn/searchproj.html?title={encoded}",
            "DRKS": f"https://drks.de/search/de?query={encoded}",
            "CTRI": f"https://ctri.nic.in/Clinicaltrials/advancesearchmain.php?search_form=1&freetxt={encoded}"
        }


def create_comprehensive_search_report(condition: str, output_dir: Path) -> None:
    """Generate a comprehensive multi-registry search report"""
    searcher = MultiRegistrySearcher()

    print(f"\n{'='*70}")
    print(f"Comprehensive Trial Registry Search: {condition.upper()}")
    print(f"{'='*70}")

    # Search all registries
    results = searcher.search_all_registries(condition)

    # Get search URLs
    urls = searcher.generate_search_urls(condition)

    # Generate report
    report = []
    report.append("=" * 70)
    report.append(f"COMPREHENSIVE TRIAL REGISTRY SEARCH REPORT")
    report.append(f"Condition: {condition}")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 70)
    report.append("")

    report.append("SEARCH RESULTS BY REGISTRY")
    report.append("-" * 50)

    for reg_id, data in results["registries"].items():
        source = data.get("source", reg_id)
        count = data.get("total_count", "N/A")
        error = data.get("error", None)

        if error:
            report.append(f"  {source}: ERROR - {error}")
        elif count != "N/A":
            report.append(f"  {source}: {count:,} trials found")
        else:
            report.append(f"  {source}: Search URL available")

    report.append("")
    report.append(f"ESTIMATED TOTAL: {results.get('total_estimated', 'N/A'):,} trials")
    report.append("")

    report.append("DIRECT SEARCH URLS")
    report.append("-" * 50)
    for name, url in urls.items():
        report.append(f"  {name}:")
        report.append(f"    {url}")
        report.append("")

    report.append("REGISTRY COVERAGE NOTES")
    report.append("-" * 50)
    report.append("  - ClinicalTrials.gov: US and international trials")
    report.append("  - ISRCTN: International Standard Randomised Controlled Trial Number")
    report.append("  - EUCTR: European Union trials (required for EU authorization)")
    report.append("  - WHO ICTRP: Aggregates 17 primary registries")
    report.append("  - ANZCTR: Australia/New Zealand trials")
    report.append("  - ChiCTR: Chinese clinical trials")
    report.append("  - CTRI: Clinical Trials Registry - India")
    report.append("")

    report.append("RECOMMENDATIONS FOR SYSTEMATIC REVIEWS")
    report.append("-" * 50)
    report.append("  1. Search ClinicalTrials.gov (mandatory)")
    report.append("  2. Search WHO ICTRP (covers multiple registries)")
    report.append("  3. Search ISRCTN (additional European trials)")
    report.append("  4. Search region-specific registries for targeted reviews")
    report.append("  5. Consider searching EUCTR for European drug trials")
    report.append("")

    # Save results
    report_text = "\n".join(report)
    print(report_text)

    # Save JSON results
    json_file = output_dir / f"multi_registry_{condition.replace(' ', '_')}.json"
    with open(json_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved JSON: {json_file}")

    # Save report
    report_file = output_dir / f"multi_registry_{condition.replace(' ', '_')}_report.txt"
    with open(report_file, 'w') as f:
        f.write(report_text)
    print(f"Saved report: {report_file}")


def main():
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")
    output_dir.mkdir(exist_ok=True)

    # Test conditions
    conditions = ["diabetes", "breast cancer", "cystic fibrosis"]

    for condition in conditions:
        create_comprehensive_search_report(condition, output_dir)
        time.sleep(1)

    print("\n" + "=" * 70)
    print("Multi-registry search complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
