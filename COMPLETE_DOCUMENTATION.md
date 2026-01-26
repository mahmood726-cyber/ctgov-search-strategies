# CT.gov Search Strategy Validation Suite
## Complete Documentation - TruthCert Rules-Based v5.0

**Date:** 2026-01-25
**Author:** Mahmood Ahmad
**Version:** 5.0

---

## Executive Summary

This project validates CT.gov search strategies using an independent gold standard and rigorous statistical methods. Through systematic testing of multiple rules-based approaches, we achieved **97% recall** using intervention-based search strategies.

### Key Achievement
- **Target:** 95% recall
- **Achieved:** 97% recall (95% CI: 91.5%-99.0%)
- **Best Strategy:** S4-Interv (Search by intervention/drug name)

---

## Problem Statement

### Original Issue
The original CT.gov search validation claimed 98.7% recall, but this was based on **circular validation** - using search results as the gold standard to validate search results.

### Editorial Concerns Addressed
1. **Circular validation** - Fixed with independent PubMed-derived gold standard
2. **Missing confidence intervals** - Added Wilson score 95% CIs
3. **Simulated multi-registry search** - Implemented actual API integrations
4. **Small sample size** - Expanded to 681 NCT IDs across 10 conditions
5. **No paper integration** - Added PubMed, CrossRef, Unpaywall integration

---

## Methodology

### 1. Gold Standard Construction

We built an independent gold standard by extracting NCT IDs from PubMed publications:

```
Source: PubMed publications with DataBank NCT ID linkage
Method: Enhanced extraction using multiple strategies
Total NCT IDs: 681 (588 post-2015)
Conditions: 10 major disease areas
```

**Conditions covered:**
- Diabetes mellitus (51 trials)
- Asthma (78 trials)
- Stroke (73 trials)
- Breast cancer (60 trials)
- COPD (70 trials)
- Heart failure (70 trials)
- Rheumatoid arthritis (66 trials)
- Parkinson disease (51 trials)
- HIV (82 trials)
- Depression (80 trials)

### 2. Search Strategies Tested

| Code | Strategy | Description |
|------|----------|-------------|
| S0-Direct | Direct lookup | API call by NCT ID (baseline) |
| S1-FirstCond | First condition | Search by first registered condition |
| S2-AllCond | All conditions | OR search across all conditions |
| S3-CondKW | Condition+Keywords | Combine condition with keywords |
| S4-Interv | **Intervention** | **Search by drug/intervention name** |
| S5-TitleKW | Title keywords | Extract keywords from title |
| S6-Broader | MeSH hierarchy | Use broader MeSH terms |
| S7-General | General search | Full-text search all fields |
| S8-Combined | Combined OR | OR across multiple field types |
| S10-Synonyms | Synonyms | Use condition synonyms |
| S11-NCTTerm | NCT in term | Search NCT ID in term field |

### 3. Statistical Methods

- **Recall:** TP / (TP + FN)
- **Confidence Intervals:** Wilson score method (recommended for proportions)
- **Sample Size:** 100 trials per strategy (post-2015 publications)

---

## Results

### Final Validation Results (n=100, post-2015)

| Strategy | Recall | 95% CI | Found/Tested |
|----------|--------|--------|--------------|
| S0-Direct | 100.0% | 96.3%-100.0% | 100/100 |
| S11-NCTTerm | 100.0% | 96.3%-100.0% | 100/100 |
| **S4-Interv** | **97.0%** | **91.5%-99.0%** | **97/100** |
| S8-Combined | 93.0% | 86.3%-96.6% | 93/100 |
| S3-CondKW | 74.0% | 64.6%-81.6% | 74/100 |
| S2-AllCond | 58.0% | 48.2%-67.2% | 58/100 |
| S5-TitleKW | 58.0% | 48.2%-67.2% | 58/100 |
| S1-FirstCond | 44.0% | 34.7%-53.8% | 44/100 |
| S7-General | 29.0% | 21.0%-38.5% | 29/100 |
| S6-Broader | 13.0% | 7.8%-21.0% | 13/100 |
| S10-Synonyms | 13.0% | 7.8%-21.0% | 13/100 |
| COMBINED | 100.0% | 96.3%-100.0% | 100/100 |

### Key Finding

**Intervention-based search (S4-Interv) achieves 97% recall** - far exceeding condition-based approaches (44-58%).

This works because:
1. Drug/intervention names are more standardized than condition terminology
2. Interventions are unique identifiers (e.g., "metformin" vs "type 2 diabetes")
3. CT.gov has excellent intervention indexing

---

## Files Created

### Scripts

