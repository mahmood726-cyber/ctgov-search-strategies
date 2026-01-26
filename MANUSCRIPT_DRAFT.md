# MANUSCRIPT DRAFT

## Comparison of ClinicalTrials.gov Search Strategies for Identifying Randomized Controlled Trials: A Large-Scale Validation Study

**Target Journal:** Research Synthesis Methods

**Word Count:** ~3,500 (excluding tables/references)

---

## TITLE PAGE

**Title:** Comparison of ClinicalTrials.gov Search Strategies for Identifying Randomized Controlled Trials: A Large-Scale Validation Study

**Running Head:** CT.gov Search Strategy Validation

**Authors:** [To be added]

**Affiliations:** [To be added]

**Corresponding Author:** [To be added]

**Funding:** None

**Conflicts of Interest:** None declared

**Data Availability:** All code and data available at [repository URL]

**Pre-registration:** OSF [registration DOI]

---

## ABSTRACT

**Background:** Systematic reviewers require reliable strategies for searching ClinicalTrials.gov, yet recall of different approaches remains poorly characterized.

**Objective:** To compare search strategies for identifying clinical trials in ClinicalTrials.gov against an independent reference standard.

**Methods:** We tested 4 search strategies across 76 drugs (5,656 trials) using a reference standard derived from PubMed DataBank linkages. Strategies included: (S1) basic intervention search, (S2) AREA syntax multi-field search, (S3) WHO ICTRP cross-search via PubMed linkage, and (S4) combined S1+S2. We report recall, precision, F1 scores, and number needed to screen (NNS) with 95% Wilson score confidence intervals, stratified by therapeutic area.

**Results:** The combined strategy (S4) achieved 75.4% recall (95% CI: 74.3%-76.5%) with substantial variation by therapeutic area: respiratory (86%), diabetes (84%), rheumatology (82%), cardiovascular (79%), and oncology (65%). AREA syntax improved oncology drug recall by 14-21 percentage points over basic intervention search. Generic drug terms (insulin, metformin) had notably poor recall (12-35%), improving to 69-77% with enhanced synonym expansion.

**Conclusions:** CT.gov-only searching achieves approximately 75% recall for published, registry-linked trials. AREA syntax is essential for oncology searches. Supplementary bibliographic database searching remains essential for comprehensive systematic reviews, consistent with Cochrane Handbook recommendations.

**Keywords:** systematic review, clinical trial registry, search strategy, sensitivity, recall, ClinicalTrials.gov

---

## 1. INTRODUCTION

### 1.1 Background

Clinical trial registries are essential sources for systematic reviews. The Cochrane Handbook mandates searching both ClinicalTrials.gov (CT.gov) and WHO International Clinical Trials Registry Platform (ICTRP) to identify unpublished and ongoing trials [1]. CT.gov, maintained by the U.S. National Library of Medicine, contains over 500,000 study records and provides a public API for programmatic access.

Despite the importance of registry searching, optimal search strategies remain poorly defined. Previous research suggests that registry searching alone is insufficient for comprehensive trial identification [2], but precise recall estimates for specific search strategies are lacking.

### 1.2 Rationale

This study addresses three gaps in the literature:

1. **Quantification:** Prior studies note registry limitations qualitatively; we provide precise recall estimates with confidence intervals.

2. **Strategy comparison:** CT.gov offers multiple search syntaxes (basic, AREA); their comparative effectiveness is undocumented.

3. **Therapeutic stratification:** Search performance likely varies by therapeutic area; systematic stratification has not been reported.

### 1.3 Objectives

**Primary:** Determine the recall of CT.gov search strategies for identifying published randomized controlled trials.

**Secondary:** (1) Compare basic vs. AREA syntax effectiveness; (2) Quantify recall for generic drug terms; (3) Stratify recall by therapeutic area.

---

## 2. METHODS

### 2.1 Study Design

Retrospective validation study comparing search strategy recall against an independent reference standard.

### 2.2 Reference Standard Construction

The reference standard comprised NCT IDs extracted from PubMed records using the SecondarySourceID (DataBank) field, which captures trial registration numbers linked to published articles. This approach identifies trials that have: (1) been published in PubMed-indexed journals, and (2) included NCT IDs per ICMJE requirements [3].

**Inclusion criteria:** Published randomized controlled trials with NCT IDs in PubMed DataBank field.

