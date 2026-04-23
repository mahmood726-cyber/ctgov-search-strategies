#!/usr/bin/env python3
# sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files.
"""
Expanded Therapeutic Area Validation for CT.gov Search Strategies

Validates all 10 search strategies across 10+ therapeutic areas with multiple
conditions per area. Calculates result counts, theoretical recall when NCT IDs
are available, and generates comprehensive performance reports.

Therapeutic Areas:
1. Oncology (breast cancer, lung cancer, colorectal cancer)
2. Cardiology (heart failure, atrial fibrillation, myocardial infarction)
3. Neurology (Parkinson's, Alzheimer's, multiple sclerosis)
4. Rheumatology (rheumatoid arthritis, lupus)
5. Infectious Disease (HIV, hepatitis C, tuberculosis)
6. Metabolic (obesity, hyperlipidemia)
7. Pulmonary (COPD, asthma)
8. Gastroenterology (Crohn's disease, ulcerative colitis)
9. Ophthalmology (macular degeneration, glaucoma)
10. Dermatology (atopic dermatitis, psoriasis)
"""

import json
import csv
import time
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import quote

from ctgov_config import (
    CTGOV_API,
    DEFAULT_RATE_LIMIT,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
)
from ctgov_utils import (
    build_params,
    fetch_nct_ids,
    fetch_total_count,
    get_session,
)

# =============================================================================
# THERAPEUTIC AREA DEFINITIONS
# =============================================================================

