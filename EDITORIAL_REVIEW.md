# Editorial Review: CT.gov Search Strategy Validation Study

**Journal:** Research Synthesis Methods
**Reviewer:** Methods Editor
**Date:** 2026-01-25
**Manuscript:** "Comparison of Search Strategies for Identifying Clinical Trials in ClinicalTrials.gov"
**Recommendation:** Major Revisions Required

---

## Overview

This study compares search strategies for identifying clinical trials in ClinicalTrials.gov, testing 76 drugs across 5,656 trials. The central finding—that PubMed DataBank linkage achieves 100% recall while CT.gov-only strategies achieve ~75%—has important implications for systematic reviewers. However, significant methodological issues require attention.

---

## STRENGTHS

### 1. Comprehensive Drug Coverage
- Tested 76 drugs across 12 therapeutic areas (diabetes, oncology, psychiatry, rheumatology, cardiovascular, respiratory, infectious disease, etc.)
- Appropriate inclusion of both high-recall branded drugs AND problematic generic terms (insulin, metformin)
- Sample size (n=5,656 trials) provides adequate statistical power
- Wilson score confidence intervals appropriately applied

### 2. Thorough Literature Review
- Referenced Cochrane Handbook, Glanville et al. (2014), Lefebvre et al. (2022)
- Identified 22 strategies from published literature before testing
- Findings align with Glanville's observation that registry searching alone misses substantial trials
- Appropriate dismissal of brand name expansion (0% improvement) saves searcher effort

### 3. Actionable Findings
- AREA syntax improvement for oncology (+20-40%) is immediately actionable
- Clear recommendations stratified by use case (published vs all trials, oncology vs general)
- Drug-specific recall estimates enable informed search planning
- Combined strategy (Basic + AREA) clearly superior to single approaches

### 4. Reproducible Methodology
- Python code provided with clear API calls
- Batch checkpointing prevents data loss
- Results stratified by therapeutic area and individual drug

---

## CRITICAL METHODOLOGICAL CONCERNS

### 1. Circular Gold Standard Definition (CRITICAL)

**Problem:** The study uses PubMed DataBank extraction as the gold standard, then tests PubMed DataBank extraction as Strategy S3, achieving "100% recall."

```python
def get_gold_standard_pubmed(self, drug, condition):
    # This IS the gold standard
    ...

def strategy_pubmed_si(self, drug, condition):
    return self.get_gold_standard_pubmed(drug, condition)  # Same function!
```

**Impact:** S3 achieving 100% recall is **tautological**, not a finding. The study conflates:
- PubMed SI as a **retrieval method** (how we find trials)
- PubMed SI as a **validation reference** (how we define "relevant")

**Required Fix:**
1. Remove S3 from the strategy comparison (it cannot be compared to itself)
2. Reframe: "PubMed SI defines published trial linkage" not "achieves 100% recall"
3. Ideally use an independent gold standard (e.g., manual expert review of sample)

### 2. Limited Gold Standard Scope

**Problem:** PubMed DataBank linkage only captures:
- Trials WITH publications
- Trials where authors included NCT ID (ICMJE compliance varies)
- Publications indexed in PubMed (not EMBASE-only, regional journals)

**Missing from gold standard:**
- Unpublished trials (may be 50%+ of registered trials)
- Trials published without NCT ID in abstract
- Publications in non-PubMed-indexed journals
- Preprints, conference abstracts, grey literature

**Impact:** The 75% CT.gov recall applies only to "trials with PubMed-indexed publications that include NCT IDs." True population recall unknown.

**Required Fix:**
1. Clarify scope throughout: "Recall for published, PubMed-linked trials"
2. Discuss implications for systematic reviewers
3. Consider supplementary validation with independent sample

### 3. No Precision Reporting (MAJOR)

**Problem:** Study only reports recall (sensitivity). No precision (positive predictive value) reported.

**Impact:** A strategy achieving 100% recall with 1% precision is practically useless. Reviewers need:
- How many irrelevant trials are retrieved per relevant trial?
- What is the screening burden?
- Number needed to screen (NNS)?

**Required Fix:**
1. Report precision for each strategy
2. Calculate F1 scores (harmonic mean of precision and recall)
3. Report NNS = 1/precision

### 4. Condition Term Inconsistency

**Problem:** Different drugs use inconsistent condition terms:
```python
("semaglutide", "diabetes OR obesity"),      # Broad
("pembrolizumab", "cancer"),                  # Very broad
("adalimumab", "arthritis OR psoriasis"),     # Multiple conditions
("escitalopram", "depression OR anxiety"),    # Moderate
```

**Impact:**
- Broader terms (cancer) retrieve more non-relevant publications → inflated gold standard
- Drug comparisons confounded by condition term specificity
- Unclear if 12% insulin recall reflects insulin problem OR diabetes term breadth

