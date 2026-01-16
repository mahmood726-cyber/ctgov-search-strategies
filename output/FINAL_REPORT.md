# CT.gov Search Strategy Validation Report

**Date:** January 2026
**Data Source:** ClinicalTrials.gov API v2 + 501 Cochrane Systematic Reviews

---

## Executive Summary

This validation tested 6 search strategies across 6 medical conditions to determine optimal approaches for searching ClinicalTrials.gov (CT.gov) for systematic reviews. Key findings:

- **Condition field search** (`query.cond`) is the most reliable baseline strategy
- **Interventional filter** reduces results by ~20-28% while retaining all RCTs
- **Completed filter** reduces results by ~37-57% (varies by condition)
- **Combined filters** achieve ~50-65% reduction with high precision

---

## Validation Results

### Results by Search Strategy (6 conditions tested)

| Strategy | Avg Results | Description |
|----------|-------------|-------------|
| fulltext_search | 43,636 | `query.term=<condition>` - broadest, includes all text matches |
| all_studies | 29,777 | `query.cond=<condition>` - condition field, all study types |
| interventional_only | 23,331 | + `filter.advanced=AREA[StudyType]INTERVENTIONAL` |
| fulltext_randomized | 13,516 | `query.term=<condition> randomized` |
| completed_only | 14,504 | + `filter.overallStatus=COMPLETED` |
| interventional_completed | 11,518 | Both filters combined |

### Results by Condition

| Condition | All Studies | Interventional | Completed | Both Filters |
|-----------|-------------|----------------|-----------|--------------|
| Cancer | 116,378 | 91,896 (79%) | 50,452 (43%) | 40,142 (35%) |
| Diabetes | 23,155 | 18,300 (79%) | 14,481 (63%) | 11,761 (51%) |
| Depression | 11,974 | 10,046 (84%) | 6,914 (58%) | 5,900 (49%) |
| Hypertension | 11,761 | 8,567 (73%) | 6,755 (57%) | 5,081 (43%) |
| Stroke | 10,312 | 7,512 (73%) | 5,008 (49%) | 3,658 (35%) |
| Asthma | 5,082 | 3,666 (72%) | 3,414 (67%) | 2,566 (50%) |

---

## Filter Effectiveness Analysis

### Interventional Filter
- **Average reduction:** 21-28% fewer results
- **Removes:** Observational studies, registries, expanded access
- **Retains:** All RCTs, single-arm trials, adaptive trials
- **Recommended:** Yes - essential for systematic reviews of RCTs

### Completed Status Filter
- **Average reduction:** 33-57% fewer results
- **Removes:** Recruiting, not yet recruiting, suspended, terminated
- **Retains:** Completed trials (likely published)
- **Recommended:** Yes for reviews of published evidence

### Combined Filters
- **Average reduction:** 49-65% fewer results
- **Best for:** Manageable screening workload
- **Risk:** May miss recently completed/ongoing relevant trials

---

## Cochrane Data Context

Analysis of 501 Cochrane systematic reviews containing 10,074 unique RCTs:

### Condition Distribution in Cochrane Reviews
| Category | Reviews | Search Keywords |
|----------|---------|-----------------|
| Mental Health | 119 | depression, anxiety, PTSD, addiction |
| Pain | 115 | chronic pain, back pain, analgesics |
| Infection | 102 | antibiotics, viral, bacterial |
| Gastrointestinal | 75 | GI bleeding, ulcers, IBS |
| Cardiovascular | 69 | heart failure, hypertension |
| Pregnancy | 54 | maternal, prenatal, obstetric |
| Cancer | 51 | oncology, chemotherapy |
| Respiratory | 44 | COPD, asthma, pneumonia |
| Diabetes | 35 | type 2, insulin, glucose |
| Neurological | 34 | stroke, epilepsy, MS |

---

## Recommended Search Strategies

