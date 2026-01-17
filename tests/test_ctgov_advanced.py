"""
Tests for ctgov_advanced.py - Advanced search strategies with combination/hybrid approaches.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ctgov_advanced import (  # noqa: E402
    SearchResult,
    RecallResult,
    AdvancedSearcher,
    EfficientPresenter,
)


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


class TestSearchResultDataclass(unittest.TestCase):
    """Test the SearchResult dataclass."""

    def test_search_result_creation(self):
        """Test basic creation of SearchResult."""
        result = SearchResult(
            strategy_id="S1",
            strategy_name="Condition Only",
            condition="diabetes",
            total_count=500,
            nct_ids=["NCT00000001", "NCT00000002"],
            execution_time=1.5
        )
        self.assertEqual(result.strategy_id, "S1")
        self.assertEqual(result.strategy_name, "Condition Only")
        self.assertEqual(result.condition, "diabetes")
        self.assertEqual(result.total_count, 500)
        self.assertEqual(len(result.nct_ids), 2)
        self.assertEqual(result.execution_time, 1.5)
        self.assertIsNone(result.error)

    def test_search_result_with_error(self):
        """Test SearchResult with error."""
        result = SearchResult(
            strategy_id="S1",
            strategy_name="Condition Only",
            condition="diabetes",
            total_count=0,
            error="Network timeout"
        )
        self.assertEqual(result.error, "Network timeout")
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.nct_ids, [])

    def test_search_result_default_values(self):
        """Test SearchResult default values."""
        result = SearchResult(
            strategy_id="S1",
            strategy_name="Test",
            condition="test",
            total_count=0
        )
        self.assertEqual(result.nct_ids, [])
        self.assertEqual(result.execution_time, 0.0)
        self.assertIsNone(result.error)


class TestRecallResultDataclass(unittest.TestCase):
    """Test the RecallResult dataclass."""

    def test_recall_result_creation(self):
        """Test basic creation of RecallResult."""
        result = RecallResult(
            strategy_id="S1",
            known=100,
            found=80,
            missed=20,
            recall=80.0,
            precision_proxy=10.0,
            f1_score=17.78
        )
        self.assertEqual(result.strategy_id, "S1")
        self.assertEqual(result.known, 100)
        self.assertEqual(result.found, 80)
        self.assertEqual(result.missed, 20)
        self.assertEqual(result.recall, 80.0)
        self.assertEqual(result.precision_proxy, 10.0)
        self.assertAlmostEqual(result.f1_score, 17.78, places=2)

    def test_recall_result_perfect_recall(self):
        """Test RecallResult with perfect recall."""
        result = RecallResult(
            strategy_id="S1",
            known=50,
            found=50,
            missed=0,
            recall=100.0,
            precision_proxy=5.0,
            f1_score=9.52
        )
        self.assertEqual(result.recall, 100.0)
        self.assertEqual(result.missed, 0)


class TestAdvancedSearcherBaseStrategies(unittest.TestCase):
    """Test AdvancedSearcher base strategy definitions."""

    def test_base_strategies_defined(self):
        """Base strategies should be defined."""
        searcher = AdvancedSearcher()
        expected_ids = ["S1", "S2", "S3", "S4", "S5", "S6", "S10"]
        for sid in expected_ids:
            self.assertIn(sid, searcher.BASE_STRATEGIES)

    def test_base_strategy_structure(self):
        """Each base strategy should have name and query function."""
        searcher = AdvancedSearcher()
        for sid, (name, query_fn) in searcher.BASE_STRATEGIES.items():
            self.assertIsInstance(name, str)
            self.assertTrue(callable(query_fn))

    def test_base_strategy_query_functions(self):
        """Query functions should return valid query strings."""
        searcher = AdvancedSearcher()
        for sid, (name, query_fn) in searcher.BASE_STRATEGIES.items():
            query = query_fn("diabetes")
            self.assertIsInstance(query, str)
            self.assertTrue(len(query) > 0)


class TestAdvancedSearcherComboStrategies(unittest.TestCase):
    """Test AdvancedSearcher combination strategy definitions."""

    def test_combo_strategies_defined(self):
        """Combination strategies should be defined."""
        searcher = AdvancedSearcher()
        expected_ids = ["C1", "C2", "C3", "C4", "C5", "C6"]
        for cid in expected_ids:
            self.assertIn(cid, searcher.COMBO_STRATEGIES)

    def test_combo_strategy_structure(self):
        """Each combo strategy should have name and list of base strategies."""
        searcher = AdvancedSearcher()
        for cid, (name, base_ids) in searcher.COMBO_STRATEGIES.items():
            self.assertIsInstance(name, str)
            self.assertIsInstance(base_ids, list)
            self.assertTrue(len(base_ids) >= 2)

    def test_combo_strategies_reference_valid_base(self):
        """Combo strategies should only reference valid base strategies."""
        searcher = AdvancedSearcher()
        for cid, (name, base_ids) in searcher.COMBO_STRATEGIES.items():
            for base_id in base_ids:
                self.assertIn(
                    base_id,
                    searcher.BASE_STRATEGIES,
                    f"Combo {cid} references invalid base {base_id}"
                )


class TestAdvancedSearcherCaching(unittest.TestCase):
    """Test AdvancedSearcher caching functionality."""

    def test_cache_initialized(self):
        """Cache should be initialized as empty dict."""
        searcher = AdvancedSearcher()
        self.assertEqual(searcher.cache, {})

    def test_cache_lock_exists(self):
        """Cache lock should be initialized."""
        searcher = AdvancedSearcher()
        self.assertIsInstance(searcher.cache_lock, type(threading.Lock()))


class TestAdvancedSearcherSearchSingle(unittest.TestCase):
    """Test AdvancedSearcher._search_single method."""

    @patch("ctgov_advanced.get_session")
    @patch("ctgov_advanced.fetch_nct_ids")
    def test_search_single_success(self, mock_fetch, mock_get_session):
        """Test successful single search."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        mock_fetch.return_value = ({"NCT00000001", "NCT00000002"}, 2)

        searcher = AdvancedSearcher()
        result = searcher._search_single("diabetes", "S1")

        self.assertEqual(result.strategy_id, "S1")
        self.assertEqual(result.total_count, 2)
        self.assertIsNone(result.error)

    @patch("ctgov_advanced.get_session")
    @patch("ctgov_advanced.fetch_nct_ids")
    def test_search_single_cached(self, mock_fetch, mock_get_session):
        """Test that results are cached."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        mock_fetch.return_value = ({"NCT00000001"}, 1)

        searcher = AdvancedSearcher()

        # First call
        result1 = searcher._search_single("diabetes", "S1")

        # Second call should use cache
        result2 = searcher._search_single("diabetes", "S1")

        self.assertEqual(result1.total_count, result2.total_count)
        # fetch_nct_ids should only be called once
        self.assertEqual(mock_fetch.call_count, 1)

    def test_search_single_unknown_strategy(self):
        """Test search with unknown strategy."""
        searcher = AdvancedSearcher()
        result = searcher._search_single("diabetes", "S99")

        self.assertEqual(result.total_count, 0)
        self.assertIn("Unknown strategy", result.error)

    @patch("ctgov_advanced.get_session")
    @patch("ctgov_advanced.fetch_nct_ids")
    def test_search_single_error_handling(self, mock_fetch, mock_get_session):
        """Test error handling in single search."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        mock_fetch.side_effect = Exception("Network error")

        searcher = AdvancedSearcher()
        result = searcher._search_single("diabetes", "S1")

        self.assertEqual(result.total_count, 0)
        self.assertIn("Network error", result.error)


