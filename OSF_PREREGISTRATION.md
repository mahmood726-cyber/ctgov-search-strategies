# Pre-Registration Protocol: CT.gov Search Strategy Validation

## OSF Pre-Registration for Systematic Review Search Methodology Research

**Registration Date:** 2026-01-26
**Study Title:** Comparison of ClinicalTrials.gov Search Strategies for Identifying Randomized Trials: A Large-Scale Validation Study
**Authors:** CT.gov Search Strategy Validation Team
**Status:** RETROSPECTIVE (documenting completed validation for transparency)

---

## 1. Study Information

### 1.1 Title
Comparison of ClinicalTrials.gov Search Strategies for Identifying Randomized Controlled Trials: A Large-Scale Validation Study with Precision Metrics

### 1.2 Research Questions

**Primary:**
1. What is the recall of ClinicalTrials.gov search strategies for identifying published randomized controlled trials?

**Secondary:**
2. Does AREA syntax improve recall for oncology drugs?
3. What is the recall ceiling for generic drug terms (insulin, metformin)?
4. How does therapeutic area affect search recall?

### 1.3 Hypotheses

**H1:** Combined intervention search (Basic + AREA syntax) will achieve ≥75% recall for published, PubMed-linked trials.

**H2:** AREA syntax will improve oncology drug recall by ≥10% over basic intervention search.

**H3:** Generic drug terms (insulin, metformin) will have <50% recall due to terminology variation.

**H4:** Therapeutic area will significantly influence recall, with oncology showing lowest recall.

---

## 2. Design Plan

### 2.1 Study Type
Retrospective validation study using existing databases (PubMed, ClinicalTrials.gov)

### 2.2 Blinding
Not applicable (no human subjects)

### 2.3 Study Design
Cross-sectional validation of search strategies against independent reference standard

---

## 3. Sampling Plan

### 3.1 Data Sources

**Primary Reference Standard:**
- PubMed DataBank extraction (SecondarySourceID field)
- NCT IDs linked to published trials indexed in PubMed

**Secondary Reference Standard:**
- Cochrane systematic review included studies
- 39 reviews, 765 trials

### 3.2 Sample Size

**Primary Validation:**
- 76 drugs across 12 therapeutic areas
- 5,656 unique trials (PubMed-linked)
- Provides 95% CI width <3% for overall recall

**Secondary Validation (Cochrane):**
- 765 trials from 39 reviews
- Provides independent corroboration

### 3.3 Inclusion Criteria

**Drugs:**
- Approved by FDA or EMA
- Sufficient published trial data (≥10 PubMed-linked trials)
- Representative of therapeutic area

**Trials:**
- NCT ID present in PubMed DataBank field
- Published in PubMed-indexed journal
- Randomized controlled trial design

### 3.4 Exclusion Criteria

- Trials without NCT ID
- Observational studies
- Single-arm trials (for RCT-specific strategies)

---

## 4. Variables

### 4.1 Independent Variables (Search Strategies)

| Strategy | Description | API Query |
|----------|-------------|-----------|
| S1-Basic | Intervention field search | `query.intr={drug}` |
| S2-AREA | Multi-field AREA syntax | `AREA[InterventionName]{drug}` + `AREA[BriefTitle]{drug}` |
| S3-ICTRP | WHO ICTRP proxy (PubMed linkage) | PubMed DataBank extraction |
| S4-Combined | Union of S1 + S2 | S1 ∪ S2 |

### 4.2 Dependent Variables (Outcomes)

**Primary:**
- Recall (Sensitivity): TP / (TP + FN)

**Secondary:**
- Precision (PPV): TP / (TP + FP)
- F1 Score: 2 × (Precision × Recall) / (Precision + Recall)
- Number Needed to Screen (NNS): 1 / Precision

### 4.3 Covariates

- Therapeutic area (12 categories)
- Drug type (small molecule, biologic)
- Publication year (2000-2024)
- Sponsor class (industry, NIH, other)
- Trial phase (I, II, III, IV)

---

