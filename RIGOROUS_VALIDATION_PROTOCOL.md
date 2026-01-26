# Rigorous Validation Protocol for CT.gov Search Strategies
## World-Class Methodology for Peer-Reviewed Publication

**Version:** 1.0
**Date:** 2026-01-25
**Status:** PROTOCOL (not yet executed)

---

## Problem Statement

### Current Limitation

Our v5.0 validation used CT.gov metadata (intervention names from the registry) to search CT.gov. This is **semi-circular**:

```
Current: NCT ID → Get intervention from CT.gov → Search CT.gov → Find trial
         ↑_________________________________↓ (circular)
```

### Rigorous Validation Requirement

```
Rigorous: Research question only → Search CT.gov → Compare to independent gold standard
          (no CT.gov metadata)      (blind search)   (externally identified trials)
```

---

## Protocol Design

### Phase 1: Gold Standard Construction

#### 1A. Cochrane Review Extraction

**Rationale:** Cochrane systematic reviews use exhaustive manual searching and are the gold standard for trial identification.

**Method:**
1. Download Cochrane Database of Systematic Reviews (CDSR)
2. Extract all included studies from recent reviews (2020-2026)
3. Identify NCT IDs from:
   - Study identifiers listed in review
   - CrossRef lookup of included publications
   - Manual matching where needed

**Target:** 50 Cochrane reviews × ~20 trials each = ~1000 trials

**Data extracted per review:**
```json
{
  "cochrane_id": "CD012345",
  "title": "Metformin for type 2 diabetes",
  "pico": {
    "population": "Adults with type 2 diabetes",
    "intervention": "Metformin",
    "comparator": "Placebo or other antidiabetic drugs",
    "outcome": "Glycemic control, mortality"
  },
  "search_date": "2024-03-15",
  "included_trials": [
    {"nct_id": "NCT00001234", "source": "CT.gov search"},
    {"nct_id": "NCT00005678", "source": "WHO ICTRP"},
    {"nct_id": "NCT00009012", "source": "Handsearch"}
  ],
  "search_strategy_used": "Cochrane CENTRAL + MEDLINE + CT.gov"
}
```

#### 1B. Published Meta-Analysis Extraction

**Rationale:** Meta-analyses have independently identified trial sets.

**Method:**
1. Search PubMed for recent meta-analyses (2022-2026)
2. Extract included RCTs with NCT IDs
3. Record the PICO for each meta-analysis

**Target:** 100 meta-analyses × ~10 trials = ~1000 trials

#### 1C. Prospective Review Registration

**Rationale:** Test on reviews BEFORE they identify trials (truly blind).

**Method:**
1. Partner with Cochrane review teams
2. Get PICO at protocol stage (before searching)
3. Run our search strategies
4. Compare to final included studies

**Target:** 10 prospective reviews

---

### Phase 2: Search Strategy Testing

#### 2A. Realistic Search Simulation

For each gold standard review, simulate a realistic search:

**Input (what a researcher would have):**
```json
{
  "population": "Adults with type 2 diabetes",
  "intervention": "Metformin",
  "comparator": "Placebo",
  "outcome": "HbA1c"
}
```

**Strategies to test:**

| Code | Strategy | CT.gov Query |
|------|----------|--------------|
| R1 | Intervention only | `query.intr=metformin` |
| R2 | Condition only | `query.cond=type 2 diabetes` |
| R3 | Intervention + Condition | `query.intr=metformin&query.cond=diabetes` |
| R4 | Intervention variants | `query.intr=metformin OR glucophage OR ...` |
| R5 | MeSH expanded | Use MeSH hierarchy for condition |
| R6 | Comprehensive | Union of R1-R5 |
| R7 | Cochrane filter | Replicate Cochrane's CT.gov strategy |

**Key difference from v5.0:** We use the PICO terms, not CT.gov's registered intervention names.

#### 2B. Intervention Name Expansion

Since we can't use CT.gov's intervention field directly, we need rules-based expansion:

```python
INTERVENTION_VARIANTS = {
    "metformin": [
        "metformin",
        "glucophage",
        "metformin hydrochloride",
        "dimethylbiguanide",
        # Generic names
        "metformina",  # Spanish
        "metformine",  # French
    ],
    "aspirin": [
        "aspirin",
        "acetylsalicylic acid",
        "ASA",
        "Bayer aspirin",
    ],
    # ... expand for all common drugs
}
```