class TestAdvancedSearcherSearchParallel(unittest.TestCase):
    """Test AdvancedSearcher.search_parallel method."""

    @patch("ctgov_advanced.get_session")
    @patch("ctgov_advanced.fetch_nct_ids")
    def test_search_parallel_default_strategies(self, mock_fetch, mock_get_session):
        """Test parallel search with default strategies."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        mock_fetch.return_value = ({"NCT00000001"}, 1)

        searcher = AdvancedSearcher()
        results = searcher.search_parallel("diabetes")

        # Should have results for all base strategies
        self.assertEqual(len(results), len(searcher.BASE_STRATEGIES))

    @patch("ctgov_advanced.get_session")
    @patch("ctgov_advanced.fetch_nct_ids")
    def test_search_parallel_specific_strategies(self, mock_fetch, mock_get_session):
        """Test parallel search with specific strategies."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        mock_fetch.return_value = ({"NCT00000001"}, 1)

        searcher = AdvancedSearcher()
        results = searcher.search_parallel("diabetes", strategies=["S1", "S2"])

        self.assertEqual(len(results), 2)
        self.assertIn("S1", results)
        self.assertIn("S2", results)


class TestAdvancedSearcherSearchCombination(unittest.TestCase):
    """Test AdvancedSearcher.search_combination method."""

    @patch("ctgov_advanced.get_session")
    @patch("ctgov_advanced.fetch_nct_ids")
    def test_search_combination_union(self, mock_fetch, mock_get_session):
        """Test combination strategy unions NCT IDs."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        # Different NCT IDs for different strategies
        call_count = [0]

        def mock_fetch_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return ({"NCT00000001", "NCT00000002"}, 2)
            else:
                return ({"NCT00000002", "NCT00000003"}, 2)

        mock_fetch.side_effect = mock_fetch_side_effect

        searcher = AdvancedSearcher()
        result = searcher.search_combination("diabetes", "C1")

        # Should be union of both sets
        self.assertEqual(result.total_count, 3)  # NCT1, NCT2, NCT3
        self.assertIn("NCT00000001", result.nct_ids)
        self.assertIn("NCT00000003", result.nct_ids)

    def test_search_combination_unknown_combo(self):
        """Test combination with unknown combo ID."""
        searcher = AdvancedSearcher()
        result = searcher.search_combination("diabetes", "C99")

        self.assertEqual(result.total_count, 0)
        self.assertIn("Unknown combo", result.error)


class TestAdvancedSearcherSearchAll(unittest.TestCase):
    """Test AdvancedSearcher.search_all method."""

    @patch("ctgov_advanced.get_session")
    @patch("ctgov_advanced.fetch_nct_ids")
    def test_search_all_returns_all_strategies(self, mock_fetch, mock_get_session):
        """Test search_all returns both base and combo strategies."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        mock_fetch.return_value = ({"NCT00000001"}, 1)

        searcher = AdvancedSearcher()
        results = searcher.search_all("diabetes")

        # Should have all base and combo strategies
        expected_count = len(searcher.BASE_STRATEGIES) + len(searcher.COMBO_STRATEGIES)
        self.assertEqual(len(results), expected_count)


