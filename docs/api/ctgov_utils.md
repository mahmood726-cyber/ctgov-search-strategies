# Utility Functions

The `ctgov_utils` module provides HTTP utilities, pagination helpers, and NCT ID extraction functions for interacting with the ClinicalTrials.gov API.

## Module Overview

```python
from ctgov_utils import (
    get_session,
    build_params,
    extract_nct_ids,
    iter_study_pages,
    fetch_nct_ids,
    fetch_total_count,
    fetch_matching_nct_ids,
    fetch_studies,
)
```

## Session Management

### `get_session(user_agent, accept)`

Return a thread-local requests session with consistent headers and retry logic.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_agent` | `str` | `"CTgov-Search-Strategy-Validator/2.1"` | User-Agent header value |
| `accept` | `str` | `"application/json"` | Accept header value |

**Returns:** `requests.Session` - Configured session instance

**Features:**

- Thread-local storage for concurrent use
- Automatic retry logic for transient failures
- Configurable with status codes: 429, 500, 502, 503, 504
- Exponential backoff (0.5s factor, 3 retries)

**Example:**

```python
from ctgov_utils import get_session

# Get thread-safe session
session = get_session()

# Custom user agent
session = get_session(user_agent="MyApp/1.0")

# Make requests
response = session.get("https://clinicaltrials.gov/api/v2/studies")
```

## Parameter Handling

### `build_params(query)`

Parse a query string into a params dictionary.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | URL query string (with or without leading '?') |

**Returns:** `Dict[str, str]` - Dictionary of query parameters

**Example:**

```python
from ctgov_utils import build_params

# Parse query string
params = build_params("query.cond=diabetes&filter.status=COMPLETED")
# Result: {'query.cond': 'diabetes', 'filter.status': 'COMPLETED'}

# Handles leading '?'
params = build_params("?query.cond=hypertension")
# Result: {'query.cond': 'hypertension'}
```

## NCT ID Extraction

### `extract_nct_ids(studies)`

Extract NCT IDs from CT.gov study records.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `studies` | `Iterable[Dict[str, Any]]` | Iterable of study dictionaries from API |

**Returns:** `Set[str]` - Set of uppercase NCT IDs

**Example:**

```python
from ctgov_utils import extract_nct_ids

# Extract NCT IDs from API response
studies = [
    {"protocolSection": {"identificationModule": {"nctId": "NCT12345678"}}},
    {"protocolSection": {"identificationModule": {"nctId": "NCT87654321"}}},
]

nct_ids = extract_nct_ids(studies)
print(nct_ids)  # {'NCT12345678', 'NCT87654321'}
```

## Pagination

### `iter_study_pages(session, params, timeout, page_size, max_pages)`

Yield paginated CT.gov API responses for a query.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session` | `requests.Session` | *required* | Configured requests session |
| `params` | `Dict[str, str]` | *required* | Query parameters |
| `timeout` | `int` | `30` | Request timeout in seconds |
| `page_size` | `int` | `1000` | Results per page |
| `max_pages` | `Optional[int]` | `None` | Max pages to fetch (None = unlimited) |

**Yields:** `Dict[str, Any]` - API response data for each page

**Example:**

```python
from ctgov_utils import get_session, iter_study_pages

session = get_session()
params = {"query.cond": "diabetes"}

# Iterate through pages
for page_num, data in enumerate(iter_study_pages(session, params, max_pages=5)):
    studies = data.get("studies", [])
    print(f"Page {page_num + 1}: {len(studies)} studies")

    # Check if there are more pages
    if not data.get("nextPageToken"):
        break
```

## Fetching Functions

### `fetch_nct_ids(session, params, timeout, page_size, max_pages)`

Fetch all NCT IDs for a query, returning IDs and total count.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session` | `requests.Session` | *required* | Configured session |
| `params` | `Dict[str, str]` | *required* | Query parameters |
| `timeout` | `int` | `30` | Request timeout |
| `page_size` | `int` | `1000` | Results per page |
| `max_pages` | `Optional[int]` | `None` | Max pages (None = all) |

**Returns:** `Tuple[Set[str], int]` - (NCT IDs set, total count)

**Example:**

```python
from ctgov_utils import get_session, fetch_nct_ids

session = get_session()
params = {"query.cond": "hypertension", "filter.overallStatus": "COMPLETED"}

nct_ids, total = fetch_nct_ids(session, params, max_pages=10)
print(f"Fetched {len(nct_ids)} NCT IDs (total: {total})")
```

---

### `fetch_total_count(session, params, timeout)`

Fetch only the total count for a query (without paging through results).

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session` | `requests.Session` | *required* | Configured session |
| `params` | `Dict[str, str]` | *required* | Query parameters |
| `timeout` | `int` | `30` | Request timeout |

