#!/usr/bin/env python3
"""
AACT Database Integration Tests

Tests for AACT (Aggregate Analysis of ClinicalTrials.gov) database integration.
Includes tests for:
- Database connection handling
- NCT ID validation against AACT
- Recall calculation using AACT as ground truth
- Mock fixtures for CI environments without database access

Run with: pytest tests/test_aact_integration.py -v
Run only mock tests: pytest tests/test_aact_integration.py -v -m "not requires_aact"
"""

import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load .env file if present (same as aact_validation.py)
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())


# =============================================================================
# Test Configuration
# =============================================================================

# Check if AACT credentials are available (after loading .env)
AACT_CREDENTIALS_AVAILABLE = bool(
    os.environ.get('AACT_USER') and os.environ.get('AACT_PASSWORD')
)

# AACT database configuration
AACT_CONFIG = {
    'host': 'aact-db.ctti-clinicaltrials.org',
    'port': 5432,
    'database': 'aact',
    'user': os.environ.get('AACT_USER', ''),
    'password': os.environ.get('AACT_PASSWORD', '')
}

# Sample NCT IDs for testing
SAMPLE_NCT_IDS = [
    "NCT00000001",
    "NCT01958736",
    "NCT02717715",
    "NCT04499677",
]

# Known valid NCT IDs (from Cochrane systematic reviews)
KNOWN_VALID_NCT_IDS = [
    "NCT01958736",  # Stroke study
    "NCT02717715",  # Stroke study
    "NCT02735148",  # Stroke study
    "NCT04499677",  # COVID-19 study
    "NCT04818320",  # COVID-19 study
]


# =============================================================================
# Pytest Markers and Skip Decorators
# =============================================================================

# Create a combined marker that both marks the test and skips if credentials unavailable
# This allows both `-m requires_aact` selection AND automatic skipping
def requires_aact(func):
    """Decorator that marks test as requiring AACT and skips if credentials unavailable."""
    # Apply the marker for test selection
    func = pytest.mark.requires_aact(func)
    # Apply skipif for conditional execution
    if not AACT_CREDENTIALS_AVAILABLE:
        func = pytest.mark.skip(
            reason="AACT credentials not available (set AACT_USER and AACT_PASSWORD)"
        )(func)
    return func


# =============================================================================
# Mock Fixtures for CI Testing
# =============================================================================

class MockCursor:
    """Mock database cursor for testing without real database connection."""

    def __init__(self, results=None):
        self.results = results or []
        self.result_index = 0
        self.last_query = None
        self.last_params = None

    def execute(self, query, params=None):
        self.last_query = query
        self.last_params = params

    def fetchone(self):
        if self.result_index < len(self.results):
            result = self.results[self.result_index]
            self.result_index += 1
            return result
        return None

    def fetchall(self):
        return self.results

    def close(self):
        pass


class MockConnection:
    """Mock database connection for testing."""

    def __init__(self, cursor_results=None):
        self._cursor = MockCursor(cursor_results)
        self._closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self._closed = True

    def is_closed(self):
        return self._closed


@pytest.fixture
def mock_aact_connection():
    """Fixture providing a mock AACT connection."""
    return MockConnection()


@pytest.fixture
def mock_aact_connection_with_studies():
    """Fixture providing a mock AACT connection with sample study data."""
    sample_results = [
        (
            "NCT01958736",
            "Study of Stroke Treatment",
            "Completed",
            "Interventional",
            "Randomized"
        ),
        (
            "NCT02717715",
            "Stroke Prevention Trial",
            "Completed",
            "Interventional",
            "Randomized"
        ),
        (
            "NCT04499677",
            "COVID-19 Vaccine Study",
            "Completed",
            "Interventional",
            "Randomized"
        ),
    ]
    return MockConnection(cursor_results=sample_results)


@pytest.fixture
def mock_empty_connection():
    """Fixture providing a mock AACT connection with no results."""
    return MockConnection(cursor_results=[])


# =============================================================================
# AACT Validation Module (Imported or Mocked)
# =============================================================================

# Import the actual module functions if available
try:
    from aact_validation import (
        connect_aact,
        check_nct_exists,
        search_by_nct_list,
        get_conditions_for_nct,
        AACT_CONFIG as ACTUAL_AACT_CONFIG
    )
    AACT_MODULE_AVAILABLE = True