class TestAdvancedSearcherCalculateRecall(unittest.TestCase):
    """Test AdvancedSearcher.calculate_recall method."""

    def test_calculate_recall_full(self):
        """Test calculate_recall with 100% recall."""
        searcher = AdvancedSearcher()
        search_result = SearchResult(
            strategy_id="S1",
            strategy_name="Test",
            condition="diabetes",
            total_count=100,
            nct_ids=["NCT00000001", "NCT00000002", "NCT00000003"]
        )
        known_ids = {"NCT00000001", "NCT00000002", "NCT00000003"}

        recall_result = searcher.calculate_recall(search_result, known_ids)

        self.assertEqual(recall_result.recall, 100.0)
        self.assertEqual(recall_result.found, 3)
        self.assertEqual(recall_result.missed, 0)

    def test_calculate_recall_partial(self):
        """Test calculate_recall with partial recall."""
        searcher = AdvancedSearcher()
        search_result = SearchResult(
            strategy_id="S1",
            strategy_name="Test",
            condition="diabetes",
            total_count=50,
            nct_ids=["NCT00000001"]
        )
        known_ids = {"NCT00000001", "NCT00000002"}

        recall_result = searcher.calculate_recall(search_result, known_ids)

        self.assertEqual(recall_result.recall, 50.0)
        self.assertEqual(recall_result.found, 1)
        self.assertEqual(recall_result.missed, 1)

    def test_calculate_recall_zero(self):
        """Test calculate_recall with 0% recall."""
        searcher = AdvancedSearcher()
        search_result = SearchResult(
            strategy_id="S1",
            strategy_name="Test",
            condition="diabetes",
            total_count=100,
            nct_ids=["NCT00000099"]
        )
        known_ids = {"NCT00000001", "NCT00000002"}

        recall_result = searcher.calculate_recall(search_result, known_ids)

        self.assertEqual(recall_result.recall, 0.0)
        self.assertEqual(recall_result.found, 0)
        self.assertEqual(recall_result.missed, 2)

    def test_calculate_recall_empty_known(self):
        """Test calculate_recall with empty known set."""
        searcher = AdvancedSearcher()
        search_result = SearchResult(
            strategy_id="S1",
            strategy_name="Test",
            condition="diabetes",
            total_count=100,
            nct_ids=["NCT00000001"]
        )

        recall_result = searcher.calculate_recall(search_result, set())

        self.assertEqual(recall_result.recall, 0.0)

    def test_calculate_recall_precision_proxy(self):
        """Test precision proxy calculation."""
        searcher = AdvancedSearcher()
        search_result = SearchResult(
            strategy_id="S1",
            strategy_name="Test",
            condition="diabetes",
            total_count=100,
            nct_ids=["NCT00000001", "NCT00000002"]
        )
        known_ids = {"NCT00000001", "NCT00000002"}

        recall_result = searcher.calculate_recall(search_result, known_ids)

        # precision_proxy = found/total_count * 100 = 2/100 * 100 = 2.0
        self.assertEqual(recall_result.precision_proxy, 2.0)

    def test_calculate_recall_f1_score(self):
        """Test F1 score calculation."""
        searcher = AdvancedSearcher()
        search_result = SearchResult(
            strategy_id="S1",
            strategy_name="Test",
            condition="diabetes",
            total_count=10,
            nct_ids=["NCT00000001", "NCT00000002"]
        )
        known_ids = {"NCT00000001", "NCT00000002"}

        recall_result = searcher.calculate_recall(search_result, known_ids)

        # recall = 100%, precision_proxy = 20%
        # F1 = 2 * (100 * 20) / (100 + 20) = 4000/120 = 33.33
        self.assertAlmostEqual(recall_result.f1_score, 33.33, places=1)

    def test_calculate_recall_case_sensitivity(self):
        """Test NCT ID comparison - known_ids are uppercased but search results are not."""
        searcher = AdvancedSearcher()
        # The actual implementation uppercases known_ids but not search result nct_ids
        # So uppercase in search results will match, but lowercase will not
        search_result = SearchResult(
            strategy_id="S1",
            strategy_name="Test",
            condition="diabetes",
            total_count=10,
            nct_ids=["NCT00000001", "NCT00000002"]  # uppercase matches
        )
        known_ids = {"nct00000001", "nct00000002"}  # lowercase - will be uppercased

        recall_result = searcher.calculate_recall(search_result, known_ids)

        # Both should match since known_ids are uppercased
        self.assertEqual(recall_result.recall, 100.0)


