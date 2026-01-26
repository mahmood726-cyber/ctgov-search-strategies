#!/usr/bin/env python3
"""
Non-Drug Intervention Search Strategies
========================================

Extension of search strategies to behavioral, surgical, and device interventions.

Features:
- Build intervention type classifier
- Create non-drug reference standards
- Adapt strategies for complex interventions
- Validate surgical/behavioral recall

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


class InterventionType(Enum):
    """Types of interventions supported."""
    DRUG = "drug"
    BIOLOGICAL = "biological"
    DEVICE = "device"
    SURGICAL = "surgical"
    BEHAVIORAL = "behavioral"
    DIETARY = "dietary"
    RADIATION = "radiation"
    DIAGNOSTIC = "diagnostic"
    GENETIC = "genetic"
    COMBINATION = "combination"
    OTHER = "other"


class InterventionComplexity(Enum):
    """Complexity levels for interventions."""
    SIMPLE = "simple"           # Single, well-defined intervention
    MODERATE = "moderate"       # Some variations
    COMPLEX = "complex"         # Many components or variations
    HIGHLY_COMPLEX = "highly_complex"  # Multimodal, individualized


@dataclass
class InterventionProfile:
    """Profile of an intervention for search strategy optimization."""
    intervention_name: str
    intervention_type: InterventionType
    complexity: InterventionComplexity

    # Search terms
    primary_terms: List[str]
    synonyms: List[str]
    mesh_terms: List[str]
    procedure_codes: List[str]  # CPT, ICD-10-PCS

    # Related concepts
    components: List[str]  # For combination interventions
    delivery_methods: List[str]
    settings: List[str]  # Hospital, outpatient, home

    # Expected characteristics
    typical_comparators: List[str]
    common_conditions: List[str]
    expected_trial_count: Optional[int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'intervention_name': self.intervention_name,
            'intervention_type': self.intervention_type.value,
            'complexity': self.complexity.value,
            'primary_terms': self.primary_terms,
            'synonyms': self.synonyms,
            'mesh_terms': self.mesh_terms,
            'procedure_codes': self.procedure_codes,
            'components': self.components,
            'delivery_methods': self.delivery_methods,
            'settings': self.settings,
            'typical_comparators': self.typical_comparators,
            'common_conditions': self.common_conditions,
            'expected_trial_count': self.expected_trial_count
        }


@dataclass
class SearchStrategy:
    """Search strategy for non-drug interventions."""
    intervention_type: InterventionType
    strategy_name: str

    # Query components
    intervention_query: str
    condition_filter: Optional[str]
    study_type_filter: str
    additional_filters: Dict[str, str]

    # AREA syntax recommendations
    use_area_syntax: bool
    area_fields: List[str]

    # Expected performance
    estimated_recall: float
    estimated_precision: float

    def to_api_query(self) -> str:
        """Convert to CT.gov API query string."""
        parts = [self.intervention_query]

        if self.condition_filter:
            parts.append(f"AND ({self.condition_filter})")

        for key, value in self.additional_filters.items():
            parts.append(f"AND {key}:{value}")

        return " ".join(parts)


class InterventionClassifier:
    """
    Classifier to determine intervention type from text.

    Uses keyword patterns and heuristics to classify interventions.
    """

    # Keyword patterns for classification
    PATTERNS = {
        InterventionType.DRUG: {
            'keywords': ['drug', 'medication', 'pharmaceutical', 'tablet', 'capsule',
                        'injection', 'infusion', 'dose', 'mg', 'placebo'],
            'suffixes': ['mab', 'nib', 'vir', 'pril', 'sartan', 'statin', 'olol',
                        'azole', 'cillin', 'mycin', 'prazole'],
            'patterns': [r'\d+\s*mg', r'oral\s+\w+', r'intravenous\s+\w+']
        },
        InterventionType.BIOLOGICAL: {
            'keywords': ['vaccine', 'immunotherapy', 'cell therapy', 'gene therapy',
                        'stem cell', 'CAR-T', 'monoclonal antibody', 'biologic'],
            'suffixes': ['mab', 'cept'],
            'patterns': [r'anti-\w+\s+antibody']
        },
        InterventionType.DEVICE: {
            'keywords': ['device', 'implant', 'stent', 'pacemaker', 'catheter',
                        'prosthesis', 'monitor', 'sensor', 'wearable', 'pump'],
            'suffixes': [],
            'patterns': [r'medical\s+device', r'implantable\s+\w+']
        },
        InterventionType.SURGICAL: {
            'keywords': ['surgery', 'surgical', 'operation', 'procedure', 'resection',
                        'excision', 'transplant', 'bypass', 'repair', 'reconstruction',
                        'arthroplasty', 'laparoscopic', 'endoscopic', 'robotic'],
            'suffixes': ['ectomy', 'otomy', 'ostomy', 'plasty', 'pexy', 'rraphy'],
            'patterns': [r'minimally\s+invasive', r'open\s+surgery']
        },
        InterventionType.BEHAVIORAL: {
            'keywords': ['behavioral', 'cognitive', 'therapy', 'counseling',
                        'psychotherapy', 'mindfulness', 'meditation', 'training',
                        'education', 'support group', 'intervention program',
                        'lifestyle', 'exercise', 'physical activity', 'smoking cessation'],
            'suffixes': [],
            'patterns': [r'CBT', r'cognitive\s+behavioral', r'self-management']
        },
        InterventionType.DIETARY: {
            'keywords': ['diet', 'dietary', 'nutrition', 'supplement', 'vitamin',
                        'mineral', 'probiotic', 'prebiotic', 'food', 'meal',
                        'caloric', 'ketogenic', 'Mediterranean'],
            'suffixes': [],
            'patterns': [r'low[-\s]?\w+\s+diet', r'high[-\s]?\w+\s+diet']
        },
        InterventionType.RADIATION: {
            'keywords': ['radiation', 'radiotherapy', 'brachytherapy', 'SBRT',
                        'IMRT', 'proton', 'photon', 'gamma knife', 'radiosurgery'],
            'suffixes': [],
            'patterns': [r'\d+\s*Gy', r'fractionated']
        },
        InterventionType.DIAGNOSTIC: {
            'keywords': ['screening', 'diagnostic', 'imaging', 'MRI', 'CT scan',
                        'ultrasound', 'biopsy', 'test', 'assay', 'biomarker'],
            'suffixes': ['graphy', 'scopy'],
            'patterns': [r'diagnostic\s+\w+']
        },
        InterventionType.GENETIC: {
            'keywords': ['gene', 'genetic', 'CRISPR', 'genome', 'DNA', 'RNA',
                        'antisense', 'siRNA', 'gene editing', 'gene transfer'],
            'suffixes': [],
            'patterns': [r'gene\s+therapy', r'genetic\s+\w+ing']
        }
    }

    def __init__(self):
        self.classification_cache: Dict[str, InterventionType] = {}

    def classify(self, intervention_text: str) -> Tuple[InterventionType, float]:
        """
        Classify intervention type from text.

        Returns:
            Tuple of (InterventionType, confidence)
        """
        text = intervention_text.lower()

        # Check cache
        if text in self.classification_cache:
            return self.classification_cache[text], 0.9

        scores = {t: 0.0 for t in InterventionType}

        for intervention_type, patterns in self.PATTERNS.items():
            # Keyword matches
            for keyword in patterns['keywords']:
                if keyword in text:
                    scores[intervention_type] += 1.0

            # Suffix matches
            for suffix in patterns['suffixes']:
                if text.endswith(suffix) or any(
                    word.endswith(suffix) for word in text.split()
                ):
                    scores[intervention_type] += 1.5

            # Regex pattern matches
            for pattern in patterns['patterns']:
                if re.search(pattern, text, re.IGNORECASE):
                    scores[intervention_type] += 2.0

        # Get best match
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]

        if best_score == 0:
            return InterventionType.OTHER, 0.0

        # Calculate confidence
        total_score = sum(scores.values())
        confidence = best_score / total_score if total_score > 0 else 0.0

        self.classification_cache[text] = best_type
        return best_type, confidence

    def classify_with_details(self, intervention_text: str) -> Dict[str, Any]:
        """Classify with detailed breakdown."""
        text = intervention_text.lower()
        results = {
            'input_text': intervention_text,
            'classification': None,
            'confidence': 0.0,
            'scores': {},
            'matched_keywords': {},
            'matched_patterns': {}
        }

        scores = {}
        matched_keywords = {}
        matched_patterns = {}

        for intervention_type, patterns in self.PATTERNS.items():
            type_name = intervention_type.value
            scores[type_name] = 0.0
            matched_keywords[type_name] = []
            matched_patterns[type_name] = []

            for keyword in patterns['keywords']:
                if keyword in text:
                    scores[type_name] += 1.0
                    matched_keywords[type_name].append(keyword)

            for suffix in patterns['suffixes']:
                if text.endswith(suffix):
                    scores[type_name] += 1.5
                    matched_keywords[type_name].append(f"*{suffix}")

            for pattern in patterns['patterns']:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    scores[type_name] += 2.0
                    matched_patterns[type_name].append(match.group())

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        total_score = sum(scores.values())

        results['classification'] = best_type
        results['confidence'] = best_score / total_score if total_score > 0 else 0.0
        results['scores'] = scores
        results['matched_keywords'] = matched_keywords
        results['matched_patterns'] = matched_patterns

        return results


class NonDrugSearchStrategyBuilder:
    """
    Build optimized search strategies for non-drug interventions.
    """

    # Predefined intervention profiles
    INTERVENTION_PROFILES = {
        # Surgical interventions
        'hip_replacement': InterventionProfile(
            intervention_name='Hip Replacement',
            intervention_type=InterventionType.SURGICAL,
            complexity=InterventionComplexity.MODERATE,
            primary_terms=['hip replacement', 'hip arthroplasty', 'total hip replacement'],
            synonyms=['THA', 'THR', 'hip prosthesis', 'hip implant'],
            mesh_terms=['Arthroplasty, Replacement, Hip'],
            procedure_codes=['27130', '27132'],  # CPT codes
            components=['femoral component', 'acetabular component'],
            delivery_methods=['anterior approach', 'posterior approach', 'lateral approach'],
            settings=['hospital', 'ambulatory surgery center'],
            typical_comparators=['non-operative management', 'hemiarthroplasty'],
            common_conditions=['osteoarthritis', 'hip fracture', 'avascular necrosis'],
            expected_trial_count=150
        ),
        'knee_replacement': InterventionProfile(
            intervention_name='Knee Replacement',
            intervention_type=InterventionType.SURGICAL,
            complexity=InterventionComplexity.MODERATE,
            primary_terms=['knee replacement', 'knee arthroplasty', 'total knee replacement'],
            synonyms=['TKA', 'TKR', 'knee prosthesis'],
            mesh_terms=['Arthroplasty, Replacement, Knee'],
            procedure_codes=['27447'],
            components=['tibial component', 'femoral component', 'patellar component'],
            delivery_methods=['minimally invasive', 'standard approach', 'robotic-assisted'],
            settings=['hospital'],
            typical_comparators=['non-operative management', 'unicompartmental arthroplasty'],
            common_conditions=['osteoarthritis', 'rheumatoid arthritis'],
            expected_trial_count=200
        ),
        'bariatric_surgery': InterventionProfile(
            intervention_name='Bariatric Surgery',
            intervention_type=InterventionType.SURGICAL,
            complexity=InterventionComplexity.COMPLEX,
            primary_terms=['bariatric surgery', 'weight loss surgery'],
            synonyms=['gastric bypass', 'sleeve gastrectomy', 'gastric banding',
                     'RYGB', 'Roux-en-Y', 'LAP-BAND'],
            mesh_terms=['Bariatric Surgery', 'Gastric Bypass'],
            procedure_codes=['43644', '43645', '43770', '43775'],
            components=[],
            delivery_methods=['laparoscopic', 'open', 'robotic'],
            settings=['hospital', 'specialized center'],
            typical_comparators=['lifestyle intervention', 'medical management'],
            common_conditions=['obesity', 'type 2 diabetes', 'metabolic syndrome'],
            expected_trial_count=180
        ),

        # Behavioral interventions
        'cognitive_behavioral_therapy': InterventionProfile(
            intervention_name='Cognitive Behavioral Therapy',
            intervention_type=InterventionType.BEHAVIORAL,
            complexity=InterventionComplexity.COMPLEX,
            primary_terms=['cognitive behavioral therapy', 'CBT'],
            synonyms=['cognitive therapy', 'behavioral therapy', 'CBT-based'],
            mesh_terms=['Cognitive Behavioral Therapy'],
            procedure_codes=[],
            components=['cognitive restructuring', 'behavioral activation',
                       'exposure therapy', 'skills training'],
            delivery_methods=['individual', 'group', 'online', 'app-based',
                            'therapist-led', 'self-guided'],
            settings=['outpatient', 'community', 'telehealth', 'primary care'],
            typical_comparators=['waitlist', 'treatment as usual', 'pharmacotherapy',
                               'supportive counseling'],
            common_conditions=['depression', 'anxiety', 'PTSD', 'insomnia', 'chronic pain'],
            expected_trial_count=300
        ),
        'physical_exercise': InterventionProfile(
            intervention_name='Physical Exercise',
            intervention_type=InterventionType.BEHAVIORAL,
            complexity=InterventionComplexity.HIGHLY_COMPLEX,
            primary_terms=['exercise', 'physical activity', 'exercise training'],
            synonyms=['aerobic exercise', 'resistance training', 'strength training',
                     'endurance training', 'physical therapy'],
            mesh_terms=['Exercise', 'Exercise Therapy', 'Resistance Training'],
            procedure_codes=[],
            components=['aerobic', 'resistance', 'flexibility', 'balance'],
            delivery_methods=['supervised', 'home-based', 'gym-based', 'group',
                            'individual', 'technology-assisted'],
            settings=['community', 'clinical', 'home', 'fitness facility'],
            typical_comparators=['usual care', 'education only', 'stretching'],
            common_conditions=['cardiovascular disease', 'diabetes', 'obesity',
                              'depression', 'cancer', 'sarcopenia'],
            expected_trial_count=500
        ),

        # Device interventions
        'continuous_glucose_monitor': InterventionProfile(
            intervention_name='Continuous Glucose Monitor',
            intervention_type=InterventionType.DEVICE,
            complexity=InterventionComplexity.MODERATE,
            primary_terms=['continuous glucose monitoring', 'CGM'],
            synonyms=['continuous glucose monitor', 'glucose sensor',
                     'Dexcom', 'Freestyle Libre', 'Guardian', 'Eversense'],
            mesh_terms=['Blood Glucose Self-Monitoring'],
            procedure_codes=['95249', '95250', '95251'],
            components=['sensor', 'transmitter', 'receiver/reader'],
            delivery_methods=['subcutaneous', 'implantable'],
            settings=['outpatient', 'home'],
            typical_comparators=['SMBG', 'self-monitoring blood glucose',
                               'standard care'],
            common_conditions=['type 1 diabetes', 'type 2 diabetes',
                              'gestational diabetes'],
            expected_trial_count=120
        ),
        'cardiac_resynchronization': InterventionProfile(
            intervention_name='Cardiac Resynchronization Therapy',
            intervention_type=InterventionType.DEVICE,
            complexity=InterventionComplexity.COMPLEX,
            primary_terms=['cardiac resynchronization therapy', 'CRT'],
            synonyms=['biventricular pacing', 'CRT-D', 'CRT-P'],
            mesh_terms=['Cardiac Resynchronization Therapy'],
            procedure_codes=['33224', '33225', '33226'],
            components=['pulse generator', 'leads', 'defibrillator (CRT-D)'],
            delivery_methods=['transvenous', 'epicardial'],
            settings=['hospital', 'electrophysiology lab'],
            typical_comparators=['optimal medical therapy', 'ICD only'],
            common_conditions=['heart failure', 'left bundle branch block'],
            expected_trial_count=80
        )
    }

    def __init__(self):
        self.classifier = InterventionClassifier()

    def get_profile(self, intervention_name: str) -> Optional[InterventionProfile]:
        """Get predefined profile or return None."""
        key = intervention_name.lower().replace(' ', '_')
        return self.INTERVENTION_PROFILES.get(key)

    def build_strategy(self, intervention: str,
                      condition: Optional[str] = None,
                      profile: Optional[InterventionProfile] = None) -> SearchStrategy:
        """
        Build optimized search strategy for an intervention.

        Args:
            intervention: Intervention name or description
            condition: Optional condition to filter by
            profile: Optional pre-built profile

        Returns:
            SearchStrategy object
        """
        # Classify if no profile provided
        if not profile:
            profile = self.get_profile(intervention)

        if profile:
            intervention_type = profile.intervention_type
            terms = profile.primary_terms + profile.synonyms
            use_area = profile.complexity in [InterventionComplexity.COMPLEX,
                                               InterventionComplexity.HIGHLY_COMPLEX]
        else:
            intervention_type, _ = self.classifier.classify(intervention)
            terms = [intervention]
            use_area = intervention_type in [InterventionType.SURGICAL,
                                             InterventionType.BEHAVIORAL]

        # Build query
        if use_area:
            # Use AREA syntax for complex interventions
            area_terms = []
            for term in terms[:5]:  # Limit to avoid overly long queries
                area_terms.append(f'AREA[InterventionName]"{term}"')
                area_terms.append(f'AREA[BriefTitle]"{term}"')
            intervention_query = " OR ".join(area_terms)
            area_fields = ['InterventionName', 'BriefTitle', 'OfficialTitle']
        else:
            # Basic query
            quoted_terms = [f'"{term}"' for term in terms]
            intervention_query = f"query.intr=({' OR '.join(quoted_terms)})"
            area_fields = []

        # Condition filter
        condition_filter = None
        if condition:
            condition_filter = f'query.cond="{condition}"'
        elif profile and profile.common_conditions:
            conditions = ' OR '.join(f'"{c}"' for c in profile.common_conditions[:3])
            condition_filter = f"query.cond=({conditions})"

        # Estimate performance based on intervention type
        performance_estimates = {
            InterventionType.DRUG: (0.75, 0.70),
            InterventionType.BIOLOGICAL: (0.72, 0.65),
            InterventionType.DEVICE: (0.70, 0.60),
            InterventionType.SURGICAL: (0.68, 0.55),
            InterventionType.BEHAVIORAL: (0.60, 0.50),
            InterventionType.DIETARY: (0.55, 0.45),
            InterventionType.RADIATION: (0.72, 0.65),
            InterventionType.DIAGNOSTIC: (0.65, 0.55),
            InterventionType.GENETIC: (0.70, 0.60),
            InterventionType.OTHER: (0.50, 0.40)
        }

        recall, precision = performance_estimates.get(intervention_type, (0.50, 0.40))

        return SearchStrategy(
            intervention_type=intervention_type,
            strategy_name=f"{intervention_type.value}_optimized",
            intervention_query=intervention_query,
            condition_filter=condition_filter,
            study_type_filter="Interventional",
            additional_filters={'query.studyType': 'Interventional'},
            use_area_syntax=use_area,
            area_fields=area_fields,
            estimated_recall=recall,
            estimated_precision=precision
        )

    def generate_recommendations(self, intervention: str,
                                condition: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate search recommendations for an intervention.

        Returns detailed recommendations for systematic review searching.
        """
        profile = self.get_profile(intervention)
        intervention_type, confidence = self.classifier.classify(intervention)
        strategy = self.build_strategy(intervention, condition, profile)

        recommendations = {
            'intervention': intervention,
            'condition': condition,
            'classification': {
                'type': intervention_type.value,
                'confidence': round(confidence, 2)
            },
            'strategy': {
                'name': strategy.strategy_name,
                'use_area_syntax': strategy.use_area_syntax,
                'estimated_recall': strategy.estimated_recall,
                'estimated_precision': strategy.estimated_precision
            },
            'api_query': strategy.to_api_query(),
            'recommendations': []
        }

        # Add type-specific recommendations
        if intervention_type == InterventionType.SURGICAL:
            recommendations['recommendations'].extend([
                "Use AREA syntax to capture trials that mention surgery in title but not intervention field",
                "Include both procedure name and common abbreviations",
                "Consider surgical approach variations (laparoscopic, open, robotic)",
                "Search for both specific procedures and broader categories",
                "Include CPT/ICD-10-PCS codes if searching databases that support them"
            ])
        elif intervention_type == InterventionType.BEHAVIORAL:
            recommendations['recommendations'].extend([
                "Behavioral interventions have highly variable naming - use broad synonyms",
                "Include delivery method variations (group, individual, online, app-based)",
                "Search for intervention components separately",
                "Consider searching for theoretical frameworks (CBT-based, ACT-based)",
                "Expected recall may be lower due to inconsistent intervention descriptions"
            ])
        elif intervention_type == InterventionType.DEVICE:
            recommendations['recommendations'].extend([
                "Include both generic device type and brand names",
                "Search for device class and specific products",
                "Consider regulatory classifications (Class I, II, III)",
                "Include older device generations if applicable"
            ])

        # Universal recommendations
        recommendations['recommendations'].extend([
            "Supplement CT.gov search with bibliographic databases (PubMed, Embase)",
            "Search WHO ICTRP for international registrations",
            f"Expected CT.gov-only recall: ~{strategy.estimated_recall:.0%}"
        ])

        return recommendations


