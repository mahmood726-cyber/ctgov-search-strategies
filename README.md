# CT.gov Search Strategy Tool

![Version](https://img.shields.io/badge/version-3.0.0-purple)
![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![API Recall](https://img.shields.io/badge/API%20recall-99%25-brightgreen)
![NCT IDs](https://img.shields.io/badge/reference%20NCTs-1736-orange)

**A systematic review search tool for ClinicalTrials.gov.**

Features PICO-based search generation, 7-database translation, heuristic quality assessment, and publication-ready reporting.

### Important Terminology

| Term | Definition |
|------|------------|
| **API Recall** | % of known NCT IDs retrievable via CT.gov API (we validated 99%) |
| **Search Sensitivity** | % of ALL relevant studies found (requires human screening to validate) |

**Note**: We validated 99% API recall (known NCT IDs are retrievable via the API). This is NOT the same as search sensitivity, which would require prospective human screening to measure.

## Features

### Core Functionality
- **10 Search Strategies** - Tested against 1,736 Cochrane NCT IDs (99% API recall)
- **ML Strategy Optimizer** - Personalized recommendations based on condition and goals
- **Multi-Registry Search** - ANZCTR, ChiCTR, DRKS, CTRI, jRCT + WHO ICTRP
- **AACT Database Integration** - Direct NCT ID validation

### Advanced Search (NEW in v3.0)
- **PICO Search Generator** - Automated strategy from research questions (pattern-based, not validated NLP)
- **7-Database Translator** - PubMed, Embase, Cochrane, CT.gov, WoS, CINAHL, PsycINFO
  - **Note**: Syntax is approximate; always verify in target platform
- **Semantic Similarity** - Find related studies using TF-IDF
- **Quality Assessor** - Heuristic scoring with Gold/Silver/Bronze grading
  - **Note**: Does NOT replace PRESS 2015 peer review

### Search Methodology
- **PRESS 2015-Informed Scoring** - Heuristic 6-element validation (not equivalent to peer review)
- **Cochrane HSSS** - Official Cochrane Highly Sensitive Search Strategy for RCT filter
- **Boolean Optimization** - Synonyms, truncation, 50+ spelling variants
- **Grey Literature Guidance** - CADTH Grey Matters source recommendations
- **ML Screening Estimation** - Workload reduction estimates
  - **Caveat**: Published estimates vary 30-90%; not validated predictions

### Benchmarking & Validation
- **Reference Datasets** - 12 medical categories from Cochrane reviews (sample, not exhaustive)
- **Reference Information** - Context about other SR tools (Rayyan, ASReview, etc.)
  - **Note**: Screening tools measure different things than search tools
- **API Recall Testing** - Test whether known NCT IDs are retrievable
- **Wilson Score CIs** - Proper confidence intervals for proportions

### Export & Reporting
- **SR Tool Integration** - Export to Covidence, Rayyan, EndNote (RIS)
- **PRISMA Flow Diagrams** - PRISMA 2020 compliant auto-generation
- **Publication Reports** - Markdown/LaTeX with methods section text
- **ROC Curve Visualization** - Interactive performance analysis

### Progressive Web App
- **Offline Support** - Works without internet after first load
- **Search History** - Track, bookmark, and export your searches
- **Install as App** - Add to home screen on mobile/desktop

## Quick Start

### Web Application (Recommended)

1. Open `CTGov-Search-Complete.html` in any modern browser
2. Enter a condition (e.g., "type 2 diabetes")
3. Select a strategy or use the **Strategy Optimizer** for recommendations
4. Export results to Covidence, Rayyan, or RIS format

### Python CLI

```bash
# Install
pip install -e .

# Search with a specific strategy
ctgov-search search "breast cancer" -s S1

# Compare all strategies
ctgov-search compare "hypertension"

# Validate NCT IDs
ctgov-workflow validate NCT03702452
```

## Search Strategies

| ID | Name | Recall | Precision | NNS | Best For |
|----|------|--------|-----------|-----|----------|
| S1 | Condition Only | 98.7% | 15.2% | 6.6 | Maximum recall |
| S2 | Interventional Studies | 98.7% | 18.5% | 5.4 | General searches |
| S3 | Randomized Allocation | 98.7% | 22.3% | 4.5 | RCT-focused reviews |
| S4 | Phase 3/4 Studies | 45.5% | 45.2% | 2.2 | Late-phase only |
| S5 | Has Posted Results | 63.6% | 35.8% | 2.8 | Results available |
| S6 | Completed Status | 87.0% | 28.4% | 3.5 | Completed trials |
| S7 | Interventional + Completed | 87.0% | 32.1% | 3.1 | Quality focus |
| S8 | RCT + Phase 3/4 + Completed | 42.9% | 52.3% | 1.9 | Highest quality |
| S9 | Full-Text RCT Keywords | 79.2% | 25.6% | 3.9 | Keyword search |
| S10 | Treatment RCTs Only | 89.6% | 30.2% | 3.3 | Treatment purpose |

## ML Strategy Optimizer

The Strategy Optimizer uses machine learning to recommend the best search strategy:

```python
from strategy_optimizer import recommend_strategy, SearchGoal

# Get recommendations for a condition
recommendations = recommend_strategy(
    condition="type 2 diabetes",
    goal=SearchGoal.BALANCED,
    min_recall=0.85
)

for rec in recommendations[:3]:
    print(f"{rec.strategy_id}: {rec.name} (Score: {rec.score:.2f})")
```

### Search Goals
- **Maximum Recall** - Find all relevant studies (Cochrane reviews)
- **Balanced** - Optimal trade-off (most systematic reviews)
- **High Precision** - Minimize irrelevant results (rapid reviews)
- **Quick Overview** - Fast feasibility assessment

## Multi-Registry Search

Search multiple clinical trial registries simultaneously:

```python
from registry_adapters import UnifiedRegistrySearch, RegistryType

search = UnifiedRegistrySearch()

# Search all registries
results = search.search_all_registries("diabetes")
print(f"Total: {results.total_count} studies from {len(results.registries_searched)} registries")

# Search specific registries
results = search.search(
    "breast cancer",
    registries=[RegistryType.ANZCTR, RegistryType.DRKS]
)
```

### Supported Registries
- **ANZCTR** - Australian New Zealand Clinical Trials Registry
- **ChiCTR** - Chinese Clinical Trial Registry
- **DRKS** - German Clinical Trials Register
- **CTRI** - Clinical Trials Registry - India
- **jRCT** - Japan Registry of Clinical Trials

## Search Methodology Module

The `search_methodology.py` module implements search practices informed by academic literature:

### PRESS 2015 Guidelines Validation
Validate searches against the Peer Review of Electronic Search Strategies (PRESS) guidelines:

```python
from search_methodology import SearchMethodology

methodology = SearchMethodology()

# Create comprehensive search with full validation
result = methodology.create_comprehensive_search(
    condition="type 2 diabetes",
    intervention="metformin",
    synonyms={
        "condition": ["T2DM", "NIDDM", "diabetes mellitus type 2"],
        "intervention": ["glucophage", "metformin hydrochloride"]
    }
)

print(f"PRESS Score: {result['validation']['press']['overall_score']:.1%}")
print(f"Cochrane Compliance: {result['validation']['cochrane_compliance']['score']}%")
```

### Boolean Query Optimization
Build optimized Boolean queries with spelling variants and synonyms:

```python
from search_methodology import BooleanOptimizer

optimizer = BooleanOptimizer()

# Build optimized query from PICO concepts
query = optimizer.optimize_query({
    "population": ["heart failure", "cardiac failure", "CHF"],
    "intervention": ["digoxin", "digitalis"]
})
```

### Grey Literature Search Guidance
Get CADTH Grey Matters-compliant source recommendations:

```python
from search_methodology import GreyLiteratureSearcher

grey = GreyLiteratureSearcher()

# Get recommended sources
sources = grey.get_recommended_sources(
    review_type="systematic",
    topic_area="clinical"
)

# Generate search protocol
protocol = grey.generate_search_protocol(
    condition="COVID-19",
    intervention="remdesivir"
)
```

### ML Screening Workload Estimation
Estimate potential workload reduction from ML-assisted screening:

```python
from search_methodology import SearchMethodology

methodology = SearchMethodology()

workload = methodology.estimate_screening_workload(
    expected_results=5000,
    estimated_relevant=50
)

print(f"ML can reduce workload by: {workload['workload_reduction_percent']}%")
```

### Academic References
- McGowan J, et al. PRESS 2015 Guideline Statement (J Clin Epidemiol 2016)
- Lefebvre C, et al. Cochrane Handbook Chapter 4 (v6.5, 2024)
- CADTH Grey Matters Checklist
- ASReview Active Learning methodology

## Advanced Search Module (NEW in v3.0)

The `advanced_search.py` module provides additional search capabilities:

**Important Limitations:**
- PICO extraction uses simple pattern matching, not validated NLP
- Quality scores are heuristic and do NOT replace expert peer review
- Database translations are approximate; always verify in target platform

### PICO Search Generator
Create searches automatically from research questions:

```python
from advanced_search import SystematicReviewSearchTool

tool = SystematicReviewSearchTool()

# Generate complete search from research question
result = tool.create_search_from_question(
    research_question="What is the effectiveness of metformin compared to placebo for glycemic control in type 2 diabetes?",
    target_databases=["pubmed", "embase", "ctgov"]
)

print(f"Quality Score: {result['quality_assessment']['score']}/100 (heuristic)")
print(f"PubMed Search:\n{result['searches']['pubmed']['search_strategy']}")
```

### Multi-Database Translation
Translate searches between 7 databases:

```python
from advanced_search import DatabaseTranslator

translator = DatabaseTranslator()

# Translate PubMed search to Embase
result = translator.translate(
    search='(diabetes[mesh] OR diabetes[tiab]) AND metformin*[tiab]',
    from_db="pubmed",
    to_db="embase"
)

print(f"Embase Search: {result['translated']}")
print(f"Warnings: {result['warnings']}")
```

### Search Quality Assessment
Get comprehensive quality scoring:

```python
from advanced_search import SearchQualityAssessor

assessor = SearchQualityAssessor()

assessment = assessor.assess(
    search_strategy=my_search,
    databases_searched=["pubmed", "embase", "cochrane"]
)

print(f"Grade: {assessment.level.value}")  # gold, silver, bronze
print(f"Score: {assessment.score}/100")
print(f"Strengths: {assessment.strengths}")
print(f"Weaknesses: {assessment.weaknesses}")
```

## Benchmarking Module

The `benchmarks.py` module provides API recall testing and reference information:

**Important Notes:**
- The NCT ID datasets are reference samples, not exhaustive gold standards
- API recall ≠ search sensitivity (different concepts)
- Screening tools (Rayyan, ASReview) measure different things than search tools

### API Recall Testing
Test whether known NCT IDs are retrievable via the CT.gov API:

```python
from benchmarks import ValidationTestSuite, GoldStandardDataset

# Get reference dataset
dataset = GoldStandardDataset.get_dataset("cardiovascular")
print(f"Reference NCT IDs: {len(dataset['nct_ids'])}")

# Run API recall test
suite = ValidationTestSuite()
result = suite.run_api_recall_test(
    search_function=my_search_function,
    gold_standard_ids=set(dataset['nct_ids']),
    condition="cardiovascular"
)

print(f"API Recall: {result['api_recall']:.1%}")  # % of known NCT IDs retrievable
print(f"Grade: {result['grade']}")
# Note: This is NOT search sensitivity
```

### Reference Information
Get context about other SR tools (for background, not direct comparison):

```python
from benchmarks import IndustryBenchmarks

# Get information about other tools
info = IndustryBenchmarks.get_tool_info("rayyan")
print(f"Tool Type: {info['tool_type']}")  # "screening"
print(f"Note: {info['notes']}")
# Note: Screening tools measure classification accuracy, not search recall
```

## Export Formats

### Covidence Export
```python
from ris_export import export_to_covidence

export_to_covidence(studies, "search_results.csv")
```

### Rayyan Export
```python
from ris_export import export_to_rayyan

export_to_rayyan(studies, "search_results.csv")
```

### PRISMA Flow Diagram
```python
from prisma_generator import PRISMAGenerator

generator = PRISMAGenerator()
generator.set_identification(
    database_results={"ClinicalTrials.gov": 1500, "ANZCTR": 200},
    register_results={"ICTRP": 300}
)
generator.set_screening(duplicates_removed=150, excluded=800)
generator.set_eligibility(excluded=400, reasons={"Not RCT": 200, "Wrong population": 200})
generator.set_included(final_count=150)

svg = generator.generate_svg()
```

## MeSH Term Integration

Expand searches with MeSH terminology:

```python
from mesh_integration import MeSHIntegration

mesh = MeSHIntegration()

# Get MeSH terms for a condition
terms = mesh.get_mesh_terms("diabetes")
print(f"MeSH terms: {terms.mesh_terms}")
print(f"Synonyms: {terms.synonyms}")

# Build expanded query
query = mesh.build_expanded_query("hypertension")
```

## Validation Dataset

Our validation dataset includes **502 NCT IDs** across 17 condition categories:

| Category | NCT IDs | Source |
|----------|---------|--------|
| Diabetes | 77 | Cochrane, Published SRs |
| Hypertension | 62 | Cochrane, AHRQ |
| Cardiovascular | 45 | ESC Guidelines |
| Cancer | 38 | Cochrane Oncology |
| Mental Health | 35 | Cochrane CDSR |
| Infectious Disease | 32 | WHO/Cochrane |
| ... | ... | ... |

```python
from tests.validation_data import get_all_nct_ids, get_nct_ids_by_condition

# Get all validated NCT IDs
all_ncts = get_all_nct_ids()
print(f"Total: {len(all_ncts)} NCT IDs")

# Get NCT IDs for a specific condition
diabetes_ncts = get_nct_ids_by_condition("diabetes")
```

## Project Structure

```
ctgov-search-strategies/
├── CTGov-Search-Complete.html  # Main web application (PWA)
├── manifest.json               # PWA manifest
├── service-worker.js           # Offline support
├── README.md                   # This file
│
├── # Core Modules
├── ctgov_search.py            # Core search functionality
├── ctgov_workflow.py          # Workflow automation
├── strategy_optimizer.py      # ML-powered recommendations
├── mesh_integration.py        # MeSH/SNOMED integration
├── prisma_generator.py        # PRISMA diagram generation
├── ris_export.py              # Export to Covidence/Rayyan/RIS
├── precision_metrics.py       # Recall/precision calculation
│
├── # Registry Adapters
├── registry_adapters/
│   ├── __init__.py            # Unified search interface
│   ├── base_adapter.py        # Base adapter class
│   ├── anzctr_adapter.py      # ANZCTR adapter
│   ├── chictr_adapter.py      # ChiCTR adapter
│   ├── drks_adapter.py        # DRKS adapter
│   ├── ctri_adapter.py        # CTRI adapter
│   └── jrct_adapter.py        # jRCT adapter
│
├── # Validation Data
├── tests/
│   ├── validation_data/
│   │   ├── expanded_nct_dataset.py  # 502 validated NCT IDs
│   │   └── aact_validator.py        # AACT validation tools
│   └── test_*.py              # Test files
│
├── # Documentation
├── docs/
│   ├── api/                   # API reference
│   └── strategies.md          # Strategy documentation
│
└── # Data
    └── data/
        └── condition_synonyms.json  # Synonym mappings
```

## Configuration

### Environment Variables

```env
# AACT Database (optional, for advanced validation)
AACT_USER=your_username
AACT_PASSWORD=your_password
```

### Python Configuration

```python
# ctgov_config.py
CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"
DEFAULT_TIMEOUT = 30
DEFAULT_PAGE_SIZE = 1000
DEFAULT_RATE_LIMIT = 0.3
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test module
pytest tests/test_strategy_optimizer.py

# Skip integration tests
pytest -m "not integration"
```

## Key Findings

| Finding | Detail |
|---------|--------|
| **CT.gov API Limitation** | ~12.7% of NCT IDs unfindable via standard API |
| **AACT Database** | 100% recall with direct NCT ID queries |
| **Best Strategy (S1)** | 98.7% recall with condition-only search |
| **Validation Dataset** | 502 NCT IDs from Cochrane reviews & published SRs |

**Recommendation**: For systematic reviews requiring complete recall, supplement CT.gov API searches with AACT database queries and multi-registry searches.

## Changelog

### v2.0.0 (2025-01)
- Added ML Strategy Optimizer with condition classification
- Added multi-registry search (ANZCTR, ChiCTR, DRKS, CTRI, jRCT)
- Added Covidence/Rayyan export formats
- Added PRISMA flow diagram generator
- Added MeSH/SNOMED term integration
- Added ROC curve visualization
- Added PWA support with offline mode
- Added search history and bookmarks
- Expanded validation dataset to 502 NCT IDs
- Added AACT validation in web app

### v1.0.0 (2024-06)
- Initial release with 10 search strategies
- Basic validation with 155 NCT IDs
- CLI tools and web interface

## Citation

```bibtex
@software{ctgov_search_strategies,
  title = {CT.gov Search Strategy Tool},
  author = {Pairwise70 Project},
  year = {2025},
  url = {https://github.com/ctgov-search-strategies/ctgov-search}
}
```

## License

MIT License - See [LICENSE](LICENSE) for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