THERAPEUTIC_AREAS = {
    "Oncology": {
        "description": "Cancer and oncological conditions",
        "conditions": {
            "breast_cancer": {
                "primary_term": "breast cancer",
                "synonyms": [
                    "breast neoplasm",
                    "breast carcinoma",
                    "breast malignancy",
                    "mammary cancer",
                    "breast tumor",
                ],
                "mesh_terms": ["Breast Neoplasms"],
            },
            "lung_cancer": {
                "primary_term": "lung cancer",
                "synonyms": [
                    "lung neoplasm",
                    "lung carcinoma",
                    "non-small cell lung cancer",
                    "small cell lung cancer",
                    "NSCLC",
                    "SCLC",
                    "pulmonary neoplasm",
                ],
                "mesh_terms": ["Lung Neoplasms", "Carcinoma, Non-Small-Cell Lung"],
            },
            "colorectal_cancer": {
                "primary_term": "colorectal cancer",
                "synonyms": [
                    "colon cancer",
                    "rectal cancer",
                    "colorectal carcinoma",
                    "bowel cancer",
                    "colorectal neoplasm",
                    "CRC",
                ],
                "mesh_terms": ["Colorectal Neoplasms"],
            },
        },
    },
    "Cardiology": {
        "description": "Cardiovascular conditions",
        "conditions": {
            "heart_failure": {
                "primary_term": "heart failure",
                "synonyms": [
                    "cardiac failure",
                    "congestive heart failure",
                    "CHF",
                    "HFrEF",
                    "HFpEF",
                    "ventricular dysfunction",
                ],
                "mesh_terms": ["Heart Failure"],
            },
            "atrial_fibrillation": {
                "primary_term": "atrial fibrillation",
                "synonyms": [
                    "AF",
                    "AFib",
                    "A-fib",
                    "auricular fibrillation",
                    "atrial flutter",
                ],
                "mesh_terms": ["Atrial Fibrillation"],
            },
            "myocardial_infarction": {
                "primary_term": "myocardial infarction",
                "synonyms": [
                    "heart attack",
                    "MI",
                    "acute coronary syndrome",
                    "ACS",
                    "STEMI",
                    "NSTEMI",
                    "cardiac infarction",
                ],
                "mesh_terms": ["Myocardial Infarction"],
            },
        },
    },
    "Neurology": {
        "description": "Neurological disorders",
        "conditions": {
            "parkinsons_disease": {
                "primary_term": "Parkinson's disease",
                "synonyms": [
                    "Parkinson disease",
                    "PD",
                    "parkinsonism",
                    "idiopathic Parkinson's",
                ],
                "mesh_terms": ["Parkinson Disease"],
            },
            "alzheimers_disease": {
                "primary_term": "Alzheimer's disease",
                "synonyms": [
                    "Alzheimer disease",
                    "AD",
                    "Alzheimer dementia",
                    "dementia of Alzheimer type",
                ],
                "mesh_terms": ["Alzheimer Disease"],
            },
            "multiple_sclerosis": {
                "primary_term": "multiple sclerosis",
                "synonyms": [
                    "MS",
                    "relapsing remitting MS",
                    "RRMS",
                    "progressive MS",
                    "demyelinating disease",
                ],
                "mesh_terms": ["Multiple Sclerosis"],
            },
        },
    },
    "Rheumatology": {
        "description": "Rheumatological and autoimmune conditions",
        "conditions": {
            "rheumatoid_arthritis": {
                "primary_term": "rheumatoid arthritis",
                "synonyms": [
                    "RA",
                    "inflammatory arthritis",
                    "polyarthritis",
                    "rheumatoid disease",
                ],
                "mesh_terms": ["Arthritis, Rheumatoid"],
            },
            "systemic_lupus": {
                "primary_term": "systemic lupus erythematosus",
                "synonyms": [
                    "lupus",
                    "SLE",
                    "lupus erythematosus",
                ],
                "mesh_terms": ["Lupus Erythematosus, Systemic"],
            },
        },
    },
    "Infectious_Disease": {
        "description": "Infectious diseases",
        "conditions": {
            "hiv": {
                "primary_term": "HIV infection",
                "synonyms": [
                    "HIV",
                    "human immunodeficiency virus",
                    "AIDS",
                    "HIV/AIDS",
                    "HIV-1",
                ],
                "mesh_terms": ["HIV Infections", "Acquired Immunodeficiency Syndrome"],
            },
            "hepatitis_c": {
                "primary_term": "hepatitis C",
                "synonyms": [
                    "HCV",
                    "hepatitis C virus",
                    "chronic hepatitis C",
                    "HCV infection",
                ],
                "mesh_terms": ["Hepatitis C"],
            },
            "tuberculosis": {
                "primary_term": "tuberculosis",
                "synonyms": [
                    "TB",
                    "pulmonary tuberculosis",
                    "mycobacterium tuberculosis",
                    "latent TB",
                ],
                "mesh_terms": ["Tuberculosis"],
            },
        },
    },
    "Metabolic": {
        "description": "Metabolic and endocrine disorders",
        "conditions": {
            "obesity": {
                "primary_term": "obesity",
                "synonyms": [
                    "morbid obesity",
                    "overweight",
                    "weight management",
                    "adiposity",
                    "BMI",
                ],
                "mesh_terms": ["Obesity"],
            },
            "hyperlipidemia": {
                "primary_term": "hyperlipidemia",
                "synonyms": [
                    "dyslipidemia",
                    "hypercholesterolemia",
                    "high cholesterol",
                    "hypertriglyceridemia",
                    "lipid disorder",
                ],
                "mesh_terms": ["Hyperlipidemias", "Hypercholesterolemia"],
            },
        },
    },
    "Pulmonary": {
        "description": "Respiratory and pulmonary conditions",
        "conditions": {
            "copd": {
                "primary_term": "COPD",
                "synonyms": [
                    "chronic obstructive pulmonary disease",
                    "emphysema",
                    "chronic bronchitis",
                    "chronic airway obstruction",
                ],
                "mesh_terms": ["Pulmonary Disease, Chronic Obstructive"],
            },
            "asthma": {
                "primary_term": "asthma",
                "synonyms": [
                    "bronchial asthma",
                    "allergic asthma",
                    "asthma bronchiale",
                    "reactive airway disease",
                ],
                "mesh_terms": ["Asthma"],
            },
        },
    },
    "Gastroenterology": {
        "description": "Gastrointestinal conditions",
        "conditions": {
            "crohns_disease": {
                "primary_term": "Crohn's disease",
                "synonyms": [
                    "Crohn disease",
                    "regional enteritis",
                    "inflammatory bowel disease",
                    "IBD",
                    "ileitis",
                ],
                "mesh_terms": ["Crohn Disease"],
            },
            "ulcerative_colitis": {
                "primary_term": "ulcerative colitis",
                "synonyms": [
                    "UC",
                    "colitis ulcerosa",
                    "inflammatory bowel disease",
                    "IBD",
                ],
                "mesh_terms": ["Colitis, Ulcerative"],
            },
        },
    },
    "Ophthalmology": {
        "description": "Eye and vision disorders",
        "conditions": {
            "macular_degeneration": {
                "primary_term": "macular degeneration",
                "synonyms": [
                    "AMD",
                    "age-related macular degeneration",
                    "ARMD",
                    "wet AMD",
                    "dry AMD",
                ],
                "mesh_terms": ["Macular Degeneration"],
            },
            "glaucoma": {
                "primary_term": "glaucoma",
                "synonyms": [
                    "open angle glaucoma",
                    "angle closure glaucoma",
                    "primary open angle glaucoma",
                    "POAG",
                    "ocular hypertension",
                ],
                "mesh_terms": ["Glaucoma"],
            },
        },
    },
    "Dermatology": {
        "description": "Skin and dermatological conditions",
        "conditions": {
            "atopic_dermatitis": {
                "primary_term": "atopic dermatitis",
                "synonyms": [
                    "eczema",
                    "atopic eczema",
                    "AD",
                    "neurodermatitis",
                ],
                "mesh_terms": ["Dermatitis, Atopic"],
            },
            "psoriasis": {
                "primary_term": "psoriasis",
                "synonyms": [
                    "plaque psoriasis",
                    "psoriatic skin disease",
                    "psoriasis vulgaris",
                ],
                "mesh_terms": ["Psoriasis"],
            },
        },
    },
}

