# CT.gov Search Strategy Comprehensive Report

**Version:** 2.0
**Date:** January 2026
**Methodology:** Evidence-based validation using CT.gov API v2
**Guidance Sources:** Cochrane Handbook, PMC Research, NLM Documentation

---

## Executive Summary

This report presents evidence-based search strategies for ClinicalTrials.gov, validated against 6 medical conditions using 10 distinct search approaches. Key findings align with Cochrane guidance that **simple condition searches without filters provide maximum sensitivity**.

### Key Metrics

| Strategy | Avg Results | % of Baseline | Recommended For |
|----------|-------------|---------------|-----------------|
| S1: Condition Only | 13,403 | 100% | Systematic Reviews |
| S2: Interventional | 10,291 | 77% | Intervention Studies |
| S3: Randomized | 7,238 | 54% | True RCTs |
| S6: Completed | 7,340 | 55% | Published Trials |
| S7: Interv+Completed | 5,768 | 43% | Balanced Approach |
| S8: RCT+Phase3/4+Completed | 1,107 | 8% | High Quality Subset |

---

## Methodology

### Data Sources Consulted

1. **[Cochrane Handbook Chapter 4](https://training.cochrane.org/handbook/current/chapter-04)** - Gold standard for systematic review searching
2. **[PMC: Optimal CT.gov Search Approaches](https://pmc.ncbi.nlm.nih.gov/articles/PMC4076126/)** - Empirical sensitivity analysis
3. **[Cochrane Webinar on Registry Searching](https://training.cochrane.org/resource/searching-clinical-trials-registers-guide-for-systematic-reviewers)** - Step-by-step guidance
4. **[ClinicalTrials.gov API Documentation](https://clinicaltrials.gov/data-api/api)** - Official API v2 reference

### Key Research Findings

From [PMC4076126](https://pmc.ncbi.nlm.nih.gov/articles/PMC4076126/):
> "Highly sensitive single-concept searches in the basic interface performed best... retrieving 100% of relevant records for all 6 reviews tested."

From Cochrane Guidance:
> "Avoiding using filters (e.g., by participant age or study type)" is recommended for maximum recall.

---

## Search Strategies Tested

### Strategy Definitions

| ID | Name | API Query Pattern |
|----|------|-------------------|
| S1 | Condition Only | `query.cond=<condition>` |
| S2 | Interventional | `query.cond=...&query.term=AREA[StudyType]INTERVENTIONAL` |
| S3 | Randomized Allocation | `query.cond=...&query.term=AREA[DesignAllocation]RANDOMIZED` |
| S4 | Phase 3/4 | `query.cond=...&query.term=AREA[Phase](PHASE3 OR PHASE4)` |
| S5 | Has Posted Results | `query.cond=...&query.term=AREA[ResultsFirstPostDate]RANGE[MIN,MAX]` |
| S6 | Completed Status | `query.cond=...&filter.overallStatus=COMPLETED` |
| S7 | Interventional + Completed | S2 + S6 combined |
| S8 | RCT + Phase3/4 + Completed | S3 + S4 + S6 combined |
| S9 | Full-Text RCT Keywords | `query.term=<condition> AND randomized AND controlled` |
| S10 | Treatment RCTs | `AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT` |

---

## Results by Condition

### Diabetes (N = 23,155 baseline)

| Strategy | Count | Retention |
|----------|-------|-----------|
| S1 Condition Only | 23,155 | 100.0% |
| S2 Interventional | 18,300 | 79.0% |
| S3 Randomized | 14,167 | 61.2% |
| S4 Phase 3/4 | 4,583 | 19.8% |
| S5 Has Results | 3,655 | 15.8% |
| S6 Completed | 14,481 | 62.5% |
| S7 Interv+Completed | 11,761 | 50.8% |
| S8 RCT+Phase3/4+Comp | 2,704 | 11.7% |

### Breast Cancer (N = 15,856 baseline)

| Strategy | Count | Retention |
|----------|-------|-----------|
| S1 Condition Only | 15,856 | 100.0% |
| S2 Interventional | 12,372 | 78.0% |
| S3 Randomized | 5,854 | 36.9% |
| S4 Phase 3/4 | 1,812 | 11.4% |
| S5 Has Results | 2,316 | 14.6% |
| S6 Completed | 7,287 | 46.0% |
| S7 Interv+Completed | 5,734 | 36.2% |
| S8 RCT+Phase3/4+Comp | 726 | 4.6% |

### Depression (N = 11,974 baseline)

| Strategy | Count | Retention |
|----------|-------|-----------|
| S1 Condition Only | 11,974 | 100.0% |
| S2 Interventional | 10,046 | 83.9% |
| S3 Randomized | 7,753 | 64.7% |
| S4 Phase 3/4 | 1,659 | 13.9% |
| S5 Has Results | 1,768 | 14.8% |
| S6 Completed | 6,914 | 57.7% |
| S7 Interv+Completed | 5,900 | 49.3% |
| S8 RCT+Phase3/4+Comp | 871 | 7.3% |

### Additional Conditions

| Condition | Baseline | S3 (RCT) | S7 (Interv+Comp) | S8 (Best Quality) |
|-----------|----------|----------|------------------|-------------------|
| Hypertension | 11,761 | 6,285 (53%) | 5,081 (43%) | 1,370 (12%) |
| Heart Failure | 7,360 | 3,646 (50%) | 2,474 (34%) | 519 (7%) |
| Stroke | 10,312 | 5,721 (55%) | 3,658 (35%) | 453 (4%) |

---

## Key Findings

### 1. Filter Impact Varies by Condition

The percentage of studies retained after applying filters varies significantly:

- **Cancer conditions** show larger reductions (only 37% retained with Randomized filter)
- **Drug-focused conditions** (diabetes, hypertension) retain more (53-61%)
- **Behavioral conditions** (depression) have higher interventional ratios (84%)

### 2. Full-Text Search Can Exceed Condition Search

Strategy S9 (full-text with RCT keywords) sometimes returns MORE results than S1:
- Depression: 173% of baseline (20,753 vs 11,974)
- Stroke: 77% of baseline (7,966 vs 10,312)

This occurs because `query.term` searches ALL fields, not just condition.

### 3. Posted Results are Rare

Only 14-16% of registered trials have posted results on ClinicalTrials.gov, making S5 very restrictive.

### 4. Phase 3/4 Filter is Highly Restrictive

Only 10-22% of trials are Phase 3 or 4, making S4 and S8 useful only for focused searches.

---

## Recommendations

### For Systematic Reviews (Maximum Sensitivity)

```
https://clinicaltrials.gov/api/v2/studies?query.cond=<condition>&countTotal=true
```

**Rationale:** Cochrane recommends avoiding filters. This captures ALL study types.

### For RCT-Focused Reviews

```
https://clinicaltrials.gov/api/v2/studies?query.cond=<condition>&query.term=AREA[DesignAllocation]RANDOMIZED
```

**Rationale:** More precise than `StudyType=INTERVENTIONAL` (which includes single-arm studies).

### For Completed Trials with Published Results

```
https://clinicaltrials.gov/api/v2/studies?query.cond=<condition>&query.term=AREA[StudyType]INTERVENTIONAL&filter.overallStatus=COMPLETED
```

**Rationale:** Best balance of precision and recall for finding published evidence.

### For Validation/Quick Checks

```
https://clinicaltrials.gov/api/v2/studies?query.cond=<condition>&query.term=AREA[DesignAllocation]RANDOMIZED AND AREA[Phase](PHASE3 OR PHASE4)&filter.overallStatus=COMPLETED
```

**Rationale:** Highest quality subset for confirming specific trials exist.

---

## Recommended Workflow for Systematic Reviews

1. **Primary Search**: Run S1 (Condition Only) - export all NCT IDs
2. **Sensitivity Check**: Also run S9 (Full-text RCT keywords)
3. **De-duplicate**: Merge results by NCT ID
4. **Search ICTRP**: Also search WHO International Clinical Trials Registry Platform
5. **Screen**: Apply inclusion/exclusion criteria
6. **Document**: Record search dates, strategies, and results

---

## API Reference

### Query Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `query.cond` | Condition/disease field | `query.cond=diabetes` |
| `query.term` | Full-text + AREA syntax | `query.term=AREA[StudyType]INTERVENTIONAL` |
| `query.intr` | Intervention field | `query.intr=metformin` |
| `filter.overallStatus` | Recruitment status | `COMPLETED`, `RECRUITING` |
| `countTotal` | Include total count | `true` |
| `pageSize` | Results per page (max 1000) | `100` |

### AREA Syntax

```
AREA[FieldName]Value
AREA[FieldName](Value1 OR Value2)
AREA[FieldName]RANGE[start,end]
```

### Available AREA Fields

- `StudyType`: INTERVENTIONAL, OBSERVATIONAL
- `Phase`: EARLY_PHASE1, PHASE1, PHASE2, PHASE3, PHASE4, NA
- `DesignAllocation`: RANDOMIZED, NON_RANDOMIZED
- `DesignPrimaryPurpose`: TREATMENT, PREVENTION, DIAGNOSTIC
- `ResultsFirstPostDate`: Date results posted
- `LocationCountry`: Country name

---

## Files Delivered

| File | Description |
|------|-------------|
| `CTGov-Strategy-Tester-v2.html` | Interactive testing tool |
| `comprehensive_results.csv` | Raw validation data (60 searches) |
| `IMPROVEMENT_PLAN.md` | Technical analysis of issues and solutions |
| `COMPREHENSIVE_REPORT.md` | This report |

---

## Sources

- [Cochrane Handbook Chapter 4](https://training.cochrane.org/handbook/current/chapter-04)
- [PMC: Optimal CT.gov Search Approaches](https://pmc.ncbi.nlm.nih.gov/articles/PMC4076126/)
- [Searching Clinical Trials Registers: Guide for Systematic Reviewers](https://training.cochrane.org/resource/searching-clinical-trials-registers-guide-for-systematic-reviewers)
- [ClinicalTrials.gov API Documentation](https://clinicaltrials.gov/data-api/api)
- [NLM Technical Bulletin: API v2](https://www.nlm.nih.gov/pubs/techbull/ma24/ma24_clinicaltrials_api.html)

---

*Report generated from CT.gov Search Strategy Validation Project v2*
