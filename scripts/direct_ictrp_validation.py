#!/usr/bin/env python3
"""
Direct WHO ICTRP Validation Module

Performs direct validation against WHO ICTRP portal instead of PubMed proxy.
Implements robust web scraping with rate limiting and retry logic.

Features:
- Direct ICTRP portal search
- Cross-registry trial identification
- NCT ID to ICTRP ID mapping
- Incremental yield calculation over CT.gov alone
- Comprehensive logging and error handling

Author: CT.gov Search Strategy Team
Version: 1.0
"""

import json
import time
import re
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from urllib.parse import quote, urljoin
import sys

import requests
from bs4 import BeautifulSoup

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ctgov_config import DEFAULT_TIMEOUT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ICTRP Configuration
ICTRP_BASE_URL = "https://trialsearch.who.int"
ICTRP_SEARCH_URL = f"{ICTRP_BASE_URL}/Trial2.aspx"
ICTRP_RATE_LIMIT = 2.0  # Seconds between requests (respectful to WHO servers)
ICTRP_MAX_RETRIES = 3
ICTRP_TIMEOUT = 90


@dataclass
class ICTRPTrialRecord:
    """A trial record from ICTRP."""
    trial_id: str
    registry: str
    public_title: str = ""
    scientific_title: str = ""
    recruitment_status: str = ""
    conditions: List[str] = field(default_factory=list)
    interventions: List[str] = field(default_factory=list)
    primary_sponsor: str = ""
    countries: List[str] = field(default_factory=list)
    registration_date: str = ""
    secondary_ids: List[str] = field(default_factory=list)
    url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ICTRPSearchResult:
    """Results from an ICTRP search."""
    query: str
    total_found: int
    trials: List[ICTRPTrialRecord]
    search_url: str
    timestamp: str
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "total_found": self.total_found,
            "trials": [t.to_dict() for t in self.trials],
            "search_url": self.search_url,
            "timestamp": self.timestamp,
            "error": self.error
        }


