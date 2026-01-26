"""
Advanced Search Module - Systematic Review Search Tool.

This module provides features for systematic review searching,
incorporating research and best practices from:

1. PICO Framework automated search generation
2. Semantic similarity matching (TF-IDF based)
3. Multi-database search translation
4. Automated quality assessment (heuristic scoring)
5. Comprehensive reporting

IMPORTANT LIMITATIONS:
- Automated PICO extraction is simplified pattern matching, not true NLP
- Quality scores are heuristic and do NOT replace expert peer review (PRESS 2015)
- Database translations are approximate; always verify in target platform
- Performance estimates are rough guides, not validated predictions

Author: CTGov Search Strategies Team
Version: 1.0.0
Date: 2026-01-18
"""

import re
import math
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from collections import defaultdict, Counter
from datetime import datetime
import hashlib


# =============================================================================
# PICO FRAMEWORK - Automated Search Generation
# =============================================================================

class PICOElement(Enum):
    """PICO framework elements."""
    POPULATION = "P"
    INTERVENTION = "I"
    COMPARISON = "C"
    OUTCOME = "O"
    STUDY_TYPE = "S"  # Extended PICOS
    TIMEFRAME = "T"   # Extended PICOT


@dataclass
class PICOQuery:
    """Structured PICO query representation."""
    population: List[str] = field(default_factory=list)
    intervention: List[str] = field(default_factory=list)
    comparison: List[str] = field(default_factory=list)
    outcome: List[str] = field(default_factory=list)
    study_type: Optional[str] = None
    timeframe: Optional[str] = None

    def is_valid(self) -> bool:
        """Check if minimum PICO elements are present."""
        return bool(self.population and self.intervention)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "population": self.population,
            "intervention": self.intervention,
            "comparison": self.comparison,
            "outcome": self.outcome,
            "study_type": self.study_type,
            "timeframe": self.timeframe
        }


