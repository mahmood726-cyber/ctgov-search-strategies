"""
Regression test for McNemar's test in scripts/relative_recall_framework.py.

Previously the p-value was read off a hardcoded critical-value ladder that
pinned chi-squared in [3.841, 6.635) to exactly p=0.05. Combined with the
strict `p_value < 0.05` verdict, genuinely significant comparisons were reported
as non-significant. The fix uses scipy.stats.chi2.sf for the exact upper-tail
p-value.

Concrete failing input (b=8, c=0):
    chi_squared = (|8-0| - 1)^2 / 8 = 6.125
    old code:  p_value pinned to 0.05  -> significant_difference = False (WRONG)
    scipy:     chi2.sf(6.125, 1) = 0.01332...  -> significant_difference = True
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from relative_recall_framework import (
    BenchmarkSet,
    RelativeRecallCalculator,
    SearchStringResult,
)


def _make_benchmark(records):
    return BenchmarkSet(
        name="bench",
        description="test benchmark",
        source="test",
        records=set(records),
        creation_date="2026-01-01",
        therapeutic_area="test",
        drug_or_intervention="test",
        condition="test",
        is_prespecified=True,
        sources_searched=["test"],
        years_covered="2020-2026",
    )


def _make_search(search_id, records):
    return SearchStringResult(
        search_id=search_id,
        search_string="test",
        database="ctgov",
        records_retrieved=set(records),
        execution_date="2026-01-01",
        api_version="v2",
    )


def test_mcnemar_significant_b8_c0():
    """b=8, c=0 is significant (p=0.0133); must NOT be reported non-significant."""
    benchmark_records = {f"NCT{i:08d}" for i in range(10)}  # 10 known-relevant
    calc = RelativeRecallCalculator()
    calc.add_benchmark(_make_benchmark(benchmark_records))

    # search1 finds 8 of the benchmark records; search2 finds none of them.
    calc.add_search_result(_make_search("S1", {f"NCT{i:08d}" for i in range(8)}))
    calc.add_search_result(_make_search("S2", {"NCT99999999"}))

    result = calc.mcnemar_test("S1", "S2", "bench")

    assert result["contingency_table"]["search1_only"] == 8
    assert result["contingency_table"]["search2_only"] == 0
    assert result["chi_squared"] == pytest.approx(6.125, abs=1e-3)
    # Exact scipy p-value, not the old 0.05 ladder value.
    assert result["p_value"] == pytest.approx(0.013328, abs=1e-4)
    assert result["significant_difference"] is True


def test_mcnemar_no_discordant_pairs_is_nonsignificant():
    """b + c == 0 -> chi_squared 0, p 1.0, not significant (guard preserved)."""
    benchmark_records = {f"NCT{i:08d}" for i in range(5)}
    calc = RelativeRecallCalculator()
    calc.add_benchmark(_make_benchmark(benchmark_records))
    calc.add_search_result(_make_search("S1", benchmark_records))
    calc.add_search_result(_make_search("S2", benchmark_records))

    result = calc.mcnemar_test("S1", "S2", "bench")
    assert result["chi_squared"] == 0.0
    assert result["p_value"] == 1.0
    assert result["significant_difference"] is False
