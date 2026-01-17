"""
Tests for ctgov_config.py - Configuration constants and settings.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ctgov_config import (  # noqa: E402
    CTGOV_API,
    DEFAULT_TIMEOUT,
    DEFAULT_PAGE_SIZE,
    DEFAULT_RATE_LIMIT,
    DEFAULT_USER_AGENT,
)


class TestApiConfiguration(unittest.TestCase):
    """Test API endpoint configuration."""

    def test_api_endpoint_is_valid_url(self):
        """CTGOV_API should be a valid HTTPS URL."""
        self.assertTrue(CTGOV_API.startswith("https://"))
        self.assertIn("clinicaltrials.gov", CTGOV_API)
        self.assertIn("api", CTGOV_API)

    def test_api_endpoint_is_v2(self):
        """CTGOV_API should use v2 of the API."""
        self.assertIn("/v2/", CTGOV_API)

    def test_api_endpoint_studies_path(self):
        """CTGOV_API should point to studies endpoint."""
        self.assertTrue(CTGOV_API.endswith("/studies"))


class TestTimeoutConfiguration(unittest.TestCase):
    """Test timeout configuration."""

    def test_timeout_is_positive_integer(self):
        """DEFAULT_TIMEOUT should be a positive integer."""
        self.assertIsInstance(DEFAULT_TIMEOUT, int)
        self.assertGreater(DEFAULT_TIMEOUT, 0)

    def test_timeout_is_reasonable(self):
        """DEFAULT_TIMEOUT should be reasonable (between 5 and 120 seconds)."""
        self.assertGreaterEqual(DEFAULT_TIMEOUT, 5)
        self.assertLessEqual(DEFAULT_TIMEOUT, 120)


class TestPageSizeConfiguration(unittest.TestCase):
    """Test page size configuration."""

    def test_page_size_is_positive_integer(self):
        """DEFAULT_PAGE_SIZE should be a positive integer."""
        self.assertIsInstance(DEFAULT_PAGE_SIZE, int)
        self.assertGreater(DEFAULT_PAGE_SIZE, 0)

    def test_page_size_within_api_limits(self):
        """DEFAULT_PAGE_SIZE should be within CT.gov API limits (max 1000)."""
        self.assertLessEqual(DEFAULT_PAGE_SIZE, 1000)

    def test_page_size_is_efficient(self):
        """DEFAULT_PAGE_SIZE should be efficient (at least 100)."""
        self.assertGreaterEqual(DEFAULT_PAGE_SIZE, 100)


class TestRateLimitConfiguration(unittest.TestCase):
    """Test rate limit configuration."""

    def test_rate_limit_is_numeric(self):
        """DEFAULT_RATE_LIMIT should be a number."""
        self.assertIsInstance(DEFAULT_RATE_LIMIT, (int, float))

    def test_rate_limit_is_non_negative(self):
        """DEFAULT_RATE_LIMIT should be non-negative."""
        self.assertGreaterEqual(DEFAULT_RATE_LIMIT, 0)

    def test_rate_limit_is_reasonable(self):
        """DEFAULT_RATE_LIMIT should be reasonable (between 0 and 5 seconds)."""
        self.assertLessEqual(DEFAULT_RATE_LIMIT, 5)


class TestUserAgentConfiguration(unittest.TestCase):
    """Test user agent configuration."""

    def test_user_agent_is_string(self):
        """DEFAULT_USER_AGENT should be a non-empty string."""
        self.assertIsInstance(DEFAULT_USER_AGENT, str)
        self.assertTrue(len(DEFAULT_USER_AGENT) > 0)

    def test_user_agent_is_descriptive(self):
        """DEFAULT_USER_AGENT should contain identifying information."""
        # Should contain tool name or similar identifier
        self.assertTrue(
            any(term in DEFAULT_USER_AGENT.lower() for term in ["ctgov", "search", "validator"]),
            "User agent should contain identifying information"
        )

    def test_user_agent_contains_version(self):
        """DEFAULT_USER_AGENT should contain a version number."""
        import re
        version_pattern = r'\d+\.\d+'
        self.assertTrue(
            re.search(version_pattern, DEFAULT_USER_AGENT),
            "User agent should contain version number"
        )


class TestConfigurationConsistency(unittest.TestCase):
    """Test that configuration values work well together."""

    def test_timeout_allows_page_fetch(self):
        """Timeout should be long enough to fetch a page of results."""
        # With max page size and slow network, should still have time
        min_reasonable_timeout = 10
        self.assertGreaterEqual(DEFAULT_TIMEOUT, min_reasonable_timeout)

    def test_rate_limit_prevents_throttling(self):
        """Rate limit should prevent API throttling (minimum delay)."""
        # CT.gov doesn't have strict rate limits, but some delay is good practice
        min_delay = 0.1
        self.assertGreaterEqual(DEFAULT_RATE_LIMIT, min_delay)

    def test_config_values_are_immutable_types(self):
        """Configuration values should be immutable."""
        # All config values should be basic immutable types
        self.assertIsInstance(CTGOV_API, str)
        self.assertIsInstance(DEFAULT_TIMEOUT, int)
        self.assertIsInstance(DEFAULT_PAGE_SIZE, int)
        self.assertIsInstance(DEFAULT_RATE_LIMIT, (int, float))
        self.assertIsInstance(DEFAULT_USER_AGENT, str)


class TestConfigurationImport(unittest.TestCase):
    """Test that configuration can be imported correctly."""

    def test_all_config_values_importable(self):
        """All expected configuration values should be importable."""
        # Re-import to test import mechanism
        from ctgov_config import (
            CTGOV_API,
            DEFAULT_TIMEOUT,
            DEFAULT_PAGE_SIZE,
            DEFAULT_RATE_LIMIT,
            DEFAULT_USER_AGENT,
        )

        # Verify values exist and are not None
        self.assertIsNotNone(CTGOV_API)
        self.assertIsNotNone(DEFAULT_TIMEOUT)
        self.assertIsNotNone(DEFAULT_PAGE_SIZE)
        self.assertIsNotNone(DEFAULT_RATE_LIMIT)
        self.assertIsNotNone(DEFAULT_USER_AGENT)


class TestConfigurationDocumentation(unittest.TestCase):
    """Test that configuration values are well-documented in practice."""

    def test_api_url_is_complete(self):
        """API URL should be a complete, usable endpoint."""
        # Should not have trailing slash or query params
        self.assertFalse(CTGOV_API.endswith("/"))
        self.assertNotIn("?", CTGOV_API)

    def test_values_are_documented_defaults(self):
        """Configuration values should match documented CT.gov practices."""
        # CT.gov API v2 max page size is 1000
        self.assertLessEqual(DEFAULT_PAGE_SIZE, 1000)

        # Standard HTTP timeout range
        self.assertIn(DEFAULT_TIMEOUT, range(1, 300))


class TestEdgeCases(unittest.TestCase):
    """Test edge cases in configuration."""

    def test_config_values_not_empty_strings(self):
        """String configuration values should not be empty."""
        self.assertTrue(len(CTGOV_API) > 0)
        self.assertTrue(len(DEFAULT_USER_AGENT) > 0)

    def test_numeric_configs_not_zero(self):
        """Numeric configuration values should not be zero (except rate limit)."""
        self.assertNotEqual(DEFAULT_TIMEOUT, 0)
        self.assertNotEqual(DEFAULT_PAGE_SIZE, 0)
        # Rate limit CAN be zero for no delay

    def test_api_url_no_whitespace(self):
        """API URL should not contain whitespace."""
        self.assertEqual(CTGOV_API, CTGOV_API.strip())
        self.assertNotIn(" ", CTGOV_API)
        self.assertNotIn("\t", CTGOV_API)
        self.assertNotIn("\n", CTGOV_API)


if __name__ == "__main__":
    unittest.main()
