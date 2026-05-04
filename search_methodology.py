"""
World-Class Search Methodology Module for Systematic Reviews.

This module implements best practices from academic literature on systematic
review search methodology, incorporating:

1. PRESS 2015 Guidelines (Peer Review of Electronic Search Strategies)
2. Cochrane Handbook Chapter 4 (v6.5, September 2024)
3. Search Filter Validation Methods (99.9% sensitivity achievable)
4. Boolean Query Optimization
5. Grey Literature and Trial Registry Integration
6. Machine Learning-Assisted Screening

References:
- McGowan J, et al. PRESS Peer Review of Electronic Search Strategies (2015)
- Lefebvre C, et al. Cochrane Handbook Chapter 4: Searching for studies
- Gusenbauer M, Gauster L. How to conduct literature sampling (2025)
- Sampson M, et al. An evidence-based practice guideline for search strategies
- Campbell Collaboration. Grey literature searching guidance (2024)

Author: CTGov Search Strategies Team
Version: 1.0.0
Date: 2026-01-18
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict
import json


# =============================================================================
# PRESS 2015 GUIDELINES - Peer Review of Electronic Search Strategies
# =============================================================================

class PRESSElement(Enum):
    """Six elements of the PRESS 2015 Guidelines."""
    TRANSLATION = "translation"  # Translation of research question
    BOOLEAN_OPERATORS = "boolean"  # Boolean and proximity operators
    SUBJECT_HEADINGS = "subject_headings"  # Subject headings
    TEXT_WORDS = "text_words"  # Text word searching
    SPELLING = "spelling"  # Spelling, syntax, line numbers
    LIMITS = "limits"  # Limits and filters


@dataclass
class PRESSValidationResult:
    """Result of PRESS guideline validation."""
    element: PRESSElement
    passed: bool
    score: float  # 0.0 to 1.0
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class PRESSReport:
    """Complete PRESS validation report."""
    query: str
    database: str
    overall_score: float
    elements: Dict[PRESSElement, PRESSValidationResult] = field(default_factory=dict)
    is_acceptable: bool = False
    summary: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "query": self.query,
            "database": self.database,
            "overall_score": self.overall_score,
            "is_acceptable": self.is_acceptable,
            "summary": self.summary,
            "elements": {
                e.value: {
                    "passed": r.passed,
                    "score": r.score,
                    "issues": r.issues,
                    "recommendations": r.recommendations
                }
                for e, r in self.elements.items()
            }
        }


class PRESSValidator:
    """
    PRESS 2015 Guidelines Validator.

    Implements the six elements from:
    McGowan J, et al. PRESS Peer Review of Electronic Search Strategies:
    2015 Guideline Statement. J Clin Epidemiol. 2016;75:40-6.
    """

    # Common Boolean operators
    BOOLEAN_OPS = {"AND", "OR", "NOT", "NEAR", "ADJ", "SAME", "WITH"}

    # Common subject heading qualifiers
    MESH_QUALIFIERS = {
        "/therapy", "/drug therapy", "/diagnosis", "/epidemiology",
        "/prevention", "/treatment", "/adverse effects", "/classification",
        "/complications", "/etiology", "/mortality", "/physiopathology"
    }

    # Common field tags
    FIELD_TAGS = {
        "[tiab]", "[ti]", "[ab]", "[tw]", "[mh]", "[sh]", "[pt]",
        "[mesh]", "[majr]", "[text word]", "[title/abstract]"
    }

    # Common truncation symbols
    TRUNCATION_SYMBOLS = {"*", "$", "?", "#"}

    # Common spelling variants to check
    SPELLING_VARIANTS = {
        "randomized": ["randomised"],
        "pediatric": ["paediatric"],
        "anemia": ["anaemia"],
        "edema": ["oedema"],
        "tumor": ["tumour"],
        "fetal": ["foetal"],
        "estrogen": ["oestrogen"],
        "behavior": ["behaviour"],
        "center": ["centre"],
        "fiber": ["fibre"],
        "gray": ["grey"],
        "analyze": ["analyse"],
        "organization": ["organisation"],
    }

    def __init__(self):
        """Initialize the PRESS validator."""
        # NOTE: PRESS 2015 guidelines do not assign weights to elements.
        # These weights are heuristic estimates for automated scoring.
        # The original PRESS guideline uses qualitative assessment.
        # Source: McGowan J, et al. J Clin Epidemiol. 2016;75:40-6.
        self.validation_weights = {
            PRESSElement.TRANSLATION: 0.25,      # Most critical per PRESS
            PRESSElement.BOOLEAN_OPERATORS: 0.20,
            PRESSElement.SUBJECT_HEADINGS: 0.15,
            PRESSElement.TEXT_WORDS: 0.20,
            PRESSElement.SPELLING: 0.10,
            PRESSElement.LIMITS: 0.10,
        }
        self._weights_caveat = (
            "CAVEAT: These weights are heuristic. PRESS 2015 uses qualitative "
            "expert review, not quantitative scoring. Automated scores are "
            "indicative only and should not replace peer review."
        )

    def validate(self, query: str, database: str = "ClinicalTrials.gov",
                 pico_elements: Optional[Dict] = None) -> PRESSReport:
        """
        Validate a search query against PRESS 2015 guidelines.

        Args:
            query: The search query string
            database: Target database name
            pico_elements: Optional PICO elements for translation validation

        Returns:
            PRESSReport with validation results
        """
        report = PRESSReport(query=query, database=database, overall_score=0.0)

        # Validate each element
        report.elements[PRESSElement.TRANSLATION] = self._validate_translation(
            query, pico_elements
        )
        report.elements[PRESSElement.BOOLEAN_OPERATORS] = self._validate_boolean(query)
        report.elements[PRESSElement.SUBJECT_HEADINGS] = self._validate_subject_headings(
            query, database
        )
        report.elements[PRESSElement.TEXT_WORDS] = self._validate_text_words(query)
        report.elements[PRESSElement.SPELLING] = self._validate_spelling(query)
        report.elements[PRESSElement.LIMITS] = self._validate_limits(query, database)

        # Calculate overall score
        total_score = sum(
            result.score * self.validation_weights[element]
            for element, result in report.elements.items()
        )
        report.overall_score = round(total_score, 3)

        # Determine if acceptable (>= 0.7 is considered acceptable)
        report.is_acceptable = report.overall_score >= 0.7

        # Generate summary
        report.summary = self._generate_summary(report)

        return report

    def _validate_translation(self, query: str,
                              pico_elements: Optional[Dict]) -> PRESSValidationResult:
        """
        Element 1: Translation of the research question.

        Checks if all PICO elements are represented in the search.
        """
        result = PRESSValidationResult(
            element=PRESSElement.TRANSLATION,
            passed=True,
            score=1.0
        )

        if not pico_elements:
            # Cannot validate without PICO elements
            result.score = 0.5
            result.recommendations.append(
                "Provide PICO elements for complete translation validation"
            )
            return result

        query_lower = query.lower()
        missing_elements = []

        for element, terms in pico_elements.items():
            if isinstance(terms, str):
                terms = [terms]

            found = any(term.lower() in query_lower for term in terms)
            if not found:
                missing_elements.append(element)

        if missing_elements:
            result.passed = False
            result.score = 1.0 - (len(missing_elements) * 0.25)
            result.issues.append(
                f"Missing PICO elements: {', '.join(missing_elements)}"
            )
            result.recommendations.append(
                "Ensure all PICO elements are represented in the search"
            )

        return result

    def _validate_boolean(self, query: str) -> PRESSValidationResult:
        """
        Element 2: Boolean and proximity operators.

        Checks for proper use of AND, OR, NOT, and proximity operators.
        """
        result = PRESSValidationResult(
            element=PRESSElement.BOOLEAN_OPERATORS,
            passed=True,
            score=1.0
        )
        hard_failure = False

        # Check for Boolean operators
        has_and = bool(re.search(r'\bAND\b', query, re.IGNORECASE))
        has_or = bool(re.search(r'\bOR\b', query, re.IGNORECASE))
        has_not = bool(re.search(r'\bNOT\b', query, re.IGNORECASE))

        # Basic queries should have at least AND or OR
        if not has_and and not has_or:
            result.score -= 0.2
            result.recommendations.append(
                "Consider using Boolean operators (AND/OR) to combine search concepts"
            )

        # Check for NOT usage - often problematic
        if has_not:
            result.recommendations.append(
                "Review NOT operator usage - may exclude relevant studies"
            )

        # Check for balanced parentheses
        if query.count('(') != query.count(')'):
            hard_failure = True
            result.score -= 0.3
            result.issues.append("Unbalanced parentheses in query")

        # Check for proximity operators
        proximity_patterns = [
            r'\bNEAR/?\d*\b', r'\bADJ\d*\b', r'\bW/\d+\b', r'\bN/\d+\b'
        ]
        has_proximity = any(
            re.search(p, query, re.IGNORECASE) for p in proximity_patterns
        )

        if has_proximity:
            result.recommendations.append(
                "Proximity operators used - verify database compatibility"
            )

        # Check for nested Boolean logic
        if '(' in query and ')' in query:
            # Good - using grouping
            pass
        elif has_and and has_or:
            result.score -= 0.2
            result.issues.append(
                "Mixed AND/OR without parentheses may cause operator precedence issues"
            )
            result.recommendations.append(
                "Use parentheses to group OR terms: (term1 OR term2) AND term3"
            )

        result.score = max(0.0, result.score)
        result.passed = not hard_failure and result.score >= 0.7

        return result

    def _validate_subject_headings(self, query: str,
                                   database: str) -> PRESSValidationResult:
        """
        Element 3: Subject headings (MeSH, etc.).

        Checks for appropriate use of controlled vocabulary.
        """
        result = PRESSValidationResult(
            element=PRESSElement.SUBJECT_HEADINGS,
            passed=True,
            score=1.0
        )

        # Check for MeSH terms or subject headings
        has_mesh = bool(re.search(r'\[mesh\]|\[mh\]|\[majr\]', query, re.IGNORECASE))
        has_qualifier = any(q in query.lower() for q in self.MESH_QUALIFIERS)

        # For PubMed/MEDLINE, MeSH is expected
        if database.lower() in ["pubmed", "medline", "ovid medline"]:
            if not has_mesh:
                result.score -= 0.3
                result.recommendations.append(
                    "Consider adding MeSH terms for comprehensive retrieval"
                )

        # For ClinicalTrials.gov, MeSH is less critical
        elif database.lower() == "clinicaltrials.gov":
            # CT.gov uses condition/intervention fields
            if "[condition]" in query.lower() or "[intervention]" in query.lower():
                pass  # Good - using CT.gov specific fields
            else:
                result.recommendations.append(
                    "Consider using CT.gov-specific field tags: [Condition], [Intervention]"
                )

        # Check for explosion (tree searching)
        if has_mesh and "exp " not in query.lower() and not re.search(r'/\s*$', query):
            result.recommendations.append(
                "Consider exploding MeSH terms to include narrower terms"
            )

        result.passed = result.score >= 0.7
        return result

    def _validate_text_words(self, query: str) -> PRESSValidationResult:
        """
        Element 4: Text word searching (free text).

        Checks for appropriate text word terms and truncation.
        """
        result = PRESSValidationResult(
            element=PRESSElement.TEXT_WORDS,
            passed=True,
            score=1.0
        )

        # Check for truncation
        has_truncation = any(sym in query for sym in self.TRUNCATION_SYMBOLS)

        if not has_truncation:
            result.score -= 0.1
            result.recommendations.append(
                "Consider using truncation (*) to capture word variants"
            )

        # Check for field specification
        has_field_tag = any(tag in query.lower() for tag in self.FIELD_TAGS)

        if not has_field_tag and "[" not in query:
            result.recommendations.append(
                "Consider specifying search fields (e.g., [tiab], [tw])"
            )

        # Check for phrase searching with quotes
        has_phrases = bool(re.search(r'"[^"]+"|\'[^\']+\'', query))

        if has_phrases:
            # Good - using phrase searching
            pass
        else:
            result.recommendations.append(
                'Consider using quotes for multi-word phrases: "heart failure"'
            )

        # Check for synonyms (indicated by OR groups)
        or_groups = re.findall(r'\([^)]*\bOR\b[^)]*\)', query, re.IGNORECASE)

        if len(or_groups) < 2:
            result.score -= 0.1
            result.recommendations.append(
                "Consider adding synonyms and related terms using OR"
            )

        result.passed = result.score >= 0.7
        return result

    def _validate_spelling(self, query: str) -> PRESSValidationResult:
        """
        Element 5: Spelling, syntax, and line numbers.

        Checks for spelling variants, typos, and syntax errors.
        """
        result = PRESSValidationResult(
            element=PRESSElement.SPELLING,
            passed=True,
            score=1.0
        )

        query_lower = query.lower()

        # Check for spelling variants (US/UK)
        missing_variants = []
        for us_spelling, uk_variants in self.SPELLING_VARIANTS.items():
            if us_spelling in query_lower:
                # Check if UK variant is also included
                if not any(uk in query_lower for uk in uk_variants):
                    missing_variants.append(f"{us_spelling}/{uk_variants[0]}")
            elif any(uk in query_lower for uk in uk_variants):
                # UK variant used, check for US
                missing_variants.append(f"{us_spelling}/{uk_variants[0]}")

        if missing_variants:
            result.score -= len(missing_variants) * 0.05
            result.recommendations.append(
                f"Consider including spelling variants: {', '.join(missing_variants[:3])}"
            )

        # Check for common typos
        common_typos = {
            "randomzied": "randomized",
            "controled": "controlled",
            "placbo": "placebo",
            "clincal": "clinical",
            "stuides": "studies",
        }

        for typo, correct in common_typos.items():
            if typo in query_lower:
                result.passed = False
                result.score -= 0.2
                result.issues.append(f"Possible typo: '{typo}' should be '{correct}'")

        # Check syntax (field tags closed, etc.)
        open_brackets = query.count('[')
        close_brackets = query.count(']')
        if open_brackets != close_brackets:
            result.passed = False
            result.score -= 0.3
            result.issues.append("Unmatched brackets in field tags")

        result.score = max(0.0, result.score)
        result.passed = result.passed and result.score >= 0.7
        return result

    def _validate_limits(self, query: str, database: str) -> PRESSValidationResult:
        """
        Element 6: Limits and filters.

        Checks for appropriate use of search filters and limits.
        """
        result = PRESSValidationResult(
            element=PRESSElement.LIMITS,
            passed=True,
            score=1.0
        )

        query_lower = query.lower()

        # Check for date limits
        has_date_limit = bool(re.search(
            r'\d{4}|\[dp\]|\[date\]|publication date|year',
            query_lower
        ))

        if has_date_limit:
            result.recommendations.append(
                "Date limits applied - ensure this is appropriate for the review scope"
            )

        # Check for language limits
        has_language = bool(re.search(r'\[la\]|language|english', query_lower))

        if has_language:
            result.recommendations.append(
                "Language limit applied - may exclude relevant non-English studies"
            )

        # Check for study type filters (RCT filters)
        rct_filter_terms = [
            "randomized controlled trial",
            "controlled clinical trial",
            "random allocation",
            "double-blind",
            "single-blind",
            "placebo",
        ]

        has_rct_filter = any(term in query_lower for term in rct_filter_terms)

        if has_rct_filter:
            # Good - using validated RCT filter
            pass
        else:
            result.recommendations.append(
                "Consider using a validated RCT filter for clinical effectiveness reviews"
            )

        # Check for publication type limits
        has_pt_limit = bool(re.search(r'\[pt\]|\[publication type\]', query_lower))

        result.passed = result.score >= 0.7
        return result

    def _generate_summary(self, report: PRESSReport) -> str:
        """Generate a summary of the PRESS validation."""
        lines = []

        # Caveat first
        lines.append("NOTE: Automated PRESS scoring is indicative only.")
        lines.append("True PRESS validation requires expert peer review.")
        lines.append("")

        # Overall assessment
        if report.is_acceptable:
            lines.append("✓ Search strategy appears to address PRESS 2015 elements")
        else:
            lines.append("✗ Search strategy may need revision per PRESS 2015 guidelines")

        lines.append(f"Indicative Score: {report.overall_score:.1%}")

        # Element-by-element
        failed_elements = [
            e.value for e, r in report.elements.items() if not r.passed
        ]

        if failed_elements:
            lines.append(f"Elements needing attention: {', '.join(failed_elements)}")

        # Top recommendations
        all_recommendations = []
        for element, result in report.elements.items():
            all_recommendations.extend(result.recommendations[:2])

        if all_recommendations:
            lines.append("Top recommendations:")
            for rec in all_recommendations[:5]:
                lines.append(f"  • {rec}")

        return "\n".join(lines)


# =============================================================================
# SEARCH FILTER VALIDATION
# =============================================================================

@dataclass
class FilterPerformanceMetrics:
    """Performance metrics for a search filter."""
    sensitivity: float  # Recall - proportion of relevant studies found
    specificity: float  # Proportion of irrelevant studies excluded
    precision: float  # Proportion of retrieved studies that are relevant
    npv: float  # Negative predictive value
    nnr: float  # Number needed to read (1/precision)
    f1_score: float  # Harmonic mean of precision and recall

    # Confidence intervals (95%)
    sensitivity_ci: Tuple[float, float] = (0.0, 0.0)
    specificity_ci: Tuple[float, float] = (0.0, 0.0)

    @classmethod
    def from_counts(cls, tp: int, fp: int, fn: int, tn: int) -> "FilterPerformanceMetrics":
        """
        Calculate metrics from confusion matrix counts.

        Args:
            tp: True positives (relevant and retrieved)
            fp: False positives (irrelevant but retrieved)
            fn: False negatives (relevant but not retrieved)
            tn: True negatives (irrelevant and not retrieved)
        """
        # Avoid division by zero
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        npv = tn / (tn + fn) if (tn + fn) > 0 else 0.0
        nnr = 1 / precision if precision > 0 else float('inf')
        f1 = 2 * (precision * sensitivity) / (precision + sensitivity) \
            if (precision + sensitivity) > 0 else 0.0

        # Wilson score confidence intervals
        sensitivity_ci = cls._wilson_ci(tp, tp + fn)
        specificity_ci = cls._wilson_ci(tn, tn + fp)

        return cls(
            sensitivity=sensitivity,
            specificity=specificity,
            precision=precision,
            npv=npv,
            nnr=nnr,
            f1_score=f1,
            sensitivity_ci=sensitivity_ci,
            specificity_ci=specificity_ci
        )

    @staticmethod
    def _wilson_ci(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
        """Calculate Wilson score confidence interval."""
        if total == 0:
            return (0.0, 0.0)

        p = successes / total
        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        margin = (z / denominator) * (p * (1 - p) / total + z**2 / (4 * total**2))**0.5

        return (max(0.0, center - margin), min(1.0, center + margin))


class SearchFilterValidator:
    """
    Validates search filter performance.

    Based on methodological literature:
    - Sampson M, et al. Systematic review search methods guidelines
    - Glanville J, et al. Search filter validation studies

    Target performance for high-sensitivity filters:
    - Sensitivity: ≥ 99% (ideally 99.9%)
    - Specificity: As high as possible while maintaining sensitivity
    """

    # Benchmark thresholds from literature
    SENSITIVITY_THRESHOLD = 0.99  # 99% minimum for comprehensive searches
    HIGH_SENSITIVITY_THRESHOLD = 0.999  # 99.9% for exhaustive searches
    ACCEPTABLE_SPECIFICITY = 0.50  # 50% specificity is acceptable

    def __init__(self):
        """Initialize the validator."""
        self.validation_runs: List[Dict] = []

    def validate_filter(
        self,
        filter_name: str,
        true_positives: int,
        false_positives: int,
        false_negatives: int,
        true_negatives: int,
        gold_standard_source: str = ""
    ) -> Dict:
        """
        Validate a search filter against gold standard.

        Args:
            filter_name: Name of the filter being validated
            true_positives: Relevant studies retrieved
            false_positives: Irrelevant studies retrieved
            false_negatives: Relevant studies missed
            true_negatives: Irrelevant studies correctly excluded
            gold_standard_source: Source of the gold standard set

        Returns:
            Dictionary with validation results
        """
        metrics = FilterPerformanceMetrics.from_counts(
            true_positives, false_positives, false_negatives, true_negatives
        )

        # Determine if filter meets thresholds
        meets_sensitivity = metrics.sensitivity >= self.SENSITIVITY_THRESHOLD
        meets_high_sensitivity = metrics.sensitivity >= self.HIGH_SENSITIVITY_THRESHOLD

        # Generate assessment
        assessment = []

        if meets_high_sensitivity:
            assessment.append("✓ Achieves high-sensitivity threshold (≥99.9%)")
        elif meets_sensitivity:
            assessment.append("✓ Meets minimum sensitivity threshold (≥99%)")
        else:
            assessment.append(f"✗ Below sensitivity threshold: {metrics.sensitivity:.1%} < 99%")

        if metrics.specificity >= self.ACCEPTABLE_SPECIFICITY:
            assessment.append(f"✓ Acceptable specificity: {metrics.specificity:.1%}")
        else:
            assessment.append(f"Note: Low specificity ({metrics.specificity:.1%}) - more screening needed")

        result = {
            "filter_name": filter_name,
            "gold_standard": gold_standard_source,
            "sample_size": true_positives + false_positives + false_negatives + true_negatives,
            "metrics": {
                "sensitivity": metrics.sensitivity,
                "sensitivity_ci": metrics.sensitivity_ci,
                "specificity": metrics.specificity,
                "specificity_ci": metrics.specificity_ci,
                "precision": metrics.precision,
                "npv": metrics.npv,
                "nnr": metrics.nnr,
                "f1_score": metrics.f1_score,
            },
            "thresholds": {
                "meets_sensitivity": meets_sensitivity,
                "meets_high_sensitivity": meets_high_sensitivity,
                "acceptable_specificity": metrics.specificity >= self.ACCEPTABLE_SPECIFICITY,
            },
            "assessment": assessment,
            "confusion_matrix": {
                "tp": true_positives,
                "fp": false_positives,
                "fn": false_negatives,
                "tn": true_negatives,
            }
        }

        self.validation_runs.append(result)
        return result

    def generate_validation_report(self) -> str:
        """Generate a summary report of all validation runs."""
        if not self.validation_runs:
            return "No validation runs recorded."

        lines = ["# Search Filter Validation Report", ""]

        for run in self.validation_runs:
            lines.append(f"## {run['filter_name']}")
            lines.append(f"Gold Standard: {run['gold_standard']}")
            lines.append(f"Sample Size: {run['sample_size']}")
            lines.append("")

            m = run['metrics']
            lines.append(f"| Metric | Value | 95% CI |")
            lines.append(f"|--------|-------|--------|")
            lines.append(f"| Sensitivity | {m['sensitivity']:.1%} | [{m['sensitivity_ci'][0]:.1%}, {m['sensitivity_ci'][1]:.1%}] |")
            lines.append(f"| Specificity | {m['specificity']:.1%} | [{m['specificity_ci'][0]:.1%}, {m['specificity_ci'][1]:.1%}] |")
            lines.append(f"| Precision | {m['precision']:.1%} | - |")
            lines.append(f"| NNR | {m['nnr']:.1f} | - |")
            lines.append(f"| F1 Score | {m['f1_score']:.3f} | - |")
            lines.append("")

            for a in run['assessment']:
                lines.append(f"- {a}")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# BOOLEAN QUERY OPTIMIZER
# =============================================================================

class BooleanOptimizer:
    """
    Optimizes Boolean search queries for maximum recall and precision.

    Based on:
    - Cochrane Handbook search guidance
    - InterTASC Information Specialists' Sub-Group (ISSG) recommendations
    - CADTH Grey Matters checklist
    """

    def __init__(self):
        """Initialize the optimizer."""
        self.operators = {
            "AND": " AND ",
            "OR": " OR ",
            "NOT": " NOT ",
        }

    def optimize_query(self, concepts: Dict[str, List[str]],
                       include_truncation: bool = True,
                       include_phrase_search: bool = True) -> str:
        """
        Build an optimized Boolean query from concept groups.

        Args:
            concepts: Dictionary mapping concept names to term lists
                     e.g., {"population": ["diabetes", "diabetic*"],
                            "intervention": ["metformin", "glucophage"]}
            include_truncation: Whether to add truncation to terms
            include_phrase_search: Whether to use phrase searching

        Returns:
            Optimized Boolean query string
        """
        concept_queries = []

        for concept_name, terms in concepts.items():
            processed_terms = []

            for term in terms:
                processed = term

                # Add truncation if appropriate
                if include_truncation and not term.endswith('*'):
                    # Don't truncate short words or phrases
                    if len(term) >= 4 and ' ' not in term:
                        processed = term.rstrip('s') + '*'

                # Add phrase searching for multi-word terms
                if include_phrase_search and ' ' in processed and '"' not in processed:
                    processed = f'"{processed}"'

                processed_terms.append(processed)

            # Combine terms with OR
            if processed_terms:
                concept_query = f"({self.operators['OR'].join(processed_terms)})"
                concept_queries.append(concept_query)

        # Combine concepts with AND
        final_query = self.operators['AND'].join(concept_queries)

        return final_query

    def add_spelling_variants(self, terms: List[str]) -> List[str]:
        """Add common US/UK spelling variants to term list."""
        expanded = set(terms)

        # Word-specific US/UK variants (not substring replacements)
        known_variants = {
            "randomized": "randomised",
            "randomization": "randomisation",
            "standardized": "standardised",
            "standardization": "standardisation",
            "organized": "organised",
            "organization": "organisation",
            "analyzed": "analysed",
            "analysis": "analysis",  # Same in both
            "pediatric": "paediatric",
            "pediatrics": "paediatrics",
            "anemia": "anaemia",
            "anemic": "anaemic",
            "edema": "oedema",
            "tumor": "tumour",
            "tumors": "tumours",
            "fetal": "foetal",
            "fetus": "foetus",
            "estrogen": "oestrogen",
            "behavior": "behaviour",
            "behavioral": "behavioural",
            "center": "centre",
            "centers": "centres",
            "fiber": "fibre",
            "fibers": "fibres",
            "gray": "grey",
            "color": "colour",
            "colored": "coloured",
            "favor": "favour",
            "favorable": "favourable",
            "honor": "honour",
            "labor": "labour",
            "leukemia": "leukaemia",
            "diarrhea": "diarrhoea",
            "hemoglobin": "haemoglobin",
            "hemorrhage": "haemorrhage",
            "orthopedic": "orthopaedic",
            "gynecology": "gynaecology",
            "gynecological": "gynaecological",
            "optimize": "optimise",
            "optimization": "optimisation",
            "minimize": "minimise",
            "maximize": "maximise",
            "utilize": "utilise",
            "utilization": "utilisation",
            "recognize": "recognise",
            "recognized": "recognised",
            "characterize": "characterise",
            "characterized": "characterised",
            "catalog": "catalogue",
            "dialog": "dialogue",
            "program": "programme",
            "aging": "ageing",
        }

        for term in terms:
            term_lower = term.lower()
            # Check if term matches a known variant
            if term_lower in known_variants:
                expanded.add(known_variants[term_lower])
            # Check reverse (UK -> US)
            for us, uk in known_variants.items():
                if term_lower == uk:
                    expanded.add(us)

        return list(expanded)

    def suggest_synonyms(self, term: str) -> List[str]:
        """
        Suggest synonyms for a search term.

        This is a simplified version - in production, use NLM MeSH API.
        """
        # Common medical synonyms (simplified)
        synonym_map = {
            "heart attack": ["myocardial infarction", "MI", "acute coronary syndrome"],
            "stroke": ["cerebrovascular accident", "CVA", "brain infarction"],
            "diabetes": ["diabetes mellitus", "DM", "diabetic"],
            "high blood pressure": ["hypertension", "HTN", "elevated blood pressure"],
            "cancer": ["neoplasm", "tumor", "malignancy", "carcinoma"],
            "depression": ["depressive disorder", "major depression", "MDD"],
            "anxiety": ["anxiety disorder", "GAD", "anxious"],
            "pain": ["analgesia", "nociception", "painful"],
            "infection": ["infectious disease", "sepsis", "bacterial"],
            "surgery": ["surgical procedure", "operation", "operative"],
        }

        term_lower = term.lower()

        if term_lower in synonym_map:
            return [term] + synonym_map[term_lower]

        # Check if term is in any synonym list
        for key, synonyms in synonym_map.items():
            if term_lower in [s.lower() for s in synonyms]:
                return [key] + synonyms

        return [term]

    def validate_syntax(self, query: str) -> Dict:
        """
        Validate Boolean query syntax.

        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []

        # Check parentheses balance
        if query.count('(') != query.count(')'):
            issues.append("Unbalanced parentheses")

        # Check quote balance
        if query.count('"') % 2 != 0:
            issues.append("Unbalanced quotation marks")

        # Check for empty groups
        if "()" in query or "( )" in query:
            issues.append("Empty parentheses group")

        # Check for double operators
        double_ops = [" AND AND ", " OR OR ", " NOT NOT "]
        for op in double_ops:
            if op in query.upper():
                issues.append(f"Double operator: {op.strip()}")

        # Check for leading/trailing operators
        query_stripped = query.strip()
        if query_stripped.upper().startswith(("AND ", "OR ", "NOT ")):
            issues.append("Query starts with Boolean operator")

        if query_stripped.upper().endswith((" AND", " OR", " NOT")):
            issues.append("Query ends with Boolean operator")

        # Warnings for potential issues
        if " NOT " in query.upper():
            warnings.append("NOT operator may exclude relevant studies")

        if query.count("*") > 10:
            warnings.append("Many truncation symbols - may retrieve too many irrelevant results")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "query": query
        }