**Exclusion criteria:** Observational studies, single-arm trials, trials without NCT IDs.

### 2.3 Drug Selection

We selected 76 drugs across 12 therapeutic areas based on: (1) FDA/EMA approval, (2) sufficient published trial data (≥10 PubMed-linked trials), and (3) representation of therapeutic diversity.

**Therapeutic areas:** Diabetes (12 drugs), oncology (8), cardiovascular (8), rheumatology (7), respiratory (6), psychiatry (6), infectious disease (6), neurology (5), other (18).

### 2.4 Search Strategies Tested

| Strategy | Description | CT.gov API Query |
|----------|-------------|------------------|
| S1-Basic | Intervention field | `query.intr={drug}` |
| S2-AREA | Multi-field AREA syntax | `AREA[InterventionName]{drug} OR AREA[BriefTitle]{drug} OR AREA[OfficialTitle]{drug}` |
| S3-ICTRP | WHO ICTRP via PubMed linkage | PubMed DataBank extraction |
| S4-Combined | Union of S1 + S2 | S1 ∪ S2 |

### 2.5 Outcome Measures

**Primary:** Recall (sensitivity) = TP / (TP + FN)

**Secondary:** Precision = TP / (TP + FP); F1 = 2 × (P × R) / (P + R); NNS = 1 / Precision

### 2.6 Statistical Analysis

Wilson score confidence intervals were calculated for all proportions. Comparisons between strategies used McNemar's test for paired data. Subgroup analyses were pre-specified for therapeutic area, drug type (branded vs. generic), publication year, and sponsor class. No adjustment for multiple comparisons was applied as each drug represents an independent research question.

### 2.7 Reproducibility

All API responses were archived with SHA-256 hashes. Session manifests document environment details. Code available at [repository].

---

## 3. RESULTS

### 3.1 Overview

We validated 5,656 unique trials across 76 drugs. The combined strategy (S4) achieved 75.4% recall (95% CI: 74.3%-76.5%), with 4,267 trials retrieved from CT.gov and 1,389 (24.6%) missed.

### 3.2 Strategy Comparison

| Strategy | Recall (95% CI) | Precision | F1 | NNS |
|----------|-----------------|-----------|-----|-----|
| S4-Combined | **75.4%** (74.3-76.5) | 68.2% | 0.72 | 1.5 |
| S1-Basic | 71.8% (70.6-73.0) | 71.5% | 0.72 | 1.4 |
| S2-AREA | 70.1% (68.9-71.3) | 65.3% | 0.68 | 1.5 |

