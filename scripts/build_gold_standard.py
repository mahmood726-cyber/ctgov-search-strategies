#!/usr/bin/env python3
"""
Build Independent Gold Standard for CT.gov Search Validation
Extracts NCT IDs from multiple independent sources to create robust validation dataset.

Sources:
1. PubMed - Published RCTs with NCT IDs in abstract/metadata
2. Cochrane CENTRAL - Trial registry links
3. CrossRef - DOIs linked to registry entries
4. OpenTrials - Aggregated trial data

This creates an independent gold standard that is NOT derived from CT.gov searching.

Author: Mahmood Ahmad
Version: 4.1
"""

import requests
import json
import re
import time
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field, asdict
from defusedxml import ElementTree as ET
import math


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class GoldStandardTrial:
    """A trial in the gold standard dataset"""
    nct_id: str
    source: str  # "pubmed", "cochrane", "crossref", "manual"
    condition: str
    pmid: Optional[str] = None
    doi: Optional[str] = None
    title: str = ""
    publication_year: Optional[int] = None
    is_rct: bool = True
    mesh_terms: List[str] = field(default_factory=list)


@dataclass
class ValidationMetrics:
    """Statistical metrics for search validation"""
    true_positives: int
    false_negatives: int
    total_retrieved: int

    @property
    def recall(self) -> float:
        total = self.true_positives + self.false_negatives
        return self.true_positives / total if total > 0 else 0.0

    @property
    def precision(self) -> float:
        return self.true_positives / self.total_retrieved if self.total_retrieved > 0 else 0.0

    @property
    def nns(self) -> float:
        """Number Needed to Screen"""
        return 1 / self.precision if self.precision > 0 else float('inf')

    def wilson_ci(self, confidence: float = 0.95) -> Tuple[float, float]:
        """Wilson score confidence interval for recall"""
        n = self.true_positives + self.false_negatives
        if n == 0:
            return (0.0, 0.0)

        p = self.recall
        z = 1.96 if confidence == 0.95 else 2.576  # 95% or 99%

        denominator = 1 + z**2 / n
        center = (p + z**2 / (2*n)) / denominator
        margin = z * math.sqrt((p * (1-p) + z**2 / (4*n)) / n) / denominator

        return (max(0, center - margin), min(1, center + margin))


# =============================================================================
# PUBMED SEARCH - INDEPENDENT SOURCE
# =============================================================================

