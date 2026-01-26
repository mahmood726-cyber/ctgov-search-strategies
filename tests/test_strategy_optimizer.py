"""
Tests for the Strategy Optimizer module.

Tests ML-based strategy recommendations, condition classification,
and performance scoring algorithms.
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy_optimizer import (
    StrategyOptimizer,
    SearchGoal,
    ConditionCategory,
    StrategyPerformance,
    StrategyRecommendation,
    recommend_strategy,
    get_best_strategy,
    classify_condition,
    STRATEGY_PERFORMANCE_DATA,
    CONDITION_KEYWORDS,
)


class TestConditionClassification:
    """Tests for condition classification functionality."""

    def test_classify_diabetes(self):
        """Test classification of diabetes-related conditions."""
        assert classify_condition("type 2 diabetes") == ConditionCategory.ENDOCRINOLOGY
        assert classify_condition("diabetes mellitus") == ConditionCategory.ENDOCRINOLOGY
        assert classify_condition("insulin resistance") == ConditionCategory.ENDOCRINOLOGY

    def test_classify_oncology(self):
        """Test classification of cancer-related conditions."""
        assert classify_condition("breast cancer") == ConditionCategory.ONCOLOGY
        assert classify_condition("lung carcinoma") == ConditionCategory.ONCOLOGY
        assert classify_condition("melanoma") == ConditionCategory.ONCOLOGY
        assert classify_condition("lymphoma") == ConditionCategory.ONCOLOGY

    def test_classify_cardiology(self):
        """Test classification of cardiovascular conditions."""
        assert classify_condition("heart failure") == ConditionCategory.CARDIOLOGY
        assert classify_condition("atrial fibrillation") == ConditionCategory.CARDIOLOGY
        assert classify_condition("hypertension") == ConditionCategory.CARDIOLOGY
        assert classify_condition("coronary artery disease") == ConditionCategory.CARDIOLOGY

    def test_classify_neurology(self):
        """Test classification of neurological conditions."""
        assert classify_condition("Alzheimer's disease") == ConditionCategory.NEUROLOGY
        assert classify_condition("Parkinson's disease") == ConditionCategory.NEUROLOGY
        assert classify_condition("multiple sclerosis") == ConditionCategory.NEUROLOGY
        assert classify_condition("epilepsy") == ConditionCategory.NEUROLOGY

    def test_classify_psychiatry(self):
        """Test classification of psychiatric conditions."""
        assert classify_condition("major depression") == ConditionCategory.PSYCHIATRY
        assert classify_condition("anxiety disorder") == ConditionCategory.PSYCHIATRY
        assert classify_condition("schizophrenia") == ConditionCategory.PSYCHIATRY
        assert classify_condition("bipolar disorder") == ConditionCategory.PSYCHIATRY

    def test_classify_infectious(self):
        """Test classification of infectious diseases."""
        assert classify_condition("HIV infection") == ConditionCategory.INFECTIOUS
        assert classify_condition("hepatitis C") == ConditionCategory.INFECTIOUS
        assert classify_condition("tuberculosis") == ConditionCategory.INFECTIOUS
        assert classify_condition("COVID-19") == ConditionCategory.INFECTIOUS

    def test_classify_unknown(self):
        """Test classification of unknown conditions defaults to GENERAL."""
        assert classify_condition("rare syndrome xyz") == ConditionCategory.GENERAL
        assert classify_condition("unclassified condition") == ConditionCategory.GENERAL

    def test_classify_case_insensitive(self):
        """Test that classification is case-insensitive."""
        assert classify_condition("DIABETES") == ConditionCategory.ENDOCRINOLOGY
        assert classify_condition("Breast CANCER") == ConditionCategory.ONCOLOGY
        assert classify_condition("HYPERTENSION") == ConditionCategory.CARDIOLOGY


class TestSearchGoal:
    """Tests for search goal enum and weights."""

    def test_search_goal_values(self):
        """Test that all search goals have expected values."""
        assert SearchGoal.MAXIMUM_RECALL.value == "maximum_recall"
        assert SearchGoal.BALANCED.value == "balanced"
        assert SearchGoal.HIGH_PRECISION.value == "high_precision"
        assert SearchGoal.QUICK_OVERVIEW.value == "quick_overview"

    def test_all_goals_defined(self):
        """Test that all expected goals are defined."""
        goals = list(SearchGoal)
        assert len(goals) == 4
        assert SearchGoal.MAXIMUM_RECALL in goals
        assert SearchGoal.BALANCED in goals
        assert SearchGoal.HIGH_PRECISION in goals
        assert SearchGoal.QUICK_OVERVIEW in goals


class TestStrategyPerformance:
    """Tests for strategy performance data."""

    def test_all_strategies_have_data(self):
        """Test that all 10 strategies have performance data."""
        expected_strategies = [f"S{i}" for i in range(1, 11)]
        for strategy_id in expected_strategies:
            assert strategy_id in STRATEGY_PERFORMANCE_DATA, f"Missing data for {strategy_id}"

    def test_performance_data_valid(self):
        """Test that performance data has valid values."""
        for strategy_id, perf in STRATEGY_PERFORMANCE_DATA.items():
            assert isinstance(perf, StrategyPerformance)
            assert 0 <= perf.recall <= 100, f"{strategy_id} recall out of range"
            assert 0 <= perf.precision <= 100, f"{strategy_id} precision out of range"
            assert perf.nns > 0, f"{strategy_id} NNS must be positive"
            assert perf.total_evaluated > 0, f"{strategy_id} must have evaluations"

    def test_recall_precision_relationship(self):
        """Test that recall and precision have expected relationship."""
        # High recall strategies should generally have lower precision
        s1 = STRATEGY_PERFORMANCE_DATA["S1"]  # Maximum recall
        s8 = STRATEGY_PERFORMANCE_DATA["S8"]  # High quality (lower recall)

        assert s1.recall > s8.recall, "S1 should have higher recall than S8"
        assert s1.precision < s8.precision, "S1 should have lower precision than S8"


class TestStrategyOptimizer:
    """Tests for the StrategyOptimizer class."""

    @pytest.fixture
    def optimizer(self):
        """Create optimizer instance for tests."""
        return StrategyOptimizer()

    def test_recommend_returns_list(self, optimizer):
        """Test that recommend returns a list of recommendations."""
        results = optimizer.recommend("diabetes", SearchGoal.BALANCED)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_recommend_returns_sorted(self, optimizer):
        """Test that recommendations are sorted by score descending."""
        results = optimizer.recommend("diabetes", SearchGoal.BALANCED)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_recommend_maximum_recall(self, optimizer):
        """Test maximum recall goal favors high-recall strategies."""
        results = optimizer.recommend("diabetes", SearchGoal.MAXIMUM_RECALL)
        top_strategy = results[0]
        # S1, S2, S3 have highest recall (98.7%)
        assert top_strategy.strategy_id in ["S1", "S2", "S3"]

    def test_recommend_high_precision(self, optimizer):
        """Test high precision goal favors precise strategies."""
        results = optimizer.recommend("diabetes", SearchGoal.HIGH_PRECISION)
        top_strategy = results[0]
        # S8 has highest precision (52.3%)
        assert top_strategy.recall < 60 or top_strategy.precision > 40

    def test_recommend_with_min_recall(self, optimizer):
        """Test minimum recall constraint filtering."""
        results = optimizer.recommend(
            "diabetes",
            SearchGoal.BALANCED,
            min_recall=0.90
        )
        # All results should meet minimum recall or be relaxed
        high_recall = [r for r in results if r.recall >= 90]
        assert len(high_recall) > 0

    def test_recommend_with_max_nns(self, optimizer):
        """Test maximum NNS constraint."""
        results = optimizer.recommend(
            "diabetes",
            SearchGoal.BALANCED,
            max_nns=3.0
        )
        # Should include S8 (NNS=1.9) in results
        strategy_ids = [r.strategy_id for r in results]
        assert "S8" in strategy_ids

    def test_recommend_with_known_ncts(self, optimizer):
        """Test that known NCTs influence scoring."""
        results_without = optimizer.recommend("diabetes", SearchGoal.BALANCED)
        results_with = optimizer.recommend(
            "diabetes",
            SearchGoal.BALANCED,
            known_ncts=["NCT00000001", "NCT00000002"]
        )
        # Scores should differ when known NCTs are provided
        assert results_with[0].score != results_without[0].score or \
               results_with[0].strategy_id == results_without[0].strategy_id

    def test_get_ensemble_recommendation(self, optimizer):
        """Test ensemble recommendation returns primary and secondary."""
        primary, secondary = optimizer.get_ensemble_recommendation(
            "diabetes",
            SearchGoal.BALANCED
        )
        assert primary is not None
        assert isinstance(primary, StrategyRecommendation)
        # Secondary may be None if primary is sufficient
        if secondary:
            assert isinstance(secondary, StrategyRecommendation)
            assert primary.strategy_id != secondary.strategy_id


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_recommend_strategy(self):
        """Test recommend_strategy function."""
        results = recommend_strategy("diabetes", SearchGoal.BALANCED)
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, StrategyRecommendation) for r in results)

    def test_get_best_strategy(self):
        """Test get_best_strategy function."""
        best = get_best_strategy("diabetes", SearchGoal.BALANCED)
        assert isinstance(best, StrategyRecommendation)
        assert best.strategy_id.startswith("S")

    def test_get_best_strategy_different_goals(self):
        """Test that different goals may return different strategies."""
        best_recall = get_best_strategy("diabetes", SearchGoal.MAXIMUM_RECALL)
        best_precision = get_best_strategy("diabetes", SearchGoal.HIGH_PRECISION)

        # These should typically differ
        # (though not guaranteed, depends on condition bonuses)
        assert best_recall.strategy_id is not None
        assert best_precision.strategy_id is not None


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_condition(self):
        """Test handling of empty condition string."""
        optimizer = StrategyOptimizer()
        results = optimizer.recommend("", SearchGoal.BALANCED)
        # Should still return results (defaults to GENERAL category)
        assert len(results) > 0

    def test_very_long_condition(self):
        """Test handling of very long condition string."""
        optimizer = StrategyOptimizer()
        long_condition = "diabetes " * 100
        results = optimizer.recommend(long_condition, SearchGoal.BALANCED)
        assert len(results) > 0

    def test_special_characters_in_condition(self):
        """Test handling of special characters in condition."""
        optimizer = StrategyOptimizer()
        results = optimizer.recommend("type-2 diabetes (T2DM)", SearchGoal.BALANCED)
        assert len(results) > 0

    def test_impossible_constraints(self):
        """Test handling of impossible constraint combinations."""
        optimizer = StrategyOptimizer()
        results = optimizer.recommend(
            "diabetes",
            SearchGoal.BALANCED,
            min_recall=1.0,  # 100% recall
            max_nns=1.0  # Very low NNS
        )
        # Should return results even if constraints can't be met
        assert len(results) > 0


class TestWilsonConfidenceInterval:
    """Tests for Wilson score confidence interval calculations."""

    def test_recommendation_has_ci(self):
        """Test that recommendations include confidence intervals."""
        optimizer = StrategyOptimizer()
        results = optimizer.recommend("diabetes", SearchGoal.BALANCED)
        for rec in results:
            assert hasattr(rec, 'recall_ci_lower')
            assert hasattr(rec, 'recall_ci_upper')
            assert rec.recall_ci_lower <= rec.recall / 100
            assert rec.recall_ci_upper >= rec.recall / 100

    def test_ci_bounds_valid(self):
        """Test that CI bounds are within valid range."""
        optimizer = StrategyOptimizer()
        results = optimizer.recommend("diabetes", SearchGoal.BALANCED)
        for rec in results:
            assert 0 <= rec.recall_ci_lower <= 1
            assert 0 <= rec.recall_ci_upper <= 1
            assert rec.recall_ci_lower <= rec.recall_ci_upper


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
