# CTGovSearcher Class

The `CTGovSearcher` class provides a comprehensive interface for searching ClinicalTrials.gov using the API v2.

## Class Overview

```python
from ctgov_search import CTGovSearcher

class CTGovSearcher:
    """
    Comprehensive ClinicalTrials.gov Search Interface

    Features:
    - 10 validated search strategies
    - NCT ID validation
    - Recall/precision calculation
    - MeSH synonym expansion
    - Batch searching
    - Export utilities
    """
```

## Constructor

### `__init__(timeout, synonyms_path, user_agent)`

Initialize the CTGovSearcher with optional configuration.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout` | `int` | `30` | Request timeout in seconds |
| `synonyms_path` | `Optional[str]` | `None` | Path to custom synonyms JSON file |
| `user_agent` | `str` | `"CTgov-Search-Strategy-Validator/2.1"` | User-Agent header for HTTP requests |

**Example:**

```python
from ctgov_search import CTGovSearcher

# Default configuration
searcher = CTGovSearcher()

# Custom configuration
searcher = CTGovSearcher(
    timeout=60,
    synonyms_path="data/my_synonyms.json",
    user_agent="MyApp/1.0"
)
```

## Search Methods

### `search(condition, strategy, intervention, page_size, return_studies)`

Execute a search using a specified strategy.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `condition` | `str` | *required* | Medical condition to search |
| `strategy` | `str` | `"S1"` | Strategy ID (S1-S10) |
| `intervention` | `Optional[str]` | `None` | Optional intervention filter |
| `page_size` | `int` | `100` | Number of results to return (max 1000) |
| `return_studies` | `bool` | `False` | Whether to return study details |

**Returns:** `SearchResult`

**Raises:** `ValueError` if unknown strategy ID provided

**Example:**

```python
from ctgov_search import CTGovSearcher

searcher = CTGovSearcher()

# Basic search
result = searcher.search("diabetes", strategy="S1")
print(f"Found {result.total_count:,} studies")
print(f"Execution time: {result.execution_time:.2f}s")

# Search with study details
result = searcher.search(
    "hypertension",
    strategy="S3",
    page_size=50,
    return_studies=True
)
for study in result.studies[:5]:
    nct_id = study["protocolSection"]["identificationModule"]["nctId"]
    title = study["protocolSection"]["identificationModule"]["briefTitle"]
    print(f"{nct_id}: {title[:60]}...")
```

---

### `compare_all_strategies(condition, intervention)`

Run all 10 strategies for a condition and compare results.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `condition` | `str` | *required* | Medical condition to search |
| `intervention` | `Optional[str]` | `None` | Optional intervention filter |

**Returns:** `List[SearchResult]` - Results for all 10 strategies

**Example:**

```python
from ctgov_search import CTGovSearcher

searcher = CTGovSearcher()

# Compare all strategies
results = searcher.compare_all_strategies("diabetes")

# Display comparison
baseline = results[0].total_count
for r in results:
    pct = (r.total_count / baseline * 100) if baseline > 0 else 0
    print(f"{r.strategy_id}: {r.total_count:>6,} ({pct:>5.1f}%)")
```

---

### `search_with_synonyms(condition, strategy)`

Search using condition and all known synonyms (OR logic).

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `condition` | `str` | *required* | Base condition |
| `strategy` | `str` | `"S1"` | Strategy to use |

**Returns:** `SearchResult` with combined query

**Example:**

```python
from ctgov_search import CTGovSearcher

searcher = CTGovSearcher()

# Search with automatic synonym expansion
result = searcher.search_with_synonyms("diabetes", strategy="S1")
print(f"Results with synonyms: {result.total_count:,}")
print(f"Strategy: {result.strategy_name}")
```

---

### `search_by_nct_ids(nct_ids)`

Search for specific NCT IDs.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `nct_ids` | `List[str]` | List of NCT IDs to search |

**Returns:** `SearchResult` with matching studies

**Example:**

```python
from ctgov_search import CTGovSearcher

searcher = CTGovSearcher()

# Lookup specific NCT IDs
nct_ids = ["NCT03702452", "NCT00400712", "NCT01234567"]
result = searcher.search_by_nct_ids(nct_ids)

print(f"Found {result.total_count} of {len(nct_ids)} studies")
for study in result.studies:
    nct = study["protocolSection"]["identificationModule"]["nctId"]
    print(f"  - {nct}")
```

## Validation Methods

### `validate_nct_ids(nct_ids)`

Validate that NCT IDs exist on CT.gov.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `nct_ids` | `List[str]` | List of NCT IDs to validate |

**Returns:** `Dict[str, bool]` - Maps NCT ID to existence (True/False)

**Example:**

```python
from ctgov_search import CTGovSearcher

searcher = CTGovSearcher()

# Validate NCT IDs
nct_ids = ["NCT03702452", "NCT00400712", "NCT99999999"]
validation = searcher.validate_nct_ids(nct_ids)

for nct_id, exists in validation.items():
    status = "Valid" if exists else "Not found"
    print(f"{nct_id}: {status}")