class PubMedExtractor:
    """Extract NCT IDs from published RCTs via PubMed"""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, email: str = "research@example.com"):
        self.email = email
        self.session = requests.Session()

    def search_rcts_with_nct(self, condition: str, max_results: int = 500) -> List[str]:
        """
        Search PubMed for RCTs that mention NCT IDs.
        This is an INDEPENDENT source - not derived from CT.gov searching.
        """
        # Search for RCTs with NCT ID in any field
        query = f'("{condition}"[MeSH Terms] OR "{condition}"[Title/Abstract]) AND "NCT"[Title/Abstract] AND "randomized controlled trial"[Publication Type]'

        search_url = f"{self.BASE_URL}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "email": self.email
        }

        try:
            response = self.session.get(search_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            pmids = data.get("esearchresult", {}).get("idlist", [])
            return pmids

        except Exception as e:
            print(f"PubMed search error: {e}")
            return []

    def fetch_article_details(self, pmids: List[str]) -> List[GoldStandardTrial]:
        """Fetch article details and extract NCT IDs from abstracts"""
        if not pmids:
            return []

        trials = []

        # Fetch in batches of 100
        for i in range(0, len(pmids), 100):
            batch = pmids[i:i+100]

            fetch_url = f"{self.BASE_URL}/efetch.fcgi"
            params = {
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
                "email": self.email
            }

            try:
                response = self.session.get(fetch_url, params=params, timeout=60)
                response.raise_for_status()

                # Parse XML
                root = ET.fromstring(response.content)

                for article in root.findall(".//PubmedArticle"):
                    trial = self._parse_article(article)
                    if trial:
                        trials.append(trial)

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                print(f"Fetch error: {e}")

        return trials

    def _parse_article(self, article) -> Optional[GoldStandardTrial]:
        """Parse a PubMed article XML to extract NCT ID"""
        try:
            # Get PMID
            pmid_elem = article.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else None

            # Get title
            title_elem = article.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else ""

            # Get abstract
            abstract_parts = article.findall(".//AbstractText")
            abstract = " ".join(part.text or "" for part in abstract_parts)

            # Get publication year
            year_elem = article.find(".//PubDate/Year")
            year = int(year_elem.text) if year_elem is not None else None

            # Get MeSH terms
            mesh_terms = [
                mesh.text for mesh in article.findall(".//MeshHeading/DescriptorName")
                if mesh.text
            ]

            # Get DOI
            doi = None
            for art_id in article.findall(".//ArticleId"):
                if art_id.get("IdType") == "doi":
                    doi = art_id.text
                    break

            # Extract NCT ID from abstract or databank list
            nct_id = None

            # Check DataBankList first (most reliable)
            for accession in article.findall(".//AccessionNumber"):
                if accession.text and accession.text.startswith("NCT"):
                    nct_id = accession.text
                    break

            # If not found, search in abstract
            if not nct_id:
                nct_match = re.search(r'NCT\d{8}', abstract)
                if nct_match:
                    nct_id = nct_match.group()

            # Also check title
            if not nct_id:
                nct_match = re.search(r'NCT\d{8}', title)
                if nct_match:
                    nct_id = nct_match.group()

            if not nct_id:
                return None

            # Determine condition from MeSH terms
            condition = ""
            condition_mesh = [
                "Diabetes Mellitus", "Stroke", "Heart Failure", "Hypertension",
                "Neoplasms", "Asthma", "Depression", "Alzheimer Disease",
                "Arthritis", "COVID-19", "HIV", "Parkinson Disease"
            ]
            for mesh in mesh_terms:
                if any(c.lower() in mesh.lower() for c in condition_mesh):
                    condition = mesh
                    break

            return GoldStandardTrial(
                nct_id=nct_id,
                source="pubmed",
                condition=condition,
                pmid=pmid,
                doi=doi,
                title=title[:200] if title else "",
                publication_year=year,
                is_rct=True,
                mesh_terms=mesh_terms[:10]
            )

        except Exception as e:
            return None


# =============================================================================
# CROSSREF SEARCH - DOI-LINKED TRIALS
# =============================================================================

class CrossRefExtractor:
    """Extract NCT IDs from CrossRef metadata"""

    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, email: str = "research@example.com"):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"GoldStandardBuilder/1.0 (mailto:{email})"
        })

    def search_trials(self, condition: str, max_results: int = 200) -> List[GoldStandardTrial]:
        """Search CrossRef for papers with clinical trial references"""
        trials = []

        params = {
            "query": f"{condition} randomized controlled trial NCT",
            "filter": "type:journal-article",
            "rows": min(max_results, 100),
            "select": "DOI,title,abstract,clinical-trial-number,published-print,subject"
        }

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            for item in data.get("message", {}).get("items", []):
                trial = self._parse_item(item, condition)
                if trial:
                    trials.append(trial)

        except Exception as e:
            print(f"CrossRef error: {e}")

        return trials

    def _parse_item(self, item: dict, condition: str) -> Optional[GoldStandardTrial]:
        """Parse CrossRef item to extract NCT ID"""
        # Check clinical-trial-number field first
        clinical_trials = item.get("clinical-trial-number", [])
        nct_id = None

        for ct in clinical_trials:
            if isinstance(ct, dict):
                num = ct.get("clinical-trial-number", "")
            else:
                num = str(ct)

            if num.startswith("NCT"):
                nct_id = num
                break

        # If not found, check abstract
        if not nct_id:
            abstract = item.get("abstract", "")
            nct_match = re.search(r'NCT\d{8}', abstract)
            if nct_match:
                nct_id = nct_match.group()

        if not nct_id:
            return None

        # Get year
        pub_date = item.get("published-print", {}).get("date-parts", [[None]])[0]
        year = pub_date[0] if pub_date else None

        return GoldStandardTrial(
            nct_id=nct_id,
            source="crossref",
            condition=condition,
            doi=item.get("DOI"),
            title=item.get("title", [""])[0][:200] if item.get("title") else "",
            publication_year=year,
            is_rct=True
        )


# =============================================================================
# GOLD STANDARD BUILDER
# =============================================================================

