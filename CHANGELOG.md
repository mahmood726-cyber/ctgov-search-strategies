# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-01-18 - Advanced Search Release

### Added

#### Advanced Search Module (`advanced_search.py`)
- **PICO Search Generator**: Automated search strategy generation from PICO elements
  - Simple pattern-based question parsing (not validated NLP)
  - 60+ medical abbreviation expansions (T2DM, MI, COPD, etc.)
  - Multi-database support (PubMed, Embase, CT.gov, Web of Science, CINAHL, PsycINFO)
  - RCT, systematic review, and observational study filters (based on Cochrane HSSS)
- **Semantic Similarity Search**: TF-IDF based document similarity
  - Find related studies from seed studies (citation chasing alternative)
  - Study prioritization by relevance score
  - Customizable vocabulary and weighting
- **Multi-Database Translator**: Convert searches between 7 databases
  - Approximate syntax translation (truncation, field tags, proximity)
  - Validation of translated queries
  - Warning system for unsupported features
  - **Note**: Always verify in target platform; syntax varies by vendor
- **Search Quality Assessor**: Heuristic quality scoring (0-100)
  - 6 components: comprehensiveness, structure, terminology, sensitivity, reproducibility, database coverage
  - Gold/Silver/Bronze/Needs Work grading
  - **Note**: Heuristic scoring only; does NOT replace PRESS 2015 peer review
- **Publication Report Generator**: PRISMA-compliant reporting
  - Markdown and LaTeX export formats
  - Automatic narrative generation
  - Methods section text generation

#### Benchmarking System (`benchmarks.py`)
- **Reference Datasets**: 12 medical categories from Cochrane reviews
  - 1,736 NCT IDs extracted (sample, not exhaustive gold standard)
  - 588 source systematic reviews
  - 99% API recall rate validated (i.e., API can retrieve known NCT IDs)
- **Reference Tools**: Information about other SR tools
  - Rayyan, ASReview, EPPI-Reviewer, Abstrackr
  - **Note**: These are screening tools with different purposes; not directly comparable
- **API Recall Testing**: Test whether known NCT IDs are retrievable via API
  - Wilson score confidence intervals
  - Automatic grading (A+ to F)
  - **Note**: API recall ≠ search sensitivity (different concepts)

#### Features
- **99% API Recall**: Known NCT IDs retrievable via CT.gov API (198/200 validated)
- **7 Database Syntax Support**: PubMed, Embase, Cochrane, CT.gov, WoS, CINAHL, PsycINFO
- **PRESS-Informed**: Heuristic validation inspired by PRESS 2015 (not equivalent to peer review)
- **Cochrane HSSS**: Uses official Cochrane Highly Sensitive Search Strategy for RCT filter

### Important Notes
- **API Recall ≠ Search Sensitivity**: We validated that 99% of known NCT IDs are retrievable via the CT.gov API. This is NOT the same as search sensitivity (finding all relevant studies), which requires prospective validation with human screening.
- **Heuristic Scoring**: Quality scores and workload estimates are heuristic approximations, not empirically validated predictions.
- **Database Translation**: Syntax mappings are approximate; always verify in the target platform's documentation.

---

## [2.2.0] - 2026-01-18

### Added

#### Search Methodology Module
- New `search_methodology.py` module implementing academic best practices
- PRESS 2015 Guidelines-informed validation (Peer Review of Electronic Search Strategies)
  - 6-element validation: translation, Boolean operators, subject headings, text words, spelling, limits
  - Heuristic scoring with recommendations
  - **Note**: Automated scoring uses heuristic weights; PRESS 2015 uses qualitative peer review
- Cochrane Handbook Chapter 4 (v6.5, September 2024) informed
  - Cochrane-compliant search building with proper formatting
  - Cochrane Highly Sensitive RCT Filter integration (official HSSS, not including low-specificity terms)
  - Automatic MeSH term and field tag suggestions
- Search Filter Validation with performance metrics
  - Sensitivity, specificity, precision, NPV, NNR, F1 calculations
  - Wilson score 95% confidence intervals
  - **Note**: Requires user-provided gold standard for meaningful validation

#### Boolean Query Optimization
- Automated query construction from PICO concepts
- Intelligent truncation application
- Phrase searching for multi-word terms
- 50+ US/UK spelling variant mappings
- Medical synonym suggestions
- Syntax validation with issue detection

#### Grey Literature Search Guidance
- CADTH Grey Matters-based source recommendations
- 5 trial registries with API indicators
- Regulatory agency sources (FDA, EMA, Health Canada)
- Conference abstracts and theses sources
- Preprint sources (medRxiv, bioRxiv, SSRN)
- Automated search protocol generation
- PRISMA-compliant documentation guidance

#### ML-Assisted Screening Features (Experimental)
- Workload reduction estimation
  - **Caveat**: Published estimates vary 30-90%; actual results depend on topic and screening criteria
  - Based on O'Mara-Eves A, et al. (Syst Rev. 2015;4:5)
- SAFE stopping heuristics (based on ASReview methodology)
- Study prioritization by keyword similarity
- Sample-size based recommendations
- Active learning guidance

#### Comprehensive Unit Tests
- 30+ unit tests for search methodology module
- PRESS validation tests
- Filter metrics calculation tests
- Boolean optimization tests
- Grey literature tests
- ML screening tests
- Edge case and error handling tests

### Research Base
Based on academic literature review including:
- McGowan J, et al. PRESS 2015 Guideline Statement (J Clin Epidemiol 2016)
- Lefebvre C, et al. Cochrane Handbook Chapter 4 (v6.5, 2024)
- Gusenbauer M, Gauster L. Literature sampling guidance (2025)
- Campbell Collaboration Grey Literature Guide (2024)
- ASReview Active Learning methodology
- CADTH Grey Matters Checklist

