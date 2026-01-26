#!/usr/bin/env python3
"""
Drug Name Expander
Expands drug names to all known variants using external databases.

Sources:
- RxNorm API (free)
- OpenFDA API (free)
- Built-in dictionary for common drugs

Author: Mahmood Ahmad
Version: 1.0
"""

import requests
import time
from typing import List, Set, Dict
from functools import lru_cache


class DrugNameExpander:
    """
    Expands a drug name to all known variants including:
    - Generic names
    - Brand names
    - International names
    - Chemical names
    - Common abbreviations
    """

    # Built-in dictionary for common drugs (faster than API)
    COMMON_DRUGS = {
        "metformin": [
            "metformin", "metformin hydrochloride", "metformin hcl",
            "glucophage", "glucophage xr", "fortamet", "glumetza", "riomet",
            "dimethylbiguanide", "metformina", "metformine"
        ],
        "aspirin": [
            "aspirin", "acetylsalicylic acid", "asa", "acetyl salicylic acid",
            "bayer aspirin", "ecotrin", "bufferin", "aspirina"
        ],
        "atorvastatin": [
            "atorvastatin", "atorvastatin calcium", "lipitor",
            "atorvastatina", "atorvastatine"
        ],
        "lisinopril": [
            "lisinopril", "prinivil", "zestril", "lisinoprilum"
        ],
        "amlodipine": [
            "amlodipine", "amlodipine besylate", "norvasc",
            "amlodipina", "amlodipino"
        ],
        "omeprazole": [
            "omeprazole", "prilosec", "losec", "omeprazol"
        ],
        "simvastatin": [
            "simvastatin", "zocor", "simvastatina", "simvastatine"
        ],
        "losartan": [
            "losartan", "losartan potassium", "cozaar", "losartana"
        ],
        "gabapentin": [
            "gabapentin", "neurontin", "gralise", "gabapentina"
        ],
        "sertraline": [
            "sertraline", "sertraline hydrochloride", "zoloft", "sertralina"
        ],
        "fluoxetine": [
            "fluoxetine", "fluoxetine hydrochloride", "prozac", "sarafem",
            "fluoxetina"
        ],
        "insulin": [
            "insulin", "insulin human", "insulin glargine", "lantus",
            "insulin lispro", "humalog", "insulin aspart", "novolog",
            "insulin detemir", "levemir", "insulin degludec", "tresiba"
        ],
        "warfarin": [
            "warfarin", "warfarin sodium", "coumadin", "jantoven", "warfarina"
        ],
        "clopidogrel": [
            "clopidogrel", "clopidogrel bisulfate", "plavix", "clopidogrelum"
        ],
        "prednisone": [
            "prednisone", "deltasone", "rayos", "prednisolone", "prednisona"
        ],
        "levothyroxine": [
            "levothyroxine", "levothyroxine sodium", "synthroid", "levoxyl",
            "l-thyroxine", "levotiroxina"
        ],
        "metoprolol": [
            "metoprolol", "metoprolol succinate", "metoprolol tartrate",
            "lopressor", "toprol", "toprol-xl"
        ],
        "hydrochlorothiazide": [
            "hydrochlorothiazide", "hctz", "microzide", "hydrodiuril"
        ],
        "acetaminophen": [
            "acetaminophen", "paracetamol", "tylenol", "panadol", "apap"
        ],
        "ibuprofen": [
            "ibuprofen", "advil", "motrin", "nurofen", "ibuprofeno"
        ],
        "amoxicillin": [
            "amoxicillin", "amoxil", "amoxicilina", "amoxicilline"
        ],
        "azithromycin": [
            "azithromycin", "zithromax", "z-pack", "azitromicina"
        ],
        "montelukast": [
            "montelukast", "montelukast sodium", "singulair"
        ],
        "albuterol": [
            "albuterol", "salbutamol", "ventolin", "proventil", "proair"
        ],
        "pantoprazole": [
            "pantoprazole", "pantoprazole sodium", "protonix", "pantoprazol"
        ],
        "rosuvastatin": [
            "rosuvastatin", "rosuvastatin calcium", "crestor", "rosuvastatina"
        ],
        "duloxetine": [
            "duloxetine", "duloxetine hydrochloride", "cymbalta", "duloxetina"
        ],
        "escitalopram": [
            "escitalopram", "escitalopram oxalate", "lexapro", "cipralex"
        ],
        "trastuzumab": [
            "trastuzumab", "herceptin", "herzuma", "ogivri", "ontruzant"
        ],
        "pembrolizumab": [
            "pembrolizumab", "keytruda", "anti-pd-1", "pd-1 inhibitor"
        ],
        "nivolumab": [
            "nivolumab", "opdivo", "anti-pd-1"
        ],
        "rituximab": [
            "rituximab", "rituxan", "mabthera", "anti-cd20"
        ],
        "adalimumab": [
            "adalimumab", "humira", "anti-tnf", "tnf inhibitor"
        ],
        "infliximab": [
            "infliximab", "remicade", "anti-tnf", "tnf inhibitor"
        ],
        "etanercept": [
            "etanercept", "enbrel", "anti-tnf", "tnf inhibitor"
        ],
        "bevacizumab": [
            "bevacizumab", "avastin", "anti-vegf", "vegf inhibitor"
        ],
        "empagliflozin": [
            "empagliflozin", "jardiance", "sglt2 inhibitor"
        ],
        "dapagliflozin": [
            "dapagliflozin", "farxiga", "forxiga", "sglt2 inhibitor"
        ],
        "canagliflozin": [
            "canagliflozin", "invokana", "sglt2 inhibitor"
        ],
        "semaglutide": [
            "semaglutide", "ozempic", "wegovy", "rybelsus", "glp-1 agonist"
        ],
        "liraglutide": [
            "liraglutide", "victoza", "saxenda", "glp-1 agonist"
        ],
        "sitagliptin": [
            "sitagliptin", "januvia", "dpp-4 inhibitor"
        ],
    }

    RXNORM_API = "https://rxnav.nlm.nih.gov/REST"
    OPENFDA_API = "https://api.fda.gov/drug"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "DrugExpander/1.0"})

    def expand(self, drug_name: str, use_api: bool = True) -> Set[str]:
        """
        Expand a drug name to all known variants.

        Args:
            drug_name: The drug name to expand
            use_api: Whether to query external APIs (slower but more complete)

        Returns:
            Set of all known names for this drug
        """
        drug_lower = drug_name.lower().strip()
        variants = {drug_lower, drug_name}

        # Check built-in dictionary first
        if drug_lower in self.COMMON_DRUGS:
            variants.update(self.COMMON_DRUGS[drug_lower])
        else:
            # Check if it's a variant of a known drug
            for base_drug, names in self.COMMON_DRUGS.items():
                if drug_lower in [n.lower() for n in names]:
                    variants.update(names)
                    break

        # Query APIs for more variants
        if use_api:
            try:
                rxnorm_variants = self._query_rxnorm(drug_name)
                variants.update(rxnorm_variants)
            except Exception:
                pass  # API failed, use what we have

        return variants

    @lru_cache(maxsize=500)
    def _query_rxnorm(self, drug_name: str) -> Set[str]:
        """Query RxNorm API for drug name variants"""
        variants = set()

        try:
            # Get RxCUI for the drug
            url = f"{self.RXNORM_API}/rxcui.json"
            params = {"name": drug_name, "search": 2}
            response = self.session.get(url, params=params, timeout=10)

            if response.status_code != 200:
                return variants

            data = response.json()
            rxcuis = data.get("idGroup", {}).get("rxnormId", [])

            if not rxcuis:
                return variants

            rxcui = rxcuis[0]

            # Get all related names
            url = f"{self.RXNORM_API}/rxcui/{rxcui}/allrelated.json"
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                concept_groups = data.get("allRelatedGroup", {}).get("conceptGroup", [])

                for group in concept_groups:
                    concepts = group.get("conceptProperties", [])
                    for concept in concepts:
                        name = concept.get("name", "")
                        if name:
                            variants.add(name.lower())

            time.sleep(0.1)  # Rate limiting

        except Exception:
            pass

        return variants

    def expand_multiple(self, drug_names: List[str]) -> Dict[str, Set[str]]:
        """Expand multiple drug names"""
        return {drug: self.expand(drug) for drug in drug_names}


