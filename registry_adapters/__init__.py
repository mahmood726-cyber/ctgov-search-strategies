"""
Registry Adapters Package

Provides a unified interface for searching multiple clinical trial registries.
Supports:
- ANZCTR (Australian New Zealand Clinical Trials Registry)
- ChiCTR (Chinese Clinical Trial Registry)
- DRKS (German Clinical Trials Register)
- CTRI (Clinical Trials Registry - India)
- jRCT (Japan Registry of Clinical Trials)

Example usage:
    from registry_adapters import UnifiedRegistrySearch, RegistryType

    # Search a single registry
    search = UnifiedRegistrySearch()
    results = search.search("diabetes", registries=[RegistryType.ANZCTR])

    # Search all registries
    all_results = search.search_all_registries("diabetes")

    # Get a specific study
    study = search.get_study("ACTRN12620000001p")
"""

from typing import Dict, List, Optional, Set, Any
import logging
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from .base_adapter import (
    BaseRegistryAdapter,
    RegistryType,
    StandardizedStudy,
    SearchResult,
    StudyStatus,
    StudyPhase,
)

# Import adapters (lazy loading to handle missing dependencies)
_adapters_loaded = False
_available_adapters: Dict[RegistryType, type] = {}


def _load_adapters():
    """Lazy load adapters to handle missing dependencies gracefully."""
    global _adapters_loaded, _available_adapters

    if _adapters_loaded:
        return

    try:
        from .anzctr_adapter import ANZCTRAdapter
        _available_adapters[RegistryType.ANZCTR] = ANZCTRAdapter
    except ImportError as e:
        logging.warning(f"ANZCTR adapter not available: {e}")

    try:
        from .chictr_adapter import ChiCTRAdapter
        _available_adapters[RegistryType.CHICTR] = ChiCTRAdapter
    except ImportError as e:
        logging.warning(f"ChiCTR adapter not available: {e}")

    try:
        from .drks_adapter import DRKSAdapter
        _available_adapters[RegistryType.DRKS] = DRKSAdapter
    except ImportError as e:
        logging.warning(f"DRKS adapter not available: {e}")

    try:
        from .ctri_adapter import CTRIAdapter
        _available_adapters[RegistryType.CTRI] = CTRIAdapter
    except ImportError as e:
        logging.warning(f"CTRI adapter not available: {e}")

    try:
        from .jrct_adapter import JRCTAdapter
        _available_adapters[RegistryType.JRCT] = JRCTAdapter
    except ImportError as e:
        logging.warning(f"jRCT adapter not available: {e}")

    _adapters_loaded = True


logger = logging.getLogger(__name__)


@dataclass
class UnifiedSearchResult:
    """
    Combined results from multiple registry searches.
    """
    studies: List[StandardizedStudy] = field(default_factory=list)
    total_count: int = 0
    query: str = ""
    registries_searched: List[RegistryType] = field(default_factory=list)
    registry_results: Dict[RegistryType, SearchResult] = field(default_factory=dict)
    search_time: float = 0.0
    errors: Dict[RegistryType, List[str]] = field(default_factory=dict)
    warnings: Dict[RegistryType, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "studies": [s.to_dict() for s in self.studies],
            "total_count": self.total_count,
            "query": self.query,
            "registries_searched": [r.value for r in self.registries_searched],
            "registry_counts": {r.value: res.total_count for r, res in self.registry_results.items()},
            "search_time": self.search_time,
            "errors": {r.value: e for r, e in self.errors.items()},
            "warnings": {r.value: w for r, w in self.warnings.items()},
        }

    def get_dedup_studies(self) -> List[StandardizedStudy]:
        """Return deduplicated studies based on dedup_key."""
        seen_keys: Set[str] = set()
        unique_studies = []
        for study in self.studies:
            key = study.get_dedup_key()
            if key not in seen_keys:
                seen_keys.add(key)
                unique_studies.append(study)
        return unique_studies


