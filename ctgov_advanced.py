#!/usr/bin/env python3
# sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files.
"""
Advanced CT.gov Search Strategies
- Combination/hybrid strategies
- Parallel execution
- Precision-recall optimization
- Efficient presentation
"""

import json
import time
import concurrent.futures
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional
from urllib.parse import quote
from datetime import datetime
from pathlib import Path
import sys

from ctgov_config import DEFAULT_TIMEOUT
from ctgov_utils import build_params, fetch_nct_ids, get_session

# Configuration
MAX_WORKERS = 5
TIMEOUT = DEFAULT_TIMEOUT


@dataclass
class SearchResult:
    strategy_id: str
    strategy_name: str
    condition: str
    total_count: int
    nct_ids: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    error: Optional[str] = None


@dataclass
class RecallResult:
    strategy_id: str
    known: int
    found: int
    missed: int
    recall: float
    precision_proxy: float  # found/total_results
    f1_score: float


class AdvancedSearcher:
    """Advanced CT.gov searcher with combination strategies and parallel execution"""

    # Base strategies
    BASE_STRATEGIES = {
        "S1": ("Condition Only", lambda c: f"query.cond={quote(c)}"),
        "S2": ("Interventional", lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[StudyType]INTERVENTIONAL')}"),
        "S3": ("Randomized", lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED')}"),
        "S4": ("Phase 3/4", lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[Phase](PHASE3 OR PHASE4)')}"),
        "S5": ("Has Results", lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[ResultsFirstPostDate]RANGE[MIN,MAX]')}"),
        "S6": ("Completed", lambda c: f"query.cond={quote(c)}&filter.overallStatus=COMPLETED"),
        "S10": ("Treatment RCT", lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT')}"),
    }

    # Combination strategies - unions of base strategies
    COMBO_STRATEGIES = {
        "C1": ("S3+S10 Union", ["S3", "S10"]),
        "C2": ("S3+S5 Union", ["S3", "S5"]),
        "C3": ("S3+S6 Union", ["S3", "S6"]),
        "C4": ("S2+S3 Union", ["S2", "S3"]),
        "C5": ("S3+S4+S5 Union", ["S3", "S4", "S5"]),
        "C6": ("All RCT Union", ["S3", "S5", "S6", "S10"]),
    }

    def __init__(self):
        self.cache = {}
        self.cache_lock = threading.Lock()

    def _search_single(self, condition: str, strategy_id: str) -> SearchResult:
        """Execute a single search strategy"""
        cache_key = f"{condition}:{strategy_id}"
        with self.cache_lock:
            if cache_key in self.cache:
                return self.cache[cache_key]

        if strategy_id not in self.BASE_STRATEGIES:
            return SearchResult(strategy_id, "Unknown", condition, 0, error="Unknown strategy")

        name, query_fn = self.BASE_STRATEGIES[strategy_id]
        query = query_fn(condition)
        try:
            start = time.time()
            params = build_params(query)
            session = get_session("CTgov-Advanced/2.0")
            nct_ids, total_count = fetch_nct_ids(
                session, params, timeout=TIMEOUT, page_size=1000
            )
            elapsed = time.time() - start

            result = SearchResult(
                strategy_id=strategy_id,
                strategy_name=name,
                condition=condition,
                total_count=total_count,
                nct_ids=list(nct_ids),
                execution_time=elapsed
            )
            with self.cache_lock:
                self.cache[cache_key] = result
            return result
        except Exception as e:
            return SearchResult(strategy_id, name, condition, 0, error=str(e))

    def search_parallel(self, condition: str, strategies: List[str] = None) -> Dict[str, SearchResult]:
        """Execute multiple strategies in parallel"""
        if strategies is None:
            strategies = list(self.BASE_STRATEGIES.keys())

        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_strategy = {
                executor.submit(self._search_single, condition, s): s
                for s in strategies
            }
            for future in concurrent.futures.as_completed(future_to_strategy):
                strategy_id = future_to_strategy[future]
                try:
                    results[strategy_id] = future.result()
                except Exception as e:
                    results[strategy_id] = SearchResult(strategy_id, "", condition, 0, error=str(e))

        return results

    def search_combination(self, condition: str, combo_id: str) -> SearchResult:
        """Execute a combination strategy (union of base strategies)"""
        if combo_id not in self.COMBO_STRATEGIES:
            return SearchResult(combo_id, "Unknown", condition, 0, error="Unknown combo")

        name, base_strategies = self.COMBO_STRATEGIES[combo_id]

        # Run base strategies in parallel
        base_results = self.search_parallel(condition, base_strategies)

        # Union of NCT IDs
        all_nct_ids = set()
        total_time = 0
        for sid, result in base_results.items():
            if result.error is None:
                all_nct_ids.update(result.nct_ids)
                total_time += result.execution_time

        return SearchResult(
            strategy_id=combo_id,
            strategy_name=name,
            condition=condition,
            total_count=len(all_nct_ids),
            nct_ids=list(all_nct_ids),
            execution_time=total_time
        )

    def search_all(self, condition: str) -> Dict[str, SearchResult]:
        """Search with all base and combination strategies"""
        results = {}

        # Base strategies in parallel
        base_results = self.search_parallel(condition)
        results.update(base_results)

        # Combination strategies
        for combo_id in self.COMBO_STRATEGIES:
            results[combo_id] = self.search_combination(condition, combo_id)

        return results

    def calculate_recall(self, search_result: SearchResult, known_nct_ids: Set[str]) -> RecallResult:
        """Calculate recall metrics for a search result"""
        # Normalize both sets to uppercase for consistent comparison
        found_set = set(nct.upper() for nct in search_result.nct_ids)
        known_set = set(nct.upper() for nct in known_nct_ids)

        found = len(found_set.intersection(known_set))
        missed = len(known_set - found_set)

        recall = found / len(known_set) * 100 if known_set else 0
        precision_proxy = found / search_result.total_count * 100 if search_result.total_count > 0 else 0

        # F1 score (harmonic mean of recall and precision proxy)
        if recall + precision_proxy > 0:
            f1 = 2 * (recall * precision_proxy) / (recall + precision_proxy)
        else:
            f1 = 0

        return RecallResult(
            strategy_id=search_result.strategy_id,
            known=len(known_set),
            found=found,
            missed=missed,
            recall=recall,
            precision_proxy=precision_proxy,
            f1_score=f1
        )

    def optimize_strategy(self, condition: str, known_nct_ids: Set[str]) -> Tuple[str, RecallResult]:
        """Find the best strategy based on F1 score"""
        all_results = self.search_all(condition)

        best_strategy = None
        best_recall_result = None
        best_f1 = -1

        for strategy_id, search_result in all_results.items():
            if search_result.error:
                continue
            recall_result = self.calculate_recall(search_result, known_nct_ids)
            if recall_result.f1_score > best_f1:
                best_f1 = recall_result.f1_score
                best_strategy = strategy_id
                best_recall_result = recall_result

        return best_strategy, best_recall_result


class EfficientPresenter:
    """Efficient, compact presentation of results"""

    @staticmethod
    def compact_comparison(results: Dict[str, SearchResult], baseline_id: str = "S1") -> str:
        """Generate compact comparison table"""
        baseline = results.get(baseline_id)
        baseline_count = baseline.total_count if baseline and not baseline.error else 1

        lines = []
        lines.append("+--------+--------------------+----------+---------+--------+")
        lines.append("| ID     | Strategy           |    Count |   % Base|   Time |")
        lines.append("+--------+--------------------+----------+---------+--------+")

        # Sort by count descending
        sorted_results = sorted(results.items(), key=lambda x: x[1].total_count if not x[1].error else 0, reverse=True)

        for sid, result in sorted_results:
            if result.error:
                lines.append(f"| {sid:<6} | {'ERROR':<18} | {'N/A':>8} | {'N/A':>7} | {'N/A':>6} |")
            else:
                pct = result.total_count / baseline_count * 100 if baseline_count else 0
                lines.append(f"| {sid:<6} | {result.strategy_name[:18]:<18} | {result.total_count:>8,} | {pct:>6.1f}% | {result.execution_time:>5.2f}s |")

        lines.append("+--------+--------------------+----------+---------+--------+")
        return "\n".join(lines)

    @staticmethod
    def recall_table(recall_results: List[RecallResult]) -> str:
        """Generate recall comparison table"""
        lines = []
        lines.append("+--------+--------+--------+--------+----------+---------+")
        lines.append("| ID     | Recall | Found  | Missed | Prec(est)| F1 Score|")
        lines.append("+--------+--------+--------+--------+----------+---------+")

        # Sort by recall descending
        sorted_results = sorted(recall_results, key=lambda x: x.recall, reverse=True)

        for r in sorted_results:
            lines.append(f"| {r.strategy_id:<6} | {r.recall:>5.1f}% | {r.found:>6} | {r.missed:>6} | {r.precision_proxy:>8.2f}% | {r.f1_score:>7.1f} |")

        lines.append("+--------+--------+--------+--------+----------+---------+")
        return "\n".join(lines)

    @staticmethod
    def quick_summary(condition: str, best_strategy: str, best_recall: RecallResult, total_time: float) -> str:
        """One-line summary"""
        return f"[{condition}] Best: {best_strategy} | Recall: {best_recall.recall:.1f}% | Found: {best_recall.found}/{best_recall.known} | F1: {best_recall.f1_score:.1f} | Time: {total_time:.1f}s"


def run_comprehensive_analysis(conditions: List[str], known_nct_ids_by_condition: Dict[str, Set[str]], output_dir: Path):
    """Run comprehensive analysis across multiple conditions"""
    searcher = AdvancedSearcher()
    presenter = EfficientPresenter()

    all_results = {}
    all_recall = {}

    print("\n" + "═" * 80)
    print("  ADVANCED CT.gov STRATEGY ANALYSIS")
    print("═" * 80)

    for condition in conditions:
        known_ids = known_nct_ids_by_condition.get(condition, set())
        if not known_ids:
            continue

        print(f"\n▶ {condition.upper()} ({len(known_ids)} known studies)")
        print("─" * 60)

        start = time.time()

        # Run all strategies
        results = searcher.search_all(condition)
        all_results[condition] = results

        # Calculate recall for each
        recall_results = []
        for sid, search_result in results.items():
            if not search_result.error:
                recall_result = searcher.calculate_recall(search_result, known_ids)
                recall_results.append(recall_result)

        all_recall[condition] = recall_results

        elapsed = time.time() - start

        # Find best
        best = max(recall_results, key=lambda x: x.recall) if recall_results else None

        # Compact output
        print(presenter.compact_comparison(results))
        print()
        print(presenter.recall_table(recall_results))

        if best:
            print(f"\n  ★ BEST: {best.strategy_id} with {best.recall:.1f}% recall (F1: {best.f1_score:.1f})")
        print(f"  ⏱ Total time: {elapsed:.1f}s")

    # Overall summary
    print("\n" + "═" * 80)
    print("  OVERALL SUMMARY")
    print("═" * 80)

    strategy_totals = {}
    for condition, recall_results in all_recall.items():
        for r in recall_results:
            if r.strategy_id not in strategy_totals:
                strategy_totals[r.strategy_id] = {"total_known": 0, "total_found": 0, "recalls": []}
            strategy_totals[r.strategy_id]["total_known"] += r.known
            strategy_totals[r.strategy_id]["total_found"] += r.found
            strategy_totals[r.strategy_id]["recalls"].append(r.recall)

    print("\n┌────────┬────────────┬────────────┬──────────┬──────────┐")
    print("│ ID     │ Avg Recall │ Overall    │ Total Fnd│ Conditions│")
    print("├────────┼────────────┼────────────┼──────────┼──────────┤")

    sorted_strategies = sorted(
        strategy_totals.items(),
        key=lambda x: sum(x[1]["recalls"]) / len(x[1]["recalls"]) if x[1]["recalls"] else 0,
        reverse=True
    )

    for sid, data in sorted_strategies:
        avg_recall = sum(data["recalls"]) / len(data["recalls"]) if data["recalls"] else 0
        overall = data["total_found"] / data["total_known"] * 100 if data["total_known"] > 0 else 0
        print(f"│ {sid:<6} │ {avg_recall:>9.1f}% │ {overall:>9.1f}% │ {data['total_found']:>8} │ {len(data['recalls']):>9} │")

    print("└────────┴────────────┴────────────┴──────────┴──────────┘")

    # Save results
    output_file = output_dir / f"advanced_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # Convert to serializable format
    export_data = {
        "timestamp": datetime.now().isoformat(),
        "conditions_analyzed": len(conditions),
        "strategy_summary": {
            sid: {
                "avg_recall": sum(d["recalls"]) / len(d["recalls"]) if d["recalls"] else 0,
                "overall_recall": d["total_found"] / d["total_known"] * 100 if d["total_known"] > 0 else 0,
                "total_found": d["total_found"],
                "total_known": d["total_known"]
            }
            for sid, d in strategy_totals.items()
        }
    }

    with open(output_file, 'w') as f:
        json.dump(export_data, f, indent=2)

    print(f"\n  📁 Saved: {output_file}")

    return export_data


def main():
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")
    output_dir.mkdir(exist_ok=True)

    # Load NCT IDs
    nct_file = Path("C:/Users/user/Downloads/ctgov-search-strategies/output/recall_test_results.json")

    if nct_file.exists():
        with open(nct_file) as f:
            data = json.load(f)

        condition_groups = data.get("condition_groups", {})

        # Filter to conditions with 3+ studies
        valid_conditions = {k: set(v) for k, v in condition_groups.items() if len(v) >= 3}

        print(f"Loaded {len(valid_conditions)} conditions with 3+ known studies")

        run_comprehensive_analysis(
            list(valid_conditions.keys())[:10],  # Top 10 for demo
            valid_conditions,
            output_dir
        )
    else:
        # Demo mode
        print("Running demo analysis...")
        searcher = AdvancedSearcher()
        presenter = EfficientPresenter()

        condition = "cystic fibrosis"
        print(f"\n▶ {condition.upper()}")

        results = searcher.search_all(condition)
        print(presenter.compact_comparison(results))


if __name__ == "__main__":
    main()
