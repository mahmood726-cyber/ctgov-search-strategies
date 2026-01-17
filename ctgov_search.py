#!/usr/bin/env python3
"""
CT.gov Search Strategy Module
Comprehensive Python interface for ClinicalTrials.gov API v2

Features:
- 10 validated search strategies
- NCT ID validation
- Recall/precision calculation
- WHO ICTRP integration
- MeSH synonym expansion
- Batch searching
- Export utilities

Based on Cochrane guidance and empirical validation.
"""

from __future__ import annotations

import csv
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any,
    Callable,
    Dict,
    Final,
    Iterable,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    TypedDict,
    Union,
)
from urllib.parse import quote

from ctgov_config import (
    CTGOV_API,
    DEFAULT_PAGE_SIZE,
    DEFAULT_RATE_LIMIT,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
)
from ctgov_terms import SynonymDict, load_synonyms
from ctgov_utils import (
    build_params,
    fetch_matching_nct_ids,
    fetch_studies,
    get_session,
)

import requests

# API Configuration
RATE_LIMIT_DELAY: Final[float] = DEFAULT_RATE_LIMIT
MAX_PAGE_SIZE: Final[int] = DEFAULT_PAGE_SIZE
NCT_ID_PATTERN: Final[Pattern[str]] = re.compile(r"NCT\d{8}$")


# Type definitions for strategy configuration
class StrategyConfig(TypedDict):
    """Type definition for search strategy configuration."""

    name: str
    description: str
    retention: int
    sensitivity: str
    build_query: Callable[[str, Optional[str]], str]


# Type alias for the strategies dictionary
StrategiesDict = Dict[str, StrategyConfig]


@dataclass
class SearchResult:
    """Container for search results."""

    strategy_id: str
    strategy_name: str
    condition: str
    total_count: int
    query_url: str
    execution_time: float
    studies: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class RecallMetrics:
    """Recall/precision metrics against gold standard."""

    strategy_id: str
    total_known: int
    found: int
    recall: float
    nct_ids_found: List[str] = field(default_factory=list)
    nct_ids_missed: List[str] = field(default_factory=list)


