"""
Tests for ctgov_search.py - CTGovSearcher class and search strategies.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ctgov_search import CTGovSearcher, SearchResult, RecallMetrics  # noqa: E402


class FakeResponse:
    """Mock HTTP response for testing."""

    def __init__(self, payload, status_code=200, url="https://clinicaltrials.gov/api/v2/studies"):
        self._payload = payload
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP Error: {self.status_code}")

    def json(self):
        return self._payload


class TestSearchResult(unittest.TestCase):
    """Test the SearchResult dataclass."""

    def test_search_result_creation(self):
        result = SearchResult(
            strategy_id="S1",
            strategy_name="Condition Only",
            condition="diabetes",
            total_count=1000,
            query_url="https://example.com",
            execution_time=0.5
        )
        self.assertEqual(result.strategy_id, "S1")
        self.assertEqual(result.total_count, 1000)
        self.assertEqual(result.studies, [])
        self.assertIsNone(result.error)

    def test_search_result_with_error(self):
        result = SearchResult(
            strategy_id="S1",
            strategy_name="Condition Only",
            condition="diabetes",
            total_count=0,
            query_url="https://example.com",
            execution_time=0.1,
            error="Connection timeout"
        )
        self.assertEqual(result.error, "Connection timeout")
        self.assertEqual(result.total_count, 0)


class TestRecallMetrics(unittest.TestCase):
    """Test the RecallMetrics dataclass."""

    def test_recall_metrics_creation(self):
        metrics = RecallMetrics(
            strategy_id="S1",
            total_known=10,
            found=8,
            recall=80.0,
            nct_ids_found=["NCT00000001", "NCT00000002"],
            nct_ids_missed=["NCT00000003"]
        )
        self.assertEqual(metrics.strategy_id, "S1")
        self.assertEqual(metrics.total_known, 10)
        self.assertEqual(metrics.found, 8)
        self.assertEqual(metrics.recall, 80.0)


class TestCTGovSearcherStrategies(unittest.TestCase):
    """Test CTGovSearcher strategy definitions."""

    def test_all_strategies_defined(self):
        """All 10 strategies should be defined."""
        self.assertEqual(len(CTGovSearcher.STRATEGIES), 10)
        expected_ids = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"]
        for sid in expected_ids:
            self.assertIn(sid, CTGovSearcher.STRATEGIES)

    def test_strategy_structure(self):
        """Each strategy should have required keys."""
        required_keys = ["name", "description", "retention", "sensitivity", "build_query"]
        for sid, strategy in CTGovSearcher.STRATEGIES.items():
            for key in required_keys:
                self.assertIn(key, strategy, f"Strategy {sid} missing key: {key}")

    def test_strategy_build_query_callable(self):
        """build_query should be callable and return string."""
        for sid, strategy in CTGovSearcher.STRATEGIES.items():
            query_fn = strategy["build_query"]
            self.assertTrue(callable(query_fn))
            result = query_fn("diabetes", None)
            self.assertIsInstance(result, str)
            self.assertIn("diabetes", result.lower() or result)


class TestCTGovSearcherHelperMethods(unittest.TestCase):
    """Test CTGovSearcher static helper methods."""

    def test_clamp_page_size_minimum(self):
        """Page size should be clamped to minimum of 1."""
        self.assertEqual(CTGovSearcher._clamp_page_size(0), 1)
        self.assertEqual(CTGovSearcher._clamp_page_size(-5), 1)
        self.assertEqual(CTGovSearcher._clamp_page_size(None), 1)

    def test_clamp_page_size_maximum(self):
        """Page size should be clamped to maximum of 1000."""
        self.assertEqual(CTGovSearcher._clamp_page_size(2000), 1000)
        self.assertEqual(CTGovSearcher._clamp_page_size(1500), 1000)

    def test_clamp_page_size_valid(self):
        """Valid page sizes should be unchanged."""
        self.assertEqual(CTGovSearcher._clamp_page_size(100), 100)
        self.assertEqual(CTGovSearcher._clamp_page_size(500), 500)
        self.assertEqual(CTGovSearcher._clamp_page_size(1000), 1000)

    def test_normalize_nct_ids_valid(self):
        """Valid NCT IDs should be normalized to uppercase."""
        valid, invalid = CTGovSearcher._normalize_nct_ids(["nct00000001", "NCT00000002"])
        self.assertEqual(valid, ["NCT00000001", "NCT00000002"])
        self.assertEqual(invalid, [])

    def test_normalize_nct_ids_invalid(self):
        """Invalid NCT IDs should be separated."""
        valid, invalid = CTGovSearcher._normalize_nct_ids(["NCT00000001", "INVALID123", "NCT0001"])
        self.assertEqual(valid, ["NCT00000001"])
        self.assertEqual(invalid, ["INVALID123", "NCT0001"])

    def test_normalize_nct_ids_duplicates(self):
        """Duplicate NCT IDs should be removed."""
        valid, invalid = CTGovSearcher._normalize_nct_ids(
            ["NCT00000001", "nct00000001", "NCT00000001"]
        )
        self.assertEqual(valid, ["NCT00000001"])
        self.assertEqual(invalid, [])

    def test_normalize_nct_ids_empty_and_none(self):
        """Empty strings and None values should be ignored."""
        valid, invalid = CTGovSearcher._normalize_nct_ids(["", None, "  ", "NCT00000001"])
        self.assertEqual(valid, ["NCT00000001"])
        self.assertEqual(invalid, [])

    def test_normalize_nct_ids_whitespace(self):
        """Whitespace should be stripped."""
        valid, invalid = CTGovSearcher._normalize_nct_ids(["  NCT00000001  ", "\tNCT00000002\n"])
        self.assertEqual(valid, ["NCT00000001", "NCT00000002"])


class TestCTGovSearcherSearch(unittest.TestCase):
    """Test CTGovSearcher.search method."""

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    def test_search_success(self, mock_synonyms, mock_get_session):
        """Test successful search execution."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        mock_response = FakeResponse({"totalCount": 500, "studies": []})
        mock_session.get.return_value = mock_response

        searcher = CTGovSearcher()
        result = searcher.search("diabetes", strategy="S1")

        self.assertEqual(result.strategy_id, "S1")
        self.assertEqual(result.total_count, 500)
        self.assertIsNone(result.error)
        self.assertEqual(result.condition, "diabetes")

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    def test_search_invalid_strategy(self, mock_synonyms, mock_get_session):
        """Test search with invalid strategy raises ValueError."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        searcher = CTGovSearcher()
        with self.assertRaises(ValueError) as ctx:
            searcher.search("diabetes", strategy="S99")

        self.assertIn("Unknown strategy", str(ctx.exception))

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    def test_search_with_studies(self, mock_synonyms, mock_get_session):
        """Test search returning study details."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        studies = [
            {"protocolSection": {"identificationModule": {"nctId": "NCT00000001"}}}
        ]
        mock_response = FakeResponse({"totalCount": 1, "studies": studies})
        mock_session.get.return_value = mock_response

        searcher = CTGovSearcher()
        result = searcher.search("diabetes", strategy="S1", return_studies=True)

        self.assertEqual(len(result.studies), 1)

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    def test_search_error_handling(self, mock_synonyms, mock_get_session):
        """Test search handles errors gracefully."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        mock_session.get.side_effect = Exception("Network error")

        searcher = CTGovSearcher()
        result = searcher.search("diabetes", strategy="S1")

        self.assertEqual(result.total_count, 0)
        self.assertIsNotNone(result.error)
        self.assertIn("Network error", result.error)


class TestCTGovSearcherCompareStrategies(unittest.TestCase):
    """Test CTGovSearcher.compare_all_strategies method."""

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    @patch("ctgov_search.time.sleep")
    def test_compare_all_strategies(self, mock_sleep, mock_synonyms, mock_get_session):
        """Test comparing all strategies."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        # Return different counts for different strategies
        mock_response = FakeResponse({"totalCount": 100, "studies": []})
        mock_session.get.return_value = mock_response

        searcher = CTGovSearcher()
        results = searcher.compare_all_strategies("diabetes")

        self.assertEqual(len(results), 10)  # All 10 strategies
        for result in results:
            self.assertIsInstance(result, SearchResult)