class TestAdvancedSearcherOptimizeStrategy(unittest.TestCase):
    """Test AdvancedSearcher.optimize_strategy method."""

    @patch("ctgov_advanced.get_session")
    @patch("ctgov_advanced.fetch_nct_ids")
    def test_optimize_strategy_finds_best(self, mock_fetch, mock_get_session):
        """Test that optimize_strategy finds the best strategy by F1."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        # Make S3 have the best results
        def mock_fetch_side_effect(session, params, **kwargs):
            query = params.get("query.term", "")
            if "RANDOMIZED" in query:
                return ({"NCT00000001", "NCT00000002"}, 2)
            return ({"NCT00000001"}, 10)

        mock_fetch.side_effect = mock_fetch_side_effect

        searcher = AdvancedSearcher()
        known_ids = {"NCT00000001", "NCT00000002"}

        best_strategy, recall_result = searcher.optimize_strategy("diabetes", known_ids)

        self.assertIsNotNone(best_strategy)
        self.assertIsNotNone(recall_result)


class TestEfficientPresenter(unittest.TestCase):
    """Test EfficientPresenter class."""

    def test_compact_comparison_format(self):
        """Test compact comparison table format."""
        results = {
            "S1": SearchResult("S1", "Condition Only", "diabetes", 1000, execution_time=1.0),
            "S2": SearchResult("S2", "Interventional", "diabetes", 750, execution_time=0.8)
        }

        table = EfficientPresenter.compact_comparison(results, baseline_id="S1")

        self.assertIn("S1", table)
        self.assertIn("S2", table)
        self.assertIn("1,000", table)
        self.assertIn("750", table)
        self.assertIn("100.0%", table)  # S1 baseline
        self.assertIn("75.0%", table)   # S2 percentage

    def test_compact_comparison_with_error(self):
        """Test compact comparison with error results."""
        results = {
            "S1": SearchResult("S1", "Condition Only", "diabetes", 1000),
            "S2": SearchResult("S2", "Error", "diabetes", 0, error="Network error")
        }

        table = EfficientPresenter.compact_comparison(results)

        self.assertIn("ERROR", table)
        self.assertIn("N/A", table)

    def test_recall_table_format(self):
        """Test recall table format."""
        recall_results = [
            RecallResult("S1", 100, 90, 10, 90.0, 5.0, 9.5),
            RecallResult("S2", 100, 80, 20, 80.0, 4.0, 7.6)
        ]

        table = EfficientPresenter.recall_table(recall_results)

        self.assertIn("S1", table)
        self.assertIn("S2", table)
        self.assertIn("90.0%", table)
        self.assertIn("80.0%", table)

    def test_recall_table_sorted_by_recall(self):
        """Test that recall table is sorted by recall descending."""
        recall_results = [
            RecallResult("S2", 100, 80, 20, 80.0, 4.0, 7.6),
            RecallResult("S1", 100, 90, 10, 90.0, 5.0, 9.5),
        ]

        table = EfficientPresenter.recall_table(recall_results)

        # S1 (90%) should appear before S2 (80%)
        s1_pos = table.find("90.0%")
        s2_pos = table.find("80.0%")
        self.assertLess(s1_pos, s2_pos)

    def test_quick_summary_format(self):
        """Test quick summary format."""
        recall = RecallResult("S1", 100, 90, 10, 90.0, 5.0, 9.5)

        summary = EfficientPresenter.quick_summary("diabetes", "S1", recall, 5.0)

        self.assertIn("diabetes", summary)
        self.assertIn("S1", summary)
        self.assertIn("90.0%", summary)
        self.assertIn("90/100", summary)
        self.assertIn("5.0s", summary)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_empty_nct_ids_list(self):
        """Test search result with empty NCT IDs."""
        result = SearchResult(
            strategy_id="S1",
            strategy_name="Test",
            condition="diabetes",
            total_count=0,
            nct_ids=[]
        )
        self.assertEqual(len(result.nct_ids), 0)

    def test_large_nct_ids_list(self):
        """Test search result with many NCT IDs."""
        nct_ids = [f"NCT{str(i).zfill(8)}" for i in range(10000)]
        result = SearchResult(
            strategy_id="S1",
            strategy_name="Test",
            condition="diabetes",
            total_count=10000,
            nct_ids=nct_ids
        )
        self.assertEqual(len(result.nct_ids), 10000)

    def test_special_characters_in_condition(self):
        """Test handling of special characters in condition."""
        searcher = AdvancedSearcher()
        # Query function should handle special characters
        for sid, (name, query_fn) in searcher.BASE_STRATEGIES.items():
            query = query_fn("Crohn's disease (active)")
            self.assertIsInstance(query, str)

    def test_unicode_in_condition(self):
        """Test handling of unicode in condition."""
        searcher = AdvancedSearcher()
        for sid, (name, query_fn) in searcher.BASE_STRATEGIES.items():
            query = query_fn("Sjogren's syndrome")
            self.assertIsInstance(query, str)

    def test_thread_safety_of_cache(self):
        """Test that cache operations are thread-safe."""
        searcher = AdvancedSearcher()

        # Simulate concurrent cache access
        results = []

        def cache_operation():
            with searcher.cache_lock:
                searcher.cache["test_key"] = SearchResult(
                    "S1", "Test", "test", 0
                )
                results.append(searcher.cache.get("test_key"))

        threads = [threading.Thread(target=cache_operation) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All operations should complete without error
        self.assertEqual(len(results), 10)


class TestCompactComparisonEdgeCases(unittest.TestCase):
    """Test edge cases in compact comparison."""

    def test_missing_baseline(self):
        """Test when baseline strategy is missing."""
        results = {
            "S2": SearchResult("S2", "Test", "diabetes", 100)
        }

        # Should not crash when S1 (default baseline) is missing
        table = EfficientPresenter.compact_comparison(results)
        self.assertIn("S2", table)

    def test_zero_baseline_count(self):
        """Test when baseline has zero count."""
        results = {
            "S1": SearchResult("S1", "Baseline", "diabetes", 0),
            "S2": SearchResult("S2", "Test", "diabetes", 100)
        }

        table = EfficientPresenter.compact_comparison(results, baseline_id="S1")
        # Should handle division by zero gracefully
        self.assertIn("S1", table)

    def test_empty_results(self):
        """Test with empty results dict."""
        results = {}
        table = EfficientPresenter.compact_comparison(results)
        # Should return a valid table structure
        self.assertIn("+", table)


if __name__ == "__main__":
    unittest.main()