class CTGovSearcher:
    """
    Comprehensive ClinicalTrials.gov Search Interface

    Usage:
        searcher = CTGovSearcher()

        # Single strategy search
        result = searcher.search("diabetes", strategy="S1")

        # Compare all strategies
        results = searcher.compare_all_strategies("diabetes")

        # Validate recall against known NCT IDs
        metrics = searcher.calculate_recall("diabetes", ["NCT00000001", "NCT00000002"])
    """

    # Validated search strategies based on empirical testing
    STRATEGIES: Final[StrategiesDict] = {
        "S1": {
            "name": "Condition Only (Maximum Recall)",
            "description": "Cochrane recommended - no filters for maximum sensitivity",
            "retention": 100,
            "sensitivity": "high",
            "build_query": lambda c, i: f"query.cond={quote(c)}",
        },
        "S2": {
            "name": "Interventional Studies",
            "description": "All interventional study types",
            "retention": 77,
            "sensitivity": "high",
            "build_query": lambda c, i: f"query.cond={quote(c)}&query.term={quote('AREA[StudyType]INTERVENTIONAL')}",
        },
        "S3": {
            "name": "Randomized Allocation Only",
            "description": "True RCTs - excludes single-arm trials",
            "retention": 54,
            "sensitivity": "medium",
            "build_query": lambda c, i: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED')}",
        },
        "S4": {
            "name": "Phase 3/4 Studies",
            "description": "Later phase trials only",
            "retention": 16,
            "sensitivity": "low",
            "build_query": lambda c, i: f"query.cond={quote(c)}&query.term={quote('AREA[Phase](PHASE3 OR PHASE4)')}",
        },
        "S5": {
            "name": "Has Posted Results",
            "description": "Studies with results posted on CT.gov",
            "retention": 14,
            "sensitivity": "low",
            "build_query": lambda c, i: f"query.cond={quote(c)}&query.term={quote('AREA[ResultsFirstPostDate]RANGE[MIN,MAX]')}",
        },
        "S6": {
            "name": "Completed Status",
            "description": "Completed trials only",
            "retention": 55,
            "sensitivity": "medium",
            "build_query": lambda c, i: f"query.cond={quote(c)}&filter.overallStatus=COMPLETED",
        },
        "S7": {
            "name": "Interventional + Completed",
            "description": "Completed interventional studies",
            "retention": 43,
            "sensitivity": "medium",
            "build_query": lambda c, i: f"query.cond={quote(c)}&query.term={quote('AREA[StudyType]INTERVENTIONAL')}&filter.overallStatus=COMPLETED",
        },
        "S8": {
            "name": "RCT + Phase 3/4 + Completed",
            "description": "Highest quality subset",
            "retention": 8,
            "sensitivity": "low",
            "build_query": lambda c, i: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED AND AREA[Phase](PHASE3 OR PHASE4)')}&filter.overallStatus=COMPLETED",
        },
        "S9": {
            "name": "Full-Text RCT Keywords",
            "description": "Text search: condition AND randomized AND controlled",
            "retention": 72,
            "sensitivity": "medium",
            "build_query": lambda c, i: f"query.term={quote(c + ' AND randomized AND controlled')}",
        },
        "S10": {
            "name": "Treatment RCTs Only",
            "description": "Randomized + Treatment purpose",
            "retention": 36,
            "sensitivity": "medium",
            "build_query": lambda c, i: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT')}",
        },
    }

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        synonyms_path: Optional[str] = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        """
        Initialize the CTGovSearcher.

        Args:
            timeout: Request timeout in seconds.
            synonyms_path: Optional path to a custom synonyms JSON file.
            user_agent: User-Agent header for HTTP requests.
        """
        self.timeout: int = timeout
        self.session: requests.Session = get_session(user_agent=user_agent)
        self.session.headers.update({"Accept": "application/json"})
        self.synonyms: SynonymDict = load_synonyms(synonyms_path)

    @staticmethod
    def _clamp_page_size(page_size: Optional[int]) -> int:
        """
        Clamp page size to the CT.gov API limits.

        Args:
            page_size: Requested page size (may be None).

        Returns:
            Clamped page size between 1 and MAX_PAGE_SIZE.
        """
        value: int = 1 if page_size is None else int(page_size)
        return max(1, min(value, MAX_PAGE_SIZE))

    @staticmethod
    def _normalize_nct_ids(
        nct_ids: Iterable[Optional[str]],
    ) -> Tuple[List[str], List[str]]:
        """
        Return (valid_ids, invalid_ids) in normalized uppercase form.

        Args:
            nct_ids: Iterable of NCT IDs to normalize.

        Returns:
            Tuple of (valid NCT IDs, invalid NCT IDs).
        """
        valid_ids: List[str] = []
        invalid_ids: List[str] = []
        seen: Set[str] = set()

        for raw in nct_ids or []:
            if raw is None:
                continue
            cleaned: str = raw.strip().upper()
            if not cleaned:
                continue
            if not NCT_ID_PATTERN.fullmatch(cleaned):
                invalid_ids.append(cleaned)
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            valid_ids.append(cleaned)

        return valid_ids, invalid_ids

    def search(
        self,
        condition: str,
        strategy: str = "S1",
        intervention: Optional[str] = None,
        page_size: int = 100,
        return_studies: bool = False,
    ) -> SearchResult:
        """
        Execute a search using specified strategy.

        Args:
            condition: Medical condition to search.
            strategy: Strategy ID (S1-S10).
            intervention: Optional intervention filter.
            page_size: Number of results to return (max 1000).
            return_studies: Whether to return study details.

        Returns:
            SearchResult object with count and optional studies.

        Raises:
            ValueError: If an unknown strategy ID is provided.
        """
        if strategy not in self.STRATEGIES:
            raise ValueError(
                f"Unknown strategy: {strategy}. Valid: {list(self.STRATEGIES.keys())}"
            )

        strat: StrategyConfig = self.STRATEGIES[strategy]
        query: str = strat["build_query"](condition, intervention)
        params: Dict[str, str] = build_params(query)
        params["countTotal"] = "true"
        effective_page_size: int = self._clamp_page_size(
            page_size if return_studies else 1
        )
        params["pageSize"] = str(effective_page_size)

        query_url: str = CTGOV_API
        start_time: float = time.time()
        try:
            response: requests.Response = self.session.get(
                CTGOV_API, params=params, timeout=self.timeout
            )
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            query_url = str(response.url)

            execution_time: float = time.time() - start_time

            return SearchResult(
                strategy_id=strategy,
                strategy_name=strat["name"],
                condition=condition,
                total_count=data.get("totalCount", 0),
                query_url=query_url,
                execution_time=execution_time,
                studies=data.get("studies", []) if return_studies else [],
            )
        except Exception as e:
            return SearchResult(
                strategy_id=strategy,
                strategy_name=strat["name"],
                condition=condition,
                total_count=0,
                query_url=query_url,
                execution_time=time.time() - start_time,
                error=str(e),
            )

    def compare_all_strategies(
        self, condition: str, intervention: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Run all 10 strategies for a condition and compare results.

        Args:
            condition: Medical condition to search.
            intervention: Optional intervention filter.

        Returns:
            List of SearchResult objects for each strategy.
        """
        results: List[SearchResult] = []
        for strategy_id in self.STRATEGIES.keys():
            result: SearchResult = self.search(
                condition, strategy=strategy_id, intervention=intervention
            )
            results.append(result)
            time.sleep(RATE_LIMIT_DELAY)  # Rate limiting
        return results

    def search_with_synonyms(
        self, condition: str, strategy: str = "S1"
    ) -> SearchResult:
        """
        Search using condition and all known synonyms (OR logic).

        Args:
            condition: Base condition.
            strategy: Strategy to use.

        Returns:
            SearchResult with combined query.

        Raises:
            ValueError: If an unknown strategy ID is provided.
        """
        if strategy not in self.STRATEGIES:
            raise ValueError(
                f"Unknown strategy: {strategy}. Valid: {list(self.STRATEGIES.keys())}"
            )

        strat: StrategyConfig = self.STRATEGIES[strategy]
        synonyms: List[str] = self.synonyms.get(condition.lower(), [])
        all_terms: List[str] = [condition] + synonyms

        # Build OR query
        or_query: str = " OR ".join([f'"{term}"' for term in all_terms])

        params: Dict[str, str] = build_params(strat["build_query"](condition, None))
        if strategy == "S9":
            params["query.term"] = f"({or_query}) AND randomized AND controlled"
        elif "query.cond" in params:
            params["query.cond"] = or_query
        else:
            params["query.term"] = or_query

        params["countTotal"] = "true"
        params["pageSize"] = "1"

        start_time: float = time.time()
        try:
            response: requests.Response = self.session.get(
                CTGOV_API, params=params, timeout=self.timeout
            )
            response.raise_for_status()
            data: Dict[str, Any] = response.json()

            return SearchResult(
                strategy_id=f"{strategy}_synonyms",
                strategy_name=f"Synonym Expanded ({len(all_terms)} terms)",
                condition=condition,
                total_count=data.get("totalCount", 0),
                query_url=str(response.url),
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return SearchResult(
                strategy_id=f"{strategy}_synonyms",
                strategy_name="Synonym Expanded",
                condition=condition,
                total_count=0,
                query_url=CTGOV_API,
                execution_time=time.time() - start_time,
                error=str(e),
            )

    def validate_nct_ids(self, nct_ids: List[str]) -> Dict[str, bool]:
        """
        Validate that NCT IDs exist on CT.gov.

        Args:
            nct_ids: List of NCT IDs to validate.

        Returns:
            Dict mapping NCT ID to existence (True/False).
        """
        valid_ids, invalid_ids = self._normalize_nct_ids(nct_ids)
        results: Dict[str, bool] = {nct_id: False for nct_id in invalid_ids}

        if not valid_ids:
            return results

        try:
            found_ids: Set[str] = fetch_matching_nct_ids(
                self.session, {}, valid_ids, timeout=self.timeout
            )
        except Exception:
            found_ids = set()

        for nct_id in valid_ids:
            results[nct_id] = nct_id in found_ids

        return results

    def get_study_details(self, nct_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full details for a specific study.

        Args:
            nct_id: NCT ID of the study.

        Returns:
            Study details dict or None if not found.
        """
        url: str = f"{CTGOV_API}/{nct_id}"
        try:
            response: requests.Response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    def calculate_recall(
        self, condition: str, known_nct_ids: List[str], strategy: str = "S1"
    ) -> RecallMetrics:
        """
        Calculate recall of a search strategy against known included studies.

        Args:
            condition: Condition to search.
            known_nct_ids: List of NCT IDs known to be relevant.
            strategy: Strategy to test.

        Returns:
            RecallMetrics with recall percentage and lists of found/missed.
        """
        # First, get all NCT IDs from the search
        query: str = self.STRATEGIES[strategy]["build_query"](condition, None)
        params: Dict[str, str] = build_params(query)
        found_nct_ids: Set[str] = fetch_matching_nct_ids(
            self.session, params, known_nct_ids, timeout=self.timeout
        )

        known_set: Set[str] = {nct.upper().strip() for nct in known_nct_ids if nct}
        found: Set[str] = known_set.intersection(found_nct_ids)
        missed: Set[str] = known_set - found_nct_ids

        recall: float = len(found) / len(known_set) * 100 if known_set else 0.0

        return RecallMetrics(
            strategy_id=strategy,
            total_known=len(known_set),
            found=len(found),
            recall=recall,
            nct_ids_found=list(found),
            nct_ids_missed=list(missed),
        )

    def search_by_nct_ids(self, nct_ids: List[str]) -> SearchResult:
        """
        Search for specific NCT IDs.

        Args:
            nct_ids: List of NCT IDs.

        Returns:
            SearchResult with matching studies.
        """
        valid_ids, _ = self._normalize_nct_ids(nct_ids)
        if not valid_ids:
            return SearchResult(
                strategy_id="NCT_LOOKUP",
                strategy_name="NCT ID Lookup",
                condition="N/A",
                total_count=0,
                query_url=CTGOV_API,
                execution_time=0.0,
                error="No valid NCT IDs provided.",
            )

        start_time: float = time.time()
        try:
            studies: List[Dict[str, Any]] = []
            seen_ncts: Set[str] = set()
            batch_size: int = 100

            for start in range(0, len(valid_ids), batch_size):
                batch: List[str] = valid_ids[start : start + batch_size]
                params: Dict[str, str] = {"query.id": " OR ".join(batch)}
                batch_page_size: int = self._clamp_page_size(len(batch))
                batch_studies, _ = fetch_studies(
                    self.session,
                    params,
                    timeout=self.timeout,
                    page_size=batch_page_size,
                )
                for study in batch_studies:
                    nct: str = (
                        study.get("protocolSection", {})
                        .get("identificationModule", {})
                        .get("nctId", "")
                        .upper()
                    )
                    if not nct or nct in seen_ncts:
                        continue
                    seen_ncts.add(nct)
                    studies.append(study)

            return SearchResult(
                strategy_id="NCT_LOOKUP",
                strategy_name="NCT ID Lookup",
                condition="N/A",
                total_count=len(seen_ncts),
                query_url=CTGOV_API,
                execution_time=time.time() - start_time,
                studies=studies,
            )
        except Exception as e:
            return SearchResult(
                strategy_id="NCT_LOOKUP",
                strategy_name="NCT ID Lookup",
                condition="N/A",
                total_count=0,
                query_url=CTGOV_API,
                execution_time=time.time() - start_time,
                error=str(e),
            )

    def export_results_csv(
        self, results: List[SearchResult], filepath: str
    ) -> None:
        """
        Export search results to CSV file.

        Args:
            results: List of SearchResult objects to export.
            filepath: Path to the output CSV file.
        """
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer: Any = csv.writer(f)
            writer.writerow(
                [
                    "strategy_id",
                    "strategy_name",
                    "condition",
                    "total_count",
                    "execution_time",
                    "query_url",
                    "error",
                ]
            )
            for r in results:
                writer.writerow(
                    [
                        r.strategy_id,
                        r.strategy_name,
                        r.condition,
                        r.total_count,
                        r.execution_time,
                        r.query_url,
                        r.error or "",
                    ]
                )

    def generate_search_report(self, condition: str) -> str:
        """
        Generate a formatted report for a condition search.

        Args:
            condition: Medical condition to generate report for.

        Returns:
            Formatted string report with strategy comparison.
        """
        results: List[SearchResult] = self.compare_all_strategies(condition)
        baseline: int = results[0].total_count if results else 0

        report: List[str] = []
        report.append("=" * 70)
        report.append(f"CT.gov Search Strategy Report: {condition.upper()}")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 70)
        report.append("")

        report.append(
            f"{'Strategy':<5} {'Name':<35} {'Count':>10} {'% Baseline':>12}"
        )
        report.append("-" * 65)

        for r in results:
            pct: str = (
                f"{(r.total_count / baseline * 100):.1f}%" if baseline > 0 else "N/A"
            )
            report.append(
                f"{r.strategy_id:<5} {r.strategy_name:<35} {r.total_count:>10,} {pct:>12}"
            )

        report.append("")
        report.append("RECOMMENDATIONS:")
        report.append("-" * 40)
        report.append("- For systematic reviews: Use S1 (maximum recall)")
        report.append("- For RCTs only: Use S3 (randomized allocation)")
        report.append("- For published trials: Use S7 (interventional + completed)")
        report.append("")

        return "\n".join(report)