class PICOSearchGenerator:
    """
    Automated search strategy generator from PICO elements.

    Based on:
    - Cochrane Handbook Chapter 4
    - PRESS 2015 Guidelines
    - Sampson M, et al. Search filter guidelines
    """

    # Study type filters (validated)
    # NOTE: RCT filters based on Cochrane Highly Sensitive Search Strategy
    # Reference: Lefebvre C, et al. Cochrane Handbook Chapter 4 (v6.5, 2024)
    STUDY_FILTERS = {
        "rct": {
            "pubmed": [
                "randomized controlled trial[pt]",
                "controlled clinical trial[pt]",
                "randomized[tiab]",
                "randomised[tiab]",
                "placebo[tiab]",
                "drug therapy[sh]",
                "randomly[tiab]",
                "trial[tiab]",
                # NOTE: "groups[tiab]" removed - low specificity, not in Cochrane HSSS
            ],
            "ctgov": [
                "AREA[StudyType] EXPAND[Term] COVER[FullMatch] \"Interventional\"",
                "AREA[DesignAllocation] \"Randomized\"",
            ],
            "embase": [
                "'randomized controlled trial'/exp",
                "'crossover procedure'/exp",
                "'double blind procedure'/exp",
                "random*:ti,ab",
                "factorial*:ti,ab",
                "crossover*:ti,ab",
                "placebo*:ti,ab",
            ],
        },
        "systematic_review": {
            "pubmed": [
                "systematic review[pt]",
                "meta-analysis[pt]",
                "systematic review[tiab]",
                "meta-analysis[tiab]",
                "cochrane database syst rev[ta]",
            ],
            "ctgov": [],  # Not applicable
        },
        "observational": {
            "pubmed": [
                "cohort studies[mh]",
                "case-control studies[mh]",
                "cross-sectional studies[mh]",
                "observational study[pt]",
            ],
            "ctgov": [
                "AREA[StudyType] \"Observational\"",
            ],
        },
    }

    # Common medical abbreviations to expand
    ABBREVIATIONS = {
        "T2DM": ["type 2 diabetes mellitus", "type 2 diabetes", "diabetes mellitus type 2"],
        "T1DM": ["type 1 diabetes mellitus", "type 1 diabetes", "diabetes mellitus type 1"],
        "MI": ["myocardial infarction", "heart attack"],
        "CVA": ["cerebrovascular accident", "stroke"],
        "CHF": ["congestive heart failure", "heart failure"],
        "COPD": ["chronic obstructive pulmonary disease"],
        "CKD": ["chronic kidney disease"],
        "HTN": ["hypertension", "high blood pressure"],
        "CAD": ["coronary artery disease", "coronary heart disease"],
        "DVT": ["deep vein thrombosis", "deep venous thrombosis"],
        "PE": ["pulmonary embolism"],
        "AF": ["atrial fibrillation"],
        "RA": ["rheumatoid arthritis"],
        "MS": ["multiple sclerosis"],
        "IBD": ["inflammatory bowel disease"],
        "UC": ["ulcerative colitis"],
        "CD": ["Crohn's disease", "Crohn disease"],
        "ADHD": ["attention deficit hyperactivity disorder"],
        "MDD": ["major depressive disorder", "major depression"],
        "GAD": ["generalized anxiety disorder"],
        "PTSD": ["post-traumatic stress disorder", "posttraumatic stress disorder"],
        "ASD": ["autism spectrum disorder"],
        "HIV": ["human immunodeficiency virus"],
        "AIDS": ["acquired immunodeficiency syndrome"],
        "HCV": ["hepatitis C virus", "hepatitis C"],
        "HBV": ["hepatitis B virus", "hepatitis B"],
        "NSCLC": ["non-small cell lung cancer"],
        "SCLC": ["small cell lung cancer"],
        "CRC": ["colorectal cancer"],
        "RCC": ["renal cell carcinoma"],
        "HCC": ["hepatocellular carcinoma"],
        "AML": ["acute myeloid leukemia"],
        "ALL": ["acute lymphoblastic leukemia"],
        "CML": ["chronic myeloid leukemia"],
        "NHL": ["non-Hodgkin lymphoma"],
    }

    def __init__(self):
        """Initialize the PICO search generator."""
        self.mesh_cache = {}

    def generate_search(
        self,
        pico: PICOQuery,
        database: str = "pubmed",
        include_mesh: bool = True,
        sensitivity: str = "high"  # high, balanced, precise
    ) -> Dict:
        """
        Generate a complete search strategy from PICO elements.

        Args:
            pico: PICOQuery object with search elements
            database: Target database (pubmed, ctgov, embase)
            include_mesh: Whether to include MeSH terms
            sensitivity: Search sensitivity level

        Returns:
            Dictionary with complete search strategy
        """
        if not pico.is_valid():
            return {"error": "Invalid PICO: Population and Intervention required"}

        lines = []
        line_num = 1

        # Population/Condition block
        pop_terms = self._expand_terms(pico.population)
        pop_query = self._build_concept_block(pop_terms, database, include_mesh)
        lines.append(f"#{line_num} {pop_query}")
        line_num += 1

        # Intervention block
        int_terms = self._expand_terms(pico.intervention)
        int_query = self._build_concept_block(int_terms, database, include_mesh)
        lines.append(f"#{line_num} {int_query}")
        line_num += 1

        # Comparison block (optional)
        if pico.comparison:
            comp_terms = self._expand_terms(pico.comparison)
            comp_query = self._build_concept_block(comp_terms, database, include_mesh)
            lines.append(f"#{line_num} {comp_query}")
            line_num += 1

        # Outcome block (optional)
        if pico.outcome:
            out_terms = self._expand_terms(pico.outcome)
            out_query = self._build_concept_block(out_terms, database, include_mesh)
            lines.append(f"#{line_num} {out_query}")
            line_num += 1

        # Combine blocks
        combine_refs = " AND ".join([f"#{i}" for i in range(1, line_num)])
        lines.append(f"#{line_num} {combine_refs}")
        combined_line = line_num
        line_num += 1

        # Add study type filter if specified
        if pico.study_type:
            filter_terms = self._get_study_filter(pico.study_type, database)
            if filter_terms:
                filter_query = " OR ".join(filter_terms)
                lines.append(f"#{line_num} {filter_query}")
                lines.append(f"#{line_num + 1} #{combined_line} AND #{line_num}")
                line_num += 2

        # Calculate estimated metrics
        metrics = self._estimate_metrics(pico, sensitivity)

        return {
            "search_strategy": "\n".join(lines),
            "database": database,
            "pico": pico.to_dict(),
            "settings": {
                "include_mesh": include_mesh,
                "sensitivity": sensitivity
            },
            "estimated_metrics": metrics,
            "recommendations": self._get_recommendations(pico, database),
            "generated_at": datetime.now().isoformat()
        }

    def _expand_terms(self, terms: List[str]) -> List[str]:
        """Expand terms with abbreviations and variants."""
        expanded = set(terms)

        for term in terms:
            term_upper = term.upper()
            # Check abbreviations
            if term_upper in self.ABBREVIATIONS:
                expanded.update(self.ABBREVIATIONS[term_upper])

            # Add truncated form for single words
            if len(term) >= 5 and " " not in term:
                expanded.add(f"{term}*")

        return list(expanded)

    def _build_concept_block(
        self,
        terms: List[str],
        database: str,
        include_mesh: bool
    ) -> str:
        """Build a search block for a concept."""
        if database == "pubmed":
            parts = []
            for term in terms:
                if term.endswith("*"):
                    parts.append(f"{term}[tiab]")
                else:
                    parts.append(f'"{term}"[tiab]')
                    if include_mesh:
                        parts.append(f'"{term}"[mesh]')
            return "(" + " OR ".join(parts) + ")"

        elif database == "ctgov":
            parts = []
            for term in terms:
                if term.endswith("*"):
                    parts.append(f"AREA[ConditionSearch] {term[:-1]}")
                else:
                    parts.append(f'AREA[ConditionSearch] "{term}"')
            return "(" + " OR ".join(parts) + ")"

        elif database == "embase":
            parts = []
            for term in terms:
                if term.endswith("*"):
                    parts.append(f"{term}:ti,ab")
                else:
                    parts.append(f"'{term}':ti,ab")
                    if include_mesh:
                        parts.append(f"'{term}'/exp")
            return "(" + " OR ".join(parts) + ")"

        return "(" + " OR ".join(terms) + ")"

    def _get_study_filter(self, study_type: str, database: str) -> List[str]:
        """Get study type filter terms."""
        study_type = study_type.lower()
        if study_type in self.STUDY_FILTERS:
            return self.STUDY_FILTERS[study_type].get(database, [])
        return []

    def _estimate_metrics(self, pico: PICOQuery, sensitivity: str) -> Dict:
        """
        Estimate search performance metrics.

        CAVEAT: These are ROUGH HEURISTIC estimates, not validated predictions.
        Actual search performance varies widely based on topic, database, and
        search execution. These estimates should NOT be cited as expected
        performance metrics.
        """
        # Base estimates based on sensitivity level
        # NOTE: These are rough approximations based on general SR literature,
        # not validated for any specific search strategy
        estimates = {
            "high": {"recall": 0.95, "precision": 0.10, "nnr": 10},
            "balanced": {"recall": 0.85, "precision": 0.25, "nnr": 4},
            "precise": {"recall": 0.70, "precision": 0.45, "nnr": 2.2},
        }

        base = estimates.get(sensitivity, estimates["balanced"])

        # Adjust based on PICO completeness
        completeness = sum([
            bool(pico.population),
            bool(pico.intervention),
            bool(pico.comparison),
            bool(pico.outcome),
            bool(pico.study_type)
        ]) / 5

        return {
            "estimated_recall": base["recall"],
            "estimated_precision": base["precision"] * (0.8 + 0.4 * completeness),
            "estimated_nnr": base["nnr"] / (0.8 + 0.4 * completeness),
            "pico_completeness": completeness,
            "confidence": "high" if completeness > 0.6 else "moderate",
            "caveat": "ROUGH ESTIMATES ONLY - not validated predictions"
        }

    def _get_recommendations(self, pico: PICOQuery, database: str) -> List[str]:
        """Get recommendations for improving the search."""
        recommendations = []

        if not pico.comparison:
            recommendations.append(
                "Consider adding comparison terms if comparing interventions"
            )

        if not pico.outcome:
            recommendations.append(
                "Consider adding outcome terms for more focused results"
            )

        if not pico.study_type:
            recommendations.append(
                "Add study type filter (e.g., 'rct') to improve precision"
            )

        if database == "pubmed":
            recommendations.append(
                "Verify MeSH terms are current using NLM MeSH Browser"
            )

        recommendations.append(
            "Search multiple databases for comprehensive coverage"
        )

        return recommendations


