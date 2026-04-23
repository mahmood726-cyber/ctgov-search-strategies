#!/usr/bin/env python3
"""
ML Strategy Optimizer for CT.gov Search Strategies
==================================================

Machine learning model to recommend optimal search strategy based on
drug/condition characteristics.

Features:
- Predict recall by drug characteristics
- Recommend AREA syntax when beneficial
- Flag generic terms needing expansion
- Estimate search workload

Author: CT.gov Search Strategy Validation Project
Version: 1.0.0
Date: 2026-01-26
"""

import json
import pickle
import hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime
from enum import Enum
import math
import re


class SearchStrategy(Enum):
    """Available search strategies."""
    BASIC = "basic"
    AREA_SYNTAX = "area_syntax"
    COMBINED = "combined"
    ENHANCED_SYNONYMS = "enhanced_synonyms"
    MULTI_REGISTRY = "multi_registry"


class TherapeuticArea(Enum):
    """Therapeutic area classifications."""
    ONCOLOGY = "oncology"
    DIABETES = "diabetes"
    CARDIOVASCULAR = "cardiovascular"
    RESPIRATORY = "respiratory"
    RHEUMATOLOGY = "rheumatology"
    PSYCHIATRY = "psychiatry"
    INFECTIOUS_DISEASE = "infectious_disease"
    NEUROLOGY = "neurology"
    DERMATOLOGY = "dermatology"
    GASTROENTEROLOGY = "gastroenterology"
    HEMATOLOGY = "hematology"
    NEPHROLOGY = "nephrology"
    OPHTHALMOLOGY = "ophthalmology"
    OTHER = "other"


@dataclass
class DrugFeatures:
    """Features extracted from a drug for ML prediction."""
    drug_name: str
    therapeutic_area: TherapeuticArea
    is_generic: bool
    is_biologic: bool
    is_combination_therapy: bool
    name_length: int
    has_numeric_suffix: bool
    approval_year: Optional[int]
    mechanism_class: str
    typical_trial_count: int
    synonyms_count: int

    # Computed features
    name_complexity_score: float = 0.0
    generic_risk_score: float = 0.0
    oncology_combination_risk: float = 0.0

    def __post_init__(self):
        """Compute derived features."""
        self.name_complexity_score = self._compute_name_complexity()
        self.generic_risk_score = self._compute_generic_risk()
        self.oncology_combination_risk = self._compute_oncology_risk()

    def _compute_name_complexity(self) -> float:
        """Score based on how complex/ambiguous the drug name is."""
        score = 0.0
        name = self.drug_name.lower()

        # Short names are more ambiguous
        if len(name) <= 5:
            score += 0.3
        elif len(name) <= 8:
            score += 0.1

        # Common prefixes/suffixes that may match many drugs
        common_patterns = ['mab', 'nib', 'vir', 'ide', 'ine', 'pril']
        for pattern in common_patterns:
            if name.endswith(pattern):
                score += 0.1

        # Generic class names
        if self.is_generic:
            score += 0.4

        return min(1.0, score)

    def _compute_generic_risk(self) -> float:
        """Risk score for generic term recall problems."""
        if not self.is_generic:
            return 0.0

        risk = 0.5  # Base risk for generics

        # Very common generics have higher risk
        high_risk_generics = ['insulin', 'metformin', 'aspirin', 'warfarin',
                             'methotrexate', 'prednisone', 'heparin']
        if self.drug_name.lower() in high_risk_generics:
            risk += 0.3

        # Many synonyms suggest complexity
        if self.synonyms_count > 10:
            risk += 0.2

        return min(1.0, risk)

    def _compute_oncology_risk(self) -> float:
        """Risk for oncology combination therapy issues."""
        if self.therapeutic_area != TherapeuticArea.ONCOLOGY:
            return 0.0

        risk = 0.3  # Base risk for oncology

        if self.is_biologic:
            risk += 0.2

        if self.is_combination_therapy:
            risk += 0.3

        return min(1.0, risk)

    def to_feature_vector(self) -> List[float]:
        """Convert to numeric feature vector for ML model."""
        return [
            1.0 if self.is_generic else 0.0,
            1.0 if self.is_biologic else 0.0,
            1.0 if self.is_combination_therapy else 0.0,
            float(self.name_length) / 20.0,  # Normalize
            1.0 if self.has_numeric_suffix else 0.0,
            float(self.typical_trial_count) / 500.0,  # Normalize
            float(self.synonyms_count) / 30.0,  # Normalize
            self.name_complexity_score,
            self.generic_risk_score,
            self.oncology_combination_risk,
            # One-hot encode therapeutic area (top 5)
            1.0 if self.therapeutic_area == TherapeuticArea.ONCOLOGY else 0.0,
            1.0 if self.therapeutic_area == TherapeuticArea.DIABETES else 0.0,
            1.0 if self.therapeutic_area == TherapeuticArea.CARDIOVASCULAR else 0.0,
            1.0 if self.therapeutic_area == TherapeuticArea.RESPIRATORY else 0.0,
            1.0 if self.therapeutic_area == TherapeuticArea.RHEUMATOLOGY else 0.0,
        ]


