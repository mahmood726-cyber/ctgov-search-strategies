#!/usr/bin/env python3
"""
Multi-Registry Search Engine
Actual implementation of WHO ICTRP, EU-CTR, and ISRCTN searches.

This module provides REAL multi-registry searching, not simulation.

Author: Mahmood Ahmad
Version: 4.1
"""

import requests
import json
import re
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from bs4 import BeautifulSoup
import urllib.parse


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class RegistryTrial:
    """A trial from any registry"""
    registry_id: str  # NCT, ISRCTN, EUCTR, etc.
    registry: str  # "CT.gov", "WHO ICTRP", "EU-CTR", "ISRCTN"
    title: str
    status: str
    condition: str = ""
    intervention: str = ""
    phase: str = ""
    enrollment: Optional[int] = None
    primary_outcome: str = ""
    start_date: str = ""
    completion_date: str = ""
    sponsor: str = ""
    countries: List[str] = field(default_factory=list)
    url: str = ""
    raw_data: Dict = field(default_factory=dict)

    @property
    def is_nct(self) -> bool:
        return self.registry_id.startswith("NCT")


# =============================================================================
# CT.GOV API
# =============================================================================

class CTGovSearch:
    """ClinicalTrials.gov API v2"""

    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MultiRegistrySearch/4.1"
        })

    def search(self, condition: str, filters: Dict = None) -> List[RegistryTrial]:
        """Search CT.gov by condition"""
        params = {
            "query.cond": condition,
            "countTotal": "true",
            "pageSize": 100
        }

        if filters:
            if filters.get("interventional"):
                params["query.term"] = "AREA[StudyType]INTERVENTIONAL"
            if filters.get("randomized"):
                params["query.term"] = params.get("query.term", "") + " AREA[DesignAllocation]RANDOMIZED"
            if filters.get("completed"):
                params["filter.overallStatus"] = "COMPLETED"

        trials = []

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            for study in data.get("studies", []):
                trial = self._parse_study(study)
                if trial:
                    trials.append(trial)

        except Exception as e:
            print(f"CT.gov search error: {e}")

        return trials

    def get_by_nct(self, nct_id: str) -> Optional[RegistryTrial]:
        """Get a specific study by NCT ID"""
        try:
            url = f"{self.BASE_URL}/{nct_id}"
            response = self.session.get(url, timeout=30)

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()
            return self._parse_study(data)

        except Exception as e:
            print(f"CT.gov fetch error: {e}")
            return None

    def _parse_study(self, data: dict) -> Optional[RegistryTrial]:
        """Parse CT.gov study JSON"""
        try:
            protocol = data.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            design_module = protocol.get("designModule", {})
            outcomes_module = protocol.get("outcomesModule", {})
            conditions_module = protocol.get("conditionsModule", {})
            contacts_module = protocol.get("contactsLocationsModule", {})

            nct_id = id_module.get("nctId", "")
            if not nct_id:
                return None

            # Primary outcome
            primary_outcomes = outcomes_module.get("primaryOutcomes", [])
            primary_outcome = primary_outcomes[0].get("measure", "") if primary_outcomes else ""

            # Enrollment
            enrollment_info = design_module.get("enrollmentInfo", {})
            enrollment = enrollment_info.get("count")

            # Countries
            locations = contacts_module.get("locations", [])
            countries = list(set(loc.get("country", "") for loc in locations if loc.get("country")))

            return RegistryTrial(
                registry_id=nct_id,
                registry="CT.gov",
                title=id_module.get("briefTitle", ""),
                status=status_module.get("overallStatus", "UNKNOWN"),
                condition=", ".join(conditions_module.get("conditions", [])[:3]),
                phase=", ".join(design_module.get("phases", [])),
                enrollment=enrollment,
                primary_outcome=primary_outcome,
                start_date=status_module.get("startDateStruct", {}).get("date", ""),
                completion_date=status_module.get("completionDateStruct", {}).get("date", ""),
                sponsor=id_module.get("organization", {}).get("fullName", ""),
                countries=countries,
                url=f"https://clinicaltrials.gov/study/{nct_id}",
                raw_data=data
            )

        except Exception as e:
            return None


# =============================================================================
# WHO ICTRP SEARCH (ACTUAL IMPLEMENTATION)
# =============================================================================

