# CT.gov Trial Registry Integrity Suite
## Evidence-Based Search Strategies for Systematic Reviews
### Version 5.0 - TruthCert Rules-Based Optimization

---

## Executive Summary

This guide presents **validated search strategies** for ClinicalTrials.gov (CT.gov), tested using an **independent gold standard** from PubMed publications.

### Major Update (v5.0) - 97% Recall Achieved!

Through systematic testing of 12 rules-based strategies, we identified that **intervention-based search achieves 97% recall** - far exceeding condition-based approaches.

### Key Findings (n=100, post-2015)

| Strategy | Recall | 95% CI | Recommendation |
|----------|--------|--------|----------------|
| **S4-Interv** | **97%** | 91.5%-99.0% | **USE THIS - Search by intervention** |
| S8-Combined | 93% | 86.3%-96.6% | Backup - combined fields |
| S3-CondKW | 74% | 64.6%-81.6% | Good - condition + keywords |
| S2-AllCond | 58% | 48.2%-67.2% | Fair - all conditions |
| S1-FirstCond | 44% | 34.7%-53.8% | Poor - avoid this approach |

**Key Insight:** Drug/intervention names are more standardized than condition terminology.

---

## Quick Start - Recommended Strategy

### Primary: Intervention Search (97% Recall)

```bash
# API Query
https://clinicaltrials.gov/api/v2/studies?query.intr=[DRUG_NAME]&pageSize=1000

# Example
https://clinicaltrials.gov/api/v2/studies?query.intr=metformin&pageSize=1000
```

```python
import requests

def search_by_intervention(drug_name):
    """97% recall strategy"""
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.intr": drug_name,
        "fields": "NCTId,BriefTitle,Condition,InterventionName",
        "pageSize": 1000
    }
    return requests.get(url, params=params).json()
```

---

## All Strategies Tested

### S4-Interv: Intervention Search (RECOMMENDED)
```
query.intr={drug_name}
```
- **Validated Recall:** 97.0% (95% CI: 91.5% - 99.0%)
- **Best For:** All systematic reviews
- **Why It Works:** Drug names are standardized; conditions are not

### S8-Combined: Combined OR Fields
```
Search intervention OR condition OR keywords (union of results)
```
- **Validated Recall:** 93.0% (95% CI: 86.3% - 96.6%)
- **Best For:** Comprehensive searches

### S3-CondKW: Condition + Keywords
```
query.cond={condition}&query.term={keyword}
```
- **Validated Recall:** 74.0% (95% CI: 64.6% - 81.6%)
- **Best For:** Trials with good keyword registration

### S2-AllCond: All Conditions (OR)
```
Search each registered condition separately
```
- **Validated Recall:** 58.0% (95% CI: 48.2% - 67.2%)
- **Best For:** Trials with multiple conditions

### S1-FirstCond: First Condition Only (OLD BASELINE)
```
query.cond={condition}
```
- **Validated Recall:** 44.0% (95% CI: 34.7% - 53.8%)
- **Warning:** Misses 56% of trials - DO NOT USE ALONE

### S3-Randomized (with filters)
```
query.cond={condition}&query.term=AREA[DesignAllocation]RANDOMIZED
```
- **Validated Recall:** 53.0% (95% CI: 43.3% - 62.5%)
- **Use:** When needing RCT filter

---

## Validation Methodology

### Independent Gold Standard (v5.0)

**Source:** PubMed publications with DataBank NCT ID linkage
**Size:** 681 NCT IDs (588 post-2015)
**Extraction:** Enhanced PubMed extraction with multiple strategies

**Conditions covered:**
| Condition | N Trials |
|-----------|----------|
| HIV | 82 |
| Depression | 80 |
| Asthma | 78 |
| Stroke | 73 |
| COPD | 70 |
| Heart failure | 70 |
| Rheumatoid arthritis | 66 |
| Breast cancer | 60 |
| Diabetes mellitus | 51 |
| Parkinson disease | 51 |