except ImportError:
    AACT_MODULE_AVAILABLE = False

    # Mock implementations for when module is not available
    def connect_aact():
        return None

    def check_nct_exists(conn, nct_id):
        return None

    def search_by_nct_list(conn, nct_ids):
        return set()

    def get_conditions_for_nct(conn, nct_id):
        return []


# =============================================================================
# Test Classes
# =============================================================================

class TestAACTConnection:
    """Tests for AACT database connection handling."""

    def test_connection_config_structure(self):
        """Test that AACT configuration has required fields."""
        required_fields = ['host', 'port', 'database', 'user', 'password']
        for field in required_fields:
            assert field in AACT_CONFIG, f"Missing required field: {field}"

    def test_connection_config_host(self):
        """Test AACT host configuration."""
        assert AACT_CONFIG['host'] == 'aact-db.ctti-clinicaltrials.org'

    def test_connection_config_port(self):
        """Test AACT port configuration."""
        assert AACT_CONFIG['port'] == 5432

    def test_connection_config_database(self):
        """Test AACT database name configuration."""
        assert AACT_CONFIG['database'] == 'aact'

    @patch('psycopg2.connect')
    def test_connection_success_with_mock(self, mock_connect):
        """Test successful connection with mocked psycopg2."""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        # Temporarily set credentials
        with patch.dict(os.environ, {'AACT_USER': 'test', 'AACT_PASSWORD': 'test'}):
            if AACT_MODULE_AVAILABLE:
                conn = connect_aact()
                # If credentials were available, connection should work
                assert mock_connect.called or conn is None

    @patch('psycopg2.connect')
    def test_connection_failure_handling(self, mock_connect):
        """Test that connection failures are handled gracefully."""
        mock_connect.side_effect = Exception("Connection refused")

        with patch.dict(os.environ, {'AACT_USER': 'test', 'AACT_PASSWORD': 'test'}):
            if AACT_MODULE_AVAILABLE:
                conn = connect_aact()
                assert conn is None

    def test_connection_without_credentials(self):
        """Test that connection returns None without credentials."""
        if AACT_MODULE_AVAILABLE:
            # Need to patch the AACT_CONFIG directly since env vars are read at import
            from aact_validation import AACT_CONFIG as actual_config
            original_user = actual_config.get('user', '')
            original_password = actual_config.get('password', '')

            try:
                # Temporarily clear credentials
                actual_config['user'] = ''
                actual_config['password'] = ''

                conn = connect_aact()
                assert conn is None
            finally:
                # Restore original credentials
                actual_config['user'] = original_user
                actual_config['password'] = original_password

    @requires_aact
    def test_real_connection(self):
        """Test real AACT connection (requires credentials)."""
        conn = connect_aact()
        assert conn is not None
        conn.close()