@dataclass
class StrategyRecommendation:
    """ML model recommendation for a drug."""
    drug_name: str
    recommended_strategy: SearchStrategy
    confidence: float
    predicted_recall: float
    predicted_precision: float
    estimated_workload: int  # NNS - number needed to screen

    # Flags
    needs_area_syntax: bool
    needs_synonym_expansion: bool
    needs_multi_registry: bool

    # Detailed recommendations
    specific_recommendations: List[str]
    risk_factors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'drug_name': self.drug_name,
            'recommended_strategy': self.recommended_strategy.value,
            'confidence': round(self.confidence, 3),
            'predicted_recall': round(self.predicted_recall, 3),
            'predicted_precision': round(self.predicted_precision, 3),
            'estimated_workload': self.estimated_workload,
            'needs_area_syntax': self.needs_area_syntax,
            'needs_synonym_expansion': self.needs_synonym_expansion,
            'needs_multi_registry': self.needs_multi_registry,
            'specific_recommendations': self.specific_recommendations,
            'risk_factors': self.risk_factors
        }


@dataclass
class TrainingExample:
    """A training example from validation results."""
    drug_name: str
    features: DrugFeatures
    strategy_used: SearchStrategy
    actual_recall: float
    actual_precision: float
    trials_found: int
    trials_expected: int


class GradientBoostingClassifier:
    """
    Simple gradient boosting implementation for strategy optimization.

    This is a lightweight implementation that doesn't require sklearn,
    suitable for embedding in the project.
    """

    def __init__(self, n_estimators: int = 100, learning_rate: float = 0.1,
                 max_depth: int = 3):
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.trees: List[Dict] = []
        self.initial_prediction = 0.5

    def _sigmoid(self, x: float) -> float:
        """Sigmoid function for probability."""
        return 1.0 / (1.0 + math.exp(-max(-500, min(500, x))))

    def _build_stump(self, X: List[List[float]], residuals: List[float],
                     depth: int = 0) -> Dict:
        """Build a decision stump (simplified tree)."""
        if depth >= self.max_depth or len(X) < 2:
            return {'leaf': True, 'value': sum(residuals) / max(1, len(residuals))}

        best_split = None
        best_gain = -float('inf')
        n_features = len(X[0])

        for feature_idx in range(n_features):
            values = sorted(set(x[feature_idx] for x in X))

            for i in range(len(values) - 1):
                threshold = (values[i] + values[i + 1]) / 2

                left_indices = [j for j, x in enumerate(X) if x[feature_idx] <= threshold]
                right_indices = [j for j, x in enumerate(X) if x[feature_idx] > threshold]

                if not left_indices or not right_indices:
                    continue

                left_residuals = [residuals[j] for j in left_indices]
                right_residuals = [residuals[j] for j in right_indices]

                # Compute gain (reduction in variance)
                total_var = sum(r**2 for r in residuals) / len(residuals)
                left_var = sum(r**2 for r in left_residuals) / len(left_residuals)
                right_var = sum(r**2 for r in right_residuals) / len(right_residuals)

                weighted_var = (len(left_residuals) * left_var +
                              len(right_residuals) * right_var) / len(residuals)
                gain = total_var - weighted_var

                if gain > best_gain:
                    best_gain = gain
                    best_split = {
                        'feature': feature_idx,
                        'threshold': threshold,
                        'left_indices': left_indices,
                        'right_indices': right_indices
                    }

        if best_split is None:
            return {'leaf': True, 'value': sum(residuals) / max(1, len(residuals))}

        left_X = [X[i] for i in best_split['left_indices']]
        left_residuals = [residuals[i] for i in best_split['left_indices']]
        right_X = [X[i] for i in best_split['right_indices']]
        right_residuals = [residuals[i] for i in best_split['right_indices']]

        return {
            'leaf': False,
            'feature': best_split['feature'],
            'threshold': best_split['threshold'],
            'left': self._build_stump(left_X, left_residuals, depth + 1),
            'right': self._build_stump(right_X, right_residuals, depth + 1)
        }

    def _predict_tree(self, tree: Dict, x: List[float]) -> float:
        """Predict using a single tree."""
        if tree['leaf']:
            return tree['value']

        if x[tree['feature']] <= tree['threshold']:
            return self._predict_tree(tree['left'], x)
        else:
            return self._predict_tree(tree['right'], x)

    def fit(self, X: List[List[float]], y: List[float]):
        """Train the gradient boosting model."""
        self.initial_prediction = sum(y) / len(y)
        predictions = [self.initial_prediction] * len(y)

        for _ in range(self.n_estimators):
            # Compute residuals (gradient of log loss)
            residuals = [yi - self._sigmoid(pi) for yi, pi in zip(y, predictions)]

            # Build tree on residuals
            tree = self._build_stump(X, residuals)
            self.trees.append(tree)

            # Update predictions
            for i, x in enumerate(X):
                predictions[i] += self.learning_rate * self._predict_tree(tree, x)

    def predict_proba(self, x: List[float]) -> float:
        """Predict probability for a single example."""
        pred = self.initial_prediction
        for tree in self.trees:
            pred += self.learning_rate * self._predict_tree(tree, x)
        return self._sigmoid(pred)

    def save(self, path: Path):
        """Save model to file."""
        with open(path, 'wb') as f:
            pickle.dump({
                'n_estimators': self.n_estimators,
                'learning_rate': self.learning_rate,
                'max_depth': self.max_depth,
                'trees': self.trees,
                'initial_prediction': self.initial_prediction
            }, f)

    @classmethod
    def load(cls, path: Path) -> 'GradientBoostingClassifier':
        """Load model from file."""
        with open(path, 'rb') as f:
            data = pickle.load(f)

        model = cls(data['n_estimators'], data['learning_rate'], data['max_depth'])
        model.trees = data['trees']
        model.initial_prediction = data['initial_prediction']
        return model


