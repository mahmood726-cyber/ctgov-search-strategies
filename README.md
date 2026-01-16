# CT.gov Search Strategy Development Project

A research project to develop and validate optimal search strategies for ClinicalTrials.gov (CT.gov) to find RCTs relevant to systematic reviews.

## Quick Start

1. **Open the Search Tester**: Double-click `CTGov-Search-Tester.html`
2. Enter a condition (e.g., "hypertension") and click "Search CT.gov"
3. Compare strategies using the "Compare All Strategies" button

## Project Structure

```
ctgov-search-strategies/
├── CTGov-Search-Tester.html    # Interactive search tester
├── PROJECT_PLAN.md             # Detailed project plan
├── README.md                   # This file
├── data/
│   ├── extracted_studies.csv   # 10,581 studies from 501 Cochrane reviews
│   ├── reviews_summary.csv     # Summary of 501 reviews
│   ├── review_conditions.csv   # Detected conditions per review
│   ├── test_reviews.csv        # 30 reviews for validation testing
│   └── unique_studies.csv      # 10,074 unique study-year combos
├── scripts/
│   ├── extract_cochrane_data.R # R script to extract Cochrane data
│   ├── extract_conditions.R    # R script to detect conditions
│   └── ctgov_search.js         # JS module for CT.gov API
├── analysis/                   # Analysis outputs
└── output/                     # Final results
```

## Data Sources

### Cochrane Pairwise Data
- **Location**: `C:\Users\user\OneDrive - NHS\Documents\Pairwise70`
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

### Worker Proxy
- **URL**: `https://restless-term-5510.mahmood726.workers.dev/`
- **Usage**: `?url=<encoded CT.gov API URL>`

### CT.gov API v2
- **Base**: `https://clinicaltrials.gov/api/v2/studies`
- **Key Parameters**:
  - `query.cond` - Condition/disease
  - `query.intr` - Intervention/treatment
  - `query.term` - Full text search
  - `query.titles` - Title search
  - `filter.studyType=INTERVENTIONAL` - RCTs only
  - `filter.overallStatus=COMPLETED` - Completed studies

### Example API Call
```javascript
const workerUrl = 'https://restless-term-5510.mahmood726.workers.dev/';
const apiUrl = 'https://clinicaltrials.gov/api/v2/studies';
const params = '?query.cond=hypertension&filter.studyType=INTERVENTIONAL&pageSize=100';
const fullUrl = `${workerUrl}?url=${encodeURIComponent(apiUrl + params)}`;
```

## Search Strategies

### 1. Condition Only
```
query.cond=<condition>&filter.studyType=INTERVENTIONAL
```
- **Pros**: Broadest coverage
- **Cons**: Many irrelevant results

### 2. Condition + Completed
```
query.cond=<condition>&filter.studyType=INTERVENTIONAL&filter.overallStatus=COMPLETED
```
- **Pros**: Only finished studies with results
- **Cons**: Misses ongoing trials

### 3. Condition + Intervention
```
query.cond=<condition>&query.intr=<intervention>&filter.studyType=INTERVENTIONAL
```
- **Pros**: More precise
- **Cons**: May miss variant spellings

### 4. Full Text Search
```
query.term=<terms>&filter.studyType=INTERVENTIONAL
```
- **Pros**: Searches all fields
- **Cons**: May include irrelevant matches

### 5. Broad OR Search
```
query.term=<term1> OR <term2>&filter.studyType=INTERVENTIONAL
```
- **Pros**: High sensitivity
- **Cons**: Low precision

### 6. Narrow AND Search
```
query.term=<term1> AND <term2>&filter.studyType=INTERVENTIONAL
```
- **Pros**: High precision
- **Cons**: May miss relevant studies

## Validation Approach

1. Select Cochrane reviews with clear conditions
2. Extract known included RCTs from review
3. Search CT.gov using various strategies
4. Calculate:
   - **Sensitivity**: % of known RCTs found
   - **NNS (Number Needed to Screen)**: Total results / relevant results

## Running the Scripts

### R Scripts (require R 4.5+)
```bash
# Extract Cochrane data
Rscript scripts/extract_cochrane_data.R

# Extract conditions
Rscript scripts/extract_conditions.R
```

### HTML Tester
Open `CTGov-Search-Tester.html` in any modern browser.

## Configuration
- Shared defaults live in `ctgov_config.py` (API base URL, timeouts, rate limits).
- Synonym expansion reads `data/condition_synonyms.json`. You can edit this file
  or pass `--synonyms` to `ctgov_workflow.py`.

## Testing
```bash
python -m unittest discover -s tests
```

## Key Findings (Preliminary)

1. **Condition-only searches** return thousands of results - too broad
2. **Condition + Completed** is good for finished trials
3. **Condition + Intervention** provides best balance
4. **Full text AND searches** are most precise but may miss variants
5. **MeSH terms** improve consistency (when available)

## Next Steps

1. Run systematic validation across 30 test reviews
2. Calculate sensitivity/precision for each strategy
3. Develop hybrid search approach
4. Create optimal search templates by condition type

## Author
Generated for Pairwise70 project - MAFI (Meta-Analysis Fragility Index)

## License
For research purposes only.