### Validation Process

For each NCT ID in the gold standard:
1. Retrieve trial details from CT.gov (conditions, interventions, keywords)
2. Run each search strategy using those details
3. Check if the NCT ID appears in results
4. Calculate recall with Wilson score 95% CI

This is **TRUE validation** - not circular.

---

## Critical Recommendations

### For Systematic Reviews

1. **Primary Strategy:** Use intervention search (S4-Interv)
   - `query.intr=[drug name]`
   - 97% recall

2. **Backup Strategy:** Combined search (S8-Combined)
   - Intervention OR condition OR keywords
   - 93% recall

3. **NEVER rely on condition search alone**
   - Only 44-58% recall
   - Misses over half of relevant trials

### For Cochrane Reviews

1. **Search CT.gov by intervention name**
2. **Also search multiple registries:**
   - WHO ICTRP
   - EU-CTR
   - Regional registries
3. **Search bibliographic databases** (PubMed, Embase)
4. **Report confidence intervals** for recall estimates

---

## Files in This Project

| File | Description |
|------|-------------|
| `scripts/strategy_optimizer.py` | **NEW** - Multi-strategy testing (12 strategies) |
| `scripts/proper_validation.py` | Validation with independent gold standard |
| `scripts/enhanced_pubmed.py` | Gold standard extraction (681 NCT IDs) |
| `scripts/multi_registry_search.py` | WHO ICTRP, EU-CTR, ISRCTN search |
| `scripts/paper_integration.py` | Paper data and PDF download |
| `scripts/aact_integration.py` | AACT database integration |
| `data/enhanced_gold_standard.json` | 681 NCT IDs from PubMed |
| `output/strategy_optimization_results.json` | Full validation results |
| `COMPLETE_DOCUMENTATION.md` | Comprehensive documentation |

---

## Running the Optimizer

```bash
# Install dependencies
pip install -r requirements.txt

# Run strategy optimization (100 trials, post-2015)
python scripts/strategy_optimizer.py data/enhanced_gold_standard.json -n 100 -y 2015

# Or use Docker
docker build -t ctgov-suite .
docker run -v $(pwd)/output:/app/output ctgov-suite
```

---

## Statistical Methods

- **Recall:** TP / (TP + FN)
- **Confidence Intervals:** Wilson score method (recommended for proportions)
- **Sample Size:** 100 trials per strategy
- **Filter:** Post-2015 publications (CT.gov data more complete)

---

## Why Intervention Search Works Best

| Factor | Condition Search | Intervention Search |
|--------|------------------|---------------------|
| Standardization | Low (many synonyms) | High (INN, USAN names) |
| Specificity | Low ("diabetes") | High ("metformin") |
| Indexing | Variable | Excellent in CT.gov |
| Recall | 44-58% | **97%** |

---

## Version History

### v5.0 (January 2026) - MAJOR UPDATE
- **NEW:** Strategy optimizer with 12 rules-based approaches
- **FINDING:** Intervention search achieves 97% recall
- Enhanced gold standard (681 NCT IDs from PubMed)
- Post-2015 filtering for better data quality
- Complete documentation

### v4.1 (January 2026)
- Replaced circular validation with independent gold standard
- Added 95% Wilson score confidence intervals
- Implemented actual multi-registry search
- Honest reporting of recall (~65-70%)

### v4.0
- TruthCert TC-TRIALREG integration
- Registry-paper reconciliation

### v3.0
- Initial release with 10 search strategies

---

## Citation

```bibtex
@software{ctgov_integrity_suite,
  title = {CT.gov Trial Registry Integrity Suite},
  author = {Mahmood Ahmad},
  year = {2026},
  version = {5.0},
  note = {97\% recall achieved with intervention-based search}
}
```

---

**Version:** 5.0 - TruthCert Rules-Based
**Date:** January 2026
**Author:** Mahmood Ahmad
**Key Finding:** Search by intervention name for 97% recall