---

## [2.1.0] - 2026-01-18

### Added

#### Cochrane NCT ID Reference Dataset
- Extracted 1,904 unique NCT IDs from 588 Cochrane systematic reviews
- 1,736 NCT IDs from 2010+ with high CT.gov API coverage
- Multi-registry IDs: 192 ISRCTN, 116 ACTRN, 77 EudraCT, 38 ChiCTR, 18 DRKS
- New `cochrane_real_ncts.py` module with categorized NCT IDs
- New `extract_nct_from_cochrane.py` extraction script
- New `validate_nct_ids.py` API validation script
- **Note**: This is a reference sample, not an exhaustive gold standard for sensitivity validation

#### Validated API Recall Metrics
- 99% API recall rate validated (198/200 sample tested)
  - **Important**: This measures whether known NCT IDs are retrievable via CT.gov API
  - This is NOT the same as search sensitivity (finding all relevant studies)
- Category-specific API recall data for 12 medical specialties
- Phase distribution analysis (Phase 1-4)
- Status breakdown (Completed, Terminated, etc.)

#### Enhanced Improvement Plan
- `IMPROVEMENT_PLAN_V4_ENHANCED.md` with implementation guidance
- Integration of industry best practices
- Evidence-based implementation roadmap

### Changed
- Strategy optimizer now uses empirical Cochrane validation data
- Updated S1 base API recall from 98.7% to 99.0% based on validation
- Added condition adjustments for all 12 medical categories
- Confidence intervals updated with Wilson score from actual sample sizes

### Research Findings
- CT.gov API recall rate is 99% (known NCT IDs retrievable via API)
- All 12 medical categories achieved 100% API recall in validation sample
- Phase 3 trials most common (33%), followed by NA (32%), Phase 2 (23%)
- 87% of validated studies have COMPLETED status

## [2.0.0] - 2025-01-18

### Added

#### ML Strategy Optimizer
- New `strategy_optimizer.py` module with machine learning-based recommendations
- Condition classification system detecting 9 medical categories (oncology, cardiology, neurology, etc.)
- Four search goal optimization modes: maximum_recall, balanced, high_precision, quick_overview
- Bayesian ranking with Thompson sampling for strategy selection
- Wilson score confidence intervals for all metrics
- Known NCT bonus scoring for personalized recommendations
- Strategy Optimizer tab in HTML app with interactive UI

#### Multi-Registry Search
- New `registry_adapters/` package with unified search interface
- ANZCTR (Australian New Zealand Clinical Trials Registry) adapter
- ChiCTR (Chinese Clinical Trial Registry) adapter
- DRKS (German Clinical Trials Register) adapter
- CTRI (Clinical Trials Registry - India) adapter
- jRCT (Japan Registry of Clinical Trials) adapter
- Auto-detection of registry ID formats
- Parallel search execution with thread pooling
- Result deduplication across registries

#### Export Formats
- Covidence CSV export format support
- Rayyan CSV export format support
- Enhanced RIS export with full metadata
- Batch export functionality for multi-strategy results

#### PRISMA Flow Diagram Generator
- New `prisma_generator.py` module
- PRISMA 2020 compliant flow diagram generation
- SVG and PNG export options
- Customizable styling and colors
- Database-specific count tracking
- Exclusion reason categorization

#### MeSH/SNOMED Integration
- New `mesh_integration.py` module
- MeSH term expansion via NLM API
- SNOMED CT cross-references
- Automatic synonym suggestion
- Expanded query builder

#### Validation Dataset Expansion
- Expanded from 155 to 502 validated NCT IDs
- 17 condition categories covered
- Sources: Cochrane reviews, published SRs, clinical guidelines
- Edge cases for terminated, withdrawn, and multi-phase studies
- New `aact_validator.py` for database validation

#### Progressive Web App (PWA)
- Service worker for offline functionality
- Web app manifest for installation
- Automatic update detection
- Cache-first strategy for static assets
- Network-first strategy for API calls

#### Search History & Bookmarks
- IndexedDB-based history storage
- Bookmark searches with notes
- Filter and search history
- Export/import history as JSON
- Usage statistics dashboard
- Storage management tools

#### HTML App Enhancements
- New AACT Validation tab with batch NCT validation
- New Strategy Optimizer tab with ML recommendations
- New History tab with bookmarks
- PWA install banner
- ROC curve visualization
- Improved error handling with retry logic

### Changed
- Updated README with comprehensive feature documentation
- Improved project structure documentation
- Enhanced test coverage (target 90%+)
- Better error messages and user feedback

### Fixed
- Improved handling of API rate limiting
- Better CORS proxy fallback logic
- Fixed edge cases in recall calculation

## [1.0.0] - 2024-06-16

### Added
- Initial release of CT.gov search strategy validation toolkit
- 10 validated search strategies (S1-S10) with empirical recall data
- CTGovSearcher class for programmatic API access
- WHO ICTRP multi-registry search integration
- AACT PostgreSQL database integration for 100% recall
- Precision metrics module (NNS, F1, specificity calculations)
- Interactive decision flowchart (HTML)
- Comprehensive unit tests (106 tests)
- GitHub Actions CI workflow
- MkDocs documentation
- R package functions matching Python functionality
- Expanded therapeutic area validation (24 conditions)
- Type hints for all core modules

### Research Findings
- CT.gov API has ~12.7% inherent miss rate
- AACT database provides 100% recall
- Strategy S1 (Condition Only) achieves 98.7% recall
- Validated against 155 NCT IDs from 501 Cochrane reviews
