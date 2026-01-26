# Benchmark Report v2.0 - CT.gov Search Strategy Validation Project

**Date:** 2026-01-26
**Reviewer:** Independent Assessment
**Target Journal:** Research Synthesis Methods

---

## Executive Summary

### Current Project Score: 4.7/5.0

The project has advanced significantly with comprehensive implementations across all four phases of the roadmap. However, gaps remain compared to state-of-the-art methods in the literature.

---

## Current State Assessment

### Strengths (What's Working Well)

| Component | Assessment | Score |
|-----------|------------|-------|
| **Core Validation Framework** | Solid implementation with Wilson CIs, therapeutic area stratification | 5/5 |
| **API Versioning & Reproducibility** | SHA-256 hashing, session manifests | 5/5 |
| **Drug Synonym Expansion** | Comprehensive for insulin/metformin with INN/BAN/JAN | 4/5 |
| **ML Strategy Optimizer** | Novel gradient boosting for strategy recommendation | 4/5 |
| **Real-time Recall Estimation** | Practical utility for users | 4/5 |
| **Natural Language Parser** | PICO extraction from queries | 4/5 |
| **Non-drug Interventions** | Good intervention classifier | 4/5 |
| **Documentation** | Pre-registration, manuscript draft, methodology notes | 5/5 |

### Code Statistics

```
Total Python files: 103
Total lines of code: 54,717
New implementations (Phase 1-4): 8 scripts, 5,518 lines
```

---

## Gaps Identified from Literature Review

### 1. Missing: Validated RCT Search Filter Integration

