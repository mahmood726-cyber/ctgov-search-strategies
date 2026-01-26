# CTGov Search Strategies - Comprehensive Improvement Plan v3.0

## Executive Summary

Based on analysis of the **Pairwise70 R package** containing 501 Cochrane systematic reviews with ~50,000 RCTs, we have extracted a substantial real-world validation dataset:

- **1,904 unique NCT IDs** extracted from 588 Cochrane reviews
- **1,736 NCT IDs** from 2010+ (high-confidence CT.gov coverage)
- **192 ISRCTN IDs**, **116 ACTRN IDs**, **77 EudraCT IDs**, **38 ChiCTR IDs**, **18 DRKS IDs**

This provides the foundation for **evidence-based improvements** to the CT.gov search strategy tool.

---

## Phase 1: Validation Dataset Enhancement (Critical)

### 1.1 Replace Synthetic with Real NCT IDs
**Current State:** 502 validated NCT IDs (many synthetic)
**Target State:** 1,700+ real NCT IDs from Cochrane reviews

**Files to Update:**
- `tests/validation_data/expanded_nct_dataset.py`
- `tests/validation_data/cochrane_nct_ids.py` (NEW - already created)

**Implementation:**
```python
# Use extracted Cochrane NCT IDs grouped by medical category
VALIDATION_NCT_IDS = {
    'oncology': [...],      # ~150 NCT IDs
    'cardiology': [...],    # ~120 NCT IDs
    'neurology': [...],     # ~100 NCT IDs
    'psychiatry': [...],    # ~90 NCT IDs
    'endocrinology': [...], # ~80 NCT IDs
    'infectious': [...],    # ~75 NCT IDs
    # ... more categories
}
```

### 1.2 Add Multi-Registry Validation
**Files:** `tests/validation_data/multi_registry_ids.py` (NEW)

Include other registry IDs for cross-registry search validation:
- 192 ISRCTN IDs (UK)
- 116 ACTRN IDs (Australia/NZ)
- 77 EudraCT IDs (Europe)
- 38 ChiCTR IDs (China)
- 18 DRKS IDs (Germany)

### 1.3 Source Attribution
Every NCT ID should have:
- Cochrane review DOI source
- Study author/year
- Medical category
- Publication year

---

## Phase 2: Strategy Performance Re-Validation

### 2.1 Re-Run All 10 Strategies with Real Data
**Current Performance (Synthetic Data):**

| Strategy | Recall | Precision | NNS |
|----------|--------|-----------|-----|
| S1 | 98.7% | 15.2% | 6.6 |
| S2 | 98.7% | 18.5% | 5.4 |
| S3 | 98.7% | 22.3% | 4.5 |
| S8 | 42.9% | 52.3% | 1.9 |

**Task:** Re-validate with 1,700+ real NCT IDs to get accurate empirical performance.

### 2.2 Condition-Specific Performance Analysis
Test each strategy against NCT IDs grouped by:
- Medical specialty (oncology, cardiology, etc.)
- Study phase (Phase 1, 2, 3, 4)
- Study status (Recruiting, Completed, etc.)
- Publication year (2010-2015, 2016-2020, 2021+)

**Expected Output:**
```
S1 Performance by Condition:
  Oncology: 97.2% recall (145/149)
  Cardiology: 98.5% recall (118/120)
  Neurology: 96.8% recall (91/94)
  ...
```

### 2.3 API Miss Rate Analysis
From extracted data:
- **Total NCT IDs:** 1,736 (2010+)
- **Expected findable via API:** ~87% (~1,510)
- **Expected API misses:** ~13% (~226)

Validate these numbers against CT.gov API.

---

## Phase 3: ML Strategy Optimizer Improvements

### 3.1 Train on Real Performance Data
**Current:** Uses synthetic performance estimates
**Target:** Train on empirical recall/precision from Cochrane NCT validation

**Features for ML Model:**
1. Condition category (from Cochrane review topics)
2. Study year distribution
3. Study phase distribution
4. Expected result count
5. User's search goal

### 3.2 Condition Classification Enhancement
**Current Keywords:** 9 categories
**Expanded Keywords:** Based on Cochrane review topics

```python
# Extract condition keywords from Cochrane review titles
CONDITION_KEYWORDS = {
    'oncology': ['cancer', 'carcinoma', 'tumor', 'neoplasm', 'leukemia',
                 'lymphoma', 'melanoma', 'chemotherapy', 'radiotherapy'],
    'cardiology': ['heart', 'cardiac', 'cardiovascular', 'hypertension',
                   'stroke', 'coronary', 'atrial fibrillation', 'heart failure'],
    # ... expanded based on Cochrane data
}
```

### 3.3 Bayesian Prior Updates
Update Thompson sampling priors based on:
- Actual strategy performance across 1,700+ NCT IDs
- Condition-specific success rates
- Year-specific API recall rates

---

## Phase 4: Multi-Registry Search Enhancements

### 4.1 Cross-Registry ID Matching
**Use Case:** User provides ISRCTN/ACTRN ID, tool finds NCT ID

**Implementation:**
```python
def cross_reference_id(registry_id):
    """
    Given any registry ID, find corresponding NCT ID.
    Uses WHO ICTRP cross-reference data.
    """
    # Query WHO ICTRP
    # Map ISRCTN -> NCT, ACTRN -> NCT, etc.
```

