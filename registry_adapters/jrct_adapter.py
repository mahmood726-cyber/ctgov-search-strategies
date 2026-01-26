"""
jRCT (Japan Registry of Clinical Trials) adapter.

Provides search and retrieval functionality for jRCT trials.
Registry URL: https://jrct.niph.go.jp
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


class JRCTAdapter(BaseRegistryAdapter):
    """
    Adapter for jRCT (Japan Registry of Clinical Trials).

    jRCT provides both Japanese and English interfaces.
    Trial IDs follow format: jRCT1234567890 or jRCTs012345678901

    Example usage:
        adapter = JRCTAdapter()
        results = adapter.search("cancer")
        study = adapter.get_study("jRCT1234567890")
    """

    # jRCT ID patterns
    ID_PATTERN = re.compile(r'^jRCT[s]?\d{10,12}$', re.IGNORECASE)

    def __init__(
        self,
        rate_limit: float = 0.5,
        timeout: int = 60,
        cache_ttl: int = 3600,
        use_english: bool = True,
    ):
        super().__init__(
            registry_type=RegistryType.JRCT,
            base_url="https://jrct.niph.go.jp",
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
        """Validate jRCT trial ID format."""
        return bool(self.ID_PATTERN.match(registry_id.strip()))

    def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> SearchResult:
        """
        Search jRCT for clinical trials.

        Args:
            query: Search query string
            page: Page number (1-indexed)
            page_size: Results per page (max 100)
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

            # jRCT search URL (English version)
            lang = "en" if self.use_english else "ja"
            search_url = f"{self.base_url}/{lang}-search"

            # Build search parameters
            params = {
                "keyword": query,
                "page": page,
                "size": min(page_size, 100),
            }

            # Apply filters
            if filters:
                if filters.get("status"):
                    params["recruitment_status"] = self._map_status_filter(filters["status"])
                if filters.get("phase"):
                    params["phase"] = filters["phase"]

            response = requests.get(
                search_url,
                params=params,
                timeout=self.timeout,
                headers={
                    "User-Agent": "CTGov-Search-Strategies/1.0",
                    "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
                }
            )
            response.raise_for_status()

            # Parse HTML response
            soup = BeautifulSoup(response.text, "lxml")

            # Extract total count
            count_elem = soup.select_one(".total-count, .result-count, .search-result-count")
            if count_elem:
                count_text = count_elem.get_text()
                match = re.search(r'(\d+)', count_text.replace(",", ""))
                if match:
                    total_count = int(match.group(1))

            # Extract trial IDs from results
            trial_links = soup.select("a[href*='jRCT']")
            trial_ids = []
            for link in trial_links:
                href = link.get("href", "")
                text = link.get_text(strip=True)

                # Try to extract ID from href or text
                match = re.search(r'(jRCT[s]?\d{10,12})', href + text, re.IGNORECASE)
                if match:
                    trial_ids.append(match.group(1))

            # Also look for IDs in table cells
            for cell in soup.select("td"):
                text = cell.get_text(strip=True)
                match = re.search(r'(jRCT[s]?\d{10,12})', text, re.IGNORECASE)
                if match:
                    trial_ids.append(match.group(1))

            # Remove duplicates
            seen = set()
            unique_ids = []
            for tid in trial_ids:
                normalized = tid.lower()
                if normalized not in seen:
                    seen.add(normalized)
                    unique_ids.append(tid)

            # Fetch study details for each ID
            for trial_id in unique_ids[:page_size]:
                study = self.get_study(trial_id)
                if study:
                    studies.append(study)

        except requests.RequestException as e:
            logger.error(f"jRCT search error: {e}")
            errors.append(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"jRCT parsing error: {e}")
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
        Retrieve a single study by jRCT ID.

        Args:
            registry_id: jRCT trial ID (e.g., jRCT1234567890)

        Returns:
            StandardizedStudy or None if not found
        """
        registry_id = registry_id.strip()

        if not self.validate_id(registry_id):
            logger.warning(f"Invalid jRCT ID format: {registry_id}")
            return None

        # Check cache
        cache_key = f"study:{registry_id}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            self._rate_limit_wait()

            # jRCT detail URL
            lang = "en" if self.use_english else "ja"
            detail_url = f"{self.base_url}/{lang}-detail/{registry_id}"

            response = requests.get(
                detail_url,
                timeout=self.timeout,
                headers={
                    "User-Agent": "CTGov-Search-Strategies/1.0",
                    "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
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
            logger.error(f"jRCT fetch error for {registry_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"jRCT parse error for {registry_id}: {e}")
            return None

    def _parse_html_to_study(
        self,
        soup: BeautifulSoup,
        registry_id: str
    ) -> Optional[StandardizedStudy]:
        """Parse jRCT HTML response to StandardizedStudy."""

        def get_field_value(label: str) -> str:
            """Extract value for a given field label."""
            # jRCT uses definition list format
            for dt in soup.select("dt"):
                if label.lower() in dt.get_text(strip=True).lower():
                    dd = dt.find_next_sibling("dd")
                    if dd:
                        return dd.get_text(strip=True)

            # Also try table format
            for row in soup.select("tr"):
                cells = row.select("th, td")
                if len(cells) >= 2:
                    label_text = cells[0].get_text(strip=True).lower()
                    if label.lower() in label_text:
                        return cells[1].get_text(strip=True)

            return ""

        def get_all_field_values(label: str) -> List[str]:
            """Extract all values for fields matching label."""
            values = []
            for dt in soup.select("dt"):
                if label.lower() in dt.get_text(strip=True).lower():
                    dd = dt.find_next_sibling("dd")
                    if dd:
                        values.append(dd.get_text(strip=True))
            return values

        try:
            study = StandardizedStudy(
                registry_id=registry_id,
                registry_type=RegistryType.JRCT,
                url=f"{self.base_url}/en-detail/{registry_id}",
            )

            # Titles
            title_elem = soup.select_one("h1, h2, .trial-title")
            if title_elem:
                study.title = title_elem.get_text(strip=True)
            else:
                study.title = get_field_value("Title") or get_field_value("Scientific title")

            study.brief_title = get_field_value("Brief title") or get_field_value("Public title")
            study.scientific_title = get_field_value("Scientific title")
            study.acronym = get_field_value("Acronym")

            # Secondary IDs
            secondary = get_field_value("Secondary ID") or get_field_value("Other ID")
            if secondary:
                study.secondary_ids = [s.strip() for s in secondary.split(";") if s.strip()]

            # Status
            status_text = get_field_value("Recruitment status") or get_field_value("Overall status")
            study.status = self._standardize_status(status_text)

            # Dates
            study.start_date = self._parse_date(get_field_value("Study start date") or get_field_value("Date of first enrollment"))
            study.completion_date = self._parse_date(get_field_value("Completion date") or get_field_value("Target end date"))
            study.first_posted = self._parse_date(get_field_value("Date of registration") or get_field_value("First posted"))
            study.last_updated = self._parse_date(get_field_value("Last update") or get_field_value("Last modified"))

            # Study design
            study.study_type = get_field_value("Study type") or get_field_value("Type of trial")
            study.phase = self._standardize_phase(get_field_value("Phase") or get_field_value("Study phase"))
            study.allocation = get_field_value("Allocation") or get_field_value("Method of allocation")
            study.intervention_model = get_field_value("Intervention model") or get_field_value("Study design")
            study.masking = get_field_value("Masking") or get_field_value("Blinding")
            study.primary_purpose = get_field_value("Primary purpose") or get_field_value("Purpose")

            # Enrollment
            enrollment_text = get_field_value("Target sample size") or get_field_value("Enrollment")
            if enrollment_text:
                try:
                    study.enrollment = int(re.sub(r'\D', '', enrollment_text))
                except ValueError:
                    pass

            # Population
            study.min_age = self._parse_age(get_field_value("Minimum age") or get_field_value("Age minimum"))
            study.max_age = self._parse_age(get_field_value("Maximum age") or get_field_value("Age maximum"))
            study.sex = get_field_value("Gender") or get_field_value("Sex") or "All"

            inclusion = get_field_value("Inclusion criteria") or get_field_value("Key inclusion")
            exclusion = get_field_value("Exclusion criteria") or get_field_value("Key exclusion")
            study.eligibility_criteria = f"Inclusion:\n{inclusion}\n\nExclusion:\n{exclusion}"

            # Conditions
            condition_text = get_field_value("Health condition") or get_field_value("Target disease")
            if condition_text:
                study.conditions = [c.strip() for c in re.split(r'[;,]', condition_text) if c.strip()]

            # Interventions
            intervention_texts = get_all_field_values("Intervention") or get_all_field_values("Treatment")
            if intervention_texts:
                study.interventions = [{"name": i, "type": "Other"} for i in intervention_texts]
            else:
                single_intervention = get_field_value("Intervention")
                if single_intervention:
                    study.interventions = [{"name": single_intervention, "type": "Other"}]

            # Outcomes
            primary_outcome = get_field_value("Primary outcome") or get_field_value("Primary endpoint")
            if primary_outcome:
                study.primary_outcomes = [{"measure": primary_outcome}]

            secondary_outcome = get_field_value("Secondary outcome") or get_field_value("Secondary endpoint")
            if secondary_outcome:
                study.secondary_outcomes = [{"measure": secondary_outcome}]

            # Sponsor
            study.lead_sponsor = get_field_value("Sponsor") or get_field_value("Research implementing agency")
            study.sponsor_type = get_field_value("Sponsor type") or get_field_value("Type of sponsor")

            # Collaborators
            collaborators = get_field_value("Collaborators") or get_field_value("Cooperative research institutions")
            if collaborators:
                study.collaborators = [c.strip() for c in collaborators.split(";") if c.strip()]

            # Countries - jRCT is Japan-specific
            study.countries = ["Japan"]

            # Contact
            study.contact_name = get_field_value("Contact person") or get_field_value("Research responsible person")
            study.contact_email = get_field_value("Email") or get_field_value("Contact email")
            study.contact_phone = get_field_value("Phone") or get_field_value("Contact phone")

            return study

        except Exception as e:
            logger.error(f"Error parsing jRCT HTML: {e}")
            return None

    def _map_status_filter(self, status: str) -> str:
        """Map standardized status to jRCT-specific filter value."""
        status_map = {
            "recruiting": "Recruiting",
            "active": "Ongoing",
            "completed": "Complete",
            "terminated": "Terminated",
            "withdrawn": "Withdrawn",
            "suspended": "Suspended",
            "not_yet_recruiting": "Not yet recruiting",
        }
        return status_map.get(status.lower(), status)


# Convenience function
def create_jrct_adapter(**kwargs) -> JRCTAdapter:
    """Create and return a jRCT adapter instance."""
    return JRCTAdapter(**kwargs)