**Literature Evidence:**
- Cochrane RCT Classifier achieves 99.64% recall ([Moberg & Gornitzki 2025](https://www.cambridge.org/core/journals/research-synthesis-methods/article/combining-search-filters-for-randomized-controlled-trials-with-the-cochrane-rct-classifier-in-covidence-a-methodological-validation-study/04406772BE26A14F77510D1D539E2765))
- Duggan filter has 99% sensitivity but 4% precision
- Current project doesn't leverage established filters

**Recommendation:** Integrate Cochrane-validated RCT filters for CT.gov searches

---

### 2. Missing: Cross-Registry Deduplication with Registry IDs

**Literature Evidence:**
- [Deduklick](https://systematicreviewsjournal.biomedcentral.com/articles/10.1186/s13643-022-02045-9) achieves 99.51% recall, 100% precision
- [ISPOR 2025](https://www.ispor.org/heor-resources/presentations-database/presentation-cti/ispor-2025/poster-session-3/evaluation-of-a-novel-approach-to-deduplication-of-trial-registry-records-in-systematic-reviews) shows new method using registry numbers identifies 280 duplicates vs 48 by automated methods
- Current project has basic deduplication but not registry-ID-based matching

**Recommendation:** Implement NCT/ISRCTN/EudraCT ID cross-matching algorithm

---

### 3. Missing: EU Clinical Trials Register (EUCTR) Integration

**Literature Evidence:**
- [BMJ Medicine 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10806997/) shows EUCTR has 44,181 trials with 23,000 results
- 77% of sampled EUCTR trials had results available
- EUCTR contains results unavailable elsewhere
- Cochrane Handbook should recommend EUCTR specifically

**Recommendation:** Add EUCTR/CTIS search adapter

---

### 4. Missing: ASReview/ML-Assisted Screening Integration

**Literature Evidence:**
- [ASReview LAB v2](https://www.cell.com/patterns/fulltext/S2666-3899(25)00166-7) reduces workload by 95%
- New ELAS models improve performance by 24.1%
- LLMs can reduce manual screening by >60% while maintaining >90% recall

**Recommendation:** Add ASReview export format and integration hooks

---

### 5. Missing: Unpublished Trial Detection Pipeline

**Literature Evidence:**
- [Baudard et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC4217330/) found 122 eligible trials in 47% of reviews that hadn't searched registries
- Only 11.3% of systematic reviews perform registry searches
- 56% of reviews not searching registries miss potentially relevant trials

**Recommendation:** Build unpublished trial detector comparing registry vs publication status

---

### 6. Missing: PRISMA-S Compliant Reporting

**Literature Evidence:**
- [PRISMA 2020](https://www.prisma-statement.org/) requires full search strategies for ALL databases
- PRISMA-S extension specifically for search reporting
- Current project doesn't auto-generate PRISMA-compliant output

**Recommendation:** Add PRISMA-S compliant search report generator

---

### 7. Missing: Relative Recall Benchmarking Framework

**Literature Evidence:**
- [RSM 2025 Guide](https://www.cambridge.org/core/journals/research-synthesis-methods/article/practical-guide-to-evaluating-sensitivity-of-literature-search-strings-for-systematic-reviews-using-relative-recall/BC6A8387DAB7539D7F96EBD5965ECC32) provides practical methodology
- Validation set approach with benchmark publications
- Current project uses gold standard but not formal relative recall framework

**Recommendation:** Implement formal relative recall calculation per RSM guidelines

---

### 8. Missing: Biomedical NLP for PICO Extraction

**Literature Evidence:**
- [EBM-NLP corpus](https://www.nature.com/articles/s41598-025-03979-5) has 4,993 annotated abstracts
- ScispaCy, BioBERT, ClinicalBERT available for medical NLP
- Current NL parser uses pattern matching, not trained models

**Recommendation:** Integrate ScispaCy/BioBERT for improved PICO extraction

---

## Prioritized Improvement Roadmap

### Priority 1: High Impact, Quick Wins (1-2 weeks)

| Improvement | Expected Impact | Effort |
|-------------|-----------------|--------|
| PRISMA-S Report Generator | Publication compliance | Low |
| Cross-Registry ID Deduplication | +5% unique trial identification | Medium |
| Unpublished Trial Detector | Novel contribution | Medium |
| Relative Recall Framework | Methodological rigor | Low |

### Priority 2: Significant Value (2-4 weeks)

| Improvement | Expected Impact | Effort |
|-------------|-----------------|--------|
| EUCTR/CTIS Integration | +10-15% European trials | Medium |
| ASReview Export Integration | Screening workflow | Medium |
| Cochrane RCT Filter Integration | +2-5% RCT identification | Low |

### Priority 3: Advanced Features (1-2 months)

| Improvement | Expected Impact | Effort |
|-------------|-----------------|--------|
| BioBERT/ScispaCy PICO Extraction | Improved NL parsing | High |
| Publication Bias Quantification | Methodological contribution | High |
| Web Application Dashboard | User accessibility | High |

---

## Specific Implementation Recommendations

### 1. PRISMA-S Report Generator

```python
# Generate PRISMA-S compliant search documentation
class PRISMASReporter:
    def generate_report(self, search_results):
        # Item 1: Database name
        # Item 2: Database interface
        # Item 3: Date of search
        # Item 4: Search strategy (full)
        # Item 5: Limits/filters
        # Item 6: Records retrieved
```

### 2. Cross-Registry ID Matcher

```python
# Match trials across registries using IDs
REGISTRY_PATTERNS = {
    'NCT': r'NCT\d{8}',
    'ISRCTN': r'ISRCTN\d{8}',
    'EudraCT': r'\d{4}-\d{6}-\d{2}',
    'ACTRN': r'ACTRN\d{14}',
    'ChiCTR': r'ChiCTR\d+',
    'JPRN': r'(UMIN|jRCT)\d+'
}
```

### 3. Unpublished Trial Detector

```python
# Identify completed but unpublished trials
def detect_unpublished(registry_record):
    status = registry_record['status']
    completion_date = registry_record['completion_date']
    has_publication = check_pubmed_linkage(registry_record['nct_id'])

    if status == 'Completed' and not has_publication:
        if days_since(completion_date) > 365:
            return 'likely_unpublished'
```

### 4. EUCTR Search Adapter

```python
# EU Clinical Trials Register integration
class EUCTRSearcher:
    def search(self, intervention, condition):
        # Web scraping with rate limiting
        # Export handling (20 record limit)
        # EudraCT ID extraction
```

---

## Revised Project Score After Improvements

| If Implemented | Projected Score |
|----------------|-----------------|
| Priority 1 only | 4.85/5.0 |
| Priority 1 + 2 | 4.95/5.0 |
| All priorities | 5.0/5.0 |

---

## Comparison with Literature Standards

| Criterion | Current | Literature Best | Gap |
|-----------|---------|-----------------|-----|
| Registries searched | CT.gov + ICTRP | CT.gov + ICTRP + EUCTR + ANZCTR + CENTRAL | Missing EUCTR |
| RCT filter validation | Not used | Cochrane 99.64% recall | Missing |
| Deduplication method | Basic | Registry-ID matching (99.5%) | Upgrade needed |
| PICO extraction | Pattern-based | BioBERT/ScispaCy | Upgrade available |
| Publication bias | Not addressed | Registry comparison | Missing |
| Reporting standard | Custom | PRISMA-S | Upgrade needed |

---

## Sources

1. [Cochrane RCT Classifier Validation](https://www.cambridge.org/core/journals/research-synthesis-methods/article/combining-search-filters-for-randomized-controlled-trials-with-the-cochrane-rct-classifier-in-covidence-a-methodological-validation-study/04406772BE26A14F77510D1D539E2765) - 99.64% recall
2. [Deduklick Algorithm](https://systematicreviewsjournal.biomedcentral.com/articles/10.1186/s13643-022-02045-9) - 99.51% recall, 100% precision
3. [EUCTR for Systematic Reviews](https://pmc.ncbi.nlm.nih.gov/articles/PMC10806997/) - BMJ Medicine 2024
4. [ASReview LAB v2](https://www.cell.com/patterns/fulltext/S2666-3899(25)00166-7) - 24.1% performance improvement
5. [Relative Recall Guide](https://www.cambridge.org/core/journals/research-synthesis-methods/article/practical-guide-to-evaluating-sensitivity-of-literature-search-strings-for-systematic-reviews-using-relative-recall/BC6A8387DAB7539D7F96EBD5965ECC32) - RSM 2025
6. [PRISMA 2020](https://www.prisma-statement.org/) - Updated reporting guidelines
7. [Registry Search Under-utilization](https://pmc.ncbi.nlm.nih.gov/articles/PMC4217330/) - 56% miss relevant trials
8. [NLP for Data Extraction](https://www.nature.com/articles/s41598-025-03979-5) - Deep learning for SLR

---

*Benchmark Report v2.0 - CT.gov Search Strategy Validation Project*