### 4.2 Registry-Specific Recall Tracking
Track API recall for each registry:
- ClinicalTrials.gov: ~87%
- ANZCTR: TBD
- ChiCTR: TBD
- DRKS: TBD
- CTRI: TBD
- jRCT: TBD

### 4.3 Unified Search Interface Improvements
- Add progress indicators for multi-registry search
- Show registry-specific result counts
- Highlight cross-registered studies

---

## Phase 5: Export & Integration Improvements

### 5.1 Cochrane Review Export Format
**New Feature:** Export in Cochrane RevMan format

```python
def export_to_revman(studies, filename):
    """Export to Cochrane RevMan-compatible format."""
    # Include: Study ID, NCT ID, Authors, Year, Status
```

### 5.2 PROSPERO Registration Helper
**New Feature:** Auto-populate PROSPERO registration fields

```python
def generate_prospero_search_strategy(condition, strategies_used):
    """Generate PROSPERO-formatted search strategy documentation."""
```

### 5.3 Search Strategy Reproducibility Report
**New Feature:** Generate reproducible search documentation

Output includes:
- Exact API queries used
- Date of search
- Number of results per strategy
- Deduplication details
- Registry coverage

---

## Phase 6: Performance Metrics Enhancement

### 6.1 Real Recall/Precision Calculation
**Current:** Estimated based on limited validation
**Target:** Calculate from 1,700+ real NCT IDs

```python
def calculate_strategy_performance(strategy, nct_ids):
    """
    Run strategy against known NCT IDs.
    Return actual recall, precision, NNS.
    """
    found = set()
    for nct in nct_ids:
        results = search_ctgov(strategy_query)
        if nct in results:
            found.add(nct)

    recall = len(found) / len(nct_ids)
    precision = len(found) / total_results
    nns = 1 / precision if precision > 0 else float('inf')

    return {'recall': recall, 'precision': precision, 'nns': nns}
```

### 6.2 Confidence Intervals with Real Data
Update Wilson CI calculations with actual sample sizes:
- n = 1,736 (2010+ NCT IDs)
- Per-category n varies (50-150 each)

### 6.3 ROC Curve with Real Data
Generate ROC curves using:
- X-axis: 1 - Specificity (false positive rate)
- Y-axis: Sensitivity (recall)
- Each point: One search strategy

---

## Phase 7: Documentation & Publication

### 7.1 Methods Paper Update
**Target Journal:** Research Synthesis Methods

Key additions:
- Validation dataset from 501 Cochrane reviews
- 1,736 real NCT IDs from 2010+
- Empirical strategy performance
- API recall rate analysis

### 7.2 Validation Dataset Publication
**Publish as:**
1. R package supplement to Pairwise70
2. JSON/CSV on Zenodo
3. Python package on PyPI

### 7.3 Reproducibility Package
Include:
- All NCT IDs with sources
- Strategy validation code
- Performance calculation scripts
- Raw results

---

## Implementation Priority

| Phase | Task | Impact | Effort |
|-------|------|--------|--------|
| 1.1 | Replace validation NCT IDs | Critical | Medium |
| 1.2 | Add multi-registry IDs | High | Low |
| 2.1 | Re-validate strategies | Critical | High |
| 2.2 | Condition-specific analysis | High | Medium |
| 3.1 | Train ML on real data | High | High |
| 4.1 | Cross-registry matching | Medium | Medium |
| 5.1 | Cochrane export format | Medium | Low |
| 6.1 | Real performance metrics | Critical | Medium |
| 7.1 | Methods paper | High | High |

---

## Expected Outcomes

### Validation Dataset
- **Current:** 502 NCT IDs (many synthetic)
- **After:** 1,736+ real NCT IDs from Cochrane reviews

### Strategy Performance
- **Current:** Estimated recall/precision
- **After:** Empirically validated performance

### ML Optimizer
- **Current:** Generic recommendations
- **After:** Evidence-based, condition-specific recommendations

### Publication
- **Target:** Research Synthesis Methods journal
- **Dataset:** Largest validated CT.gov search dataset

---

## Files to Create/Modify

### New Files
1. `tests/validation_data/cochrane_nct_ids.py` ✅ Created
2. `tests/validation_data/cochrane_nct_extraction.json` ✅ Created
3. `tests/validation_data/multi_registry_ids.py`
4. `scripts/validate_strategy_performance.py`
5. `scripts/generate_condition_report.py`

### Modified Files
1. `tests/validation_data/expanded_nct_dataset.py`
2. `strategy_optimizer.py`
3. `CTGov-Search-Complete.html`
4. `README.md`
5. `CHANGELOG.md`

---

## Success Metrics

1. **Validation Dataset Size:** 1,700+ real NCT IDs (vs. current 502)
2. **Strategy Recall Accuracy:** Within 2% of real performance
3. **ML Optimizer Accuracy:** 85%+ top-3 recommendation accuracy
4. **Publication:** Accepted to Research Synthesis Methods

---

## Timeline (Suggested)

- **Week 1:** Phase 1 (Validation dataset)
- **Week 2:** Phase 2 (Strategy re-validation)
- **Week 3:** Phase 3 (ML optimizer updates)
- **Week 4:** Phases 4-6 (Enhancements)
- **Week 5-6:** Phase 7 (Documentation & publication)

---

*Plan created: 2026-01-18*
*Based on: Pairwise70 extraction of 1,904 NCT IDs*
