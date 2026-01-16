"""
Pytest configuration and shared fixtures for ctgov-search-strategies tests.

This module provides common fixtures used across test modules including:
- Mock API responses for CT.gov API
- Mock session objects for requests
- Sample NCT IDs and search results
- AACT database connection fixture (with skip if unavailable)
- Custom markers for test categorization
"""

import os
import sys
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# =============================================================================
# Custom Pytest Markers
# =============================================================================

def pytest_configure(config):
    """Register custom markers for test categorization."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require external services)"
    )
    config.addinivalue_line(
        "markers", "aact: marks tests that require AACT database connection"
    )
    config.addinivalue_line(
        "markers", "api: marks tests that make real API calls to CT.gov"
    )


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_nct_ids() -> List[str]:
    """
    Provide a list of sample NCT IDs for testing.

    These are real NCT ID formats but used only for testing purposes.
    """
    return [
        "NCT00000001",
        "NCT00000002",
        "NCT00000003",
        "NCT01234567",
        "NCT98765432",
        "NCT00001111",
        "NCT00002222",
        "NCT00003333",
        "NCT00004444",
        "NCT00005555",
    ]


@pytest.fixture
def sample_study_data() -> Dict[str, Any]:
    """
    Provide a sample study data structure as returned by CT.gov API.
    """
    return {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT00000001",
                "orgStudyIdInfo": {"id": "STUDY-001"},
                "briefTitle": "Test Study for Diabetes Treatment",
                "officialTitle": "A Randomized Controlled Trial of Test Drug for Type 2 Diabetes"
            },
            "statusModule": {
                "overallStatus": "COMPLETED",
                "startDateStruct": {"date": "2020-01-15"},
                "completionDateStruct": {"date": "2023-06-30"}
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {
                    "name": "Test University",
                    "class": "OTHER"
                }
            },
            "descriptionModule": {
                "briefSummary": "This study evaluates the efficacy of test drug in patients with type 2 diabetes.",
                "detailedDescription": "A detailed description of the study methodology and endpoints."
            },
            "conditionsModule": {
                "conditions": ["Type 2 Diabetes Mellitus", "Diabetes"]
            },
            "designModule": {
                "studyType": "INTERVENTIONAL",
                "phases": ["PHASE3"],
                "designInfo": {
                    "allocation": "RANDOMIZED",
                    "interventionModel": "PARALLEL",
                    "primaryPurpose": "TREATMENT",
                    "maskingInfo": {
                        "masking": "DOUBLE"
                    }
                },
                "enrollmentInfo": {
                    "count": 500,
                    "type": "ACTUAL"
                }
            },
            "armsInterventionsModule": {
                "armGroups": [
                    {"label": "Treatment", "type": "EXPERIMENTAL"},
                    {"label": "Placebo", "type": "PLACEBO_COMPARATOR"}
                ],
                "interventions": [
                    {"type": "DRUG", "name": "Test Drug", "description": "Experimental treatment"}
                ]
            },
            "outcomesModule": {
                "primaryOutcomes": [
                    {
                        "measure": "Change in HbA1c",
                        "description": "Change from baseline in HbA1c at week 24",
                        "timeFrame": "24 weeks"
                    }
                ]
            },
            "eligibilityModule": {
                "eligibilityCriteria": "Inclusion: Adults with T2DM. Exclusion: Pregnancy.",
                "healthyVolunteers": False,
                "sex": "ALL",
                "minimumAge": "18 Years",
                "maximumAge": "75 Years"
            },
            "contactsLocationsModule": {
                "locations": [
                    {
                        "facility": "Test Medical Center",
                        "city": "Boston",
                        "state": "Massachusetts",
                        "country": "United States"
                    }
                ]
            }
        },
        "hasResults": True
    }


@pytest.fixture
def mock_api_response(sample_study_data) -> Dict[str, Any]:
    """
    Provide a mock CT.gov API response structure.

    This mimics the response from the ClinicalTrials.gov API v2.
    """
    return {
        "studies": [
            sample_study_data,
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT00000002",
                        "briefTitle": "Another Test Study"
                    },
                    "statusModule": {"overallStatus": "RECRUITING"},
                    "conditionsModule": {"conditions": ["Diabetes"]},
                    "designModule": {
                        "studyType": "INTERVENTIONAL",
                        "phases": ["PHASE2"]
                    }
                },
                "hasResults": False
            },
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT00000003",
                        "briefTitle": "Third Test Study"
                    },
                    "statusModule": {"overallStatus": "COMPLETED"},
                    "conditionsModule": {"conditions": ["Type 1 Diabetes"]},
                    "designModule": {
                        "studyType": "OBSERVATIONAL",
                        "phases": ["NA"]
                    }
                },
                "hasResults": True
            }
        ],
        "totalCount": 3,
        "nextPageToken": None
    }


@pytest.fixture
def mock_api_response_paginated(sample_study_data) -> Dict[str, Any]:
    """
    Provide a mock paginated CT.gov API response with nextPageToken.
    """
    return {
        "studies": [sample_study_data],
        "totalCount": 100,
        "nextPageToken": "abc123nextpage"
    }


@pytest.fixture
def sample_search_result() -> Dict[str, Any]:
    """
    Provide a sample SearchResult-like dictionary for testing.
    """
    return {
        "strategy_id": "S1",
        "strategy_name": "Condition Only (Maximum Recall)",
        "condition": "diabetes",
        "total_count": 15000,
        "query_url": "https://clinicaltrials.gov/api/v2/studies?query.cond=diabetes",
        "execution_time": 0.523,
        "studies": [],
        "error": None
    }


@pytest.fixture
def sample_recall_metrics() -> Dict[str, Any]:
    """
    Provide sample recall metrics for testing.
    """
    return {
        "strategy_id": "S1",
        "total_known": 10,
        "found": 8,
        "recall": 80.0,
        "nct_ids_found": ["NCT00000001", "NCT00000002", "NCT00000003",
                         "NCT00000004", "NCT00000005", "NCT00000006",
                         "NCT00000007", "NCT00000008"],
        "nct_ids_missed": ["NCT00000009", "NCT00000010"]
    }


# =============================================================================
# Mock Session and Response Fixtures
# =============================================================================

class FakeResponse:
    """Mock HTTP response for testing."""

    def __init__(
        self,
        payload: Dict[str, Any],
        status_code: int = 200,
        url: str = "https://clinicaltrials.gov/api/v2/studies"
    ):
        self._payload = payload
        self.status_code = status_code
        self.url = url
        self.headers = {"Content-Type": "application/json"}
        self.text = str(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests.exceptions import HTTPError
            raise HTTPError(f"HTTP Error: {self.status_code}")

    def json(self):
        return self._payload


@pytest.fixture
def fake_response_factory():
    """
    Factory fixture to create FakeResponse objects with custom payloads.

    Usage:
        def test_something(fake_response_factory):
            response = fake_response_factory({"studies": [], "totalCount": 0})
    """
    def _create_response(
        payload: Dict[str, Any],
        status_code: int = 200,
        url: str = "https://clinicaltrials.gov/api/v2/studies"
    ) -> FakeResponse:
        return FakeResponse(payload, status_code, url)
    return _create_response


@pytest.fixture
def mock_session(mock_api_response):
    """
    Provide a mock requests.Session that returns predefined API responses.

    The mock session's get method returns a FakeResponse with the mock_api_response.
    """
    session = MagicMock()
    session.get.return_value = FakeResponse(mock_api_response)
    session.headers = {}
    return session


@pytest.fixture
def mock_session_factory(fake_response_factory):
    """
    Factory fixture to create mock sessions with custom responses.

    Usage:
        def test_something(mock_session_factory):
            session = mock_session_factory({"studies": [], "totalCount": 0})
    """
    def _create_session(
        payload: Dict[str, Any],
        status_code: int = 200
    ) -> MagicMock:
        session = MagicMock()
        session.get.return_value = fake_response_factory(payload, status_code)
        session.headers = {}
        return session
    return _create_session


@pytest.fixture
def mock_session_error():
    """
    Provide a mock session that raises connection errors.
    """
    from requests.exceptions import ConnectionError, Timeout

    session = MagicMock()
    session.get.side_effect = ConnectionError("Connection refused")
    session.headers = {}
    return session


@pytest.fixture
def mock_session_timeout():
    """
    Provide a mock session that raises timeout errors.
    """
    from requests.exceptions import Timeout

    session = MagicMock()
    session.get.side_effect = Timeout("Request timed out")
    session.headers = {}
    return session


# =============================================================================
# AACT Database Connection Fixture
# =============================================================================

@pytest.fixture
def aact_connection():
    """
    Provide an AACT database connection for integration tests.

    Skips the test if AACT credentials are not available or connection fails.

    Required environment variables:
        - AACT_USER: AACT database username
        - AACT_PASSWORD: AACT database password

    Or uses default public credentials if not set.
    """
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed - skipping AACT tests")

    # Check for AACT credentials
    aact_user = os.environ.get("AACT_USER", "")
    aact_password = os.environ.get("AACT_PASSWORD", "")

    # AACT public database connection parameters
    connection_params = {
        "host": "aact-db.ctti-clinicaltrials.org",
        "port": 5432,
        "database": "aact",
        "user": aact_user if aact_user else "aact_reader",
        "password": aact_password if aact_password else "",
        "connect_timeout": 10
    }

    # Skip if no credentials and default doesn't work
    if not aact_user and not aact_password:
        pytest.skip(
            "AACT credentials not configured. Set AACT_USER and AACT_PASSWORD "
            "environment variables to run AACT integration tests."
        )

    try:
        conn = psycopg2.connect(**connection_params)
        yield conn
        conn.close()
    except psycopg2.OperationalError as e:
        pytest.skip(f"Could not connect to AACT database: {e}")
    except Exception as e:
        pytest.skip(f"AACT connection error: {e}")


@pytest.fixture
def aact_cursor(aact_connection):
    """
    Provide an AACT database cursor for integration tests.

    Automatically rolls back any changes after the test.
    """
    cursor = aact_connection.cursor()
    yield cursor
    aact_connection.rollback()
    cursor.close()


# =============================================================================
# Test Data Fixtures for Specific Conditions
# =============================================================================

@pytest.fixture
def diabetes_studies() -> List[Dict[str, Any]]:
    """
    Provide sample diabetes-related study data.
    """
    return [
        {
            "protocolSection": {
                "identificationModule": {
                    "nctId": f"NCT0000000{i}",
                    "briefTitle": f"Diabetes Study {i}"
                },
                "conditionsModule": {"conditions": ["Type 2 Diabetes Mellitus"]},
                "designModule": {"studyType": "INTERVENTIONAL"}
            }
        }
        for i in range(1, 6)
    ]


@pytest.fixture
def oncology_studies() -> List[Dict[str, Any]]:
    """
    Provide sample oncology-related study data.
    """
    return [
        {
            "protocolSection": {
                "identificationModule": {
                    "nctId": f"NCT1000000{i}",
                    "briefTitle": f"Cancer Study {i}"
                },
                "conditionsModule": {"conditions": ["Breast Cancer", "Neoplasms"]},
                "designModule": {"studyType": "INTERVENTIONAL", "phases": ["PHASE3"]}
            }
        }
        for i in range(1, 4)
    ]


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def temp_output_dir(tmp_path):
    """
    Provide a temporary directory for test output files.
    """
    output_dir = tmp_path / "test_output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def mock_rate_limiter():
    """
    Provide a mock that disables rate limiting for faster tests.
    """
    with patch("time.sleep", return_value=None):
        yield


@pytest.fixture(autouse=False)
def no_network():
    """
    Fixture to ensure no real network calls are made.

    Use this fixture explicitly in tests that should not make network calls:
        def test_something(no_network):
            ...
    """
    with patch("requests.Session") as mock_session_cls:
        mock_session_cls.return_value.get.side_effect = RuntimeError(
            "Network calls are disabled in this test"
        )
        yield mock_session_cls
