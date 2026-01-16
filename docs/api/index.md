# API Reference

This section provides comprehensive documentation for the CT.gov Search Strategies Python API.

## Module Overview

The toolkit is organized into several modules, each handling specific functionality:

| Module | Description |
|--------|-------------|
| [`ctgov_search`](ctgov_search.md) | Core search functionality with `CTGovSearcher` class |
| [`ctgov_utils`](ctgov_utils.md) | HTTP utilities, pagination, and NCT ID extraction |
| [`precision_metrics`](precision_metrics.md) | Precision, recall, NNS, and validation metrics |
| `ctgov_config` | Shared configuration constants |
| `ctgov_terms` | Synonym loading and condition normalization |

## Quick Start

### Basic Search

```python
from ctgov_search import CTGovSearcher

# Initialize with default settings
searcher = CTGovSearcher()

# Search for a condition
result = searcher.search("diabetes", strategy="S1")
print(f"Found {result.total_count:,} studies")
```

### Calculate Recall

```python
from ctgov_search import CTGovSearcher

searcher = CTGovSearcher()

# Known NCT IDs from your systematic review
known_ncts = ["NCT03702452", "NCT00400712", "NCT01234567"]

# Calculate recall
metrics = searcher.calculate_recall("diabetes", known_ncts, strategy="S1")
print(f"Recall: {metrics.recall:.1f}%")
print(f"Found: {metrics.found}/{metrics.total_known}")
```

### Precision Analysis

```python
from precision_metrics import PrecisionCalculator, ValidationMetrics

calc = PrecisionCalculator()

# Calculate precision
precision = calc.calculate_precision(relevant_found=50, total_retrieved=500)
print(f"Precision: {precision:.2%}")

# Calculate Number Needed to Screen
nns = calc.calculate_nns(total_retrieved=500, relevant_found=50)
print(f"NNS: {nns:.1f}")
```

## Data Classes

### SearchResult

Container for search results from `CTGovSearcher.search()`:

```python
@dataclass
class SearchResult:
    strategy_id: str        # Strategy identifier (e.g., "S1")
    strategy_name: str      # Human-readable name
    condition: str          # Searched condition
    total_count: int        # Total studies found
    query_url: str          # API query URL
    execution_time: float   # Query execution time
    studies: List[Dict]     # Study details (if requested)
    error: Optional[str]    # Error message (if any)
```

### RecallMetrics

Container for recall validation results:

```python
@dataclass
class RecallMetrics:
    strategy_id: str            # Strategy tested
    total_known: int            # Total known relevant studies
    found: int                  # Studies found by search
    recall: float               # Recall percentage
    nct_ids_found: List[str]    # NCT IDs successfully found
    nct_ids_missed: List[str]   # NCT IDs missed
```

### StrategyResult

Container for strategy comparison results:

```python
@dataclass
class StrategyResult:
    strategy_id: str            # Strategy identifier
    strategy_name: str          # Human-readable name
    total_retrieved: int        # Total studies retrieved
    relevant_found: int         # Relevant studies found
    nct_ids_found: Set[str]     # NCT IDs found
    execution_time: float       # Execution time
```

## Error Handling

All API calls handle errors gracefully and return meaningful error messages:

```python
from ctgov_search import CTGovSearcher

searcher = CTGovSearcher()

# Invalid strategy ID
try:
    result = searcher.search("diabetes", strategy="INVALID")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Unknown strategy: INVALID. Valid: ['S1', 'S2', ...]

# Network errors are captured in SearchResult.error
result = searcher.search("diabetes")
if result.error:
    print(f"Search failed: {result.error}")
```

## Thread Safety

The `ctgov_utils` module provides thread-local session management:

```python
from ctgov_utils import get_session

# Each thread gets its own session with retry logic
session = get_session()
```

## Rate Limiting

The API automatically implements rate limiting to respect CT.gov's usage policies:

- Default delay: 0.3 seconds between requests
- Configurable via `ctgov_config.DEFAULT_RATE_LIMIT`

## Next Steps

- [CTGovSearcher Class](ctgov_search.md) - Full search API documentation
- [Utility Functions](ctgov_utils.md) - HTTP and extraction utilities
- [Precision Metrics](precision_metrics.md) - Validation metrics