# =============================================================================
# SEARCH STRATEGIES (from ctgov_search.py)
# =============================================================================

STRATEGIES = {
    "S1": {
        "name": "Condition Only (Maximum Recall)",
        "description": "Cochrane recommended - no filters for maximum sensitivity",
        "build_query": lambda c: f"query.cond={quote(c)}",
    },
    "S2": {
        "name": "Interventional Studies",
        "description": "All interventional study types",
        "build_query": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[StudyType]INTERVENTIONAL')}",
    },
    "S3": {
        "name": "Randomized Allocation Only",
        "description": "True RCTs - excludes single-arm trials",
        "build_query": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED')}",
    },
    "S4": {
        "name": "Phase 3/4 Studies",
        "description": "Later phase trials only",
        "build_query": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[Phase](PHASE3 OR PHASE4)')}",
    },
    "S5": {
        "name": "Has Posted Results",
        "description": "Studies with results posted on CT.gov",
        "build_query": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[ResultsFirstPostDate]RANGE[MIN,MAX]')}",
    },
    "S6": {
        "name": "Completed Status",
        "description": "Completed trials only",
        "build_query": lambda c: f"query.cond={quote(c)}&filter.overallStatus=COMPLETED",
    },
    "S7": {
        "name": "Interventional + Completed",
        "description": "Completed interventional studies",
        "build_query": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[StudyType]INTERVENTIONAL')}&filter.overallStatus=COMPLETED",
    },
    "S8": {
        "name": "RCT + Phase 3/4 + Completed",
        "description": "Highest quality subset",
        "build_query": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED AND AREA[Phase](PHASE3 OR PHASE4)')}&filter.overallStatus=COMPLETED",
    },
    "S9": {
        "name": "Full-Text RCT Keywords",
        "description": "Text search: condition AND randomized AND controlled",
        "build_query": lambda c: f"query.term={quote(c + ' AND randomized AND controlled')}",
    },
    "S10": {
        "name": "Treatment RCTs Only",
        "description": "Randomized + Treatment purpose",
        "build_query": lambda c: f"query.cond={quote(c)}&query.term={quote('AREA[DesignAllocation]RANDOMIZED AND AREA[DesignPrimaryPurpose]TREATMENT')}",
    },
}

