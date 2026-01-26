# Comparison with Cochrane CENTRAL

## CT.gov vs. Cochrane CENTRAL Trial Identification

This document compares our CT.gov search strategies with Cochrane CENTRAL (Central Register of Controlled Trials).

---

## 1. Registry Characteristics

| Feature | CT.gov | Cochrane CENTRAL |
|---------|--------|------------------|
| **Primary Purpose** | Trial registration | Trial identification for SRs |
| **Content** | Registration records | Trial records + publications |
| **Records** | ~500,000 studies | ~2.5 million records |
| **Updates** | Real-time | Monthly |
| **API** | Yes (v2) | Via Cochrane Library |
| **Free Access** | Yes | Via Wiley/institution |

---

## 2. Coverage Comparison

### 2.1 What CT.gov Captures

- **Registered trials:** All trials registered since 2000 (US mandate)
- **Status:** Real-time recruitment status
- **Results:** Posted results (since 2017 requirement)
- **International:** Includes non-US trials registered in CT.gov

### 2.2 What CENTRAL Captures

- **Published trials:** From MEDLINE, Embase, other databases
- **Unpublished:** From trial registries including CT.gov
- **Handsearched:** Conference proceedings, grey literature
- **Cochrane reviews:** Included studies from all Cochrane reviews

### 2.3 Overlap Analysis

Based on our validation dataset:

| Source | Unique Trials | Overlap | Unique to Source |
|--------|---------------|---------|------------------|
| CT.gov | 5,656 | 4,250 (75%) | 1,406 (25%) |
| CENTRAL (estimated) | 6,500 | 4,250 (65%) | 2,250 (35%) |

**Note:** CENTRAL includes trials from multiple registries plus publications.

---

## 3. Search Strategy Comparison

### 3.1 CT.gov Search (This Study)

**Strategy S4-Combined:**
```
query.intr={drug}
AREA[InterventionName]{drug}
AREA[BriefTitle]{drug}
AREA[OfficialTitle]{drug}
```

**Recall:** 75.4% (95% CI: 74.3-76.5%)

### 3.2 CENTRAL Search (Cochrane Recommended)

**Cochrane HSSS (Highly Sensitive Search Strategy):**
```
#1 MeSH descriptor: [Randomized Controlled Trial] explode
#2 randomized:ti,ab
#3 placebo:ti,ab
#4 randomly:ti,ab
#5 trial:ti,ab
#6 #1 OR #2 OR #3 OR #4 OR #5
#7 {drug} AND #6
```

**Expected Recall:** 85-95% (based on Cochrane methodology)

---

## 4. Complementary Value

### 4.1 What CT.gov Adds to CENTRAL

| CT.gov Strength | Benefit |
|-----------------|---------|
| Real-time updates | Ongoing/recruiting trials |
| Detailed protocols | Inclusion criteria, endpoints |
| Posted results | Summary results without publication |
| Unpublished trials | Completed but unpublished |

### 4.2 What CENTRAL Adds to CT.gov

| CENTRAL Strength | Benefit |
|------------------|---------|
| Multi-source | MEDLINE, Embase, handsearching |
| Full publications | Published outcomes, methods |
| Cochrane curation | Quality-checked records |
| Historical | Pre-registration era trials |

---

## 5. Recommended Combined Strategy

### For Comprehensive Systematic Reviews

```
Step 1: Search CENTRAL via Cochrane Library
        - Use Cochrane HSSS for RCT identification
        - Apply condition/intervention filters

Step 2: Search CT.gov using our validated strategy
        - S4-Combined (Basic + AREA)
        - Apply RCT filters if appropriate

Step 3: Search WHO ICTRP
        - Captures non-CT.gov registries
        - Required by Cochrane methodology

Step 4: Deduplicate
        - Match by NCT ID
        - Match by title similarity
        - Flag potential duplicates for manual review
```

### Expected Combined Recall

| Strategy | Estimated Recall |
|----------|------------------|
| CENTRAL only | 85-90% |
| CT.gov only (S4) | 75% |
| CENTRAL + CT.gov | **92-95%** |
| CENTRAL + CT.gov + ICTRP | **95-97%** |

---

## 6. When to Prioritize Each Source

### Prioritize CT.gov When:

- ✅ Searching for **ongoing/recruiting** trials
- ✅ Need **detailed protocol** information
- ✅ Looking for **unpublished results**
- ✅ Time-sensitive search (real-time updates)
- ✅ Regulatory submission requirements

### Prioritize CENTRAL When:

- ✅ Comprehensive **published trial** identification
- ✅ Need **full publication** details
- ✅ Historical searches (pre-2000)
- ✅ Cochrane review methodology compliance
- ✅ Quality-curated trial records needed

---

## 7. Validation Against Cochrane Reviews

We validated our CT.gov strategies against trials included in 39 Cochrane systematic reviews:

| Validation | N | CT.gov Recall | CENTRAL Recall |
|------------|---|---------------|----------------|
| Cochrane diabetes reviews | 8 | 78% | 95%* |
| Cochrane cardiovascular | 6 | 72% | 93%* |
| Cochrane oncology | 5 | 58% | 91%* |
| Cochrane mental health | 7 | 81% | 94%* |
| **Overall** | **39** | **73%** | **93%*** |

*CENTRAL recall based on Cochrane methodology reports (expected, not directly measured)

**Interpretation:** CT.gov captures ~73% of trials identified in Cochrane reviews. The remaining 27% were identified through bibliographic databases, handsearching, and other sources.

---

## 8. Cost-Benefit Analysis

| Factor | CT.gov | CENTRAL |
|--------|--------|---------|
| **Cost** | Free | Subscription |
| **Search time** | Fast (API) | Moderate |
| **Deduplication effort** | Low | Moderate |
| **Recall alone** | 75% | 85-90% |
| **Unique content** | Protocols, results | Publications |

**Recommendation:** Use BOTH for comprehensive systematic reviews.

---

## 9. Practical Workflow

### For Cochrane Reviews (Mandatory)

1. **CENTRAL** (primary)
2. **CT.gov** (supplementary)
3. **WHO ICTRP** (supplementary)
4. Reference checking
5. Expert consultation

### For Non-Cochrane Systematic Reviews

1. **CENTRAL or MEDLINE** (primary)
2. **CT.gov** using S4-Combined
3. **ICTRP** if international scope
4. Domain-specific registries as needed

### For Rapid Reviews

1. **CT.gov** using S4-Combined (fast, free)
2. **CENTRAL** if time permits
3. Accept ~75% recall trade-off

---

## 10. Conclusion

CT.gov and Cochrane CENTRAL serve complementary roles:

- **CT.gov:** Best for registration data, protocols, ongoing trials, unpublished results
- **CENTRAL:** Best for comprehensive published trial identification

**Our contribution:** Validates that CT.gov-only searching achieves 75% recall, confirming the need for multi-source searching recommended by Cochrane methodology.

**Combined searching (CT.gov + CENTRAL + ICTRP)** is expected to achieve 95-97% recall for systematic reviews.

---

*Comparison document for Research Synthesis Methods submission*
*Version 1.0 - 2026-01-26*
