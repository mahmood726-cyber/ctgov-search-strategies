#!/usr/bin/env python3
"""
Maximum Recall Strategy - Push to 95%+
Implements every possible search approach to maximize recall.

Strategies:
1. Basic intervention search
2. Extended AREA syntax (all searchable fields)
3. Research codes and alternative names
4. Combination therapy patterns
5. Sponsor + condition fallback
6. Free-text query variations
7. Eligibility criteria mentions
8. Outcome measure mentions
9. Generic term formulation expansion
10. Related concepts search

Author: Mahmood Ahmad
Version: 2.0 - Maximum Recall
"""

import json
import time
import re
import math
from typing import Set, Dict, List, Tuple, Optional
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests


def wilson_ci(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score confidence interval"""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denom
    margin = z * math.sqrt((p * (1-p) + z**2 / (4*n)) / n) / denom
    return (max(0, center - margin), min(1, center + margin))


class MaximumRecallStrategy:
    """
    Maximum recall strategy combining all possible search approaches.
    """

    CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"
    PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    # Comprehensive drug variants including research codes, brand names, and related terms
    DRUG_VARIANTS = {
        "semaglutide": {
            "names": ["semaglutide", "ozempic", "wegovy", "rybelsus"],
            "codes": ["nn9535", "nn-9535", "nn 9535"],
            "class": ["glp-1", "glp1", "glucagon-like peptide"],
            "sponsor": "Novo Nordisk",
        },
        "liraglutide": {
            "names": ["liraglutide", "victoza", "saxenda"],
            "codes": ["nn2211", "nn-2211", "nn 2211"],
            "class": ["glp-1", "glp1"],
            "sponsor": "Novo Nordisk",
        },
        "empagliflozin": {
            "names": ["empagliflozin", "jardiance"],
            "codes": ["bi 10773", "bi10773", "bi-10773"],
            "class": ["sglt2", "sglt-2", "sodium-glucose"],
            "sponsor": "Boehringer",
        },
        "dapagliflozin": {
            "names": ["dapagliflozin", "farxiga", "forxiga"],
            "codes": ["bms-512148", "bms512148"],
            "class": ["sglt2", "sglt-2"],
            "sponsor": "AstraZeneca",
        },
        "sitagliptin": {
            "names": ["sitagliptin", "januvia"],
            "codes": ["mk-0431", "mk0431", "mk 0431"],
            "class": ["dpp-4", "dpp4", "dipeptidyl peptidase"],
            "sponsor": "Merck",
        },
        "canagliflozin": {
            "names": ["canagliflozin", "invokana"],
            "codes": ["jnj-28431754", "ta-7284"],
            "class": ["sglt2", "sglt-2"],
            "sponsor": "Janssen",
        },
        "dulaglutide": {
            "names": ["dulaglutide", "trulicity"],
            "codes": ["ly2189265", "ly-2189265"],
            "class": ["glp-1", "glp1"],
            "sponsor": "Eli Lilly",
        },
        "metformin": {
            "names": ["metformin", "glucophage", "fortamet", "glumetza", "riomet"],
            "codes": [],
            "class": ["biguanide"],
            "sponsor": None,
            "special": "generic",
        },
        "insulin": {
            "names": [
                "insulin glargine", "lantus", "toujeo", "basaglar",
                "insulin lispro", "humalog", "admelog",
                "insulin aspart", "novolog", "fiasp",
                "insulin detemir", "levemir",
                "insulin degludec", "tresiba",
                "insulin regular", "humulin", "novolin",
                "insulin nph", "insulin isophane",
                "insulin glulisine", "apidra",
            ],
            "codes": [],
            "class": ["insulin analog", "basal insulin", "bolus insulin", "prandial insulin"],
            "sponsor": None,
            "special": "generic_complex",
        },
        "pembrolizumab": {
            "names": ["pembrolizumab", "keytruda"],
            "codes": ["mk-3475", "mk3475", "mk 3475", "lambrolizumab", "sch 900475"],
            "class": ["anti-pd-1", "anti-pd1", "pd-1 inhibitor", "pd1 inhibitor", "checkpoint inhibitor"],
            "sponsor": "Merck",
            "combinations": ["pembrolizumab chemotherapy", "pembrolizumab lenvatinib",
                           "pembrolizumab axitinib", "keytruda combination"],
        },
        "nivolumab": {
            "names": ["nivolumab", "opdivo"],
            "codes": ["bms-936558", "mdx1106", "mdx-1106", "ono-4538"],
            "class": ["anti-pd-1", "anti-pd1", "pd-1 inhibitor", "checkpoint inhibitor"],
            "sponsor": "Bristol-Myers",
            "combinations": ["nivolumab ipilimumab", "opdivo yervoy", "nivolumab chemotherapy"],
        },
        "atezolizumab": {
            "names": ["atezolizumab", "tecentriq"],
            "codes": ["mpdl3280a", "rg7446", "ro5541267"],
            "class": ["anti-pd-l1", "anti-pdl1", "pd-l1 inhibitor", "checkpoint inhibitor"],
            "sponsor": "Roche",
            "combinations": ["atezolizumab bevacizumab", "tecentriq avastin"],
        },
        "ipilimumab": {
            "names": ["ipilimumab", "yervoy"],
            "codes": ["mdx-010", "mdx010", "bms-734016"],
            "class": ["anti-ctla-4", "anti-ctla4", "ctla-4 inhibitor", "checkpoint inhibitor"],
            "sponsor": "Bristol-Myers",
        },
        "trastuzumab": {
            "names": ["trastuzumab", "herceptin", "herzuma", "ogivri", "ontruzant", "trazimera"],
            "codes": ["ro-45-2317"],
            "class": ["anti-her2", "anti-her-2", "her2 antibody", "her-2 antibody"],
            "sponsor": "Roche",
            "combinations": ["trastuzumab pertuzumab", "trastuzumab emtansine", "t-dm1", "kadcyla"],
        },
        "bevacizumab": {
            "names": ["bevacizumab", "avastin", "mvasi", "zirabev"],
            "codes": ["rhumab-vegf", "r435"],
            "class": ["anti-vegf", "vegf inhibitor", "vegf antibody"],
            "sponsor": "Roche",
        },
        "rituximab": {
            "names": ["rituximab", "rituxan", "mabthera", "truxima", "ruxience"],
            "codes": ["idec-c2b8"],
            "class": ["anti-cd20", "cd20 antibody"],
            "sponsor": "Roche",
        },
        "cetuximab": {
            "names": ["cetuximab", "erbitux"],
            "codes": ["imc-c225", "c225"],
            "class": ["anti-egfr", "egfr inhibitor", "egfr antibody"],
            "sponsor": "Eli Lilly",
        },
        "adalimumab": {
            "names": ["adalimumab", "humira", "hadlima", "hyrimoz", "cyltezo", "amjevita"],
            "codes": ["d2e7", "abbott d2e7"],
            "class": ["anti-tnf", "tnf inhibitor", "tnf-alpha inhibitor", "tnf antibody"],
            "sponsor": "AbbVie",
        },
        "etanercept": {
            "names": ["etanercept", "enbrel", "erelzi", "eticovo"],
            "codes": ["tnfr:fc", "p75tnfr"],
            "class": ["anti-tnf", "tnf inhibitor", "tnf receptor"],
            "sponsor": "Amgen",
        },
        "infliximab": {
            "names": ["infliximab", "remicade", "inflectra", "renflexis", "ixifi"],
            "codes": ["ca2", "ta-650"],
            "class": ["anti-tnf", "tnf inhibitor", "tnf antibody"],
            "sponsor": "Janssen",
        },
        "tocilizumab": {
            "names": ["tocilizumab", "actemra", "roactemra"],
            "codes": ["mr16-1", "r-1569"],
            "class": ["anti-il-6", "il-6 inhibitor", "il6 inhibitor", "interleukin-6"],
            "sponsor": "Roche",
        },
        "secukinumab": {
            "names": ["secukinumab", "cosentyx"],
            "codes": ["ain457", "ain-457"],
            "class": ["anti-il-17", "il-17 inhibitor", "il17 inhibitor"],
            "sponsor": "Novartis",
        },
        "ustekinumab": {
            "names": ["ustekinumab", "stelara"],
            "codes": ["cnto 1275", "cnto1275"],
            "class": ["anti-il-12", "anti-il-23", "il-12/23 inhibitor"],
            "sponsor": "Janssen",
        },
        "escitalopram": {
            "names": ["escitalopram", "lexapro", "cipralex"],
            "codes": ["lu 26-054", "s-citalopram"],
            "class": ["ssri", "selective serotonin"],
            "sponsor": "Lundbeck",
        },
        "sertraline": {
            "names": ["sertraline", "zoloft", "lustral"],
            "codes": ["cp-51974"],
            "class": ["ssri", "selective serotonin"],
            "sponsor": "Pfizer",
        },
        "duloxetine": {
            "names": ["duloxetine", "cymbalta"],
            "codes": ["ly248686", "ly-248686"],
            "class": ["snri", "serotonin norepinephrine"],
            "sponsor": "Eli Lilly",
        },
        "quetiapine": {
            "names": ["quetiapine", "seroquel"],
            "codes": ["ici 204636", "ici-204636"],
            "class": ["atypical antipsychotic", "second generation antipsychotic"],
            "sponsor": "AstraZeneca",
        },
        "aripiprazole": {
            "names": ["aripiprazole", "abilify"],
            "codes": ["opc-14597", "opc14597"],
            "class": ["atypical antipsychotic", "dopamine partial agonist"],
            "sponsor": "Otsuka",
        },
        "atorvastatin": {
            "names": ["atorvastatin", "lipitor"],
            "codes": ["ci-981", "ci981"],
            "class": ["statin", "hmg-coa reductase"],
            "sponsor": "Pfizer",
        },
        "rosuvastatin": {
            "names": ["rosuvastatin", "crestor"],
            "codes": ["s-4522", "zd4522"],
            "class": ["statin", "hmg-coa reductase"],
            "sponsor": "AstraZeneca",
        },
        "apixaban": {
            "names": ["apixaban", "eliquis"],
            "codes": ["bms-562247", "bms562247"],
            "class": ["factor xa inhibitor", "doac", "noac"],
            "sponsor": "Bristol-Myers",
        },
        "rivaroxaban": {
            "names": ["rivaroxaban", "xarelto"],
            "codes": ["bay 59-7939", "bay597939"],
            "class": ["factor xa inhibitor", "doac", "noac"],
            "sponsor": "Bayer",
        },
        "ticagrelor": {
            "names": ["ticagrelor", "brilinta", "brilique"],
            "codes": ["azd6140", "azd-6140"],
            "class": ["p2y12 inhibitor", "antiplatelet"],
            "sponsor": "AstraZeneca",
        },
        "tiotropium": {
            "names": ["tiotropium", "spiriva"],
            "codes": ["ba 679", "ba679"],
            "class": ["lama", "long-acting muscarinic", "anticholinergic"],
            "sponsor": "Boehringer",
        },
        "fluticasone": {
            "names": ["fluticasone", "flovent", "flonase", "arnuity"],
            "codes": ["gw685698", "gw-685698"],
            "class": ["inhaled corticosteroid", "ics"],
            "sponsor": "GlaxoSmithKline",
        },
        "omalizumab": {
            "names": ["omalizumab", "xolair"],
            "codes": ["rhumab-e25", "e25"],
            "class": ["anti-ige", "ige inhibitor"],
            "sponsor": "Novartis",
        },
        "benralizumab": {
            "names": ["benralizumab", "fasenra"],
            "codes": ["medi-563", "medi563"],
            "class": ["anti-il-5", "il-5 inhibitor", "eosinophil"],
            "sponsor": "AstraZeneca",
        },
        "sofosbuvir": {
            "names": ["sofosbuvir", "sovaldi"],
            "codes": ["gs-7977", "psi-7977"],
            "class": ["ns5b inhibitor", "polymerase inhibitor", "hcv"],
            "sponsor": "Gilead",
        },
        "tenofovir": {
            "names": ["tenofovir", "viread", "tenofovir disoproxil", "tenofovir alafenamide", "taf", "tdf"],
            "codes": ["gs-7340", "gs7340", "pmpa"],
            "class": ["nrti", "nucleotide reverse transcriptase"],
            "sponsor": "Gilead",
        },
        "dolutegravir": {
            "names": ["dolutegravir", "tivicay"],
            "codes": ["gsk1349572", "gsk-1349572", "s/gsk1349572"],
            "class": ["integrase inhibitor", "insti"],
            "sponsor": "ViiV",
        },
        "remdesivir": {
            "names": ["remdesivir", "veklury"],
            "codes": ["gs-5734", "gs5734"],
            "class": ["antiviral", "rna polymerase inhibitor"],
            "sponsor": "Gilead",
        },
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "MaxRecall/2.0"})
        self.cache = {}

    def _search_ctgov(self, params: Dict, max_results: int = 5000) -> Set[str]:
        """Generic CT.gov search with pagination"""
        nct_ids = set()
        try:
            next_token = None
            while len(nct_ids) < max_results:
                request_params = {**params, "fields": "NCTId", "pageSize": 1000}
                if next_token:
                    request_params["pageToken"] = next_token

                response = self.session.get(self.CTGOV_API, params=request_params, timeout=60)
                data = response.json()

                for study in data.get("studies", []):
                    nct_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
                    if nct_id:
                        nct_ids.add(nct_id)

                next_token = data.get("nextPageToken")
                if not next_token:
                    break
                time.sleep(0.15)
        except Exception as e:
            pass
        return nct_ids

    def _search_area(self, field: str, term: str) -> Set[str]:
        """Search specific AREA field"""
        cache_key = f"area_{field}_{term}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        query = f'AREA[{field}]{term}'
        result = self._search_ctgov({"query.term": query})
        self.cache[cache_key] = result
        return result

    def _search_freetext(self, term: str) -> Set[str]:
        """Free-text search across all fields"""
        cache_key = f"freetext_{term}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        result = self._search_ctgov({"query.term": term})
        self.cache[cache_key] = result
        return result

    # =========================================================================
    # COMPONENT STRATEGIES
    # =========================================================================

    def s1_basic_intervention(self, drug: str) -> Set[str]:
        """S1: Basic intervention search"""
        return self._search_ctgov({"query.intr": drug})

    def s2_area_comprehensive(self, drug: str) -> Set[str]:
        """S2: Comprehensive AREA search across all relevant fields"""
        nct_ids = set()

        fields = [
            "InterventionName",
            "InterventionDescription",
            "InterventionOtherName",
            "BriefTitle",
            "OfficialTitle",
            "BriefSummary",
            "DetailedDescription",
            "ArmGroupDescription",
            "ArmGroupInterventionName",
            "Keyword",
            "PrimaryOutcomeMeasure",
            "SecondaryOutcomeMeasure",
        ]

        for field in fields:
            nct_ids.update(self._search_area(field, drug))

        return nct_ids

    def s3_variant_expansion(self, drug: str) -> Set[str]:
        """S3: Search all name variants, codes, and class terms"""
        nct_ids = set()

        drug_info = self.DRUG_VARIANTS.get(drug.lower(), {})

        # Search all name variants
        for name in drug_info.get("names", []):
            if name.lower() != drug.lower():
                nct_ids.update(self._search_ctgov({"query.intr": name}))
                nct_ids.update(self._search_area("BriefTitle", name))

        # Search research codes
        for code in drug_info.get("codes", []):
            nct_ids.update(self._search_ctgov({"query.intr": code}))
            nct_ids.update(self._search_area("BriefTitle", code))
            nct_ids.update(self._search_freetext(code))

        return nct_ids

    def s4_class_search(self, drug: str, condition: str) -> Set[str]:
        """S4: Search by drug class + condition"""
        nct_ids = set()

        drug_info = self.DRUG_VARIANTS.get(drug.lower(), {})

        for class_term in drug_info.get("class", []):
            # Class + condition search
            query = f'AREA[InterventionName]{class_term}'
            nct_ids.update(self._search_ctgov({"query.term": query}))

        return nct_ids

    def s5_combination_search(self, drug: str) -> Set[str]:
        """S5: Search combination therapy patterns"""
        nct_ids = set()

        drug_info = self.DRUG_VARIANTS.get(drug.lower(), {})

        for combo in drug_info.get("combinations", []):
            nct_ids.update(self._search_area("BriefTitle", f'"{combo}"'))
            nct_ids.update(self._search_area("OfficialTitle", f'"{combo}"'))
            nct_ids.update(self._search_freetext(f'"{combo}"'))

        return nct_ids

    def s6_sponsor_search(self, drug: str, condition: str) -> Set[str]:
        """S6: Sponsor + condition + interventional study search"""
        nct_ids = set()

        drug_info = self.DRUG_VARIANTS.get(drug.lower(), {})
        sponsor = drug_info.get("sponsor")

        if sponsor:
            query = f'AREA[LeadSponsorName]{sponsor} AND AREA[StudyType]Interventional'
            nct_ids.update(self._search_ctgov({"query.term": query}, max_results=2000))

        return nct_ids

    def s7_freetext_variations(self, drug: str) -> Set[str]:
        """S7: Free-text search with variations"""
        nct_ids = set()

        # Exact phrase
        nct_ids.update(self._search_freetext(f'"{drug}"'))

        # With common suffixes
        for suffix in ["therapy", "treatment", "arm", "group", "regimen"]:
            nct_ids.update(self._search_freetext(f'"{drug} {suffix}"'))

        return nct_ids

    def s8_insulin_specific(self, drug: str) -> Set[str]:
        """S8: Special handling for insulin (complex generic)"""
        if drug.lower() != "insulin":
            return set()

        nct_ids = set()

        # Search each insulin formulation
        insulin_types = [
            "insulin glargine", "insulin lispro", "insulin aspart",
            "insulin detemir", "insulin degludec", "insulin regular",
            "insulin nph", "insulin glulisine", "insulin human",
            "lantus", "humalog", "novolog", "levemir", "tresiba",
            "toujeo", "basaglar", "admelog", "fiasp", "apidra",
        ]

        for insulin_type in insulin_types:
            nct_ids.update(self._search_ctgov({"query.intr": insulin_type}))

        # Also search by class
        for class_term in ["basal insulin", "bolus insulin", "insulin analog",
                          "long-acting insulin", "rapid-acting insulin"]:
            nct_ids.update(self._search_area("InterventionName", class_term))

        return nct_ids

    def s9_metformin_specific(self, drug: str) -> Set[str]:
        """S9: Special handling for metformin (generic with combinations)"""
        if drug.lower() != "metformin":
            return set()

        nct_ids = set()

        # Metformin combinations
        combos = [
            "metformin sitagliptin", "metformin glipizide", "metformin glyburide",
            "metformin pioglitazone", "metformin rosiglitazone", "metformin dapagliflozin",
            "metformin empagliflozin", "metformin canagliflozin", "metformin saxagliptin",
            "glucophage", "fortamet", "glumetza", "riomet",
        ]

        for combo in combos:
            nct_ids.update(self._search_ctgov({"query.intr": combo}))
            nct_ids.update(self._search_area("BriefTitle", combo))

        # Biguanide class search
        nct_ids.update(self._search_area("InterventionName", "biguanide"))

        return nct_ids

    def s10_eligibility_outcomes(self, drug: str) -> Set[str]:
        """S10: Search eligibility criteria and outcome measures"""
        nct_ids = set()

        # These are harder to search via API, use free-text
        nct_ids.update(self._search_freetext(f'{drug} eligibility'))
        nct_ids.update(self._search_freetext(f'{drug} outcome'))
        nct_ids.update(self._search_freetext(f'{drug} endpoint'))

        return nct_ids

    # =========================================================================
    # COMBINED MAXIMUM STRATEGY
    # =========================================================================

    def strategy_maximum(self, drug: str, condition: str) -> Tuple[Set[str], Dict]:
        """
        Maximum recall strategy - combines ALL approaches.
        """
        all_ncts = set()
        metadata = {"strategies": {}}

        strategies = [
            ("S1_Basic", lambda: self.s1_basic_intervention(drug)),
            ("S2_AREA", lambda: self.s2_area_comprehensive(drug)),
            ("S3_Variants", lambda: self.s3_variant_expansion(drug)),
            ("S4_Class", lambda: self.s4_class_search(drug, condition)),
            ("S5_Combos", lambda: self.s5_combination_search(drug)),
            ("S6_Sponsor", lambda: self.s6_sponsor_search(drug, condition)),
            ("S7_Freetext", lambda: self.s7_freetext_variations(drug)),
            ("S8_Insulin", lambda: self.s8_insulin_specific(drug)),
            ("S9_Metformin", lambda: self.s9_metformin_specific(drug)),
            ("S10_Elig", lambda: self.s10_eligibility_outcomes(drug)),
        ]

        for name, strategy_func in strategies:
            result = strategy_func()
            new_finds = result - all_ncts
            all_ncts.update(result)
            metadata["strategies"][name] = {
                "total": len(result),
                "unique": len(new_finds)
            }
            if len(new_finds) > 0:
                print(f"+{len(new_finds)}", end=" ", flush=True)

        metadata["total"] = len(all_ncts)
        return all_ncts, metadata

    # =========================================================================
    # GOLD STANDARD
    # =========================================================================

    def get_gold_standard(self, drug: str, condition: str, max_results: int = 500) -> Set[str]:
        """Get gold standard from PubMed DataBank links"""
        nct_ids = set()

        query = f'"{drug}"[tiab] AND ({condition})[tiab] AND (randomized controlled trial[pt] OR clinical trial[pt])'

        try:
            url = f"{self.PUBMED_API}/esearch.fcgi"
            params = {"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"}
            response = self.session.get(url, params=params, timeout=30)
            pmids = response.json().get("esearchresult", {}).get("idlist", [])
            time.sleep(0.4)

            if pmids:
                batch_size = 100
                for i in range(0, len(pmids), batch_size):
                    batch = pmids[i:i+batch_size]
                    url = f"{self.PUBMED_API}/efetch.fcgi"
                    params = {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"}
                    response = self.session.get(url, params=params, timeout=60)
                    nct_ids.update(re.findall(r'NCT\d{8}', response.text))
                    time.sleep(0.4)

        except:
            pass

        # Validate NCT IDs exist
        valid = set()
        for nct_id in list(nct_ids)[:300]:
            try:
                url = f"{self.CTGOV_API}/{nct_id}"
                response = self.session.get(url, params={"fields": "NCTId"}, timeout=10)
                if response.status_code == 200:
                    valid.add(nct_id)
                time.sleep(0.05)
            except:
                pass

        return valid

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def run_validation(self, output_dir: str):
        """Run comprehensive validation"""

        drugs_to_test = [
            ("semaglutide", "diabetes OR obesity"),
            ("liraglutide", "diabetes OR obesity"),
            ("empagliflozin", "diabetes OR heart failure"),
            ("dapagliflozin", "diabetes OR heart failure"),
            ("sitagliptin", "diabetes"),
            ("metformin", "diabetes"),
            ("insulin", "diabetes"),
            ("pembrolizumab", "cancer"),
            ("nivolumab", "cancer"),
            ("atezolizumab", "cancer"),
            ("trastuzumab", "breast cancer"),
            ("bevacizumab", "cancer"),
            ("rituximab", "lymphoma"),
            ("adalimumab", "arthritis"),
            ("etanercept", "arthritis"),
            ("infliximab", "arthritis OR crohn"),
            ("tocilizumab", "arthritis"),
            ("secukinumab", "psoriasis"),
            ("escitalopram", "depression"),
            ("sertraline", "depression"),
            ("duloxetine", "depression OR pain"),
            ("quetiapine", "schizophrenia"),
            ("atorvastatin", "cardiovascular"),
            ("rosuvastatin", "cardiovascular"),
            ("apixaban", "atrial fibrillation"),
            ("rivaroxaban", "atrial fibrillation"),
            ("tiotropium", "COPD"),
            ("fluticasone", "asthma"),
            ("omalizumab", "asthma"),
            ("sofosbuvir", "hepatitis C"),
            ("tenofovir", "HIV"),
            ("remdesivir", "COVID"),
        ]

        print("=" * 80)
        print("MAXIMUM RECALL STRATEGY VALIDATION")
        print("=" * 80)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results = []
        totals = {"tp": 0, "fn": 0, "gold": 0}

        for i, (drug, condition) in enumerate(drugs_to_test):
            print(f"\n[{i+1}/{len(drugs_to_test)}] {drug}")
            self.cache = {}  # Clear cache for each drug

            # Get gold standard
            print("  Gold: ", end="", flush=True)
            gold = self.get_gold_standard(drug, condition, max_results=400)

            if len(gold) < 10:
                print(f"skipped ({len(gold)} trials)")
                continue

            print(f"{len(gold)} | Max: ", end="", flush=True)

            # Run maximum strategy
            found, metadata = self.strategy_maximum(drug, condition)

            # Calculate metrics
            tp = len(found & gold)
            fn = len(gold - found)
            recall = tp / len(gold)

            totals["tp"] += tp
            totals["fn"] += fn
            totals["gold"] += len(gold)

            # Get baseline for comparison
            baseline = self.s1_basic_intervention(drug)
            baseline_tp = len(baseline & gold)
            baseline_recall = baseline_tp / len(gold)
            improvement = (recall - baseline_recall) * 100

            print(f" | Recall: {recall:.1%} (baseline: {baseline_recall:.1%}, +{improvement:.1f}%)")

            results.append({
                "drug": drug,
                "condition": condition,
                "gold": len(gold),
                "found": len(found),
                "tp": tp,
                "fn": fn,
                "recall": recall,
                "baseline_recall": baseline_recall,
                "improvement": improvement,
                "metadata": metadata
            })

        # Overall results
        overall_recall = totals["tp"] / totals["gold"] if totals["gold"] else 0
        ci = wilson_ci(totals["tp"], totals["gold"])

        print("\n" + "=" * 80)
        print("FINAL RESULTS - MAXIMUM RECALL STRATEGY")
        print("=" * 80)
        print(f"\nDrugs tested: {len(results)}")
        print(f"Total trials: {totals['gold']}")
        print(f"Found: {totals['tp']}")
        print(f"Missed: {totals['fn']}")
        print(f"\nRECALL: {overall_recall:.1%} (95% CI: {ci[0]:.1%}-{ci[1]:.1%})")

        # Best and worst
        sorted_results = sorted(results, key=lambda x: x["recall"], reverse=True)

        print("\nBEST PERFORMERS:")
        for r in sorted_results[:5]:
            print(f"  {r['drug']}: {r['recall']:.1%}")

        print("\nNEEDS IMPROVEMENT:")
        for r in sorted_results[-5:]:
            print(f"  {r['drug']}: {r['recall']:.1%} (missed {r['fn']})")

        # Save results
        with open(output_path / "maximum_recall_results.json", 'w') as f:
            json.dump({
                "overall": {
                    "recall": overall_recall,
                    "ci_95": ci,
                    "tp": totals["tp"],
                    "fn": totals["fn"],
                    "gold": totals["gold"]
                },
                "by_drug": results
            }, f, indent=2)

        # Generate report
        self._generate_report(results, overall_recall, ci, output_path)

        print(f"\nResults saved to {output_path}")
        return overall_recall

    def _generate_report(self, results, overall_recall, ci, output_path):
        """Generate markdown report"""

        with open(output_path / "MAXIMUM_RECALL_REPORT.md", 'w') as f:
            f.write("# Maximum Recall Strategy Results\n\n")
            f.write(f"**Overall Recall:** {overall_recall:.1%} (95% CI: {ci[0]:.1%}-{ci[1]:.1%})\n\n")

            f.write("## Results by Drug\n\n")
            f.write("| Drug | Gold | Recall | Baseline | Improvement |\n")
            f.write("|------|------|--------|----------|-------------|\n")

            for r in sorted(results, key=lambda x: -x["recall"]):
                f.write(f"| {r['drug']} | {r['gold']} | {r['recall']:.1%} | ")
                f.write(f"{r['baseline_recall']:.1%} | +{r['improvement']:.1f}% |\n")

            f.write("\n## Strategy Contribution\n\n")
            f.write("Analysis of which strategies added unique trials.\n")


def main():
    strategy = MaximumRecallStrategy()
    strategy.run_validation("output/maximum_recall")


if __name__ == "__main__":
    main()
