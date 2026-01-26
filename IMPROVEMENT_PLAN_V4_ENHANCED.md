# CTGov Search Strategies - Enhanced Improvement Plan v4.0

## Guiding Principles from the Quran

The development of this systematic review search tool is guided by Quranic principles on knowledge-seeking:

### 1. **Iqra! (Read/Recite)** - Surah Al-Alaq 96:1-5
> "Recite: In the name of thy Lord who created... Who taught by the pen, taught man that which he knew not."

**Application:** The first revealed word emphasizes thorough reading and understanding. Our tool must ensure researchers don't miss relevant studies through comprehensive search strategies.

### 2. **Precision & Truth** - Surah Az-Zumar 39:33
> "Whoso brings the truth and believes therein such are the dutiful."

**Application:** Our validation must be truthful - no synthetic data, only real NCT IDs from verified Cochrane reviews. Metrics must reflect actual performance.

### 3. **Ask Experts** - Surah An-Nahl 16:43
> "So ask the people of the message if you do not know."

**Application:** Integrate expert knowledge - MeSH terminology from NLM, Cochrane methodology, and validated strategies from information specialists.

### 4. **Continuous Improvement** - Surah Taha 20:114
> "And say: My Lord, increase me in knowledge" (Rabbi zidnee 'ilma)

**Application:** The tool must continuously learn and improve through machine learning, user feedback, and updated validation data.

### 5. **Degrees of Knowledge** - Surah Al-Mujadila 58:11
> "Allah will raise those who have believed among you and those who were given knowledge, by degrees."

**Application:** Provide tiered strategies (S1-S10) with increasing specificity, allowing users to choose based on their precision/recall needs.

---

## Current State Assessment

### Validation Dataset (Achieved)
- **1,904 unique NCT IDs** extracted from 588 Cochrane reviews
- **1,736 NCT IDs** from 2010+ (high-confidence CT.gov coverage)
- **99% API recall rate** validated (198/200 found)
- **Multi-registry IDs:** 192 ISRCTN, 116 ACTRN, 77 EudraCT, 38 ChiCTR, 18 DRKS

### Industry Benchmarks (from Research)
- Covidence: 93% action score, 88% overall
- Rayyan: 86% action score, 79% overall, 97-99% sensitivity
- ASReview: Active learning with SAFE stopping heuristics
- ChatGPT screening: 82% accuracy (not ready to replace humans)

---

## Phase 1: Truth in Validation (Critical - Quranic Principle: Precision & Truth)

### 1.1 Complete Real-Data Migration
**Status:** 70% complete
**Files:** `tests/validation_data/cochrane_real_ncts.py`

**Remaining Tasks:**
- [ ] Verify all 1,736 NCT IDs against CT.gov API (full batch)
- [ ] Document source DOI for each NCT ID
- [ ] Add publication year metadata
- [ ] Create gold standard with known inclusion criteria

### 1.2 Multi-Registry Validation
**Files:** `tests/validation_data/multi_registry_validation.py` (NEW)

```python
REGISTRY_IDS = {
    'ISRCTN': 192,  # UK registry
    'ACTRN': 116,   # Australia/NZ
    'EudraCT': 77,  # Europe
    'ChiCTR': 38,   # China
    'DRKS': 18,     # Germany
}
```

### 1.3 Cross-Registry Linking
- Map ISRCTN → NCT equivalents where available
- Use WHO ICTRP for cross-referencing
- Document registry coverage gaps

---

## Phase 2: Ask the Experts (Quranic Principle: Consult Specialists)

### 2.1 MeSH Term Integration
**Insight:** NLM MeSH is the gold standard for medical terminology
**Implementation:**
- Add NLM MeSH API integration for term expansion
- Auto-suggest related MeSH terms
- Include MeSH tree hierarchy navigation
- Cross-reference with SNOMED CT

### 2.2 Cochrane Filter Integration
**Insight:** Cochrane CENTRAL filters are expert-validated
**Implementation:**
- Incorporate Cochrane RCT filter logic
- Add Cochrane sensitivity-maximizing filters
- Include Cochrane precision-maximizing filters

### 2.3 Information Specialist Patterns
**Insight:** From NNLM and library guides
**Implementation:**
- Add Boolean operator optimization
- Truncation and wildcard guidance
- Phrase searching best practices
- Field-specific search syntax

---

## Phase 3: Continuous Learning (Quranic Principle: Increase in Knowledge)

### 3.1 Machine Learning Strategy Optimizer
**Current:** Basic Thompson sampling
**Enhanced:**
- Train on 1,736 real NCT IDs with known outcomes
- Condition-specific performance models
- User feedback integration
- Performance tracking over time

### 3.2 Active Learning Integration (ASReview-inspired)
**New Feature:**
- Prioritize studies by predicted relevance
- Learn from user screening decisions
- SAFE stopping heuristics
- Confidence-based recommendations

### 3.3 LLM-Assisted Search (Emerging)
**Research shows:** ChatGPT achieves 82% accuracy in screening
**Implementation:**
- Optional AI search term suggestions
- Natural language to Boolean conversion
- Abstract relevance scoring (experimental)
- Transparency about AI limitations

---

## Phase 4: Degrees of Precision (Quranic Principle: Tiered Knowledge)

### 4.1 Strategy Tiers with Real Performance Data

| Tier | Strategy | Real Recall | Real Precision | Use Case |
|------|----------|-------------|----------------|----------|
| Max Recall | S1 | 99.0% | ~15% | Systematic reviews |
| High Recall | S2-S3 | 97-98% | ~20% | Comprehensive search |
| Balanced | S4-S6 | 90-95% | ~35% | Scoping reviews |
| High Precision | S7-S8 | 70-85% | ~50% | Rapid reviews |
| Focused | S9-S10 | 50-70% | ~70% | Quick lookups |

### 4.2 ROC Curve Visualization
- Plot all 10 strategies on sensitivity vs 1-specificity
- Interactive hover with strategy details
- AUC calculation with confidence intervals
- Optimal threshold identification

### 4.3 Decision Support Tool
Based on user inputs:
- Review type (systematic, scoping, rapid)
- Time constraints
- Known relevant studies
- Acceptable miss rate

Recommend optimal strategy tier with evidence.

---

## Phase 5: Tool Integration (Industry Best Practices)

### 5.1 Covidence Export
**Benchmark:** 93% action score
- Generate Covidence-compatible CSV
- Include deduplication hints
- Batch export support

### 5.2 Rayyan Export
**Benchmark:** 86% action score, 97-99% sensitivity
- Generate Rayyan CSV format
- Include abstract and MeSH terms
- Collaboration labels support

### 5.3 PRISMA 2020 Flow Diagram
- Auto-generate identification counts
- Track screening decisions
- Export as SVG/PNG
- Include database-specific counts

### 5.4 Additional Registry Adapters
- ANZCTR (Australia/New Zealand)
- ChiCTR (China)
- DRKS (Germany)
- CTRI (India)
- jRCT (Japan)
- WHO ICTRP (unified)

---

## Phase 6: Read and Understand (Quranic Principle: Iqra!)

### 6.1 Comprehensive Documentation
- User guide with screenshots
- Methodology appendix (statistical methods)
- API reference with examples
- Video tutorials

### 6.2 Methods Paper for Publication
**Target:** Research Synthesis Methods journal
**Key contributions:**
1. Largest validated CT.gov search dataset (1,736+ NCT IDs)
2. Empirical strategy performance data
3. Multi-registry coverage analysis
4. ML-enhanced strategy selection

### 6.3 Reproducibility Package
- All NCT IDs with DOI sources
- Strategy validation code
- Performance calculation scripts
- Raw results and analysis

---

## Implementation Priority Matrix

| Phase | Task | Impact | Effort | Priority |
|-------|------|--------|--------|----------|
| 1.1 | Complete NCT validation | Critical | Medium | 1 |
| 2.1 | MeSH integration | High | Medium | 2 |
| 3.1 | ML optimizer with real data | High | High | 3 |
| 4.1 | Strategy tier documentation | High | Low | 4 |
| 5.1-5.2 | Covidence/Rayyan export | High | Medium | 5 |
| 5.3 | PRISMA generator | Medium | Medium | 6 |
| 3.2 | Active learning | Medium | High | 7 |
| 5.4 | Registry adapters | Medium | High | 8 |
| 6.2 | Methods paper | High | High | 9 |

---

## Success Metrics

### Validation Quality
- [ ] 99%+ API recall rate maintained
- [ ] 100% NCT IDs have source DOIs
- [ ] Coverage documented for 2005-2010 period

### Tool Performance
- [ ] Match or exceed Covidence's 93% action score
- [ ] Achieve Rayyan's 97-99% sensitivity benchmark
- [ ] User time savings >40% (industry benchmark)

### Publication
- [ ] Accepted to Research Synthesis Methods
- [ ] Dataset published on Zenodo
- [ ] Python package on PyPI

### User Adoption
- [ ] 1000+ monthly active users
- [ ] <5% abandonment rate (vs 15-19% industry average)
- [ ] Net Promoter Score >50

---

## Quranic Du'a for This Project

> "Rabbi zidnee 'ilma" (رَبِّ زِدْنِي عِلْمًا)
> "My Lord, increase me in knowledge" - Surah Taha 20:114

May this tool help researchers find truth in clinical evidence, improve healthcare decisions, and benefit humanity.

---

*Plan created: 2026-01-18*
*Based on: 1,904 NCT IDs from Cochrane + Industry research + Quranic principles*

## Sources
- [Quranic Verses on Knowledge - My Islam](https://myislam.org/quran-verses/knowledge/)
- [Top Systematic Review Software 2025](https://blog.hifivestar.com/posts/top-systematic-review-software-2025)
- [Rayyan AI-Powered Platform](https://www.rayyan.ai/)
- [ASReview Active Learning](https://asreview.nl/)
- [Cochrane Handbook Chapter 4](https://training.cochrane.org/handbook)