class ConditionExpander:
    """
    Expands condition/disease names using MeSH hierarchy and synonyms.
    """

    # Built-in condition expansions
    CONDITION_TERMS = {
        "type 2 diabetes": [
            "type 2 diabetes", "type 2 diabetes mellitus", "t2dm", "t2d",
            "diabetes mellitus type 2", "non-insulin dependent diabetes",
            "niddm", "adult onset diabetes", "maturity onset diabetes",
            "diabetes mellitus, type 2"
        ],
        "type 1 diabetes": [
            "type 1 diabetes", "type 1 diabetes mellitus", "t1dm", "t1d",
            "diabetes mellitus type 1", "insulin dependent diabetes",
            "iddm", "juvenile diabetes", "diabetes mellitus, type 1"
        ],
        "diabetes": [
            "diabetes", "diabetes mellitus", "diabetic", "dm"
        ],
        "hypertension": [
            "hypertension", "high blood pressure", "htn", "elevated blood pressure",
            "arterial hypertension", "essential hypertension"
        ],
        "heart failure": [
            "heart failure", "cardiac failure", "congestive heart failure",
            "chf", "hf", "left ventricular failure", "right ventricular failure",
            "systolic heart failure", "diastolic heart failure", "hfref", "hfpef"
        ],
        "myocardial infarction": [
            "myocardial infarction", "heart attack", "mi", "ami",
            "acute myocardial infarction", "stemi", "nstemi",
            "st elevation myocardial infarction", "non-st elevation myocardial infarction"
        ],
        "stroke": [
            "stroke", "cerebrovascular accident", "cva", "brain attack",
            "ischemic stroke", "hemorrhagic stroke", "cerebral infarction",
            "cerebrovascular disease"
        ],
        "breast cancer": [
            "breast cancer", "breast neoplasm", "breast carcinoma",
            "mammary cancer", "breast tumor", "breast malignancy",
            "breast neoplasms"
        ],
        "lung cancer": [
            "lung cancer", "lung neoplasm", "lung carcinoma",
            "pulmonary cancer", "nsclc", "sclc",
            "non-small cell lung cancer", "small cell lung cancer"
        ],
        "copd": [
            "copd", "chronic obstructive pulmonary disease",
            "chronic obstructive lung disease", "emphysema",
            "chronic bronchitis", "cold"
        ],
        "asthma": [
            "asthma", "bronchial asthma", "asthmatic", "reactive airway disease"
        ],
        "depression": [
            "depression", "major depressive disorder", "mdd",
            "depressive disorder", "clinical depression", "major depression",
            "unipolar depression"
        ],
        "anxiety": [
            "anxiety", "anxiety disorder", "generalized anxiety disorder",
            "gad", "anxiety disorders"
        ],
        "rheumatoid arthritis": [
            "rheumatoid arthritis", "ra", "rheumatoid disease",
            "inflammatory arthritis"
        ],
        "osteoarthritis": [
            "osteoarthritis", "oa", "degenerative arthritis",
            "degenerative joint disease", "djd"
        ],
        "alzheimer": [
            "alzheimer", "alzheimer's disease", "alzheimers disease",
            "alzheimer disease", "ad", "dementia"
        ],
        "parkinson": [
            "parkinson", "parkinson's disease", "parkinsons disease",
            "parkinson disease", "pd", "parkinsonism"
        ],
        "hiv": [
            "hiv", "hiv infection", "hiv/aids", "aids",
            "human immunodeficiency virus", "hiv-1", "hiv-2"
        ],
        "covid": [
            "covid", "covid-19", "sars-cov-2", "coronavirus",
            "coronavirus disease 2019", "2019-ncov"
        ],
        "obesity": [
            "obesity", "obese", "overweight", "morbid obesity",
            "severe obesity"
        ],
        "atrial fibrillation": [
            "atrial fibrillation", "afib", "af", "a-fib",
            "auricular fibrillation"
        ],
    }

    MESH_API = "https://id.nlm.nih.gov/mesh/lookup/descriptor"

    def __init__(self):
        self.session = requests.Session()

    def expand(self, condition: str, use_api: bool = False) -> Set[str]:
        """Expand a condition to all known variants"""
        condition_lower = condition.lower().strip()
        variants = {condition_lower, condition}

        # Check built-in dictionary
        for base_condition, terms in self.CONDITION_TERMS.items():
            if condition_lower in [t.lower() for t in terms] or base_condition in condition_lower:
                variants.update([t.lower() for t in terms])

        # Also add singular/plural variants
        if condition_lower.endswith('s'):
            variants.add(condition_lower[:-1])
        else:
            variants.add(condition_lower + 's')

        return variants

    def expand_multiple(self, conditions: List[str]) -> Dict[str, Set[str]]:
        """Expand multiple conditions"""
        return {cond: self.expand(cond) for cond in conditions}


def main():
    """Test the expanders"""
    drug_exp = DrugNameExpander()
    cond_exp = ConditionExpander()

    # Test drug expansion
    print("=" * 60)
    print("Drug Name Expansion")
    print("=" * 60)

    test_drugs = ["metformin", "aspirin", "pembrolizumab", "insulin"]
    for drug in test_drugs:
        variants = drug_exp.expand(drug, use_api=False)
        print(f"\n{drug}: {len(variants)} variants")
        print(f"  {', '.join(sorted(variants)[:10])}...")

    # Test condition expansion
    print("\n" + "=" * 60)
    print("Condition Expansion")
    print("=" * 60)

    test_conditions = ["type 2 diabetes", "heart failure", "breast cancer"]
    for cond in test_conditions:
        variants = cond_exp.expand(cond)
        print(f"\n{cond}: {len(variants)} variants")
        print(f"  {', '.join(sorted(variants)[:10])}...")


if __name__ == "__main__":
    main()