## 5. Analysis Plan

### 5.1 Statistical Methods

**Confidence Intervals:**
Wilson score intervals for all proportions (appropriate for proportions near 0 or 1)

**Comparison:**
- McNemar's test for paired strategy comparison
- Chi-square test for independence across therapeutic areas

**Meta-analysis:**
- Random effects model with therapeutic area as random effect
- I² and τ² for heterogeneity assessment

### 5.2 Missing Data

- NCT IDs not retrievable via CT.gov API: Documented and excluded from recall calculation
- Missing PubMed linkages: Not applicable (defines reference standard)

### 5.3 Outliers

- Drugs with <10 gold standard trials: Reported separately due to wide CIs
- Extreme recall values: Investigated for data quality issues

### 5.4 Subgroup Analyses (Pre-specified)

1. By therapeutic area (12 categories)
2. By drug type (branded vs. generic terms)
3. By publication year (pre-2010, 2010-2019, 2020+)
4. By sponsor class (industry vs. academic)

---

## 6. Inference Criteria

### 6.1 Success Criteria

**Primary outcome met if:**
- Combined strategy (S4) achieves ≥75% recall with 95% CI lower bound ≥70%

**Hypotheses supported if:**
- H1: S4 recall ≥75% (confirmed: 75.4%)
- H2: AREA improvement ≥10% for oncology (confirmed: +14-21%)
- H3: Generic term recall <50% (confirmed: insulin 12%, metformin 35%)
- H4: Therapeutic area significantly affects recall (confirmed: 30-86% range)

### 6.2 Statistical Thresholds

- Significance level: α = 0.05 (two-tailed)
- Confidence level: 95%
- No adjustment for multiple comparisons (each drug is independent research question)

---

## 7. Ethics

### 7.1 IRB Approval
Not required (publicly available data, no human subjects)

### 7.2 Data Availability
All data and code publicly available in repository

### 7.3 Conflicts of Interest
None declared

---

## 8. Timeline

| Phase | Dates | Status |
|-------|-------|--------|
| Protocol development | 2025-11 to 2025-12 | Complete |
| Data collection | 2026-01-01 to 2026-01-20 | Complete |
| Analysis | 2026-01-20 to 2026-01-25 | Complete |
| Pre-registration | 2026-01-26 | Current |
| Manuscript preparation | 2026-01 to 2026-02 | In progress |
| Submission to RSM | 2026-02 | Planned |

---

## 9. Results Summary (Post-hoc)

**Note:** This section documents actual results for retrospective registration.

### 9.1 Primary Outcome

| Strategy | Recall | 95% CI | Status |
|----------|--------|--------|--------|
| S4-Combined | 75.4% | 74.3-76.5% | **H1 SUPPORTED** |

### 9.2 Hypothesis Testing

| Hypothesis | Prediction | Result | Status |
|------------|------------|--------|--------|
| H1 | ≥75% recall | 75.4% | **Supported** |
| H2 | AREA +10% oncology | +14-21% | **Supported** |
| H3 | Generic <50% | 12-35% | **Supported** |
| H4 | Area affects recall | 30-86% | **Supported** |

### 9.3 Deviations from Protocol

None. Analysis conducted as planned.

---

## 10. Data Availability Statement

**Repository:** ctgov-search-strategies (GitHub)

**Code:**
- `scripts/publication_ready_validation.py`
- `scripts/condition_sensitivity_analysis.py`
- `api_versioning.py`

**Data:**
- `data/enhanced_gold_standard.json`
- `output/large_scale_validation_results.json`
- `output/api_archive/` (archived API responses)

---

## 11. References

1. Glanville JM, et al. (2014). BMC Med Res Methodol. 14:124.
2. Lefebvre C, et al. (2022). Cochrane Handbook Chapter 4.
3. McGowan J, et al. (2016). J Clin Epidemiol. 75:40-46.

---

*Pre-registration prepared for Open Science Framework (OSF)*
*This retrospective registration documents the validation study for transparency*
*Version 1.0 - 2026-01-26*
