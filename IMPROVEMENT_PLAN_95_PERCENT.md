# Plan to Achieve 95% Recall
## Comprehensive Strategy to Close the Gap

**Baseline Status:** 75.4% recall (CT.gov Combined)
**Current Status:** 84.9% recall (Maximum Recall Strategy) ✓
**Target:** 95% recall
**Gap Remaining:** ~10 percentage points

---

## LATEST RESULTS - Maximum Recall Strategy (32 drugs)

**Overall: 84.9% (95% CI: 83.7%-86.0%)**

| Drug | Recall | Change from Baseline |
|------|--------|---------------------|
| Semaglutide | 94.5% | +2.8% |
| Liraglutide | 91.5% | +6.8% |
| Tocilizumab | 90.5% | +2.7% |
| Atezolizumab | 89.8% | +1.5% |
| Tiotropium | 89.5% | +0.0% |
| Nivolumab | 89.1% | +2.3% |
| Sofosbuvir | 88.8% | +3.0% |
| Tenofovir | 87.6% | +7.7% |
| Omalizumab | 87.0% | +3.7% |
| Rituximab | 87.0% | +4.6% |
| Pembrolizumab | 87.0% | +0.4% |
| Duloxetine | 87.0% | +0.0% |
| Fluticasone | 86.3% | +3.4% |
| Escitalopram | 86.1% | +1.4% |
| Apixaban | 85.7% | +8.6% |
| Dapagliflozin | 85.7% | +1.8% |
| Atorvastatin | 84.8% | +2.7% |
| Sertraline | 84.5% | +0.0% |
| Empagliflozin | 84.5% | +0.0% |
| Secukinumab | 84.2% | +0.0% |
| Trastuzumab | 83.9% | +4.7% |
| Rosuvastatin | 83.8% | +1.3% |
| Sitagliptin | 83.6% | +3.6% |
| Rivaroxaban | 80.9% | +4.3% |
| Bevacizumab | 79.8% | +5.2% |
| Etanercept | 79.3% | +1.1% |
| Infliximab | 79.2% | +5.6% |
| Quetiapine | 79.1% | +0.0% |
| **Adalimumab** | **78.0%** | +6.4% |
| **Metformin** | **76.5%** | +9.6% |
| **Remdesivir** | **71.9%** | +6.2% |
| **Insulin** | **68.8%** | **+43.1%** |

**Major improvements achieved:**
- Insulin: 25.7% → 68.8% (+43.1% - massive gain)
- Metformin: 67.0% → 76.5% (+9.6%)
- Tenofovir: 79.9% → 87.6% (+7.7%)
- Apixaban: 77.1% → 85.7% (+8.6%)

---

## DIAGNOSTIC FINDINGS - Why Trials Are Missed

### Targeted Improvement Analysis Results

| Drug | Missed Trials | Drug Found in Record | Drug NOT Found |
|------|---------------|---------------------|----------------|
| Insulin | 101 | 60% (in summary/desc/eligibility) | **40%** |
| Metformin | 47 | 65% (mostly eligibility) | **35%** |
| Adalimumab | 33 | 0% | **100%** |

### Key Finding: IRREDUCIBLE CEILING

**For adalimumab, 100% of missed trials have NO mention of adalimumab or any TNF inhibitor term anywhere in the CT.gov record.**

These trials are in the PubMed gold standard because:
1. Publications mention adalimumab as a comparator/background therapy
2. Post-hoc analyses mention adalimumab in results
3. Trials registered before drug name was finalized

**This represents a fundamental ceiling for CT.gov-based search - trials where the drug is mentioned in publications but not in trial registration cannot be found via CT.gov.**

### Insulin: Field Location Analysis (20 missed trials)
- `brief_summary`: 5 trials
- `detailed_desc`: 8 trials
- `eligibility`: 7 trials
- NOT in record: 8 trials

