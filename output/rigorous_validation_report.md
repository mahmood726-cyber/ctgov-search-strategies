# Rigorous Validation Results

**Date:** 2026-01-25
**Gold Standard:** 39 systematic reviews
**Method:** PICO-only search (no CT.gov metadata)

## Summary Results

| Strategy | Recall | 95% CI | Precision | TP | FN | FP |
|----------|--------|--------|-----------|----|----|----| 
| R4-Comprehensive | 44.8% | 41.3%-48.4% | 0.5% | 343 | 422 | 64233 |
| R3-IntervCond | 41.4% | 38.0%-45.0% | 1.5% | 317 | 448 | 21532 |
| R5-RCTFiltered | 35.7% | 32.4%-39.1% | 1.6% | 273 | 492 | 16745 |
| R1-IntervOnly | 34.0% | 30.7%-37.4% | 1.3% | 260 | 505 | 19450 |
| R2-CondOnly | 10.8% | 8.8%-13.3% | 0.2% | 83 | 682 | 35419 |

## Key Findings

**Best Strategy:** R4-Comprehensive
**Best Recall:** 44.8% (95% CI: 41.3% - 48.4%)
**Target (95%) Met:** NO

## Methodology

This validation uses **PICO input only** - no CT.gov metadata.
Drug and condition names are expanded using external dictionaries.
This simulates a real systematic review search scenario.

## Interpretation

- **R1-IntervOnly:** Search intervention variants in CT.gov intervention field
- **R2-CondOnly:** Search condition variants in CT.gov condition field
- **R3-IntervCond:** Combined intervention + condition search
- **R4-Comprehensive:** Union of all search approaches
- **R5-RCTFiltered:** Intervention search with RCT allocation filter

---
*Rigorous Validation Protocol v1.0*