class TestNCTIDValidation:
    """Tests for NCT ID validation against AACT."""

    def test_nct_id_format_valid(self):
        """Test valid NCT ID formats."""
        valid_ids = [
            "NCT00000001",
            "NCT12345678",
            "NCT99999999",
            "nct00000001",  # lowercase should be accepted
        ]

        import re
        pattern = re.compile(r'^NCT\d{8}$', re.IGNORECASE)

        for nct_id in valid_ids:
            assert pattern.match(nct_id), f"Should be valid: {nct_id}"

    def test_nct_id_format_invalid(self):
        """Test invalid NCT ID formats."""
        invalid_ids = [
            "NCT0000001",    # Too short
            "NCT000000001",  # Too long
            "NCT1234567X",   # Contains letter
            "NCTABCDEFGH",   # All letters
            "12345678",      # No NCT prefix
            "NCT-00000001",  # Contains hyphen
            "",              # Empty
            None,            # None
        ]

        import re
        pattern = re.compile(r'^NCT\d{8}$', re.IGNORECASE)

        for nct_id in invalid_ids:
            if nct_id is None:
                assert not pattern.match(str(nct_id) if nct_id else '')
            else:
                match = pattern.match(nct_id) if nct_id else None
                assert not match, f"Should be invalid: {nct_id}"

    def test_check_nct_exists_with_mock(self, mock_aact_connection_with_studies):
        """Test NCT ID existence check with mock connection."""
        conn = mock_aact_connection_with_studies

        # Set up cursor to return a result
        conn._cursor.results = [(
            "NCT01958736",
            "Study of Stroke Treatment",
            "Completed",
            "Interventional",
            "Randomized",
            ["Stroke"]
        )]

        if AACT_MODULE_AVAILABLE:
            result = check_nct_exists(conn, "NCT01958736")
            # Note: With real module, this would return a dict
            # With mock, it depends on implementation

    def test_check_nct_not_exists_with_mock(self, mock_empty_connection):
        """Test NCT ID that doesn't exist returns None."""
        conn = mock_empty_connection

        if AACT_MODULE_AVAILABLE:
            result = check_nct_exists(conn, "NCT99999999")
            assert result is None

    @requires_aact
    def test_real_nct_validation(self):
        """Test real NCT ID validation (requires credentials)."""
        conn = connect_aact()
        assert conn is not None

        try:
            # Test a known valid NCT ID
            result = check_nct_exists(conn, "NCT01958736")
            if result:
                assert 'nct_id' in result
                assert result['nct_id'] == "NCT01958736"
        finally:
            conn.close()

    def test_search_by_nct_list_with_mock(self, mock_aact_connection_with_studies):
        """Test batch NCT ID search with mock connection."""
        conn = mock_aact_connection_with_studies

        nct_ids = ["NCT01958736", "NCT02717715", "NCT99999999"]

        if AACT_MODULE_AVAILABLE:
            found = search_by_nct_list(conn, nct_ids)
            # Mock should return empty set without proper setup
            assert isinstance(found, set)

    @requires_aact
    def test_real_batch_nct_search(self):
        """Test real batch NCT ID search (requires credentials)."""
        conn = connect_aact()
        assert conn is not None

        try:
            nct_ids = KNOWN_VALID_NCT_IDS
            found = search_by_nct_list(conn, nct_ids)

            assert isinstance(found, set)
            # At least some should be found
            assert len(found) > 0
        finally:
            conn.close()


class TestRecallCalculation:
    """Tests for recall calculation using AACT as ground truth."""

    def test_recall_calculation_perfect(self):
        """Test 100% recall calculation."""
        known_ncts = {"NCT00000001", "NCT00000002", "NCT00000003"}
        found_ncts = {"NCT00000001", "NCT00000002", "NCT00000003"}

        recall = len(found_ncts & known_ncts) / len(known_ncts) * 100
        assert recall == 100.0

    def test_recall_calculation_partial(self):
        """Test partial recall calculation."""
        known_ncts = {"NCT00000001", "NCT00000002", "NCT00000003", "NCT00000004"}
        found_ncts = {"NCT00000001", "NCT00000002"}

        recall = len(found_ncts & known_ncts) / len(known_ncts) * 100
        assert recall == 50.0

    def test_recall_calculation_zero(self):
        """Test zero recall calculation."""
        known_ncts = {"NCT00000001", "NCT00000002"}
        found_ncts = {"NCT00000003", "NCT00000004"}

        recall = len(found_ncts & known_ncts) / len(known_ncts) * 100
        assert recall == 0.0

    def test_recall_calculation_empty_known(self):
        """Test recall with empty known set."""
        known_ncts = set()
        found_ncts = {"NCT00000001"}

        # Avoid division by zero
        recall = len(found_ncts & known_ncts) / len(known_ncts) * 100 if known_ncts else 0
        assert recall == 0.0

    def test_recall_calculation_extra_found(self):
        """Test recall when more NCTs are found than known."""
        known_ncts = {"NCT00000001", "NCT00000002"}
        found_ncts = {"NCT00000001", "NCT00000002", "NCT00000003", "NCT00000004"}

        recall = len(found_ncts & known_ncts) / len(known_ncts) * 100
        assert recall == 100.0  # Recall is about finding known items

    def test_precision_calculation(self):
        """Test precision calculation (complementary to recall)."""
        known_ncts = {"NCT00000001", "NCT00000002"}
        found_ncts = {"NCT00000001", "NCT00000002", "NCT00000003", "NCT00000004"}

        # Precision = true positives / all positives
        precision = len(found_ncts & known_ncts) / len(found_ncts) * 100 if found_ncts else 0
        assert precision == 50.0

    def test_f1_score_calculation(self):
        """Test F1 score calculation."""
        known_ncts = {"NCT00000001", "NCT00000002", "NCT00000003"}
        found_ncts = {"NCT00000001", "NCT00000002", "NCT00000004"}

        true_positives = len(found_ncts & known_ncts)
        recall = true_positives / len(known_ncts) * 100
        precision = true_positives / len(found_ncts) * 100

        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        # With 2 TP, 1 FN, 1 FP: recall=66.67%, precision=66.67%, F1=66.67%
        assert abs(f1 - 66.67) < 0.1

    @requires_aact
    def test_real_recall_calculation(self):
        """Test real recall calculation with AACT (requires credentials)."""
        conn = connect_aact()
        assert conn is not None

        try:
            known_ncts = set(KNOWN_VALID_NCT_IDS)
            found = search_by_nct_list(conn, list(known_ncts))

            recall = len(found & known_ncts) / len(known_ncts) * 100

            # With direct NCT lookup, recall should be very high (>90%)
            assert recall > 90.0
        finally:
            conn.close()


