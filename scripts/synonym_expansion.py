#!/usr/bin/env python3
# sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files.
"""
MeSH-Based Synonym Expansion System for Clinical Trial Searching
Uses NLM MeSH API and curated synonyms to expand search terms
"""

import requests
import json
import time
from typing import List, Dict, Set, Optional
from urllib.parse import quote
from pathlib import Path
from datetime import datetime

# NLM MeSH API
MESH_API = "https://id.nlm.nih.gov/mesh/lookup/descriptor"
MESH_SUGGEST_API = "https://id.nlm.nih.gov/mesh/suggest"

# Rate limiting
RATE_LIMIT = 0.3


class MeSHLookup:
    """MeSH term lookup and synonym expansion"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'CTgov-Strategy-Tool/1.0 (Research)'
        })
        self.cache = {}

    def lookup_mesh_term(self, term: str) -> Optional[Dict]:
        """Look up a MeSH term and get its descriptor"""
        if term.lower() in self.cache:
            return self.cache[term.lower()]

        try:
            # Try the suggest API first
            url = f"{MESH_SUGGEST_API}?q={quote(term)}&limit=5"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                suggestions = response.json()
                if suggestions:
                    # Get the first match
                    match = suggestions[0]
                    result = {
                        "term": term,
                        "mesh_id": match.get("resource", "").split("/")[-1],
                        "label": match.get("label", term),
                        "found": True
                    }
                    self.cache[term.lower()] = result
                    return result

            return {"term": term, "found": False}
        except Exception as e:
            return {"term": term, "found": False, "error": str(e)}

    def get_mesh_synonyms(self, mesh_id: str) -> List[str]:
        """Get synonyms for a MeSH descriptor"""
        try:
            url = f"https://id.nlm.nih.gov/mesh/lookup/descriptor/{mesh_id}/terms"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()
                synonyms = []
                for term in data:
                    label = term.get("label", "")
                    if label:
                        synonyms.append(label)
                return list(set(synonyms))
            return []
        except Exception as e:
            print(f"  Error getting MeSH synonyms: {e}")
            return []


class SynonymExpander:
    """Comprehensive synonym expansion for clinical conditions"""

    def __init__(self):
        self.mesh = MeSHLookup()

        # Curated synonyms for common conditions
        self.curated_synonyms = {
            # Metabolic conditions
            "diabetes": [
                "diabetes mellitus", "diabetic", "type 2 diabetes",
                "type 1 diabetes", "T2DM", "T1DM", "NIDDM", "IDDM",
                "hyperglycemia", "glucose intolerance", "diabetic patient"
            ],
            "obesity": [
                "obese", "overweight", "morbid obesity", "severe obesity",
                "body mass index", "BMI", "weight loss", "bariatric"
            ],
            "hypertension": [
                "high blood pressure", "elevated blood pressure", "HTN",
                "essential hypertension", "primary hypertension",
                "blood pressure", "antihypertensive"
            ],

            # Cardiovascular
            "heart failure": [
                "cardiac failure", "CHF", "congestive heart failure",
                "HFrEF", "HFpEF", "systolic heart failure",
                "diastolic heart failure", "left ventricular dysfunction"
            ],
            "stroke": [
                "cerebrovascular accident", "CVA", "brain infarction",
                "ischemic stroke", "hemorrhagic stroke", "cerebral infarction",
                "transient ischemic attack", "TIA"
            ],
            "atrial fibrillation": [
                "AF", "AFib", "A-fib", "auricular fibrillation",
                "cardiac arrhythmia", "irregular heartbeat"
            ],

            # Cancer
            "breast cancer": [
                "breast neoplasm", "breast carcinoma", "mammary cancer",
                "breast tumor", "breast malignancy"
            ],
            "lung cancer": [
                "lung neoplasm", "lung carcinoma", "pulmonary cancer",
                "NSCLC", "SCLC", "non-small cell lung cancer"
            ],
            "colorectal cancer": [
                "colon cancer", "rectal cancer", "bowel cancer",
                "colorectal carcinoma", "CRC"
            ],

            # Respiratory
            "asthma": [
                "bronchial asthma", "asthmatic", "reactive airway disease",
                "wheezing", "bronchospasm"
            ],
            "copd": [
                "chronic obstructive pulmonary disease", "emphysema",
                "chronic bronchitis", "COLD", "chronic airflow limitation"
            ],
            "cystic fibrosis": [
                "CF", "mucoviscidosis", "fibrocystic disease of pancreas"
            ],

            # Neurological/Psychiatric
            "depression": [
                "major depressive disorder", "MDD", "depressive disorder",
                "clinical depression", "major depression", "unipolar depression"
            ],
            "anxiety": [
                "anxiety disorder", "generalized anxiety disorder", "GAD",
                "anxious", "panic disorder", "social anxiety"
            ],
            "schizophrenia": [
                "schizophrenic disorder", "psychosis", "psychotic disorder"
            ],
            "alzheimer": [
                "alzheimer's disease", "alzheimers", "AD",
                "dementia", "cognitive impairment", "memory loss"
            ],
            "autism": [
                "autism spectrum disorder", "ASD", "autistic disorder",
                "autistic", "pervasive developmental disorder", "PDD",
                "Asperger", "Asperger's syndrome"
            ],

            # Autoimmune/Inflammatory
            "rheumatoid arthritis": [
                "RA", "rheumatoid", "inflammatory arthritis",
                "polyarthritis", "joint inflammation"
            ],
            "psoriasis": [
                "psoriatic", "plaque psoriasis", "scalp psoriasis",
                "nail psoriasis", "guttate psoriasis"
            ],
            "multiple sclerosis": [
                "MS", "relapsing-remitting MS", "RRMS",
                "progressive MS", "demyelinating disease"
            ],

            # Infectious
            "covid-19": [
                "COVID", "coronavirus", "SARS-CoV-2", "COVID19",
                "coronavirus disease 2019", "corona virus"
            ],
            "hiv": [
                "HIV infection", "AIDS", "human immunodeficiency virus",
                "HIV/AIDS", "HIV positive"
            ],

            # Other common
            "pain": [
                "chronic pain", "acute pain", "neuropathic pain",
                "pain management", "analgesia"
            ],
            "hypertriglyceridemia": [
                "high triglycerides", "elevated triglycerides",
                "dyslipidemia", "hyperlipidemia"
            ]
        }

    def expand_term(self, term: str, use_mesh: bool = True) -> Dict:
        """Expand a term to include synonyms"""
        term_lower = term.lower().strip()

        # Start with curated synonyms
        synonyms = set()
        synonyms.add(term)

        # Check curated database
        if term_lower in self.curated_synonyms:
            synonyms.update(self.curated_synonyms[term_lower])

        # Check if term is a synonym in another entry
        for key, syns in self.curated_synonyms.items():
            if term_lower in [s.lower() for s in syns]:
                synonyms.add(key)
                synonyms.update(syns)

        # Try MeSH lookup if enabled
        mesh_result = None
        if use_mesh:
            print(f"  Looking up MeSH for: {term}")
            mesh_result = self.mesh.lookup_mesh_term(term)

            if mesh_result and mesh_result.get("found"):
                mesh_id = mesh_result.get("mesh_id")
                if mesh_id:
                    mesh_synonyms = self.mesh.get_mesh_synonyms(mesh_id)
                    synonyms.update(mesh_synonyms)
                    time.sleep(RATE_LIMIT)

        return {
            "original_term": term,
            "synonyms": sorted(list(synonyms)),
            "count": len(synonyms),
            "mesh_lookup": mesh_result,
            "sources": {
                "curated": term_lower in self.curated_synonyms,
                "mesh": mesh_result.get("found", False) if mesh_result else False
            }
        }

    def build_or_query(self, term: str, use_mesh: bool = True) -> str:
        """Build an OR query string with all synonyms"""
        expanded = self.expand_term(term, use_mesh)
        synonyms = expanded["synonyms"]

        # Quote multi-word terms
        quoted = []
        for syn in synonyms:
            if " " in syn or "-" in syn:
                quoted.append(f'"{syn}"')
            else:
                quoted.append(syn)

        return " OR ".join(quoted)

    def generate_search_strings(self, term: str, use_mesh: bool = True) -> Dict:
        """Generate various search string formats"""
        expanded = self.expand_term(term, use_mesh)

        # Different formats for different uses
        formats = {
            "or_query": " OR ".join([f'"{s}"' if " " in s else s for s in expanded["synonyms"]]),
            "ctgov_condition": " OR ".join([f'"{s}"' for s in expanded["synonyms"][:10]]),  # Limit for URL
            "pubmed_mesh": f'"{term}"[MeSH Terms]' if expanded["sources"]["mesh"] else f'"{term}"[Title/Abstract]',
            "embase": "/".join([f'"{s}"' for s in expanded["synonyms"][:5]]),
            "cochrane": " OR ".join([f'"{s}"' for s in expanded["synonyms"]])
        }

        return {
            "term": term,
            "expansion": expanded,
            "formats": formats
        }


def main():
    """Demonstrate synonym expansion"""
    output_dir = Path("C:/Users/user/Downloads/ctgov-search-strategies/output")
    output_dir.mkdir(exist_ok=True)

    expander = SynonymExpander()

    # Test conditions
    test_terms = [
        "diabetes",
        "breast cancer",
        "cystic fibrosis",
        "autism",
        "depression",
        "covid-19",
        "hypertension",
        "stroke"
    ]

    print("=" * 70)
    print("MeSH-Based Synonym Expansion System")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    all_results = {}

    for term in test_terms:
        print(f"\nExpanding: {term}")
        print("-" * 50)

        result = expander.generate_search_strings(term, use_mesh=True)
        all_results[term] = result

        expansion = result["expansion"]
        print(f"  Found {expansion['count']} synonyms")
        print(f"  Sources: Curated={expansion['sources']['curated']}, MeSH={expansion['sources']['mesh']}")
        print(f"  Sample synonyms: {', '.join(expansion['synonyms'][:5])}")

        time.sleep(RATE_LIMIT)

    # Save results
    output_file = output_dir / "synonym_expansion_results.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved results: {output_file}")

    # Generate summary report
    report = []
    report.append("=" * 70)
    report.append("SYNONYM EXPANSION SUMMARY REPORT")
    report.append("=" * 70)
    report.append("")

    for term, result in all_results.items():
        expansion = result["expansion"]
        report.append(f"TERM: {term.upper()}")
        report.append("-" * 40)
        report.append(f"Total synonyms: {expansion['count']}")
        report.append(f"Synonyms: {', '.join(expansion['synonyms'])}")
        report.append("")
        report.append("CT.gov Condition Query:")
        report.append(f"  {result['formats']['ctgov_condition']}")
        report.append("")
        report.append("PubMed Format:")
        report.append(f"  {result['formats']['pubmed_mesh']}")
        report.append("")
        report.append("")

    report_text = "\n".join(report)
    report_file = output_dir / "synonym_expansion_report.txt"
    with open(report_file, 'w') as f:
        f.write(report_text)
    print(f"Saved report: {report_file}")

    print("\n" + "=" * 70)
    print("Synonym expansion complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