class UnifiedRegistrySearch:
    """
    Unified interface for searching multiple clinical trial registries.

    Supports parallel searching across registries with result aggregation
    and deduplication.

    Example:
        search = UnifiedRegistrySearch()

        # Search specific registries
        results = search.search(
            "diabetes type 2",
            registries=[RegistryType.ANZCTR, RegistryType.DRKS],
            max_per_registry=100
        )

        # Search all available registries
        all_results = search.search_all_registries("cancer")

        # Get a study by ID (auto-detects registry)
        study = search.get_study("ACTRN12620000001p")
    """

    # ID patterns for auto-detection
    ID_PATTERNS = {
        RegistryType.ANZCTR: r'^ACTRN\d{14}[a-z]?$',
        RegistryType.CHICTR: r'^ChiCTR[-]?\d{10,14}$',
        RegistryType.DRKS: r'^DRKS\d{8}$',
        RegistryType.CTRI: r'^CTRI[/]?\d{4}[/]?\d{2}[/]?\d{6}$',
        RegistryType.JRCT: r'^jRCT[s]?\d{10,12}$',
    }

    def __init__(
        self,
        max_workers: int = 5,
        default_timeout: int = 60,
        default_rate_limit: float = 0.5,
    ):
        """
        Initialize unified search.

        Args:
            max_workers: Maximum parallel threads for registry searches
            default_timeout: Default timeout for API requests (seconds)
            default_rate_limit: Default rate limit (requests per second)
        """
        _load_adapters()

        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self.default_rate_limit = default_rate_limit
        self._adapters: Dict[RegistryType, BaseRegistryAdapter] = {}

    def get_available_registries(self) -> List[RegistryType]:
        """Return list of available registry types."""
        return list(_available_adapters.keys())

    def _get_adapter(self, registry_type: RegistryType) -> Optional[BaseRegistryAdapter]:
        """Get or create adapter for registry type."""
        if registry_type not in self._adapters:
            adapter_class = _available_adapters.get(registry_type)
            if adapter_class:
                try:
                    self._adapters[registry_type] = adapter_class(
                        timeout=self.default_timeout,
                        rate_limit=self.default_rate_limit,
                    )
                except Exception as e:
                    logger.error(f"Failed to create adapter for {registry_type}: {e}")
                    return None
        return self._adapters.get(registry_type)

    def detect_registry(self, registry_id: str) -> Optional[RegistryType]:
        """
        Auto-detect registry type from ID format.

        Args:
            registry_id: Trial ID to identify

        Returns:
            RegistryType if detected, None otherwise
        """
        import re
        registry_id = registry_id.strip()

        for registry_type, pattern in self.ID_PATTERNS.items():
            if re.match(pattern, registry_id, re.IGNORECASE):
                return registry_type

        return None

    def get_study(
        self,
        registry_id: str,
        registry_type: Optional[RegistryType] = None,
    ) -> Optional[StandardizedStudy]:
        """
        Retrieve a study by ID, auto-detecting registry if not specified.

        Args:
            registry_id: Trial ID
            registry_type: Registry type (optional, auto-detected if not provided)

        Returns:
            StandardizedStudy or None if not found
        """
        if registry_type is None:
            registry_type = self.detect_registry(registry_id)
            if registry_type is None:
                logger.warning(f"Could not detect registry for ID: {registry_id}")
                return None

        adapter = self._get_adapter(registry_type)
        if adapter is None:
            logger.error(f"No adapter available for {registry_type}")
            return None

        return adapter.get_study(registry_id)

    def search(
        self,
        query: str,
        registries: Optional[List[RegistryType]] = None,
        page: int = 1,
        max_per_registry: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        parallel: bool = True,
    ) -> UnifiedSearchResult:
        """
        Search one or more registries.

        Args:
            query: Search query string
            registries: List of registries to search (None = all available)
            page: Page number for paginated results
            max_per_registry: Maximum results per registry
            filters: Filters to apply (status, phase, etc.)
            parallel: If True, search registries in parallel

        Returns:
            UnifiedSearchResult with aggregated results
        """
        start_time = time.time()

        if registries is None:
            registries = self.get_available_registries()

        result = UnifiedSearchResult(
            query=query,
            registries_searched=registries,
        )

        if parallel and len(registries) > 1:
            # Parallel search
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {}
                for registry_type in registries:
                    adapter = self._get_adapter(registry_type)
                    if adapter:
                        future = executor.submit(
                            self._search_registry,
                            adapter,
                            query,
                            page,
                            max_per_registry,
                            filters,
                        )
                        futures[future] = registry_type

                for future in as_completed(futures):
                    registry_type = futures[future]
                    try:
                        search_result = future.result()
                        result.registry_results[registry_type] = search_result
                        result.studies.extend(search_result.studies)
                        result.total_count += search_result.total_count
                        if search_result.errors:
                            result.errors[registry_type] = search_result.errors
                        if search_result.warnings:
                            result.warnings[registry_type] = search_result.warnings
                    except Exception as e:
                        logger.error(f"Search failed for {registry_type}: {e}")
                        result.errors[registry_type] = [str(e)]
        else:
            # Sequential search
            for registry_type in registries:
                adapter = self._get_adapter(registry_type)
                if adapter:
                    try:
                        search_result = self._search_registry(
                            adapter, query, page, max_per_registry, filters
                        )
                        result.registry_results[registry_type] = search_result
                        result.studies.extend(search_result.studies)
                        result.total_count += search_result.total_count
                        if search_result.errors:
                            result.errors[registry_type] = search_result.errors
                        if search_result.warnings:
                            result.warnings[registry_type] = search_result.warnings
                    except Exception as e:
                        logger.error(f"Search failed for {registry_type}: {e}")
                        result.errors[registry_type] = [str(e)]

        result.search_time = time.time() - start_time
        return result

    def _search_registry(
        self,
        adapter: BaseRegistryAdapter,
        query: str,
        page: int,
        max_results: int,
        filters: Optional[Dict[str, Any]],
    ) -> SearchResult:
        """Execute search on a single registry."""
        return adapter.search(
            query=query,
            page=page,
            page_size=max_results,
            filters=filters,
        )

    def search_all_registries(
        self,
        query: str,
        max_per_registry: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> UnifiedSearchResult:
        """
        Search all available registries.

        Args:
            query: Search query string
            max_per_registry: Maximum results per registry
            filters: Filters to apply

        Returns:
            UnifiedSearchResult with results from all registries
        """
        return self.search(
            query=query,
            registries=None,  # All available
            max_per_registry=max_per_registry,
            filters=filters,
            parallel=True,
        )

    def clear_all_caches(self) -> None:
        """Clear caches for all adapters."""
        for adapter in self._adapters.values():
            adapter.clear_cache()


# Convenience functions
def search_registry(
    query: str,
    registry_type: RegistryType,
    max_results: int = 100,
) -> SearchResult:
    """
    Quick search of a single registry.

    Args:
        query: Search query
        registry_type: Registry to search
        max_results: Maximum results

    Returns:
        SearchResult
    """
    search = UnifiedRegistrySearch()
    result = search.search(query, registries=[registry_type], max_per_registry=max_results)
    return result.registry_results.get(registry_type, SearchResult(
        studies=[],
        total_count=0,
        query=query,
        registry=registry_type,
        search_time=0,
    ))


def get_study_by_id(registry_id: str) -> Optional[StandardizedStudy]:
    """
    Retrieve a study by ID with auto-detection of registry.

    Args:
        registry_id: Trial ID (any supported format)

    Returns:
        StandardizedStudy or None
    """
    search = UnifiedRegistrySearch()
    return search.get_study(registry_id)


# Public exports
__all__ = [
    # Base classes
    "BaseRegistryAdapter",
    "RegistryType",
    "StandardizedStudy",
    "SearchResult",
    "StudyStatus",
    "StudyPhase",

    # Unified interface
    "UnifiedRegistrySearch",
    "UnifiedSearchResult",

    # Convenience functions
    "search_registry",
    "get_study_by_id",
]