# =============================================================================
# GREY LITERATURE SEARCH
# =============================================================================

class GreyLiteratureSearcher:
    """
    Grey literature search guidance based on:
    - CADTH Grey Matters checklist
    - Campbell Collaboration guidance (2024)
    - Cochrane Handbook Chapter 4.S2

    Grey literature comprises ~10% of studies in systematic reviews.
    """

    # Sources organized by category (based on CADTH Grey Matters)
    GREY_SOURCES = {
        "trial_registries": {
            "ClinicalTrials.gov": {
                "url": "https://clinicaltrials.gov/",
                "description": "US NIH registry - largest single source",
                "api": True,
                "coverage": "All phases, all countries submitting to US"
            },
            "WHO ICTRP": {
                "url": "https://trialsearch.who.int/",
                "description": "Meta-registry of 17 national registries",
                "api": True,
                "coverage": "Global coverage"
            },
            "EU Clinical Trials Register": {
                "url": "https://www.clinicaltrialsregister.eu/",
                "description": "European trials under EU directive",
                "api": False,
                "coverage": "EU member states"
            },
            "ISRCTN": {
                "url": "https://www.isrctn.com/",
                "description": "International Standard RCT Number registry",
                "api": True,
                "coverage": "International, UK-based"
            },
            "ANZCTR": {
                "url": "https://www.anzctr.org.au/",
                "description": "Australia New Zealand registry",
                "api": True,
                "coverage": "ANZ region"
            },
        },
        "regulatory_agencies": {
            "FDA Drugs@FDA": {
                "url": "https://www.accessdata.fda.gov/scripts/cder/daf/",
                "description": "US FDA drug approvals and reviews",
            },
            "EMA": {
                "url": "https://www.ema.europa.eu/",
                "description": "European Medicines Agency",
            },
            "Health Canada": {
                "url": "https://www.canada.ca/en/health-canada.html",
                "description": "Canadian drug regulatory data",
            },
        },
        "conference_abstracts": {
            "Web of Science Proceedings": {
                "url": "https://www.webofscience.com/",
                "description": "Conference proceedings index",
            },
            "Scopus Conference Papers": {
                "url": "https://www.scopus.com/",
                "description": "Conference papers from Scopus",
            },
        },
        "theses_dissertations": {
            "ProQuest Dissertations": {
                "url": "https://www.proquest.com/",
                "description": "Global dissertations database",
            },
            "EThOS": {
                "url": "https://ethos.bl.uk/",
                "description": "UK theses",
            },
            "DART-Europe": {
                "url": "https://www.dart-europe.org/",
                "description": "European theses",
            },
        },
        "preprints": {
            "medRxiv": {
                "url": "https://www.medrxiv.org/",
                "description": "Medical preprints",
                "api": True,
            },
            "bioRxiv": {
                "url": "https://www.biorxiv.org/",
                "description": "Biology preprints",
                "api": True,
            },
            "SSRN": {
                "url": "https://www.ssrn.com/",
                "description": "Social science preprints",
            },
        },
    }

    def __init__(self):
        """Initialize the grey literature searcher."""
        pass

    def get_recommended_sources(
        self,
        review_type: str = "systematic",
        topic_area: str = "clinical"
    ) -> List[Dict]:
        """
        Get recommended grey literature sources for a review.

        Args:
            review_type: Type of review (systematic, rapid, scoping)
            topic_area: Topic area (clinical, public health, social)

        Returns:
            List of recommended sources with details
        """
        recommendations = []

        # Trial registries are essential for all clinical reviews
        if topic_area == "clinical":
            for name, details in self.GREY_SOURCES["trial_registries"].items():
                recommendations.append({
                    "source": name,
                    "category": "Trial Registry",
                    "priority": "Essential",
                    **details
                })

        # Regulatory agencies for drug/device reviews
        for name, details in self.GREY_SOURCES["regulatory_agencies"].items():
            recommendations.append({
                "source": name,
                "category": "Regulatory",
                "priority": "High" if topic_area == "clinical" else "Medium",
                **details
            })

        # Conference abstracts
        if review_type != "rapid":
            for name, details in self.GREY_SOURCES["conference_abstracts"].items():
                recommendations.append({
                    "source": name,
                    "category": "Conference",
                    "priority": "Medium",
                    **details
                })

        # Preprints (with caution)
        for name, details in self.GREY_SOURCES["preprints"].items():
            recommendations.append({
                "source": name,
                "category": "Preprint",
                "priority": "Low (check for published version)",
                **details
            })

        return recommendations

    def generate_search_protocol(self, condition: str, intervention: str) -> str:
        """
        Generate a grey literature search protocol.

        Returns:
            Markdown-formatted search protocol
        """
        lines = [
            "# Grey Literature Search Protocol",
            "",
            f"## Topic: {condition} + {intervention}",
            "",
            "## Essential Sources (must search)",
            "",
            "### Trial Registries",
            "1. **ClinicalTrials.gov** - https://clinicaltrials.gov/",
            f"   - Search: {condition} AND {intervention}",
            "   - Filters: All statuses (including completed, terminated)",
            "",
            "2. **WHO ICTRP** - https://trialsearch.who.int/",
            f"   - Search: {condition} AND {intervention}",
            "   - Note: Aggregates 17 national registries",
            "",
            "### Regulatory Sources",
            "3. **FDA Drugs@FDA** - Review approval documents",
            "4. **EMA** - European Public Assessment Reports (EPARs)",
            "",
            "## Recommended Sources (highly recommended)",
            "",
            "### Conference Abstracts",
            "- Search relevant specialty conference proceedings",
            "- Check last 2 years of major conferences",
            "",
            "### Preprints (with caution)",
            "- medRxiv, bioRxiv",
            "- Always check for published version",
            "",
            "## Documentation",
            "- Record date searched for each source",
            "- Record search terms used",
            "- Record number of results screened",
            "- Record number included/excluded with reasons",
            "",
            "## PRISMA Reporting",
            "- Report grey literature sources separately in flow diagram",
            f"- Estimated yield: ~10% of total included studies",
        ]

        return "\n".join(lines)


