# CT.gov Search Strategies

A comprehensive Python toolkit for developing and validating search strategies for ClinicalTrials.gov (CT.gov) to identify RCTs relevant to systematic reviews.

## Overview

This project provides validated search strategies for ClinicalTrials.gov, enabling systematic reviewers to:

- **Search efficiently**: Use 10 validated strategies optimized for different use cases
- **Calculate recall**: Validate search performance against gold standard NCT IDs
- **Measure precision**: Analyze screening burden with Number Needed to Screen (NNS)
- **Expand synonyms**: Automatically include condition synonyms for improved recall
- **Export results**: Generate reports and export data in multiple formats

## Key Findings

Our validation research against Cochrane systematic review data revealed critical insights:

| Finding | Detail |
|---------|--------|
| **CT.gov API Limitation** | ~12.7% of known RCT NCT IDs are unfindable via the standard API |
| **AACT Database** | Provides 100% recall when using direct NCT ID queries |
| **Best Strategy (S1)** | Achieves 98.7% recall with condition-only search |
| **Validation Dataset** | 155 NCT IDs from 501 Cochrane systematic reviews |

!!! warning "Recommendation"
    For systematic reviews requiring complete recall, supplement CT.gov API searches with AACT database queries.

## Installation

### Requirements

- Python 3.8 or higher
- pip package manager

### Quick Install

```bash
# Clone the repository
git clone https://github.com/ctgov-search-strategies/ctgov-search.git
cd ctgov-search-strategies

# Install the package
pip install .

# Or for development (includes testing tools)
pip install -e ".[dev]"
```

### Dependencies

The package automatically installs the following dependencies:

- `requests` - HTTP client for API calls
- `python-dotenv` - Environment variable management
- `psycopg2-binary` - PostgreSQL adapter for AACT database (optional)

## Quick Start

### Python API

```python
from ctgov_search import CTGovSearcher

# Initialize the searcher
searcher = CTGovSearcher()

# Search for diabetes trials using Strategy S1 (maximum recall)
result = searcher.search("diabetes", strategy="S1")
print(f"Found {result.total_count:,} studies")

# Compare all 10 strategies
results = searcher.compare_all_strategies("diabetes")
for r in results:
    print(f"{r.strategy_id}: {r.total_count:,} studies")
```

### Command Line Interface

Three CLI tools are available after installation:

```bash
# Search with a specific strategy
ctgov-search search diabetes -s S1

# Compare all strategies for a condition
ctgov-search compare "breast cancer"

# List available strategies
ctgov-search strategies
```

### Interactive HTML Tester

For quick browser-based testing:

1. Open `CTGov-Search-Tester.html` in your browser
2. Enter a condition (e.g., "hypertension")
3. Click "Search CT.gov" to see results
4. Use "Compare All Strategies" to compare all 10 strategies

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# AACT Database Credentials (required for validation)
AACT_USER=your_username
AACT_PASSWORD=your_password
```

Register for free AACT credentials at: [https://aact.ctti-clinicaltrials.org/users/sign_up](https://aact.ctti-clinicaltrials.org/users/sign_up)

### Configuration Options

Edit `ctgov_config.py` to customize:

```python
# API Configuration
CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"
DEFAULT_TIMEOUT = 30          # Request timeout in seconds
DEFAULT_PAGE_SIZE = 1000      # Max results per page
DEFAULT_RATE_LIMIT = 0.3      # Delay between requests (seconds)
```

## Project Structure

```
ctgov-search-strategies/
├── ctgov_search.py          # Core search module
├── ctgov_utils.py           # Utility functions
├── ctgov_config.py          # Shared configuration
├── ctgov_terms.py           # Synonym handling
├── precision_metrics.py     # Precision/recall metrics
├── ctgov_workflow.py        # Workflow automation
├── aact_validation.py       # AACT database validation
├── data/
│   ├── extracted_studies.csv
│   ├── condition_synonyms.json
│   └── ...
├── tests/                   # Test suite
├── docs/                    # Documentation
└── output/                  # Results output
```

## Next Steps

- [Search Strategies](strategies.md) - Learn about all 10 validated strategies
- [API Reference](api/index.md) - Detailed API documentation
- [Validation](validation.md) - Understand the validation methodology

## License

MIT License - For research purposes.

## Citation

If you use this tool in your research, please cite:

```
CT.gov Search Strategy Validation Project
A comprehensive toolkit for ClinicalTrials.gov search strategy validation
https://github.com/ctgov-search-strategies/ctgov-search
```