**Data sources for expansion:**
- DrugBank database
- RxNorm
- WHO ATC codes
- ChEMBL

#### 2C. Condition Term Expansion

```python
CONDITION_EXPANSION = {
    "type 2 diabetes": [
        "type 2 diabetes",
        "type 2 diabetes mellitus",
        "T2DM",
        "non-insulin dependent diabetes",
        "NIDDM",
        "adult onset diabetes",
        # MeSH terms
        "Diabetes Mellitus, Type 2"
    ],
}
```

**Data sources:**
- MeSH hierarchy
- SNOMED-CT
- ICD-10/ICD-11

---

### Phase 3: Metrics and Analysis

#### 3A. Primary Outcome: Recall

```
Recall = Trials found by strategy / Trials in Cochrane review gold standard
```

**Why recall (sensitivity)?** For systematic reviews, missing trials is the critical failure mode.

#### 3B. Secondary Outcomes

| Metric | Formula | Importance |
|--------|---------|------------|
| Precision | TP / (TP + FP) | Workload for screening |
| NNS | 1 / Precision | Number needed to screen |
| F1 Score | 2 × (P × R) / (P + R) | Balance of P and R |
| Unique contribution | Trials found ONLY by this strategy | Value-add |

#### 3C. Subgroup Analyses

- By condition area (oncology, cardiology, etc.)
- By drug type (small molecule, biologic, device)
- By review date (older vs newer reviews)
- By geographic region of trials

#### 3D. Statistical Methods

- Wilson score 95% CIs for all proportions
- McNemar's test for paired strategy comparison
- Random effects meta-analysis across reviews
- Heterogeneity assessment (I², τ²)

---

### Phase 4: Comparison to Existing Methods

#### 4A. Cochrane Baseline

Compare our strategies to Cochrane's actual CT.gov search yield:

```
Our recall vs Cochrane's CT.gov-specific recall
```

#### 4B. Published Search Filters

Test against:
- Glanville et al. (2006) RCT filters
- Lefebvre et al. (2022) Cochrane Handbook strategies
- Wong et al. clinical query filters

#### 4C. Expert Searcher Benchmark

Partner with information specialists to:
1. Have experts search CT.gov for same reviews
2. Compare our automated strategy to expert searches

---

### Phase 5: Validation Levels

#### Level 1: Retrospective (n=100 reviews)
- Use completed Cochrane reviews
- Compare search results to included studies
- **Timeline:** 4 weeks

#### Level 2: Quasi-prospective (n=20 reviews)
- Use reviews where search is complete but not published
- Blind comparison
- **Timeline:** 3 months

#### Level 3: Fully Prospective (n=10 reviews)
- Partner with review teams at protocol stage
- Run our search before they search
- Compare after review completion
- **Timeline:** 12-18 months

---

## Implementation Plan

### Script: rigorous_validation.py

```python
#!/usr/bin/env python3
"""
Rigorous Validation Protocol Implementation
Tests search strategies using PICO input only (no CT.gov metadata)
"""

class RigorousValidator:
    """
    Validates CT.gov search strategies against Cochrane gold standard
    using only PICO information (not CT.gov metadata)
    """

    def __init__(self):
        self.drug_expander = DrugNameExpander()  # DrugBank, RxNorm
        self.condition_expander = ConditionExpander()  # MeSH, SNOMED
        self.ctgov_api = CTGovAPI()

    def search_from_pico(self, pico: dict) -> Set[str]:
        """
        Search CT.gov using only PICO information
        (the realistic scenario)
        """
        nct_ids = set()

        # Expand intervention names
        interventions = self.drug_expander.expand(pico["intervention"])

        # Expand condition names
        conditions = self.condition_expander.expand(pico["population"])

        # Strategy R1: Intervention variants
        for drug in interventions:
            results = self.ctgov_api.search(query_intr=drug)
            nct_ids.update(results)

        # Strategy R3: Intervention + Condition
        for drug in interventions:
            for condition in conditions:
                results = self.ctgov_api.search(
                    query_intr=drug,
                    query_cond=condition
                )
                nct_ids.update(results)

        return nct_ids

    def validate_against_cochrane(
        self,
        cochrane_reviews: List[CochraneReview]
    ) -> ValidationResults:
        """
        Validate search strategy against Cochrane gold standard
        """
        results = []

        for review in cochrane_reviews:
            # Get PICO (what researcher would have)
            pico = review.pico

            # Run our search (blind to gold standard)
            found = self.search_from_pico(pico)

            # Compare to Cochrane's included trials
            gold_standard = set(review.included_nct_ids)

            # Calculate metrics
            tp = len(found & gold_standard)
            fn = len(gold_standard - found)
            fp = len(found - gold_standard)

            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0

            results.append({
                "review_id": review.id,
                "gold_standard_size": len(gold_standard),
                "found": len(found),
                "true_positives": tp,
                "recall": recall,
                "precision": precision,
                "ci_95": wilson_ci(tp, tp + fn)
            })

        return ValidationResults(results)
```