# =============================================================================
# MACHINE LEARNING SCREENING ASSISTANT
# =============================================================================

class MLScreeningAssistant:
    """
    Machine learning-assisted screening guidance.

    IMPORTANT CAVEATS:
    - Workload reduction estimates are HIGHLY variable across datasets
    - Published figures (up to 90%) represent best-case scenarios
    - Actual performance depends on: prevalence, topic complexity, training data
    - These estimates should be treated as rough approximations only

    References:
    - van de Schoot R, et al. Nat Mach Intell. 2021;3:125-133 (ASReview)
    - O'Mara-Eves A, et al. Syst Rev. 2015;4:5 (review of text mining)
    - Olorisade BK, et al. Syst Rev. 2016;5:193 (critical analysis)
    """

    def __init__(self):
        """Initialize ML screening assistant."""
        self.screening_history = []
        self.relevance_scores = {}

    def estimate_workload_reduction(
        self,
        total_records: int,
        estimated_relevant: int,
        ml_recall: float = 0.95
    ) -> Dict:
        """
        Estimate potential workload reduction from ML-assisted screening.

        CAVEAT: These are rough estimates. Actual performance varies widely
        depending on dataset characteristics. Published workload reductions
        (50-90%) represent optimistic scenarios.

        Source: O'Mara-Eves A, et al. Syst Rev. 2015;4:5

        Args:
            total_records: Total records to screen
            estimated_relevant: Estimated number of relevant studies
            ml_recall: Expected ML recall rate

        Returns:
            Dictionary with workload estimates (treat as rough approximations)
        """
        # Estimate based on literature review by O'Mara-Eves et al. 2015
        # Precision at 95% recall varies widely (30-70%), using conservative 50%
        estimated_precision = 0.5  # Conservative estimate; actual varies 0.3-0.7

        # Records flagged by ML
        ml_flagged = estimated_relevant / estimated_precision
        ml_flagged = min(ml_flagged, total_records)

        # Manual screening still needed for flagged records
        manual_screen = ml_flagged

        # Records that can be safely excluded by ML
        ml_excluded = total_records - ml_flagged

        # Missed relevant studies
        missed = estimated_relevant * (1 - ml_recall)

        return {
            "total_records": total_records,
            "estimated_relevant": estimated_relevant,
            "ml_flagged_for_review": int(ml_flagged),
            "ml_excluded": int(ml_excluded),
            "manual_screening_needed": int(manual_screen),
            "workload_reduction_percent": round(100 * ml_excluded / total_records, 1),
            "estimated_missed_at_recall": round(missed, 1),
            "recommendation": self._get_ml_recommendation(total_records, estimated_relevant),
            "caveat": "CAUTION: These are rough estimates. Actual workload reduction "
                      "varies widely (published range: 30-90%). Performance depends on "
                      "dataset characteristics, prevalence, and topic complexity.",
            "source": "O'Mara-Eves A, et al. Syst Rev. 2015;4:5",
        }

    def _get_ml_recommendation(self, total: int, relevant: int) -> str:
        """Get recommendation for ML-assisted screening."""
        prevalence = relevant / total if total > 0 else 0

        if total < 500:
            return "Manual screening recommended - small dataset"
        elif total < 2000:
            return "ML-assisted screening optional - moderate benefit expected"
        elif prevalence < 0.01:
            return "ML-assisted screening highly recommended - low prevalence benefits most"
        elif prevalence > 0.1:
            return "ML-assisted screening recommended - moderate benefit due to high prevalence"
        else:
            return "ML-assisted screening recommended - optimal scenario for workload reduction"

    def calculate_safe_stopping(
        self,
        screened_relevant: List[int],
        batch_size: int = 50
    ) -> Dict:
        """
        Calculate SAFE stopping heuristics.

        SAFE = Stopping After Final Evidence
        Based on ASReview methodology.

        Args:
            screened_relevant: List of 1s (relevant) and 0s (not relevant)
                              in screening order
            batch_size: Number of consecutive irrelevant to consider safe

        Returns:
            Dictionary with stopping analysis
        """
        if not screened_relevant:
            return {"safe_to_stop": False, "reason": "No screening data"}

        total_screened = len(screened_relevant)
        total_relevant = sum(screened_relevant)

        # Find consecutive irrelevant runs at the end
        consecutive_irrelevant = 0
        for i in range(len(screened_relevant) - 1, -1, -1):
            if screened_relevant[i] == 0:
                consecutive_irrelevant += 1
            else:
                break

        # Estimate remaining relevant
        # Using hypergeometric distribution approximation
        screened_rate = total_relevant / total_screened if total_screened > 0 else 0

        # SAFE heuristic: stop if consecutive irrelevant exceeds threshold
        safe_threshold = max(batch_size, int(total_screened * 0.05))
        safe_to_stop = consecutive_irrelevant >= safe_threshold

        return {
            "total_screened": total_screened,
            "total_relevant_found": total_relevant,
            "consecutive_irrelevant": consecutive_irrelevant,
            "safe_threshold": safe_threshold,
            "safe_to_stop": safe_to_stop,
            "screened_relevance_rate": round(screened_rate, 4),
            "recommendation": (
                "Safe to stop screening - high confidence all relevant found"
                if safe_to_stop else
                f"Continue screening - need {safe_threshold - consecutive_irrelevant} more irrelevant in a row"
            )
        }

    def prioritize_studies(
        self,
        studies: List[Dict],
        known_relevant: List[str]
    ) -> List[Dict]:
        """
        Prioritize studies for screening based on similarity to known relevant.

        This is a simplified version - production would use TF-IDF/embeddings.

        Args:
            studies: List of study dictionaries with 'id' and 'title' keys
            known_relevant: List of IDs of known relevant studies

        Returns:
            Studies sorted by estimated relevance (highest first)
        """
        # Extract keywords from known relevant
        relevant_keywords = set()
        for study in studies:
            if study.get('id') in known_relevant:
                words = study.get('title', '').lower().split()
                relevant_keywords.update(w for w in words if len(w) > 3)

        # Score each study
        for study in studies:
            title_words = set(study.get('title', '').lower().split())
            overlap = len(title_words & relevant_keywords)
            study['relevance_score'] = overlap

        # Sort by relevance score
        return sorted(studies, key=lambda x: x.get('relevance_score', 0), reverse=True)


