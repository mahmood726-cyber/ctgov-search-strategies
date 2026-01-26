# All Possible CT.gov Search Strategies
## Comprehensive Review from Literature and Practice

**Date:** 2026-01-25
**Sources:** Cochrane Handbook, Glanville et al., Lefebvre et al., NLM, WHO, Published Research

---

## Overview of Strategies Identified

| # | Strategy | Source | Our Status |
|---|----------|--------|------------|
| 1 | Basic intervention search | Standard | **Tested - 80% recall** |
| 2 | Basic condition search | Standard | **Tested - 11% recall** |
| 3 | Combined intervention + condition | Cochrane | **Tested - 45% recall** |
| 4 | AREA syntax field targeting | CT.gov API | To test |
| 5 | Truncation/wildcards | CT.gov | To test |
| 6 | Synonym expansion (automatic) | CT.gov built-in | Already active |
| 7 | RxNorm/UMLS drug expansion | NLM | To test |
| 8 | Brand name expansion | Common practice | **Tested - 0% improvement** |
| 9 | MeSH term expansion | Cochrane | To test |
| 10 | Sponsor/collaborator search | CT.gov fields | To test |
| 11 | Secondary ID linkage (PubMed SI field) | NLM | To test |
| 12 | WHO ICTRP cross-search | Cochrane mandatory | To test |
| 13 | AACT database SQL queries | CTTI | To test |
| 14 | Machine learning (SVM) | Lanera et al. | Not rules-based |
| 15 | Trial2rev crowdsourcing | Marshall et al. | Not rules-based |
| 16 | RCT allocation filter | CT.gov | **Tested - 36% recall** |
| 17 | Phase filter | CT.gov | To test |
| 18 | Status filter (Completed) | CT.gov | To test |
| 19 | Date range filter | CT.gov | To test |
| 20 | Title/acronym search | CT.gov | To test |
| 21 | Outcome measure search | CT.gov | To test |
| 22 | NCT ID reverse lookup from PubMed | DataBank linkage | To implement |

---

## Strategy Details

### 1. Basic Intervention Search (query.intr)
**Status: TESTED - 80% recall for specific drugs**

```
https://clinicaltrials.gov/api/v2/studies?query.intr=semaglutide
```

**Findings:**
- Best single strategy for specific drug names
- CT.gov automatically includes synonyms
- Brand names don't add value (already normalized)

---

### 2. Basic Condition Search (query.cond)
**Status: TESTED - 11% recall**

```
https://clinicaltrials.gov/api/v2/studies?query.cond=diabetes
```

**Findings:**
- Low recall due to terminology variation
- Condition field not consistently populated

---

### 3. Combined Intervention + Condition
**Status: TESTED - 45% recall (PICO), 80% (specific drugs)**

```
https://clinicaltrials.gov/api/v2/studies?query.intr=semaglutide&query.cond=diabetes
```

**Cochrane Recommendation:** Search both registries (CT.gov + WHO ICTRP) using intervention + condition

---

### 4. AREA Syntax Field Targeting
**Status: TO TEST**

The AREA syntax allows targeting specific database fields:

```
# Study type filter
query.term=AREA[StudyType]Interventional

# Allocation filter
query.term=AREA[DesignAllocation]Randomized

# Phase filter
query.term=AREA[Phase]Phase3

# Status filter
query.term=AREA[OverallStatus]Completed

# Date range
query.term=AREA[LastUpdatePostDate]RANGE[2020-01-01,MAX]

# Combined example
AREA[StudyType]Interventional AND AREA[DesignAllocation]Randomized
```

---

### 5. Truncation and Wildcards
**Status: TO TEST**

```
# Truncation (finds immun*, immunity, immunoglobulin)
immun*

# Note: Truncation DISABLES automatic synonym expansion
```

**Caution:** May reduce recall by disabling built-in synonyms

---

### 6. Automatic Synonym Expansion
**Status: ALREADY ACTIVE (default behavior)**

CT.gov automatically expands search terms using UMLS concepts:
- "tumor" finds "tumour"
- "heart attack" finds "myocardial infarction"

To DISABLE: `EXPANSION[Term]"exact phrase"`

---

### 7. RxNorm/UMLS Drug Expansion
**Status: TO TEST**

Use RxNorm API to get all drug variants:
```
https://rxnav.nlm.nih.gov/REST/rxcui.json?name=metformin
→ Returns all RxNorm CUIs for metformin
→ Then get related names/synonyms
```

This could help with:
- metformin → metformin hydrochloride, Glucophage, etc.
- insulin → insulin glargine, insulin lispro, etc.

---

### 8. Brand Name Expansion
**Status: TESTED - 0% IMPROVEMENT**

CT.gov normalizes to generic names internally. Adding brand names provides zero additional recall.

---

### 9. MeSH Term Expansion
**Status: TO TEST**

Use MeSH hierarchy to expand condition terms:
```
Diabetes Mellitus
├── Diabetes Mellitus, Type 1
├── Diabetes Mellitus, Type 2
├── Diabetes, Gestational
└── Prediabetic State
```

---

### 10. Sponsor/Collaborator Search
**Status: TO TEST**

```
https://clinicaltrials.gov/api/v2/studies?query.spons=Pfizer
```

Useful for:
- Finding all trials by a specific pharma company
- Searching by NIH institute (e.g., "NIMH")

---

### 11. Secondary ID Linkage (PubMed → CT.gov)
**Status: TO TEST - HIGH POTENTIAL**

PubMed stores NCT IDs in the Secondary Source ID [SI] field:
```
PubMed search: NCT00000419[SI]
```