def main() -> None:
    """Demo usage of the CTGovSearcher."""
    print("CT.gov Search Strategy Module - Demo")
    print("=" * 50)

    searcher: CTGovSearcher = CTGovSearcher()

    # Test single search
    print("\n1. Single Strategy Search (diabetes, S1):")
    result: SearchResult = searcher.search("diabetes", strategy="S1")
    print(f"   Total: {result.total_count:,} studies")
    print(f"   Time: {result.execution_time:.2f}s")

    # Compare all strategies
    print("\n2. Comparing All Strategies (diabetes):")
    results: List[SearchResult] = searcher.compare_all_strategies("diabetes")
    for r in results:
        print(f"   {r.strategy_id}: {r.total_count:,}")

    # Synonym expansion
    print("\n3. Synonym Expansion (diabetes):")
    syn_result: SearchResult = searcher.search_with_synonyms("diabetes")
    print(f"   Total with synonyms: {syn_result.total_count:,}")

    # Validate NCT IDs
    print("\n4. NCT ID Validation (sample):")
    sample_ncts: List[str] = ["NCT03702452", "NCT00400712", "NCT99999999"]
    validation: Dict[str, bool] = searcher.validate_nct_ids(sample_ncts)
    for nct, exists in validation.items():
        print(f"   {nct}: {'Valid' if exists else 'Not found'}")

    print("\n" + "=" * 50)
    print("Demo complete!")


if __name__ == "__main__":
    main()