class DirectICTRPValidator:
    """
    Direct WHO ICTRP validation without PubMed proxy.

    This class performs actual searches on the WHO ICTRP portal
    and extracts trial information for validation purposes.
    """

    # Registry ID patterns
    REGISTRY_PATTERNS = {
        "ClinicalTrials.gov": r"NCT\d{8}",
        "ISRCTN": r"ISRCTN\d{8}",
        "ANZCTR": r"ACTRN\d{14}",
        "ChiCTR": r"ChiCTR[\w-]+",
        "EUCTR": r"\d{4}-\d{6}-\d{2}",
        "DRKS": r"DRKS\d{8}",
        "CTRI": r"CTRI/\d{4}/\d{2}/\d+",
        "JPRN": r"(jRCT|UMIN|JapicCTI)\d+",
        "IRCT": r"IRCT\d+N\d+",
        "PACTR": r"PACTR\d+",
        "NTR": r"NL\d+",
        "ReBec": r"RBR-\w+",
        "KCT": r"KCT\d+",
    }

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the ICTRP validator."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DirectICTRPValidator/1.0 (Systematic Review Research)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.last_request_time = 0.0
        self.cache_dir = cache_dir or Path(__file__).parent.parent / "output" / "ictrp_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info("DirectICTRPValidator initialized")

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < ICTRP_RATE_LIMIT:
            sleep_time = ICTRP_RATE_LIMIT - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _make_request(self, url: str, params: Dict = None, method: str = "GET") -> Optional[requests.Response]:
        """Make an HTTP request with retry logic."""
        self._rate_limit()

        for attempt in range(ICTRP_MAX_RETRIES):
            try:
                if method == "GET":
                    response = self.session.get(url, params=params, timeout=ICTRP_TIMEOUT)
                else:
                    response = self.session.post(url, data=params, timeout=ICTRP_TIMEOUT)

                response.raise_for_status()
                return response

            except requests.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{ICTRP_MAX_RETRIES}): {e}")
                if attempt < ICTRP_MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"All {ICTRP_MAX_RETRIES} attempts failed for {url}")
                    return None

        return None

    def _get_cache_key(self, query: str) -> str:
        """Generate cache key for a query."""
        return hashlib.md5(query.lower().encode()).hexdigest()

    def _get_cached_result(self, query: str) -> Optional[ICTRPSearchResult]:
        """Get cached search result if available and fresh."""
        cache_key = self._get_cache_key(query)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    data = json.load(f)

                # Check if cache is less than 24 hours old
                cached_time = datetime.fromisoformat(data["timestamp"])
                if (datetime.now() - cached_time).total_seconds() < 86400:
                    logger.info(f"Using cached result for '{query}'")
                    trials = [ICTRPTrialRecord(**t) for t in data["trials"]]
                    return ICTRPSearchResult(
                        query=data["query"],
                        total_found=data["total_found"],
                        trials=trials,
                        search_url=data["search_url"],
                        timestamp=data["timestamp"]
                    )
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")

        return None

    def _save_to_cache(self, result: ICTRPSearchResult) -> None:
        """Save search result to cache."""
        cache_key = self._get_cache_key(result.query)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            with open(cache_file, 'w') as f:
                json.dump(result.to_dict(), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _parse_trial_from_html(self, html: str, trial_id: str) -> Optional[ICTRPTrialRecord]:
        """Parse trial details from ICTRP HTML."""
        soup = BeautifulSoup(html, 'html.parser')

        trial = ICTRPTrialRecord(trial_id=trial_id, registry="ICTRP")

        # Try to extract common fields
        # Note: ICTRP HTML structure may vary; this is a best-effort parser

        # Find title
        title_elem = soup.find(['h1', 'h2'], class_=re.compile(r'title', re.I))
        if title_elem:
            trial.public_title = title_elem.get_text(strip=True)

        # Find registry source
        for registry, pattern in self.REGISTRY_PATTERNS.items():
            if re.search(pattern, trial_id, re.I):
                trial.registry = registry
                break

        # Extract status
        status_patterns = ['status', 'recruitment', 'recruiting']
        for pattern in status_patterns:
            status_elem = soup.find(text=re.compile(pattern, re.I))
            if status_elem:
                parent = status_elem.find_parent(['tr', 'div', 'p'])
                if parent:
                    trial.recruitment_status = parent.get_text(strip=True)[:100]
                    break

        # Build URL
        trial.url = f"{ICTRP_BASE_URL}/Trial2.aspx?TrialID={quote(trial_id)}"

        return trial

    def search_ictrp(self, query: str, max_results: int = 100) -> ICTRPSearchResult:
        """
        Search ICTRP directly by condition or intervention.

        Args:
            query: Search query (condition or intervention name)
            max_results: Maximum number of results to return

        Returns:
            ICTRPSearchResult with found trials
        """
        logger.info(f"Searching ICTRP for: {query}")

        # Check cache first
        cached = self._get_cached_result(query)
        if cached:
            return cached

        search_url = f"{ICTRP_BASE_URL}/Default.aspx"
        params = {"SearchAll": query}

        response = self._make_request(search_url, params)

        if not response:
            return ICTRPSearchResult(
                query=query,
                total_found=0,
                trials=[],
                search_url=f"{search_url}?SearchAll={quote(query)}",
                timestamp=datetime.now().isoformat(),
                error="Failed to connect to ICTRP"
            )

        # Parse results
        soup = BeautifulSoup(response.text, 'html.parser')
        trials = []

        # Extract total count
        total_found = 0
        count_patterns = [
            r'(\d+)\s*(?:record|result|trial)s?\s*found',
            r'Showing.*of\s*(\d+)',
            r'Total:\s*(\d+)',
        ]

        for pattern in count_patterns:
            match = re.search(pattern, response.text, re.I)
            if match:
                total_found = int(match.group(1).replace(',', ''))
                break

        # Extract trial IDs from results
        found_ids = set()
        for registry, pattern in self.REGISTRY_PATTERNS.items():
            matches = re.findall(pattern, response.text, re.I)
            for trial_id in matches:
                if trial_id not in found_ids and len(trials) < max_results:
                    found_ids.add(trial_id)
                    trial = ICTRPTrialRecord(
                        trial_id=trial_id,
                        registry=registry,
                        url=f"{ICTRP_BASE_URL}/Trial2.aspx?TrialID={quote(trial_id)}"
                    )
                    trials.append(trial)

        result = ICTRPSearchResult(
            query=query,
            total_found=total_found or len(trials),
            trials=trials,
            search_url=f"{search_url}?SearchAll={quote(query)}",
            timestamp=datetime.now().isoformat()
        )

        # Cache the result
        self._save_to_cache(result)

        logger.info(f"Found {len(trials)} trials for '{query}'")
        return result

    def search_by_nct_id(self, nct_id: str) -> ICTRPSearchResult:
        """
        Search ICTRP for a specific NCT ID to find cross-registrations.

        Args:
            nct_id: ClinicalTrials.gov NCT number

        Returns:
            ICTRPSearchResult with cross-registered trials
        """
        nct_id = nct_id.upper().strip()
        if not re.match(r'^NCT\d{8}$', nct_id):
            return ICTRPSearchResult(
                query=nct_id,
                total_found=0,
                trials=[],
                search_url="",
                timestamp=datetime.now().isoformat(),
                error=f"Invalid NCT ID format: {nct_id}"
            )

        return self.search_ictrp(nct_id, max_results=50)

    def validate_drug_against_ictrp(
        self,
        drug: str,
        condition: str,
        ctgov_nct_ids: Set[str]
    ) -> Dict[str, Any]:
        """
        Validate a drug's CT.gov results against ICTRP.

        Args:
            drug: Drug name
            condition: Condition/disease
            ctgov_nct_ids: NCT IDs found via CT.gov search

        Returns:
            Validation results with incremental yield
        """
        logger.info(f"Validating {drug} ({condition}) against ICTRP")

        # Search ICTRP
        ictrp_result = self.search_ictrp(f"{drug} {condition}", max_results=500)

        if ictrp_result.error:
            return {
                "drug": drug,
                "condition": condition,
                "error": ictrp_result.error
            }

        # Extract NCT IDs from ICTRP results
        ictrp_nct_ids = set()
        other_registry_ids = set()

        for trial in ictrp_result.trials:
            if trial.registry == "ClinicalTrials.gov":
                ictrp_nct_ids.add(trial.trial_id.upper())
            else:
                other_registry_ids.add(f"{trial.registry}:{trial.trial_id}")

            # Also check secondary IDs
            for sec_id in trial.secondary_ids:
                if re.match(r'^NCT\d{8}$', sec_id, re.I):
                    ictrp_nct_ids.add(sec_id.upper())

        # Calculate overlap and incremental yield
        overlap = ctgov_nct_ids & ictrp_nct_ids
        ctgov_only = ctgov_nct_ids - ictrp_nct_ids
        ictrp_only = ictrp_nct_ids - ctgov_nct_ids

        return {
            "drug": drug,
            "condition": condition,
            "timestamp": datetime.now().isoformat(),
            "ctgov_count": len(ctgov_nct_ids),
            "ictrp_total": ictrp_result.total_found,
            "ictrp_nct_count": len(ictrp_nct_ids),
            "overlap": len(overlap),
            "ctgov_only": len(ctgov_only),
            "ictrp_only": len(ictrp_only),
            "other_registries": len(other_registry_ids),
            "incremental_yield": len(ictrp_only) / len(ctgov_nct_ids) if ctgov_nct_ids else 0,
            "ictrp_nct_ids": list(ictrp_nct_ids),
            "other_registry_ids": list(other_registry_ids)[:20]  # Limit for readability
        }

    def run_validation_batch(
        self,
        drugs: List[Dict[str, Any]],
        ctgov_results: Dict[str, Set[str]]
    ) -> Dict[str, Any]:
        """
        Run validation for multiple drugs.

        Args:
            drugs: List of {"drug": name, "condition": condition}
            ctgov_results: Dict mapping drug names to CT.gov NCT IDs

        Returns:
            Batch validation results
        """
        results = []
        total_ctgov = 0
        total_ictrp_only = 0

        for drug_info in drugs:
            drug = drug_info["drug"]
            condition = drug_info.get("condition", "")

            ctgov_ncts = ctgov_results.get(drug.lower(), set())
            total_ctgov += len(ctgov_ncts)

            result = self.validate_drug_against_ictrp(drug, condition, ctgov_ncts)
            results.append(result)

            if "ictrp_only" in result:
                total_ictrp_only += result["ictrp_only"]

            # Progress indicator
            print(f"  {drug}: CT.gov={len(ctgov_ncts)}, ICTRP incremental={result.get('ictrp_only', 0)}")

            time.sleep(1)  # Additional delay between drugs

        return {
            "validation_type": "direct_ictrp",
            "timestamp": datetime.now().isoformat(),
            "drugs_validated": len(drugs),
            "total_ctgov_trials": total_ctgov,
            "total_ictrp_incremental": total_ictrp_only,
            "incremental_yield_percent": (total_ictrp_only / total_ctgov * 100) if total_ctgov else 0,
            "results": results
        }


def main():
    """Run direct ICTRP validation."""
    print("=" * 70)
    print("DIRECT WHO ICTRP VALIDATION")
    print("Validating against ICTRP portal (not PubMed proxy)")
    print("=" * 70)

    validator = DirectICTRPValidator()

    # Test drugs
    test_drugs = [
        {"drug": "semaglutide", "condition": "type 2 diabetes"},
        {"drug": "pembrolizumab", "condition": "cancer"},
        {"drug": "adalimumab", "condition": "rheumatoid arthritis"},
        {"drug": "tiotropium", "condition": "COPD"},
        {"drug": "rivaroxaban", "condition": "atrial fibrillation"},
    ]

    print("\nSearching ICTRP for test drugs...")

    results = []
    for drug_info in test_drugs:
        drug = drug_info["drug"]
        condition = drug_info["condition"]

        print(f"\n  Searching: {drug} + {condition}")
        result = validator.search_ictrp(f"{drug} {condition}")

        print(f"    Found: {result.total_found} total, {len(result.trials)} parsed")

        # Count by registry
        registry_counts = {}
        for trial in result.trials:
            registry_counts[trial.registry] = registry_counts.get(trial.registry, 0) + 1

        for registry, count in sorted(registry_counts.items(), key=lambda x: -x[1])[:5]:
            print(f"      {registry}: {count}")

        results.append({
            "drug": drug,
            "condition": condition,
            "total": result.total_found,
            "parsed": len(result.trials),
            "by_registry": registry_counts
        })

    # Save results
    output_dir = Path(__file__).parent.parent / "output"
    output_file = output_dir / "direct_ictrp_validation.json"

    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "method": "direct_ictrp_portal",
            "results": results
        }, f, indent=2)

    print(f"\n\nResults saved to: {output_file}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Drugs searched: {len(test_drugs)}")
    total_trials = sum(r["total"] for r in results)
    print(f"Total trials found: {total_trials}")
    print("\nNote: Direct ICTRP validation provides access to trials from 17+ registries")
    print("including ANZCTR, ChiCTR, DRKS, EUCTR, ISRCTN, and others not in CT.gov.")


if __name__ == "__main__":
    main()