class MLStrategyOptimizer:
    """
    Machine learning optimizer for CT.gov search strategies.

    Uses gradient boosting to predict:
    1. Optimal search strategy for a drug
    2. Expected recall
    3. Need for AREA syntax
    4. Need for synonym expansion
    """

    # Known drug classifications
    THERAPEUTIC_AREA_KEYWORDS = {
        TherapeuticArea.ONCOLOGY: ['cancer', 'tumor', 'carcinoma', 'leukemia',
                                   'lymphoma', 'melanoma', 'oncology'],
        TherapeuticArea.DIABETES: ['diabetes', 'diabetic', 'glycemic', 'insulin',
                                   'glucose', 'a1c', 'hba1c'],
        TherapeuticArea.CARDIOVASCULAR: ['heart', 'cardiac', 'cardiovascular',
                                         'hypertension', 'blood pressure', 'atrial'],
        TherapeuticArea.RESPIRATORY: ['asthma', 'copd', 'respiratory', 'lung',
                                      'pulmonary', 'bronchial'],
        TherapeuticArea.RHEUMATOLOGY: ['arthritis', 'rheumatoid', 'lupus',
                                       'autoimmune', 'joint'],
        TherapeuticArea.PSYCHIATRY: ['depression', 'anxiety', 'schizophrenia',
                                     'bipolar', 'psychiatric', 'mental'],
        TherapeuticArea.INFECTIOUS_DISEASE: ['hiv', 'hepatitis', 'infection',
                                             'viral', 'bacterial', 'antibiotic'],
        TherapeuticArea.NEUROLOGY: ['alzheimer', 'parkinson', 'epilepsy',
                                    'multiple sclerosis', 'neurological', 'seizure']
    }

    BIOLOGIC_SUFFIXES = ['mab', 'cept', 'zumab', 'ximab', 'umab', 'kinra']

    GENERIC_DRUGS = {
        'insulin', 'metformin', 'aspirin', 'warfarin', 'heparin',
        'prednisone', 'methotrexate', 'azathioprine', 'cyclosporine',
        'tacrolimus', 'mycophenolate', 'sirolimus', 'everolimus',
        'dexamethasone', 'methylprednisolone', 'hydrocortisone'
    }

    def __init__(self, models_dir: Optional[Path] = None):
        self.models_dir = models_dir or Path("models")
        self.models_dir.mkdir(exist_ok=True)

        # ML models for different predictions
        self.area_syntax_model: Optional[GradientBoostingClassifier] = None
        self.synonym_expansion_model: Optional[GradientBoostingClassifier] = None
        self.recall_predictor: Optional[GradientBoostingClassifier] = None

        # Training data
        self.training_examples: List[TrainingExample] = []

        # Rule-based defaults (used before ML model is trained)
        self.default_rules = self._initialize_default_rules()

    def _initialize_default_rules(self) -> Dict[str, Any]:
        """Initialize rule-based defaults based on validation findings."""
        return {
            'oncology_area_syntax_boost': 0.15,  # +15% recall with AREA
            'generic_synonym_expansion_boost': 0.50,  # +50% recall with expansion
            'base_recall_by_area': {
                TherapeuticArea.RESPIRATORY: 0.86,
                TherapeuticArea.DIABETES: 0.84,
                TherapeuticArea.RHEUMATOLOGY: 0.82,
                TherapeuticArea.PSYCHIATRY: 0.80,
                TherapeuticArea.CARDIOVASCULAR: 0.79,
                TherapeuticArea.INFECTIOUS_DISEASE: 0.79,
                TherapeuticArea.ONCOLOGY: 0.65,
                TherapeuticArea.OTHER: 0.75
            },
            'generic_recall_without_expansion': 0.25,
            'generic_recall_with_expansion': 0.75
        }

    def extract_features(self, drug_name: str, condition: str = "",
                        synonyms: List[str] = None) -> DrugFeatures:
        """Extract ML features from drug information."""
        name_lower = drug_name.lower()

        # Determine therapeutic area
        therapeutic_area = TherapeuticArea.OTHER
        condition_lower = condition.lower()
        for area, keywords in self.THERAPEUTIC_AREA_KEYWORDS.items():
            if any(kw in condition_lower or kw in name_lower for kw in keywords):
                therapeutic_area = area
                break

        # Check if generic
        is_generic = name_lower in self.GENERIC_DRUGS

        # Check if biologic
        is_biologic = any(name_lower.endswith(suffix) for suffix in self.BIOLOGIC_SUFFIXES)

        # Check for combination patterns
        is_combination = '+' in drug_name or '/' in drug_name or ' and ' in name_lower

        # Check for numeric suffix (research codes)
        has_numeric_suffix = bool(re.search(r'\d{3,}$', drug_name))

        # Estimate typical trial count based on characteristics
        if is_generic:
            typical_trial_count = 200
        elif is_biologic and therapeutic_area == TherapeuticArea.ONCOLOGY:
            typical_trial_count = 150
        elif therapeutic_area == TherapeuticArea.ONCOLOGY:
            typical_trial_count = 100
        else:
            typical_trial_count = 75

        return DrugFeatures(
            drug_name=drug_name,
            therapeutic_area=therapeutic_area,
            is_generic=is_generic,
            is_biologic=is_biologic,
            is_combination_therapy=is_combination,
            name_length=len(drug_name),
            has_numeric_suffix=has_numeric_suffix,
            approval_year=None,
            mechanism_class="",
            typical_trial_count=typical_trial_count,
            synonyms_count=len(synonyms) if synonyms else 1
        )

    def recommend_strategy(self, drug_name: str, condition: str = "",
                          synonyms: List[str] = None) -> StrategyRecommendation:
        """
        Recommend optimal search strategy for a drug.

        Uses ML models if trained, otherwise falls back to rule-based system.
        """
        features = self.extract_features(drug_name, condition, synonyms)
        feature_vector = features.to_feature_vector()

        # Determine if AREA syntax is needed
        if self.area_syntax_model:
            area_syntax_prob = self.area_syntax_model.predict_proba(feature_vector)
            needs_area = area_syntax_prob > 0.5
        else:
            # Rule-based: oncology and biologics benefit from AREA
            needs_area = (features.therapeutic_area == TherapeuticArea.ONCOLOGY or
                         features.is_biologic or
                         features.is_combination_therapy)

        # Determine if synonym expansion is needed
        if self.synonym_expansion_model:
            expansion_prob = self.synonym_expansion_model.predict_proba(feature_vector)
            needs_expansion = expansion_prob > 0.5
        else:
            # Rule-based: generics need expansion
            needs_expansion = features.is_generic or features.generic_risk_score > 0.5

        # Predict recall
        if self.recall_predictor:
            predicted_recall = self.recall_predictor.predict_proba(feature_vector)
        else:
            # Rule-based recall prediction
            base_recall = self.default_rules['base_recall_by_area'].get(
                features.therapeutic_area, 0.75)

            if features.is_generic:
                if needs_expansion:
                    predicted_recall = self.default_rules['generic_recall_with_expansion']
                else:
                    predicted_recall = self.default_rules['generic_recall_without_expansion']
            elif needs_area and features.therapeutic_area == TherapeuticArea.ONCOLOGY:
                predicted_recall = base_recall + self.default_rules['oncology_area_syntax_boost']
            else:
                predicted_recall = base_recall

        # Determine recommended strategy
        if needs_expansion:
            recommended = SearchStrategy.ENHANCED_SYNONYMS
        elif needs_area:
            recommended = SearchStrategy.COMBINED
        else:
            recommended = SearchStrategy.BASIC

        # Generate specific recommendations
        recommendations = self._generate_recommendations(features, needs_area, needs_expansion)
        risk_factors = self._identify_risk_factors(features)

        # Estimate workload (NNS)
        predicted_precision = 0.68 if needs_area else 0.72
        estimated_workload = int(1.0 / predicted_precision) if predicted_precision > 0 else 10

        # Confidence based on feature certainty
        confidence = self._calculate_confidence(features, needs_area, needs_expansion)

        return StrategyRecommendation(
            drug_name=drug_name,
            recommended_strategy=recommended,
            confidence=confidence,
            predicted_recall=predicted_recall,
            predicted_precision=predicted_precision,
            estimated_workload=estimated_workload,
            needs_area_syntax=needs_area,
            needs_synonym_expansion=needs_expansion,
            needs_multi_registry=features.therapeutic_area == TherapeuticArea.ONCOLOGY,
            specific_recommendations=recommendations,
            risk_factors=risk_factors
        )

    def _generate_recommendations(self, features: DrugFeatures,
                                  needs_area: bool, needs_expansion: bool) -> List[str]:
        """Generate specific recommendations based on features."""
        recommendations = []

        if needs_area:
            recommendations.append(
                "Use AREA syntax: AREA[InterventionName], AREA[BriefTitle], AREA[OfficialTitle]"
            )

        if needs_expansion:
            if features.is_generic:
                recommendations.append(
                    f"Expand '{features.drug_name}' to include all formulations, "
                    "combinations, and international names (INN, BAN, JAN)"
                )
            else:
                recommendations.append(
                    "Consider adding brand names and research codes as synonyms"
                )

        if features.therapeutic_area == TherapeuticArea.ONCOLOGY:
            recommendations.append(
                "Search for combination therapy trials using 'OR' for each component"
            )
            recommendations.append(
                "Include research codes (e.g., BMS-xxxxx, MK-xxxx) if known"
            )

        if features.is_biologic:
            recommendations.append(
                "Include biosimilar names if searching for all related trials"
            )

        if features.name_complexity_score > 0.5:
            recommendations.append(
                "Drug name may match unrelated trials; consider adding condition filter"
            )

        # Always recommend
        recommendations.append(
            "Supplement with bibliographic database search (PubMed, Embase) "
            "for comprehensive coverage"
        )

        return recommendations

    def _identify_risk_factors(self, features: DrugFeatures) -> List[str]:
        """Identify risk factors that may reduce recall."""
        risks = []

        if features.generic_risk_score > 0.6:
            risks.append(
                f"HIGH: '{features.drug_name}' is a high-risk generic term "
                f"(baseline recall ~25%)"
            )
        elif features.generic_risk_score > 0.3:
            risks.append(
                f"MODERATE: '{features.drug_name}' is a generic term "
                f"requiring synonym expansion"
            )

        if features.oncology_combination_risk > 0.5:
            risks.append(
                "HIGH: Oncology combination therapy - trials may not list "
                "all drugs in InterventionName field"
            )
        elif features.oncology_combination_risk > 0.2:
            risks.append(
                "MODERATE: Oncology drug - AREA syntax recommended"
            )

        if features.name_complexity_score > 0.5:
            risks.append(
                "MODERATE: Short/common drug name may match unrelated records"
            )

        if features.is_biologic and features.therapeutic_area == TherapeuticArea.ONCOLOGY:
            risks.append(
                "MODERATE: Biologic oncology drug often used in combinations "
                "not reflected in intervention field"
            )

        return risks

    def _calculate_confidence(self, features: DrugFeatures,
                             needs_area: bool, needs_expansion: bool) -> float:
        """Calculate confidence in the recommendation."""
        # Base confidence
        confidence = 0.7

        # Higher confidence for well-characterized therapeutic areas
        well_characterized = [
            TherapeuticArea.DIABETES, TherapeuticArea.CARDIOVASCULAR,
            TherapeuticArea.RESPIRATORY
        ]
        if features.therapeutic_area in well_characterized:
            confidence += 0.15

        # Lower confidence for oncology (more variable)
        if features.therapeutic_area == TherapeuticArea.ONCOLOGY:
            confidence -= 0.1

        # Lower confidence for generics (depends on expansion quality)
        if features.is_generic:
            confidence -= 0.1

        # ML models provide higher confidence
        if self.area_syntax_model:
            confidence += 0.05

        return min(0.95, max(0.3, confidence))

    def add_training_example(self, drug_name: str, condition: str,
                            strategy: SearchStrategy, recall: float,
                            precision: float, found: int, expected: int,
                            synonyms: List[str] = None):
        """Add a training example from validation results."""
        features = self.extract_features(drug_name, condition, synonyms)

        example = TrainingExample(
            drug_name=drug_name,
            features=features,
            strategy_used=strategy,
            actual_recall=recall,
            actual_precision=precision,
            trials_found=found,
            trials_expected=expected
        )

        self.training_examples.append(example)

    def train_models(self, n_folds: int = 5) -> Dict[str, Any]:
        """
        Train ML models from collected examples with k-fold cross-validation.

        Args:
            n_folds: Number of cross-validation folds (default: 5)

        Returns:
            Dictionary with training results and cross-validation metrics
        """
        if len(self.training_examples) < 20:
            print(f"Insufficient training data ({len(self.training_examples)} examples). "
                  f"Need at least 20.")
            return {'success': False, 'error': 'Insufficient training data'}

        # Prepare training data
        X = []
        y_area = []  # 1 if AREA syntax improved recall
        y_expansion = []  # 1 if expansion needed
        y_recall = []  # Actual recall value

        for example in self.training_examples:
            X.append(example.features.to_feature_vector())

            # AREA syntax target: did strategy S2/S4 outperform S1?
            y_area.append(1.0 if example.strategy_used in
                         [SearchStrategy.AREA_SYNTAX, SearchStrategy.COMBINED] and
                         example.actual_recall > 0.75 else 0.0)

            # Expansion target: is recall low without expansion?
            y_expansion.append(1.0 if example.features.is_generic and
                              example.actual_recall < 0.5 else 0.0)

            y_recall.append(example.actual_recall)

        # Perform k-fold cross-validation
        cv_results = self._cross_validate(X, y_area, y_expansion, y_recall, n_folds)

        print(f"\n{'='*50}")
        print("Cross-Validation Results")
        print(f"{'='*50}")
        print(f"AREA Syntax Model AUC: {cv_results['area_syntax_auc']:.3f} "
              f"(±{cv_results['area_syntax_auc_std']:.3f})")
        print(f"Expansion Model AUC: {cv_results['expansion_auc']:.3f} "
              f"(±{cv_results['expansion_auc_std']:.3f})")
        print(f"Recall Predictor MAE: {cv_results['recall_mae']:.3f} "
              f"(±{cv_results['recall_mae_std']:.3f})")
        print(f"Calibration Slope: {cv_results['calibration_slope']:.3f}")
        print(f"{'='*50}\n")

        # Train final models on all data
        print("Training final AREA syntax recommendation model...")
        self.area_syntax_model = GradientBoostingClassifier(n_estimators=50)
        self.area_syntax_model.fit(X, y_area)

        print("Training final synonym expansion model...")
        self.synonym_expansion_model = GradientBoostingClassifier(n_estimators=50)
        self.synonym_expansion_model.fit(X, y_expansion)

        print("Training final recall predictor...")
        self.recall_predictor = GradientBoostingClassifier(n_estimators=100)
        self.recall_predictor.fit(X, y_recall)

        # Save models
        self.area_syntax_model.save(self.models_dir / "area_syntax_model.pkl")
        self.synonym_expansion_model.save(self.models_dir / "expansion_model.pkl")
        self.recall_predictor.save(self.models_dir / "recall_model.pkl")

        # Save cross-validation metrics
        cv_results_path = self.models_dir / "cv_metrics.json"
        with open(cv_results_path, 'w') as f:
            json.dump(cv_results, f, indent=2)

        print(f"Models trained on {len(self.training_examples)} examples and saved.")
        print(f"Cross-validation metrics saved to {cv_results_path}")

        return {
            'success': True,
            'n_examples': len(self.training_examples),
            'n_folds': n_folds,
            'cv_metrics': cv_results
        }

    def _cross_validate(
        self,
        X: List[List[float]],
        y_area: List[float],
        y_expansion: List[float],
        y_recall: List[float],
        n_folds: int
    ) -> Dict[str, float]:
        """
        Perform k-fold cross-validation.

        Returns:
            Dictionary with AUC, MAE, and calibration metrics
        """
        import random

        n = len(X)
        indices = list(range(n))
        random.seed(42)  # Reproducibility
        random.shuffle(indices)

        fold_size = n // n_folds

        area_aucs = []
        expansion_aucs = []
        recall_maes = []
        all_predicted_recalls = []
        all_actual_recalls = []

        for fold in range(n_folds):
            # Split data
            val_start = fold * fold_size
            val_end = val_start + fold_size if fold < n_folds - 1 else n
            val_indices = indices[val_start:val_end]
            train_indices = indices[:val_start] + indices[val_end:]

            X_train = [X[i] for i in train_indices]
            X_val = [X[i] for i in val_indices]

            y_area_train = [y_area[i] for i in train_indices]
            y_area_val = [y_area[i] for i in val_indices]

            y_expansion_train = [y_expansion[i] for i in train_indices]
            y_expansion_val = [y_expansion[i] for i in val_indices]

            y_recall_train = [y_recall[i] for i in train_indices]
            y_recall_val = [y_recall[i] for i in val_indices]

            # Train fold models
            area_model = GradientBoostingClassifier(n_estimators=50)
            area_model.fit(X_train, y_area_train)

            expansion_model = GradientBoostingClassifier(n_estimators=50)
            expansion_model.fit(X_train, y_expansion_train)

            recall_model = GradientBoostingClassifier(n_estimators=100)
            recall_model.fit(X_train, y_recall_train)

            # Evaluate
            area_preds = [area_model.predict_proba(x) for x in X_val]
            expansion_preds = [expansion_model.predict_proba(x) for x in X_val]
            recall_preds = [recall_model.predict_proba(x) for x in X_val]

            # Calculate AUC (simplified ROC-AUC)
            area_aucs.append(self._calculate_auc(y_area_val, area_preds))
            expansion_aucs.append(self._calculate_auc(y_expansion_val, expansion_preds))

            # Calculate MAE for recall
            mae = sum(abs(p - a) for p, a in zip(recall_preds, y_recall_val)) / len(y_recall_val)
            recall_maes.append(mae)

            all_predicted_recalls.extend(recall_preds)
            all_actual_recalls.extend(y_recall_val)

        # Calculate calibration slope
        calibration_slope = self._calculate_calibration_slope(
            all_predicted_recalls, all_actual_recalls
        )

        return {
            'area_syntax_auc': sum(area_aucs) / len(area_aucs),
            'area_syntax_auc_std': self._std(area_aucs),
            'expansion_auc': sum(expansion_aucs) / len(expansion_aucs),
            'expansion_auc_std': self._std(expansion_aucs),
            'recall_mae': sum(recall_maes) / len(recall_maes),
            'recall_mae_std': self._std(recall_maes),
            'calibration_slope': calibration_slope,
            'n_folds': n_folds,
        }

    def _calculate_auc(self, y_true: List[float], y_pred: List[float]) -> float:
        """Calculate ROC-AUC using Mann-Whitney U statistic."""
        positives = [(p, i) for i, (t, p) in enumerate(zip(y_true, y_pred)) if t > 0.5]
        negatives = [(p, i) for i, (t, p) in enumerate(zip(y_true, y_pred)) if t <= 0.5]

        if not positives or not negatives:
            return 0.5

        # Count concordant pairs
        concordant = 0
        for p_pos, _ in positives:
            for p_neg, _ in negatives:
                if p_pos > p_neg:
                    concordant += 1
                elif p_pos == p_neg:
                    concordant += 0.5

        auc = concordant / (len(positives) * len(negatives))
        return auc

    def _calculate_calibration_slope(
        self,
        predicted: List[float],
        actual: List[float]
    ) -> float:
        """Calculate calibration slope using linear regression."""
        if not predicted or not actual:
            return 1.0

        n = len(predicted)
        mean_pred = sum(predicted) / n
        mean_actual = sum(actual) / n

        # Calculate slope: Cov(pred, actual) / Var(pred)
        cov = sum((p - mean_pred) * (a - mean_actual) for p, a in zip(predicted, actual)) / n
        var_pred = sum((p - mean_pred) ** 2 for p in predicted) / n

        if var_pred < 1e-10:
            return 1.0

        slope = cov / var_pred
        return slope

    def _std(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)

    def load_models(self) -> bool:
        """Load pre-trained models."""
        try:
            self.area_syntax_model = GradientBoostingClassifier.load(
                self.models_dir / "area_syntax_model.pkl")
            self.synonym_expansion_model = GradientBoostingClassifier.load(
                self.models_dir / "expansion_model.pkl")
            self.recall_predictor = GradientBoostingClassifier.load(
                self.models_dir / "recall_model.pkl")
            return True
        except FileNotFoundError:
            return False

    def load_training_data_from_validation(self, validation_results_path: Path):
        """Load training data from validation results JSON."""
        with open(validation_results_path) as f:
            results = json.load(f)

        for drug_result in results.get('drug_results', []):
            drug_name = drug_result['drug']
            condition = drug_result.get('condition', '')

            for strategy_name, strategy_data in drug_result.get('strategies', {}).items():
                strategy_map = {
                    'basic': SearchStrategy.BASIC,
                    'area': SearchStrategy.AREA_SYNTAX,
                    'combined': SearchStrategy.COMBINED
                }
                strategy = strategy_map.get(strategy_name.lower(), SearchStrategy.BASIC)

                self.add_training_example(
                    drug_name=drug_name,
                    condition=condition,
                    strategy=strategy,
                    recall=strategy_data.get('recall', 0),
                    precision=strategy_data.get('precision', 0),
                    found=strategy_data.get('found', 0),
                    expected=strategy_data.get('expected', 0)
                )

        print(f"Loaded {len(self.training_examples)} training examples from validation results.")

    def batch_recommend(self, drugs: List[Dict[str, str]]) -> List[StrategyRecommendation]:
        """Generate recommendations for multiple drugs."""
        recommendations = []
        for drug_info in drugs:
            rec = self.recommend_strategy(
                drug_name=drug_info['drug'],
                condition=drug_info.get('condition', ''),
                synonyms=drug_info.get('synonyms', [])
            )
            recommendations.append(rec)
        return recommendations

    def generate_report(self, recommendations: List[StrategyRecommendation]) -> str:
        """Generate a formatted report from recommendations."""
        lines = [
            "=" * 70,
            "ML Strategy Optimizer Report",
            "=" * 70,
            f"Generated: {datetime.now().isoformat()}",
            f"Drugs analyzed: {len(recommendations)}",
            "",
        ]

        # Summary statistics
        need_area = sum(1 for r in recommendations if r.needs_area_syntax)
        need_expansion = sum(1 for r in recommendations if r.needs_synonym_expansion)
        need_multi = sum(1 for r in recommendations if r.needs_multi_registry)

        avg_recall = sum(r.predicted_recall for r in recommendations) / len(recommendations)

        lines.extend([
            "SUMMARY",
            "-" * 40,
            f"Drugs needing AREA syntax: {need_area} ({100*need_area/len(recommendations):.1f}%)",
            f"Drugs needing synonym expansion: {need_expansion} ({100*need_expansion/len(recommendations):.1f}%)",
            f"Drugs needing multi-registry search: {need_multi} ({100*need_multi/len(recommendations):.1f}%)",
            f"Average predicted recall: {avg_recall:.1%}",
            "",
        ])

        # High-risk drugs
        high_risk = [r for r in recommendations if any('HIGH' in rf for rf in r.risk_factors)]
        if high_risk:
            lines.extend([
                "HIGH-RISK DRUGS (require special attention)",
                "-" * 40,
            ])
            for rec in high_risk:
                lines.append(f"  - {rec.drug_name}: {rec.risk_factors[0]}")
            lines.append("")

        # Individual recommendations
        lines.extend([
            "INDIVIDUAL RECOMMENDATIONS",
            "-" * 40,
        ])

        for rec in sorted(recommendations, key=lambda r: -r.predicted_recall):
            lines.extend([
                f"\n{rec.drug_name}",
                f"  Strategy: {rec.recommended_strategy.value}",
                f"  Predicted recall: {rec.predicted_recall:.1%}",
                f"  Confidence: {rec.confidence:.1%}",
                f"  Workload (NNS): {rec.estimated_workload}",
            ])

            if rec.risk_factors:
                lines.append("  Risk factors:")
                for rf in rec.risk_factors:
                    lines.append(f"    - {rf}")

            lines.append("  Recommendations:")
            for r in rec.specific_recommendations[:3]:  # Top 3
                lines.append(f"    - {r}")

        return "\n".join(lines)


