"""
Base adapter for clinical trial registry searches.

Provides abstract interface for implementing registry-specific adapters.
All adapters should inherit from BaseRegistryAdapter and implement the
required methods.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RegistryType(Enum):
    """Enumeration of supported trial registries."""
    CTGOV = "clinicaltrials.gov"
    ANZCTR = "anzctr.org.au"
    CHICTR = "chictr.org.cn"
    DRKS = "drks.de"
    CTRI = "ctri.nic.in"
    JRCT = "jrct.niph.go.jp"
    ICTRP = "who.int/ictrp"
    EUCTR = "clinicaltrialsregister.eu"
    ISRCTN = "isrctn.com"


class StudyStatus(Enum):
    """Standardized study status across registries."""
    RECRUITING = "recruiting"
    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    WITHDRAWN = "withdrawn"
    SUSPENDED = "suspended"
    NOT_YET_RECRUITING = "not_yet_recruiting"
    ENROLLING_BY_INVITATION = "enrolling_by_invitation"
    UNKNOWN = "unknown"


class StudyPhase(Enum):
    """Standardized study phases across registries."""
    EARLY_PHASE_1 = "early_phase_1"
    PHASE_1 = "phase_1"
    PHASE_1_2 = "phase_1_2"
    PHASE_2 = "phase_2"
    PHASE_2_3 = "phase_2_3"
    PHASE_3 = "phase_3"
    PHASE_4 = "phase_4"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


@dataclass
class StandardizedStudy:
    """
    Standardized study representation across all registries.

    Maps registry-specific fields to common schema for unified
    analysis and export.
    """
    # Core identifiers
    registry_id: str  # Native ID (e.g., NCT12345678, ACTRN12620000001p)
    registry_type: RegistryType
    secondary_ids: List[str] = field(default_factory=list)

    # Title and description
    title: str = ""
    brief_title: str = ""
    acronym: str = ""
    scientific_title: str = ""

    # Status and dates
    status: StudyStatus = StudyStatus.UNKNOWN
    status_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    completion_date: Optional[datetime] = None
    first_posted: Optional[datetime] = None
    last_updated: Optional[datetime] = None

    # Study design
    study_type: str = ""  # Interventional, Observational, etc.
    phase: StudyPhase = StudyPhase.UNKNOWN
    allocation: str = ""  # Randomized, Non-randomized
    intervention_model: str = ""  # Parallel, Crossover, etc.
    masking: str = ""  # Open, Single, Double, Triple, Quadruple
    primary_purpose: str = ""  # Treatment, Prevention, Diagnostic, etc.

    # Population
    enrollment: Optional[int] = None
    enrollment_type: str = ""  # Actual, Anticipated
    min_age: str = ""
    max_age: str = ""
    sex: str = ""  # All, Female, Male
    healthy_volunteers: bool = False
    eligibility_criteria: str = ""

    # Conditions and interventions
    conditions: List[str] = field(default_factory=list)
    condition_mesh_terms: List[str] = field(default_factory=list)
    interventions: List[Dict[str, str]] = field(default_factory=list)
    intervention_mesh_terms: List[str] = field(default_factory=list)

    # Outcomes
    primary_outcomes: List[Dict[str, str]] = field(default_factory=list)
    secondary_outcomes: List[Dict[str, str]] = field(default_factory=list)

    # Sponsors and collaborators
    lead_sponsor: str = ""
    sponsor_type: str = ""  # Industry, Academic, Government, etc.
    collaborators: List[str] = field(default_factory=list)

    # Locations
    countries: List[str] = field(default_factory=list)
    locations: List[Dict[str, str]] = field(default_factory=list)

    # Contact
    contact_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""

    # URLs and references
    url: str = ""
    results_url: str = ""
    publications: List[str] = field(default_factory=list)

    # Raw data for debugging
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "registry_id": self.registry_id,
            "registry_type": self.registry_type.value,
            "secondary_ids": self.secondary_ids,
            "title": self.title,
            "brief_title": self.brief_title,
            "acronym": self.acronym,
            "scientific_title": self.scientific_title,
            "status": self.status.value,
            "status_date": self.status_date.isoformat() if self.status_date else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "completion_date": self.completion_date.isoformat() if self.completion_date else None,
            "first_posted": self.first_posted.isoformat() if self.first_posted else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "study_type": self.study_type,
            "phase": self.phase.value,
            "allocation": self.allocation,
            "intervention_model": self.intervention_model,
            "masking": self.masking,
            "primary_purpose": self.primary_purpose,
            "enrollment": self.enrollment,
            "enrollment_type": self.enrollment_type,
            "min_age": self.min_age,
            "max_age": self.max_age,
            "sex": self.sex,
            "healthy_volunteers": self.healthy_volunteers,
            "eligibility_criteria": self.eligibility_criteria,
            "conditions": self.conditions,
            "condition_mesh_terms": self.condition_mesh_terms,
            "interventions": self.interventions,
            "intervention_mesh_terms": self.intervention_mesh_terms,
            "primary_outcomes": self.primary_outcomes,
            "secondary_outcomes": self.secondary_outcomes,
            "lead_sponsor": self.lead_sponsor,
            "sponsor_type": self.sponsor_type,
            "collaborators": self.collaborators,
            "countries": self.countries,
            "locations": self.locations,
            "contact_name": self.contact_name,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "url": self.url,
            "results_url": self.results_url,
            "publications": self.publications,
        }

    def get_dedup_key(self) -> str:
        """Generate deduplication key for cross-registry matching."""
        # Use combination of registry ID and standardized title
        import hashlib
        title_normalized = self.title.lower().strip()
        key_string = f"{self.registry_id}|{title_normalized}"
        return hashlib.md5(key_string.encode()).hexdigest()[:16]


@dataclass
class SearchResult:
    """Result from a registry search."""
    studies: List[StandardizedStudy]
    total_count: int
    query: str
    registry: RegistryType
    search_time: float  # seconds
    page: int = 1
    page_size: int = 100
    has_more: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "studies": [s.to_dict() for s in self.studies],
            "total_count": self.total_count,
            "query": self.query,
            "registry": self.registry.value,
            "search_time": self.search_time,
            "page": self.page,
            "page_size": self.page_size,
            "has_more": self.has_more,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class BaseRegistryAdapter(ABC):
    """
    Abstract base class for clinical trial registry adapters.

    Subclasses must implement search() and get_study() methods
    with registry-specific logic. The base class provides common
    functionality for rate limiting, caching, and standardization.
    """

    def __init__(
        self,
        registry_type: RegistryType,
        base_url: str,
        rate_limit: float = 1.0,  # requests per second
        timeout: int = 30,
        cache_ttl: int = 3600,  # cache time-to-live in seconds
    ):
        self.registry_type = registry_type
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self._last_request_time = 0.0
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}

    @property
    def name(self) -> str:
        """Human-readable registry name."""
        return self.registry_type.value

    def _rate_limit_wait(self) -> None:
        """Wait to respect rate limiting."""
        import time
        elapsed = time.time() - self._last_request_time
        wait_time = (1.0 / self.rate_limit) - elapsed
        if wait_time > 0:
            time.sleep(wait_time)
        self._last_request_time = time.time()

    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        import time
        if key in self._cache:
            timestamp = self._cache_timestamps.get(key, 0)
            if time.time() - timestamp < self.cache_ttl:
                return self._cache[key]
            else:
                # Expired, remove from cache
                del self._cache[key]
                del self._cache_timestamps[key]
        return None

    def _set_cached(self, key: str, value: Any) -> None:
        """Set cached value with timestamp."""
        import time
        self._cache[key] = value
        self._cache_timestamps[key] = time.time()

    def clear_cache(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
        self._cache_timestamps.clear()

    @abstractmethod
    def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> SearchResult:
        """
        Search the registry for clinical trials.

        Args:
            query: Search query string
            page: Page number (1-indexed)
            page_size: Number of results per page
            filters: Optional filters (status, phase, dates, etc.)

        Returns:
            SearchResult containing matched studies
        """
        pass

    @abstractmethod
    def get_study(self, registry_id: str) -> Optional[StandardizedStudy]:
        """
        Retrieve a single study by registry ID.

        Args:
            registry_id: The registry-specific trial ID

        Returns:
            StandardizedStudy or None if not found
        """
        pass

    @abstractmethod
    def validate_id(self, registry_id: str) -> bool:
        """
        Validate that an ID matches the expected format for this registry.

        Args:
            registry_id: The ID to validate

        Returns:
            True if valid format, False otherwise
        """
        pass

    def batch_get_studies(
        self,
        registry_ids: List[str],
        skip_invalid: bool = True,
    ) -> List[StandardizedStudy]:
        """
        Retrieve multiple studies by their IDs.

        Args:
            registry_ids: List of registry-specific trial IDs
            skip_invalid: If True, skip invalid IDs; if False, raise error

        Returns:
            List of StandardizedStudy objects
        """
        studies = []
        for registry_id in registry_ids:
            if not self.validate_id(registry_id):
                if skip_invalid:
                    logger.warning(f"Skipping invalid ID: {registry_id}")
                    continue
                else:
                    raise ValueError(f"Invalid registry ID: {registry_id}")

            study = self.get_study(registry_id)
            if study:
                studies.append(study)
            else:
                logger.warning(f"Study not found: {registry_id}")

        return studies

    def search_all(
        self,
        query: str,
        max_results: int = 1000,
        filters: Optional[Dict[str, Any]] = None,
    ) -> SearchResult:
        """
        Search and retrieve all results (with pagination).

        Args:
            query: Search query string
            max_results: Maximum total results to retrieve
            filters: Optional filters

        Returns:
            SearchResult with all retrieved studies
        """
        all_studies = []
        page = 1
        page_size = 100
        total_time = 0.0
        total_count = 0
        errors = []
        warnings = []

        while len(all_studies) < max_results:
            result = self.search(query, page=page, page_size=page_size, filters=filters)
            all_studies.extend(result.studies)
            total_time += result.search_time
            total_count = result.total_count
            errors.extend(result.errors)
            warnings.extend(result.warnings)

            if not result.has_more or len(result.studies) == 0:
                break

            page += 1

        # Trim to max_results if we got more
        if len(all_studies) > max_results:
            all_studies = all_studies[:max_results]

        return SearchResult(
            studies=all_studies,
            total_count=total_count,
            query=query,
            registry=self.registry_type,
            search_time=total_time,
            page=1,
            page_size=len(all_studies),
            has_more=len(all_studies) < total_count,
            errors=errors,
            warnings=warnings,
        )

    # Standardization helper methods

    def _standardize_status(self, status: str) -> StudyStatus:
        """Convert registry-specific status to standardized status."""
        status_lower = status.lower().strip()

        status_map = {
            # Recruiting variants
            "recruiting": StudyStatus.RECRUITING,
            "open": StudyStatus.RECRUITING,
            "open to recruitment": StudyStatus.RECRUITING,
            "currently recruiting": StudyStatus.RECRUITING,
            "actively recruiting": StudyStatus.RECRUITING,

            # Active variants
            "active": StudyStatus.ACTIVE,
            "active, not recruiting": StudyStatus.ACTIVE,
            "ongoing": StudyStatus.ACTIVE,
            "in progress": StudyStatus.ACTIVE,

            # Completed variants
            "completed": StudyStatus.COMPLETED,
            "finished": StudyStatus.COMPLETED,
            "closed": StudyStatus.COMPLETED,
            "ended": StudyStatus.COMPLETED,

            # Terminated variants
            "terminated": StudyStatus.TERMINATED,
            "stopped": StudyStatus.TERMINATED,
            "halted": StudyStatus.TERMINATED,

            # Withdrawn variants
            "withdrawn": StudyStatus.WITHDRAWN,
            "cancelled": StudyStatus.WITHDRAWN,

            # Suspended variants
            "suspended": StudyStatus.SUSPENDED,
            "temporarily closed": StudyStatus.SUSPENDED,

            # Not yet recruiting variants
            "not yet recruiting": StudyStatus.NOT_YET_RECRUITING,
            "pending": StudyStatus.NOT_YET_RECRUITING,
            "not yet open": StudyStatus.NOT_YET_RECRUITING,
            "approved": StudyStatus.NOT_YET_RECRUITING,

            # Enrolling by invitation
            "enrolling by invitation": StudyStatus.ENROLLING_BY_INVITATION,
            "invitation only": StudyStatus.ENROLLING_BY_INVITATION,
        }

        return status_map.get(status_lower, StudyStatus.UNKNOWN)

    def _standardize_phase(self, phase: str) -> StudyPhase:
        """Convert registry-specific phase to standardized phase."""
        phase_lower = phase.lower().strip()

        # Handle various phase formats
        if "early" in phase_lower or "0" in phase_lower:
            return StudyPhase.EARLY_PHASE_1
        elif "1/2" in phase_lower or "1-2" in phase_lower or "i/ii" in phase_lower:
            return StudyPhase.PHASE_1_2
        elif "2/3" in phase_lower or "2-3" in phase_lower or "ii/iii" in phase_lower:
            return StudyPhase.PHASE_2_3
        elif "1" in phase_lower or "i" in phase_lower:
            return StudyPhase.PHASE_1
        elif "2" in phase_lower or "ii" in phase_lower:
            return StudyPhase.PHASE_2
        elif "3" in phase_lower or "iii" in phase_lower:
            return StudyPhase.PHASE_3
        elif "4" in phase_lower or "iv" in phase_lower:
            return StudyPhase.PHASE_4
        elif "n/a" in phase_lower or "not applicable" in phase_lower:
            return StudyPhase.NOT_APPLICABLE
        else:
            return StudyPhase.UNKNOWN

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object."""
        if not date_str:
            return None

        # Common date formats across registries
        formats = [
            "%Y-%m-%d",
            "%Y-%m",
            "%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%B %d, %Y",
            "%d %B %Y",
            "%Y%m%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None

    def _parse_age(self, age_str: str) -> str:
        """Standardize age string format."""
        if not age_str:
            return ""

        age_str = age_str.strip().lower()

        # Handle common formats
        if "year" in age_str:
            # Extract number
            import re
            match = re.search(r'(\d+)', age_str)
            if match:
                return f"{match.group(1)} Years"
        elif "month" in age_str:
            import re
            match = re.search(r'(\d+)', age_str)
            if match:
                return f"{match.group(1)} Months"
        elif "no limit" in age_str or "none" in age_str:
            return "No limit"

        return age_str.title()