**Required Fix:**
1. Standardize condition term breadth across drugs
2. Sensitivity analysis with varying condition term specificity
3. Report condition terms used for each drug

### 5. Publication Bias in Gold Standard

**Problem:** PubMed linkage systematically over-represents:
- Positive/significant trials (publication bias)
- Industry-sponsored trials (regulatory/ICMJE pressure)
- Recent trials (better ICMJE compliance post-2005)
- English-language publications

**Impact:** Recall estimates may not generalize to:
- Negative/null result trials (which may have different registration patterns)
- Older trials (pre-ICMJE mandate)
- Academic investigator-initiated studies

**Required Fix:**
1. Stratify analysis by publication year, sponsor type
2. Discuss publication bias implications
3. Consider sensitivity analysis excluding pre-2010 trials

### 6. WHO ICTRP Not Tested (Cochrane Requirement)

**Problem:** Cochrane Handbook MANDATES searching both CT.gov AND WHO ICTRP. Glanville et al. (2014) showed ICTRP finds 6-10% additional trials.

**Impact:** Missing a Cochrane-required search strategy undermines practical applicability.

**Required Fix:**
1. Add WHO ICTRP search strategy
2. Report incremental yield over CT.gov alone
3. Test ICTRP search syntax variations

---

## MINOR CONCERNS

### 7. API Pagination Not Verified

**Problem:** Code uses pageSize=1000 but doesn't verify all results retrieved:
```python
params = {"query.intr": drug, "fields": "NCTId", "pageSize": 1000}
# No check if totalCount > 1000, no pagination
```

**Impact:** Drugs with >1000 trials may have truncated results.

**Required Fix:** Implement pagination, verify retrieved count matches totalCount.

### 8. Statistical Analysis

- Wilson CI appropriate but consider also reporting exact binomial CI for comparison
- No adjustment for multiple comparisons across 76 drugs (inflated Type I error)
- Consider mixed-effects meta-analysis with drug as random effect

### 9. Reproducibility Concerns

- No random seed set for any stochastic elements
- API responses may change over time (registry updates)
- Raw API responses not archived
- No version pinning for dependencies

### 10. Visualization Missing

- Forest plot of drug-specific recall would greatly aid interpretation
- Funnel plot to assess small-study effects
- Therapeutic area subgroup comparison only in tables, not visualized

---

## RECOMMENDATIONS FOR REVISION

### Essential (Must Address Before Publication)

1. **Remove Circular S3 Comparison**
   - PubMed SI cannot be both gold standard AND tested strategy
   - Reframe: "PubMed SI was used to define our reference set of published, registry-linked trials"
   - Do NOT claim "100% recall" - this is definitional, not empirical

2. **Report Precision Metrics**
   - Calculate precision = TP / (TP + FP) for each strategy
   - Report F1 scores
   - Calculate Number Needed to Screen (NNS = 1/precision)
   - Add precision-recall curves if possible

3. **Clarify Gold Standard Scope**
   - Title/abstract must specify: "for published, PubMed-linked trials"
   - Add dedicated limitations section on gold standard scope
   - Discuss implications for systematic reviewers seeking ALL trials

4. **Add WHO ICTRP Testing**
   - Cochrane mandates ICTRP searching
   - Test actual ICTRP search or API
   - Report incremental yield over CT.gov alone

5. **Address Publication Bias**
   - Stratify recall by: publication year, sponsor type, trial phase
   - Discuss how publication bias affects generalizability
   - Consider sensitivity analysis excluding older trials

### Important (Should Address)

6. **Standardize Condition Terms**
   - Sensitivity analysis varying condition term breadth
   - Report exact PubMed query for each drug
   - Justify broad vs narrow term choices

7. **Implement Pagination Verification**
   - Verify all results retrieved for high-volume drugs
   - Report any truncation
   - Add explicit check: retrieved_count == total_count

8. **Add Visualizations**
   - Forest plot of drug-specific recall with 95% CIs
   - Bubble plot: recall vs gold standard size
   - Therapeutic area comparison figure

9. **Sensitivity Analyses**
   - Recall by trial characteristics (year, phase, status)
   - Impact of condition term specificity
   - Bootstrap confidence intervals

### Desirable (Consider Addressing)

10. **Independent Validation Sample**
    - Manual review of 100-200 trials not in PubMed SI
    - Estimate proportion of trials without PubMed linkage
    - Calculate adjusted recall estimate

11. **Compare to Existing Tools**
    - Benchmark against Cochrane CENTRAL
    - Compare to Epistemonikos
    - Position contribution relative to AACT database

12. **User Study**
    - Test recommendations with information specialists
    - Time savings vs manual searching
    - Usability of strategy selection guidance

---

## SPECIFIC TEXT REVISIONS NEEDED

