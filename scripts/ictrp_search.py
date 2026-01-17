#!/usr/bin/env python3
"""
WHO ICTRP Search Integration
Searches the WHO International Clinical Trials Registry Platform
Combines with CT.gov for comprehensive trial registry searching

The WHO ICTRP (https://trialsearch.who.int/) aggregates trial data from
17+ primary registries worldwide, providing a single point of access to
information about clinical trials.

Features:
- Search by condition/disease term
- Search by NCT ID to find cross-registered trials
- Parse and extract trial information from results
- Combine CT.gov and ICTRP results for comprehensive searching
- Rate limiting to be respectful to WHO servers
- Retry logic with exponential backoff
"""

import requests
import time
import sys
import re
import json
import logging
from typing import List, Dict, Optional, Tuple, Any, Union
from urllib.parse import quote, urlencode, parse_qs, urlparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
from functools import wraps
import random

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ctgov_config import CTGOV_API, DEFAULT_TIMEOUT, DEFAULT_RATE_LIMIT, DEFAULT_USER_AGENT  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# ICTRP URLs
ICTRP_BASE_URL = "https://trialsearch.who.int"
ICTRP_SEARCH_URL = f"{ICTRP_BASE_URL}/Trial2.aspx"
ICTRP_DEFAULT_SEARCH_URL = f"{ICTRP_BASE_URL}/Default.aspx"

# Rate limiting configuration
ICTRP_RATE_LIMIT = 1.0  # Seconds between requests (be respectful to WHO servers)
ICTRP_MAX_RETRIES = 3
ICTRP_RETRY_BACKOFF = 2.0  # Exponential backoff multiplier
ICTRP_TIMEOUT = 60  # Longer timeout for ICTRP (can be slow)

# Request configuration
DEFAULT_HEADERS = {
    'User-Agent': 'Clinical-Trial-Search-Tool/2.0 (Research; Systematic Review Support)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}


# =============================================================================
# DATA CLASSES
# =============================================================================


class TrialStatus(Enum):
    """Standard trial status values across registries."""
    RECRUITING = "Recruiting"
    NOT_RECRUITING = "Not Recruiting"
    COMPLETED = "Completed"
    ACTIVE = "Active"
    TERMINATED = "Terminated"
    WITHDRAWN = "Withdrawn"
    SUSPENDED = "Suspended"
    UNKNOWN = "Unknown"


@dataclass
class TrialRecord:
    """
    Standardized trial record that can represent trials from any registry.

    Attributes:
        trial_id: Primary identifier (e.g., NCT number, ISRCTN number)
        registry: Source registry name
        title: Official trial title
        status: Recruitment status
        condition: Primary condition/disease being studied
        intervention: Primary intervention being tested
        phase: Trial phase (if applicable)
        enrollment: Target or actual enrollment
        start_date: Trial start date
        completion_date: Expected or actual completion date
        sponsor: Primary sponsor organization
        countries: List of countries where trial is conducted
        secondary_ids: Cross-registration IDs from other registries
        url: Direct URL to trial record
        last_updated: When the record was last updated
    """
    trial_id: str
    registry: str
    title: str = ""
    status: str = ""
    condition: str = ""
    intervention: str = ""
    phase: str = ""
    enrollment: Optional[int] = None
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    sponsor: str = ""
    countries: List[str] = None
    secondary_ids: List[str] = None
    url: str = ""
    last_updated: Optional[str] = None

    def __post_init__(self):
        """Initialize list fields if None."""
        if self.countries is None:
            self.countries = []
        if self.secondary_ids is None:
            self.secondary_ids = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class SearchResult:
    """
    Container for search results from any registry.

    Attributes:
        source: Name of the registry/source
        query: The search query used
        total_count: Total number of matching trials
        returned_count: Number of trials returned in this result
        trials: List of TrialRecord objects
        search_url: URL that can be used to view results in browser
        error: Error message if search failed
        timestamp: When the search was performed
        metadata: Additional source-specific metadata
    """
    source: str
    query: str
    total_count: int = 0
    returned_count: int = 0
    trials: List[TrialRecord] = None
    search_url: str = ""
    error: Optional[str] = None
    timestamp: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        """Initialize fields."""
        if self.trials is None:
            self.trials = []
        if self.metadata is None:
            self.metadata = {}
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def is_successful(self) -> bool:
        """Check if search was successful."""
        return self.error is None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            'source': self.source,
            'query': self.query,
            'total_count': self.total_count,
            'returned_count': self.returned_count,
            'trials': [t.to_dict() for t in self.trials],
            'search_url': self.search_url,
            'error': self.error,
            'timestamp': self.timestamp,
            'metadata': self.metadata
        }
        return result


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def rate_limit(min_interval: float = ICTRP_RATE_LIMIT):
    """
    Decorator to enforce rate limiting between function calls.

    Args:
        min_interval: Minimum seconds between calls
    """
    last_call = [0.0]  # Use list for mutable closure

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call[0]
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed + random.uniform(0.1, 0.3)
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
            result = func(*args, **kwargs)
            last_call[0] = time.time()
            return result
        return wrapper
    return decorator