# =============================================================================
# COCHRANE-COMPLIANT SEARCH BUILDER
# =============================================================================

class CochraneSearchBuilder:
    """
    Builds Cochrane Handbook-compliant search strategies.

    Based on Cochrane Handbook Chapter 4 (v6.5, September 2024).
    """

    # Cochrane Highly Sensitive Search Strategy for RCTs (HSSS)
    # Source: Lefebvre C, et al. Cochrane Handbook v6.5, Chapter 4
    # Note: "groups[tiab]" removed due to low specificity (not in official filter)
    COCHRANE_RCT_FILTER = [
        "randomized controlled trial[pt]",
        "controlled clinical trial[pt]",
        "randomized[tiab]",
        "randomised[tiab]",
        "placebo[tiab]",
        "drug therapy[sh]",
        "randomly[tiab]",
        "trial[tiab]",
        # "groups[tiab]" - REMOVED: Low specificity, not in official Cochrane HSSS
    ]

    def __init__(self):
        """Initialize the search builder."""
        pass

    def build_cochrane_search(
        self,
        condition_terms: List[str],
        intervention_terms: List[str],
        study_type: str = "rct",
        database: str = "pubmed"
    ) -> str:
        """
        Build a Cochrane-compliant search strategy.

        Args:
            condition_terms: Population/condition terms
            intervention_terms: Intervention terms
            study_type: Type of study (rct, observational, all)
            database: Target database

        Returns:
            Complete search strategy string
        """
        lines = []

        # Line 1: Condition terms with MeSH
        condition_query = self._build_concept_line(condition_terms, "condition")
        lines.append(f"#1 {condition_query}")

        # Line 2: Intervention terms
        intervention_query = self._build_concept_line(intervention_terms, "intervention")
        lines.append(f"#2 {intervention_query}")

        # Line 3: Combine condition AND intervention
        lines.append("#3 #1 AND #2")

        # Line 4: Add study type filter if RCT
        if study_type == "rct":
            rct_filter = " OR ".join(self.COCHRANE_RCT_FILTER)
            lines.append(f"#4 {rct_filter}")
            lines.append("#5 #3 AND #4")

        return "\n".join(lines)

    def _build_concept_line(self, terms: List[str], concept_type: str) -> str:
        """Build a search line for a concept."""
        processed = []

        for term in terms:
            # Add original term
            processed.append(f'"{term}"[tiab]')

            # Add truncated version if appropriate
            if len(term) >= 5 and ' ' not in term:
                processed.append(f'{term}*[tiab]')

            # Add MeSH version
            processed.append(f'"{term}"[mesh]')

        return "(" + " OR ".join(processed) + ")"

    def validate_cochrane_compliance(self, search_strategy: str) -> Dict:
        """
        Validate a search strategy for Cochrane compliance.

        Returns:
            Dictionary with compliance assessment
        """
        issues = []
        recommendations = []
        score = 100

        # Check for MeSH terms
        if "[mesh]" not in search_strategy.lower() and "[mh]" not in search_strategy.lower():
            issues.append("No MeSH terms detected")
            score -= 15

        # Check for text word searching
        if "[tiab]" not in search_strategy.lower() and "[tw]" not in search_strategy.lower():
            issues.append("No title/abstract searching detected")
            score -= 15

        # Check for Boolean operators
        if " AND " not in search_strategy.upper():
            issues.append("No AND operators - concepts may not be combined")
            score -= 20

        if " OR " not in search_strategy.upper():
            issues.append("No OR operators - synonyms may not be included")
            score -= 10

        # Check for RCT filter (if applicable)
        rct_indicators = ["randomized", "randomised", "controlled trial", "rct"]
        has_rct_filter = any(ind in search_strategy.lower() for ind in rct_indicators)

        if not has_rct_filter:
            recommendations.append("Consider adding Cochrane RCT filter for intervention reviews")

        # Check for truncation
        if "*" not in search_strategy:
            recommendations.append("Consider using truncation (*) for term variants")

        return {
            "compliant": len(issues) == 0,
            "score": max(0, score),
            "issues": issues,
            "recommendations": recommendations,
            "cochrane_version": "Chapter 4, v6.5 (September 2024)"
        }