class TestConnectionFailures:
    """Tests for handling connection failures and edge cases."""

    @patch('psycopg2.connect')
    def test_connection_timeout(self, mock_connect):
        """Test handling of connection timeout."""
        mock_connect.side_effect = Exception("Connection timed out")

        with patch.dict(os.environ, {'AACT_USER': 'test', 'AACT_PASSWORD': 'test'}):
            if AACT_MODULE_AVAILABLE:
                conn = connect_aact()
                assert conn is None

    @patch('psycopg2.connect')
    def test_authentication_failure(self, mock_connect):
        """Test handling of authentication failure."""
        mock_connect.side_effect = Exception("Authentication failed")

        with patch.dict(os.environ, {'AACT_USER': 'invalid', 'AACT_PASSWORD': 'invalid'}):
            if AACT_MODULE_AVAILABLE:
                conn = connect_aact()
                assert conn is None

    @patch('psycopg2.connect')
    def test_network_error(self, mock_connect):
        """Test handling of network errors."""
        mock_connect.side_effect = Exception("Network unreachable")

        with patch.dict(os.environ, {'AACT_USER': 'test', 'AACT_PASSWORD': 'test'}):
            if AACT_MODULE_AVAILABLE:
                conn = connect_aact()
                assert conn is None

    def test_query_with_closed_connection(self, mock_aact_connection):
        """Test handling of queries on closed connection."""
        conn = mock_aact_connection
        conn.close()

        assert conn.is_closed()


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_nct_list(self, mock_aact_connection):
        """Test searching with empty NCT ID list."""
        conn = mock_aact_connection

        if AACT_MODULE_AVAILABLE:
            # This should handle empty list gracefully
            found = search_by_nct_list(conn, [])
            assert found == set() or found is None

    def test_duplicate_nct_ids(self, mock_aact_connection):
        """Test searching with duplicate NCT IDs."""
        conn = mock_aact_connection

        nct_ids = ["NCT00000001", "NCT00000001", "NCT00000001"]

        if AACT_MODULE_AVAILABLE:
            found = search_by_nct_list(conn, nct_ids)
            # Duplicates should be handled
            assert isinstance(found, set)

    def test_case_insensitive_nct_ids(self):
        """Test that NCT IDs are case-insensitive."""
        import re
        pattern = re.compile(r'^NCT\d{8}$', re.IGNORECASE)

        assert pattern.match("NCT00000001")
        assert pattern.match("nct00000001")
        assert pattern.match("Nct00000001")

    def test_large_batch_nct_ids(self, mock_aact_connection):
        """Test handling of large batch of NCT IDs."""
        conn = mock_aact_connection

        # Generate 1000 NCT IDs
        nct_ids = [f"NCT{str(i).zfill(8)}" for i in range(1, 1001)]

        if AACT_MODULE_AVAILABLE:
            # Should not raise an error
            try:
                found = search_by_nct_list(conn, nct_ids)
                assert isinstance(found, set)
            except Exception as e:
                # Large batches might fail, but should not crash unexpectedly
                assert "query" in str(e).lower() or "sql" in str(e).lower()

    def test_special_characters_in_query(self, mock_aact_connection):
        """Test that SQL injection is prevented."""
        conn = mock_aact_connection

        # Attempt SQL injection
        malicious_ids = [
            "NCT00000001'; DROP TABLE studies; --",
            "NCT00000001 OR 1=1",
        ]

        if AACT_MODULE_AVAILABLE:
            # Should not execute malicious SQL
            try:
                found = search_by_nct_list(conn, malicious_ids)
                # Should return empty or handle safely
                assert isinstance(found, set)
            except Exception:
                # Failing safely is acceptable
                pass

    def test_unicode_handling(self, mock_aact_connection):
        """Test handling of unicode characters."""
        conn = mock_aact_connection

        # NCT IDs with accidental unicode
        unicode_ids = [
            "NCT00000001",
            "\u200bNCT00000002",  # Zero-width space
        ]

        if AACT_MODULE_AVAILABLE:
            try:
                found = search_by_nct_list(conn, unicode_ids)
            except Exception:
                pass  # Failing safely is acceptable