# =============================================================================
# KNOWN NCT IDS FOR RECALL CALCULATION (Gold Standard)
# These are known relevant trials from published systematic reviews
# =============================================================================

KNOWN_NCT_IDS = {
    # Oncology - Breast Cancer (from landmark trials)
    "breast_cancer": [
        "NCT00174655",  # HERA (trastuzumab)
        "NCT00045032",  # ATAC (anastrozole)
        "NCT00352989",  # SOFT (tamoxifen vs aromatase inhibitors)
        "NCT00433589",  # TEXT
        "NCT01674140",  # CLEOPATRA (pertuzumab)
        "NCT02131064",  # MONALEESA-2 (ribociclib)
        "NCT01958021",  # PALOMA-2 (palbociclib)
        "NCT02107703",  # MONARCH 2 (abemaciclib)
    ],
    # Cardiology - Heart Failure (from ESC guidelines)
    "heart_failure": [
        "NCT00634309",  # PARADIGM-HF (sacubitril/valsartan)
        "NCT03036124",  # DAPA-HF (dapagliflozin)
        "NCT03057977",  # EMPEROR-Reduced (empagliflozin)
        "NCT01035255",  # SHIFT (ivabradine)
        "NCT01920711",  # VICTORIA (vericiguat)
        "NCT01626079",  # GALACTIC-HF (omecamtiv)
    ],
    # Cardiology - Atrial Fibrillation (from ACC/AHA guidelines)
    "atrial_fibrillation": [
        "NCT00262600",  # RE-LY (dabigatran)
        "NCT00403767",  # ROCKET-AF (rivaroxaban)
        "NCT00412984",  # ARISTOTLE (apixaban)
        "NCT01150474",  # ENGAGE AF-TIMI 48 (edoxaban)
        "NCT01342458",  # RELY-ABLE
    ],
    # Cardiology - MI/ACS
    "myocardial_infarction": [
        "NCT01156571",  # PLATO (ticagrelor)
        "NCT00391872",  # TRITON-TIMI 38 (prasugrel)
        "NCT01187134",  # PEGASUS-TIMI 54
        "NCT01482767",  # ATLAS ACS 2-TIMI 51
    ],
    # Neurology - Parkinson's
    "parkinsons_disease": [
        "NCT00031239",  # ADAGIO (rasagiline)
        "NCT00256204",  # TEMPO
        "NCT00322036",  # ELLDOPA
    ],
    # Neurology - Alzheimer's
    "alzheimers_disease": [
        "NCT02477800",  # EMERGE (aducanumab)
        "NCT02484547",  # ENGAGE (aducanumab)
        "NCT03887455",  # CLARITY AD (lecanemab)
    ],
    # Rheumatology - RA
    "rheumatoid_arthritis": [
        "NCT00106535",  # AMBITION (tocilizumab)
        "NCT00413660",  # ORAL Start (tofacitinib)
        "NCT01197521",  # RA-BEAM (baricitinib)
        "NCT02187055",  # SELECT-COMPARE (upadacitinib)
    ],
    # Infectious Disease - HIV
    "hiv": [
        "NCT01797445",  # HPTN 083 (cabotegravir)
        "NCT02831673",  # ATLAS (cabotegravir)
        "NCT01598831",  # GEMINI 1 (dolutegravir)
    ],
    # Metabolic - Obesity
    "obesity": [
        "NCT03548935",  # STEP 1 (semaglutide)
        "NCT03552757",  # STEP 4
        "NCT03611582",  # STEP 5
    ],
    # Pulmonary - COPD
    "copd": [
        "NCT01313676",  # FLAME (indacaterol/glycopyrronium)
        "NCT01854645",  # IMPACT (triple therapy)
        "NCT01706198",  # TRIBUTE
    ],
    # Gastroenterology - Crohn's
    "crohns_disease": [
        "NCT01369342",  # UNITI-1 (ustekinumab)
        "NCT01369355",  # UNITI-2
        "NCT02499783",  # VARSITY (vedolizumab vs adalimumab)
    ],
    # Dermatology - Psoriasis
    "psoriasis": [
        "NCT01474512",  # VOYAGE 1 (guselkumab)
        "NCT01544595",  # FIXTURE (secukinumab)
        "NCT02207231",  # IMMvent (risankizumab)
    ],
}


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class StrategyResult:
    """Result for a single strategy search"""

    strategy_id: str
    strategy_name: str
    total_count: int
    execution_time: float
    error: Optional[str] = None