| File | Purpose |
|------|---------|
| `scripts/build_gold_standard.py` | Extract NCT IDs from PubMed |
| `scripts/enhanced_pubmed.py` | Enhanced PubMed extraction (681 NCT IDs) |
| `scripts/multi_registry_search.py` | WHO ICTRP, EU-CTR, ISRCTN search |
| `scripts/paper_integration.py` | PubMed/CrossRef/Unpaywall integration |
| `scripts/validation_statistics.py` | Wilson score CIs, precision metrics |
| `scripts/proper_validation.py` | Correct validation methodology |
| `scripts/comprehensive_validation.py` | Full validation suite |
| `scripts/strategy_optimizer.py` | **Multi-strategy optimization (v5.0)** |
| `scripts/aact_integration.py` | AACT PostgreSQL database integration |

### Data

| File | Contents |
|------|----------|
| `data/enhanced_gold_standard.json` | 681 NCT IDs from PubMed |
| `data/gold_standard.json` | Initial 339 NCT IDs |

### Output

| File | Contents |
|------|----------|
| `output/strategy_optimization_report.md` | Final optimization results |
| `output/strategy_optimization_results.json` | Machine-readable results |
| `output/proper_validation_report.md` | Validation report |
| `output/proper_validation_results.json` | Validation data |

---

## Implementation Details

### S4-Interv Strategy (97% Recall)

```python
def strategy_intervention_search(self, nct_id: str, details: Dict) -> bool:
    """Search by intervention/drug name"""
    interventions = details.get("interventions", [])
    conditions = details.get("conditions", [])

    for intervention in interventions[:3]:
        # Clean intervention name
        intervention = self.normalize_condition(intervention)
        if len(intervention) < 3:
            continue

        # Search by intervention
        results = self.search({"query.intr": intervention})
        if nct_id in results:
            return True

        # Search intervention + condition
        if conditions:
            condition = self.normalize_condition(conditions[0])
            results = self.search({
                "query.intr": intervention,
                "query.cond": condition
            })
            if nct_id in results:
                return True

    return False
```

### CT.gov API Parameters

```python
# Intervention search
params = {
    "query.intr": "metformin",  # Intervention name
    "fields": "NCTId",
    "pageSize": 1000
}

# Combined search
params = {
    "query.intr": "metformin",
    "query.cond": "diabetes",
    "fields": "NCTId",
    "pageSize": 1000
}
```

---

## Recommendations

### For Systematic Reviews

1. **Primary Strategy:** Use intervention-based search (S4-Interv)
   - Query: `query.intr=[drug name]`
   - Expected recall: 97%

2. **Backup Strategy:** Combine with condition search (S8-Combined)
   - Search intervention OR condition OR keywords
   - Expected recall: 93-100%

3. **Never Rely on CT.gov Alone**
   - Combine with PubMed, Embase, Cochrane CENTRAL
   - Use WHO ICTRP for international trials
   - Check EU-CTR for European trials

### Search Strategy Template

```
For systematic reviews of [INTERVENTION] for [CONDITION]:

1. CT.gov intervention search:
   query.intr=[INTERVENTION]

2. CT.gov condition search:
   query.cond=[CONDITION]

3. Combine results (union)

4. Supplement with:
   - PubMed: [INTERVENTION][pt:clinical trial]
   - WHO ICTRP: [INTERVENTION]
   - EU-CTR: [INTERVENTION]
```

---

## Technical Notes

### Wilson Score Confidence Interval

```python
def wilson_ci(successes: int, n: int) -> Tuple[float, float]:
    """Wilson score 95% CI - recommended for proportions"""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    z = 1.96  # 95% confidence
    denom = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denom
    margin = z * math.sqrt((p * (1-p) + z**2 / (4*n)) / n) / denom
    return (max(0, center - margin), min(1, center + margin))
```

### API Rate Limiting

- 0.3-0.5 second delay between requests
- Search result caching to minimize API calls
- Maximum 1000 results per query

---

## Changelog

### v5.0 (2026-01-25)
- Added strategy optimizer with 12 search strategies
- Achieved 97% recall with intervention-based search
- Comprehensive documentation

### v4.2 (2026-01-25)
- Enhanced PubMed extraction (681 NCT IDs)
- AACT database integration
- Multi-registry search

### v4.1 (2026-01-25)
- Fixed circular validation methodology
- Added Wilson score confidence intervals
- Created independent gold standard

### v1.0 (Original)
- Circular validation (98.7% claimed - invalid)
- No confidence intervals
- Simulated multi-registry search

---

## Conclusion

Through systematic testing of rules-based search strategies, we identified that **intervention-based search achieves 97% recall** on CT.gov - meeting and exceeding the 95% target. This is a major improvement over condition-based searches (44-58% recall).

The key insight is that drug/intervention names are more standardized and searchable than condition terminology, making them more effective for trial registry searches.

---

*Generated by CT.gov Trial Registry Integrity Suite - TruthCert Rules-Based v5.0*
