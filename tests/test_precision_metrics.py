"""
Numerical baseline tests for precision_metrics.py.

Covers the statistical core (Wilson-score CI, recall-with-CI, precision, NNS,
F1, specificity). Reference values are independently derived and cross-checked
against statsmodels.stats.proportion.proportion_confint(method='wilson') and a
hand computation of the Wilson score formula.
"""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import precision_metrics as pm
from precision_metrics import PrecisionCalculator


# ---------------------------------------------------------------------------
# wilson_ci
# ---------------------------------------------------------------------------

def test_wilson_ci_reference_value():
    """wilson_ci(45, 50, 0.95) matches the independently verified Wilson interval.

    Verified against statsmodels proportion_confint(45, 50, method='wilson')
    and a direct evaluation of the Wilson score formula: (0.786398, 0.956524).
    NOTE: the module's original docstring example claimed (0.777, 0.963); that
    documented value was wrong. The code itself is correct.
    """
    lower, upper = pm.wilson_ci(45, 50, 0.95)
    assert lower == pytest.approx(0.786398, abs=1e-4)
    assert upper == pytest.approx(0.956524, abs=1e-4)


def test_wilson_ci_total_zero():
    assert pm.wilson_ci(0, 0) == (0.0, 0.0)


def test_wilson_ci_all_successes_clamps_upper_to_one():
    lower, upper = pm.wilson_ci(50, 50, 0.95)
    assert upper == pytest.approx(1.0, abs=1e-12)
    assert 0.0 < lower < 1.0


def test_wilson_ci_zero_successes_clamps_lower_to_zero():
    lower, upper = pm.wilson_ci(0, 50, 0.95)
    assert lower == pytest.approx(0.0, abs=1e-12)
    assert 0.0 < upper < 1.0


def test_wilson_ci_k1():
    """Single trial found out of 1 known -> valid interval strictly inside [0, 1]."""
    lower, upper = pm.wilson_ci(1, 1, 0.95)
    assert 0.0 <= lower < upper == pytest.approx(1.0, abs=1e-12)


def test_wilson_ci_invalid_inputs():
    with pytest.raises(ValueError):
        pm.wilson_ci(-1, 10)
    with pytest.raises(ValueError):
        pm.wilson_ci(11, 10)
    with pytest.raises(ValueError):
        pm.wilson_ci(5, 10, confidence=1.5)


# ---------------------------------------------------------------------------
# calculate_recall_with_ci
# ---------------------------------------------------------------------------

def test_calculate_recall_with_ci_basic():
    found = {"NCT00000001", "NCT00000002", "NCT00000003"}
    known = {"NCT00000001", "NCT00000002", "NCT00000004", "NCT00000005"}
    result = pm.calculate_recall_with_ci(found, known)
    assert result["successes"] == 2
    assert result["total"] == 4
    assert result["recall"] == pytest.approx(0.5)
    assert 0.0 <= result["recall_ci_lower"] <= result["recall"] <= result["recall_ci_upper"] <= 1.0


def test_calculate_recall_with_ci_empty_known():
    result = pm.calculate_recall_with_ci(set(), set())
    assert result["recall"] == 0.0
    assert result["total"] == 0


# ---------------------------------------------------------------------------
# PrecisionCalculator
# ---------------------------------------------------------------------------

def test_calculate_precision():
    assert PrecisionCalculator.calculate_precision(50, 500) == pytest.approx(0.10)


def test_calculate_precision_zero_retrieved():
    assert PrecisionCalculator.calculate_precision(0, 0) == 0.0


def test_calculate_precision_invalid():
    with pytest.raises(ValueError):
        PrecisionCalculator.calculate_precision(-1, 10)
    with pytest.raises(ValueError):
        PrecisionCalculator.calculate_precision(11, 10)


def test_calculate_nns():
    assert PrecisionCalculator.calculate_nns(500, 50) == pytest.approx(10.0)


def test_calculate_nns_no_relevant_is_inf():
    assert PrecisionCalculator.calculate_nns(500, 0) == math.inf


def test_calculate_f1_score():
    # precision=0.5, recall=1.0 -> F1 = 2*0.5/1.5 = 0.6667
    assert PrecisionCalculator.calculate_f1_score(0.5, 1.0) == pytest.approx(2 / 3)


def test_calculate_f1_score_zero_zero():
    assert PrecisionCalculator.calculate_f1_score(0.0, 0.0) == 0.0


def test_calculate_specificity():
    assert PrecisionCalculator.calculate_specificity(90, 10) == pytest.approx(0.9)


def test_calculate_specificity_zero_total():
    assert PrecisionCalculator.calculate_specificity(0, 0) == 0.0