def retry_with_backoff(
    max_retries: int = ICTRP_MAX_RETRIES,
    backoff_factor: float = ICTRP_RETRY_BACKOFF,
    exceptions: Tuple = (requests.RequestException, ConnectionError, TimeoutError)
):
    """
    Decorator to retry a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = (backoff_factor ** attempt) + random.uniform(0.5, 1.5)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                            f"Retrying in {wait_time:.1f}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed: {e}")
            raise last_exception
        return wrapper
    return decorator


def extract_nct_ids(text: str) -> List[str]:
    """
    Extract NCT IDs from text.

    Args:
        text: Text to search for NCT IDs

    Returns:
        List of NCT IDs found (format: NCT########)
    """
    pattern = r'NCT\d{8}'
    return list(set(re.findall(pattern, text, re.IGNORECASE)))


def extract_isrctn_ids(text: str) -> List[str]:
    """
    Extract ISRCTN IDs from text.

    Args:
        text: Text to search for ISRCTN IDs

    Returns:
        List of ISRCTN IDs found
    """
    pattern = r'ISRCTN\d{8}'
    return list(set(re.findall(pattern, text, re.IGNORECASE)))


def normalize_status(status: str) -> str:
    """
    Normalize trial status to standard values.

    Args:
        status: Raw status string from registry

    Returns:
        Normalized status string
    """
    status_lower = status.lower().strip()

    status_mapping = {
        'recruiting': TrialStatus.RECRUITING.value,
        'active, not recruiting': TrialStatus.NOT_RECRUITING.value,
        'not yet recruiting': TrialStatus.NOT_RECRUITING.value,
        'completed': TrialStatus.COMPLETED.value,
        'active': TrialStatus.ACTIVE.value,
        'terminated': TrialStatus.TERMINATED.value,
        'withdrawn': TrialStatus.WITHDRAWN.value,
        'suspended': TrialStatus.SUSPENDED.value,
        'enrolling by invitation': TrialStatus.RECRUITING.value,
    }

    for key, value in status_mapping.items():
        if key in status_lower:
            return value

    return TrialStatus.UNKNOWN.value


# =============================================================================
# ICTRP SEARCHER CLASS
# =============================================================================


class ICTRPSearcher:
    """
    WHO ICTRP trial registry searcher.

    The ICTRP (International Clinical Trials Registry Platform) aggregates
    trial data from 17+ primary registries worldwide. This class provides
    methods to search ICTRP and parse results.

    Note: ICTRP does not have a public REST API, so this implementation
    uses web scraping techniques. Results should be verified against the
    official ICTRP website.

    Attributes:
        session: Requests session for making HTTP calls
        last_request_time: Timestamp of last request (for rate limiting)
    """

    def __init__(self, timeout: int = ICTRP_TIMEOUT):
        """
        Initialize the ICTRP searcher.

        Args:
            timeout: Request timeout in seconds
        """
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.timeout = timeout
        self.last_request_time = 0.0
        self._registries = None

        logger.info("ICTRPSearcher initialized")

    def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < ICTRP_RATE_LIMIT:
            sleep_time = ICTRP_RATE_LIMIT - elapsed + random.uniform(0.1, 0.3)
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    @retry_with_backoff()
    def _make_request(
        self,
        url: str,
        method: str = "GET",
        **kwargs
    ) -> requests.Response:
        """
        Make an HTTP request with retry logic.

        Args:
            url: URL to request
            method: HTTP method (GET or POST)
            **kwargs: Additional arguments to pass to requests

        Returns:
            Response object

        Raises:
            requests.RequestException: If request fails after retries
        """
        self._enforce_rate_limit()

        kwargs.setdefault('timeout', self.timeout)

        logger.debug(f"Making {method} request to {url}")

        if method.upper() == "GET":
            response = self.session.get(url, **kwargs)
        elif method.upper() == "POST":
            response = self.session.post(url, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response

    def get_registry_list(self) -> List[Dict[str, Any]]:
        """
        Get list of registries indexed by ICTRP.

        Returns:
            List of dictionaries with registry information
        """
        if self._registries is not None:
            return self._registries

        self._registries = [
            {
                "name": "ClinicalTrials.gov",
                "code": "NCT",
                "country": "United States",
                "has_api": True,
                "url": "https://clinicaltrials.gov",
                "id_pattern": r"NCT\d{8}",
                "description": "US National Library of Medicine registry"
            },
            {
                "name": "EU Clinical Trials Register",
                "code": "EUCTR",
                "country": "European Union",
                "has_api": True,
                "url": "https://www.clinicaltrialsregister.eu",
                "id_pattern": r"\d{4}-\d{6}-\d{2}",
                "description": "European Union clinical trials (EudraCT)"
            },
            {
                "name": "ISRCTN",
                "code": "ISRCTN",
                "country": "International",
                "has_api": True,
                "url": "https://www.isrctn.com",
                "id_pattern": r"ISRCTN\d{8}",
                "description": "International Standard Randomised Controlled Trial Number"
            },
            {
                "name": "Australian New Zealand Clinical Trials Registry",
                "code": "ACTRN",
                "country": "Australia/New Zealand",
                "has_api": False,
                "url": "https://www.anzctr.org.au",
                "id_pattern": r"ACTRN\d{14}",
                "description": "Australia and New Zealand trials"
            },
            {
                "name": "Chinese Clinical Trial Registry",
                "code": "ChiCTR",
                "country": "China",
                "has_api": False,
                "url": "https://www.chictr.org.cn",
                "id_pattern": r"ChiCTR\d+",
                "description": "Chinese clinical trials"
            },
            {
                "name": "German Clinical Trials Register",
                "code": "DRKS",
                "country": "Germany",
                "has_api": False,
                "url": "https://www.drks.de",
                "id_pattern": r"DRKS\d{8}",
                "description": "German clinical trials (DRKS)"
            },
            {
                "name": "Iranian Registry of Clinical Trials",
                "code": "IRCT",
                "country": "Iran",
                "has_api": False,
                "url": "https://en.irct.ir",
                "id_pattern": r"IRCT\d+N\d+",
                "description": "Iranian clinical trials"
            },
            {
                "name": "Japan Primary Registries Network",
                "code": "JPRN",
                "country": "Japan",
                "has_api": False,
                "url": "https://rctportal.niph.go.jp",
                "id_pattern": r"(jRCT|UMIN|JapicCTI)\d+",
                "description": "Japanese clinical trials network"
            },
            {
                "name": "Pan African Clinical Trials Registry",
                "code": "PACTR",
                "country": "Africa",
                "has_api": False,
                "url": "https://pactr.samrc.ac.za",
                "id_pattern": r"PACTR\d+",
                "description": "Pan-African clinical trials"
            },
            {
                "name": "Clinical Trials Registry - India",
                "code": "CTRI",
                "country": "India",
                "has_api": False,
                "url": "https://ctri.nic.in",
                "id_pattern": r"CTRI/\d{4}/\d{2}/\d+",
                "description": "Indian clinical trials"
            },
            {
                "name": "Sri Lanka Clinical Trials Registry",
                "code": "SLCTR",
                "country": "Sri Lanka",
                "has_api": False,
                "url": "https://slctr.lk",
                "id_pattern": r"SLCTR/\d{4}/\d+",
                "description": "Sri Lankan clinical trials"
            },
            {
                "name": "Thai Clinical Trials Registry",
                "code": "TCTR",
                "country": "Thailand",
                "has_api": False,
                "url": "https://www.thaiclinicaltrials.org",
                "id_pattern": r"TCTR\d+",
                "description": "Thai clinical trials"
            },
            {
                "name": "Netherlands Trial Register",
                "code": "NTR",
                "country": "Netherlands",
                "has_api": False,
                "url": "https://www.trialregister.nl",
                "id_pattern": r"NL\d+",
                "description": "Dutch clinical trials"
            },
            {
                "name": "Brazilian Clinical Trials Registry",
                "code": "ReBec",
                "country": "Brazil",
                "has_api": False,
                "url": "https://ensaiosclinicos.gov.br",
                "id_pattern": r"RBR-\w+",
                "description": "Brazilian clinical trials"
            },
            {
                "name": "Cuban Public Registry of Clinical Trials",
                "code": "RPCEC",
                "country": "Cuba",
                "has_api": False,
                "url": "https://registroclinico.sld.cu",
                "id_pattern": r"RPCEC\d+",
                "description": "Cuban clinical trials"
            },
            {
                "name": "Peruvian Clinical Trials Registry",
                "code": "REPEC",
                "country": "Peru",
                "has_api": False,
                "url": "https://ensayosclinicos-repec.ins.gob.pe",
                "id_pattern": r"PER-\d+-\d+",
                "description": "Peruvian clinical trials"
            },
            {
                "name": "Lebanese Clinical Trials Registry",
                "code": "LBCTR",
                "country": "Lebanon",
                "has_api": False,
                "url": "https://lbctr.emro.who.int",
                "id_pattern": r"LBCTR\d+",
                "description": "Lebanese clinical trials"
            },
        ]

        return self._registries

    def search_by_condition(
        self,
        condition: str,
        max_results: int = 100
    ) -> SearchResult:
        """
        Search ICTRP by condition/disease term.

        This method generates the search URL and provides information about
        how to access ICTRP results. Due to ICTRP's ASP.NET architecture
        with ViewState/EventValidation, automated scraping is limited.

        Args:
            condition: Disease or condition term to search for
            max_results: Maximum number of results to return

        Returns:
            SearchResult with search information and URL
        """
        logger.info(f"Searching ICTRP for condition: {condition}")

        # Build search URL
        encoded_condition = quote(condition)
        search_url = f"{ICTRP_DEFAULT_SEARCH_URL}?SearchAll={encoded_condition}"

        try:
            # Attempt to fetch the search page to get basic info
            response = self._make_request(search_url)
            html_content = response.text

            # Try to extract result count from page
            total_count = self._extract_result_count(html_content)

            # Try to parse any visible trial information
            trials = self._parse_trial_list(html_content, max_results)

            return SearchResult(
                source="WHO ICTRP",
                query=condition,
                total_count=total_count,
                returned_count=len(trials),
                trials=trials,
                search_url=search_url,
                metadata={
                    "search_type": "condition",
                    "registries_searched": [r["name"] for r in self.get_registry_list()],
                    "note": "ICTRP aggregates data from 17+ primary registries"
                }
            )

        except requests.RequestException as e:
            logger.error(f"Error searching ICTRP: {e}")
            return SearchResult(
                source="WHO ICTRP",
                query=condition,
                error=str(e),
                search_url=search_url,
                metadata={"search_type": "condition"}
            )

    def search_by_trial_id(
        self,
        trial_id: str
    ) -> SearchResult:
        """
        Search ICTRP by trial ID to find cross-registered trials.

        This is useful for finding the same trial registered in multiple
        registries (e.g., finding an ISRCTN registration for an NCT trial).

        Args:
            trial_id: Trial ID to search for (e.g., NCT12345678, ISRCTN12345678)

        Returns:
            SearchResult with cross-registration information
        """
        logger.info(f"Searching ICTRP for trial ID: {trial_id}")

        # Normalize trial ID
        trial_id_upper = trial_id.upper().strip()

        # Build search URL
        search_url = f"{ICTRP_DEFAULT_SEARCH_URL}?SearchAll={trial_id_upper}"

        try:
            response = self._make_request(search_url)
            html_content = response.text

            # Parse results
            total_count = self._extract_result_count(html_content)
            trials = self._parse_trial_list(html_content, max_results=50)

            # Look for cross-registrations in the results
            cross_registrations = self._find_cross_registrations(trials, trial_id_upper)

            return SearchResult(
                source="WHO ICTRP",
                query=trial_id,
                total_count=total_count,
                returned_count=len(trials),
                trials=trials,
                search_url=search_url,
                metadata={
                    "search_type": "trial_id",
                    "cross_registrations": cross_registrations,
                    "primary_id": trial_id_upper
                }
            )

        except requests.RequestException as e:
            logger.error(f"Error searching ICTRP for trial ID: {e}")
            return SearchResult(
                source="WHO ICTRP",
                query=trial_id,
                error=str(e),
                search_url=search_url,
                metadata={"search_type": "trial_id"}
            )

    def search_by_nct_id(self, nct_id: str) -> SearchResult:
        """
        Search ICTRP by NCT ID to find cross-registered trials.

        Convenience method that validates and searches for NCT IDs specifically.

        Args:
            nct_id: ClinicalTrials.gov NCT number (e.g., NCT12345678)

        Returns:
            SearchResult with cross-registration information

        Raises:
            ValueError: If NCT ID format is invalid
        """
        # Validate NCT ID format
        nct_id = nct_id.upper().strip()
        if not re.match(r'^NCT\d{8}$', nct_id):
            raise ValueError(f"Invalid NCT ID format: {nct_id}. Expected format: NCT########")

        return self.search_by_trial_id(nct_id)

    def _extract_result_count(self, html: str) -> int:
        """
        Extract the total result count from ICTRP HTML.

        Args:
            html: HTML content from ICTRP search page

        Returns:
            Total number of results, or 0 if not found
        """
        # Try various patterns used by ICTRP
        patterns = [
            r'(\d+)\s*(?:records?|results?|trials?)\s*found',
            r'Showing\s*\d+\s*-\s*\d+\s*of\s*(\d+)',
            r'Total:\s*(\d+)',
            r'Found\s*(\d+)\s*(?:records?|results?|trials?)',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1).replace(',', ''))
                except ValueError:
                    continue

        return 0

    def _parse_trial_list(
        self,
        html: str,
        max_results: int = 100
    ) -> List[TrialRecord]:
        """
        Parse trial list from ICTRP HTML content.

        Args:
            html: HTML content from ICTRP search page
            max_results: Maximum number of trials to parse

        Returns:
            List of TrialRecord objects
        """
        trials = []

        # Pattern to find trial entries in ICTRP HTML
        # ICTRP uses various table/div structures depending on the page version

        # Try to find trial ID patterns
        trial_id_patterns = [
            (r'(NCT\d{8})', 'ClinicalTrials.gov'),
            (r'(ISRCTN\d{8})', 'ISRCTN'),
            (r'(ACTRN\d{14})', 'ANZCTR'),
            (r'(ChiCTR[\w-]+)', 'ChiCTR'),
            (r'(EUCTR\d{4}-\d{6}-\d{2})', 'EUCTR'),
            (r'(DRKS\d{8})', 'DRKS'),
            (r'(CTRI/\d{4}/\d{2}/\d+)', 'CTRI'),
            (r'(JPRN-\w+)', 'JPRN'),
            (r'(KCT\d+)', 'CRIS'),  # Korean Clinical Research Information Service
        ]

        found_ids = set()

        for pattern, registry in trial_id_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for trial_id in matches:
                if trial_id not in found_ids and len(trials) < max_results:
                    found_ids.add(trial_id)

                    # Try to extract title near the trial ID
                    title = self._extract_title_for_id(html, trial_id)

                    trial = TrialRecord(
                        trial_id=trial_id,
                        registry=registry,
                        title=title,
                        url=self._get_trial_url(trial_id, registry)
                    )
                    trials.append(trial)

        return trials

    def _extract_title_for_id(self, html: str, trial_id: str) -> str:
        """
        Try to extract the trial title near a trial ID in HTML.

        Args:
            html: HTML content
            trial_id: Trial ID to find title for

        Returns:
            Trial title if found, empty string otherwise
        """
        # Look for title in surrounding context
        # This is a simplified approach - actual parsing would need HTML parser

        escaped_id = re.escape(trial_id)

        # Try to find title patterns near the ID
        patterns = [
            # Title in same cell/div
            rf'{escaped_id}[^<]*<[^>]*>[^<]*</[^>]*>\s*([^<]+)',
            # Title in adjacent element
            rf'{escaped_id}.*?(?:title|name)["\s:>]+([^<]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                title = match.group(1).strip()
                # Clean up the title
                title = re.sub(r'\s+', ' ', title)
                title = title[:500]  # Limit length
                if len(title) > 10:  # Reasonable minimum for a title
                    return title

        return ""

    def _get_trial_url(self, trial_id: str, registry: str) -> str:
        """
        Get the direct URL to a trial record.

        Args:
            trial_id: Trial ID
            registry: Registry name

        Returns:
            URL to trial record
        """
        url_templates = {
            'ClinicalTrials.gov': f'https://clinicaltrials.gov/study/{trial_id}',
            'ISRCTN': f'https://www.isrctn.com/{trial_id}',
            'ANZCTR': f'https://www.anzctr.org.au/Trial/Registration/TrialReview.aspx?id={trial_id}',
            'ChiCTR': f'https://www.chictr.org.cn/showproj.html?proj={trial_id}',
            'EUCTR': f'https://www.clinicaltrialsregister.eu/ctr-search/search?query={trial_id}',
            'DRKS': f'https://drks.de/search/en/trial/{trial_id}',
            'CTRI': f'https://ctri.nic.in/Clinicaltrials/showallp.php?mid1={trial_id}',
        }

        return url_templates.get(registry, f'{ICTRP_DEFAULT_SEARCH_URL}?SearchAll={trial_id}')

    def _find_cross_registrations(
        self,
        trials: List[TrialRecord],
        primary_id: str
    ) -> List[Dict[str, str]]:
        """
        Find cross-registrations for a trial.

        Args:
            trials: List of parsed trials
            primary_id: The original trial ID searched for

        Returns:
            List of cross-registration info dictionaries
        """
        cross_regs = []

        for trial in trials:
            if trial.trial_id.upper() != primary_id:
                cross_regs.append({
                    'id': trial.trial_id,
                    'registry': trial.registry,
                    'url': trial.url
                })

        return cross_regs

    def search_isrctn(
        self,
        condition: str,
        max_results: int = 100
    ) -> SearchResult:
        """
        Search ISRCTN registry (has public API).

        Args:
            condition: Condition term to search for
            max_results: Maximum results to return

        Returns:
            SearchResult with ISRCTN trials
        """
        logger.info(f"Searching ISRCTN for: {condition}")

        search_url = f"https://www.isrctn.com/search?q={quote(condition)}"
        api_url = f"https://www.isrctn.com/api/query/format/json?q={quote(condition)}&pageSize={max_results}"

        try:
            response = self._make_request(api_url)
            data = response.json()

            total = data.get('totalCount', 0)
            results = data.get('results', [])

            trials = []
            for item in results[:max_results]:
                trial = TrialRecord(
                    trial_id=item.get('isrctn', ''),
                    registry='ISRCTN',
                    title=item.get('title', ''),
                    status=normalize_status(item.get('recruitmentStatus', '')),
                    condition=item.get('condition', ''),
                    sponsor=item.get('sponsor', {}).get('name', ''),
                    url=f"https://www.isrctn.com/{item.get('isrctn', '')}"
                )
                trials.append(trial)

            return SearchResult(
                source="ISRCTN",
                query=condition,
                total_count=total,
                returned_count=len(trials),
                trials=trials,
                search_url=search_url,
                metadata={"api_available": True}
            )

        except requests.RequestException as e:
            logger.error(f"Error searching ISRCTN: {e}")
            return SearchResult(
                source="ISRCTN",
                query=condition,
                error=str(e),
                search_url=search_url
            )

    def search_euctr(self, condition: str) -> SearchResult:
        """
        Generate search URL for EU Clinical Trials Register.

        The EUCTR doesn't have a simple API, but we can generate search URLs.

        Args:
            condition: Condition term to search for

        Returns:
            SearchResult with EUCTR search URL
        """
        logger.info(f"Generating EUCTR search URL for: {condition}")

        search_url = f"https://www.clinicaltrialsregister.eu/ctr-search/search?query={quote(condition)}"

        return SearchResult(
            source="EU Clinical Trials Register",
            query=condition,
            search_url=search_url,
            metadata={
                "note": "EUCTR requires manual search or specialized scraping",
                "api_available": False
            }
        )

    def generate_all_registry_urls(self, condition: str) -> Dict[str, str]:
        """
        Generate search URLs for all registries.

        Args:
            condition: Condition term to search for

        Returns:
            Dictionary mapping registry names to search URLs
        """
        encoded = quote(condition)

        return {
            "ClinicalTrials.gov": f"https://clinicaltrials.gov/search?cond={encoded}",
            "WHO ICTRP": f"{ICTRP_DEFAULT_SEARCH_URL}?SearchAll={encoded}",
            "ISRCTN": f"https://www.isrctn.com/search?q={encoded}",
            "EUCTR": f"https://www.clinicaltrialsregister.eu/ctr-search/search?query={encoded}",
            "ANZCTR": f"https://www.anzctr.org.au/TrialSearch.aspx#&&searchTxt={encoded}",
            "ChiCTR": f"https://www.chictr.org.cn/searchproj.html?title={encoded}",
            "DRKS": f"https://drks.de/search/de?query={encoded}",
            "CTRI": f"https://ctri.nic.in/Clinicaltrials/advancesearchmain.php?search_form=1&freetxt={encoded}",
            "JPRN": f"https://rctportal.niph.go.jp/en/search?term={encoded}",
        }


# =============================================================================
# MULTI-REGISTRY SEARCHER CLASS
# =============================================================================


class MultiRegistrySearcher:
    """
    Search across multiple trial registries.

    This class provides unified searching across ClinicalTrials.gov,
    WHO ICTRP, ISRCTN, and other registries, combining results for
    comprehensive systematic review searches.

    Attributes:
        ctgov_api: ClinicalTrials.gov API URL
        ictrp: ICTRPSearcher instance
        session: Requests session
    """

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        """
        Initialize the multi-registry searcher.

        Args:
            timeout: Request timeout in seconds
        """
        self.ctgov_api = CTGOV_API
        self.ictrp = ICTRPSearcher(timeout=timeout)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': DEFAULT_USER_AGENT,
            'Accept': 'application/json'
        })
        self.timeout = timeout

        logger.info("MultiRegistrySearcher initialized")

    @retry_with_backoff()
    def search_ctgov(
        self,
        condition: str,
        strategy: str = "basic",
        max_results: int = 1000
    ) -> SearchResult:
        """
        Search ClinicalTrials.gov with specified strategy.

        Args:
            condition: Condition term to search for
            strategy: Search strategy to use:
                - "basic": Simple condition search
                - "rct": Randomized controlled trials only
                - "rct_treatment": RCTs with treatment purpose
            max_results: Maximum results to return

        Returns:
            SearchResult with ClinicalTrials.gov trials
        """
        logger.info(f"Searching ClinicalTrials.gov for: {condition} (strategy: {strategy})")

        # Build query based on strategy
        query_parts = [f"query.cond={quote(condition)}"]

        if strategy == "rct":
            query_parts.append(f"query.term={quote('AREA[DesignAllocation]RANDOMIZED')}")
        elif strategy == "rct_treatment":
            query_parts.append(f"query.term={quote('AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT')}")

        query_parts.extend([
            "countTotal=true",
            f"pageSize={min(max_results, 1000)}"
        ])

        url = f"{self.ctgov_api}?{'&'.join(query_parts)}"
        search_url = f"https://clinicaltrials.gov/search?cond={quote(condition)}"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            total_count = data.get('totalCount', 0)
            studies = data.get('studies', [])

            trials = []
            for study in studies[:max_results]:
                protocol = study.get('protocolSection', {})
                id_module = protocol.get('identificationModule', {})
                status_module = protocol.get('statusModule', {})
                design_module = protocol.get('designModule', {})

                # Extract secondary IDs
                secondary_ids = []
                for sec_id in id_module.get('secondaryIdInfos', []):
                    secondary_ids.append(sec_id.get('id', ''))

                trial = TrialRecord(
                    trial_id=id_module.get('nctId', ''),
                    registry='ClinicalTrials.gov',
                    title=id_module.get('officialTitle', id_module.get('briefTitle', '')),
                    status=normalize_status(status_module.get('overallStatus', '')),
                    condition=', '.join(protocol.get('conditionsModule', {}).get('conditions', [])),
                    phase=', '.join(design_module.get('phases', [])),
                    enrollment=design_module.get('enrollmentInfo', {}).get('count'),
                    start_date=status_module.get('startDateStruct', {}).get('date'),
                    completion_date=status_module.get('completionDateStruct', {}).get('date'),
                    sponsor=protocol.get('sponsorCollaboratorsModule', {}).get('leadSponsor', {}).get('name', ''),
                    secondary_ids=secondary_ids,
                    url=f"https://clinicaltrials.gov/study/{id_module.get('nctId', '')}"
                )
                trials.append(trial)

            return SearchResult(
                source="ClinicalTrials.gov",
                query=condition,
                total_count=total_count,
                returned_count=len(trials),
                trials=trials,
                search_url=search_url,
                metadata={
                    "strategy": strategy,
                    "api_version": "v2"
                }
            )

        except requests.RequestException as e:
            logger.error(f"Error searching ClinicalTrials.gov: {e}")
            return SearchResult(
                source="ClinicalTrials.gov",
                query=condition,
                error=str(e),
                search_url=search_url,
                metadata={"strategy": strategy}
            )

    def search_all_registries(
        self,
        condition: str,
        include_ctgov: bool = True,
        include_ictrp: bool = True,
        include_isrctn: bool = True,
        include_euctr: bool = True
    ) -> Dict[str, Any]:
        """
        Search across all available registries.

        Args:
            condition: Condition term to search for
            include_ctgov: Whether to search ClinicalTrials.gov
            include_ictrp: Whether to search WHO ICTRP
            include_isrctn: Whether to search ISRCTN
            include_euctr: Whether to generate EUCTR search URL

        Returns:
            Dictionary with combined results from all registries
        """
        logger.info(f"Starting multi-registry search for: {condition}")

        results = {
            "condition": condition,
            "timestamp": datetime.now().isoformat(),
            "registries": {},
            "total_estimated": 0,
            "search_urls": {}
        }

        # ClinicalTrials.gov
        if include_ctgov:
            print("  Searching ClinicalTrials.gov...")
            ctgov_result = self.search_ctgov(condition, strategy="basic")
            results["registries"]["ctgov"] = ctgov_result.to_dict()
            if ctgov_result.is_successful():
                results["total_estimated"] += ctgov_result.total_count
            time.sleep(DEFAULT_RATE_LIMIT)

        # ISRCTN
        if include_isrctn:
            print("  Searching ISRCTN...")
            isrctn_result = self.ictrp.search_isrctn(condition)
            results["registries"]["isrctn"] = isrctn_result.to_dict()
            if isrctn_result.is_successful():
                results["total_estimated"] += isrctn_result.total_count
            time.sleep(ICTRP_RATE_LIMIT)

        # WHO ICTRP
        if include_ictrp:
            print("  Searching WHO ICTRP...")
            ictrp_result = self.ictrp.search_by_condition(condition)
            results["registries"]["ictrp"] = ictrp_result.to_dict()
            # Don't add to total as ICTRP aggregates other registries
            time.sleep(ICTRP_RATE_LIMIT)

        # EUCTR (URL only)
        if include_euctr:
            euctr_result = self.ictrp.search_euctr(condition)
            results["registries"]["euctr"] = euctr_result.to_dict()

        # Generate all search URLs
        results["search_urls"] = self.ictrp.generate_all_registry_urls(condition)

        logger.info(f"Multi-registry search complete. Estimated total: {results['total_estimated']}")

        return results

    def find_cross_registrations(self, nct_id: str) -> Dict[str, Any]:
        """
        Find cross-registrations for an NCT trial.

        Args:
            nct_id: ClinicalTrials.gov NCT number

        Returns:
            Dictionary with cross-registration information
        """
        logger.info(f"Finding cross-registrations for: {nct_id}")

        result = {
            "primary_id": nct_id,
            "timestamp": datetime.now().isoformat(),
            "ctgov_secondary_ids": [],
            "ictrp_cross_registrations": [],
            "all_registrations": []
        }

        # First, get secondary IDs from ClinicalTrials.gov
        print("  Checking ClinicalTrials.gov for secondary IDs...")
        ctgov_result = self.search_ctgov(nct_id, strategy="basic", max_results=1)

        if ctgov_result.is_successful() and ctgov_result.trials:
            trial = ctgov_result.trials[0]
            result["ctgov_secondary_ids"] = trial.secondary_ids
            result["all_registrations"].append({
                "id": nct_id,
                "registry": "ClinicalTrials.gov",
                "url": trial.url,
                "title": trial.title
            })

        time.sleep(DEFAULT_RATE_LIMIT)

        # Then search ICTRP for cross-registrations
        print("  Searching WHO ICTRP for cross-registrations...")
        ictrp_result = self.ictrp.search_by_nct_id(nct_id)

        if ictrp_result.is_successful():
            cross_regs = ictrp_result.metadata.get("cross_registrations", [])
            result["ictrp_cross_registrations"] = cross_regs

            for reg in cross_regs:
                result["all_registrations"].append(reg)

        # Deduplicate registrations
        seen = set()
        unique_regs = []
        for reg in result["all_registrations"]:
            reg_id = reg.get("id", "")
            if reg_id and reg_id not in seen:
                seen.add(reg_id)
                unique_regs.append(reg)
        result["all_registrations"] = unique_regs

        logger.info(f"Found {len(result['all_registrations'])} registrations for {nct_id}")

        return result

    def combine_ctgov_and_ictrp_results(
        self,
        condition: str,
        deduplicate: bool = True
    ) -> Dict[str, Any]:
        """
        Combine CT.gov and ICTRP results for comprehensive searching.

        This method searches both registries and optionally deduplicates
        results based on trial IDs and secondary identifiers.

        Args:
            condition: Condition term to search for
            deduplicate: Whether to attempt deduplication

        Returns:
            Dictionary with combined and optionally deduplicated results
        """
        logger.info(f"Combining CT.gov and ICTRP results for: {condition}")

        result = {
            "condition": condition,
            "timestamp": datetime.now().isoformat(),
            "ctgov": {},
            "ictrp": {},
            "combined_count": 0,
            "unique_count": 0,
            "all_trials": [],
            "deduplication_applied": deduplicate
        }

        # Search ClinicalTrials.gov
        print("  Searching ClinicalTrials.gov...")
        ctgov_result = self.search_ctgov(condition, strategy="basic")
        result["ctgov"] = {
            "total": ctgov_result.total_count,
            "returned": ctgov_result.returned_count,
            "error": ctgov_result.error
        }

        all_trials = []
        if ctgov_result.is_successful():
            all_trials.extend(ctgov_result.trials)

        time.sleep(DEFAULT_RATE_LIMIT)

        # Search ICTRP
        print("  Searching WHO ICTRP...")
        ictrp_result = self.ictrp.search_by_condition(condition)
        result["ictrp"] = {
            "total": ictrp_result.total_count,
            "returned": ictrp_result.returned_count,
            "error": ictrp_result.error
        }

        if ictrp_result.is_successful():
            all_trials.extend(ictrp_result.trials)

        result["combined_count"] = len(all_trials)

        # Deduplicate if requested
        if deduplicate:
            seen_ids = set()
            unique_trials = []

            for trial in all_trials:
                # Check primary ID
                if trial.trial_id in seen_ids:
                    continue

                # Check secondary IDs
                is_duplicate = False
                for sec_id in trial.secondary_ids:
                    if sec_id in seen_ids:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    seen_ids.add(trial.trial_id)
                    for sec_id in trial.secondary_ids:
                        seen_ids.add(sec_id)
                    unique_trials.append(trial)

            result["all_trials"] = [t.to_dict() for t in unique_trials]
            result["unique_count"] = len(unique_trials)
            result["duplicates_removed"] = len(all_trials) - len(unique_trials)
        else:
            result["all_trials"] = [t.to_dict() for t in all_trials]
            result["unique_count"] = len(all_trials)

        logger.info(
            f"Combined results: {result['combined_count']} total, "
            f"{result['unique_count']} unique"
        )

        return result


# =============================================================================
# REPORT GENERATION
# =============================================================================


def create_comprehensive_search_report(
    condition: str,
    output_dir: Path,
    searcher: Optional[MultiRegistrySearcher] = None
) -> Dict[str, Any]:
    """
    Generate a comprehensive multi-registry search report.

    Args:
        condition: Condition term to search for
        output_dir: Directory to save output files
        searcher: Optional pre-initialized searcher instance

    Returns:
        Dictionary with all search results
    """
    if searcher is None:
        searcher = MultiRegistrySearcher()

    print(f"\n{'=' * 70}")
    print(f"Comprehensive Trial Registry Search: {condition.upper()}")
    print(f"{'=' * 70}")

    # Search all registries
    results = searcher.search_all_registries(condition)

    # Generate report
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("COMPREHENSIVE TRIAL REGISTRY SEARCH REPORT")
    report_lines.append(f"Condition: {condition}")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 70)
    report_lines.append("")

    report_lines.append("SEARCH RESULTS BY REGISTRY")
    report_lines.append("-" * 50)

    for reg_id, data in results["registries"].items():
        source = data.get("source", reg_id)
        count = data.get("total_count", 0)
        error = data.get("error")

        if error:
            report_lines.append(f"  {source}: ERROR - {error}")
        elif count > 0:
            report_lines.append(f"  {source}: {count:,} trials found")
        else:
            report_lines.append(f"  {source}: Search URL available (manual search required)")

    report_lines.append("")
    report_lines.append(f"ESTIMATED TOTAL (excluding ICTRP to avoid double-counting): {results.get('total_estimated', 0):,}")
    report_lines.append("")

    report_lines.append("DIRECT SEARCH URLS")
    report_lines.append("-" * 50)
    for name, url in results.get("search_urls", {}).items():
        report_lines.append(f"  {name}:")
        report_lines.append(f"    {url}")
        report_lines.append("")

    report_lines.append("REGISTRY COVERAGE NOTES")
    report_lines.append("-" * 50)
    report_lines.append("  - ClinicalTrials.gov: US and international trials (API available)")
    report_lines.append("  - WHO ICTRP: Aggregates 17+ primary registries worldwide")
    report_lines.append("  - ISRCTN: International Standard Randomised Controlled Trials (API available)")
    report_lines.append("  - EUCTR: European Union trials (required for EU drug authorization)")
    report_lines.append("  - ANZCTR: Australia/New Zealand trials")
    report_lines.append("  - ChiCTR: Chinese clinical trials")
    report_lines.append("  - CTRI: Clinical Trials Registry - India")
    report_lines.append("  - DRKS: German clinical trials")
    report_lines.append("")

    report_lines.append("RECOMMENDATIONS FOR SYSTEMATIC REVIEWS")
    report_lines.append("-" * 50)
    report_lines.append("  1. Search ClinicalTrials.gov (mandatory for most reviews)")
    report_lines.append("  2. Search WHO ICTRP (aggregates multiple registries)")
    report_lines.append("  3. Search ISRCTN (captures additional European trials)")
    report_lines.append("  4. Consider EUCTR for European drug trials")
    report_lines.append("  5. Search region-specific registries for targeted geographic reviews")
    report_lines.append("  6. Document all registries searched in review methodology")
    report_lines.append("")

    # Print and save report
    report_text = "\n".join(report_lines)
    print(report_text)

    # Ensure output directory exists
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create safe filename
    safe_condition = re.sub(r'[^\w\s-]', '', condition).replace(' ', '_')[:50]

    # Save JSON results
    json_file = output_dir / f"multi_registry_{safe_condition}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved JSON: {json_file}")

    # Save text report
    report_file = output_dir / f"multi_registry_{safe_condition}_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f"Saved report: {report_file}")

    return results


# =============================================================================
# MAIN FUNCTION
# =============================================================================


def main():
    """Main function demonstrating the ICTRP search capabilities."""

    # Setup output directory
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print("WHO ICTRP Search Integration Demo")
    print("=" * 70)

    # Initialize searcher
    searcher = MultiRegistrySearcher()

    # Demo 1: Search by condition
    print("\n--- Demo 1: Search by condition ---")
    conditions = ["type 2 diabetes", "breast cancer"]

    for condition in conditions:
        create_comprehensive_search_report(condition, output_dir, searcher)
        time.sleep(2)  # Be respectful between searches

    # Demo 2: Find cross-registrations for an NCT ID
    print("\n--- Demo 2: Find cross-registrations ---")
    nct_id = "NCT00000611"  # A well-known trial with cross-registrations

    print(f"\nSearching for cross-registrations of {nct_id}...")
    cross_reg_result = searcher.find_cross_registrations(nct_id)

    print(f"\nCross-registration results for {nct_id}:")
    print(f"  Secondary IDs from CT.gov: {cross_reg_result['ctgov_secondary_ids']}")
    print(f"  ICTRP cross-registrations: {len(cross_reg_result['ictrp_cross_registrations'])}")
    print(f"  All registrations found: {len(cross_reg_result['all_registrations'])}")

    # Save cross-registration results
    cross_reg_file = output_dir / f"cross_registration_{nct_id}.json"
    with open(cross_reg_file, 'w', encoding='utf-8') as f:
        json.dump(cross_reg_result, f, indent=2)
    print(f"  Saved: {cross_reg_file}")

    # Demo 3: Combined CT.gov and ICTRP search with deduplication
    print("\n--- Demo 3: Combined search with deduplication ---")
    combined_result = searcher.combine_ctgov_and_ictrp_results(
        "cystic fibrosis",
        deduplicate=True
    )

    print("\nCombined search results for 'cystic fibrosis':")
    print(f"  CT.gov total: {combined_result['ctgov']['total']}")
    print(f"  ICTRP total: {combined_result['ictrp']['total']}")
    print(f"  Combined count: {combined_result['combined_count']}")
    print(f"  Unique count (after deduplication): {combined_result['unique_count']}")

    combined_file = output_dir / "combined_search_cystic_fibrosis.json"
    with open(combined_file, 'w', encoding='utf-8') as f:
        json.dump(combined_result, f, indent=2, default=str)
    print(f"  Saved: {combined_file}")

    print("\n" + "=" * 70)
    print("Multi-registry search demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
