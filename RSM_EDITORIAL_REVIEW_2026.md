# Editorial Review: Research Synthesis Methods

**Manuscript:** "Comparison of ClinicalTrials.gov Search Strategies for Identifying Randomized Trials: A Large-Scale Validation Study"

**Journal:** Research Synthesis Methods
**Editor:** Methods Editor
**Date:** 2026-01-26
**Recommendation:** Accept with Minor Revisions

---

## Executive Summary

This manuscript presents a comprehensive validation of search strategies for ClinicalTrials.gov across 76 drugs and 5,656 trials. The authors have demonstrated commendable methodological evolution, addressing previous circularity concerns and providing honest, nuanced findings. The work makes important contributions to systematic review search methodology.

**Key Strengths:**
- Transparent acknowledgment of methodological limitations
- Large-scale validation with appropriate confidence intervals
- Novel findings on AREA syntax for oncology
- Honest characterization of recall ceilings

**Overall Assessment:** This is rigorous, honest methodology research that fills a gap in the systematic review search literature.

---

## DETAILED EVALUATION

### 1. METHODOLOGY (Score: 4/5)

#### Strengths

**1.1 Resolution of Circularity Issue**

The authors have admirably addressed the critical circularity problem identified in earlier versions. The HONEST_FINDINGS.md document explicitly distinguishes between:

- **Circular approach (rejected):** NCT ID → CT.gov metadata → Search CT.gov → Find trial (97% recall - misleading)
- **Rigorous approach (adopted):** PICO → Search CT.gov → Compare to independent gold standard (45-80% recall - honest)

This methodological transparency is exemplary and rare in the field.

**1.2 Reference Standard Construction**

The dual approach using:
1. PubMed DataBank linkages (4,839 trials)
2. Cochrane review extraction (765 trials from 39 reviews)

...provides complementary validation. The authors correctly note limitations of each approach.

**1.3 Stratified Analysis**

Excellent stratification by:
- Therapeutic area (diabetes, oncology, cardiovascular, etc.)
- Drug type (branded vs. generic)
- Time period (2000-2024)
- Sponsor class (industry vs. NIH vs. other)

This enables nuanced recommendations rather than one-size-fits-all guidance.

#### Concerns (Minor)

**1.4 ICTRP Implementation**

The manuscript uses PubMed ICTRP linkage as a proxy for direct WHO ICTRP searching. While practical, direct ICTRP API/portal validation would strengthen the Cochrane compliance claim. Consider adding a note that direct ICTRP validation remains future work.

**1.5 Condition Term Standardization**

Some variation in condition term breadth remains:
- "type 2 diabetes" (specific)
- "cancer" (very broad)

A sensitivity analysis examining the impact of condition term specificity would be valuable.

---

### 2. STATISTICAL APPROACH (Score: 5/5)

#### Exemplary Elements

**2.1 Appropriate Confidence Intervals**

Wilson score intervals for proportions are the correct choice, avoiding the well-known problems of Wald intervals for proportions near 0 or 1.

**2.2 Comprehensive Metrics**

The manuscript appropriately reports:
- Recall (sensitivity) - primary outcome for systematic review searching
- Precision (PPV) - screening burden indicator
- F1 scores - balanced assessment
- NNS (Number Needed to Screen) - practical interpretation

**2.3 Honest Uncertainty Quantification**

Wide confidence intervals for smaller drug subsets are honestly reported rather than hidden. This enables readers to appropriately weight findings.

---

### 3. NOVELTY & CONTRIBUTION (Score: 4/5)

#### Novel Findings

**3.1 AREA Syntax for Oncology (Highly Novel)**

The finding that AREA syntax improves oncology drug recall by 14-21% is new and immediately actionable:

| Drug | Basic | AREA | Improvement |
|------|-------|------|-------------|
| Nivolumab | 50% | 71% | +21% |
| Trastuzumab | 46% | 66% | +20% |
| Pembrolizumab | 33% | 47% | +14% |

This addresses a known gap (combination therapy searching) with a practical solution.

**3.2 Generic Term Recall Ceiling**

Quantifying the insulin (12%) and metformin (35%) recall problem provides evidence for what was previously anecdotal. This guides reviewers on when to prioritize bibliographic databases.

**3.3 Brand Name Expansion Finding**

The demonstration that brand name expansion provides 0% benefit (CT.gov normalizes internally) saves systematic reviewers effort. This is a practical contribution.

#### Alignment with Literature

Findings appropriately align with Glanville et al. (2014) and Lefebvre et al. (2022), validating rather than contradicting established evidence. The 75% CT.gov-only recall is consistent with prior work.

---

### 4. PRESENTATION & REPRODUCIBILITY (Score: 4/5)

#### Strengths

**4.1 Code Availability**

Python scripts provided with clear documentation:
- `scripts/publication_ready_validation.py`
- `scripts/analyze_missed_trials.py`
- `scripts/rigorous_validation.py`

**4.2 Data Transparency**

Gold standard datasets provided:
- `data/cochrane_gold_standard.json`
- `data/enhanced_gold_standard.json`

**4.3 Visual Output**

Forest plots generated for each strategy (`output/forest_plot_*.html`).

#### Concerns (Minor)

**4.4 API Versioning**

CT.gov API may change over time. Consider:
- Archiving raw API responses
- Noting API version used
- Timestamping all validation runs

**4.5 Dependency Pinning**

