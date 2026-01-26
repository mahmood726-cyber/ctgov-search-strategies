#!/usr/bin/env python3
"""
Enhanced PubMed Extraction for Gold Standard Building
Uses multiple search strategies to maximize NCT ID extraction.

Strategies:
1. DataBank linkage - Most reliable (NCT in structured field)
2. Abstract text search - Find NCT mentions in abstracts
3. Secondary ID fields - Some papers list NCT in other ID fields
4. Systematic review extraction - Get NCT IDs from included studies lists

Author: Mahmood Ahmad
Version: 4.2
"""

import requests
import json
import re
import time
import csv
from datetime import datetime, timezone
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import xml.etree.ElementTree as ET


@dataclass
class PubMedTrial:
    """A trial identified from PubMed"""
    nct_id: str
    pmid: str
    title: str
    journal: str
    year: int
    condition: str
    extraction_method: str  # "databank", "abstract", "secondary_id"
    doi: Optional[str] = None
    is_rct: bool = True
    mesh_terms: List[str] = field(default_factory=list)


class EnhancedPubMedExtractor:
    """
    Enhanced PubMed extraction using multiple strategies.
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    # Comprehensive condition list for broad coverage
    CONDITIONS = [
        # Cardiovascular
        "heart failure", "myocardial infarction", "atrial fibrillation",
        "hypertension", "coronary artery disease", "stroke",
        # Metabolic
        "diabetes mellitus", "type 2 diabetes", "obesity", "hyperlipidemia",
        # Respiratory
        "asthma", "COPD", "pulmonary fibrosis", "pneumonia",
        # Oncology
        "breast cancer", "lung cancer", "colorectal cancer", "prostate cancer",
        "leukemia", "lymphoma", "melanoma",
        # Mental Health
        "depression", "anxiety", "schizophrenia", "bipolar disorder",
        "PTSD", "OCD", "ADHD",
        # Neurology
        "Alzheimer disease", "Parkinson disease", "multiple sclerosis",
        "epilepsy", "migraine", "neuropathic pain",
        # Infectious Disease
        "HIV", "hepatitis C", "tuberculosis", "COVID-19", "influenza",
        # Autoimmune/Inflammatory
        "rheumatoid arthritis", "psoriasis", "Crohn disease",
        "ulcerative colitis", "lupus",
        # Pediatric
        "childhood asthma", "pediatric epilepsy", "juvenile arthritis",
        # Rare Diseases
        "cystic fibrosis", "sickle cell disease", "hemophilia",
        "muscular dystrophy", "ALS",
        # Other
        "chronic kidney disease", "osteoporosis", "glaucoma",
        "macular degeneration", "hearing loss"
    ]

    def __init__(self, email: str = "research@example.com"):
        self.email = email
        self.session = requests.Session()
        self.extracted_ncts: Dict[str, PubMedTrial] = {}

    def search_databank_linked(self, condition: str, max_results: int = 200) -> List[str]:
        """
        Strategy 1: Find papers with NCT IDs in DataBank field.
        This is the most reliable source - structured registration.
        """
        query = (
            f'("{condition}"[MeSH Terms] OR "{condition}"[Title/Abstract]) '
            f'AND "ClinicalTrials.gov"[si] '
            f'AND "randomized controlled trial"[pt]'
        )

        return self._search(query, max_results)

    def search_abstract_nct(self, condition: str, max_results: int = 200) -> List[str]:
        """
        Strategy 2: Find papers mentioning NCT in abstract.
        Catches papers without formal DataBank registration.
        """
        query = (
            f'("{condition}"[MeSH Terms] OR "{condition}"[Title/Abstract]) '
            f'AND "NCT"[Title/Abstract] '
            f'AND ("randomized controlled trial"[pt] OR "clinical trial"[pt])'
        )

        return self._search(query, max_results)

    def search_results_papers(self, condition: str, max_results: int = 100) -> List[str]:
        """
        Strategy 3: Find trial results papers specifically.
        These almost always have NCT IDs.
        """
        query = (
            f'("{condition}"[MeSH Terms]) '
            f'AND ("trial results"[Title] OR "randomized trial"[Title]) '
            f'AND "NCT"[Abstract]'
        )

        return self._search(query, max_results)

    def search_systematic_reviews(self, condition: str, max_results: int = 50) -> List[str]:
        """
        Strategy 4: Find systematic reviews which list included trials.
        These contain multiple NCT IDs in the full text/abstract.
        """
        query = (
            f'("{condition}"[MeSH Terms]) '
            f'AND ("systematic review"[pt] OR "meta-analysis"[pt]) '
            f'AND "NCT"[Abstract]'
        )

        return self._search(query, max_results)

    def _search(self, query: str, max_results: int) -> List[str]:
        """Execute PubMed search and return PMIDs"""
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "email": self.email
        }

        try:
            response = self.session.get(
                f"{self.BASE_URL}/esearch.fcgi",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("esearchresult", {}).get("idlist", [])
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def fetch_and_extract(self, pmids: List[str], condition: str) -> List[PubMedTrial]:
        """Fetch paper details and extract NCT IDs"""
        if not pmids:
            return []

        trials = []

        # Process in batches
        for i in range(0, len(pmids), 100):
            batch = pmids[i:i+100]

            try:
                response = self.session.get(
                    f"{self.BASE_URL}/efetch.fcgi",
                    params={
                        "db": "pubmed",
                        "id": ",".join(batch),
                        "retmode": "xml",
                        "email": self.email
                    },
                    timeout=60
                )
                response.raise_for_status()

                root = ET.fromstring(response.content)

                for article in root.findall(".//PubmedArticle"):
                    extracted = self._extract_from_article(article, condition)
                    trials.extend(extracted)

                time.sleep(0.4)  # Rate limiting

            except Exception as e:
                print(f"Fetch error: {e}")

        return trials

    def _extract_from_article(self, article, condition: str) -> List[PubMedTrial]:
        """Extract NCT IDs from a single article"""
        trials = []

        try:
            # Get basic info
            pmid_elem = article.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else ""

            title_elem = article.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else ""

            journal_elem = article.find(".//Journal/Title")
            journal = journal_elem.text if journal_elem is not None else ""

            year_elem = article.find(".//PubDate/Year")
            year = int(year_elem.text) if year_elem is not None else 0

            doi = None
            for art_id in article.findall(".//ArticleId"):
                if art_id.get("IdType") == "doi":
                    doi = art_id.text
                    break

            # Get MeSH terms
            mesh_terms = [
                mesh.text for mesh in article.findall(".//MeshHeading/DescriptorName")
                if mesh.text
            ][:10]

            # Strategy 1: DataBank accession numbers (most reliable)
            for accession in article.findall(".//AccessionNumber"):
                if accession.text and accession.text.startswith("NCT"):
                    nct_id = accession.text
                    if nct_id not in self.extracted_ncts:
                        trial = PubMedTrial(
                            nct_id=nct_id,
                            pmid=pmid,
                            title=title[:200] if title else "",
                            journal=journal,
                            year=year,
                            condition=condition,
                            extraction_method="databank",
                            doi=doi,
                            mesh_terms=mesh_terms
                        )
                        trials.append(trial)
                        self.extracted_ncts[nct_id] = trial

            # Strategy 2: Abstract text extraction
            abstract_parts = article.findall(".//AbstractText")
            abstract = " ".join(part.text or "" for part in abstract_parts)

            # Find all NCT IDs in abstract
            nct_matches = re.findall(r'NCT\d{8}', abstract)
            for nct_id in set(nct_matches):
                if nct_id not in self.extracted_ncts:
                    trial = PubMedTrial(
                        nct_id=nct_id,
                        pmid=pmid,
                        title=title[:200] if title else "",
                        journal=journal,
                        year=year,
                        condition=condition,
                        extraction_method="abstract",
                        doi=doi,
                        mesh_terms=mesh_terms
                    )
                    trials.append(trial)
                    self.extracted_ncts[nct_id] = trial

            # Strategy 3: Title extraction (rare but happens)
            if title:
                title_ncts = re.findall(r'NCT\d{8}', title)
                for nct_id in set(title_ncts):
                    if nct_id not in self.extracted_ncts:
                        trial = PubMedTrial(
                            nct_id=nct_id,
                            pmid=pmid,
                            title=title[:200],
                            journal=journal,
                            year=year,
                            condition=condition,
                            extraction_method="title",
                            doi=doi,
                            mesh_terms=mesh_terms
                        )
                        trials.append(trial)
                        self.extracted_ncts[nct_id] = trial

        except Exception as e:
            pass  # Skip problematic articles

        return trials

    def extract_all_conditions(self, max_per_condition: int = 100) -> Dict[str, List[PubMedTrial]]:
        """Extract NCT IDs for all conditions"""
        results = {}

        for condition in self.CONDITIONS:
            print(f"\nExtracting: {condition}")
            condition_trials = []

            # Run all search strategies
            print("  DataBank linkage...", end=" ", flush=True)
            pmids1 = self.search_databank_linked(condition, max_per_condition)
            trials1 = self.fetch_and_extract(pmids1, condition)
            print(f"{len(trials1)} NCTs")
            condition_trials.extend(trials1)

            print("  Abstract search...", end=" ", flush=True)
            pmids2 = self.search_abstract_nct(condition, max_per_condition)
            trials2 = self.fetch_and_extract(pmids2, condition)
            print(f"{len(trials2)} NCTs")
            condition_trials.extend(trials2)

            print("  Results papers...", end=" ", flush=True)
            pmids3 = self.search_results_papers(condition, max_per_condition // 2)
            trials3 = self.fetch_and_extract(pmids3, condition)
            print(f"{len(trials3)} NCTs")
            condition_trials.extend(trials3)

            results[condition] = condition_trials

            # Progress
            total = len(self.extracted_ncts)
            print(f"  Total unique NCTs so far: {total}")

            time.sleep(1)  # Be nice to NCBI

        return results

    def export_gold_standard(self, output_path: str):
        """Export all extracted NCT IDs as gold standard"""
        trials = list(self.extracted_ncts.values())

        # CSV export
        csv_path = output_path.replace('.json', '.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'nct_id', 'pmid', 'title', 'journal', 'year',
                'condition', 'extraction_method', 'doi', 'is_rct'
            ])
            for trial in trials:
                writer.writerow([
                    trial.nct_id, trial.pmid, trial.title, trial.journal,
                    trial.year, trial.condition, trial.extraction_method,
                    trial.doi or '', trial.is_rct
                ])

        # JSON export
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "version": "4.2",
                "created": datetime.now(timezone.utc).isoformat(),
                "source": "PubMed Enhanced Extraction",
                "total_trials": len(trials),
                "by_method": {
                    "databank": len([t for t in trials if t.extraction_method == "databank"]),
                    "abstract": len([t for t in trials if t.extraction_method == "abstract"]),
                    "title": len([t for t in trials if t.extraction_method == "title"])
                },
                "by_condition": {
                    cond: len([t for t in trials if t.condition == cond])
                    for cond in set(t.condition for t in trials)
                },
                "trials": [
                    {
                        "nct_id": t.nct_id,
                        "pmid": t.pmid,
                        "title": t.title,
                        "journal": t.journal,
                        "year": t.year,
                        "condition": t.condition,
                        "extraction_method": t.extraction_method,
                        "doi": t.doi,
                        "mesh_terms": t.mesh_terms
                    }
                    for t in trials
                ]
            }, f, indent=2)

        print(f"\nExported {len(trials)} trials to {output_path}")
        return trials


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced PubMed NCT Extraction")
    parser.add_argument("-o", "--output", default="data/enhanced_gold_standard.json",
                       help="Output file path")
    parser.add_argument("-n", "--max-per-condition", type=int, default=100,
                       help="Max results per condition")
    parser.add_argument("--email", default="research@example.com",
                       help="Email for NCBI API")
    parser.add_argument("--conditions", nargs="+",
                       help="Specific conditions to search (default: all)")

    args = parser.parse_args()

    extractor = EnhancedPubMedExtractor(email=args.email)

    if args.conditions:
        extractor.CONDITIONS = args.conditions

    print("=" * 60)
    print("Enhanced PubMed NCT Extraction")
    print("=" * 60)
    print(f"Conditions to search: {len(extractor.CONDITIONS)}")
    print(f"Max per condition: {args.max_per_condition}")

    extractor.extract_all_conditions(args.max_per_condition)

    # Export
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    extractor.export_gold_standard(str(output_path))

    # Summary
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"Total unique NCT IDs: {len(extractor.extracted_ncts)}")
    print(f"By extraction method:")
    methods = {}
    for trial in extractor.extracted_ncts.values():
        methods[trial.extraction_method] = methods.get(trial.extraction_method, 0) + 1
    for method, count in sorted(methods.items(), key=lambda x: -x[1]):
        print(f"  {method}: {count}")


if __name__ == "__main__":
    main()
