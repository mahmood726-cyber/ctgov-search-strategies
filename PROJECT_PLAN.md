<!-- sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files. -->

# CT.gov Search Strategy Development Project

## Project Goal
Develop and validate optimal search strategies for ClinicalTrials.gov (CT.gov) to find RCTs relevant to systematic reviews, using existing Cochrane pairwise meta-analysis data as ground truth.

## Data Sources
1. **Cochrane Pairwise Data**: `C:\Users\user\OneDrive - NHS\Documents\Pairwise70`
   - 501 cleaned RDS files containing meta-analysis data
   - Each contains: Study names, years, outcomes, interventions
   - Cochrane DOIs for review context

2. **CT.gov API**: Accessed via Cloudflare Worker proxy
   - Worker URL: `https://restless-term-5510.mahmood726.workers.dev/`
   - CT.gov API: `https://clinicaltrials.gov/api/v2/studies`

## Project Structure
```
ctgov-search-strategies/
├── PROJECT_PLAN.md          # This file
├── data/
│   ├── extracted_studies.csv    # Studies from Cochrane reviews
│   ├── search_results/          # CT.gov search results
│   └── validation/              # Validation results
├── scripts/
│   ├── extract_cochrane_data.R  # Extract studies from RDS files
│   ├── ctgov_search.js          # CT.gov API search functions
│   └── validate_searches.js     # Validation scripts
├── analysis/
│   └── search_strategy_report.md
└── output/
    └── optimal_strategies.json
```

## CT.gov API Search Parameters
Key searchable fields:
- `query.term` - Full text search
- `query.cond` - Condition/disease
- `query.intr` - Intervention/treatment
- `query.titles` - Title search
- `query.outc` - Outcome measures
- `filter.overallStatus` - Study status
- `filter.studyType` - INTERVENTIONAL for RCTs

## Search Strategy Development

### Phase 1: Data Extraction
- Extract all unique study identifiers from Cochrane data
- Extract conditions/topics from review DOIs
- Map Cochrane review titles to medical conditions

### Phase 2: Search Testing
- Test condition-based searches
- Test intervention-based searches
- Test combined searches
- Test MeSH term searches

### Phase 3: Validation
- For each Cochrane review, search CT.gov
- Check if known included RCTs are found
- Calculate sensitivity and precision
- Identify optimal search strategies

### Phase 4: Strategy Optimization
- Compare single-term vs multi-term searches
- Test Boolean operators
- Evaluate field-specific vs full-text searches
- Document best practices

## Success Metrics
- **Sensitivity**: % of known RCTs found by search
- **Precision**: % of search results that are relevant
- **Efficiency**: Number of results to screen

## Worker Proxy Usage
```javascript
const workerUrl = 'https://restless-term-5510.mahmood726.workers.dev/';
const ctgovApi = 'https://clinicaltrials.gov/api/v2/studies';
const searchUrl = `${workerUrl}?url=${encodeURIComponent(ctgovApi + '?query.cond=diabetes')}`;
```

## Timeline
- Setup and extraction: Phase 1
- Search testing: Phase 2
- Validation: Phase 3
- Documentation: Phase 4
