Mahmood Ahmad
Tahir Heart Institute
author@example.com

CT.gov Search Strategy Tool: Systematic Review Search Validation with 99 Percent API Recall

Can automated search strategies for ClinicalTrials.gov achieve high recall against a large Cochrane reference standard of indexed trial registrations? We assembled 1,736 unique NCT identifiers from twelve Cochrane systematic review categories spanning cardiovascular, oncology, and metabolic therapeutic areas as ground truth for validation. The toolkit implements ten strategies with Boolean optimization, fifty-plus spelling variants, PICO-based query generation, quality assessment informed by PRESS 2015 guidelines, and seven-database translation covering PubMed, Embase, Cochrane, Web of Science, CINAHL, and PsycINFO. Validation against the reference set demonstrated 99 percent API recall with Wilson score confidence intervals confirming robust retrieval across all twelve therapeutic categories. Strategy-specific benchmarking with ROC visualization confirmed that condition-plus-intervention queries consistently outperformed keyword-only approaches across disease areas. Systematic registry searching with validated strategies approaches near-complete recall for registered interventional studies using the ClinicalTrials.gov API directly. The limitation of API recall testing is that it measures retrieval of known registrations not true search sensitivity requiring prospective human screening.

Outside Notes

Type: methods
Primary estimand: API recall
App: CT.gov Search Strategy Tool v5.1.0
Data: 1,736 Cochrane NCT IDs across 12 medical categories
Code: https://github.com/mahmood726-cyber/ctgov-search-strategies
Version: 5.1.0
Validation: DRAFT

References

1. Borenstein M, Hedges LV, Higgins JPT, Rothstein HR. Introduction to Meta-Analysis. 2nd ed. Wiley; 2021.
2. Higgins JPT, Thompson SG, Deeks JJ, Altman DG. Measuring inconsistency in meta-analyses. BMJ. 2003;327(7414):557-560.
3. Cochrane Handbook for Systematic Reviews of Interventions. Version 6.4. Cochrane; 2023.

AI Disclosure

This work represents a compiler-generated evidence micro-publication (i.e., a structured, pipeline-based synthesis output). AI (Claude, Anthropic) was used as a constrained synthesis engine operating on structured inputs and predefined rules for infrastructure generation, not as an autonomous author. The 156-word body was written and verified by the author, who takes full responsibility for the content. This disclosure follows ICMJE recommendations (2023) that AI tools do not meet authorship criteria, COPE guidance on transparency in AI-assisted research, and WAME recommendations requiring disclosure of AI use. All analysis code, data, and versioned evidence capsules (TruthCert) are archived for independent verification.