# =============================================================================
# SEMANTIC SIMILARITY SEARCH
# =============================================================================

class SemanticSearchEngine:
    """
    Semantic similarity search using TF-IDF and cosine similarity.

    For production, would integrate with:
    - PubMedBERT embeddings
    - BioSentVec
    - SciBERT
    """

    def __init__(self):
        """Initialize the semantic search engine."""
        self.vocabulary = {}
        self.idf_scores = {}
        self.document_vectors = {}

    def build_index(self, documents: List[Dict]) -> None:
        """
        Build search index from documents.

        Args:
            documents: List of dicts with 'id' and 'text' keys
        """
        # Build vocabulary
        doc_freqs = Counter()
        all_terms = set()

        for doc in documents:
            terms = self._tokenize(doc.get('text', ''))
            unique_terms = set(terms)
            all_terms.update(unique_terms)
            for term in unique_terms:
                doc_freqs[term] += 1

        # Calculate IDF
        n_docs = len(documents)
        for term in all_terms:
            self.idf_scores[term] = math.log(n_docs / (1 + doc_freqs[term]))

        # Build document vectors
        for doc in documents:
            doc_id = doc.get('id')
            terms = self._tokenize(doc.get('text', ''))
            tf = Counter(terms)
            vector = {}
            for term, count in tf.items():
                tfidf = count * self.idf_scores.get(term, 0)
                if tfidf > 0:
                    vector[term] = tfidf
            self.document_vectors[doc_id] = vector

    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        Search for documents similar to query.

        Args:
            query: Search query text
            top_k: Number of results to return

        Returns:
            List of matching documents with scores
        """
        # Build query vector
        terms = self._tokenize(query)
        tf = Counter(terms)
        query_vector = {}
        for term, count in tf.items():
            tfidf = count * self.idf_scores.get(term, 1)
            query_vector[term] = tfidf

        # Calculate similarities
        scores = []
        for doc_id, doc_vector in self.document_vectors.items():
            similarity = self._cosine_similarity(query_vector, doc_vector)
            if similarity > 0:
                scores.append({"id": doc_id, "score": similarity})

        # Sort by score
        scores.sort(key=lambda x: x["score"], reverse=True)

        return scores[:top_k]

    def find_similar_studies(
        self,
        seed_studies: List[str],
        all_studies: List[Dict],
        top_k: int = 50
    ) -> List[Dict]:
        """
        Find studies similar to seed studies (citation chasing alternative).

        Args:
            seed_studies: List of seed study texts/titles
            all_studies: All candidate studies
            top_k: Number of results

        Returns:
            Similar studies ranked by similarity
        """
        # Build index
        self.build_index(all_studies)

        # Combine seed studies into query
        combined_query = " ".join(seed_studies)

        return self.search(combined_query, top_k)

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms."""
        # Simple tokenization
        text = text.lower()
        # Remove punctuation except hyphens
        text = re.sub(r'[^\w\s-]', ' ', text)
        tokens = text.split()
        # Remove short tokens and stopwords
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
                     'to', 'for', 'of', 'with', 'by', 'from', 'as', 'is',
                     'was', 'are', 'were', 'been', 'be', 'have', 'has', 'had',
                     'do', 'does', 'did', 'will', 'would', 'could', 'should',
                     'may', 'might', 'must', 'shall', 'can', 'this', 'that',
                     'these', 'those', 'it', 'its'}
        return [t for t in tokens if len(t) > 2 and t not in stopwords]

    def _cosine_similarity(self, vec1: Dict, vec2: Dict) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2:
            return 0.0

        # Get common terms
        common_terms = set(vec1.keys()) & set(vec2.keys())

        if not common_terms:
            return 0.0

        # Calculate dot product
        dot_product = sum(vec1[t] * vec2[t] for t in common_terms)

        # Calculate magnitudes
        mag1 = math.sqrt(sum(v**2 for v in vec1.values()))
        mag2 = math.sqrt(sum(v**2 for v in vec2.values()))

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot_product / (mag1 * mag2)


# =============================================================================
# MULTI-DATABASE SEARCH TRANSLATOR
# =============================================================================