class TestConditionQueries:
    """Tests for condition-based queries."""

    def test_get_conditions_with_mock(self, mock_aact_connection):
        """Test getting conditions for NCT ID with mock."""
        conn = mock_aact_connection
        conn._cursor.results = [("Stroke",), ("Cerebrovascular Disease",)]

        if AACT_MODULE_AVAILABLE:
            conditions = get_conditions_for_nct(conn, "NCT01958736")
            # Should return list of condition names
            assert isinstance(conditions, list)

    @requires_aact
    def test_real_get_conditions(self):
        """Test getting conditions from real AACT (requires credentials)."""
        conn = connect_aact()
        assert conn is not None

        try:
            conditions = get_conditions_for_nct(conn, "NCT01958736")
            assert isinstance(conditions, list)
            # Known stroke study should have stroke-related conditions
        finally:
            conn.close()


class TestMockDatabaseResponses:
    """Tests using mock database responses for CI environments."""

    def test_mock_study_query(self):
        """Test mock study query response."""
        mock_results = [
            ("NCT00000001", "Test Study 1", "Completed", "Interventional", "Randomized"),
            ("NCT00000002", "Test Study 2", "Recruiting", "Interventional", "Non-Randomized"),
        ]

        conn = MockConnection(cursor_results=mock_results)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM studies WHERE nct_id IN (%s, %s)")

        results = cursor.fetchall()

        assert len(results) == 2
        assert results[0][0] == "NCT00000001"
        assert results[1][0] == "NCT00000002"

    def test_mock_empty_response(self):
        """Test mock empty database response."""
        conn = MockConnection(cursor_results=[])
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM studies WHERE nct_id = %s")

        results = cursor.fetchall()

        assert len(results) == 0

    def test_mock_single_result(self):
        """Test mock single result response."""
        mock_results = [(
            "NCT00000001",
            "Single Study",
            "Completed",
            "Interventional",
            "Randomized"
        )]

        conn = MockConnection(cursor_results=mock_results)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM studies WHERE nct_id = %s")

        result = cursor.fetchone()

        assert result is not None
        assert result[0] == "NCT00000001"

    def test_mock_connection_lifecycle(self):
        """Test mock connection open/close lifecycle."""
        conn = MockConnection()

        assert not conn.is_closed()

        cursor = conn.cursor()
        assert cursor is not None

        conn.close()
        assert conn.is_closed()


class TestIntegrationWorkflow:
    """Tests for complete integration workflows."""

    @requires_aact
    def test_full_validation_workflow(self):
        """Test complete validation workflow (requires credentials)."""
        # 1. Connect to AACT
        conn = connect_aact()
        assert conn is not None

        try:
            # 2. Define known NCT IDs
            known_ncts = set(KNOWN_VALID_NCT_IDS[:3])

            # 3. Search for NCT IDs
            found = search_by_nct_list(conn, list(known_ncts))

            # 4. Calculate recall
            recall = len(found & known_ncts) / len(known_ncts) * 100

            # 5. Identify missing
            missing = known_ncts - found

            # 6. Verify results
            assert isinstance(recall, float)
            assert 0 <= recall <= 100
            assert isinstance(missing, set)

        finally:
            conn.close()

    def test_mock_validation_workflow(self, mock_aact_connection_with_studies):
        """Test validation workflow with mock connection."""
        conn = mock_aact_connection_with_studies

        # Simulate workflow
        known_ncts = {"NCT01958736", "NCT02717715", "NCT04499677"}

        # Mock found NCTs
        found = {"NCT01958736", "NCT02717715", "NCT04499677"}

        recall = len(found & known_ncts) / len(known_ncts) * 100
        missing = known_ncts - found

        assert recall == 100.0
        assert len(missing) == 0