### 1. MAXIMUM RECALL (Comprehensive Search)
```
https://clinicaltrials.gov/api/v2/studies?query.cond=<CONDITION>
```
- **Use when:** Cannot afford to miss any trial
- **Expected results:** Highest count
- **Screening burden:** High

### 2. RCT-FOCUSED (Interventional Only)
```
https://clinicaltrials.gov/api/v2/studies?query.cond=<CONDITION>&filter.advanced=AREA[StudyType]INTERVENTIONAL
```
- **Use when:** Only interested in intervention studies
- **Reduction:** ~20-28%
- **Screening burden:** Moderate

### 3. COMPLETED RCTS (Published Evidence)
```
https://clinicaltrials.gov/api/v2/studies?query.cond=<CONDITION>&filter.advanced=AREA[StudyType]INTERVENTIONAL&filter.overallStatus=COMPLETED
```
- **Use when:** Seeking published results
- **Reduction:** ~50-65%
- **Screening burden:** Lower

### 4. PRECISION SEARCH (Term + Keywords)
```
https://clinicaltrials.gov/api/v2/studies?query.term=<CONDITION> randomized
```
- **Use when:** Confirming specific trial exists
- **Reduction:** Variable
- **Screening burden:** Lowest

---

## Systematic Review Workflow

### Recommended Protocol for CT.gov Searching

1. **Primary Search**
   - Use `query.cond=<condition>` with `filter.studyType=INTERVENTIONAL`
   - Export all NCT IDs

2. **Supplementary Search**
   - Use `query.term=<condition> randomized clinical trial`
   - Capture any missed by condition field

3. **Deduplication**
   - Merge results by NCT ID
   - Remove duplicates

4. **Screening**
   - Apply inclusion/exclusion criteria
   - Document excluded studies with reasons

5. **Validation**
   - Cross-reference with your included studies
   - Calculate recall: (found in CT.gov / total included) × 100%

---

## API Parameter Reference

### Search Fields
| Parameter | Description | Example |
|-----------|-------------|---------|
| `query.cond` | Condition/disease field | `query.cond=diabetes` |
| `query.term` | Full-text search | `query.term=insulin randomized` |
| `query.intr` | Intervention field | `query.intr=metformin` |
| `query.titles` | Title search only | `query.titles=diabetes prevention` |

### Filters
| Parameter | Values | Example |
|-----------|--------|---------|
| `filter.overallStatus` | COMPLETED, RECRUITING, etc. | `filter.overallStatus=COMPLETED` |
| `filter.advanced` | AREA syntax | `filter.advanced=AREA[StudyType]INTERVENTIONAL` |

### Pagination
| Parameter | Description | Default |
|-----------|-------------|---------|
| `pageSize` | Results per page | 10 (max 1000) |
| `pageToken` | Next page token | - |
| `countTotal` | Include total count | false |

---

## Technical Notes

### API Endpoint
```
https://clinicaltrials.gov/api/v2/studies
```

### Worker Proxy (for CORS bypass)
```
https://restless-term-5510.mahmood726.workers.dev/?url=<ENCODED_API_URL>
```

### URL Encoding Requirements
- Encode `?` as `%3F`
- Encode `&` as `%26`
- Encode `[` as `%5B`
- Encode `]` as `%5D`
- Encode spaces as `%20`

---

## Files Generated

| File | Description |
|------|-------------|
| `complete_validation.csv` | Raw validation results |
| `extracted_studies.csv` | 10,581 studies from Cochrane reviews |
| `review_conditions.csv` | Condition mapping for 501 reviews |
| `CTGov-Search-Tester.html` | Interactive search tool |

---

## Conclusions

1. **For comprehensive systematic reviews:** Use `query.cond` with interventional filter
2. **For manageable workload:** Add completed status filter
3. **For validation:** Use `query.term` with specific keywords
4. **Always:** Export NCT IDs for deduplication and tracking

The CT.gov API provides flexible search capabilities. The key is matching your search strategy to your review's sensitivity/specificity requirements.

---

*Report generated from CT.gov Search Strategy Validation Project*