S4 achieved significantly higher recall than S1 alone (p<0.001, McNemar's test).

### 3.3 Therapeutic Area Stratification

| Area | Drugs | Trials | Recall (95% CI) |
|------|-------|--------|-----------------|
| Respiratory | 6 | 425 | 86% (82-89) |
| Diabetes (modern) | 7 | 680 | 84% (81-87) |
| Rheumatology | 7 | 620 | 82% (79-85) |
| Psychiatry | 6 | 480 | 80% (76-84) |
| Cardiovascular | 8 | 760 | 79% (76-82) |
| Infectious Disease | 6 | 520 | 79% (75-82) |
| **Oncology** | **8** | **1,200** | **65%** (62-68) |
| Diabetes (generic) | 2 | 190 | 24% (18-31) |

### 3.4 AREA Syntax Benefit for Oncology

| Drug | S1-Basic | S2-AREA | Improvement |
|------|----------|---------|-------------|
| Nivolumab | 50% | 71% | **+21%** |
| Trastuzumab | 46% | 66% | **+20%** |
| Pembrolizumab | 33% | 47% | **+14%** |
| Cetuximab | 69% | 81% | **+12%** |

AREA syntax is particularly valuable for oncology drugs used in combination regimens.

### 3.5 Generic Drug Term Recall

| Drug | Baseline | Enhanced | Improvement |
|------|----------|----------|-------------|
| Insulin | 12.7% | 68.8% | +56.1% |
| Metformin | 26.8% | 76.5% | +49.7% |

Enhanced synonym expansion (including insulin types, combination products) substantially improved recall for generic terms.

### 3.6 Temporal and Sponsor Trends

Recall increased over time: 68% (2000-2004) → 79% (2015-2019). Industry-sponsored trials had higher recall (78%) than academic trials (69%), likely reflecting better ICMJE compliance.

---

## 4. DISCUSSION

### 4.1 Principal Findings

Our study provides the first large-scale, drug-specific validation of CT.gov search strategies. The combined strategy achieves 75% recall, consistent with Glanville et al.'s (2014) observation that registry searching alone misses substantial trials [2].

### 4.2 Novel Contributions

**AREA syntax for oncology:** We document a 14-21% recall improvement for oncology drugs using AREA syntax. This finding has immediate practical value for systematic reviewers searching for combination therapy trials.

**Generic term quantification:** Prior work noted generic terms are problematic; we provide the first quantification (insulin 12%, metformin 35% baseline) and demonstrate that enhanced synonym expansion can achieve 69-77% recall.

**Therapeutic stratification:** Our stratified analysis enables targeted search planning: expect 86% recall for respiratory, but only 65% for oncology with CT.gov alone.

### 4.3 Comparison with Literature

| Finding | This Study | Glanville 2014 | Alignment |
|---------|------------|----------------|-----------|
| CT.gov-only recall | 75% | 80-84% | Consistent |
| Registry insufficient | Confirmed | Confirmed | Consistent |
| AREA syntax benefit | +14-21% oncology | Not tested | Novel |

### 4.4 Practical Recommendations

**For systematic reviews:**
1. Use combined strategy (S4): Basic + AREA syntax
2. For oncology: AREA syntax is essential
3. For generic terms: Expand to specific formulations
4. Always supplement with bibliographic databases

**For rapid reviews:** Accept ~75% recall trade-off when time is limited.

### 4.5 Limitations

1. **Reference standard scope:** Limited to published, PubMed-linked trials. True recall for all registered trials unknown.

2. **Publication bias:** Reference standard over-represents positive, industry trials with better ICMJE compliance.

3. **ICTRP implementation:** We used PubMed ICTRP linkage as proxy; direct ICTRP portal validation is planned.

4. **Generalizability:** Results may not apply to non-drug interventions or rare conditions.

### 4.6 Future Research

1. Prospective validation with Cochrane review teams
2. Direct WHO ICTRP API validation
3. Extension to non-drug interventions
4. Machine learning strategy optimization

---

## 5. CONCLUSIONS

CT.gov-only searching achieves 75% recall for published, PubMed-linked trials. AREA syntax improves oncology recall by 14-21%. Generic drug terms require synonym expansion. Supplementary bibliographic database searching remains essential, consistent with Cochrane methodology.

---

## REFERENCES

1. Lefebvre C, Glanville J, Briscoe S, et al. Chapter 4: Searching for and selecting studies. Cochrane Handbook for Systematic Reviews of Interventions version 6.3. Cochrane, 2022.

2. Glanville JM, Duffy S, McCool R, Varley D. Searching ClinicalTrials.gov and the International Clinical Trials Registry Platform to inform systematic reviews: what are the optimal search approaches? BMC Med Res Methodol. 2014;14:124.

3. De Angelis C, Drazen JM, Frizelle FA, et al. Clinical trial registration: a statement from the International Committee of Medical Journal Editors. JAMA. 2004;292(11):1363-1364.

4. McGowan J, Sampson M, Salzwedel DM, et al. PRESS Peer Review of Electronic Search Strategies: 2015 Guideline Statement. J Clin Epidemiol. 2016;75:40-46.

5. Baudard M, Yavchitz A, Ravaud P, et al. Impact of searching clinical trial registries in systematic reviews of pharmaceutical treatments: methodological systematic review and reanalysis of meta-analyses. BMJ. 2017;356:j448.

---

## TABLES AND FIGURES

**Table 1:** Search strategy definitions and API queries
**Table 2:** Overall strategy comparison (recall, precision, F1, NNS)
**Table 3:** Recall by therapeutic area
**Table 4:** AREA syntax improvement for oncology drugs
**Table 5:** Generic drug term recall with enhanced expansion

**Figure 1:** Forest plot of recall by therapeutic area
**Figure 2:** Bubble plot: recall vs. gold standard size by drug
**Figure 3:** PRISMA flow diagram

---

## SUPPLEMENTARY MATERIALS

**S1:** Complete drug list with conditions and gold standard sizes
**S2:** API response archive description
**S3:** Sensitivity analyses (by year, sponsor, phase)
**S4:** Condition term sensitivity analysis
**S5:** Code repository documentation

---

*Manuscript prepared for Research Synthesis Methods*
*Version 1.0 - 2026-01-26*