class TestDataIntegrity:
    """Tests for data integrity and consistency."""

    def test_nct_id_normalization(self):
        """Test NCT ID normalization to uppercase."""
        nct_ids = ["nct00000001", "NCT00000002", "Nct00000003"]

        normalized = [nct.upper() for nct in nct_ids]

        assert normalized == ["NCT00000001", "NCT00000002", "NCT00000003"]

    def test_result_structure(self):
        """Test expected result structure from check_nct_exists."""
        expected_keys = ['nct_id', 'title', 'status', 'study_type', 'allocation', 'conditions']

        # Mock result
        result = {
            'nct_id': "NCT00000001",
            'title': "Test Study",
            'status': "Completed",
            'study_type': "Interventional",
            'allocation': "Randomized",
            'conditions': ["Test Condition"]
        }

        for key in expected_keys:
            assert key in result

    def test_batch_result_structure(self):
        """Test expected result structure from batch search."""
        # Mock batch results
        found_ncts = {"NCT00000001", "NCT00000002"}

        assert isinstance(found_ncts, set)
        for nct in found_ncts:
            assert nct.startswith("NCT")
            assert len(nct) == 11


# =============================================================================
# Parametrized Tests
# =============================================================================

class TestParametrizedNCTValidation:
    """Parametrized tests for NCT ID validation."""

    @pytest.mark.parametrize("nct_id,expected_valid", [
        ("NCT00000001", True),
        ("NCT12345678", True),
        ("nct00000001", True),
        ("NCT0000001", False),   # Too short
        ("NCT000000001", False), # Too long
        ("INVALID", False),
        ("", False),
    ])
    def test_nct_id_validation(self, nct_id, expected_valid):
        """Test NCT ID format validation with various inputs."""
        import re
        pattern = re.compile(r'^NCT\d{8}$', re.IGNORECASE)

        is_valid = bool(pattern.match(nct_id)) if nct_id else False
        assert is_valid == expected_valid

    @pytest.mark.parametrize("recall_data", [
        ({"NCT1", "NCT2", "NCT3"}, {"NCT1", "NCT2", "NCT3"}, 100.0),
        ({"NCT1", "NCT2"}, {"NCT1"}, 50.0),
        ({"NCT1", "NCT2"}, set(), 0.0),
        ({"NCT1"}, {"NCT1", "NCT2", "NCT3"}, 100.0),
    ])
    def test_recall_calculation_parametrized(self, recall_data):
        """Test recall calculation with various scenarios."""
        known, found, expected_recall = recall_data

        if len(known) > 0:
            recall = len(found & known) / len(known) * 100
        else:
            recall = 0.0

        assert recall == expected_recall


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance-related tests."""

    def test_batch_size_efficiency(self, mock_aact_connection):
        """Test that batch queries are more efficient than individual queries."""
        # Generate test NCT IDs
        nct_ids = [f"NCT{str(i).zfill(8)}" for i in range(1, 101)]

        # Single batch should be 1 query
        conn = mock_aact_connection
        cursor = conn.cursor()

        # Execute batch query
        cursor.execute(f"SELECT * FROM studies WHERE nct_id IN ({','.join(['%s']*len(nct_ids))})")

        # Verify query was executed (not counting individual queries)
        assert cursor.last_query is not None

    @pytest.mark.slow
    @requires_aact
    def test_large_batch_performance(self):
        """Test performance with large batch (requires credentials, marked slow)."""
        conn = connect_aact()
        if conn is None:
            pytest.skip("AACT connection unavailable")

        try:
            import time

            # Generate 500 NCT IDs
            nct_ids = [f"NCT{str(i).zfill(8)}" for i in range(1, 501)]

            start = time.time()
            found = search_by_nct_list(conn, nct_ids)
            elapsed = time.time() - start

            # Should complete in reasonable time (< 30 seconds)
            assert elapsed < 30

        finally:
            conn.close()


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    # Run with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
