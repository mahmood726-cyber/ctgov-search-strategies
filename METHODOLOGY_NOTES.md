# Methodology Notes and Clarifications

## For Research Synthesis Methods Submission

This document provides explicit clarifications requested during editorial review.

---

## 1. ICTRP Implementation Clarification

### What We Implemented

**Current Implementation:** PubMed ICTRP linkage proxy

We used PubMed's DataBank extraction (SecondarySourceID field) which captures trials registered in WHO ICTRP partner registries when those trials have published results indexed in PubMed.

### Why This Approach

1. **WHO ICTRP does not have a public REST API** - The ICTRP website uses ASP.NET ViewState architecture that complicates automated searching
2. **PubMed linkage provides verified registrations** - These are trials that have been published and thus represent a subset of ICTRP content
3. **Reproducibility** - PubMed queries are reproducible; ICTRP web scraping is not

### Limitations of This Approach

- Only captures trials WITH PubMed-indexed publications
- May under-represent trials from non-English journals
- Does not capture unpublished/ongoing trials in ICTRP

### Future Work

Direct ICTRP validation via the `scripts/ictrp_search.py` module is available but was not used for the primary validation due to rate limiting and reproducibility concerns. We plan to conduct prospective validation with direct ICTRP portal searching in a follow-up study.

**Sentence for manuscript:**
> "We used PubMed ICTRP linkages as a proxy for direct ICTRP searching; prospective validation with the WHO ICTRP portal is planned."

---

## 2. API Versioning and Reproducibility

### Implementation

We have implemented comprehensive API versioning via `api_versioning.py`:

- **API Version:** ClinicalTrials.gov API v2
- **Base URL:** https://clinicaltrials.gov/api/v2
- **Response Archiving:** All API responses are archived with timestamps and SHA-256 hashes
- **Session Manifests:** Each validation run generates a manifest with environment details

### To Reproduce This Validation

```bash
# Run validation with archiving
python scripts/improved_recall_validation.py

# Check archived responses
ls output/api_archive/{session_id}/

# Verify response integrity
python -c "from api_versioning import *; m = APIVersioningManager(); print(m.get_session_manifest())"
```

### Archived Data Location

- Session manifests: `output/api_archive/{session_id}/manifest.json`
- Compressed responses: `output/api_archive/{session_id}/*.json.gz`
- Validation certificates: `output/validation_certificates/`

---

## 3. Condition Term Sensitivity Analysis

### Methodology

We tested broad vs. specific condition terms for 10 drugs across 5 therapeutic areas:

| Drug | Broad Term | Specific Term |
|------|------------|---------------|
| Pembrolizumab | cancer | non-small cell lung cancer |
| Semaglutide | diabetes | type 2 diabetes |
| Adalimumab | arthritis | rheumatoid arthritis |
| ... | ... | ... |

### Analysis Script

```bash
python scripts/condition_sensitivity_analysis.py
```

### Results Location

- JSON: `output/condition_sensitivity_analysis.json`
- Report: `output/CONDITION_SENSITIVITY_REPORT.md`

### Key Finding

Condition term specificity has **minimal impact on recall** when combined with intervention search. Both broad and specific terms achieve similar recall, but specific terms yield higher precision (fewer false positives).

**Recommendation:** Use specific condition terms for systematic reviews to reduce screening burden without sacrificing recall.

---

## 4. Literature Comparison

### Document Location

`LITERATURE_COMPARISON.md` provides explicit comparison tables with:
- Glanville et al. (2014)
- Lefebvre et al. (2022) - Cochrane Handbook
- Baudard et al. (2017)
- McGowan et al. (2016) - PRESS Guidelines

### Key Alignments

| Our Finding | Prior Literature | Alignment |
|-------------|------------------|-----------|
| 75% CT.gov-only recall | 73-84% (Glanville) | **Consistent** |
| Registry searching insufficient | Glanville, Lefebvre | **Confirmed** |
| AREA syntax +14-21% oncology | Not previously tested | **Novel** |

---

## 5. Statistical Methods

### Confidence Intervals

We use **Wilson score intervals** for all proportions because:
1. They are recommended for proportions (unlike Wald intervals)
2. They perform well near 0 and 1
3. They never produce negative intervals

### Implementation

```python
from scipy import stats

def wilson_ci(successes, trials, confidence=0.95):
    """Calculate Wilson score confidence interval."""
    if trials == 0:
        return (0, 0)

    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    p = successes / trials
    n = trials

    denominator = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denominator
    spread = z * ((p * (1 - p) / n + z**2 / (4*n**2)) ** 0.5) / denominator

    return (max(0, center - spread), min(1, center + spread))
```

### No Multiple Comparison Adjustment

We did not adjust for multiple comparisons across 76 drugs because:
1. Each drug represents an independent research question
2. We report all results transparently (no cherry-picking)
3. Readers can apply their own adjustments if desired

---

## 6. Gold Standard Construction

### Primary Reference Standard: PubMed DataBank Linkages

**Construction:**
1. Search PubMed for drug + condition
2. Extract NCT IDs from SecondarySourceID XML field
3. Verify each NCT ID exists in CT.gov API

**Scope:**
- Only published trials with PubMed-indexed results
- Only trials where authors included NCT ID (ICMJE compliance)
- Not representative of ALL registered trials

### Secondary Reference Standard: Cochrane Reviews

**Construction:**
1. Extract included studies from 39 Cochrane systematic reviews
2. Match to NCT IDs via trial registry IDs or CrossRef lookup
3. Verify against CT.gov API

**Scope:**
- Independently identified by Cochrane review teams
- Represents trials meeting rigorous inclusion criteria
- Limited to Cochrane-reviewed conditions

---

## 7. Code Availability

All code is available in this repository:

| File | Purpose |
|------|---------|
| `api_versioning.py` | API response archiving |
| `scripts/condition_sensitivity_analysis.py` | Condition term analysis |
| `scripts/improved_recall_validation.py` | Enhanced synonym validation |
| `scripts/publication_ready_validation.py` | Main validation script |
| `data/enhanced_drug_synonyms.json` | Drug synonym expansion |

### Running the Complete Validation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run main validation
python scripts/publication_ready_validation.py

# 3. Run condition sensitivity analysis
python scripts/condition_sensitivity_analysis.py

# 4. Run improved recall validation
python scripts/improved_recall_validation.py

# 5. Generate reports
python scripts/generate_forest_plot.py
```

---

## 8. Ethical Considerations

This research:
- Uses only publicly available data (CT.gov, PubMed)
- Does not involve human subjects
- Promotes systematic review rigor
- Makes code and data openly available

No IRB approval was required.

---

## 9. Funding and Conflicts of Interest

**Funding:** None

**Conflicts of Interest:** The authors declare no conflicts of interest related to this work.

---

## 10. Data Availability Statement

All data and code are available at:
- Repository: `ctgov-search-strategies`
- Gold standards: `data/enhanced_gold_standard.json`
- Results: `output/`
- Archived API responses: `output/api_archive/`

---

*Methodology notes prepared for Research Synthesis Methods submission*
*Version 1.0 - 2026-01-26*
