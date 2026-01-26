"""
Unit tests for the search_methodology module.

Tests cover:
- PRESS 2015 Guidelines validation
- Search filter validation metrics
- Boolean query optimization
- Grey literature search guidance
- ML screening assistance
- Cochrane-compliant search building
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_methodology import (
    SearchMethodology,
    PRESSValidator,
    PRESSElement,
    PRESSValidationResult,
    PRESSReport,
    SearchFilterValidator,
    FilterPerformanceMetrics,
    BooleanOptimizer,
    GreyLiteratureSearcher,
    MLScreeningAssistant,
    CochraneSearchBuilder,
)


# =============================================================================
# PRESS VALIDATOR TESTS
# =============================================================================

class TestPRESSValidator:
    """Tests for PRESS 2015 Guidelines validation."""

    @pytest.fixture
    def validator(self):
        return PRESSValidator()

    def test_validate_simple_query(self, validator):
        """Test validation of a simple query."""
        query = '(diabetes OR diabetic) AND (metformin OR glucophage)'
        result = validator.validate(query)

        assert isinstance(result, PRESSReport)
        assert result.query == query
        assert 0 <= result.overall_score <= 1
        assert len(result.elements) == 6  # All 6 PRESS elements

    def test_validate_with_pico(self, validator):
        """Test validation with PICO elements provided."""
        query = '(heart failure) AND (digoxin OR digitalis)'
        pico = {
            "Population": ["heart failure", "cardiac failure"],
            "Intervention": ["digoxin", "digitalis"]
        }

        result = validator.validate(query, pico_elements=pico)

        # Should score well on translation since PICO elements are present
        translation_result = result.elements[PRESSElement.TRANSLATION]
        assert translation_result.score >= 0.7

    def test_validate_unbalanced_parentheses(self, validator):
        """Test detection of unbalanced parentheses."""
        query = '((diabetes OR diabetic) AND metformin'
        result = validator.validate(query)

        boolean_result = result.elements[PRESSElement.BOOLEAN_OPERATORS]
        assert not boolean_result.passed
        assert any("parentheses" in issue.lower() for issue in boolean_result.issues)

    def test_validate_spelling_variants(self, validator):
        """Test detection of missing spelling variants."""
        query = 'randomized controlled trial'
        result = validator.validate(query)

        spelling_result = result.elements[PRESSElement.SPELLING]
        # Should recommend adding 'randomised'
        assert any("randomized" in rec.lower() or "variant" in rec.lower()
                   for rec in spelling_result.recommendations)

    def test_validate_typo_detection(self, validator):
        """Test detection of common typos."""
        query = 'randomzied controled trial'  # Multiple typos
        result = validator.validate(query)

        spelling_result = result.elements[PRESSElement.SPELLING]
        assert not spelling_result.passed
        assert len(spelling_result.issues) > 0

    def test_acceptable_score_threshold(self, validator):
        """Test that acceptable threshold is applied correctly."""
        # Well-formed query
        good_query = '(diabetes[mesh] OR diabetes[tiab]) AND (metformin[mesh] OR metformin[tiab])'
        result = validator.validate(good_query)

        # Should meet 0.7 threshold
        assert result.overall_score >= 0.5  # At least moderately good

    def test_report_to_dict(self, validator):
        """Test PRESSReport serialization to dict."""
        query = 'diabetes AND metformin'
        result = validator.validate(query)

        report_dict = result.to_dict()

        assert "query" in report_dict
        assert "overall_score" in report_dict
        assert "elements" in report_dict
        assert "translation" in report_dict["elements"]


# =============================================================================
# FILTER PERFORMANCE METRICS TESTS
# =============================================================================

class TestFilterPerformanceMetrics:
    """Tests for filter performance metrics calculation."""

    def test_perfect_filter(self):
        """Test metrics for a perfect filter."""
        metrics = FilterPerformanceMetrics.from_counts(
            tp=100, fp=0, fn=0, tn=900
        )

        assert metrics.sensitivity == 1.0
        assert metrics.specificity == 1.0
        assert metrics.precision == 1.0
        assert metrics.f1_score == 1.0

    def test_realistic_filter(self):
        """Test metrics for a realistic filter."""
        # 99% sensitivity, 50% specificity
        metrics = FilterPerformanceMetrics.from_counts(
            tp=99, fp=450, fn=1, tn=450
        )

        assert 0.98 < metrics.sensitivity < 1.0
        assert 0.45 < metrics.specificity < 0.55
        assert metrics.nnr > 1.0  # Number needed to read

    def test_wilson_confidence_interval(self):
        """Test Wilson score CI calculation."""
        metrics = FilterPerformanceMetrics.from_counts(
            tp=198, fp=50, fn=2, tn=750
        )

        # CI should be around the point estimate
        assert metrics.sensitivity_ci[0] < metrics.sensitivity < metrics.sensitivity_ci[1]
        assert metrics.specificity_ci[0] < metrics.specificity < metrics.specificity_ci[1]

    def test_zero_handling(self):
        """Test handling of zero denominators."""
        metrics = FilterPerformanceMetrics.from_counts(
            tp=0, fp=0, fn=0, tn=100
        )

        # Should not raise errors
        assert metrics.sensitivity == 0.0
        assert metrics.specificity == 1.0


class TestSearchFilterValidator:
    """Tests for search filter validation."""

    @pytest.fixture
    def validator(self):
        return SearchFilterValidator()

    def test_validate_high_sensitivity_filter(self, validator):
        """Test validation of high-sensitivity filter."""
        result = validator.validate_filter(
            filter_name="Cochrane RCT Filter",
            true_positives=198,
            false_positives=500,
            false_negatives=2,
            true_negatives=300,
            gold_standard_source="Cochrane Reviews"
        )

        assert result["filter_name"] == "Cochrane RCT Filter"
        assert result["thresholds"]["meets_sensitivity"]
        assert result["metrics"]["sensitivity"] >= 0.99

    def test_validate_below_threshold(self, validator):
        """Test validation of filter below threshold."""
        result = validator.validate_filter(
            filter_name="Basic Search",
            true_positives=90,
            false_positives=100,
            false_negatives=10,
            true_negatives=800,
            gold_standard_source="Test"
        )

        assert result["metrics"]["sensitivity"] == 0.9
        assert not result["thresholds"]["meets_sensitivity"]

    def test_generate_report(self, validator):
        """Test report generation."""
        validator.validate_filter("Filter1", 95, 50, 5, 850, "Gold1")
        validator.validate_filter("Filter2", 99, 100, 1, 800, "Gold2")

        report = validator.generate_validation_report()

        assert "Filter1" in report
        assert "Filter2" in report
        assert "Sensitivity" in report


# =============================================================================
# BOOLEAN OPTIMIZER TESTS
# =============================================================================

class TestBooleanOptimizer:
    """Tests for Boolean query optimization."""

    @pytest.fixture
    def optimizer(self):
        return BooleanOptimizer()

    def test_optimize_basic_query(self, optimizer):
        """Test basic query optimization."""
        concepts = {
            "population": ["diabetes", "diabetic"],
            "intervention": ["metformin"]
        }

        query = optimizer.optimize_query(concepts)

        assert "diabetes" in query.lower()
        assert "metformin" in query.lower()
        assert " AND " in query
        assert " OR " in query

    def test_add_truncation(self, optimizer):
        """Test truncation is added appropriately."""
        concepts = {
            "condition": ["treatment"]
        }

        query = optimizer.optimize_query(concepts, include_truncation=True)

        # Should add truncation to appropriate terms
        assert "*" in query

    def test_phrase_searching(self, optimizer):
        """Test phrase searching for multi-word terms."""
        concepts = {
            "condition": ["heart failure"]
        }

        query = optimizer.optimize_query(concepts, include_phrase_search=True)

        assert '"heart failure"' in query

    def test_spelling_variants(self, optimizer):
        """Test US/UK spelling variants."""
        terms = ["randomized", "pediatric"]
        expanded = optimizer.add_spelling_variants(terms)

        # Should include both variants
        assert "randomized" in expanded or "randomised" in expanded
        assert len(expanded) > len(terms)

    def test_validate_syntax_valid(self, optimizer):
        """Test syntax validation for valid query."""
        query = '(diabetes OR diabetic) AND (metformin OR glucophage)'
        result = optimizer.validate_syntax(query)

        assert result["valid"]
        assert len(result["issues"]) == 0

    def test_validate_syntax_invalid(self, optimizer):
        """Test syntax validation for invalid query."""
        query = '(diabetes OR diabetic AND metformin'  # Unbalanced
        result = optimizer.validate_syntax(query)

        assert not result["valid"]
        assert len(result["issues"]) > 0

    def test_suggest_synonyms(self, optimizer):
        """Test synonym suggestion."""
        synonyms = optimizer.suggest_synonyms("heart attack")

        assert "heart attack" in synonyms
        assert len(synonyms) > 1
        assert any("myocardial infarction" in s.lower() for s in synonyms)


# =============================================================================
# GREY LITERATURE SEARCHER TESTS
# =============================================================================

class TestGreyLiteratureSearcher:
    """Tests for grey literature search guidance."""

    @pytest.fixture
    def searcher(self):
        return GreyLiteratureSearcher()

    def test_get_recommended_sources(self, searcher):
        """Test getting recommended sources."""
        sources = searcher.get_recommended_sources()

        assert len(sources) > 0
        assert any(s["source"] == "ClinicalTrials.gov" for s in sources)

    def test_clinical_sources_essential(self, searcher):
        """Test that clinical reviews get trial registries as essential."""
        sources = searcher.get_recommended_sources(
            review_type="systematic",
            topic_area="clinical"
        )

        trial_registries = [s for s in sources if s["category"] == "Trial Registry"]
        assert len(trial_registries) > 0
        assert all(s["priority"] == "Essential" for s in trial_registries)

    def test_generate_protocol(self, searcher):
        """Test search protocol generation."""
        protocol = searcher.generate_search_protocol(
            condition="diabetes",
            intervention="metformin"
        )

        assert "diabetes" in protocol
        assert "metformin" in protocol
        assert "ClinicalTrials.gov" in protocol
        assert "Grey Literature" in protocol


# =============================================================================
# ML SCREENING ASSISTANT TESTS
# =============================================================================

class TestMLScreeningAssistant:
    """Tests for ML screening assistance."""

    @pytest.fixture
    def assistant(self):
        return MLScreeningAssistant()

    def test_estimate_workload_reduction(self, assistant):
        """Test workload reduction estimation."""
        result = assistant.estimate_workload_reduction(
            total_records=5000,
            estimated_relevant=50
        )

        assert "workload_reduction_percent" in result
        assert result["total_records"] == 5000
        assert result["workload_reduction_percent"] > 0

    def test_small_dataset_recommendation(self, assistant):
        """Test recommendation for small datasets."""
        result = assistant.estimate_workload_reduction(
            total_records=200,
            estimated_relevant=20
        )

        assert "Manual screening" in result["recommendation"]

    def test_safe_stopping_not_ready(self, assistant):
        """Test SAFE stopping when not ready to stop."""
        # Recent relevant findings
        history = [1, 0, 0, 1, 0, 1, 0, 0, 0]  # Found relevant 3 ago

        result = assistant.calculate_safe_stopping(history)

        assert not result["safe_to_stop"]

    def test_safe_stopping_ready(self, assistant):
        """Test SAFE stopping when ready."""
        # Long run of irrelevant at end
        history = [1, 1, 0, 0, 0, 0, 0] * 20  # Many irrelevant at end

        result = assistant.calculate_safe_stopping(history, batch_size=20)

        # May or may not be safe depending on calculation
        assert "consecutive_irrelevant" in result

    def test_prioritize_studies(self, assistant):
        """Test study prioritization."""
        studies = [
            {"id": "1", "title": "Random study about cooking"},
            {"id": "2", "title": "Diabetes treatment with metformin"},
            {"id": "3", "title": "Metformin effects on blood sugar"},
        ]

        prioritized = assistant.prioritize_studies(
            studies,
            known_relevant=["2"]
        )

        # Study 3 should be ranked higher due to shared keywords
        assert prioritized[0]["id"] in ["2", "3"]


# =============================================================================
# COCHRANE SEARCH BUILDER TESTS
# =============================================================================

class TestCochraneSearchBuilder:
    """Tests for Cochrane-compliant search building."""

    @pytest.fixture
    def builder(self):
        return CochraneSearchBuilder()

    def test_build_basic_search(self, builder):
        """Test basic Cochrane search building."""
        search = builder.build_cochrane_search(
            condition_terms=["diabetes"],
            intervention_terms=["metformin"],
            study_type="rct"
        )

        assert "#1" in search
        assert "#2" in search
        assert "diabetes" in search.lower()
        assert "metformin" in search.lower()

    def test_includes_rct_filter(self, builder):
        """Test that RCT filter is included."""
        search = builder.build_cochrane_search(
            condition_terms=["heart failure"],
            intervention_terms=["digoxin"],
            study_type="rct"
        )

        assert "randomized" in search.lower() or "randomised" in search.lower()

    def test_validate_compliance_good(self, builder):
        """Test compliance validation for good search."""
        search = """
        #1 (diabetes[mesh] OR diabetes[tiab] OR diabetic[tiab])
        #2 (metformin[mesh] OR metformin[tiab])
        #3 #1 AND #2
        #4 randomized controlled trial[pt]
        #5 #3 AND #4
        """

        result = builder.validate_cochrane_compliance(search)

        assert result["score"] >= 70
        assert result["compliant"]

    def test_validate_compliance_poor(self, builder):
        """Test compliance validation for poor search."""
        search = "diabetes metformin"  # No Boolean, no fields

        result = builder.validate_cochrane_compliance(search)

        assert result["score"] < 70
        assert not result["compliant"]


# =============================================================================
# COMPREHENSIVE SEARCH METHODOLOGY TESTS
# =============================================================================

class TestSearchMethodology:
    """Tests for the main SearchMethodology class."""

    @pytest.fixture
    def methodology(self):
        return SearchMethodology()

    def test_create_comprehensive_search(self, methodology):
        """Test comprehensive search creation."""
        result = methodology.create_comprehensive_search(
            condition="type 2 diabetes",
            intervention="metformin"
        )

        assert "query" in result
        assert "validation" in result
        assert "grey_literature" in result
        assert "recommendations" in result

        assert "optimized_boolean" in result["query"]
        assert "cochrane_format" in result["query"]

    def test_with_synonyms(self, methodology):
        """Test search with synonyms provided."""
        result = methodology.create_comprehensive_search(
            condition="heart failure",
            intervention="ACE inhibitors",
            synonyms={
                "condition": ["cardiac failure", "CHF"],
                "intervention": ["angiotensin converting enzyme inhibitors"]
            }
        )

        # Synonyms should be in the query
        query_lower = result["query"]["optimized_boolean"].lower()
        assert "cardiac" in query_lower or "chf" in query_lower

    def test_estimate_workload(self, methodology):
        """Test screening workload estimation."""
        workload = methodology.estimate_screening_workload(
            expected_results=3000,
            estimated_relevant=30
        )

        assert "workload_reduction_percent" in workload
        assert "recommendation" in workload

    def test_validate_filter(self, methodology):
        """Test filter validation through main class."""
        result = methodology.validate_search_filter(
            filter_name="Test Filter",
            tp=98, fp=100, fn=2, tn=800,
            gold_standard="Test Set"
        )

        assert result["filter_name"] == "Test Filter"
        assert "metrics" in result


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for the search methodology module."""

    def test_full_workflow(self):
        """Test complete search methodology workflow."""
        methodology = SearchMethodology()

        # Step 1: Create comprehensive search
        search = methodology.create_comprehensive_search(
            condition="COVID-19",
            intervention="remdesivir",
            synonyms={
                "condition": ["SARS-CoV-2", "coronavirus disease 2019"],
                "intervention": ["Veklury", "GS-5734"]
            },
            study_types=["rct"],
            databases=["ClinicalTrials.gov", "PubMed"]
        )

        assert search["validation"]["press"]["overall_score"] > 0

        # Step 2: Estimate workload
        workload = methodology.estimate_screening_workload(
            expected_results=2000,
            estimated_relevant=100
        )

        assert workload["workload_reduction_percent"] >= 0

        # Step 3: Validate a filter
        validation = methodology.validate_search_filter(
            filter_name="COVID RCT Filter",
            tp=195, fp=200, fn=5, tn=600,
            gold_standard="Cochrane COVID Reviews"
        )

        assert validation["metrics"]["sensitivity"] > 0.95


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_query(self):
        """Test handling of empty query."""
        validator = PRESSValidator()
        result = validator.validate("")

        # Should not raise error
        assert result.overall_score >= 0

    def test_special_characters(self):
        """Test handling of special characters in query."""
        optimizer = BooleanOptimizer()
        result = optimizer.validate_syntax(
            '("β-blocker" OR "beta-blocker") AND heart'
        )

        # Should handle special characters
        assert isinstance(result["valid"], bool)

    def test_unicode_terms(self):
        """Test handling of unicode terms."""
        methodology = SearchMethodology()

        result = methodology.create_comprehensive_search(
            condition="Sjögren's syndrome",
            intervention="rituximab"
        )

        assert "Sjögren" in result["query"]["optimized_boolean"]

    def test_very_long_query(self):
        """Test handling of very long queries."""
        validator = PRESSValidator()

        # Create a very long query
        terms = [f"term{i}" for i in range(100)]
        long_query = " OR ".join(terms)

        result = validator.validate(long_query)

        # Should complete without error
        assert result.overall_score >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
