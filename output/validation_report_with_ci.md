# CT.gov Search Strategy Validation Report
**Generated:** 2026-01-25T13:29:14.270983+00:00

## Executive Summary

This report presents validation results with proper statistical analysis:
- 95% Wilson score confidence intervals for all proportions
- Precision (PPV) and Number Needed to Screen (NNS) metrics
- Multiple conditions tested for generalizability

---

## Strategy Performance

| Strategy | Name | Recall (95% CI) | Precision (95% CI) | NNS | Retrieved |
|----------|------|-----------------|-------------------|-----|-----------|
| S1 | Condition Only (Maximum Recall) | 0.0% (0.0%-19.4%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S2 | Interventional Studies | 0.0% (0.0%-19.4%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S3 | Randomized Allocation Only | 0.0% (0.0%-19.4%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S6 | Completed Status | 0.0% (0.0%-19.4%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S10 | Treatment RCTs Only | 0.0% (0.0%-19.4%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S1 | Condition Only (Maximum Recall) | 6.2% (1.1%-28.3%) | 1.0% (0.2%-5.4%) | 100.0 | 100 |
| S2 | Interventional Studies | 6.2% (1.1%-28.3%) | 1.0% (0.2%-5.4%) | 100.0 | 100 |
| S3 | Randomized Allocation Only | 6.2% (1.1%-28.3%) | 1.0% (0.2%-5.4%) | 100.0 | 100 |
| S6 | Completed Status | 0.0% (0.0%-19.4%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S10 | Treatment RCTs Only | 6.2% (1.1%-28.3%) | 1.0% (0.2%-5.4%) | 100.0 | 100 |
| S1 | Condition Only (Maximum Recall) | 0.0% (0.0%-22.8%) | 0.0% (0.0%-0.0%) | >1000 | 0 |
| S2 | Interventional Studies | 0.0% (0.0%-22.8%) | 0.0% (0.0%-0.0%) | >1000 | 0 |
| S3 | Randomized Allocation Only | 0.0% (0.0%-22.8%) | 0.0% (0.0%-0.0%) | >1000 | 0 |
| S6 | Completed Status | 0.0% (0.0%-22.8%) | 0.0% (0.0%-0.0%) | >1000 | 0 |
| S10 | Treatment RCTs Only | 0.0% (0.0%-22.8%) | 0.0% (0.0%-0.0%) | >1000 | 0 |
| S1 | Condition Only (Maximum Recall) | 0.0% (0.0%-22.8%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S2 | Interventional Studies | 0.0% (0.0%-22.8%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S3 | Randomized Allocation Only | 0.0% (0.0%-22.8%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S6 | Completed Status | 0.0% (0.0%-22.8%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S10 | Treatment RCTs Only | 0.0% (0.0%-22.8%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S1 | Condition Only (Maximum Recall) | 0.0% (0.0%-22.8%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S2 | Interventional Studies | 0.0% (0.0%-22.8%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S3 | Randomized Allocation Only | 0.0% (0.0%-22.8%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S6 | Completed Status | 0.0% (0.0%-22.8%) | 0.0% (0.0%-3.7%) | >1000 | 100 |
| S10 | Treatment RCTs Only | 0.0% (0.0%-22.8%) | 0.0% (0.0%-3.7%) | >1000 | 100 |

---

## Detailed Results

### S1: Condition Only (Maximum Recall)

**Condition:** heart failure
**Query:** `query.cond=heart failure`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 16 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 16 |
| Recall | 0.0% (95% CI: 0.0% - 19.4%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S2: Interventional Studies

**Condition:** heart failure
**Query:** `query.cond=heart failure&query.term=AREA[StudyType]INTERVENTIONAL`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 16 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 16 |
| Recall | 0.0% (95% CI: 0.0% - 19.4%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S3: Randomized Allocation Only

**Condition:** heart failure
**Query:** `query.cond=heart failure&query.term=AREA[DesignAllocation]RANDOMIZED`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 16 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 16 |
| Recall | 0.0% (95% CI: 0.0% - 19.4%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S6: Completed Status

**Condition:** heart failure
**Query:** `query.cond=heart failure&filter.overallStatus=COMPLETED`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 16 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 16 |
| Recall | 0.0% (95% CI: 0.0% - 19.4%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S10: Treatment RCTs Only

**Condition:** heart failure
**Query:** `query.cond=heart failure&query.term=AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 16 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 16 |
| Recall | 0.0% (95% CI: 0.0% - 19.4%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S1: Condition Only (Maximum Recall)

**Condition:** COPD
**Query:** `query.cond=COPD`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 16 |
| Total Retrieved | 100 |
| True Positives | 1 |
| False Negatives | 15 |
| Recall | 6.2% (95% CI: 1.1% - 28.3%) |
| Precision | 1.0% (95% CI: 0.2% - 5.4%) |
| F1 Score | 0.017 |
| Number Needed to Screen | 100.0 |
| Miss Rate | 93.8% |

### S2: Interventional Studies

**Condition:** COPD
**Query:** `query.cond=COPD&query.term=AREA[StudyType]INTERVENTIONAL`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 16 |
| Total Retrieved | 100 |
| True Positives | 1 |
| False Negatives | 15 |
| Recall | 6.2% (95% CI: 1.1% - 28.3%) |
| Precision | 1.0% (95% CI: 0.2% - 5.4%) |
| F1 Score | 0.017 |
| Number Needed to Screen | 100.0 |
| Miss Rate | 93.8% |

### S3: Randomized Allocation Only

**Condition:** COPD
**Query:** `query.cond=COPD&query.term=AREA[DesignAllocation]RANDOMIZED`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 16 |
| Total Retrieved | 100 |
| True Positives | 1 |
| False Negatives | 15 |
| Recall | 6.2% (95% CI: 1.1% - 28.3%) |
| Precision | 1.0% (95% CI: 0.2% - 5.4%) |
| F1 Score | 0.017 |
| Number Needed to Screen | 100.0 |
| Miss Rate | 93.8% |

### S6: Completed Status

**Condition:** COPD
**Query:** `query.cond=COPD&filter.overallStatus=COMPLETED`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 16 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 16 |
| Recall | 0.0% (95% CI: 0.0% - 19.4%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S10: Treatment RCTs Only

**Condition:** COPD
**Query:** `query.cond=COPD&query.term=AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 16 |
| Total Retrieved | 100 |
| True Positives | 1 |
| False Negatives | 15 |
| Recall | 6.2% (95% CI: 1.1% - 28.3%) |
| Precision | 1.0% (95% CI: 0.2% - 5.4%) |
| F1 Score | 0.017 |
| Number Needed to Screen | 100.0 |
| Miss Rate | 93.8% |

### S1: Condition Only (Maximum Recall)

**Condition:** CD006475
**Query:** `query.cond=CD006475`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 0 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 0.0%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S2: Interventional Studies

**Condition:** CD006475
**Query:** `query.cond=CD006475&query.term=AREA[StudyType]INTERVENTIONAL`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 0 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 0.0%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S3: Randomized Allocation Only

**Condition:** CD006475
**Query:** `query.cond=CD006475&query.term=AREA[DesignAllocation]RANDOMIZED`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 0 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 0.0%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S6: Completed Status

**Condition:** CD006475
**Query:** `query.cond=CD006475&filter.overallStatus=COMPLETED`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 0 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 0.0%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S10: Treatment RCTs Only

**Condition:** CD006475
**Query:** `query.cond=CD006475&query.term=AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 0 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 0.0%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S1: Condition Only (Maximum Recall)

**Condition:** diabetes mellitus
**Query:** `query.cond=diabetes mellitus`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S2: Interventional Studies

**Condition:** diabetes mellitus
**Query:** `query.cond=diabetes mellitus&query.term=AREA[StudyType]INTERVENTIONAL`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S3: Randomized Allocation Only

**Condition:** diabetes mellitus
**Query:** `query.cond=diabetes mellitus&query.term=AREA[DesignAllocation]RANDOMIZED`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S6: Completed Status

**Condition:** diabetes mellitus
**Query:** `query.cond=diabetes mellitus&filter.overallStatus=COMPLETED`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S10: Treatment RCTs Only

**Condition:** diabetes mellitus
**Query:** `query.cond=diabetes mellitus&query.term=AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S1: Condition Only (Maximum Recall)

**Condition:** depression
**Query:** `query.cond=depression`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S2: Interventional Studies

**Condition:** depression
**Query:** `query.cond=depression&query.term=AREA[StudyType]INTERVENTIONAL`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S3: Randomized Allocation Only

**Condition:** depression
**Query:** `query.cond=depression&query.term=AREA[DesignAllocation]RANDOMIZED`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S6: Completed Status

**Condition:** depression
**Query:** `query.cond=depression&filter.overallStatus=COMPLETED`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

### S10: Treatment RCTs Only

**Condition:** depression
**Query:** `query.cond=depression&query.term=AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT`

| Metric | Value |
|--------|-------|
| Gold Standard Size | 13 |
| Total Retrieved | 100 |
| True Positives | 0 |
| False Negatives | 13 |
| Recall | 0.0% (95% CI: 0.0% - 22.8%) |
| Precision | 0.0% (95% CI: 0.0% - 3.7%) |
| F1 Score | 0.000 |
| Number Needed to Screen | inf |
| Miss Rate | 100.0% |

---

## Statistical Methods

- **Confidence Intervals:** Wilson score method (more accurate for extreme proportions)
- **Recall:** Sensitivity = TP / (TP + FN)
- **Precision:** PPV = TP / Total Retrieved
- **NNS:** Number Needed to Screen = 1 / Precision

---

*Report generated by CT.gov Trial Registry Integrity Suite v4.1*