### Metformin: Field Location Analysis (20 missed trials)
- `eligibility`: 13 trials (mostly as exclusion criterion)
- `detailed_desc`: 3 trials
- NOT in record: 7 trials

---

## REALISTIC CEILING ASSESSMENT

Based on diagnostic analysis:

| Category | Estimated Ceiling | Reason |
|----------|-------------------|--------|
| Branded drugs (pembrolizumab, etc.) | ~95% | Research codes fill gaps |
| Generic drugs (metformin, insulin) | ~85% | Terminology variations |
| TNF inhibitors (adalimumab) | ~80% | High % with no CT.gov mention |
| Overall portfolio | ~88-90% | Weighted average |

**Conclusion: 95% overall recall is likely UNACHIEVABLE with CT.gov alone due to fundamental data limitations in trial registration.**

---

---

## Phase 1: Diagnose Why Trials Are Missed

### 1.1 Missed Trial Analysis

Before developing new strategies, we must understand WHY 25% of trials are missed.

**Hypothesis categories:**
1. **Field location** - Drug mentioned in non-searched fields
2. **Naming variations** - Different drug name forms/spellings
3. **Role in trial** - Comparator vs primary intervention
4. **Combination regimens** - Drug part of multi-drug protocol
5. **Registration timing** - Post-hoc registration issues

**Action:** Create analysis script to examine missed trials and categorize failure modes.

### 1.2 Diagnostic Script

```python
# Analyze WHY trials are missed
def analyze_missed_trials(gold_ncts, found_ncts, drug):
    missed = gold_ncts - found_ncts

    for nct_id in missed:
        # Fetch full trial record
        trial = fetch_full_trial(nct_id)

        # Check where drug appears
        locations = []
        if drug in trial['intervention_name']: locations.append('intervention_name')
        if drug in trial['brief_title']: locations.append('brief_title')
        if drug in trial['official_title']: locations.append('official_title')
        if drug in trial['description']: locations.append('description')
        if drug in trial['arm_description']: locations.append('arm_description')
        if drug in trial['eligibility']: locations.append('eligibility')
        if drug in trial['outcomes']: locations.append('outcomes')

        # Check drug role
        role = determine_drug_role(trial, drug)  # primary, comparator, combination

        # Log findings
        log_missed_trial(nct_id, locations, role)
```

---

## Phase 2: New Search Strategies to Test

### 2.1 AACT Database Full-Text Search (HIGH POTENTIAL)

**Why it might help:** AACT contains ALL CT.gov fields in normalized SQL tables. We can search across EVERY field, not just API-exposed ones.

```sql
-- Search ALL text fields in AACT
SELECT DISTINCT s.nct_id
FROM studies s
LEFT JOIN interventions i ON s.nct_id = i.nct_id
LEFT JOIN design_outcomes o ON s.nct_id = o.nct_id
LEFT JOIN eligibilities e ON s.nct_id = e.nct_id
LEFT JOIN brief_summaries bs ON s.nct_id = bs.nct_id
LEFT JOIN detailed_descriptions dd ON s.nct_id = dd.nct_id
WHERE
    LOWER(i.name) LIKE '%semaglutide%'
    OR LOWER(i.description) LIKE '%semaglutide%'
    OR LOWER(s.brief_title) LIKE '%semaglutide%'
    OR LOWER(s.official_title) LIKE '%semaglutide%'
    OR LOWER(bs.description) LIKE '%semaglutide%'
    OR LOWER(dd.description) LIKE '%semaglutide%'
    OR LOWER(o.measure) LIKE '%semaglutide%'
    OR LOWER(e.criteria) LIKE '%semaglutide%';
```

**Expected improvement:** +5-10% (access to fields not searchable via API)

### 2.2 Arm/Group Description Search

**Why it might help:** Many trials list drugs in arm descriptions but not as primary interventions.

```python
# CT.gov API doesn't expose arm descriptions well
# Use AACT instead
SELECT DISTINCT dg.nct_id
FROM design_groups dg
WHERE LOWER(dg.description) LIKE '%pembrolizumab%';
```

