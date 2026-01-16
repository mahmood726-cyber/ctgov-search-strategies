"""
CT.gov Search Strategies Package

A comprehensive Python package for searching ClinicalTrials.gov with validated
search strategies, recall/precision calculation, and systematic review support.

Features:
- 10 validated search strategies based on Cochrane guidance
- NCT ID validation and batch searching
- Recall and precision metrics calculation
- MeSH synonym expansion
- Screening efficiency analysis
- Export utilities for systematic reviews

Example:
    >>> from ctgov_search_strategies import CTGovSearcher, SearchResult
    >>> searcher = CTGovSearcher()
    >>> result = searcher.search("diabetes", strategy="S1")
    >>> print(f"Found {result.total_count} studies")
"""

__version__ = "1.0.0"

# Core search functionality
from ctgov_search import CTGovSearcher, SearchResult, RecallMetrics

# Utility functions for API access
from ctgov_utils import get_session, fetch_nct_ids, fetch_studies

# Terminology and synonym handling
from ctgov_terms import load_synonyms, normalize_condition

# Precision and validation metrics
from precision_metrics import PrecisionCalculator, ValidationMetrics

__all__ = [
    # Version
    "__version__",
    # Core classes
    "CTGovSearcher",
    "SearchResult",
    "RecallMetrics",
    # Utility functions
    "get_session",
    "fetch_nct_ids",
    "fetch_studies",
    # Terminology functions
    "load_synonyms",
    "normalize_condition",
    # Metrics classes
    "PrecisionCalculator",
    "ValidationMetrics",
]
