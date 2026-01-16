# CT.gov Search Strategy Development Project

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)

A research project to develop and validate optimal search strategies for ClinicalTrials.gov (CT.gov) to find RCTs relevant to systematic reviews.

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/ctgov-search-strategies/ctgov-search.git
cd ctgov-search-strategies

# Install the package
pip install .

# Or for development (includes testing tools)
pip install -e ".[dev]"
```

### Interactive Tester

1. **Open the Search Tester**: Double-click `CTGov-Search-Tester.html`
2. Enter a condition (e.g., "hypertension") and click "Search CT.gov"
3. Compare strategies using the "Compare All Strategies" button

## Key Findings

Our validation research revealed critical insights for systematic reviewers:

| Finding | Detail |
|---------|--------|
| **CT.gov API Limitation** | ~12.7% of known RCT NCT IDs are unfindable via the standard API |
| **AACT Database** | Provides 100% recall when using direct NCT ID queries |
| **Best Strategy (S1)** | Achieves 98.7% recall with condition-only search |
| **Validation Dataset** | 155 NCT IDs from 501 Cochrane systematic reviews |

**Recommendation**: For systematic reviews requiring complete recall, supplement CT.gov API searches with AACT database queries.

## CLI Usage

After installation, three command-line tools are available:

### ctgov-search

Search ClinicalTrials.gov with validated strategies:

```bash
# Single strategy search
ctgov-search search diabetes -s S1

# Compare all 10 strategies
ctgov-search compare "breast cancer"

# List available strategies
ctgov-search strategies
```

### ctgov-workflow

Run comprehensive search workflows:

```bash
# Full workflow with strategy comparison, synonym expansion, and multi-registry URLs
ctgov-workflow workflow "cystic fibrosis"

# Quick search with specific strategy
ctgov-workflow search diabetes -s S3

# Compare strategies for a condition
ctgov-workflow compare "heart failure"

# Validate a single NCT ID
ctgov-workflow validate NCT03702452
```

### ctgov-validate

Validate search recall against AACT database:

```bash
# Run AACT validation for unfindable NCT IDs
ctgov-validate
```

## API Usage (Python)

### Basic Search

```python
from ctgov_search import CTGovSearcher

# Initialize searcher
searcher = CTGovSearcher()

# Single strategy search
result = searcher.search("diabetes", strategy="S1")
print(f"Found {result.total_count:,} studies")

# Compare all strategies
results = searcher.compare_all_strategies("diabetes")
for r in results:
    print(f"{r.strategy_id}: {r.total_count:,}")
```

### Recall Validation

```python
from ctgov_search import CTGovSearcher

searcher = CTGovSearcher()

# Validate recall against known NCT IDs
known_ncts = ["NCT03702452", "NCT00400712", "NCT01234567"]
metrics = searcher.calculate_recall("diabetes", known_ncts, strategy="S1")

print(f"Recall: {metrics.recall:.1f}%")
print(f"Found: {metrics.found}/{metrics.total_known}")
print(f"Missed: {metrics.nct_ids_missed}")
```

### Synonym Expansion

```python
from ctgov_search import CTGovSearcher

searcher = CTGovSearcher(synonyms_path="data/condition_synonyms.json")

# Search with synonym expansion
result = searcher.search_with_synonyms("diabetes", strategy="S1")
print(f"Results with synonyms: {result.total_count:,}")
```

### NCT ID Validation

```python
from ctgov_search import CTGovSearcher

searcher = CTGovSearcher()

# Validate NCT IDs exist on CT.gov
nct_ids = ["NCT03702452", "NCT00400712", "NCT99999999"]
validation = searcher.validate_nct_ids(nct_ids)

for nct_id, exists in validation.items():
    status = "Valid" if exists else "Not found"
    print(f"{nct_id}: {status}")
```

### Workflow Automation

```python
from ctgov_workflow import CTgovWorkflow

workflow = CTgovWorkflow(output_dir="output")

# Run full workflow
results = workflow.full_workflow("cystic fibrosis", export=True)

# Get multi-registry search URLs
urls = workflow.generate_multi_registry_urls("diabetes")
for registry, url in urls.items():
    print(f"{registry}: {url}")
```

## Configuration

### Environment Variables (.env file)

Create a `.env` file in the project root for AACT database access:

```env
# AACT Database Credentials (required for validation)
AACT_USER=your_username
AACT_PASSWORD=your_password
```

Register for free AACT credentials at: https://aact.ctti-clinicaltrials.org/users/sign_up

### Configuration Settings (ctgov_config.py)

```python
# API Configuration
CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"
DEFAULT_TIMEOUT = 30          # Request timeout in seconds
DEFAULT_PAGE_SIZE = 1000      # Max results per page
DEFAULT_RATE_LIMIT = 0.3      # Delay between requests (seconds)
DEFAULT_USER_AGENT = "CTgov-Search-Strategy-Validator/2.1"
```

### Synonym Configuration

Edit `data/condition_synonyms.json` to add custom condition synonyms:

```json
{
  "diabetes": ["diabetes mellitus", "type 2 diabetes", "t2dm"],
  "hypertension": ["high blood pressure", "elevated blood pressure"]
}
```

Or pass a custom synonyms file via CLI:

```bash
ctgov-workflow --synonyms path/to/synonyms.json search diabetes
```

## Testing

Run the test suite with pytest:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=. --cov-report=term-missing

# Run specific test file
pytest tests/test_ctgov_search.py

# Run with verbose output
pytest -v

# Run only fast tests (skip integration tests)
pytest -m "not integration"
```