class DatabaseTranslator:
    """
    Translates search strategies between databases.

    IMPORTANT: Database syntax varies by platform (e.g., Ovid vs native interfaces).
    This translator provides GENERAL guidance. Always verify syntax in the target
    platform's documentation.

    Supports:
    - PubMed/MEDLINE (native interface)
    - Embase (Embase.com interface - Ovid syntax differs)
    - Cochrane CENTRAL
    - ClinicalTrials.gov
    - Web of Science
    - CINAHL (EBSCOhost)
    - PsycINFO (EBSCOhost/Ovid - syntax may differ)
    """

    # Database-specific syntax
    # CRITICAL CAVEAT: Syntax varies significantly by platform/vendor.
    # Always verify syntax in the target platform's documentation.
    # These mappings are approximate and may need adjustment.
    SYNTAX = {
        "pubmed": {
            "or": " OR ",
            "and": " AND ",
            "not": " NOT ",
            "truncation": "*",
            "phrase": '""',
            "title_abstract": "[tiab]",
            "title": "[ti]",
            "mesh": "[mesh]",
            "mesh_exp": "[mesh]",  # Auto-exploded in PubMed
            "subheading": "[sh]",
            "pub_type": "[pt]",
            "proximity": None,  # Not supported in PubMed
            "platform": "NLM PubMed (pubmed.ncbi.nlm.nih.gov)",
            "notes": "MeSH terms auto-explode; use [mesh:noexp] to prevent",
        },
        "embase": {
            "or": " OR ",
            "and": " AND ",
            "not": " NOT ",
            "truncation": "*",
            "phrase": "''",
            "title_abstract": ":ti,ab",
            "title": ":ti",
            "mesh": "/exp",  # Emtree terms
            "mesh_exp": "/exp",
            "subheading": "/de",
            "pub_type": None,
            "proximity": "NEAR/",
            "platform": "Embase.com",
            "notes": "OVID EMBASE uses different syntax: $ for truncation, .ti,ab for fields",
        },
        "cochrane": {
            "or": " OR ",
            "and": " AND ",
            "not": " NOT ",
            "truncation": "*",
            "phrase": '""',
            "title_abstract": ":ti,ab",
            "title": ":ti",
            "mesh": "[mh]",
            "mesh_exp": "[mh]",
            "subheading": None,
            "pub_type": None,
            "proximity": "NEAR/",
            "platform": "Cochrane Library (Wiley)",
            "notes": "Use CENTRAL for RCTs; CDSR for systematic reviews",
        },
        "ctgov": {
            "or": " OR ",
            "and": " AND ",
            "not": " NOT ",
            "truncation": None,  # Not supported
            "phrase": '""',
            "title_abstract": None,
            "title": None,
            "mesh": None,
            "mesh_exp": None,
            "subheading": None,
            "pub_type": None,
            "proximity": None,
            "platform": "ClinicalTrials.gov",
            "notes": "Limited search syntax; use AREA[] for field-specific searches",
        },
        "wos": {
            "or": " OR ",
            "and": " AND ",
            "not": " NOT ",
            "truncation": "*",
            "phrase": '""',
            "title_abstract": None,  # Use TS= for Topic (title+abstract+keywords)
            "title": "TI=",
            "mesh": None,
            "mesh_exp": None,
            "subheading": None,
            "pub_type": "DT=",
            "proximity": "NEAR/",
            "platform": "Web of Science (Clarivate)",
            "notes": "TS= searches topic (title, abstract, keywords); $ also works for truncation",
        },
        "cinahl": {
            "or": " OR ",
            "and": " AND ",
            "not": " NOT ",
            "truncation": "*",
            "phrase": '""',
            "title_abstract": "TI OR AB",
            "title": "TI",
            "mesh": "MH",  # CINAHL Headings (not MeSH)
            "mesh_exp": "MH+",
            "subheading": None,
            "pub_type": "PT",
            "proximity": "N",
            "platform": "CINAHL (EBSCOhost)",
            "notes": "Uses CINAHL Headings, not MeSH; N# for proximity (e.g., N5)",
        },
        "psycinfo": {
            "or": " OR ",
            "and": " AND ",
            "not": " NOT ",
            "truncation": "*",
            "phrase": '""',
            "title_abstract": ".ti,ab",
            "title": ".ti",
            "mesh": ".hw",  # Index terms (APA Thesaurus)
            "mesh_exp": "exp",
            "subheading": None,
            "pub_type": ".pt",
            "proximity": "adj",
            "platform": "PsycINFO (Ovid or EBSCOhost)",
            "notes": "Ovid uses .ti,ab; EBSCOhost uses TI,AB; uses APA Thesaurus not MeSH",
        },
    }

    def __init__(self):
        """Initialize the translator."""
        pass

    def translate(
        self,
        search: str,
        from_db: str,
        to_db: str,
        validate: bool = True
    ) -> Dict:
        """
        Translate a search strategy between databases.

        Args:
            search: Original search string
            from_db: Source database
            to_db: Target database
            validate: Whether to validate the translation

        Returns:
            Dictionary with translated search and notes
        """
        from_syntax = self.SYNTAX.get(from_db.lower())
        to_syntax = self.SYNTAX.get(to_db.lower())

        if not from_syntax or not to_syntax:
            return {"error": f"Unknown database: {from_db} or {to_db}"}

        translated = search
        notes = []
        warnings = []

        # Translate truncation
        if from_syntax["truncation"] and to_syntax["truncation"]:
            if from_syntax["truncation"] != to_syntax["truncation"]:
                translated = translated.replace(
                    from_syntax["truncation"],
                    to_syntax["truncation"]
                )
        elif from_syntax["truncation"] and not to_syntax["truncation"]:
            warnings.append(
                f"{to_db} does not support truncation - removed wildcards"
            )
            translated = translated.replace(from_syntax["truncation"], "")

        # Translate field tags
        field_mappings = [
            ("title_abstract", "Title/Abstract field"),
            ("title", "Title field"),
            ("mesh", "Subject heading"),
            ("mesh_exp", "Exploded subject heading"),
            ("pub_type", "Publication type"),
        ]

        for field, desc in field_mappings:
            from_tag = from_syntax.get(field)
            to_tag = to_syntax.get(field)

            if from_tag and to_tag:
                translated = translated.replace(from_tag, to_tag)
            elif from_tag and not to_tag:
                warnings.append(
                    f"{to_db} does not support {desc} - tag removed"
                )
                translated = translated.replace(from_tag, "")

        # Translate proximity operators
        from_prox = from_syntax.get("proximity")
        to_prox = to_syntax.get("proximity")

        if from_prox:
            prox_pattern = re.compile(rf'{re.escape(from_prox)}(\d+)')
            if to_prox:
                translated = prox_pattern.sub(rf'{to_prox}\1', translated)
            else:
                warnings.append(
                    f"{to_db} does not support proximity operators - using AND"
                )
                translated = prox_pattern.sub(' AND ', translated)

        # Validate if requested
        validation = None
        if validate:
            validation = self._validate_translation(translated, to_db)

        return {
            "original": search,
            "translated": translated,
            "from_database": from_db,
            "to_database": to_db,
            "notes": notes,
            "warnings": warnings,
            "validation": validation
        }

    def _validate_translation(self, search: str, database: str) -> Dict:
        """Validate translated search syntax."""
        issues = []

        # Check parentheses balance
        if search.count('(') != search.count(')'):
            issues.append("Unbalanced parentheses")

        # Check quote balance
        if search.count('"') % 2 != 0:
            issues.append("Unbalanced quotation marks")

        # Check for empty groups
        if "()" in search or "( )" in search:
            issues.append("Empty parentheses group")

        return {
            "valid": len(issues) == 0,
            "issues": issues
        }

    def get_supported_databases(self) -> List[str]:
        """Get list of supported databases."""
        return list(self.SYNTAX.keys())