---

## Data Sources Required

### 1. Cochrane Reviews Database

**Option A:** Cochrane Library API (requires license)
**Option B:** Scrape from Cochrane Library website
**Option C:** Partner with Cochrane directly

### 2. Drug Name Database

| Source | Access | Coverage |
|--------|--------|----------|
| DrugBank | API (free tier) | 15,000+ drugs |
| RxNorm | Free API | US drugs |
| WHO ATC | Free download | International |
| ChEMBL | Free API | Research compounds |

### 3. Condition Terminology

| Source | Access | Coverage |
|--------|--------|----------|
| MeSH | Free API | Medical terms |
| SNOMED-CT | Free (US) | Clinical terms |
| ICD-10 | Free | Diagnostic codes |
| UMLS | Free (registration) | Unified system |

---

## Expected Outcomes

### Hypothesis

We hypothesize that:

1. **Intervention search with name expansion** will achieve >90% recall
2. **Combined intervention + condition** will achieve >95% recall
3. **Our automated strategy** will match or exceed expert searcher performance

### Success Criteria

| Metric | Target | World-class |
|--------|--------|-------------|
| Recall | >90% | >95% |
| Precision | >5% | >10% |
| 95% CI width | <10% | <5% |
| Validation N | >500 | >1000 |

### Publication Target

If successful, this would be publishable in:
- Journal of Clinical Epidemiology
- Systematic Reviews
- Research Synthesis Methods
- Journal of Medical Internet Research

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 1. Data collection | 4 weeks | Cochrane gold standard (100 reviews) |
| 2. Drug/condition expansion | 2 weeks | Expansion dictionaries |
| 3. Strategy implementation | 2 weeks | rigorous_validation.py |
| 4. Level 1 validation | 2 weeks | Retrospective results |
| 5. Analysis & writing | 4 weeks | Draft manuscript |
| 6. Level 2 validation | 3 months | Quasi-prospective results |
| 7. Level 3 validation | 12 months | Prospective results |

**Total for publishable results:** 14 weeks (Level 1) to 18 months (Level 3)

---

## Comparison: Current vs Rigorous Validation

| Aspect | Current (v5.0) | Rigorous Protocol |
|--------|----------------|-------------------|
| Gold standard source | PubMed DataBank | Cochrane reviews |
| Search input | CT.gov metadata | PICO only |
| Circularity | Semi-circular | Non-circular |
| Drug names | From registry | Expanded from PICO |
| Condition terms | From registry | Expanded from PICO |
| Comparison | None | Cochrane, experts |
| Publication ready | No | Yes |
| Sample size | 100 | 500-1000 |

---

## Next Steps

1. **Immediate:** Build drug name expansion dictionary
2. **Week 1-2:** Extract Cochrane review gold standard
3. **Week 3-4:** Implement rigorous_validation.py
4. **Week 5-6:** Run Level 1 retrospective validation
5. **Week 7-8:** Analyze and document results

---

## Conclusion

This protocol addresses the key limitation of our current validation (circularity) by:

1. Using Cochrane reviews as truly independent gold standard
2. Starting from PICO only (not CT.gov metadata)
3. Expanding drug/condition names using external databases
4. Comparing to existing methods and expert performance

If our strategy achieves >95% recall in this rigorous validation, it would be a **novel contribution** worthy of publication and would establish it as one of the best CT.gov search strategies available.

---

*Protocol Version 1.0 - Ready for implementation*
