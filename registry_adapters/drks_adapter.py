"""
DRKS (German Clinical Trials Register / Deutsches Register Klinischer Studien) adapter.

Provides search and retrieval functionality for DRKS trials.
Registry URL: https://drks.de
"""

import re
import time
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

from .base_adapter import (
    BaseRegistryAdapter,
    RegistryType,
    StandardizedStudy,
    SearchResult,
    StudyStatus,
    StudyPhase,
)

logger = logging.getLogger(__name__)


class DRKSAdapter(BaseRegistryAdapter):
    """
    Adapter for DRKS (German Clinical Trials Register).

    DRKS provides XML export and web interface.
    Trial IDs follow format: DRKS00000000 (DRKS + 8 digits)

    Example usage:
        adapter = DRKSAdapter()
        results = adapter.search("diabetes type 2")
        study = adapter.get_study("DRKS00000001")
    """

    # DRKS ID pattern: DRKS + 8 digits
    ID_PATTERN = re.compile(r'^DRKS\d{8}$', re.IGNORECASE)

    def __init__(
        self,
        rate_limit: float = 0.5,
        timeout: int = 60,
        cache_ttl: int = 3600,
    ):
        super().__init__(
            registry_type=RegistryType.DRKS,
            base_url="https://drks.de",
            rate_limit=rate_limit,
            timeout=timeout,
            cache_ttl=cache_ttl,
        )

        if requests is None:
            raise ImportError("requests package required: pip install requests")
        if BeautifulSoup is None:
            raise ImportError("beautifulsoup4 package required: pip install beautifulsoup4 lxml")

    def validate_id(self, registry_id: str) -> bool:
        """Validate DRKS trial ID format."""
        return bool(self.ID_PATTERN.match(registry_id.strip()))

    def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> SearchResult:
        """
        Search DRKS for clinical trials.

        Args:
            query: Search query string
            page: Page number (1-indexed)
            page_size: Results per page (max 50)
            filters: Optional filters:
                - status: recruiting, completed, etc.
                - phase: 1, 2, 3, 4
                - study_type: Interventional, Observational

        Returns:
            SearchResult with matched studies
        """
        start_time = time.time()
        studies = []
        errors = []
        warnings = []
        total_count = 0

        # Check cache
        cache_key = f"search:{query}:{page}:{page_size}:{filters}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            self._rate_limit_wait()

            # DRKS search URL
            search_url = f"{self.base_url}/drks_web/navigate.do"

            # Build search parameters
            params = {
                "navigationId": "results",
                "searchType": "basic",
                "searchKey": query,
                "page": page,
                "resultsPerPage": min(page_size, 50),
            }

            # Apply filters
            if filters:
                if filters.get("status"):
                    params["recruitmentStatus"] = self._map_status_filter(filters["status"])
                if filters.get("phase"):
                    params["studyPhase"] = filters["phase"]

            response = requests.get(
                search_url,
                params=params,
                timeout=self.timeout,
                headers={
                    "User-Agent": "CTGov-Search-Strategies/1.0",
                    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
                }
            )
            response.raise_for_status()

            # Parse HTML response
            soup = BeautifulSoup(response.text, "lxml")

            # Extract total count
            count_elem = soup.select_one(".searchResultCount, .result-count")
            if count_elem:
                count_text = count_elem.get_text()
                match = re.search(r'(\d+)', count_text.replace(".", "").replace(",", ""))
                if match:
                    total_count = int(match.group(1))

            # Extract trial IDs from results
            trial_links = soup.select("a[href*='DRKS']")
            trial_ids = []
            for link in trial_links:
                href = link.get("href", "")
                text = link.get_text(strip=True)

                # Try to extract ID from href or text
                match = re.search(r'(DRKS\d{8})', href + text, re.IGNORECASE)
                if match:
                    trial_ids.append(match.group(1).upper())

            # Remove duplicates
            seen = set()
            unique_ids = []
            for tid in trial_ids:
                if tid not in seen:
                    seen.add(tid)
                    unique_ids.append(tid)

            # Fetch study details for each ID
            for trial_id in unique_ids[:page_size]:
                study = self.get_study(trial_id)
                if study:
                    studies.append(study)

        except requests.RequestException as e:
            logger.error(f"DRKS search error: {e}")
            errors.append(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"DRKS parsing error: {e}")
            errors.append(f"Parse error: {str(e)}")

        search_time = time.time() - start_time

        result = SearchResult(
            studies=studies,
            total_count=total_count if total_count > 0 else len(studies),
            query=query,
            registry=self.registry_type,
            search_time=search_time,
            page=page,
            page_size=page_size,
            has_more=page * page_size < total_count,
            errors=errors,
            warnings=warnings,
        )

        self._set_cached(cache_key, result)
        return result

    def get_study(self, registry_id: str) -> Optional[StandardizedStudy]:
        """
        Retrieve a single study by DRKS ID.

        Args:
            registry_id: DRKS trial ID (e.g., DRKS00000001)

        Returns:
            StandardizedStudy or None if not found
        """
        registry_id = registry_id.strip().upper()

        if not self.validate_id(registry_id):
            logger.warning(f"Invalid DRKS ID format: {registry_id}")
            return None

        # Check cache
        cache_key = f"study:{registry_id}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            self._rate_limit_wait()

            # DRKS XML export URL
            xml_url = f"{self.base_url}/drks_web/navigate.do"
            params = {
                "navigationId": "trial.XML",
                "TRIAL_ID": registry_id,
            }

            response = requests.get(
                xml_url,
                params=params,
                timeout=self.timeout,
                headers={
                    "User-Agent": "CTGov-Search-Strategies/1.0",
                    "Accept": "application/xml",
                }
            )
            response.raise_for_status()

            # Check if we got XML or need to fallback to HTML
            content_type = response.headers.get("Content-Type", "")
            if "xml" in content_type.lower():
                soup = BeautifulSoup(response.text, "lxml-xml")
                study = self._parse_xml_to_study(soup, registry_id)
            else:
                # Fallback to HTML detail page
                html_url = f"{self.base_url}/drks_web/navigate.do"
                params = {
                    "navigationId": "trial.HTML",
                    "TRIAL_ID": registry_id,
                }
                response = requests.get(
                    html_url,
                    params=params,
                    timeout=self.timeout,
                    headers={"User-Agent": "CTGov-Search-Strategies/1.0"}
                )
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "lxml")
                study = self._parse_html_to_study(soup, registry_id)

            if study:
                self._set_cached(cache_key, study)

            return study

        except requests.RequestException as e:
            logger.error(f"DRKS fetch error for {registry_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"DRKS parse error for {registry_id}: {e}")
            return None

    def _parse_xml_to_study(
        self,
        soup: BeautifulSoup,
        registry_id: str
    ) -> Optional[StandardizedStudy]:
        """Parse DRKS XML response to StandardizedStudy."""

        def get_text(tag_name: str) -> str:
            elem = soup.find(tag_name)
            return elem.get_text(strip=True) if elem else ""

        def get_all_text(tag_name: str) -> List[str]:
            elems = soup.find_all(tag_name)
            return [e.get_text(strip=True) for e in elems if e.get_text(strip=True)]

        try:
            study = StandardizedStudy(
                registry_id=registry_id,
                registry_type=RegistryType.DRKS,
                url=f"{self.base_url}/drks_web/navigate.do?navigationId=trial.HTML&TRIAL_ID={registry_id}",
            )

            # Titles
            study.title = get_text("scientificTitle") or get_text("publicTitle")
            study.brief_title = get_text("publicTitle")
            study.scientific_title = get_text("scientificTitle")
            study.acronym = get_text("acronym")

            # Secondary IDs
            study.secondary_ids = get_all_text("secondaryId")

            # Status
            status_text = get_text("recruitmentStatus")
            study.status = self._standardize_status(status_text)

            # Dates
            study.start_date = self._parse_date(get_text("studyStart"))
            study.completion_date = self._parse_date(get_text("studyEnd"))
            study.first_posted = self._parse_date(get_text("registrationDate"))
            study.last_updated = self._parse_date(get_text("lastUpdate"))

            # Study design
            study.study_type = get_text("studyType")
            study.phase = self._standardize_phase(get_text("phase"))
            study.allocation = get_text("allocation")
            study.intervention_model = get_text("interventionAssignment")
            study.masking = get_text("blinding")
            study.primary_purpose = get_text("purpose")

            # Enrollment
            enrollment_text = get_text("targetSize")
            if enrollment_text:
                try:
                    study.enrollment = int(re.sub(r'\D', '', enrollment_text))
                except ValueError:
                    pass

            # Population
            study.min_age = self._parse_age(get_text("minAge"))
            study.max_age = self._parse_age(get_text("maxAge"))
            study.sex = get_text("gender") or "All"

            inclusion = get_text("inclusionCriteria")
            exclusion = get_text("exclusionCriteria")
            study.eligibility_criteria = f"Inclusion:\n{inclusion}\n\nExclusion:\n{exclusion}"

            # Conditions
            study.conditions = get_all_text("condition") or get_all_text("healthCondition")

            # Interventions
            intervention_names = get_all_text("interventionName")
            intervention_types = get_all_text("interventionType")
            study.interventions = [
                {"name": name, "type": intervention_types[i] if i < len(intervention_types) else "Other"}
                for i, name in enumerate(intervention_names)
            ]

            # Outcomes
            primary_outcomes = get_all_text("primaryOutcome")
            study.primary_outcomes = [{"measure": o} for o in primary_outcomes]

            secondary_outcomes = get_all_text("secondaryOutcome")
            study.secondary_outcomes = [{"measure": o} for o in secondary_outcomes]

            # Sponsor
            study.lead_sponsor = get_text("sponsor") or get_text("leadSponsor")
            study.sponsor_type = get_text("sponsorType")

            # Countries
            countries = get_all_text("country")
            study.countries = countries if countries else ["Germany"]

            # Contact
            study.contact_name = get_text("contactName")
            study.contact_email = get_text("contactEmail")
            study.contact_phone = get_text("contactPhone")

            return study

        except Exception as e:
            logger.error(f"Error parsing DRKS XML: {e}")
            return None

    def _parse_html_to_study(
        self,
        soup: BeautifulSoup,
        registry_id: str
    ) -> Optional[StandardizedStudy]:
        """Parse DRKS HTML response to StandardizedStudy."""

        def get_field_value(label: str) -> str:
            """Extract value for a given field label."""
            for row in soup.select("tr"):
                cells = row.select("td, th")
                if len(cells) >= 2:
                    label_text = cells[0].get_text(strip=True).lower()
                    if label.lower() in label_text:
                        return cells[1].get_text(strip=True)
            return ""

        try:
            study = StandardizedStudy(
                registry_id=registry_id,
                registry_type=RegistryType.DRKS,
                url=f"{self.base_url}/drks_web/navigate.do?navigationId=trial.HTML&TRIAL_ID={registry_id}",
            )

            # Titles
            title_elem = soup.select_one("h1, .trial-title")
            if title_elem:
                study.title = title_elem.get_text(strip=True)
            else:
                study.title = get_field_value("Scientific title") or get_field_value("Public title")

            study.brief_title = get_field_value("Public title")
            study.scientific_title = get_field_value("Scientific title")

            # Status
            status_text = get_field_value("Recruitment status")
            study.status = self._standardize_status(status_text)

            # Dates
            study.start_date = self._parse_date(get_field_value("Study start"))
            study.completion_date = self._parse_date(get_field_value("Study end"))
            study.first_posted = self._parse_date(get_field_value("Registration date"))

            # Study design
            study.study_type = get_field_value("Study type")
            study.phase = self._standardize_phase(get_field_value("Phase"))

            # Enrollment
            enrollment_text = get_field_value("Target sample size")
            if enrollment_text:
                try:
                    study.enrollment = int(re.sub(r'\D', '', enrollment_text))
                except ValueError:
                    pass

            # Sponsor
            study.lead_sponsor = get_field_value("Sponsor")

            # Default country
            study.countries = ["Germany"]

            return study

        except Exception as e:
            logger.error(f"Error parsing DRKS HTML: {e}")
            return None

    def _map_status_filter(self, status: str) -> str:
        """Map standardized status to DRKS-specific filter value."""
        status_map = {
            "recruiting": "Recruiting",
            "active": "Ongoing",
            "completed": "Completed",
            "terminated": "Terminated",
            "withdrawn": "Withdrawn",
            "suspended": "Suspended",
            "not_yet_recruiting": "Not yet recruiting",
        }
        return status_map.get(status.lower(), status)


# Convenience function
def create_drks_adapter(**kwargs) -> DRKSAdapter:
    """Create and return a DRKS adapter instance."""
    return DRKSAdapter(**kwargs)