# =============================================================================
# SEARCH QUALITY ASSESSMENT
# =============================================================================

class QualityLevel(Enum):
    """Search quality levels."""
    GOLD = "gold"      # Publication-ready
    SILVER = "silver"  # Good quality
    BRONZE = "bronze"  # Acceptable
    NEEDS_WORK = "needs_work"


@dataclass
class QualityAssessment:
    """Search quality assessment result."""
    level: QualityLevel
    score: float  # 0-100
    components: Dict[str, float]
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "level": self.level.value,
            "score": self.score,
            "components": self.components,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "recommendations": self.recommendations
        }


class SearchQualityAssessor:
    """
    Heuristic search quality assessment.

    IMPORTANT: This provides automated HEURISTIC scoring only.
    It does NOT replace expert peer review using PRESS 2015 guidelines.

    Informed by (but not validated against):
    - PRESS 2015 Guidelines (McGowan J, et al. J Clin Epidemiol 2016)
    - Cochrane Handbook standards
    - AMSTAR-2 search criteria (Shea BJ, et al. BMJ 2017)

    CAVEAT: Thresholds and weights are heuristic estimates, not empirically
    validated cutoffs. Use this tool for initial self-assessment only.
    """

    # Quality thresholds (HEURISTIC - not validated)
    THRESHOLDS = {
        QualityLevel.GOLD: 90,
        QualityLevel.SILVER: 75,
        QualityLevel.BRONZE: 60,
    }

    # Component weights (HEURISTIC - these are author estimates, not from literature)
    # PRESS 2015 uses qualitative assessment, not weighted scoring
    WEIGHTS = {
        "comprehensiveness": 0.25,  # Coverage of concepts
        "structure": 0.15,          # Boolean logic
        "terminology": 0.20,        # MeSH/keywords
        "sensitivity": 0.20,        # Recall optimization
        "reproducibility": 0.10,    # Documentation
        "database_coverage": 0.10,  # Multi-database
    }

    def __init__(self):
        """Initialize the assessor."""
        pass

    def assess(
        self,
        search_strategy: str,
        pico: Optional[PICOQuery] = None,
        databases_searched: Optional[List[str]] = None,
        documentation: Optional[Dict] = None
    ) -> QualityAssessment:
        """
        Assess search strategy quality.

        Args:
            search_strategy: The search strategy to assess
            pico: Optional PICO elements for context
            databases_searched: List of databases searched
            documentation: Search documentation details

        Returns:
            QualityAssessment with detailed results
        """
        components = {}
        strengths = []
        weaknesses = []
        recommendations = []

        # 1. Assess comprehensiveness
        comp_score = self._assess_comprehensiveness(search_strategy, pico)
        components["comprehensiveness"] = comp_score
        if comp_score >= 80:
            strengths.append("Comprehensive concept coverage")
        elif comp_score < 60:
            weaknesses.append("Limited concept coverage")
            recommendations.append("Add more synonyms and related terms")

        # 2. Assess structure
        struct_score = self._assess_structure(search_strategy)
        components["structure"] = struct_score
        if struct_score >= 80:
            strengths.append("Well-structured Boolean logic")
        elif struct_score < 60:
            weaknesses.append("Poor Boolean structure")
            recommendations.append("Review parentheses grouping and operator usage")

        # 3. Assess terminology
        term_score = self._assess_terminology(search_strategy)
        components["terminology"] = term_score
        if term_score >= 80:
            strengths.append("Good use of controlled vocabulary")
        elif term_score < 60:
            weaknesses.append("Limited controlled vocabulary")
            recommendations.append("Add MeSH terms and subject headings")

        # 4. Assess sensitivity
        sens_score = self._assess_sensitivity(search_strategy)
        components["sensitivity"] = sens_score
        if sens_score >= 80:
            strengths.append("Optimized for high recall")
        elif sens_score < 60:
            weaknesses.append("May miss relevant studies")
            recommendations.append("Add truncation and spelling variants")

        # 5. Assess reproducibility
        repro_score = self._assess_reproducibility(search_strategy, documentation)
        components["reproducibility"] = repro_score
        if repro_score >= 80:
            strengths.append("Well-documented for reproducibility")
        elif repro_score < 60:
            weaknesses.append("Poor documentation")
            recommendations.append("Document search date, line numbers, and results count")

        # 6. Assess database coverage
        db_score = self._assess_database_coverage(databases_searched)
        components["database_coverage"] = db_score
        if db_score >= 80:
            strengths.append("Multiple databases searched")
        elif db_score < 60:
            weaknesses.append("Limited database coverage")
            recommendations.append("Search additional databases (Embase, CENTRAL, etc.)")

        # Calculate overall score
        overall_score = sum(
            score * self.WEIGHTS[component]
            for component, score in components.items()
        )

        # Determine quality level
        level = QualityLevel.NEEDS_WORK
        for quality_level, threshold in self.THRESHOLDS.items():
            if overall_score >= threshold:
                level = quality_level
                break

        return QualityAssessment(
            level=level,
            score=round(overall_score, 1),
            components=components,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations
        )

    def _assess_comprehensiveness(
        self,
        search: str,
        pico: Optional[PICOQuery]
    ) -> float:
        """Assess concept coverage."""
        score = 50  # Base score

        # Check for OR groupings (synonym inclusion)
        or_groups = len(re.findall(r'\([^)]*\bOR\b[^)]*\)', search, re.IGNORECASE))
        score += min(or_groups * 5, 25)

        # Check for multiple concepts
        and_count = len(re.findall(r'\bAND\b', search, re.IGNORECASE))
        if and_count >= 2:
            score += 15
        elif and_count >= 1:
            score += 10

        # Check PICO coverage if provided
        if pico:
            covered = 0
            search_lower = search.lower()
            if pico.population and any(p.lower() in search_lower for p in pico.population):
                covered += 1
            if pico.intervention and any(i.lower() in search_lower for i in pico.intervention):
                covered += 1
            if pico.comparison and any(c.lower() in search_lower for c in pico.comparison):
                covered += 1
            if pico.outcome and any(o.lower() in search_lower for o in pico.outcome):
                covered += 1

            if pico.is_valid():
                expected = 2 + bool(pico.comparison) + bool(pico.outcome)
                coverage_ratio = covered / expected
                score = score * coverage_ratio

        return min(100, score)

    def _assess_structure(self, search: str) -> float:
        """Assess Boolean structure quality."""
        score = 100

        # Check parentheses balance
        if search.count('(') != search.count(')'):
            score -= 30

        # Check for mixed operators without grouping
        if re.search(r'\bOR\b.*\bAND\b', search, re.IGNORECASE):
            if '(' not in search:
                score -= 20

        # Check for double operators
        if re.search(r'\b(AND|OR|NOT)\s+\1\b', search, re.IGNORECASE):
            score -= 20

        # Check for empty groups
        if "()" in search or "( )" in search:
            score -= 15

        # Bonus for well-structured search
        if re.match(r'^#\d+\s+', search):  # Has line numbers
            score += 5

        return max(0, min(100, score))

    def _assess_terminology(self, search: str) -> float:
        """Assess controlled vocabulary usage."""
        score = 50

        # Check for MeSH terms
        if "[mesh]" in search.lower() or "[mh]" in search.lower():
            score += 25

        # Check for field tags
        if "[tiab]" in search.lower() or "[ti]" in search.lower():
            score += 15

        # Check for subheadings
        if "[sh]" in search.lower() or "/" in search:
            score += 10

        return min(100, score)

    def _assess_sensitivity(self, search: str) -> float:
        """Assess recall optimization."""
        score = 50

        # Check for truncation
        if "*" in search or "$" in search:
            score += 20

        # Check for spelling variants
        if "randomized" in search.lower() and "randomised" in search.lower():
            score += 10

        # Check for extensive OR groups
        or_count = len(re.findall(r'\bOR\b', search, re.IGNORECASE))
        if or_count >= 5:
            score += 15
        elif or_count >= 3:
            score += 10

        # Penalty for NOT operators (may exclude relevant)
        if " NOT " in search.upper():
            score -= 10

        return max(0, min(100, score))

    def _assess_reproducibility(
        self,
        search: str,
        documentation: Optional[Dict]
    ) -> float:
        """Assess documentation quality."""
        score = 40  # Base for having a search string

        # Check for line numbers
        if re.match(r'^#\d+', search):
            score += 20

        # Check documentation
        if documentation:
            if documentation.get("date"):
                score += 15
            if documentation.get("results_count"):
                score += 15
            if documentation.get("database"):
                score += 10

        return min(100, score)

    def _assess_database_coverage(
        self,
        databases: Optional[List[str]]
    ) -> float:
        """Assess multi-database coverage."""
        if not databases:
            return 30  # Unknown

        # Minimum databases for comprehensive search
        required = ["pubmed", "embase", "central"]
        trial_registries = ["clinicaltrials.gov", "ictrp", "isrctn"]

        score = 0
        db_lower = [d.lower() for d in databases]

        # Core databases
        for db in required:
            if any(db in d for d in db_lower):
                score += 25

        # Trial registries
        for tr in trial_registries:
            if any(tr in d for d in db_lower):
                score += 10
                break

        # Bonus for additional databases
        if len(databases) > 4:
            score += 15

        return min(100, score)