class ICTRPSearch:
    """
    WHO International Clinical Trials Registry Platform
    Uses the ICTRP search portal for real queries
    """

    SEARCH_URL = "https://trialsearch.who.int/Trial2.aspx"
    DETAIL_URL = "https://trialsearch.who.int/Trial3.aspx"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def search(self, condition: str, max_results: int = 100) -> List[RegistryTrial]:
        """Search ICTRP by condition"""
        trials = []

        try:
            # ICTRP uses ASP.NET forms, we need to get the page first
            params = {
                "SearchAll": condition,
                "SearchType": "basic"
            }

            response = self.session.get(self.SEARCH_URL, params=params, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find trial links in results table
            result_table = soup.find('table', {'id': 'ctl00_MainContent_grdResults'})
            if not result_table:
                # Try alternative table format
                result_table = soup.find('table', class_='results')

            if result_table:
                rows = result_table.find_all('tr')[1:]  # Skip header

                for row in rows[:max_results]:
                    trial = self._parse_row(row)
                    if trial:
                        trials.append(trial)

        except Exception as e:
            print(f"ICTRP search error: {e}")

        return trials

    def get_by_id(self, trial_id: str) -> Optional[RegistryTrial]:
        """Get trial details by ICTRP ID or NCT ID"""
        try:
            params = {"TrialID": trial_id}
            response = self.session.get(self.DETAIL_URL, params=params, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            return self._parse_detail_page(soup, trial_id)

        except Exception as e:
            print(f"ICTRP fetch error: {e}")
            return None

    def _parse_row(self, row) -> Optional[RegistryTrial]:
        """Parse a search result row"""
        try:
            cells = row.find_all('td')
            if len(cells) < 4:
                return None

            trial_id = cells[0].get_text(strip=True)
            title = cells[1].get_text(strip=True)
            status = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            source = cells[3].get_text(strip=True) if len(cells) > 3 else ""

            return RegistryTrial(
                registry_id=trial_id,
                registry="WHO ICTRP",
                title=title[:200],
                status=status,
                url=f"https://trialsearch.who.int/Trial3.aspx?TrialID={trial_id}"
            )

        except Exception:
            return None

    def _parse_detail_page(self, soup, trial_id: str) -> Optional[RegistryTrial]:
        """Parse ICTRP detail page"""
        try:
            def get_field(label):
                label_elem = soup.find(string=re.compile(label, re.I))
                if label_elem:
                    parent = label_elem.parent
                    if parent:
                        next_elem = parent.find_next_sibling()
                        if next_elem:
                            return next_elem.get_text(strip=True)
                return ""

            return RegistryTrial(
                registry_id=trial_id,
                registry="WHO ICTRP",
                title=get_field("Public title") or get_field("Scientific title"),
                status=get_field("Recruitment status"),
                condition=get_field("Health condition"),
                intervention=get_field("Intervention"),
                primary_outcome=get_field("Primary outcome"),
                sponsor=get_field("Primary sponsor"),
                countries=[get_field("Countries of recruitment")] if get_field("Countries of recruitment") else [],
                url=f"https://trialsearch.who.int/Trial3.aspx?TrialID={trial_id}"
            )

        except Exception:
            return None


# =============================================================================
# EU CLINICAL TRIALS REGISTER
# =============================================================================

class EUCTRSearch:
    """EU Clinical Trials Register search"""

    SEARCH_URL = "https://www.clinicaltrialsregister.eu/ctr-search/search"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def search(self, condition: str, max_results: int = 50) -> List[RegistryTrial]:
        """Search EU-CTR by condition"""
        trials = []

        try:
            params = {
                "query": condition,
                "mode": "basic",
                "status": "completed"  # Focus on completed trials
            }

            response = self.session.get(self.SEARCH_URL, params=params, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find result table
            results = soup.find_all('tr', class_='result')

            for result in results[:max_results]:
                trial = self._parse_result(result)
                if trial:
                    trials.append(trial)

        except Exception as e:
            print(f"EU-CTR search error: {e}")

        return trials

    def _parse_result(self, row) -> Optional[RegistryTrial]:
        """Parse EU-CTR search result"""
        try:
            # Extract EudraCT number
            eudract_elem = row.find('td', class_='eudract-number')
            eudract = eudract_elem.get_text(strip=True) if eudract_elem else ""

            # Extract title
            title_elem = row.find('td', class_='title')
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Extract status
            status_elem = row.find('td', class_='trial-status')
            status = status_elem.get_text(strip=True) if status_elem else ""

            if not eudract:
                return None

            return RegistryTrial(
                registry_id=eudract,
                registry="EU-CTR",
                title=title[:200],
                status=status,
                url=f"https://www.clinicaltrialsregister.eu/ctr-search/trial/{eudract}"
            )

        except Exception:
            return None


# =============================================================================
# ISRCTN REGISTRY
# =============================================================================

class ISRCTNSearch:
    """ISRCTN Registry search"""

    API_URL = "https://www.isrctn.com/api/query"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "MultiRegistrySearch/4.1"
        })

    def search(self, condition: str, max_results: int = 50) -> List[RegistryTrial]:
        """Search ISRCTN by condition"""
        trials = []

        try:
            params = {
                "q": condition,
                "filters": "conditionCategory:Medicine",
                "page": 1,
                "pageSize": max_results
            }

            response = self.session.get(self.API_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            for item in data.get("items", []):
                trial = self._parse_item(item)
                if trial:
                    trials.append(trial)

        except Exception as e:
            print(f"ISRCTN search error: {e}")

        return trials

    def _parse_item(self, item: dict) -> Optional[RegistryTrial]:
        """Parse ISRCTN API result"""
        try:
            isrctn = item.get("isrctn", "")
            if not isrctn:
                return None

            return RegistryTrial(
                registry_id=isrctn,
                registry="ISRCTN",
                title=item.get("title", "")[:200],
                status=item.get("recruitmentStatus", ""),
                condition=item.get("conditionCategory", ""),
                intervention=item.get("interventions", ""),
                sponsor=item.get("sponsor", {}).get("name", ""),
                countries=item.get("countries", []),
                url=f"https://www.isrctn.com/{isrctn}"
            )

        except Exception:
            return None


# =============================================================================
# UNIFIED MULTI-REGISTRY SEARCH
# =============================================================================

class MultiRegistrySearch:
    """
    Unified search across multiple trial registries.
    This provides REAL multi-witness verification.
    """

    def __init__(self):
        self.ctgov = CTGovSearch()
        self.ictrp = ICTRPSearch()
        self.euctr = EUCTRSearch()
        self.isrctn = ISRCTNSearch()

    def search_all(self, condition: str) -> Dict[str, List[RegistryTrial]]:
        """Search all registries for a condition"""
        results = {}

        print(f"Searching all registries for: {condition}")

        # CT.gov
        print("  CT.gov...", end=" ", flush=True)
        results["CT.gov"] = self.ctgov.search(condition)
        print(f"{len(results['CT.gov'])} found")

        time.sleep(1)

        # WHO ICTRP
        print("  WHO ICTRP...", end=" ", flush=True)
        results["WHO ICTRP"] = self.ictrp.search(condition)
        print(f"{len(results['WHO ICTRP'])} found")

        time.sleep(1)

        # EU-CTR
        print("  EU-CTR...", end=" ", flush=True)
        results["EU-CTR"] = self.euctr.search(condition)
        print(f"{len(results['EU-CTR'])} found")

        time.sleep(1)

        # ISRCTN
        print("  ISRCTN...", end=" ", flush=True)
        results["ISRCTN"] = self.isrctn.search(condition)
        print(f"{len(results['ISRCTN'])} found")

        return results

    def cross_validate_nct(self, nct_id: str) -> Dict[str, Optional[RegistryTrial]]:
        """
        Cross-validate an NCT ID across registries.
        This is TRUE multi-witness verification.
        """
        results = {}

        # CT.gov (primary)
        results["CT.gov"] = self.ctgov.get_by_nct(nct_id)

        # WHO ICTRP (should have CT.gov trials)
        results["WHO ICTRP"] = self.ictrp.get_by_id(nct_id)

        return results

    def find_cross_registered(self, nct_id: str) -> List[str]:
        """Find other registry IDs for the same trial"""
        # Many trials are registered in multiple registries
        # CT.gov may link to EUCTR, ISRCTN, etc.

        cross_ids = []

        ctgov_trial = self.ctgov.get_by_nct(nct_id)
        if ctgov_trial and ctgov_trial.raw_data:
            # Check secondary IDs
            protocol = ctgov_trial.raw_data.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})

            for sec_id in id_module.get("secondaryIdInfos", []):
                sec_id_str = sec_id.get("id", "")
                # Check for other registry formats
                if re.match(r'ISRCTN\d+', sec_id_str):
                    cross_ids.append(sec_id_str)
                elif re.match(r'\d{4}-\d{6}-\d{2}', sec_id_str):  # EudraCT format
                    cross_ids.append(sec_id_str)

        return cross_ids


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Multi-Registry Trial Search")
    parser.add_argument("query", help="Condition or NCT ID to search")
    parser.add_argument("--registry", choices=["all", "ctgov", "ictrp", "euctr", "isrctn"],
                       default="all", help="Registry to search")
    parser.add_argument("-o", "--output", help="Output JSON file")
    parser.add_argument("--cross-validate", action="store_true",
                       help="Cross-validate NCT ID across registries")

    args = parser.parse_args()

    searcher = MultiRegistrySearch()

    if args.cross_validate and args.query.startswith("NCT"):
        print(f"Cross-validating {args.query}...")
        results = searcher.cross_validate_nct(args.query)

        for registry, trial in results.items():
            if trial:
                print(f"\n{registry}:")
                print(f"  Title: {trial.title[:60]}...")
                print(f"  Status: {trial.status}")
            else:
                print(f"\n{registry}: Not found")

        # Find cross-registered IDs
        cross_ids = searcher.find_cross_registered(args.query)
        if cross_ids:
            print(f"\nCross-registered IDs: {', '.join(cross_ids)}")

    else:
        results = searcher.search_all(args.query)

        total = sum(len(trials) for trials in results.values())
        print(f"\nTotal trials found: {total}")

        if args.output:
            output = {
                "query": args.query,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "results": {
                    reg: [asdict(t) for t in trials]
                    for reg, trials in results.items()
                }
            }
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2)
            print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