`requirements.txt` should pin specific versions for full reproducibility.

---

### 5. LIMITATIONS HANDLING (Score: 5/5 - Exceptional)

The authors deserve commendation for the HONEST_FINDINGS.md document, which transparently addresses:

1. **Why 97% was misleading** - explicitly explains the circular validation problem
2. **What they cannot claim** - 95% recall not achievable with CT.gov alone
3. **Oncology limitations** - 30% recall honestly reported
4. **Generic term problems** - quantified and explained

This level of methodological honesty is rare and should be the standard for the field.

#### Key Honest Statements (Commended)

> "The 97% was only achievable because we used CT.gov's own metadata to search CT.gov. This is NOT how real systematic reviews work."

> "95% recall achievable? FALSE (max ~92% for best drugs)"

> "NEVER rely on CT.gov alone - supplement with other sources"

---

### 6. PRACTICAL APPLICABILITY (Score: 5/5)

#### Actionable Recommendations

The manuscript provides clear, stratified guidance:

**For Non-Oncology Drug Searches:**
- CT.gov intervention search achieves ~80% recall
- Combined strategy (Basic + AREA) recommended
- Supplement with PubMed/MEDLINE

**For Oncology Searches:**
- AREA syntax is CRITICAL
- Expect only ~30% recall from CT.gov alone
- Heavy reliance on bibliographic databases required

**For Generic Terms (insulin, metformin):**
- Expect low CT.gov recall (12-35%)
- Expand to specific drug names where possible
- Prioritize bibliographic database searching

---

## SPECIFIC REVISIONS REQUESTED

### Essential (Must Address)

1. **Clarify ICTRP Implementation**
   - Add note that PubMed ICTRP linkage was used as proxy
   - Acknowledge direct ICTRP validation as future work
   - Sentence suggestion: "We used PubMed ICTRP linkages as a proxy for direct ICTRP searching; prospective validation with the WHO ICTRP portal is planned."

2. **Add Condition Term Sensitivity Analysis**
   - Test impact of broad ("cancer") vs. specific ("non-small cell lung cancer") terms
   - Report in supplementary materials if space limited

3. **Archive API Responses**
   - Provide timestamped JSON responses in supplementary data
   - Note CT.gov API version (v2) explicitly

### Desirable (Should Consider)

4. **Pre-registration**
   - Consider retrospective registration on OSF/PROSPERO for future updates
   - Strengthens credibility for ongoing validation

5. **Forest Plot Enhancement**
   - Add therapeutic area subgroup forest plots
   - Consider funnel plot for publication bias assessment

6. **Comparison Table with Literature**
   - Add explicit table comparing your recall estimates to Glanville et al., Lefebvre et al.
   - Currently mentioned but not tabulated

---

## COMPARISON TO PRIOR RSM PUBLICATIONS

| Aspect | Glanville 2014 | Lefebvre 2022 | This Manuscript |
|--------|----------------|---------------|-----------------|
| Sample size | Variable | Review-based | 5,656 trials |
| Drug coverage | Limited | Broad | 76 drugs |
| AREA syntax | Not tested | Not tested | **Novel finding** |
| Generic terms | Noted issue | Noted issue | **Quantified** |
| Precision reported | Some | Some | Yes |
| Code available | No | No | **Yes** |

This manuscript advances the field beyond prior publications.

---

## PUBLICATION RECOMMENDATION

### Decision: **Accept with Minor Revisions**

**Rationale:**

1. **Methodological rigor** - Addressed circularity, appropriate statistics
2. **Novel contributions** - AREA syntax finding, generic term quantification
3. **Practical value** - Immediately actionable for systematic reviewers
4. **Transparency** - Exceptional honesty about limitations
5. **Reproducibility** - Code and data provided

### Conditions for Acceptance

1. Address ICTRP proxy clarification
2. Add API versioning documentation
3. Consider condition term sensitivity analysis (can be supplementary)

### Post-Acceptance Suggestions

- Consider submitting interactive forest plots as supplementary web material
- Future update with direct ICTRP validation would be valuable as a follow-up

---

## REVIEWER CONFIDENCE

**High** - The methodology is sound, findings align with established literature, and the honest characterization of limitations demonstrates scientific integrity.

---

## SUMMARY SCORES

| Criterion | Score | Notes |
|-----------|-------|-------|
| Methodology | 4/5 | Strong; minor ICTRP concern |
| Statistics | 5/5 | Appropriate throughout |
| Novelty | 4/5 | AREA syntax finding is new |
| Presentation | 4/5 | Good; archive API responses |
| Limitations | 5/5 | Exceptional transparency |
| Practical Value | 5/5 | Immediately actionable |
| **Overall** | **4.5/5** | Strong contribution |

---

## FINAL COMMENTS TO AUTHORS

This is excellent methodology research. The evolution from the circular 97% claim to the honest 75-80% recall characterization demonstrates scientific integrity that should be recognized.

Key contributions:
1. **AREA syntax for oncology** - This alone is worth publication
2. **Generic term quantification** - Valuable evidence for search planning
3. **Honest limitations** - Sets a standard for the field

The manuscript is suitable for Research Synthesis Methods and will be a valuable reference for systematic reviewers and information specialists.

---

**Signed:**
Methods Editor
Research Synthesis Methods
2026-01-26

*"Methodological transparency is the foundation of evidence synthesis credibility."*