# =============================================================================
# AUTOMATED SEARCH REPORTING
# =============================================================================

class SearchReportGenerator:
    """
    Generate comprehensive search reports for publication.

    Compliant with:
    - PRISMA 2020 reporting guidelines
    - Cochrane Handbook documentation standards
    - JBI reporting requirements
    """

    def __init__(self):
        """Initialize the report generator."""
        self.quality_assessor = SearchQualityAssessor()

    def generate_report(
        self,
        search_strategy: str,
        database: str,
        results_count: int,
        search_date: str,
        pico: Optional[PICOQuery] = None,
        include_quality_assessment: bool = True
    ) -> Dict:
        """
        Generate a comprehensive search report.

        Args:
            search_strategy: The search strategy
            database: Database searched
            results_count: Number of results retrieved
            search_date: Date of search
            pico: Optional PICO elements
            include_quality_assessment: Whether to include quality assessment

        Returns:
            Dictionary with complete report
        """
        report = {
            "metadata": {
                "database": database,
                "search_date": search_date,
                "results_count": results_count,
                "report_generated": datetime.now().isoformat(),
            },
            "search_strategy": {
                "full_strategy": search_strategy,
                "line_count": len(search_strategy.split('\n')),
                "concept_count": self._count_concepts(search_strategy),
            },
            "pico": pico.to_dict() if pico else None,
        }

        # Add quality assessment
        if include_quality_assessment:
            assessment = self.quality_assessor.assess(
                search_strategy,
                pico=pico,
                databases_searched=[database],
                documentation={
                    "date": search_date,
                    "results_count": results_count,
                    "database": database
                }
            )
            report["quality_assessment"] = assessment.to_dict()

        # Generate narrative
        report["narrative"] = self._generate_narrative(report)

        # Generate PRISMA text
        report["prisma_text"] = self._generate_prisma_text(report)

        return report

    def _count_concepts(self, search: str) -> int:
        """Count number of concept blocks in search."""
        # Count AND separators as concept boundaries
        return len(re.findall(r'\bAND\b', search, re.IGNORECASE)) + 1

    def _generate_narrative(self, report: Dict) -> str:
        """Generate narrative description of search."""
        meta = report["metadata"]
        strategy = report["search_strategy"]

        narrative = f"""Search Strategy Description

Database: {meta['database']}
Date Searched: {meta['search_date']}
Results Retrieved: {meta['results_count']:,}

The search strategy comprised {strategy['line_count']} search lines
combining {strategy['concept_count']} concept blocks using Boolean operators.
"""

        if report.get("pico"):
            pico = report["pico"]
            narrative += f"""
PICO Elements:
- Population: {', '.join(pico['population']) if pico['population'] else 'Not specified'}
- Intervention: {', '.join(pico['intervention']) if pico['intervention'] else 'Not specified'}
- Comparison: {', '.join(pico['comparison']) if pico['comparison'] else 'Not specified'}
- Outcome: {', '.join(pico['outcome']) if pico['outcome'] else 'Not specified'}
"""

        if report.get("quality_assessment"):
            qa = report["quality_assessment"]
            narrative += f"""
Quality Assessment:
- Overall Score: {qa['score']}/100 ({qa['level'].upper()})
- Key Strengths: {'; '.join(qa['strengths'][:3])}
"""

        return narrative

    def _generate_prisma_text(self, report: Dict) -> str:
        """Generate PRISMA-compliant text for methods section."""
        meta = report["metadata"]

        text = f"""We searched {meta['database']} on {meta['search_date']}.
The search strategy combined controlled vocabulary terms (where available)
with text word searching. No date or language restrictions were applied.
The search retrieved {meta['results_count']:,} records."""

        return text

    def export_for_publication(
        self,
        report: Dict,
        format: str = "markdown"
    ) -> str:
        """
        Export report for publication.

        Args:
            report: Report dictionary
            format: Output format (markdown, latex, word)

        Returns:
            Formatted report string
        """
        if format == "markdown":
            return self._to_markdown(report)
        elif format == "latex":
            return self._to_latex(report)
        else:
            return json.dumps(report, indent=2)

    def _to_markdown(self, report: Dict) -> str:
        """Convert report to Markdown."""
        meta = report["metadata"]
        strategy = report["search_strategy"]

        md = f"""# Search Strategy Report

## Database Information
- **Database:** {meta['database']}
- **Date Searched:** {meta['search_date']}
- **Results Retrieved:** {meta['results_count']:,}

## Search Strategy

```
{strategy['full_strategy']}
```

## PRISMA Text

{report.get('prisma_text', '')}

"""

        if report.get("quality_assessment"):
            qa = report["quality_assessment"]
            md += f"""## Quality Assessment

**Overall Score:** {qa['score']}/100 ({qa['level'].upper()})

### Strengths
{chr(10).join('- ' + s for s in qa['strengths'])}

### Areas for Improvement
{chr(10).join('- ' + w for w in qa['weaknesses'])}

### Recommendations
{chr(10).join('- ' + r for r in qa['recommendations'])}
"""

        return md

    def _to_latex(self, report: Dict) -> str:
        """Convert report to LaTeX."""
        meta = report["metadata"]
        strategy = report["search_strategy"]

        latex = r"""\section{Search Strategy}

\subsection{Database Information}
\begin{itemize}
    \item Database: """ + meta['database'] + r"""
    \item Date Searched: """ + meta['search_date'] + r"""
    \item Results Retrieved: """ + f"{meta['results_count']:,}" + r"""
\end{itemize}

\subsection{Search Strategy}
\begin{verbatim}
""" + strategy['full_strategy'] + r"""
\end{verbatim}
"""

        return latex