**Expected improvement:** +3-5% (especially for comparator arms)

### 2.3 Results Database Search

**Why it might help:** Completed trials have results sections with outcome measure text.

```python
# Search in reported outcomes
SELECT DISTINCT ro.nct_id
FROM reported_events re
JOIN outcome_measurements om ON re.nct_id = om.nct_id
WHERE LOWER(om.title) LIKE '%drug%'
   OR LOWER(om.description) LIKE '%drug%';
```

**Expected improvement:** +2-3% (completed trials only)

### 2.4 WHO ICTRP Direct Search (COCHRANE REQUIRED)

**Why it might help:** ICTRP indexes CT.gov differently and may surface trials with different metadata.

```python
# ICTRP search (no official API, need scraping or proxy)
def search_ictrp(drug, condition):
    # Search ICTRP web interface
    # Extract CT.gov IDs from results
    pass
```

**Expected improvement:** +3-5% (Glanville et al. reported 6-10%)

### 2.5 Secondary Registry Cross-Reference

**Why it might help:** Some trials registered in multiple registries have better metadata elsewhere.

**Registries to check:**
- EudraCT (European trials)
- ISRCTN
- ANZCTR (Australia/NZ)
- ChiCTR (China)
- JPRN (Japan)

**Expected improvement:** +2-4%

### 2.6 Semantic Drug Name Expansion

**Why it might help:** Some trials use chemical names, INN names, or research codes.

```python
DRUG_VARIANTS = {
    "semaglutide": [
        "semaglutide",
        "NN9535",          # Research code
        "GLP-1 analog",    # Class name
    ],
    "pembrolizumab": [
        "pembrolizumab",
        "MK-3475",         # Research code
        "lambrolizumab",   # Previous name
        "anti-PD-1",       # Mechanism
    ],
}
```

**Expected improvement:** +3-5% (for trials using research codes)

### 2.7 Combination Therapy Expansion (ONCOLOGY)

**Why it might help:** Oncology trials often list combinations, not individual drugs.

```python
# Search for common combinations
ONCOLOGY_COMBINATIONS = {
    "pembrolizumab": [
        "pembrolizumab + chemotherapy",
        "pembrolizumab + lenvatinib",
        "pembrolizumab carboplatin",
        "keytruda combination",
    ]
}
```

**Expected improvement:** +5-10% for oncology drugs

### 2.8 Sponsor + Condition Search (Fallback)

**Why it might help:** For industry drugs, searching by sponsor + condition may find trials not mentioning drug name.

```python
# Sponsor search for branded drugs
def search_by_sponsor_condition(sponsor, condition):
    query = f'AREA[LeadSponsorName]{sponsor} AND AREA[Condition]{condition}'
    # Then filter by Phase 2/3, Interventional
```

**Expected improvement:** +2-3%

### 2.9 Related Studies Network

**Why it might help:** CT.gov tracks related studies (parent/child protocols).

```python
# Get related studies for found trials
def expand_via_related(found_ncts):
    expanded = set(found_ncts)
    for nct in found_ncts:
        related = get_related_studies(nct)
        expanded.update(related)
    return expanded
```

**Expected improvement:** +1-2%

### 2.10 Machine Learning Classifier (ADVANCED)

**Why it might help:** Train a model to identify relevant trials from features.

```python
# Features for ML classifier
features = [
    'title_contains_drug',
    'intervention_contains_drug',
    'sponsor_match',
    'condition_match',
    'phase',
    'start_year',
    'similar_trial_network',
]

# Train on known relevant/irrelevant pairs
# Apply to candidate pool
```

**Expected improvement:** +3-5% (requires significant development)

---

## Phase 3: Implementation Priority

### Tier 1: High Impact, Low Effort (Do First)

