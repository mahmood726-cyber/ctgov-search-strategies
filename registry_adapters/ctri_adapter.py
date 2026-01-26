"""
CTRI (Clinical Trials Registry - India) adapter.

Provides search and retrieval functionality for CTRI trials.
Registry URL: http://ctri.nic.in
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


class CTRIAdapter(BaseRegistryAdapter):
    """
    Adapter for CTRI (Clinical Trials Registry - India).

    CTRI uses a web interface for search and retrieval.
    Trial IDs follow format: CTRI/YYYY/MM/NNNNNN

    Example usage:
        adapter = CTRIAdapter()
        results = adapter.search("diabetes type 2")
        study = adapter.get_study("CTRI/2020/01/000001")
    """

    # CTRI ID pattern: CTRI/YYYY/MM/NNNNNN
    ID_PATTERN = re.compile(r'^CTRI[/]?\d{4}[/]?\d{2}[/]?\d{6}$', re.IGNORECASE)

    def __init__(
        self,
        rate_limit: float = 0.3,  # CTRI can be slow
        timeout: int = 90,
        cache_ttl: int = 3600,
    ):
        super().__init__(
            registry_type=RegistryType.CTRI,
            base_url="http://ctri.nic.in",
            rate_limit=rate_limit,
            timeout=timeout,
            cache_ttl=cache_ttl,
        )

        if requests is None:
            raise ImportError("requests package required: pip install requests")
        if BeautifulSoup is None:
            raise ImportError("beautifulsoup4 package required: pip install beautifulsoup4 lxml")

    def validate_id(self, registry_id: str) -> bool:
        """Validate CTRI trial ID format."""
        # Normalize the ID format
        normalized = registry_id.strip().upper()
        return bool(self.ID_PATTERN.match(normalized))

    def _normalize_id(self, registry_id: str) -> str:
        """Normalize CTRI ID to standard format: CTRI/YYYY/MM/NNNNNN"""
        # Remove any existing slashes and normalize
        cleaned = re.sub(r'[/]', '', registry_id.strip().upper())
        if cleaned.startswith("CTRI") and len(cleaned) >= 16:
            # CTRIYYYY MM NNNNNN -> CTRI/YYYY/MM/NNNNNN
            return f"CTRI/{cleaned[4:8]}/{cleaned[8:10]}/{cleaned[10:]}"
        return registry_id

    def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> SearchResult:
        """
        Search CTRI for clinical trials.

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

            # CTRI search URL
            search_url = f"{self.base_url}/Clinicaltrials/pmaindet2.php"

            # Build POST data for search
            data = {
                "term": query,
                "search_type": "basic",
                "page": page,
                "limit": min(page_size, 50),
            }

            # Apply filters
            if filters:
                if filters.get("status"):
                    data["recruitment_status"] = self._map_status_filter(filters["status"])
                if filters.get("phase"):
                    data["phase"] = filters["phase"]

            response = requests.post(
                search_url,
                data=data,
                timeout=self.timeout,
                headers={
                    "User-Agent": "CTGov-Search-Strategies/1.0",
                    "Content-Type": "application/x-www-form-urlencoded",
                }
            )
            response.raise_for_status()

            # Parse HTML response
            soup = BeautifulSoup(response.text, "lxml")

            # Extract total count
            count_elem = soup.select_one(".total-results, .result-count")
            if count_elem:
                count_text = count_elem.get_text()
                match = re.search(r'(\d+)', count_text.replace(",", ""))
                if match:
                    total_count = int(match.group(1))

            # Extract trial IDs from results
            trial_links = soup.select("a[href*='CTRI']")
            trial_ids = []
            for link in trial_links:
                href = link.get("href", "")
                text = link.get_text(strip=True)

                # Try to extract ID from href or text
                match = re.search(r'(CTRI[/]?\d{4}[/]?\d{2}[/]?\d{6})', href + text, re.IGNORECASE)
                if match:
                    trial_ids.append(self._normalize_id(match.group(1)))

            # Also look for IDs in table cells
            for cell in soup.select("td"):
                text = cell.get_text(strip=True)
                match = re.search(r'(CTRI[/]?\d{4}[/]?\d{2}[/]?\d{6})', text, re.IGNORECASE)
                if match:
                    trial_ids.append(self._normalize_id(match.group(1)))

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
            logger.error(f"CTRI search error: {e}")
            errors.append(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"CTRI parsing error: {e}")
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
        Retrieve a single study by CTRI ID.

        Args:
            registry_id: CTRI trial ID (e.g., CTRI/2020/01/000001)

        Returns:
            StandardizedStudy or None if not found
        """
        registry_id = self._normalize_id(registry_id)

        if not self.validate_id(registry_id):
            logger.warning(f"Invalid CTRI ID format: {registry_id}")
            return None

        # Check cache
        cache_key = f"study:{registry_id}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            self._rate_limit_wait()

            # CTRI detail URL
            detail_url = f"{self.base_url}/Clinicaltrials/showallp.php"
            params = {"mid1": registry_id.replace("/", "")}

            response = requests.get(
                detail_url,
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": "CTGov-Search-Strategies/1.0"}
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
            logger.error(f"CTRI fetch error for {registry_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"CTRI parse error for {registry_id}: {e}")
            return None

    def _parse_html_to_study(
        self,
        soup: BeautifulSoup,
        registry_id: str
    ) -> Optional[StandardizedStudy]:
        """Parse CTRI HTML response to StandardizedStudy."""

        def get_field_value(label: str) -> str:
            """Extract value for a given field label."""
            # CTRI uses table-based layout
            for row in soup.select("tr"):
                cells = row.select("td")
                if len(cells) >= 2:
                    label_text = cells[0].get_text(strip=True).lower()
                    if label.lower() in label_text:
                        return cells[1].get_text(strip=True)

            # Also try definition list format
            for dt in soup.select("dt"):
                if label.lower() in dt.get_text(strip=True).lower():
                    dd = dt.find_next_sibling("dd")
                    if dd:
                        return dd.get_text(strip=True)

            return ""

        try:
            study = StandardizedStudy(
                registry_id=registry_id,
                registry_type=RegistryType.CTRI,
                url=f"{self.base_url}/Clinicaltrials/showallp.php?mid1={registry_id.replace('/', '')}",
            )

            # Titles
            title_elem = soup.select_one("h1, h2, .trial-title")
            if title_elem:
                study.title = title_elem.get_text(strip=True)
            else:
                study.title = get_field_value("Public title") or get_field_value("Scientific title")

            study.brief_title = get_field_value("Public title") or get_field_value("Brief Summary")
            study.scientific_title = get_field_value("Scientific title")
            study.acronym = get_field_value("Acronym")

            # Secondary IDs
            secondary = get_field_value("Secondary ID")
            if secondary:
                study.secondary_ids = [s.strip() for s in secondary.split(";") if s.strip()]

            # Status
            status_text = get_field_value("Recruitment status") or get_field_value("Trial status")
            study.status = self._standardize_status(status_text)

            # Dates
            study.start_date = self._parse_date(get_field_value("Date of first enrollment"))
            study.completion_date = self._parse_date(get_field_value("Date of study completion"))
            study.first_posted = self._parse_date(get_field_value("Date of registration"))
            study.last_updated = self._parse_date(get_field_value("Last modified"))

            # Study design
            study.study_type = get_field_value("Type of trial") or get_field_value("Study type")
            study.phase = self._standardize_phase(get_field_value("Phase of trial") or get_field_value("Phase"))
            study.allocation = get_field_value("Method of allocation")
            study.intervention_model = get_field_value("Method of assignment")
            study.masking = get_field_value("Masking") or get_field_value("Blinding")
            study.primary_purpose = get_field_value("Purpose of trial")

            # Enrollment
            enrollment_text = get_field_value("Sample size") or get_field_value("Target sample size")
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
                study.conditions = [c.strip() for c in re.split(r'[;,]', condition_text) if c.strip()]

            # Interventions
            intervention_text = get_field_value("Intervention") or get_field_value("Treatment")
            if intervention_text:
                # Split by common delimiters
                interventions = re.split(r'[;]|\d+\)', intervention_text)
                study.interventions = [{"name": i.strip(), "type": "Other"} for i in interventions if i.strip()]

            # Outcomes
            primary_outcome = get_field_value("Primary outcome")
            if primary_outcome:
                study.primary_outcomes = [{"measure": primary_outcome}]

            secondary_outcome = get_field_value("Secondary outcome")
            if secondary_outcome:
                study.secondary_outcomes = [{"measure": secondary_outcome}]

            # Sponsor
            study.lead_sponsor = get_field_value("Primary sponsor") or get_field_value("Sponsor")
            study.sponsor_type = get_field_value("Type of sponsor")

            # Countries - CTRI is India-specific
            study.countries = ["India"]

            # Contact
            study.contact_name = get_field_value("Contact person") or get_field_value("Principal investigator")
            study.contact_email = get_field_value("Email")
            study.contact_phone = get_field_value("Phone") or get_field_value("Telephone")

            return study

        except Exception as e:
            logger.error(f"Error parsing CTRI HTML: {e}")
            return None

    def _map_status_filter(self, status: str) -> str:
        """Map standardized status to CTRI-specific filter value."""
        status_map = {
            "recruiting": "Recruiting",
            "active": "Ongoing",
            "completed": "Completed",
            "terminated": "Terminated",
            "withdrawn": "Withdrawn",
            "suspended": "Temporarily Halted",
            "not_yet_recruiting": "Not yet recruiting",
        }
        return status_map.get(status.lower(), status)


# Convenience function
def create_ctri_adapter(**kwargs) -> CTRIAdapter:
    """Create and return a CTRI adapter instance."""
    return CTRIAdapter(**kwargs)