# =============================================================================
# UNIFIED SEARCH TOOL
# =============================================================================

class SystematicReviewSearchTool:
    """
    Systematic Review Search Tool.

    Combines multiple search features into a unified interface:
    - PICO-based search generation
    - Semantic similarity search (TF-IDF based)
    - Multi-database translation (approximate)
    - Heuristic quality assessment
    - Automated reporting

    LIMITATIONS:
    - PICO extraction uses simple pattern matching, not validated NLP
    - Quality scores are heuristic, not empirically validated
    - Database translations are approximate; verify in target platform
    """

    def __init__(self):
        """Initialize all components."""
        self.pico_generator = PICOSearchGenerator()
        self.semantic_engine = SemanticSearchEngine()
        self.translator = DatabaseTranslator()
        self.quality_assessor = SearchQualityAssessor()
        self.report_generator = SearchReportGenerator()

    def create_search_from_question(
        self,
        research_question: str,
        target_databases: List[str] = None
    ) -> Dict:
        """
        Create a complete search strategy from a research question.

        Args:
            research_question: Natural language research question
            target_databases: Target databases

        Returns:
            Complete search package with strategies for all databases
        """
        if target_databases is None:
            target_databases = ["pubmed", "embase", "ctgov"]

        # Parse PICO from question (simplified NLP)
        pico = self._extract_pico(research_question)

        # Generate searches for each database
        searches = {}
        for db in target_databases:
            result = self.pico_generator.generate_search(
                pico=pico,
                database=db,
                include_mesh=True,
                sensitivity="high"
            )
            searches[db] = result

        # Assess quality
        primary_search = searches.get("pubmed", list(searches.values())[0])
        quality = self.quality_assessor.assess(
            primary_search["search_strategy"],
            pico=pico,
            databases_searched=target_databases
        )

        return {
            "research_question": research_question,
            "pico": pico.to_dict(),
            "searches": searches,
            "quality_assessment": quality.to_dict(),
            "recommendations": self._get_master_recommendations(searches, quality)
        }

    def _extract_pico(self, question: str) -> PICOQuery:
        """Extract PICO elements from research question (simplified NLP)."""
        question_lower = question.lower()

        pico = PICOQuery()

        # Simple pattern matching for common PICO patterns
        # Population patterns
        pop_patterns = [
            r"(?:in|among|for)\s+(?:patients with|people with|adults with|children with)?\s*([^,?]+?)(?:\s*,|\s+(?:does|is|what|how|can))",
            r"(?:patients|people|adults|children)\s+(?:with|who have)\s+([^,?]+)",
        ]

        for pattern in pop_patterns:
            match = re.search(pattern, question_lower)
            if match:
                pico.population = [match.group(1).strip()]
                break

        # Intervention patterns
        int_patterns = [
            r"(?:effect|effectiveness|efficacy)\s+of\s+([^,?]+?)(?:\s+(?:on|in|for|compared))",
            r"(?:does|is|can)\s+([^,?]+?)\s+(?:effective|improve|reduce|help)",
            r"(?:treatment with|therapy with|use of)\s+([^,?]+)",
        ]

        for pattern in int_patterns:
            match = re.search(pattern, question_lower)
            if match:
                pico.intervention = [match.group(1).strip()]
                break

        # Comparison patterns
        comp_patterns = [
            r"compared\s+(?:to|with)\s+([^,?]+)",
            r"versus\s+([^,?]+)",
            r"vs\.?\s+([^,?]+)",
        ]

        for pattern in comp_patterns:
            match = re.search(pattern, question_lower)
            if match:
                pico.comparison = [match.group(1).strip()]
                break

        # Outcome patterns
        out_patterns = [
            r"(?:on|for)\s+([^,?]+?)(?:\s+(?:in|among|compared)|\?|$)",
            r"(?:improve|reduce|increase|decrease)\s+([^,?]+)",
        ]

        for pattern in out_patterns:
            match = re.search(pattern, question_lower)
            if match:
                candidate = match.group(1).strip()
                # Avoid duplicating population
                if pico.population and candidate not in pico.population[0]:
                    pico.outcome = [candidate]
                    break

        # Set study type based on question type
        if "systematic review" in question_lower or "meta-analysis" in question_lower:
            pico.study_type = "systematic_review"
        elif "randomized" in question_lower or "rct" in question_lower or "efficacy" in question_lower:
            pico.study_type = "rct"

        return pico

    def _get_master_recommendations(
        self,
        searches: Dict,
        quality: QualityAssessment
    ) -> List[str]:
        """Get prioritized recommendations."""
        recommendations = []

        # Quality-based recommendations
        recommendations.extend(quality.recommendations)

        # Database-specific recommendations
        if "embase" not in searches:
            recommendations.append(
                "Add Embase search for comprehensive drug/device coverage"
            )

        if "cochrane" not in [s.lower() for s in searches]:
            recommendations.append(
                "Search Cochrane CENTRAL for RCTs"
            )

        # Best practice recommendations
        recommendations.append(
            "Have search peer-reviewed using PRESS 2015 guidelines"
        )
        recommendations.append(
            "Search grey literature (trial registries, conference abstracts)"
        )
        recommendations.append(
            "Document all searches for PRISMA flow diagram"
        )

        return recommendations[:10]

    def find_related_studies(
        self,
        seed_titles: List[str],
        candidate_studies: List[Dict]
    ) -> List[Dict]:
        """
        Find studies related to seed studies using semantic similarity.

        Args:
            seed_titles: Titles of known relevant studies
            candidate_studies: Studies to search through

        Returns:
            Ranked list of related studies
        """
        return self.semantic_engine.find_similar_studies(
            seed_titles,
            candidate_studies
        )

    def translate_search(
        self,
        search: str,
        from_db: str,
        to_db: str
    ) -> Dict:
        """
        Translate search between databases.

        Args:
            search: Original search
            from_db: Source database
            to_db: Target database

        Returns:
            Translated search with validation
        """
        return self.translator.translate(search, from_db, to_db)

    def generate_publication_report(
        self,
        search: str,
        database: str,
        results_count: int,
        search_date: str,
        pico: Optional[PICOQuery] = None
    ) -> Dict:
        """
        Generate publication-ready search report.

        Args:
            search: Search strategy
            database: Database name
            results_count: Number of results
            search_date: Date of search
            pico: Optional PICO elements

        Returns:
            Complete publication report
        """
        return self.report_generator.generate_report(
            search,
            database,
            results_count,
            search_date,
            pico
        )


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Main class
    "SystematicReviewSearchTool",
    "WorldClassSearchTool",  # Deprecated alias for backwards compatibility

    # PICO
    "PICOSearchGenerator",
    "PICOQuery",
    "PICOElement",

    # Semantic search
    "SemanticSearchEngine",

    # Database translation
    "DatabaseTranslator",

    # Quality assessment
    "SearchQualityAssessor",
    "QualityAssessment",
    "QualityLevel",

    # Reporting
    "SearchReportGenerator",
]

