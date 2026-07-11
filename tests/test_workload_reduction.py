"""
Regression test for MLScreeningAssistant.estimate_workload_reduction in
search_methodology.py.

Previously the method computed `100 * ml_excluded / total_records` with no guard,
raising ZeroDivisionError when total_records == 0. The fix returns an all-zero
estimate for an empty corpus.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from search_methodology import MLScreeningAssistant


def test_workload_reduction_zero_records_no_crash():
    """total_records=0 must not raise ZeroDivisionError."""
    assistant = MLScreeningAssistant()
    result = assistant.estimate_workload_reduction(total_records=0, estimated_relevant=0)
    assert result["total_records"] == 0
    assert result["workload_reduction_percent"] == 0.0
    assert result["ml_flagged_for_review"] == 0
    assert result["ml_excluded"] == 0


def test_workload_reduction_normal_case():
    """A normal corpus still produces a sensible workload-reduction percentage."""
    assistant = MLScreeningAssistant()
    result = assistant.estimate_workload_reduction(total_records=10000, estimated_relevant=100)
    assert 0.0 <= result["workload_reduction_percent"] <= 100.0
    assert result["ml_flagged_for_review"] > 0
