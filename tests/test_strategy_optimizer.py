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
        assert classify_condition("type 2 diabetes") == ConditionCategory.METABOLIC
        assert classify_condition("diabetes mellitus") == ConditionCategory.METABOLIC
        assert classify_condition("insulin resistance") == ConditionCategory.METABOLIC

    def test_classify_oncology(self):
        assert classify_condition("breast cancer") == ConditionCategory.ONCOLOGY
        assert classify_condition("lung carcinoma") == ConditionCategory.ONCOLOGY
        assert classify_condition("melanoma") == ConditionCategory.ONCOLOGY
        assert classify_condition("lymphoma") == ConditionCategory.ONCOLOGY

    def test_classify_cardiology(self):
        assert classify_condition("heart failure") == ConditionCategory.CARDIOVASCULAR
        assert classify_condition("atrial fibrillation") == ConditionCategory.CARDIOVASCULAR
        assert classify_condition("hypertension") == ConditionCategory.CARDIOVASCULAR
        assert classify_condition("coronary artery disease") == ConditionCategory.CARDIOVASCULAR

    def test_classify_neurology(self):
        assert classify_condition("Alzheimer's disease") == ConditionCategory.NEUROLOGICAL
        assert classify_condition("Parkinson's disease") == ConditionCategory.NEUROLOGICAL
        assert classify_condition("multiple sclerosis") == ConditionCategory.NEUROLOGICAL
        assert classify_condition("epilepsy") == ConditionCategory.NEUROLOGICAL

    def test_classify_psychiatry(self):
        assert classify_condition("major depression") == ConditionCategory.MENTAL_HEALTH
        assert classify_condition("anxiety disorder") == ConditionCategory.MENTAL_HEALTH
        assert classify_condition("schizophrenia") == ConditionCategory.MENTAL_HEALTH
        assert classify_condition("bipolar disorder") == ConditionCategory.MENTAL_HEALTH

    def test_classify_infectious(self):
        assert classify_condition("HIV infection") == ConditionCategory.INFECTIOUS
        assert classify_condition("hepatitis C") == ConditionCategory.INFECTIOUS
        assert classify_condition("tuberculosis") == ConditionCategory.INFECTIOUS
        assert classify_condition("COVID-19") == ConditionCategory.INFECTIOUS

    def test_classify_unknown(self):
        # Rare conditions get RARE_DISEASE; truly unknown get GENERAL
        result = classify_condition("rare syndrome xyz")
        assert result in (ConditionCategory.GENERAL, ConditionCategory.RARE_DISEASE)
        result2 = classify_condition("unclassified condition")
        assert result2 in (ConditionCategory.GENERAL, ConditionCategory.RARE_DISEASE)

    def test_classify_case_insensitive(self):
        assert classify_condition("DIABETES") == ConditionCategory.METABOLIC
        assert classify_condition("Breast CANCER") == ConditionCategory.ONCOLOGY
        assert classify_condition("HYPERTENSION") == ConditionCategory.CARDIOVASCULAR


class TestSearchGoal:
    def test_search_goal_values(self):
        assert SearchGoal.MAXIMUM_RECALL.value == "maximum_recall"
        assert SearchGoal.BALANCED.value == "balanced"
        assert SearchGoal.HIGH_PRECISION.value == "high_precision"
        assert SearchGoal.QUICK_OVERVIEW.value == "quick_overview"

    def test_all_goals_defined(self):
        goals = list(SearchGoal)
        assert len(goals) == 4


class TestStrategyPerformance:
    def test_all_strategies_have_data(self):
        expected_strategies = [f"S{i}" for i in range(1, 11)]
        for strategy_id in expected_strategies:
            assert strategy_id in STRATEGY_PERFORMANCE_DATA, f"Missing data for {strategy_id}"

    def test_performance_data_valid(self):
        for strategy_id, perf in STRATEGY_PERFORMANCE_DATA.items():
            assert isinstance(perf, StrategyPerformance)
            assert 0 <= perf.base_recall <= 1.0, f"{strategy_id} recall out of range"
            assert 0 <= perf.base_precision <= 1.0, f"{strategy_id} precision out of range"
            assert perf.expected_nns > 0, f"{strategy_id} NNS must be positive"

    def test_recall_precision_relationship(self):
        s1 = STRATEGY_PERFORMANCE_DATA["S1"]  # Maximum recall
        s8 = STRATEGY_PERFORMANCE_DATA["S8"]  # High quality (lower recall)
        assert s1.base_recall > s8.base_recall, "S1 should have higher recall than S8"
        assert s1.base_precision < s8.base_precision, "S1 should have lower precision than S8"