class TestCTGovSearcherSearchWithSynonyms(unittest.TestCase):
    """Test CTGovSearcher.search_with_synonyms method."""

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    def test_search_with_synonyms(self, mock_synonyms, mock_get_session):
        """Test synonym expansion search."""
        mock_synonyms.return_value = {
            "diabetes": ["diabetes mellitus", "type 2 diabetes", "t2dm"]
        }
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        mock_response = FakeResponse({"totalCount": 1000, "studies": []})
        mock_session.get.return_value = mock_response

        searcher = CTGovSearcher()
        result = searcher.search_with_synonyms("diabetes", strategy="S1")

        self.assertIn("synonyms", result.strategy_id)
        self.assertIn("4 terms", result.strategy_name)  # 1 base + 3 synonyms

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    def test_search_with_synonyms_no_matches(self, mock_synonyms, mock_get_session):
        """Test synonym search when no synonyms exist."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        mock_response = FakeResponse({"totalCount": 500, "studies": []})
        mock_session.get.return_value = mock_response

        searcher = CTGovSearcher()
        result = searcher.search_with_synonyms("rare_condition", strategy="S1")

        self.assertIn("1 terms", result.strategy_name)  # Only base term


class TestCTGovSearcherValidateNctIds(unittest.TestCase):
    """Test CTGovSearcher.validate_nct_ids method."""

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    @patch("ctgov_search.fetch_matching_nct_ids")
    def test_validate_nct_ids_found(self, mock_fetch, mock_synonyms, mock_get_session):
        """Test validating NCT IDs that exist."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        mock_fetch.return_value = {"NCT00000001", "NCT00000002"}

        searcher = CTGovSearcher()
        results = searcher.validate_nct_ids(["NCT00000001", "NCT00000002", "NCT00000003"])

        self.assertTrue(results["NCT00000001"])
        self.assertTrue(results["NCT00000002"])
        self.assertFalse(results["NCT00000003"])

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    def test_validate_nct_ids_invalid_format(self, mock_synonyms, mock_get_session):
        """Test validating invalid NCT ID formats."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        searcher = CTGovSearcher()
        results = searcher.validate_nct_ids(["INVALID", "NCT123"])

        self.assertFalse(results["INVALID"])
        self.assertFalse(results["NCT123"])


class TestCTGovSearcherGetStudyDetails(unittest.TestCase):
    """Test CTGovSearcher.get_study_details method."""

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    def test_get_study_details_success(self, mock_synonyms, mock_get_session):
        """Test fetching study details."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        study_data = {"protocolSection": {"identificationModule": {"nctId": "NCT00000001"}}}
        mock_response = FakeResponse(study_data)
        mock_session.get.return_value = mock_response

        searcher = CTGovSearcher()
        result = searcher.get_study_details("NCT00000001")

        self.assertIsNotNone(result)
        self.assertEqual(result["protocolSection"]["identificationModule"]["nctId"], "NCT00000001")

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    def test_get_study_details_not_found(self, mock_synonyms, mock_get_session):
        """Test fetching non-existent study."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        mock_session.get.side_effect = Exception("Not found")

        searcher = CTGovSearcher()
        result = searcher.get_study_details("NCT99999999")

        self.assertIsNone(result)


class TestCTGovSearcherCalculateRecall(unittest.TestCase):
    """Test CTGovSearcher.calculate_recall method."""

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    @patch("ctgov_search.fetch_matching_nct_ids")
    def test_calculate_recall_full(self, mock_fetch, mock_synonyms, mock_get_session):
        """Test calculate recall with 100% recall."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        mock_fetch.return_value = {"NCT00000001", "NCT00000002", "NCT00000003"}

        searcher = CTGovSearcher()
        metrics = searcher.calculate_recall(
            "diabetes",
            ["NCT00000001", "NCT00000002", "NCT00000003"],
            strategy="S1"
        )

        self.assertEqual(metrics.recall, 100.0)
        self.assertEqual(metrics.found, 3)
        self.assertEqual(metrics.total_known, 3)
        self.assertEqual(len(metrics.nct_ids_missed), 0)

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    @patch("ctgov_search.fetch_matching_nct_ids")
    def test_calculate_recall_partial(self, mock_fetch, mock_synonyms, mock_get_session):
        """Test calculate recall with partial recall."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        mock_fetch.return_value = {"NCT00000001"}

        searcher = CTGovSearcher()
        metrics = searcher.calculate_recall(
            "diabetes",
            ["NCT00000001", "NCT00000002"],
            strategy="S1"
        )

        self.assertEqual(metrics.recall, 50.0)
        self.assertEqual(metrics.found, 1)
        self.assertIn("NCT00000002", metrics.nct_ids_missed)


class TestCTGovSearcherSearchByNctIds(unittest.TestCase):
    """Test CTGovSearcher.search_by_nct_ids method."""

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    @patch("ctgov_search.fetch_studies")
    def test_search_by_nct_ids(self, mock_fetch_studies, mock_synonyms, mock_get_session):
        """Test searching by specific NCT IDs."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        studies = [
            {"protocolSection": {"identificationModule": {"nctId": "NCT00000001"}}},
            {"protocolSection": {"identificationModule": {"nctId": "NCT00000002"}}}
        ]
        mock_fetch_studies.return_value = (studies, 2)

        searcher = CTGovSearcher()
        result = searcher.search_by_nct_ids(["NCT00000001", "NCT00000002"])

        self.assertEqual(result.strategy_id, "NCT_LOOKUP")
        self.assertEqual(result.total_count, 2)

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    def test_search_by_nct_ids_empty(self, mock_synonyms, mock_get_session):
        """Test searching with no valid NCT IDs."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        searcher = CTGovSearcher()
        result = searcher.search_by_nct_ids(["INVALID"])

        self.assertEqual(result.total_count, 0)
        self.assertIn("No valid NCT IDs", result.error)


class TestCTGovSearcherExport(unittest.TestCase):
    """Test CTGovSearcher export methods."""

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    def test_export_results_csv(self, mock_synonyms, mock_get_session):
        """Test CSV export."""
        import tempfile
        import os

        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        searcher = CTGovSearcher()
        results = [
            SearchResult("S1", "Test", "diabetes", 100, "http://test.com", 0.5),
            SearchResult("S2", "Test2", "diabetes", 50, "http://test2.com", 0.3)
        ]

        fd, path = tempfile.mkstemp(suffix=".csv")
        try:
            os.close(fd)
            searcher.export_results_csv(results, path)

            with open(path, 'r') as f:
                content = f.read()
                self.assertIn("S1", content)
                self.assertIn("S2", content)
                self.assertIn("diabetes", content)
        finally:
            os.remove(path)

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    @patch("ctgov_search.time.sleep")
    def test_generate_search_report(self, mock_sleep, mock_synonyms, mock_get_session):
        """Test report generation."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        mock_response = FakeResponse({"totalCount": 100, "studies": []})
        mock_session.get.return_value = mock_response

        searcher = CTGovSearcher()
        report = searcher.generate_search_report("diabetes")

        self.assertIn("DIABETES", report)
        self.assertIn("RECOMMENDATIONS", report)
        self.assertIn("S1", report)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    def test_empty_condition(self, mock_synonyms, mock_get_session):
        """Test searching with empty condition."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        mock_response = FakeResponse({"totalCount": 0, "studies": []})
        mock_session.get.return_value = mock_response

        searcher = CTGovSearcher()
        result = searcher.search("", strategy="S1")

        self.assertEqual(result.condition, "")

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    def test_special_characters_in_condition(self, mock_synonyms, mock_get_session):
        """Test searching with special characters."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        mock_response = FakeResponse({"totalCount": 10, "studies": []})
        mock_session.get.return_value = mock_response

        searcher = CTGovSearcher()
        result = searcher.search("Crohn's disease", strategy="S1")

        self.assertEqual(result.condition, "Crohn's disease")

    @patch("ctgov_search.get_session")
    @patch("ctgov_search.load_synonyms")
    def test_unicode_in_condition(self, mock_synonyms, mock_get_session):
        """Test searching with unicode characters."""
        mock_synonyms.return_value = {}
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        mock_response = FakeResponse({"totalCount": 5, "studies": []})
        mock_session.get.return_value = mock_response

        searcher = CTGovSearcher()
        result = searcher.search("Sjogren syndrome", strategy="S1")

        self.assertIsNone(result.error)


if __name__ == "__main__":
    unittest.main()