| Strategy | Expected Gain | Effort | Priority |
|----------|---------------|--------|----------|
| AACT full-text search | +5-10% | Medium | **1** |
| Arm/group description | +3-5% | Low | **2** |
| Research code expansion | +3-5% | Low | **3** |

### Tier 2: Medium Impact, Medium Effort

| Strategy | Expected Gain | Effort | Priority |
|----------|---------------|--------|----------|
| WHO ICTRP direct | +3-5% | Medium | **4** |
| Combination therapy | +5-10% (oncology) | Medium | **5** |
| Results database | +2-3% | Low | **6** |

### Tier 3: Lower Impact or High Effort

| Strategy | Expected Gain | Effort | Priority |
|----------|---------------|--------|----------|
| Secondary registries | +2-4% | High | 7 |
| Sponsor + condition | +2-3% | Low | 8 |
| Related studies | +1-2% | Low | 9 |
| ML classifier | +3-5% | Very High | 10 |

---

## Phase 4: Realistic Projections

### Cumulative Improvement Estimate

| Starting Point | Strategy Added | Projected Recall |
|----------------|----------------|------------------|
| Baseline | CT.gov Combined | 75% |
| + AACT full-text | All fields searched | 82% |
| + Arm descriptions | Comparator drugs found | 85% |
| + Research codes | Early-phase trials | 88% |
| + WHO ICTRP | Cochrane compliant | 91% |
| + Combination therapy | Oncology improved | 93% |
| + Results database | Completed trials | 94% |
| + Related studies | Network expansion | **95%** |

### Confidence Assessment

| Target | Confidence | Notes |
|--------|------------|-------|
| 80% | **HIGH** | AACT alone should achieve this |
| 85% | **MEDIUM-HIGH** | Requires arm descriptions + codes |
| 90% | **MEDIUM** | Requires ICTRP + combinations |
| 95% | **MEDIUM-LOW** | Requires all strategies working |
| 100% | **IMPOSSIBLE** | Some trials will always be missed |

---

## Phase 5: Implementation Scripts

### 5.1 Missed Trial Analyzer

```python
# scripts/analyze_missed_trials.py
# Diagnoses WHY trials are missed
```

### 5.2 AACT Full-Text Searcher

```python
# scripts/aact_fulltext_search.py
# Searches all AACT fields via PostgreSQL
```

### 5.3 Research Code Expander

```python
# scripts/research_code_expansion.py
# Maps drugs to research codes, previous names
```

### 5.4 Combined 95% Strategy

```python
# scripts/combined_95_strategy.py
# Integrates all strategies for maximum recall
```

---

## Phase 6: Validation Protocol

### 6.1 Test Each Strategy Incrementally

```
For each new strategy:
1. Run on full drug set
2. Calculate incremental recall gain
3. Calculate precision impact
4. Decide if worth including
```

### 6.2 Final Validation

```
1. Run combined 95% strategy on 76 drugs
2. Report recall, precision, F1, NNS
3. Compare to 75% baseline
4. Document drug-specific improvements
```

---

## Timeline

| Week | Activities |
|------|------------|
| 1 | Missed trial analysis, AACT setup |
| 2 | AACT full-text implementation, testing |
| 3 | Research codes, arm descriptions |
| 4 | ICTRP integration, combination therapy |
| 5 | Full validation, documentation |

---

## Key Questions to Answer

1. **Why are 25% of trials missed?** - Diagnostic analysis required
2. **Is AACT access feasible?** - Need PostgreSQL connection
3. **What's the precision tradeoff?** - More recall = more noise?
4. **Is 95% achievable for ALL drugs?** - Or only some categories?

---

## Next Steps

1. **IMMEDIATE:** Build missed trial analyzer to diagnose failure modes
2. **THIS WEEK:** Set up AACT database connection
3. **NEXT WEEK:** Implement and test top 3 strategies
4. **ONGOING:** Iterate based on results

---

*Plan v1.0 - CT.gov Search Strategy Improvement Project*
*Target: 95% Recall*
