"""
Tests for the Registry Adapters module.

Tests unified search interface, individual registry adapters,
and result standardization.
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from registry_adapters import (
    UnifiedRegistrySearch,
    UnifiedSearchResult,
    RegistryType,
    StandardizedStudy,
    SearchResult,
    StudyStatus,
    StudyPhase,
    search_registry,
    get_study_by_id,
)


class TestRegistryType:
    """Tests for RegistryType enum."""

    def test_all_registries_defined(self):
        """Test that all expected registries are defined."""
        registries = list(RegistryType)
        assert RegistryType.ANZCTR in registries
        assert RegistryType.CHICTR in registries
        assert RegistryType.DRKS in registries
        assert RegistryType.CTRI in registries
        assert RegistryType.JRCT in registries

    def test_registry_values(self):
        """Test registry enum values."""
        assert RegistryType.ANZCTR.value == "anzctr"
        assert RegistryType.CHICTR.value == "chictr"
        assert RegistryType.DRKS.value == "drks"
        assert RegistryType.CTRI.value == "ctri"
        assert RegistryType.JRCT.value == "jrct"


class TestStudyStatus:
    """Tests for StudyStatus enum."""

    def test_status_values(self):
        """Test that common statuses are defined."""
        statuses = list(StudyStatus)
        assert StudyStatus.RECRUITING in statuses
        assert StudyStatus.COMPLETED in statuses
        assert StudyStatus.NOT_YET_RECRUITING in statuses
        assert StudyStatus.TERMINATED in statuses


class TestStudyPhase:
    """Tests for StudyPhase enum."""

    def test_phase_values(self):
        """Test that all phases are defined."""
        phases = list(StudyPhase)
        assert StudyPhase.PHASE_1 in phases
        assert StudyPhase.PHASE_2 in phases
        assert StudyPhase.PHASE_3 in phases
        assert StudyPhase.PHASE_4 in phases
        assert StudyPhase.NOT_APPLICABLE in phases


class TestStandardizedStudy:
    """Tests for StandardizedStudy dataclass."""

    def test_create_study(self):
        """Test creating a standardized study."""
        study = StandardizedStudy(
            registry_id="ACTRN12620000001p",
            registry=RegistryType.ANZCTR,
            title="Test Study",
            status=StudyStatus.RECRUITING
        )
        assert study.registry_id == "ACTRN12620000001p"
        assert study.registry == RegistryType.ANZCTR
        assert study.title == "Test Study"
        assert study.status == StudyStatus.RECRUITING

    def test_study_to_dict(self):
        """Test converting study to dictionary."""
        study = StandardizedStudy(
            registry_id="ACTRN12620000001p",
            registry=RegistryType.ANZCTR,
            title="Test Study",
            status=StudyStatus.RECRUITING
        )
        d = study.to_dict()
        assert isinstance(d, dict)
        assert d["registry_id"] == "ACTRN12620000001p"
        assert d["registry"] == "anzctr"
        assert d["title"] == "Test Study"

    def test_study_dedup_key(self):
        """Test deduplication key generation."""
        study = StandardizedStudy(
            registry_id="ACTRN12620000001p",
            registry=RegistryType.ANZCTR,
            title="Test Study",
            status=StudyStatus.RECRUITING
        )
        key = study.get_dedup_key()
        assert isinstance(key, str)
        assert len(key) > 0


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_create_result(self):
        """Test creating a search result."""
        result = SearchResult(
            studies=[],
            total_count=0,
            query="diabetes",
            registry=RegistryType.ANZCTR,
            search_time=1.5
        )
        assert result.query == "diabetes"
        assert result.registry == RegistryType.ANZCTR
        assert result.search_time == 1.5

    def test_result_with_studies(self):
        """Test result with studies."""
        study = StandardizedStudy(
            registry_id="ACTRN12620000001p",
            registry=RegistryType.ANZCTR,
            title="Test Study",
            status=StudyStatus.RECRUITING
        )
        result = SearchResult(
            studies=[study],
            total_count=1,
            query="diabetes",
            registry=RegistryType.ANZCTR,
            search_time=1.5
        )
        assert len(result.studies) == 1
        assert result.total_count == 1


class TestUnifiedSearchResult:
    """Tests for UnifiedSearchResult dataclass."""

    def test_create_unified_result(self):
        """Test creating a unified search result."""
        result = UnifiedSearchResult(
            studies=[],
            total_count=0,
            query="diabetes",
            registries_searched=[RegistryType.ANZCTR, RegistryType.DRKS]
        )
        assert result.query == "diabetes"
        assert len(result.registries_searched) == 2

    def test_unified_result_to_dict(self):
        """Test converting unified result to dictionary."""
        result = UnifiedSearchResult(
            studies=[],
            total_count=0,
            query="diabetes",
            registries_searched=[RegistryType.ANZCTR]
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["query"] == "diabetes"
        assert "anzctr" in d["registries_searched"]

    def test_get_dedup_studies(self):
        """Test deduplication of studies."""
        study1 = StandardizedStudy(
            registry_id="ACTRN12620000001p",
            registry=RegistryType.ANZCTR,
            title="Test Study",
            status=StudyStatus.RECRUITING
        )
        study2 = StandardizedStudy(
            registry_id="ACTRN12620000001p",  # Same ID
            registry=RegistryType.ANZCTR,
            title="Test Study",
            status=StudyStatus.RECRUITING
        )
        result = UnifiedSearchResult(
            studies=[study1, study2],
            total_count=2,
            query="diabetes",
            registries_searched=[RegistryType.ANZCTR]
        )
        deduped = result.get_dedup_studies()
        assert len(deduped) == 1


class TestUnifiedRegistrySearch:
    """Tests for UnifiedRegistrySearch class."""

    @pytest.fixture
    def search(self):
        """Create search instance for tests."""
        return UnifiedRegistrySearch()

    def test_get_available_registries(self, search):
        """Test getting available registries."""
        registries = search.get_available_registries()
        assert isinstance(registries, list)
        # At least some registries should be available
        # (depends on installed dependencies)

    def test_detect_anzctr_id(self, search):
        """Test detecting ANZCTR ID format."""
        reg = search.detect_registry("ACTRN12620000001p")
        assert reg == RegistryType.ANZCTR

    def test_detect_chictr_id(self, search):
        """Test detecting ChiCTR ID format."""
        reg = search.detect_registry("ChiCTR2000000001")
        assert reg == RegistryType.CHICTR

    def test_detect_drks_id(self, search):
        """Test detecting DRKS ID format."""
        reg = search.detect_registry("DRKS00000001")
        assert reg == RegistryType.DRKS

    def test_detect_ctri_id(self, search):
        """Test detecting CTRI ID format."""
        reg = search.detect_registry("CTRI/2020/01/000001")
        assert reg == RegistryType.CTRI

    def test_detect_jrct_id(self, search):
        """Test detecting jRCT ID format."""
        reg = search.detect_registry("jRCTs000000001")
        assert reg == RegistryType.JRCT

    def test_detect_unknown_id(self, search):
        """Test handling of unknown ID format."""
        reg = search.detect_registry("UNKNOWN123456")
        assert reg is None

    def test_id_patterns(self, search):
        """Test ID pattern definitions."""
        assert len(search.ID_PATTERNS) >= 5
        for registry_type, pattern in search.ID_PATTERNS.items():
            assert isinstance(pattern, str)
            assert len(pattern) > 0

    def test_initialization_params(self):
        """Test initialization with custom parameters."""
        search = UnifiedRegistrySearch(
            max_workers=3,
            default_timeout=30,
            default_rate_limit=1.0
        )
        assert search.max_workers == 3
        assert search.default_timeout == 30
        assert search.default_rate_limit == 1.0

    def test_clear_all_caches(self, search):
        """Test clearing all caches."""
        # Should not raise an error
        search.clear_all_caches()


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_search_registry_function_exists(self):
        """Test that search_registry function exists."""
        assert callable(search_registry)

    def test_get_study_by_id_function_exists(self):
        """Test that get_study_by_id function exists."""
        assert callable(get_study_by_id)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_query(self):
        """Test handling of empty query string."""
        search = UnifiedRegistrySearch()
        # Should not raise an error
        result = search.search("", registries=[])
        assert isinstance(result, UnifiedSearchResult)

    def test_special_characters_in_query(self):
        """Test handling of special characters in query."""
        search = UnifiedRegistrySearch()
        result = search.search(
            "diabetes & hypertension (T2DM)",
            registries=[]  # Empty to test parsing only
        )
        assert isinstance(result, UnifiedSearchResult)

    def test_invalid_registry_type(self):
        """Test handling when no valid registries specified."""
        search = UnifiedRegistrySearch()
        result = search.search("diabetes", registries=[])
        assert result.total_count == 0

    def test_parallel_vs_sequential(self):
        """Test parallel and sequential search modes."""
        search = UnifiedRegistrySearch()

        # Both modes should work without errors
        result_parallel = search.search(
            "diabetes",
            registries=[],
            parallel=True
        )
        result_sequential = search.search(
            "diabetes",
            registries=[],
            parallel=False
        )

        assert isinstance(result_parallel, UnifiedSearchResult)
        assert isinstance(result_sequential, UnifiedSearchResult)


class TestDataclassDefaults:
    """Tests for dataclass default values."""

    def test_standardized_study_defaults(self):
        """Test StandardizedStudy default values."""
        study = StandardizedStudy(
            registry_id="TEST123",
            registry=RegistryType.ANZCTR,
            title="Test",
            status=StudyStatus.RECRUITING
        )
        # Check optional fields have proper defaults
        assert study.conditions == [] or study.conditions is None or isinstance(study.conditions, list)

    def test_search_result_defaults(self):
        """Test SearchResult default values."""
        result = SearchResult(
            studies=[],
            total_count=0,
            query="test",
            registry=RegistryType.ANZCTR,
            search_time=0.0
        )
        assert result.errors == [] or result.errors is None or isinstance(result.errors, list)

    def test_unified_result_defaults(self):
        """Test UnifiedSearchResult default values."""
        result = UnifiedSearchResult()
        assert result.studies == []
        assert result.total_count == 0
        assert result.query == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