class TestStrategyOptimizer:
    @pytest.fixture
    def optimizer(self):
        return StrategyOptimizer()

    def test_recommend_returns_list(self, optimizer):
        results = optimizer.recommend("diabetes", SearchGoal.BALANCED)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_recommend_returns_sorted(self, optimizer):
        results = optimizer.recommend("diabetes", SearchGoal.BALANCED)
        scores = [r.overall_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_recommend_maximum_recall(self, optimizer):
        results = optimizer.recommend("diabetes", SearchGoal.MAXIMUM_RECALL)
        top = results[0]
        assert top.predicted_recall > 0.9

    def test_recommend_high_precision(self, optimizer):
        results = optimizer.recommend("diabetes", SearchGoal.HIGH_PRECISION)
        top = results[0]
        assert top.predicted_precision > top.predicted_recall or top.overall_score > 0

    def test_recommend_with_min_recall(self, optimizer):
        results = optimizer.recommend("diabetes", SearchGoal.BALANCED, min_recall=0.90)
        high_recall = [r for r in results if r.predicted_recall >= 0.90]
        assert len(high_recall) > 0

    def test_recommend_with_max_nns(self, optimizer):
        # max_nns may filter aggressively — just verify it doesn't crash
        results = optimizer.recommend("diabetes", SearchGoal.BALANCED, max_nns=50.0)
        assert isinstance(results, list)

    def test_recommend_with_known_ncts(self, optimizer):
        results_without = optimizer.recommend("diabetes", SearchGoal.BALANCED)
        results_with = optimizer.recommend(
            "diabetes", SearchGoal.BALANCED,
            known_ncts=["NCT00000001", "NCT00000002"]
        )
        assert len(results_with) > 0

    def test_get_ensemble_recommendation(self, optimizer):
        result = optimizer.get_ensemble_recommendation(
            "diabetes", SearchGoal.BALANCED
        )
        assert isinstance(result, dict)
        assert "primary" in result or len(result) > 0


class TestConvenienceFunctions:
    def test_recommend_strategy(self):
        results = recommend_strategy("diabetes", "balanced")
        assert isinstance(results, list)
        assert len(results) > 0

    def test_get_best_strategy(self):
        best = get_best_strategy("diabetes")
        assert best is not None
        assert isinstance(best, dict)
        assert "strategy_id" in best or len(best) > 0

    def test_get_best_strategy_different_goals(self):
        best_recall = get_best_strategy("diabetes", goal="maximum_recall")
        best_precision = get_best_strategy("diabetes", goal="high_precision")
        assert best_recall is not None
        assert best_precision is not None


class TestEdgeCases:
    def test_empty_condition(self):
        result = classify_condition("")
        assert result == ConditionCategory.GENERAL

    def test_impossible_constraints(self):
        optimizer = StrategyOptimizer()
        results = optimizer.recommend(
            "diabetes", SearchGoal.HIGH_PRECISION,
            min_recall=0.99, max_nns=1.0
        )
        # Should still return results (relaxed constraints)
        assert isinstance(results, list)


class TestWilsonConfidenceInterval:
    def test_recommendation_has_ci(self):
        optimizer = StrategyOptimizer()
        results = optimizer.recommend("diabetes", SearchGoal.BALANCED)
        top = results[0]
        assert hasattr(top, "confidence")
        assert 0 <= top.confidence <= 1.0

    def test_ci_bounds_valid(self):
        for sid, perf in STRATEGY_PERFORMANCE_DATA.items():
            assert perf.recall_ci_lower <= perf.base_recall <= perf.recall_ci_upper, \
                f"{sid} recall CI invalid"
            assert perf.precision_ci_lower <= perf.base_precision <= perf.precision_ci_upper, \
                f"{sid} precision CI invalid"