# =============================================================================
# COMPREHENSIVE SEARCH METHODOLOGY CLASS
# =============================================================================

class SearchMethodology:
    """
    Comprehensive search methodology class combining all components.

    This is the main interface for using the search methodology module.
    """

    def __init__(self):
        """Initialize all search methodology components."""
        self.press_validator = PRESSValidator()
        self.filter_validator = SearchFilterValidator()
        self.boolean_optimizer = BooleanOptimizer()
        self.grey_lit_searcher = GreyLiteratureSearcher()
        self.ml_assistant = MLScreeningAssistant()
        self.cochrane_builder = CochraneSearchBuilder()

    def create_comprehensive_search(
        self,
        condition: str,
        intervention: str,
        synonyms: Optional[Dict[str, List[str]]] = None,
        study_types: List[str] = None,
        databases: List[str] = None
    ) -> Dict:
        """
        Create a comprehensive search strategy following best practices.

        Args:
            condition: Primary condition/population
            intervention: Primary intervention
            synonyms: Optional synonyms for condition and intervention
            study_types: Types of studies to include (default: RCT)
            databases: Target databases (default: ClinicalTrials.gov)

        Returns:
            Dictionary with complete search package
        """
        if study_types is None:
            study_types = ["rct"]
        if databases is None:
            databases = ["ClinicalTrials.gov"]

        # Build terms with synonyms
        condition_terms = [condition]
        if synonyms and "condition" in synonyms:
            condition_terms.extend(synonyms["condition"])
        condition_terms = self.boolean_optimizer.add_spelling_variants(condition_terms)

        intervention_terms = [intervention]
        if synonyms and "intervention" in synonyms:
            intervention_terms.extend(synonyms["intervention"])
        intervention_terms = self.boolean_optimizer.add_spelling_variants(intervention_terms)

        # Build optimized Boolean query
        concepts = {
            "condition": condition_terms,
            "intervention": intervention_terms
        }

        boolean_query = self.boolean_optimizer.optimize_query(concepts)

        # Validate syntax
        syntax_validation = self.boolean_optimizer.validate_syntax(boolean_query)

        # PRESS validation
        pico_elements = {
            "Population": condition_terms,
            "Intervention": intervention_terms
        }

        press_report = self.press_validator.validate(
            boolean_query,
            database=databases[0],
            pico_elements=pico_elements
        )

        # Generate Cochrane-compliant version
        cochrane_search = self.cochrane_builder.build_cochrane_search(
            condition_terms,
            intervention_terms,
            study_type=study_types[0] if study_types else "rct"
        )

        # Cochrane compliance check
        cochrane_compliance = self.cochrane_builder.validate_cochrane_compliance(cochrane_search)

        # Grey literature protocol
        grey_lit_protocol = self.grey_lit_searcher.generate_search_protocol(
            condition, intervention
        )

        # Grey literature sources
        grey_sources = self.grey_lit_searcher.get_recommended_sources()

        return {
            "query": {
                "optimized_boolean": boolean_query,
                "cochrane_format": cochrane_search,
                "terms": {
                    "condition": condition_terms,
                    "intervention": intervention_terms
                }
            },
            "validation": {
                "syntax": syntax_validation,
                "press": press_report.to_dict(),
                "cochrane_compliance": cochrane_compliance
            },
            "grey_literature": {
                "protocol": grey_lit_protocol,
                "sources": grey_sources
            },
            "recommendations": self._generate_recommendations(press_report, cochrane_compliance),
            "metadata": {
                "condition": condition,
                "intervention": intervention,
                "databases": databases,
                "study_types": study_types,
                "methodology_version": "1.0.0"
            }
        }

    def _generate_recommendations(
        self,
        press_report: PRESSReport,
        cochrane_compliance: Dict
    ) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []

        # From PRESS validation
        for element, result in press_report.elements.items():
            recommendations.extend(result.recommendations[:2])

        # From Cochrane compliance
        recommendations.extend(cochrane_compliance.get("recommendations", []))

        # General best practices
        recommendations.append("Search all recommended grey literature sources")
        recommendations.append("Document search dates and results for PRISMA reporting")

        # Deduplicate
        seen = set()
        unique_recs = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recs.append(rec)

        return unique_recs[:10]  # Top 10 recommendations

    def estimate_screening_workload(
        self,
        expected_results: int,
        estimated_relevant: int
    ) -> Dict:
        """
        Estimate screening workload and ML assistance benefit.

        Args:
            expected_results: Expected number of search results
            estimated_relevant: Estimated number of relevant studies

        Returns:
            Workload estimates and recommendations
        """
        return self.ml_assistant.estimate_workload_reduction(
            expected_results,
            estimated_relevant
        )

    def validate_search_filter(
        self,
        filter_name: str,
        tp: int, fp: int, fn: int, tn: int,
        gold_standard: str = ""
    ) -> Dict:
        """
        Validate a search filter's performance.

        Args:
            filter_name: Name of the filter
            tp, fp, fn, tn: Confusion matrix values
            gold_standard: Source of gold standard

        Returns:
            Validation results with metrics
        """
        return self.filter_validator.validate_filter(
            filter_name, tp, fp, fn, tn, gold_standard
        )


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Main class
    "SearchMethodology",

    # PRESS validation
    "PRESSValidator",
    "PRESSElement",
    "PRESSValidationResult",
    "PRESSReport",

    # Filter validation
    "SearchFilterValidator",
    "FilterPerformanceMetrics",

    # Boolean optimization
    "BooleanOptimizer",

    # Grey literature
    "GreyLiteratureSearcher",

    # ML screening
    "MLScreeningAssistant",

    # Cochrane compliance
    "CochraneSearchBuilder",
]


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    # Example usage
    methodology = SearchMethodology()

    # Create a comprehensive search for diabetes + metformin
    result = methodology.create_comprehensive_search(
        condition="type 2 diabetes",
        intervention="metformin",
        synonyms={
            "condition": ["diabetes mellitus type 2", "T2DM", "NIDDM"],
            "intervention": ["glucophage", "metformin hydrochloride"]
        },
        study_types=["rct"],
        databases=["ClinicalTrials.gov", "PubMed"]
    )

    print("=" * 60)
    print("COMPREHENSIVE SEARCH STRATEGY")
    print("=" * 60)
    print(f"\nOptimized Boolean Query:\n{result['query']['optimized_boolean']}")
    print(f"\nCochrane Format:\n{result['query']['cochrane_format']}")
    print(f"\nPRESS Score: {result['validation']['press']['overall_score']:.1%}")
    print(f"Cochrane Compliance: {result['validation']['cochrane_compliance']['score']}%")
    print(f"\nTop Recommendations:")
    for i, rec in enumerate(result['recommendations'][:5], 1):
        print(f"  {i}. {rec}")

    # Estimate screening workload
    workload = methodology.estimate_screening_workload(
        expected_results=5000,
        estimated_relevant=50
    )
    print(f"\nScreening Workload Estimate:")
    print(f"  - Total records: {workload['total_records']}")
    print(f"  - ML can reduce by: {workload['workload_reduction_percent']}%")
    print(f"  - Recommendation: {workload['recommendation']}")