**Reverse approach:**
1. Search PubMed for drug+condition
2. Extract NCT IDs from SecondarySourceID field
3. These are CONFIRMED linked trials

This is essentially what we did for gold standard building!

---

### 12. WHO ICTRP Cross-Search
**Status: TO TEST**

Cochrane MANDATES searching both CT.gov AND WHO ICTRP.

Research shows:
- ICTRP finds 6-10% additional CT.gov records not found by CT.gov search
- Different search engines = different results

```
https://trialsearch.who.int/
```

---

### 13. AACT Database SQL Queries
**Status: TO TEST**

Direct PostgreSQL access to normalized CT.gov data:
```sql
SELECT DISTINCT s.nct_id
FROM studies s
JOIN interventions i ON s.nct_id = i.nct_id
WHERE LOWER(i.name) LIKE '%semaglutide%'
AND s.study_type = 'Interventional';
```

Benefits:
- Full-text search across all fields
- Complex joins across tables
- No API rate limits

---

### 14-15. Machine Learning Approaches
**Status: NOT RULES-BASED (per user requirement)**

- Lanera et al. (2018): SVM classifier extending PubMed to CT.gov
- Trial2rev: Crowdsourcing + ML for systematic review updates
- RobotReviewer: ML for risk of bias assessment

---

### 16. RCT Allocation Filter
**Status: TESTED - 36% recall**

```
query.term=AREA[DesignAllocation]Randomized
```

Lower recall because many trials don't have allocation field populated.

---

### 17-19. Additional Filters
**Status: TO TEST**

```
# Phase filter
query.term=AREA[Phase]Phase2 OR AREA[Phase]Phase3

# Status filter (completed trials more likely to have results)
filter.overallStatus=COMPLETED

# Date range (post-2010 for better data quality)
query.term=AREA[StartDate]RANGE[2010-01-01,MAX]
```

---

### 20. Title/Acronym Search
**Status: TO TEST**

```
query.titles=EMPA-REG
```

Useful for finding specific named trials.

---

### 21. Outcome Measure Search
**Status: TO TEST**

Search within outcome measure text (only in results section).

---

### 22. NCT ID Reverse Lookup from PubMed
**Status: HIGH POTENTIAL**

**The Strategy:**
1. Search PubMed: `"drug name"[tiab] AND randomized controlled trial[pt]`
2. Extract DataBankList/SecondarySourceID containing NCT IDs
3. These NCT IDs are VERIFIED published trials

This is independent of CT.gov search and uses publication linkage.

---

## Literature-Recommended Best Practices

### From Cochrane Handbook (Lefebvre et al., 2022)
1. Search BOTH ClinicalTrials.gov AND WHO ICTRP
2. Use sensitive (broad) search approaches
3. Don't use RCT filters in registries (reduces recall)
4. Search basic interface with simple terms
5. Combine multiple search approaches

### From Glanville et al. (2014)
1. No single search approach identifies all trials
2. Basic interface searches are most sensitive
3. 84% of trials in reviews were NOT in registries
4. Registry searching supplements but doesn't replace database searching

### From NNLM Quick Guide (2024)
1. Start with condition/intervention search
2. Use Advanced Search for complex queries
3. Export results in CSV/JSON for processing
4. Check recruitment status
5. Use multiple search approaches

---

## Strategies We Should Test

### Priority 1: High Potential
| Strategy | Why |
|----------|-----|
| PubMed SI field extraction | Verified publication links |
| WHO ICTRP cross-search | Cochrane mandatory, +6-10% |
| RxNorm expansion for insulin/metformin | May fix generic term problem |
| AACT SQL full-text search | No API limits, all fields |

### Priority 2: Medium Potential
| Strategy | Why |
|----------|-----|
| MeSH hierarchy expansion | Structured vocabulary |
| Sponsor search | Alternative pathway |
| Title/acronym search | Named trials |
| Completed status filter | Higher quality data |

### Priority 3: Already Tested/Low Potential
| Strategy | Result |
|----------|--------|
| Brand name expansion | 0% improvement |
| Condition-only search | 11% recall |
| RCT allocation filter | Reduces recall |

---

## Key Insight from Literature

**Glanville et al. (2014):** "No single search approach was sensitive enough to identify all studies included in the reviews. Trials registers cannot yet be relied upon as the sole means to locate trials."

**Our finding aligns:** Even our best strategy (specific drug intervention search) achieves ~80% recall, not 95%+. This is consistent with published evidence.

---

## Sources

1. [Cochrane Handbook Chapter 4](https://training.cochrane.org/handbook/current/chapter-04)
2. [Glanville et al. (2014) - PMC4076126](https://pmc.ncbi.nlm.nih.gov/articles/PMC4076126/)
3. [Lanera et al. (2018) - PMID 29981872](https://pubmed.ncbi.nlm.nih.gov/29981872/)
4. [NNLM ClinicalTrials.gov Quick Guide](https://www.nnlm.gov/sites/default/files/2024-11/ClinicalTrialsgov%20Search%20Tools%20-%20Quick%20Guide%20for%20Systematic%20Reviewers.pdf)
5. [ClinicalTrials.gov API Documentation](https://clinicaltrials.gov/data-api/api)
6. [AACT Database](https://aact.ctti-clinicaltrials.org/)
7. [Trial2rev - PMC6951914](https://pmc.ncbi.nlm.nih.gov/articles/PMC6951914/)
8. [Linking CT.gov and PubMed - PMC3706420](https://pmc.ncbi.nlm.nih.gov/articles/PMC3706420/)
9. [WHO ICTRP](https://www.who.int/tools/clinical-trials-registry-platform)
10. [RxNorm](https://www.nlm.nih.gov/research/umls/rxnorm/index.html)
