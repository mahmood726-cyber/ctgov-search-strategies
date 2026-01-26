"""
ANZCTR (Australian New Zealand Clinical Trials Registry) adapter.

Provides search and retrieval functionality for ANZCTR trials.
API Documentation: https://www.anzctr.org.au/Support/FAQ.aspx
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


class ANZCTRAdapter(BaseRegistryAdapter):
    """
    Adapter for ANZCTR (Australian New Zealand Clinical Trials Registry).

    ANZCTR uses an XML export API and web scraping for search functionality.
    Trial IDs follow format: ACTRN12620000001p (ACTRN + 14 digits + check letter)

    Example usage:
        adapter = ANZCTRAdapter()
        results = adapter.search("diabetes type 2")
        study = adapter.get_study("ACTRN12620000001p")
    """

    # ANZCTR ID pattern: ACTRN + 14 digits + optional check letter
    ID_PATTERN = re.compile(r'^ACTRN\d{14}[a-z]?$', re.IGNORECASE)

    def __init__(
        self,
        rate_limit: float = 0.5,  # ANZCTR is slow, be conservative
        timeout: int = 60,
        cache_ttl: int = 3600,
    ):
        super().__init__(
            registry_type=RegistryType.ANZCTR,
            base_url="https://www.anzctr.org.au",
            rate_limit=rate_limit,
            timeout=timeout,
            cache_ttl=cache_ttl,
        )

        if requests is None:
            raise ImportError("requests package required: pip install requests")
        if BeautifulSoup is None:
            raise ImportError("beautifulsoup4 package required: pip install beautifulsoup4 lxml")

    def validate_id(self, registry_id: str) -> bool:
        """Validate ANZCTR trial ID format."""
        return bool(self.ID_PATTERN.match(registry_id.strip()))

    def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> SearchResult:
        """
        Search ANZCTR for clinical trials.

        Args:
            query: Search query string
            page: Page number (1-indexed)
            page_size: Results per page (max 100)
            filters: Optional filters:
                - status: recruiting, completed, etc.
                - phase: 1, 2, 3, 4
                - study_type: Interventional, Observational
                - country: AU, NZ, etc.

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

            # ANZCTR search URL
            search_url = f"{self.base_url}/TrialSearch.aspx"

            # Build search parameters
            params = {
                "searchTxt": query,
                "isBasic": "true",
                "pageSize": min(page_size, 100),
                "pg": page,
            }

            # Apply filters
            if filters:
                if filters.get("status"):
                    params["recruitmentStatus"] = self._map_status_filter(filters["status"])
                if filters.get("phase"):
                    params["phase"] = filters["phase"]
                if filters.get("country"):
                    params["country"] = filters["country"]

            response = requests.get(
                search_url,
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": "CTGov-Search-Strategies/1.0"}
            )
            response.raise_for_status()

            # Parse HTML response
            soup = BeautifulSoup(response.text, "lxml")

            # Extract total count
            count_elem = soup.select_one(".resultsCount")
            if count_elem:
                count_text = count_elem.get_text()
                match = re.search(r'(\d+)', count_text.replace(",", ""))
                if match:
                    total_count = int(match.group(1))

            # Extract trial IDs from results
            trial_links = soup.select("a[href*='ACTRN']")
            trial_ids = []
            for link in trial_links:
                href = link.get("href", "")
                match = re.search(r'(ACTRN\d{14}[a-z]?)', href, re.IGNORECASE)
                if match:
                    trial_ids.append(match.group(1).upper())

            # Remove duplicates while preserving order
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
            logger.error(f"ANZCTR search error: {e}")
            errors.append(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"ANZCTR parsing error: {e}")
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
        Retrieve a single study by ANZCTR ID.

        Args:
            registry_id: ANZCTR trial ID (e.g., ACTRN12620000001p)

        Returns:
            StandardizedStudy or None if not found
        """
        registry_id = registry_id.strip().upper()

        if not self.validate_id(registry_id):
            logger.warning(f"Invalid ANZCTR ID format: {registry_id}")
            return None

        # Check cache
        cache_key = f"study:{registry_id}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            self._rate_limit_wait()

            # ANZCTR XML export URL
            xml_url = f"{self.base_url}/Trial/Registration/TrialReview.aspx"
            params = {"id": registry_id, "isReview": "true", "outputFormat": "xml"}

            response = requests.get(
                xml_url,
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": "CTGov-Search-Strategies/1.0"}
            )
            response.raise_for_status()

            # Parse XML response
            soup = BeautifulSoup(response.text, "lxml-xml")

            # Extract study data
            study = self._parse_xml_to_study(soup, registry_id)

            if study:
                self._set_cached(cache_key, study)

            return study

        except requests.RequestException as e:
            logger.error(f"ANZCTR fetch error for {registry_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"ANZCTR parse error for {registry_id}: {e}")
            return None

    def _parse_xml_to_study(
        self,
        soup: BeautifulSoup,
        registry_id: str
    ) -> Optional[StandardizedStudy]:
        """Parse ANZCTR XML response to StandardizedStudy."""

        def get_text(tag_name: str) -> str:
            elem = soup.find(tag_name)
            return elem.get_text(strip=True) if elem else ""

        def get_all_text(tag_name: str) -> List[str]:
            elems = soup.find_all(tag_name)
            return [e.get_text(strip=True) for e in elems if e.get_text(strip=True)]

        try:
            study = StandardizedStudy(
                registry_id=registry_id,
                registry_type=RegistryType.ANZCTR,
                url=f"{self.base_url}/Trial/Registration/TrialReview.aspx?id={registry_id}",
            )

            # Titles
            study.title = get_text("scientifictitle") or get_text("publictitle")
            study.brief_title = get_text("publictitle")
            study.scientific_title = get_text("scientifictitle")
            study.acronym = get_text("acronym")

            # Secondary IDs
            secondary_ids = get_all_text("secondaryid")
            study.secondary_ids = secondary_ids

            # Status
            status_text = get_text("recruitmentstatus")
            study.status = self._standardize_status(status_text)

            # Dates
            study.start_date = self._parse_date(get_text("anticipatedstartdate"))
            study.completion_date = self._parse_date(get_text("actualenddate"))
            study.first_posted = self._parse_date(get_text("dateregistered"))
            study.last_updated = self._parse_date(get_text("dateupdated"))

            # Study design
            study.study_type = get_text("studytype")
            study.phase = self._standardize_phase(get_text("phase"))
            study.allocation = get_text("allocation")
            study.intervention_model = get_text("interventionassignment")
            study.masking = get_text("masking")
            study.primary_purpose = get_text("purpose")

            # Enrollment
            enrollment_text = get_text("enrollmenttarget")
            if enrollment_text:
                try:
                    study.enrollment = int(re.sub(r'\D', '', enrollment_text))
                except ValueError:
                    pass
            study.enrollment_type = "Anticipated"

            # Population
            study.min_age = self._parse_age(get_text("agemin"))
            study.max_age = self._parse_age(get_text("agemax"))
            study.sex = get_text("gender") or "All"
            study.healthy_volunteers = "healthy" in get_text("healthyvolunteer").lower()
            study.eligibility_criteria = get_text("eligibilityinclusion") + "\n\nExclusion:\n" + get_text("eligibilityexclusion")

            # Conditions
            conditions = get_all_text("conditioncode1") + get_all_text("conditioncode2")
            study.conditions = list(set(conditions)) if conditions else [get_text("healthcondition")]

            # Interventions
            intervention_texts = get_all_text("intervention")
            study.interventions = [{"name": i, "type": "Other"} for i in intervention_texts]

            # Outcomes
            primary_outcome_text = get_text("primaryoutcome")
            if primary_outcome_text:
                study.primary_outcomes = [{"measure": primary_outcome_text}]

            secondary_outcome_text = get_text("secondaryoutcome")
            if secondary_outcome_text:
                study.secondary_outcomes = [{"measure": secondary_outcome_text}]

            # Sponsor
            study.lead_sponsor = get_text("sponsorname") or get_text("primarysponsor")
            study.sponsor_type = get_text("sponsortype")

            # Countries
            countries = get_all_text("countryofrecruit")
            if not countries:
                countries = get_all_text("country")
            study.countries = list(set(countries)) if countries else ["Australia"]

            # Contact
            study.contact_name = get_text("contactname")
            study.contact_email = get_text("contactemail")
            study.contact_phone = get_text("contactphone")

            # Raw data for debugging
            study.raw_data = {"xml_source": str(soup)[:5000]}

            return study

        except Exception as e:
            logger.error(f"Error parsing ANZCTR XML: {e}")
            return None

    def _map_status_filter(self, status: str) -> str:
        """Map standardized status to ANZCTR-specific filter value."""
        status_map = {
            "recruiting": "Open",
            "active": "Open",
            "completed": "Closed",
            "terminated": "Closed",
            "withdrawn": "Withdrawn",
            "suspended": "Suspended",
            "not_yet_recruiting": "Not yet recruiting",
        }
        return status_map.get(status.lower(), status)


# Convenience function
def create_anzctr_adapter(**kwargs) -> ANZCTRAdapter:
    """Create and return an ANZCTR adapter instance."""
    return ANZCTRAdapter(**kwargs)