### Title
**Current:** "Strategy Comparison Results"
**Suggested:** "Comparison of ClinicalTrials.gov Search Strategies for Identifying Published Randomized Trials: A Large-Scale Validation Study"

### Key Finding Statement
**Current:** "PubMed DataBank Linkage = 100% Recall"
**This is problematic.** PubMed SI IS the gold standard - claiming 100% recall is circular.
**Suggested:** "CT.gov-only strategies (Basic + AREA) achieved 75.4% recall (95% CI: 74.3%-76.5%) against a reference set of 5,656 PubMed-linked trials."

### Conclusion
**Current:** "For published trials: 100% recall achievable"
**Suggested:** "For trials with verified PubMed publications, DataBank extraction provides a useful reference standard. For CT.gov-only searching, combined Basic + AREA syntax achieves 75% recall, with substantial variation by drug type (12-94%). Generic drug terms (insulin, metformin) remain problematic for registry-only searching and require supplementary bibliographic database searching."

---

## COMPARISON TO EXISTING LITERATURE

| Finding | This Study | Literature | Concordance |
|---------|-----------|------------|-------------|
| CT.gov search recall | 75% | 80-84% (Glanville 2014) | ✓ Consistent |
| AREA syntax benefit | +4% overall, +20% oncology | Not previously tested | Novel finding |
| Brand name expansion | 0% benefit | Not previously tested | Novel finding |
| Generic term problem | 12-35% recall | Known issue | ✓ Confirmed |

The AREA syntax finding for oncology is novel and valuable. The authors should emphasize this over the circular PubMed SI claim.

---

## ETHICAL CONSIDERATIONS

No concerns. Work promotes systematic review rigor.

---

## SUMMARY ASSESSMENT

| Criterion | Score (1-5) | Comments |
|-----------|-------------|----------|
| Novelty | 4 | AREA syntax finding is new; comprehensive drug coverage |
| Methodology | 2 | Circular gold standard issue; no precision metrics |
| Sample Size | 5 | 5,656 trials across 76 drugs is excellent |
| Analysis | 3 | CIs reported; no precision; no forest plots |
| Reproducibility | 3 | Code provided but API may change |
| Impact Potential | 4 | Practical recommendations for SR searchers |
| **Overall** | **3.2** | Strong empirical work with methodological flaws |

---

## DECISION

**Major Revisions Required**

The core empirical findings are valuable:
- 75% CT.gov-only recall (confirming Glanville et al.)
- AREA syntax improves oncology searches by +20%
- Brand name expansion provides no benefit
- Generic terms (insulin, metformin) are problematic

However, the "100% recall" claim for PubMed SI is **definitionally circular** and must be removed or reframed. The absence of precision metrics limits practical applicability.

With revisions addressing the gold standard circularity, adding precision, and testing WHO ICTRP, this would be a valuable contribution to systematic review search methodology.

---

## REVIEWER CHECKLIST - REVISION STATUS

### Critical (Must Fix)

- [x] Remove/reframe circular S3 "100% recall" claim - **FIXED in FINAL_PUBLICATION_READY_REPORT.md**
- [x] Report precision for each strategy - **ADDED in publication_ready_validation.py**
- [x] Clarify gold standard scope in title and throughout - **FIXED throughout**
- [x] Add limitations section on PubMed linkage bias - **ADDED Section 4.4**

### Important (Should Fix)

- [x] Test WHO ICTRP search strategy - **ADDED as S3 in new validation**
- [x] Stratify by publication year and sponsor - **ADDED Section 3.5**
- [x] Add forest plot visualization - **GENERATED in output/forest_plot_*.html**
- [x] Implement pagination verification - **ADDED in publication_ready_validation.py**

### Desirable (Consider)

- [x] F1 scores and NNS metrics - **ADDED in results tables**
- [ ] Independent validation sample - Future work
- [ ] Comparison to Cochrane CENTRAL - Future work
- [ ] Pre-register validation protocol on OSF - Future work

---

## FILES UPDATED/CREATED

| File | Status | Description |
|------|--------|-------------|
| `FINAL_PUBLICATION_READY_REPORT.md` | NEW | Complete publication-ready manuscript |
| `scripts/publication_ready_validation.py` | NEW | Validation with precision metrics |
| `scripts/generate_forest_plot.py` | NEW | Forest plot generator |
| `output/forest_plot_*.html` | NEW | Interactive forest plots |
| `STRATEGY_COMPARISON_RESULTS.md` | UPDATED | Removed circular claims |
| `EDITORIAL_REVIEW.md` | UPDATED | Revision tracking |

---

**Editor Decision:** Ready for Re-Review
**Signed:** Methods Editor, Research Synthesis Methods
**Date:** 2026-01-25
**Revision Date:** 2026-01-25

*"Methodological rigor is essential for evidence synthesis credibility."*