**Returns:** `int` - Total count of matching studies

**Example:**

```python
from ctgov_utils import get_session, fetch_total_count

session = get_session()

# Quick count without fetching all records
count = fetch_total_count(session, {"query.cond": "breast cancer"})
print(f"Total studies: {count:,}")
```

---

### `fetch_matching_nct_ids(session, params, nct_ids, timeout, batch_size)`

Fetch NCT IDs that match both query parameters and a provided list.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session` | `requests.Session` | *required* | Configured session |
| `params` | `Dict[str, str]` | *required* | Base query parameters |
| `nct_ids` | `Iterable[str]` | *required* | NCT IDs to check |
| `timeout` | `int` | `30` | Request timeout |
| `batch_size` | `int` | `100` | IDs per batch request |

**Returns:** `Set[str]` - NCT IDs matching both query and provided list

**Example:**

```python
from ctgov_utils import get_session, fetch_matching_nct_ids

session = get_session()
params = {"query.cond": "diabetes"}

# Check which of your known NCT IDs match the condition search
known_ncts = ["NCT03702452", "NCT00400712", "NCT99999999"]
matching = fetch_matching_nct_ids(session, params, known_ncts)

print(f"Matching NCT IDs: {matching}")
```

---

### `fetch_studies(session, params, timeout, page_size, max_pages)`

Fetch all studies for a query, returning studies and total count.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session` | `requests.Session` | *required* | Configured session |
| `params` | `Dict[str, str]` | *required* | Query parameters |
| `timeout` | `int` | `30` | Request timeout |
| `page_size` | `int` | `1000` | Results per page |
| `max_pages` | `Optional[int]` | `None` | Max pages (None = all) |

**Returns:** `Tuple[List[Dict[str, Any]], int]` - (Study list, total count)

**Example:**

```python
from ctgov_utils import get_session, fetch_studies

session = get_session()
params = {
    "query.cond": "covid-19",
    "filter.overallStatus": "COMPLETED",
}

# Fetch first 3 pages of studies
studies, total = fetch_studies(session, params, max_pages=3)
print(f"Fetched {len(studies)} studies (total: {total})")

for study in studies[:5]:
    nct = study["protocolSection"]["identificationModule"]["nctId"]
    title = study["protocolSection"]["identificationModule"]["briefTitle"]
    print(f"  {nct}: {title[:50]}...")
```

## Configuration Constants

The module uses constants from `ctgov_config`:

| Constant | Default | Description |
|----------|---------|-------------|
| `CTGOV_API` | `"https://clinicaltrials.gov/api/v2/studies"` | API endpoint |
| `DEFAULT_PAGE_SIZE` | `1000` | Max results per page |
| `DEFAULT_USER_AGENT` | `"CTgov-Search-Strategy-Validator/2.1"` | User agent string |

## Retry Configuration

The session is configured with automatic retry logic:

| Setting | Value | Description |
|---------|-------|-------------|
| `total` | `3` | Maximum retry attempts |
| `backoff_factor` | `0.5` | Exponential backoff multiplier |
| `status_forcelist` | `(429, 500, 502, 503, 504)` | HTTP codes to retry |
| `allowed_methods` | `("GET", "HEAD", "OPTIONS")` | Methods to retry |

## Complete Example

```python
from ctgov_utils import (
    get_session,
    build_params,
    fetch_nct_ids,
    fetch_total_count,
    fetch_matching_nct_ids,
    extract_nct_ids,
)

def validate_nct_recall(condition: str, known_ncts: list[str]) -> float:
    """Calculate recall of known NCT IDs against a condition search."""

    session = get_session()

    # Get total count
    params = {"query.cond": condition}
    total = fetch_total_count(session, params)
    print(f"Total '{condition}' studies: {total:,}")

    # Find matching NCT IDs
    matching = fetch_matching_nct_ids(session, params, known_ncts)

    # Calculate recall
    recall = len(matching) / len(known_ncts) * 100 if known_ncts else 0

    print(f"Known NCT IDs: {len(known_ncts)}")
    print(f"Found: {len(matching)}")
    print(f"Recall: {recall:.1f}%")

    # Report missed
    missed = set(nct.upper() for nct in known_ncts) - matching
    if missed:
        print(f"Missed: {missed}")

    return recall


# Example usage
known = ["NCT03702452", "NCT00400712", "NCT01234567"]
validate_nct_recall("diabetes", known)
```