@dataclass
class ConditionResult:
    """Results for a single condition across all strategies"""

    condition_id: str
    primary_term: str
    therapeutic_area: str
    strategy_results: Dict[str, StrategyResult] = field(default_factory=dict)
    baseline_count: int = 0
    known_nct_ids: List[str] = field(default_factory=list)
    recall_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class TherapeuticAreaSummary:
    """Summary statistics for a therapeutic area"""

    area_name: str
    description: str
    num_conditions: int
    total_trials_s1: int
    total_trials_s3: int
    avg_retention_s3: float
    conditions: List[str] = field(default_factory=list)


# =============================================================================
# VALIDATION CLASS
# =============================================================================


class ExpandedTherapeuticValidation:
    """Validates search strategies across therapeutic areas"""

    def __init__(
        self,
        output_dir: Optional[str] = None,
        user_agent: str = DEFAULT_USER_AGENT,
        rate_limit: float = DEFAULT_RATE_LIMIT,
    ):
        self.session = get_session(user_agent=user_agent)
        self.output_dir = Path(output_dir) if output_dir else Path("output")
        self.output_dir.mkdir(exist_ok=True)
        self.rate_limit = rate_limit
        self.results: Dict[str, Dict[str, ConditionResult]] = {}

    def search_condition(
        self, condition: str, strategy_id: str
    ) -> Tuple[int, float, Optional[str]]:
        """Execute a single search and return (count, time, error)"""
        if strategy_id not in STRATEGIES:
            return 0, 0.0, f"Unknown strategy: {strategy_id}"

        strategy = STRATEGIES[strategy_id]
        query = strategy["build_query"](condition)
        params = build_params(query)

        start_time = time.time()
        try:
            total_count = fetch_total_count(
                self.session, params, timeout=DEFAULT_TIMEOUT
            )
            execution_time = time.time() - start_time
            return total_count, execution_time, None
        except Exception as e:
            execution_time = time.time() - start_time
            return 0, execution_time, str(e)

    def calculate_recall(
        self, condition: str, known_nct_ids: List[str], strategy_id: str
    ) -> float:
        """Calculate recall for a strategy against known NCT IDs"""
        if not known_nct_ids:
            return 0.0

        strategy = STRATEGIES[strategy_id]
        query = strategy["build_query"](condition)
        params = build_params(query)

        try:
            found_ncts, _ = fetch_nct_ids(
                self.session,
                params,
                timeout=DEFAULT_TIMEOUT,
                page_size=1000,
                max_pages=10,
            )
            known_set = {nct.upper() for nct in known_nct_ids}
            found_known = known_set & found_ncts
            recall = len(found_known) / len(known_set) * 100 if known_set else 0.0
            return recall
        except Exception:
            return 0.0

    def validate_condition(
        self,
        area_name: str,
        condition_id: str,
        condition_config: dict,
        calculate_recall: bool = True,
    ) -> ConditionResult:
        """Validate all strategies for a single condition"""
        primary_term = condition_config["primary_term"]

        result = ConditionResult(
            condition_id=condition_id,
            primary_term=primary_term,
            therapeutic_area=area_name,
        )

        # Get known NCT IDs if available
        known_ncts = KNOWN_NCT_IDS.get(condition_id, [])
        result.known_nct_ids = known_ncts

        print(f"    {primary_term}:")

        # Test all strategies
        for strategy_id in STRATEGIES:
            count, exec_time, error = self.search_condition(primary_term, strategy_id)

            result.strategy_results[strategy_id] = StrategyResult(
                strategy_id=strategy_id,
                strategy_name=STRATEGIES[strategy_id]["name"],
                total_count=count,
                execution_time=exec_time,
                error=error,
            )

            if strategy_id == "S1":
                result.baseline_count = count

            # Calculate recall for key strategies if NCT IDs available
            if calculate_recall and known_ncts and strategy_id in ["S1", "S3", "S10"]:
                recall = self.calculate_recall(primary_term, known_ncts, strategy_id)
                result.recall_metrics[strategy_id] = recall

            time.sleep(self.rate_limit)

        # Print summary line
        s1_count = result.strategy_results.get("S1", StrategyResult("", "", 0, 0)).total_count
        s3_count = result.strategy_results.get("S3", StrategyResult("", "", 0, 0)).total_count
        retention = (s3_count / s1_count * 100) if s1_count > 0 else 0

        recall_str = ""
        if result.recall_metrics:
            s3_recall = result.recall_metrics.get("S3", 0)
            recall_str = f", S3 recall: {s3_recall:.1f}%"

        print(f"      S1: {s1_count:,} | S3: {s3_count:,} ({retention:.1f}%){recall_str}")

        return result

    def validate_therapeutic_area(
        self, area_name: str, area_config: dict, calculate_recall: bool = True
    ) -> Dict[str, ConditionResult]:
        """Validate all conditions in a therapeutic area"""
        print(f"\n  {area_name} ({area_config['description']})")
        print("  " + "-" * 60)

        area_results = {}

        for condition_id, condition_config in area_config["conditions"].items():
            result = self.validate_condition(
                area_name, condition_id, condition_config, calculate_recall
            )
            area_results[condition_id] = result

        return area_results

    def run_full_validation(
        self, calculate_recall: bool = True
    ) -> Dict[str, Dict[str, ConditionResult]]:
        """Run validation across all therapeutic areas"""
        print("=" * 70)
        print("  EXPANDED THERAPEUTIC AREA VALIDATION")
        print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print(f"\n  Testing {len(THERAPEUTIC_AREAS)} therapeutic areas")
        print(f"  Testing {len(STRATEGIES)} search strategies")

        total_conditions = sum(
            len(area["conditions"]) for area in THERAPEUTIC_AREAS.values()
        )
        print(f"  Total conditions: {total_conditions}")
        print(f"  Total searches: {total_conditions * len(STRATEGIES)}")

        self.results = {}

        for area_name, area_config in THERAPEUTIC_AREAS.items():
            area_results = self.validate_therapeutic_area(
                area_name, area_config, calculate_recall
            )
            self.results[area_name] = area_results

        return self.results

    def generate_area_summary(self) -> List[TherapeuticAreaSummary]:
        """Generate summary statistics per therapeutic area"""
        summaries = []

        for area_name, conditions in self.results.items():
            total_s1 = sum(
                c.strategy_results.get("S1", StrategyResult("", "", 0, 0)).total_count
                for c in conditions.values()
            )
            total_s3 = sum(
                c.strategy_results.get("S3", StrategyResult("", "", 0, 0)).total_count
                for c in conditions.values()
            )

            retention_pcts = []
            for c in conditions.values():
                s1 = c.strategy_results.get("S1", StrategyResult("", "", 0, 0)).total_count
                s3 = c.strategy_results.get("S3", StrategyResult("", "", 0, 0)).total_count
                if s1 > 0:
                    retention_pcts.append(s3 / s1 * 100)

            avg_retention = sum(retention_pcts) / len(retention_pcts) if retention_pcts else 0

            summary = TherapeuticAreaSummary(
                area_name=area_name,
                description=THERAPEUTIC_AREAS[area_name]["description"],
                num_conditions=len(conditions),
                total_trials_s1=total_s1,
                total_trials_s3=total_s3,
                avg_retention_s3=avg_retention,
                conditions=list(conditions.keys()),
            )
            summaries.append(summary)

        return summaries

    def generate_strategy_comparison(self) -> Dict[str, Dict[str, float]]:
        """Generate strategy comparison across all conditions"""
        strategy_stats = {sid: {"total": 0, "retention_sum": 0, "count": 0} for sid in STRATEGIES}

        for area_results in self.results.values():
            for condition_result in area_results.values():
                baseline = condition_result.baseline_count
                if baseline == 0:
                    continue

                for strategy_id, strat_result in condition_result.strategy_results.items():
                    strategy_stats[strategy_id]["total"] += strat_result.total_count
                    strategy_stats[strategy_id]["retention_sum"] += (
                        strat_result.total_count / baseline * 100
                    )
                    strategy_stats[strategy_id]["count"] += 1

        # Calculate averages
        comparison = {}
        for strategy_id, stats in strategy_stats.items():
            comparison[strategy_id] = {
                "total_results": stats["total"],
                "avg_retention": (
                    stats["retention_sum"] / stats["count"]
                    if stats["count"] > 0
                    else 0
                ),
            }

        return comparison

    def generate_recall_summary(self) -> Dict[str, Dict[str, float]]:
        """Generate recall summary for conditions with known NCT IDs"""
        recall_summary = {}

        for area_name, conditions in self.results.items():
            for condition_id, condition_result in conditions.items():
                if condition_result.recall_metrics:
                    recall_summary[condition_id] = {
                        "therapeutic_area": area_name,
                        "primary_term": condition_result.primary_term,
                        "known_nct_count": len(condition_result.known_nct_ids),
                        **condition_result.recall_metrics,
                    }

        return recall_summary

    def print_summary_report(self):
        """Print comprehensive summary report"""
        print("\n" + "=" * 70)
        print("  SUMMARY REPORT")
        print("=" * 70)

        # Area summaries
        print("\n  THERAPEUTIC AREA SUMMARY:")
        print("  " + "-" * 65)
        print(f"  {'Area':<20} {'Cond':>5} {'S1 Total':>12} {'S3 Total':>12} {'S3 Ret%':>8}")
        print("  " + "-" * 65)

        summaries = self.generate_area_summary()
        for s in summaries:
            print(
                f"  {s.area_name:<20} {s.num_conditions:>5} "
                f"{s.total_trials_s1:>12,} {s.total_trials_s3:>12,} {s.avg_retention_s3:>7.1f}%"
            )

        # Strategy comparison
        print("\n  STRATEGY COMPARISON (Average Across All Conditions):")
        print("  " + "-" * 65)
        print(f"  {'Strategy':<5} {'Name':<35} {'Total':>12} {'Avg Ret%':>8}")
        print("  " + "-" * 65)

        comparison = self.generate_strategy_comparison()
        for sid in STRATEGIES:
            stats = comparison.get(sid, {"total_results": 0, "avg_retention": 0})
            print(
                f"  {sid:<5} {STRATEGIES[sid]['name']:<35} "
                f"{stats['total_results']:>12,} {stats['avg_retention']:>7.1f}%"
            )

        # Recall summary
        recall_summary = self.generate_recall_summary()
        if recall_summary:
            print("\n  RECALL METRICS (Conditions with Known NCT IDs):")
            print("  " + "-" * 65)
            print(f"  {'Condition':<25} {'Known':>6} {'S1':>8} {'S3':>8} {'S10':>8}")
            print("  " + "-" * 65)

            for cond_id, metrics in recall_summary.items():
                s1_recall = metrics.get("S1", 0)
                s3_recall = metrics.get("S3", 0)
                s10_recall = metrics.get("S10", 0)
                print(
                    f"  {cond_id:<25} {metrics['known_nct_count']:>6} "
                    f"{s1_recall:>7.1f}% {s3_recall:>7.1f}% {s10_recall:>7.1f}%"
                )

        print("\n  RECOMMENDATIONS:")
        print("  " + "-" * 65)
        print("  - For maximum recall: Use S1 (Condition Only)")
        print("  - For RCTs with good recall: Use S3 (Randomized Allocation)")
        print("  - For treatment trials: Use S10 (Treatment RCTs)")
        print("  - Always search multiple therapeutic areas for comprehensive reviews")

    def export_json(self, filename: Optional[str] = None) -> Path:
        """Export results to JSON"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"therapeutic_validation_{timestamp}.json"

        output_path = self.output_dir / filename

        # Convert results to serializable format
        export_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "therapeutic_areas": len(THERAPEUTIC_AREAS),
                "strategies": len(STRATEGIES),
                "total_conditions": sum(
                    len(area["conditions"]) for area in THERAPEUTIC_AREAS.values()
                ),
            },
            "therapeutic_areas": {},
            "area_summaries": [asdict(s) for s in self.generate_area_summary()],
            "strategy_comparison": self.generate_strategy_comparison(),
            "recall_summary": self.generate_recall_summary(),
        }

        for area_name, conditions in self.results.items():
            export_data["therapeutic_areas"][area_name] = {}
            for cond_id, cond_result in conditions.items():
                export_data["therapeutic_areas"][area_name][cond_id] = {
                    "primary_term": cond_result.primary_term,
                    "baseline_count": cond_result.baseline_count,
                    "known_nct_ids": cond_result.known_nct_ids,
                    "recall_metrics": cond_result.recall_metrics,
                    "strategies": {
                        sid: {
                            "name": sr.strategy_name,
                            "count": sr.total_count,
                            "time": sr.execution_time,
                            "error": sr.error,
                        }
                        for sid, sr in cond_result.strategy_results.items()
                    },
                }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)

        print(f"\n  JSON exported: {output_path}")
        return output_path

    def export_csv(self, filename: Optional[str] = None) -> Path:
        """Export results to CSV"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"therapeutic_validation_{timestamp}.csv"

        output_path = self.output_dir / filename

        rows = []
        for area_name, conditions in self.results.items():
            for cond_id, cond_result in conditions.items():
                baseline = cond_result.baseline_count
                for sid, sr in cond_result.strategy_results.items():
                    retention = (sr.total_count / baseline * 100) if baseline > 0 else 0
                    recall = cond_result.recall_metrics.get(sid, None)

                    rows.append({
                        "therapeutic_area": area_name,
                        "condition_id": cond_id,
                        "primary_term": cond_result.primary_term,
                        "strategy_id": sid,
                        "strategy_name": sr.strategy_name,
                        "result_count": sr.total_count,
                        "baseline_count": baseline,
                        "retention_pct": round(retention, 2),
                        "recall_pct": round(recall, 2) if recall is not None else "",
                        "execution_time": round(sr.execution_time, 3),
                        "error": sr.error or "",
                    })

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

        print(f"  CSV exported: {output_path}")
        return output_path


# =============================================================================
# MAIN
# =============================================================================


def main():
    """Run expanded therapeutic area validation"""
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")

    validator = ExpandedTherapeuticValidation(
        output_dir=str(output_dir),
        rate_limit=DEFAULT_RATE_LIMIT,
    )

    # Run validation
    validator.run_full_validation(calculate_recall=True)

    # Print summary
    validator.print_summary_report()

    # Export results
    validator.export_json()
    validator.export_csv()

    print("\n" + "=" * 70)
    print("  Validation complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
