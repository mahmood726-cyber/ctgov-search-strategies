"""
ChiCTR (Chinese Clinical Trial Registry) adapter.

Provides search and retrieval functionality for ChiCTR trials.
Registry URL: http://www.chictr.org.cn
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


class ChiCTRAdapter(BaseRegistryAdapter):
    """
    Adapter for ChiCTR (Chinese Clinical Trial Registry).

    ChiCTR uses a web interface with English and Chinese versions.
    Trial IDs follow format: ChiCTR2000000000 (ChiCTR + year + serial number)

    Example usage:
        adapter = ChiCTRAdapter()
        results = adapter.search("diabetes mellitus")
        study = adapter.get_study("ChiCTR2000039904")
    """

    # ChiCTR ID pattern: ChiCTR + year + 6 digits (or older formats)
    ID_PATTERN = re.compile(r'^ChiCTR[-]?\d{10,14}$', re.IGNORECASE)

    def __init__(
        self,
        rate_limit: float = 0.3,  # ChiCTR can be slow
        timeout: int = 60,
        cache_ttl: int = 3600,
        use_english: bool = True,
    ):
        super().__init__(
            registry_type=RegistryType.CHICTR,
            base_url="http://www.chictr.org.cn",
            rate_limit=rate_limit,
            timeout=timeout,
            cache_ttl=cache_ttl,
        )
        self.use_english = use_english

        if requests is None:
            raise ImportError("requests package required: pip install requests")
        if BeautifulSoup is None:
            raise ImportError("beautifulsoup4 package required: pip install beautifulsoup4 lxml")

    def validate_id(self, registry_id: str) -> bool:
        """Validate ChiCTR trial ID format."""
        return bool(self.ID_PATTERN.match(registry_id.strip()))

    def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> SearchResult:
        """
        Search ChiCTR for clinical trials.

        Args:
            query: Search query string
            page: Page number (1-indexed)
            page_size: Results per page (max 50)
            filters: Optional filters:
                - status: recruiting, completed, etc.
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

            # ChiCTR search URL (English version)
            lang_suffix = "en" if self.use_english else "cn"
            search_url = f"{self.base_url}/searchprojen.aspx"

            # Build search parameters
            params = {
                "title": query,
                "officialname": "",
                "subjectid": "",
                "secondaryid": "",
                "applession": "",
                "session": "",
                "isalidate": "",
                "registstatus": "",
                "recstatus": "",
                "page": page,
            }

            # Apply filters
            if filters:
                if filters.get("status"):
                    params["recstatus"] = self._map_status_filter(filters["status"])

            response = requests.get(
                search_url,
                params=params,
                timeout=self.timeout,
                headers={
                    "User-Agent": "CTGov-Search-Strategies/1.0",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
            response.raise_for_status()

            # Parse HTML response
            soup = BeautifulSoup(response.text, "lxml")

            # Extract total count
            count_elem = soup.select_one(".total") or soup.select_one(".result-count")
            if count_elem:
                count_text = count_elem.get_text()
                match = re.search(r'(\d+)', count_text.replace(",", ""))
                if match:
                    total_count = int(match.group(1))

            # Extract trial IDs from results table
            trial_links = soup.select("a[href*='ChiCTR']")
            trial_ids = []
            for link in trial_links:
                href = link.get("href", "")
                text = link.get_text(strip=True)

                # Try to extract ID from href or text
                match = re.search(r'(ChiCTR[-]?\d{10,14})', href + text, re.IGNORECASE)
                if match:
                    trial_ids.append(match.group(1))

            # Remove duplicates
            seen = set()
            unique_ids = []
            for tid in trial_ids:
                normalized = tid.upper().replace("-", "")
                if normalized not in seen:
                    seen.add(normalized)
                    unique_ids.append(tid)

            # Fetch study details for each ID (limit to page_size)
            for trial_id in unique_ids[:page_size]:
                study = self.get_study(trial_id)
                if study:
                    studies.append(study)

        except requests.RequestException as e:
            logger.error(f"ChiCTR search error: {e}")
            errors.append(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"ChiCTR parsing error: {e}")
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
        Retrieve a single study by ChiCTR ID.

        Args:
            registry_id: ChiCTR trial ID (e.g., ChiCTR2000039904)

        Returns:
            StandardizedStudy or None if not found
        """
        registry_id = registry_id.strip()

        if not self.validate_id(registry_id):
            logger.warning(f"Invalid ChiCTR ID format: {registry_id}")
            return None

        # Check cache
        cache_key = f"study:{registry_id}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            self._rate_limit_wait()

            # ChiCTR detail URL
            detail_url = f"{self.base_url}/showprojen.aspx"
            params = {"proj": registry_id}

            response = requests.get(
                detail_url,
                params=params,
                timeout=self.timeout,
                headers={
                    "User-Agent": "CTGov-Search-Strategies/1.0",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
            response.raise_for_status()

            # Parse HTML response
            soup = BeautifulSoup(response.text, "lxml")

            # Extract study data
            study = self._parse_html_to_study(soup, registry_id)

            if study:
                self._set_cached(cache_key, study)

            return study

        except requests.RequestException as e:
            logger.error(f"ChiCTR fetch error for {registry_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"ChiCTR parse error for {registry_id}: {e}")
            return None

    def _parse_html_to_study(
        self,
        soup: BeautifulSoup,
        registry_id: str
    ) -> Optional[StandardizedStudy]:
        """Parse ChiCTR HTML response to StandardizedStudy."""

        def get_field_value(label: str) -> str:
            """Extract value for a given field label."""
            # Look for table rows with label
            for row in soup.select("tr"):
                cells = row.select("td")
                if len(cells) >= 2:
                    label_text = cells[0].get_text(strip=True).lower()
                    if label.lower() in label_text:
                        return cells[1].get_text(strip=True)

            # Also try div-based layout
            for div in soup.select(".field-label, .label"):
                if label.lower() in div.get_text(strip=True).lower():
                    value_div = div.find_next_sibling()
                    if value_div:
                        return value_div.get_text(strip=True)

            return ""

        try:
            study = StandardizedStudy(
                registry_id=registry_id.upper(),
                registry_type=RegistryType.CHICTR,
                url=f"{self.base_url}/showprojen.aspx?proj={registry_id}",
            )

            # Titles
            title_elem = soup.select_one("h2, .study-title, .title")
            if title_elem:
                study.title = title_elem.get_text(strip=True)
            else:
                study.title = get_field_value("Public title") or get_field_value("Scientific title")

            study.brief_title = get_field_value("Public title")
            study.scientific_title = get_field_value("Scientific title")

            # Registration number and secondary IDs
            secondary = get_field_value("Secondary ID")
            if secondary:
                study.secondary_ids = [s.strip() for s in secondary.split(";") if s.strip()]

            # Status
            status_text = get_field_value("Recruitment status") or get_field_value("Status")
            study.status = self._standardize_status(status_text)

            # Dates
            study.start_date = self._parse_date(get_field_value("Date of first enrollment"))
            study.completion_date = self._parse_date(get_field_value("Study completion date"))
            study.first_posted = self._parse_date(get_field_value("Date of registration"))
            study.last_updated = self._parse_date(get_field_value("Date of last update"))

            # Study design
            study.study_type = get_field_value("Study type") or "Interventional"
            study.phase = self._standardize_phase(get_field_value("Study phase"))
            study.allocation = get_field_value("Allocation")
            study.intervention_model = get_field_value("Intervention assignment")
            study.masking = get_field_value("Masking") or get_field_value("Blinding")
            study.primary_purpose = get_field_value("Primary purpose")

            # Enrollment
            enrollment_text = get_field_value("Target sample size") or get_field_value("Enrollment")
            if enrollment_text:
                try:
                    study.enrollment = int(re.sub(r'\D', '', enrollment_text))
                except ValueError:
                    pass

            # Population
            study.min_age = self._parse_age(get_field_value("Minimum age"))
            study.max_age = self._parse_age(get_field_value("Maximum age"))
            study.sex = get_field_value("Gender") or "All"

            inclusion = get_field_value("Inclusion criteria")
            exclusion = get_field_value("Exclusion criteria")
            study.eligibility_criteria = f"Inclusion:\n{inclusion}\n\nExclusion:\n{exclusion}"

            # Conditions
            condition_text = get_field_value("Health condition") or get_field_value("Condition")
            if condition_text:
                study.conditions = [c.strip() for c in condition_text.split(";") if c.strip()]

            # Interventions
            intervention_text = get_field_value("Intervention") or get_field_value("Interventions")
            if intervention_text:
                study.interventions = [{"name": intervention_text, "type": "Other"}]

            # Outcomes
            primary_outcome = get_field_value("Primary outcome")
            if primary_outcome:
                study.primary_outcomes = [{"measure": primary_outcome}]

            secondary_outcome = get_field_value("Secondary outcome")
            if secondary_outcome:
                study.secondary_outcomes = [{"measure": secondary_outcome}]

            # Sponsor
            study.lead_sponsor = get_field_value("Primary sponsor") or get_field_value("Sponsor")

            # Countries
            study.countries = ["China"]

            # Contact
            study.contact_name = get_field_value("Contact name") or get_field_value("Principal investigator")
            study.contact_email = get_field_value("Contact email")
            study.contact_phone = get_field_value("Contact phone")

            return study

        except Exception as e:
            logger.error(f"Error parsing ChiCTR HTML: {e}")
            return None

    def _map_status_filter(self, status: str) -> str:
        """Map standardized status to ChiCTR-specific filter value."""
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
def create_chictr_adapter(**kwargs) -> ChiCTRAdapter:
    """Create and return a ChiCTR adapter instance."""
    return ChiCTRAdapter(**kwargs)