```

---

### `calculate_recall(condition, known_nct_ids, strategy)`

Calculate recall of a search strategy against known included studies.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `condition` | `str` | *required* | Condition to search |
| `known_nct_ids` | `List[str]` | *required* | NCT IDs known to be relevant |
| `strategy` | `str` | `"S1"` | Strategy to test |

**Returns:** `RecallMetrics` with recall percentage and found/missed lists

**Example:**

```python
from ctgov_search import CTGovSearcher

searcher = CTGovSearcher()

# Gold standard NCT IDs from your systematic review
known_ncts = ["NCT03702452", "NCT00400712", "NCT01234567"]

# Calculate recall for each strategy
for strategy in ["S1", "S3", "S7"]:
    metrics = searcher.calculate_recall("diabetes", known_ncts, strategy=strategy)
    print(f"{strategy}: Recall={metrics.recall:.1f}% ({metrics.found}/{metrics.total_known})")

    if metrics.nct_ids_missed:
        print(f"  Missed: {', '.join(metrics.nct_ids_missed)}")
```

## Utility Methods

### `get_study_details(nct_id)`

Get full details for a specific study.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `nct_id` | `str` | NCT ID of the study |

**Returns:** `Optional[Dict[str, Any]]` - Study details or None if not found

**Example:**

```python
from ctgov_search import CTGovSearcher

searcher = CTGovSearcher()

# Get study details
details = searcher.get_study_details("NCT03702452")

if details:
    protocol = details.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    print(f"Title: {ident.get('briefTitle')}")
    print(f"Status: {protocol.get('statusModule', {}).get('overallStatus')}")
```

---

### `export_results_csv(results, filepath)`

Export search results to CSV file.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `results` | `List[SearchResult]` | List of search results to export |
| `filepath` | `str` | Path to output CSV file |

**Example:**

```python
from ctgov_search import CTGovSearcher

searcher = CTGovSearcher()

# Compare strategies and export
results = searcher.compare_all_strategies("diabetes")
searcher.export_results_csv(results, "output/diabetes_comparison.csv")
```

---

### `generate_search_report(condition)`

Generate a formatted text report for a condition search.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `condition` | `str` | Medical condition to report on |

**Returns:** `str` - Formatted report string

**Example:**

```python
from ctgov_search import CTGovSearcher

searcher = CTGovSearcher()

# Generate report
report = searcher.generate_search_report("diabetes")
print(report)

# Save to file
with open("output/diabetes_report.txt", "w") as f:
    f.write(report)
```

## Available Strategies

The `STRATEGIES` class attribute contains all 10 validated search strategies:

| ID | Name | Description | Sensitivity |
|----|------|-------------|-------------|
| S1 | Condition Only | Cochrane recommended - no filters | High |
| S2 | Interventional Studies | All interventional study types | High |
| S3 | Randomized Allocation | True RCTs - excludes single-arm | Medium |
| S4 | Phase 3/4 Studies | Later phase trials only | Low |
| S5 | Has Posted Results | Studies with results on CT.gov | Low |
| S6 | Completed Status | Completed trials only | Medium |
| S7 | Interventional + Completed | Completed interventional studies | Medium |
| S8 | RCT + Phase 3/4 + Completed | Highest quality subset | Low |
| S9 | Full-Text RCT Keywords | Text search with RCT terms | Medium |
| S10 | Treatment RCTs Only | Randomized + Treatment purpose | Medium |

**Access strategy information:**

```python
from ctgov_search import CTGovSearcher

# List all strategies
for strategy_id, config in CTGovSearcher.STRATEGIES.items():
    print(f"{strategy_id}: {config['name']}")
    print(f"  {config['description']}")
    print(f"  Sensitivity: {config['sensitivity']}")
```

## Complete Example

```python
from ctgov_search import CTGovSearcher

def analyze_search_strategies(condition: str, known_ncts: list[str]):
    """Complete workflow for analyzing search strategies."""

    searcher = CTGovSearcher(timeout=60)

    # 1. Compare all strategies
    print(f"Analyzing strategies for: {condition}")
    print("=" * 60)

    results = searcher.compare_all_strategies(condition)
    baseline = results[0].total_count

    print(f"\n{'Strategy':<5} {'Name':<30} {'Count':>10} {'% Base':>10}")
    print("-" * 60)

    for r in results:
        pct = (r.total_count / baseline * 100) if baseline else 0
        print(f"{r.strategy_id:<5} {r.strategy_name:<30} {r.total_count:>10,} {pct:>9.1f}%")

    # 2. Calculate recall for top strategies
    print(f"\nRecall Analysis (against {len(known_ncts)} known NCT IDs):")
    print("-" * 60)

    for strategy in ["S1", "S3", "S7"]:
        metrics = searcher.calculate_recall(condition, known_ncts, strategy=strategy)
        print(f"{strategy}: Recall={metrics.recall:.1f}% ({metrics.found}/{metrics.total_known})")

    # 3. Export results
    searcher.export_results_csv(results, f"output/{condition.replace(' ', '_')}_strategies.csv")
    print(f"\nResults exported to: output/{condition.replace(' ', '_')}_strategies.csv")


# Run analysis
known_ids = ["NCT03702452", "NCT00400712", "NCT01234567"]
analyze_search_strategies("diabetes", known_ids)
```
