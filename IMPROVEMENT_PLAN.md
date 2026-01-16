# CT.gov Search Strategy - Comprehensive Improvement Plan

## What Went Wrong Previously

### Technical Issues
1. **URL Encoding Problems**: R scripts double-encoded URLs causing HTTP 400 errors
2. **Regex Incompatibility**: Used `grep -P` (Perl regex) which doesn't work in Git Bash
3. **Worker Proxy Issues**: The Cloudflare worker added complexity; direct API calls are more reliable
4. **Incorrect Filter Syntax**: Used `filter.studyType` instead of proper AREA syntax

### Methodological Issues
1. **No Gold Standard Validation**: Didn't test against known included studies from Cochrane
2. **Limited Search Strategies**: Only tested basic condition field searches
3. **No Recall/Precision Metrics**: Didn't calculate how many known RCTs each strategy finds
4. **Ignored Cochrane Guidance**: Didn't follow systematic review search best practices

---

## Research Findings from Web Sources

### Key Sources Consulted
- [Cochrane Handbook Chapter 4](https://training.cochrane.org/handbook/current/chapter-04)
- [PMC Article on Optimal CT.gov Search Approaches](https://pmc.ncbi.nlm.nih.gov/articles/PMC4076126/)
- [Cochrane Webinar on Trial Registry Searching](https://training.cochrane.org/resource/searching-clinical-trials-registers-guide-for-systematic-reviewers)
- [ClinicalTrials.gov API Documentation](https://clinicaltrials.gov/data-api/api)

### Key Findings

1. **Basic Interface > Advanced Interface for Sensitivity**
   - Highly sensitive single-concept searches in basic interface retrieved 100% of relevant records
   - Advanced interface only maintained sensitivity in 84% of searches

2. **Single-Concept Strategy Works Best**
   - Focus on ONE concept (condition OR intervention) with multiple synonyms
   - Avoid combining restrictive filters when sensitivity matters

3. **No Single Strategy Is 100% Sensitive**
   - Must search BOTH ClinicalTrials.gov AND WHO ICTRP
   - CENTRAL alone is insufficient for identifying trials

4. **Avoid Over-Filtering**
   - Cochrane recommends: "avoiding using filters (e.g., by participant age or study type)"
   - Filters reduce recall and may miss relevant studies

---

## CT.gov API v2 - Complete Reference

### Query Parameters
| Parameter | Description | Example |
|-----------|-------------|---------|
| `query.cond` | Condition/disease field | `query.cond=diabetes` |
| `query.term` | Full-text + AREA syntax | `query.term=insulin AND randomized` |
| `query.intr` | Intervention field | `query.intr=metformin` |
| `query.titles` | Title/acronym only | `query.titles=ACCORD` |
| `query.outc` | Outcome measures | `query.outc=mortality` |
| `query.spons` | Sponsor/collaborator | `query.spons=NIH` |
| `query.lead` | Lead sponsor | `query.lead=Pfizer` |
| `query.id` | NCT ID (OR semantics) | `query.id=NCT00000001` |

### Filter Parameters
| Parameter | Description | Example |
|-----------|-------------|---------|
| `filter.overallStatus` | Recruitment status | `COMPLETED,RECRUITING` |
| `filter.geo` | Geographic (distance) | `distance(40.7,-74.0,100mi)` |
| `filter.ids` | NCT IDs (AND semantics) | Forces intersection |
| `filter.advanced` | AREA expressions | Complex field queries |

### AREA Syntax (in query.term or filter.advanced)
```
AREA[FieldName]Value
AREA[FieldName](Value1 OR Value2)
AREA[FieldName]RANGE[start,end]
AREA[FieldName]MISSING
```

### Available AREA Fields
- `StudyType` - INTERVENTIONAL, OBSERVATIONAL, etc.
- `Phase` - EARLY_PHASE1, PHASE1, PHASE2, PHASE3, PHASE4, NA
- `ResultsFirstPostDate` - Date results were posted
- `LastUpdatePostDate` - Last update date
- `LeadSponsorName` - Lead sponsor
- `LocationCountry` - Country
- `Condition` - Condition/disease
- `InterventionName` - Intervention
- `DesignAllocation` - RANDOMIZED, NON_RANDOMIZED
- `DesignPrimaryPurpose` - TREATMENT, PREVENTION, etc.

### Boolean Operators
- `AND` - Both terms required
- `OR` - Either term matches
- `NOT` - Exclude term
- Parentheses for grouping: `(diabetes OR diabetic) AND randomized`

---

## Improved Search Strategies to Test

### Strategy 1: Maximum Recall (Cochrane Recommended)
```
query.cond=<condition>
```
- No filters, captures everything
- Expected: Highest count, lowest precision

### Strategy 2: Condition + Intervention Field
```
query.cond=<condition>&query.intr=<intervention>
```
- More specific without losing RCTs

### Strategy 3: AREA-Based RCT Filter
```
query.cond=<condition>&query.term=AREA[StudyType]INTERVENTIONAL
```
- Filters to interventional studies only

### Strategy 4: AREA-Based Randomized Filter
```
query.cond=<condition>&query.term=AREA[DesignAllocation]RANDOMIZED
```
- True RCTs only (excludes single-arm)

### Strategy 5: Phase 3/4 Studies
```
query.cond=<condition>&query.term=AREA[Phase](PHASE3 OR PHASE4)
```
- Later phase trials more likely published

### Strategy 6: Studies with Posted Results
```
query.cond=<condition>&query.term=AREA[ResultsFirstPostDate]RANGE[MIN,MAX]
```
- Only studies that have posted results

### Strategy 7: Completed + Interventional
```
query.cond=<condition>&query.term=AREA[StudyType]INTERVENTIONAL&filter.overallStatus=COMPLETED
```
- Completed interventional studies

### Strategy 8: Boolean Full-Text Search
```
query.term=<condition> AND randomized AND (controlled OR placebo)
```
- Full-text with RCT keywords

### Strategy 9: Multi-Concept (Sensitive)
```
query.term=(<condition> OR <synonym1> OR <synonym2>) AND (trial OR study)
```
- Multiple synonyms for sensitivity

### Strategy 10: Combined Advanced Query
```
query.cond=<condition>&query.term=AREA[StudyType]INTERVENTIONAL AND AREA[Phase](PHASE3 OR PHASE4)&filter.overallStatus=COMPLETED
```
- Highly focused search

---

## Validation Methodology

### Gold Standard: Cochrane Included Studies
1. Extract NCT IDs from Cochrane systematic reviews (where available)
2. For each search strategy, check if strategy finds the known NCT IDs
3. Calculate RECALL = (found by strategy / total known) × 100%
4. Calculate PRECISION = (relevant / total retrieved) × 100%

### Test Matrix
- **6 medical conditions** with high Cochrane review coverage
- **10 search strategies** as defined above
- **Metrics**: Total count, Recall (if NCT IDs known), Response time

### NCT ID Extraction
- Parse Cochrane RDS files for registry references
- Match study names to CT.gov using title search
- Build ground truth dataset of condition → NCT IDs

---

## Implementation Plan

### Phase 1: Build Robust API Client
- [ ] Create clean R/Python functions with proper error handling
- [ ] Use direct API calls (no worker proxy)
- [ ] Implement retry logic and rate limiting
- [ ] Store all responses for analysis

### Phase 2: Extract Ground Truth Data
- [ ] Parse Cochrane RDS files for NCT IDs
- [ ] Use `query.id` to verify NCT IDs exist
- [ ] Map conditions to review sets

### Phase 3: Comprehensive Strategy Testing
- [ ] Test all 10 strategies across all conditions
- [ ] Calculate recall against known included studies
- [ ] Measure precision where feasible
- [ ] Time all queries

### Phase 4: Analysis & Recommendations
- [ ] Identify best strategy for each use case
- [ ] Document trade-offs (sensitivity vs specificity)
- [ ] Create decision flowchart for searchers

---

## Expected Deliverables

1. **Validated Search Strategy Guide** - Evidence-based recommendations
2. **Interactive Testing Tool** - HTML interface for testing queries
3. **R Package Functions** - Reusable search functions
4. **Recall/Precision Data** - Empirical performance metrics
5. **Decision Flowchart** - Visual guide for strategy selection