def main():
    """Demo of ML strategy optimizer."""
    print("ML Strategy Optimizer Demo")
    print("=" * 50)

    optimizer = MLStrategyOptimizer()

    # Try to load pre-trained models
    if optimizer.load_models():
        print("Loaded pre-trained models")
    else:
        print("No pre-trained models found, using rule-based defaults")

    # Test drugs across therapeutic areas
    test_drugs = [
        {'drug': 'pembrolizumab', 'condition': 'cancer'},
        {'drug': 'nivolumab', 'condition': 'melanoma'},
        {'drug': 'insulin', 'condition': 'diabetes'},
        {'drug': 'metformin', 'condition': 'type 2 diabetes'},
        {'drug': 'adalimumab', 'condition': 'rheumatoid arthritis'},
        {'drug': 'fluticasone', 'condition': 'asthma'},
        {'drug': 'atorvastatin', 'condition': 'hyperlipidemia'},
        {'drug': 'sertraline', 'condition': 'depression'},
    ]

    recommendations = optimizer.batch_recommend(test_drugs)
    report = optimizer.generate_report(recommendations)
    print(report)

    # Save recommendations
    output_path = Path("output/ml_recommendations.json")
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump([r.to_dict() for r in recommendations], f, indent=2)

    print(f"\nRecommendations saved to {output_path}")


if __name__ == "__main__":
    main()