# Backwards compatibility alias (deprecated)
WorldClassSearchTool = SystematicReviewSearchTool


# =============================================================================
# DEMONSTRATION
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("SYSTEMATIC REVIEW SEARCH TOOL - DEMO")
    print("=" * 70)

    # Initialize
    tool = SystematicReviewSearchTool()

    # Example research question
    question = "What is the effectiveness of metformin compared to placebo for glycemic control in patients with type 2 diabetes?"

    print(f"\nResearch Question:\n{question}")

    # Create complete search package
    result = tool.create_search_from_question(
        question,
        target_databases=["pubmed", "embase", "ctgov"]
    )

    print("\n" + "=" * 70)
    print("EXTRACTED PICO")
    print("=" * 70)
    pico = result["pico"]
    print(f"Population: {pico['population']}")
    print(f"Intervention: {pico['intervention']}")
    print(f"Comparison: {pico['comparison']}")
    print(f"Outcome: {pico['outcome']}")
    print(f"Study Type: {pico['study_type']}")

    print("\n" + "=" * 70)
    print("PUBMED SEARCH STRATEGY")
    print("=" * 70)
    print(result["searches"]["pubmed"]["search_strategy"])

    print("\n" + "=" * 70)
    print("QUALITY ASSESSMENT")
    print("=" * 70)
    qa = result["quality_assessment"]
    print(f"Score: {qa['score']}/100 ({qa['level'].upper()})")
    print(f"Strengths: {', '.join(qa['strengths'])}")
    print(f"Weaknesses: {', '.join(qa['weaknesses'])}")

    print("\n" + "=" * 70)
    print("TOP RECOMMENDATIONS")
    print("=" * 70)
    for i, rec in enumerate(result["recommendations"][:5], 1):
        print(f"{i}. {rec}")

    # Translate to Embase
    print("\n" + "=" * 70)
    print("EMBASE TRANSLATION")
    print("=" * 70)
    pubmed_search = result["searches"]["pubmed"]["search_strategy"]
    embase_result = tool.translate_search(pubmed_search, "pubmed", "embase")
    print(embase_result["translated"][:500] + "...")
    if embase_result["warnings"]:
        print(f"\nWarnings: {embase_result['warnings']}")

    print("\n" + "=" * 70)
    print("DEMO COMPLETE - See documentation for limitations and caveats")
    print("=" * 70)