class GoldStandardBuilder:
    """Build comprehensive gold standard dataset"""

    # Diverse conditions covering editorial review concerns
    CONDITIONS = [
        # Cardiovascular/Metabolic (existing)
        "diabetes mellitus",
        "stroke",
        "heart failure",
        "hypertension",
        "myocardial infarction",

        # Mental Health (underrepresented)
        "depression",
        "anxiety disorders",
        "schizophrenia",
        "bipolar disorder",
        "PTSD",

        # Pediatrics (underrepresented)
        "pediatric asthma",
        "childhood obesity",
        "ADHD",
        "pediatric epilepsy",

        # Rare Diseases (underrepresented)
        "cystic fibrosis",
        "multiple sclerosis",
        "Parkinson disease",
        "ALS",
        "sickle cell disease",

        # Oncology
        "breast cancer",
        "lung cancer",
        "colorectal cancer",
        "leukemia",

        # Infectious Disease
        "HIV",
        "tuberculosis",
        "hepatitis C",
        "COVID-19",

        # Other
        "rheumatoid arthritis",
        "chronic pain",
        "COPD",
        "Alzheimer disease"
    ]

    def __init__(self):
        self.pubmed = PubMedExtractor()
        self.crossref = CrossRefExtractor()
        self.trials: Dict[str, GoldStandardTrial] = {}  # NCT ID -> Trial

    def build(self, target_count: int = 500) -> List[GoldStandardTrial]:
        """Build gold standard aiming for target count"""
        print(f"Building gold standard dataset (target: {target_count} trials)")
        print("=" * 60)

        per_condition = max(20, target_count // len(self.CONDITIONS))

        for condition in self.CONDITIONS:
            print(f"\nSearching: {condition}")

            # PubMed search
            print(f"  PubMed...", end=" ", flush=True)
            pmids = self.pubmed.search_rcts_with_nct(condition, max_results=per_condition)
            pubmed_trials = self.pubmed.fetch_article_details(pmids)

            for trial in pubmed_trials:
                trial.condition = condition
                if trial.nct_id not in self.trials:
                    self.trials[trial.nct_id] = trial

            print(f"{len(pubmed_trials)} found")

            # CrossRef search
            print(f"  CrossRef...", end=" ", flush=True)
            crossref_trials = self.crossref.search_trials(condition, max_results=per_condition // 2)

            for trial in crossref_trials:
                if trial.nct_id not in self.trials:
                    self.trials[trial.nct_id] = trial

            print(f"{len(crossref_trials)} found")

            # Check if we have enough
            if len(self.trials) >= target_count:
                print(f"\nReached target count ({len(self.trials)} trials)")
                break

            time.sleep(1)  # Rate limiting between conditions

        return list(self.trials.values())

    def add_existing_cochrane(self, csv_path: str):
        """Add existing Cochrane NCT IDs to the dataset"""
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    nct_id = row.get('nct_id', '')
                    if nct_id and nct_id not in self.trials:
                        self.trials[nct_id] = GoldStandardTrial(
                            nct_id=nct_id,
                            source="cochrane",
                            condition=row.get('dataset_id', '').split('_')[0],
                            is_rct=True
                        )
        except Exception as e:
            print(f"Error loading Cochrane data: {e}")

    def export_csv(self, path: str):
        """Export gold standard to CSV"""
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'nct_id', 'source', 'condition', 'pmid', 'doi',
                'title', 'publication_year', 'is_rct'
            ])

            for trial in self.trials.values():
                writer.writerow([
                    trial.nct_id,
                    trial.source,
                    trial.condition,
                    trial.pmid or '',
                    trial.doi or '',
                    trial.title,
                    trial.publication_year or '',
                    trial.is_rct
                ])

    def export_json(self, path: str):
        """Export gold standard to JSON"""
        data = {
            "version": "4.1",
            "created": datetime.now(timezone.utc).isoformat(),
            "total_trials": len(self.trials),
            "sources": {
                "pubmed": len([t for t in self.trials.values() if t.source == "pubmed"]),
                "crossref": len([t for t in self.trials.values() if t.source == "crossref"]),
                "cochrane": len([t for t in self.trials.values() if t.source == "cochrane"])
            },
            "conditions": list(set(t.condition for t in self.trials.values())),
            "trials": [asdict(t) for t in self.trials.values()]
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def get_statistics(self) -> dict:
        """Get statistics about the gold standard"""
        trials = list(self.trials.values())

        conditions = {}
        sources = {}
        years = {}

        for trial in trials:
            conditions[trial.condition] = conditions.get(trial.condition, 0) + 1
            sources[trial.source] = sources.get(trial.source, 0) + 1
            if trial.publication_year:
                decade = (trial.publication_year // 10) * 10
                years[decade] = years.get(decade, 0) + 1

        return {
            "total": len(trials),
            "by_condition": conditions,
            "by_source": sources,
            "by_decade": years
        }


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build Gold Standard Validation Dataset")
    parser.add_argument("-n", "--count", type=int, default=500,
                       help="Target number of trials")
    parser.add_argument("-o", "--output", default="data/gold_standard.csv",
                       help="Output CSV path")
    parser.add_argument("--json", help="Also export JSON")
    parser.add_argument("--add-cochrane", help="Path to existing Cochrane NCT IDs")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    builder = GoldStandardBuilder()

    # Add existing Cochrane data if provided
    if args.add_cochrane:
        print(f"Loading existing Cochrane data from {args.add_cochrane}")
        builder.add_existing_cochrane(args.add_cochrane)
        print(f"  Loaded {len(builder.trials)} Cochrane trials")

    # Build from PubMed and CrossRef
    remaining = args.count - len(builder.trials)
    if remaining > 0:
        builder.build(target_count=args.count)

    # Statistics
    stats = builder.get_statistics()
    print("\n" + "=" * 60)
    print("GOLD STANDARD STATISTICS")
    print("=" * 60)
    print(f"Total trials: {stats['total']}")
    print(f"\nBy source:")
    for source, count in sorted(stats['by_source'].items()):
        print(f"  {source}: {count}")
    print(f"\nBy condition (top 10):")
    for cond, count in sorted(stats['by_condition'].items(), key=lambda x: -x[1])[:10]:
        print(f"  {cond}: {count}")

    # Export
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    builder.export_csv(str(output_path))
    print(f"\nExported to {output_path}")

    if args.json:
        builder.export_json(args.json)
        print(f"Exported JSON to {args.json}")


if __name__ == "__main__":
    main()