Test files:
- `tests/test_ctgov_search.py` - Core search functionality
- `tests/test_ctgov_config.py` - Configuration tests
- `tests/test_ctgov_utils.py` - Utility function tests
- `tests/test_ctgov_terms.py` - Term/synonym tests
- `tests/test_ctgov_advanced.py` - Advanced search features

## Project Structure

```
ctgov-search-strategies/
├── CTGov-Search-Tester.html    # Interactive search tester
├── PROJECT_PLAN.md             # Detailed project plan
├── README.md                   # This file
├── pyproject.toml              # Package configuration
├── ctgov_config.py             # Shared configuration
├── ctgov_search.py             # Core search module (CLI: ctgov-search)
├── ctgov_workflow.py           # Workflow automation (CLI: ctgov-workflow)
├── ctgov_utils.py              # Utility functions
├── ctgov_terms.py              # Synonym/term handling
├── aact_validation.py          # AACT database validation (CLI: ctgov-validate)
├── data/
│   ├── extracted_studies.csv   # 10,581 studies from 501 Cochrane reviews
│   ├── reviews_summary.csv     # Summary of 501 reviews
│   ├── review_conditions.csv   # Detected conditions per review
│   ├── condition_synonyms.json # Condition synonym mappings
│   ├── test_reviews.csv        # 30 reviews for validation testing
│   └── unique_studies.csv      # 10,074 unique study-year combos
├── scripts/
│   ├── extract_cochrane_data.R # R script to extract Cochrane data
│   ├── extract_conditions.R    # R script to detect conditions
│   ├── synonym_expansion.py    # Synonym expansion utilities
│   └── validate_and_recall.py  # Recall validation scripts
├── tests/                      # Test suite
├── docs/
│   └── decision-flowchart.html # Search strategy decision flowchart
├── analysis/                   # Analysis outputs
└── output/                     # Final results
```

## Search Strategies

Ten validated search strategies are available:

| ID | Name | Description | Recall |
|----|------|-------------|--------|
| S1 | Condition Only | Maximum recall, Cochrane recommended | 48.2% |
| S2 | Interventional Studies | All interventional study types | 53.9% |
| S3 | Randomized Allocation | True RCTs only (BEST BALANCE) | 63.2% |
| S4 | Phase 3/4 Studies | Later phase trials | 34.4% |
| S5 | Has Posted Results | Studies with results on CT.gov | 55.5% |
| S6 | Completed Status | Completed trials only | 51.7% |
| S7 | Interventional + Completed | Completed interventional studies | 56.8% |
| S8 | RCT + Phase 3/4 + Completed | Highest quality subset | 33.8% |
| S9 | Full-Text RCT Keywords | Text search with RCT terms | 51.6% |
| S10 | Treatment RCTs Only | Randomized + Treatment purpose | 60.0% |

## Decision Flowchart

For guidance on selecting the appropriate search strategy, see the interactive decision flowchart:

[docs/decision-flowchart.html](docs/decision-flowchart.html)

## Data Sources

### Cochrane Pairwise Data
- **Content**: 501 Cochrane systematic reviews with 10,581 study entries
- **Studies**: Named by author + year (e.g., "Carter 1970", "SHEP 1991")

### Condition Distribution (from 501 reviews)

| Condition | Count |
|-----------|-------|
| Other | 125 |
| Mental Health | 119 |
| Pain | 115 |
| Infection | 102 |
| Cardiovascular | 95 |
| Gastrointestinal | 79 |
| Neurological | 77 |
| Pregnancy | 75 |
| Hypertension | 62 |
| Respiratory | 62 |
| Renal | 55 |
| Diabetes | 50 |
| Cancer | 29 |
| Dermatology | 29 |

## CT.gov API Access

### CT.gov API v2
- **Base**: `https://clinicaltrials.gov/api/v2/studies`
- **Key Parameters**:
  - `query.cond` - Condition/disease
  - `query.intr` - Intervention/treatment
  - `query.term` - Full text search
  - `query.titles` - Title search
  - `filter.studyType=INTERVENTIONAL` - RCTs only
  - `filter.overallStatus=COMPLETED` - Completed studies

### Worker Proxy (for browser CORS)
- **URL**: `https://restless-term-5510.mahmood726.workers.dev/`
- **Usage**: `?url=<encoded CT.gov API URL>`

## Running R Scripts

### R Scripts (require R 4.5+)

```bash
# Extract Cochrane data
Rscript scripts/extract_cochrane_data.R

# Extract conditions
Rscript scripts/extract_conditions.R
```

## Citation

If you use this tool in your research, please cite:

```
CT.gov Search Strategy Validation Project
A comprehensive toolkit for ClinicalTrials.gov search strategy validation
https://github.com/ctgov-search-strategies/ctgov-search
```

## Author

Generated for Pairwise70 project - MAFI (Meta-Analysis Fragility Index)

## License

MIT License - For research purposes.