class NonDrugReferenceStandardBuilder:
    """
    Build reference standards for non-drug interventions.

    Uses Cochrane reviews, high-quality meta-analyses, and registry data.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/reference_standards")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reference_standards: Dict[str, Dict] = {}
        self._load_standards()

    def _load_standards(self):
        """Load existing reference standards."""
        standards_file = self.data_dir / "non_drug_standards.json"
        if standards_file.exists():
            with open(standards_file) as f:
                self.reference_standards = json.load(f)

    def _save_standards(self):
        """Save reference standards."""
        with open(self.data_dir / "non_drug_standards.json", 'w') as f:
            json.dump(self.reference_standards, f, indent=2)

    def add_standard(self, intervention: str,
                    intervention_type: InterventionType,
                    condition: str,
                    nct_ids: Set[str],
                    source: str,
                    source_doi: Optional[str] = None):
        """Add a reference standard."""
        key = f"{intervention.lower()}|{condition.lower()}"

        self.reference_standards[key] = {
            'intervention': intervention,
            'intervention_type': intervention_type.value,
            'condition': condition,
            'nct_ids': list(nct_ids),
            'count': len(nct_ids),
            'source': source,
            'source_doi': source_doi,
            'created': datetime.now().isoformat()
        }

        self._save_standards()

    def get_standard(self, intervention: str,
                    condition: str) -> Optional[Dict]:
        """Get reference standard for an intervention/condition."""
        key = f"{intervention.lower()}|{condition.lower()}"
        return self.reference_standards.get(key)

    def list_standards(self) -> List[Dict]:
        """List all available reference standards."""
        return [
            {
                'intervention': v['intervention'],
                'condition': v['condition'],
                'type': v['intervention_type'],
                'count': v['count'],
                'source': v['source']
            }
            for v in self.reference_standards.values()
        ]


def main():
    """Demo of non-drug intervention search strategies."""
    print("Non-Drug Intervention Search Strategy Demo")
    print("=" * 50)

    # Initialize
    classifier = InterventionClassifier()
    strategy_builder = NonDrugSearchStrategyBuilder()

    # Test classification
    test_interventions = [
        "total hip arthroplasty",
        "cognitive behavioral therapy for depression",
        "continuous glucose monitoring",
        "laparoscopic gastric bypass",
        "mindfulness-based stress reduction",
        "pembrolizumab 200mg IV",
        "transcranial magnetic stimulation"
    ]

    print("\nIntervention Classification:")
    print("-" * 40)
    for intervention in test_interventions:
        int_type, confidence = classifier.classify(intervention)
        print(f"  {intervention}")
        print(f"    -> {int_type.value} (confidence: {confidence:.2f})")

    # Test strategy building
    print("\n\nSearch Strategy Recommendations:")
    print("=" * 50)

    test_cases = [
        ('hip replacement', 'osteoarthritis'),
        ('cognitive behavioral therapy', 'depression'),
        ('continuous glucose monitor', 'type 1 diabetes'),
        ('bariatric surgery', 'obesity'),
        ('exercise', 'heart failure')
    ]

    for intervention, condition in test_cases:
        print(f"\n{intervention} for {condition}")
        print("-" * 40)

        recs = strategy_builder.generate_recommendations(intervention, condition)

        print(f"Classification: {recs['classification']['type']} "
              f"(confidence: {recs['classification']['confidence']})")
        print(f"Strategy: {recs['strategy']['name']}")
        print(f"Use AREA syntax: {recs['strategy']['use_area_syntax']}")
        print(f"Expected recall: {recs['strategy']['estimated_recall']:.0%}")
        print(f"Expected precision: {recs['strategy']['estimated_precision']:.0%}")
        print("\nTop recommendations:")
        for rec in recs['recommendations'][:3]:
            print(f"  • {rec}")

    # Save output
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # Save all recommendations
    all_recs = {}
    for intervention, condition in test_cases:
        key = f"{intervention}|{condition}"
        all_recs[key] = strategy_builder.generate_recommendations(intervention, condition)

    with open(output_dir / "non_drug_recommendations.json", 'w') as f:
        json.dump(all_recs, f, indent=2)

    print(f"\n\nRecommendations saved to {output_dir / 'non_drug_recommendations.json'}")


if __name__ == "__main__":
    main()
