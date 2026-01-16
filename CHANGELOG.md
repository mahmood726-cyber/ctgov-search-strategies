# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-16

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
