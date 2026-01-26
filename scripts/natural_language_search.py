#!/usr/bin/env python3
"""
Natural Language Search Interface
=================================

Accept research questions in natural language and translate to optimized
registry searches.

Example:
    User: "What RCTs have tested GLP-1 agonists for weight loss in adults with obesity?"

    System: Parses to PICO, expands synonyms, executes multi-registry search,
            returns structured results with recall estimates

Author: CT.gov Search Strategy Validation Project
Version: 1.0.0
Date: 2026-01-26
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime
from enum import Enum


class StudyDesign(Enum):
    """Study design filters."""
    RCT = "rct"
    CONTROLLED_TRIAL = "controlled_trial"
    ALL_INTERVENTIONAL = "all_interventional"
    OBSERVATIONAL = "observational"
    ANY = "any"


@dataclass
class ParsedPICO:
    """PICO elements parsed from natural language."""
    population: Optional[str] = None
    intervention: Optional[str] = None
    comparator: Optional[str] = None
    outcome: Optional[str] = None

    # Additional parsed elements
    age_group: Optional[str] = None  # adults, children, elderly
    study_design: StudyDesign = StudyDesign.ANY
    time_frame: Optional[str] = None

    # Confidence scores
    confidence: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'population': self.population,
            'intervention': self.intervention,
            'comparator': self.comparator,
            'outcome': self.outcome,
            'age_group': self.age_group,
            'study_design': self.study_design.value,
            'time_frame': self.time_frame,
            'confidence': self.confidence
        }


@dataclass
class ExpandedTerms:
    """Expanded search terms with synonyms."""
    original_term: str
    synonyms: List[str]
    mesh_terms: List[str]
    brand_names: List[str]
    abbreviations: List[str]
    drug_class: Optional[str]

    def all_terms(self) -> List[str]:
        """Get all search terms."""
        terms = [self.original_term] + self.synonyms + self.mesh_terms
        terms += self.brand_names + self.abbreviations
        return list(set(terms))


@dataclass
class SearchResult:
    """Search result from a registry."""
    registry: str
    nct_id: str
    title: str
    status: str
    phase: Optional[str]
    enrollment: Optional[int]
    start_date: Optional[str]
    conditions: List[str]
    interventions: List[str]


@dataclass
class UnifiedSearchResults:
    """Unified results from multi-registry search."""
    query: str
    parsed_pico: ParsedPICO
    expanded_terms: Dict[str, ExpandedTerms]

    # Results by registry
    ctgov_results: List[SearchResult]
    ictrp_results: List[SearchResult]
    other_registry_results: Dict[str, List[SearchResult]]

    # Metrics
    total_unique: int
    total_duplicates: int
    recall_estimate: float
    recall_ci: Tuple[float, float]

    # Metadata
    search_timestamp: str
    api_versions: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'query': self.query,
            'parsed_pico': self.parsed_pico.to_dict(),
            'expanded_terms': {k: v.all_terms() for k, v in self.expanded_terms.items()},
            'results': {
                'ctgov': len(self.ctgov_results),
                'ictrp': len(self.ictrp_results),
                'other': {k: len(v) for k, v in self.other_registry_results.items()}
            },
            'total_unique': self.total_unique,
            'total_duplicates': self.total_duplicates,
            'recall_estimate': round(self.recall_estimate, 3),
            'recall_ci': [round(x, 3) for x in self.recall_ci],
            'search_timestamp': self.search_timestamp,
            'api_versions': self.api_versions
        }


class NaturalLanguageParser:
    """
    Parse natural language research questions into structured PICO.

    Uses pattern matching and heuristics to extract:
    - Population (who)
    - Intervention (what)
    - Comparator (vs what)
    - Outcome (effect on what)
    """

    # Patterns for study design
    STUDY_DESIGN_PATTERNS = {
        StudyDesign.RCT: [
            r'\bRCT[s]?\b', r'randomized controlled trial[s]?',
            r'randomised controlled trial[s]?', r'randomized trial[s]?'
        ],
        StudyDesign.CONTROLLED_TRIAL: [
            r'controlled trial[s]?', r'clinical trial[s]?'
        ],
        StudyDesign.OBSERVATIONAL: [
            r'observational', r'cohort', r'case-control'
        ]
    }

    # Population age groups
    AGE_PATTERNS = {
        'adults': [r'\badult[s]?\b', r'\bgrown-?up[s]?\b', r'18\s*(?:years?|y\.?o\.?)'],
        'children': [r'\bchild(?:ren)?\b', r'\bpediatric\b', r'\bpaediatric\b',
                    r'\binfant[s]?\b', r'\badolescent[s]?\b'],
        'elderly': [r'\belderly\b', r'\bolder adult[s]?\b', r'\bsenior[s]?\b',
                   r'65\s*(?:years?|y\.?o\.?)\s*(?:and older|or older|\+)']
    }

    # Intervention triggers
    INTERVENTION_TRIGGERS = [
        r'(?:have )?tested', r'evaluating', r'comparing', r'using',
        r'treatment with', r'therapy with', r'receiving', r'given',
        r'administered', r'treated with'
    ]

    # Outcome triggers
    OUTCOME_TRIGGERS = [
        r'for\s+(?:treating|improving|reducing|preventing)',
        r'effect[s]?\s+on', r'impact\s+on', r'efficacy\s+(?:for|in|on)',
        r'effectiveness\s+(?:for|in|on)', r'to\s+(?:treat|improve|reduce|prevent)'
    ]

    # Condition/population triggers
    POPULATION_TRIGGERS = [
        r'(?:patient[s]?\s+)?with', r'(?:people|individuals)\s+(?:with|who have)',
        r'diagnosed\s+with', r'suffering\s+from', r'in\s+(?:patient[s]?\s+)?with'
    ]

    def __init__(self):
        self.drug_database = self._load_drug_database()

    def _load_drug_database(self) -> Dict[str, List[str]]:
        """Load known drugs and their classes."""
        return {
            # GLP-1 agonists
            'glp-1': ['semaglutide', 'liraglutide', 'dulaglutide', 'exenatide',
                     'tirzepatide', 'lixisenatide'],
            'sglt2': ['empagliflozin', 'dapagliflozin', 'canagliflozin', 'ertugliflozin'],
            'dpp-4': ['sitagliptin', 'saxagliptin', 'linagliptin', 'alogliptin'],
            'pd-1': ['pembrolizumab', 'nivolumab', 'cemiplimab'],
            'pd-l1': ['atezolizumab', 'durvalumab', 'avelumab'],
            'tnf': ['adalimumab', 'infliximab', 'etanercept', 'golimumab', 'certolizumab'],
            'ssri': ['sertraline', 'fluoxetine', 'paroxetine', 'citalopram', 'escitalopram']
        }

    def parse(self, query: str) -> ParsedPICO:
        """
        Parse natural language query into PICO elements.

        Args:
            query: Natural language research question

        Returns:
            ParsedPICO with extracted elements
        """
        query_lower = query.lower()
        pico = ParsedPICO()
        pico.confidence = {}

        # Extract study design
        pico.study_design = self._extract_study_design(query_lower)
        pico.confidence['study_design'] = 0.9 if pico.study_design != StudyDesign.ANY else 0.3

        # Extract age group
        pico.age_group = self._extract_age_group(query_lower)
        pico.confidence['age_group'] = 0.8 if pico.age_group else 0.0

        # Extract intervention (drugs, procedures)
        pico.intervention = self._extract_intervention(query_lower)
        pico.confidence['intervention'] = 0.9 if pico.intervention else 0.3

        # Extract population/condition
        pico.population = self._extract_population(query_lower, pico.intervention)
        pico.confidence['population'] = 0.8 if pico.population else 0.3

        # Extract outcome
        pico.outcome = self._extract_outcome(query_lower, pico.population)
        pico.confidence['outcome'] = 0.7 if pico.outcome else 0.2

        return pico

    def _extract_study_design(self, query: str) -> StudyDesign:
        """Extract study design from query."""
        for design, patterns in self.STUDY_DESIGN_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    return design
        return StudyDesign.ANY

    def _extract_age_group(self, query: str) -> Optional[str]:
        """Extract age group from query."""
        for group, patterns in self.AGE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    return group
        return None

    def _extract_intervention(self, query: str) -> Optional[str]:
        """Extract intervention from query."""
        # Check for drug class mentions
        for drug_class, drugs in self.drug_database.items():
            class_pattern = rf'\b{drug_class}[- ]?(?:agonist|inhibitor|blocker)?s?\b'
            if re.search(class_pattern, query, re.IGNORECASE):
                return drug_class

            # Check for specific drugs
            for drug in drugs:
                if drug.lower() in query:
                    return drug

        # Extract intervention after trigger words
        for trigger in self.INTERVENTION_TRIGGERS:
            match = re.search(rf'{trigger}\s+(\w+(?:\s+\w+)?)', query, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_population(self, query: str, intervention: str = None) -> Optional[str]:
        """Extract population/condition from query."""
        # Common conditions
        conditions = [
            'diabetes', 'obesity', 'hypertension', 'heart failure',
            'cancer', 'depression', 'anxiety', 'asthma', 'copd',
            'arthritis', 'multiple sclerosis', 'parkinson', 'alzheimer'
        ]

        for condition in conditions:
            if condition in query:
                return condition

        # Try pattern extraction
        for trigger in self.POPULATION_TRIGGERS:
            match = re.search(rf'{trigger}\s+(\w+(?:\s+\w+)?)', query, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_outcome(self, query: str, population: str = None) -> Optional[str]:
        """Extract outcome from query."""
        outcome_keywords = [
            'weight loss', 'glycemic control', 'blood pressure', 'mortality',
            'survival', 'response', 'remission', 'improvement', 'reduction',
            'prevention', 'incidence'
        ]

        for outcome in outcome_keywords:
            if outcome in query:
                return outcome

        # Pattern-based extraction
        for trigger in self.OUTCOME_TRIGGERS:
            match = re.search(rf'{trigger}\s+(\w+(?:\s+\w+)?)', query, re.IGNORECASE)
            if match:
                return match.group(1)

        return None


class SynonymExpander:
    """
    Expand search terms with synonyms, MeSH terms, and brand names.
    """

    # Drug synonym database
    DRUG_SYNONYMS = {
        'semaglutide': {
            'synonyms': ['semaglutide'],
            'brand_names': ['Ozempic', 'Wegovy', 'Rybelsus'],
            'mesh_terms': ['semaglutide'],
            'class': 'GLP-1 agonist'
        },
        'liraglutide': {
            'synonyms': ['liraglutide'],
            'brand_names': ['Victoza', 'Saxenda'],
            'mesh_terms': ['liraglutide'],
            'class': 'GLP-1 agonist'
        },
        'glp-1': {
            'synonyms': ['GLP-1 agonist', 'GLP-1 receptor agonist',
                        'glucagon-like peptide-1', 'incretin mimetic'],
            'brand_names': [],
            'mesh_terms': ['Glucagon-Like Peptide-1 Receptor Agonists'],
            'class': 'GLP-1 agonist'
        },
        'pembrolizumab': {
            'synonyms': ['pembrolizumab', 'MK-3475'],
            'brand_names': ['Keytruda'],
            'mesh_terms': ['pembrolizumab'],
            'class': 'PD-1 inhibitor'
        },
        'adalimumab': {
            'synonyms': ['adalimumab', 'D2E7'],
            'brand_names': ['Humira', 'Hadlima', 'Hyrimoz', 'Cyltezo'],
            'mesh_terms': ['adalimumab'],
            'class': 'TNF inhibitor'
        }
    }

    # Condition synonym database
    CONDITION_SYNONYMS = {
        'obesity': {
            'synonyms': ['obesity', 'obese', 'overweight', 'excess weight'],
            'mesh_terms': ['Obesity', 'Overweight'],
            'icd_codes': ['E66']
        },
        'diabetes': {
            'synonyms': ['diabetes mellitus', 'diabetes', 'diabetic',
                        'type 2 diabetes', 'T2DM', 'T2D'],
            'mesh_terms': ['Diabetes Mellitus', 'Diabetes Mellitus, Type 2'],
            'icd_codes': ['E11']
        },
        'depression': {
            'synonyms': ['depression', 'major depressive disorder', 'MDD',
                        'depressive disorder', 'clinical depression'],
            'mesh_terms': ['Depressive Disorder', 'Depressive Disorder, Major'],
            'icd_codes': ['F32', 'F33']
        }
    }

    def expand(self, term: str, term_type: str = 'drug') -> ExpandedTerms:
        """
        Expand a term with synonyms.

        Args:
            term: Original search term
            term_type: 'drug' or 'condition'

        Returns:
            ExpandedTerms with all variations
        """
        term_lower = term.lower()

        if term_type == 'drug' and term_lower in self.DRUG_SYNONYMS:
            data = self.DRUG_SYNONYMS[term_lower]
            return ExpandedTerms(
                original_term=term,
                synonyms=data['synonyms'],
                mesh_terms=data['mesh_terms'],
                brand_names=data['brand_names'],
                abbreviations=[],
                drug_class=data.get('class')
            )

        if term_type == 'condition' and term_lower in self.CONDITION_SYNONYMS:
            data = self.CONDITION_SYNONYMS[term_lower]
            return ExpandedTerms(
                original_term=term,
                synonyms=data['synonyms'],
                mesh_terms=data['mesh_terms'],
                brand_names=[],
                abbreviations=data.get('icd_codes', []),
                drug_class=None
            )

        # Default: return term as-is
        return ExpandedTerms(
            original_term=term,
            synonyms=[term],
            mesh_terms=[],
            brand_names=[],
            abbreviations=[],
            drug_class=None
        )


class MultiRegistrySearcher:
    """
    Execute searches across multiple trial registries.

    Supports:
    - ClinicalTrials.gov (CT.gov)
    - WHO ICTRP
    - EU-CTR
    - ANZCTR
    """

    def __init__(self):
        self.api_versions = {
            'ctgov': 'v2.0.0',
            'ictrp': '2024',
            'euctr': '2023',
            'anzctr': '2024'
        }

    def build_ctgov_query(self, pico: ParsedPICO,
                         expanded_terms: Dict[str, ExpandedTerms]) -> str:
        """Build CT.gov API query from parsed PICO."""
        query_parts = []

        # Intervention query
        if pico.intervention and pico.intervention in expanded_terms:
            terms = expanded_terms[pico.intervention].all_terms()
            intr_query = ' OR '.join(f'"{t}"' for t in terms[:10])
            query_parts.append(f"query.intr=({intr_query})")

        # Condition query
        if pico.population and pico.population in expanded_terms:
            terms = expanded_terms[pico.population].all_terms()
            cond_query = ' OR '.join(f'"{t}"' for t in terms[:10])
            query_parts.append(f"query.cond=({cond_query})")

        # Study type filter
        query_parts.append("query.studyType=Interventional")

        # Phase filter for RCTs
        if pico.study_design in [StudyDesign.RCT, StudyDesign.CONTROLLED_TRIAL]:
            query_parts.append("filter.phase=Phase 2,Phase 3,Phase 4")

        return "&".join(query_parts)

    def search_ctgov(self, query: str) -> List[SearchResult]:
        """
        Search ClinicalTrials.gov.

        Note: This is a mock implementation. Real implementation would
        call the CT.gov API.
        """
        # Mock results for demonstration
        return []

    def search_ictrp(self, pico: ParsedPICO,
                     expanded_terms: Dict[str, ExpandedTerms]) -> List[SearchResult]:
        """
        Search WHO ICTRP.

        Note: This is a mock implementation.
        """
        return []

    def deduplicate_results(self, all_results: List[SearchResult]) -> Tuple[List[SearchResult], int]:
        """
        Deduplicate results across registries.

        Returns:
            Tuple of (unique_results, duplicate_count)
        """
        seen_ncts = set()
        unique = []
        duplicates = 0

        for result in all_results:
            if result.nct_id and result.nct_id not in seen_ncts:
                seen_ncts.add(result.nct_id)
                unique.append(result)
            else:
                duplicates += 1

        return unique, duplicates


class NaturalLanguageSearchInterface:
    """
    Main interface for natural language trial searches.

    Combines parsing, synonym expansion, and multi-registry search.
    """

    def __init__(self):
        self.parser = NaturalLanguageParser()
        self.expander = SynonymExpander()
        self.searcher = MultiRegistrySearcher()

    def search(self, query: str) -> UnifiedSearchResults:
        """
        Execute full search pipeline from natural language query.

        Args:
            query: Natural language research question

        Returns:
            UnifiedSearchResults with all findings
        """
        # Step 1: Parse natural language
        pico = self.parser.parse(query)

        # Step 2: Expand terms
        expanded = {}
        if pico.intervention:
            expanded[pico.intervention] = self.expander.expand(pico.intervention, 'drug')
        if pico.population:
            expanded[pico.population] = self.expander.expand(pico.population, 'condition')

        # Step 3: Build and execute queries
        ctgov_query = self.searcher.build_ctgov_query(pico, expanded)
        ctgov_results = self.searcher.search_ctgov(ctgov_query)
        ictrp_results = self.searcher.search_ictrp(pico, expanded)

        # Step 4: Deduplicate
        all_results = ctgov_results + ictrp_results
        unique_results, duplicates = self.searcher.deduplicate_results(all_results)

        # Step 5: Estimate recall
        recall_estimate = self._estimate_recall(pico, expanded, len(unique_results))

        return UnifiedSearchResults(
            query=query,
            parsed_pico=pico,
            expanded_terms=expanded,
            ctgov_results=ctgov_results,
            ictrp_results=ictrp_results,
            other_registry_results={},
            total_unique=len(unique_results),
            total_duplicates=duplicates,
            recall_estimate=recall_estimate,
            recall_ci=(max(0, recall_estimate - 0.1), min(1.0, recall_estimate + 0.1)),
            search_timestamp=datetime.now().isoformat(),
            api_versions=self.searcher.api_versions
        )

    def _estimate_recall(self, pico: ParsedPICO,
                        expanded: Dict[str, ExpandedTerms],
                        results_count: int) -> float:
        """Estimate recall based on search characteristics."""
        # Base recall estimate
        base_recall = 0.75

        # Adjustments
        if pico.intervention in expanded:
            drug_terms = expanded[pico.intervention]
            if len(drug_terms.all_terms()) > 5:
                base_recall += 0.05  # Good synonym expansion
            if drug_terms.drug_class:
                base_recall += 0.03  # Drug class recognized

        if pico.population in expanded:
            if len(expanded[pico.population].all_terms()) > 3:
                base_recall += 0.03

        # Study design filter helps precision, may affect recall
        if pico.study_design == StudyDesign.RCT:
            base_recall -= 0.05  # Stricter filter

        return min(0.95, max(0.50, base_recall))

    def explain_search(self, query: str) -> str:
        """
        Explain how the query was interpreted.

        Useful for users to understand and refine their searches.
        """
        pico = self.parser.parse(query)
        expanded = {}
        if pico.intervention:
            expanded[pico.intervention] = self.expander.expand(pico.intervention, 'drug')
        if pico.population:
            expanded[pico.population] = self.expander.expand(pico.population, 'condition')

        lines = [
            "Query Interpretation",
            "=" * 50,
            f"Original: {query}",
            "",
            "Parsed PICO Elements:",
            "-" * 30,
            f"Population: {pico.population or 'Not identified'}",
            f"Intervention: {pico.intervention or 'Not identified'}",
            f"Comparator: {pico.comparator or 'Not identified'}",
            f"Outcome: {pico.outcome or 'Not identified'}",
            f"Study Design: {pico.study_design.value}",
            f"Age Group: {pico.age_group or 'Not specified'}",
            "",
            "Expanded Terms:",
            "-" * 30,
        ]

        for term, expansion in expanded.items():
            lines.append(f"\n{term}:")
            lines.append(f"  Synonyms: {', '.join(expansion.synonyms[:5])}")
            if expansion.brand_names:
                lines.append(f"  Brand names: {', '.join(expansion.brand_names)}")
            if expansion.mesh_terms:
                lines.append(f"  MeSH: {', '.join(expansion.mesh_terms)}")

        lines.extend([
            "",
            "CT.gov Query:",
            "-" * 30,
            self.searcher.build_ctgov_query(pico, expanded),
            "",
            "Confidence Scores:",
            "-" * 30,
        ])

        for element, score in pico.confidence.items():
            lines.append(f"  {element}: {score:.0%}")

        return "\n".join(lines)


def main():
    """Demo of natural language search interface."""
    print("Natural Language Search Interface Demo")
    print("=" * 50)

    interface = NaturalLanguageSearchInterface()

    # Example queries
    queries = [
        "What RCTs have tested GLP-1 agonists for weight loss in adults with obesity?",
        "Clinical trials of pembrolizumab for lung cancer",
        "Studies evaluating adalimumab in patients with rheumatoid arthritis",
        "Randomized trials comparing semaglutide vs placebo for diabetes"
    ]

    for query in queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print("=" * 60)

        # Show interpretation
        explanation = interface.explain_search(query)
        print(explanation)

        # Execute search (mock)
        results = interface.search(query)
        print(f"\nSearch Results Summary:")
        print(f"  Estimated recall: {results.recall_estimate:.0%}")
        print(f"  (Note: Actual API calls are mocked in this demo)")

    # Save example output
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    sample_results = interface.search(queries[0])
    with open(output_dir / "nl_search_example.json", 'w') as f:
        json.dump(sample_results.to_dict(), f, indent=2)

    print(f"\n\nExample output saved to {output_dir / 'nl_search_example.json'}")


if __name__ == "__main__":
    main()
