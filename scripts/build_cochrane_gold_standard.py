#!/usr/bin/env python3
"""
Build Gold Standard from Cochrane Systematic Reviews
Extracts included trials from published Cochrane reviews via PubMed.

Author: Mahmood Ahmad
Version: 1.0
"""

import json
import re
import time
from datetime import datetime, timezone
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import requests


@dataclass
class CochraneReview:
    """A Cochrane systematic review with PICO and included trials"""
    pmid: str
    cochrane_id: str
    title: str
    population: str
    intervention: str
    comparator: str
    outcome: str
    included_nct_ids: Set[str]
    publication_year: int
    doi: str = ""


class CochraneGoldStandardBuilder:
    """
    Builds a gold standard from Cochrane systematic reviews.

    Process:
    1. Search PubMed for Cochrane reviews
    2. Extract PICO from title/abstract
    3. Find included trials via references/full text
    4. Validate NCT IDs exist in CT.gov
    """

    PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"

    def __init__(self, email: str = "researcher@example.com"):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": f"CochraneBuilder/1.0 ({email})"})
        self.email = email

    def search_cochrane_reviews(
        self,
        condition: str,
        intervention: str = None,
        max_results: int = 50
    ) -> List[str]:
        """Search PubMed for Cochrane systematic reviews"""

        # Build query
        query_parts = [
            f'"{condition}"[Title/Abstract]',
            '"Cochrane Database Syst Rev"[Journal]',
            "systematic review[Publication Type]"
        ]
        if intervention:
            query_parts.append(f'"{intervention}"[Title/Abstract]')

        query = " AND ".join(query_parts)

        # Search PubMed
        url = f"{self.PUBMED_API}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "email": self.email
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            pmids = data.get("esearchresult", {}).get("idlist", [])
            time.sleep(0.4)
            return pmids
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def get_review_details(self, pmid: str) -> Optional[Dict]:
        """Get details for a Cochrane review from PubMed"""

        url = f"{self.PUBMED_API}/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml",
            "email": self.email
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            xml_text = response.text

            # Parse basic info from XML
            title_match = re.search(r'<ArticleTitle>(.+?)</ArticleTitle>', xml_text, re.DOTALL)
            abstract_match = re.search(r'<AbstractText[^>]*>(.+?)</AbstractText>', xml_text, re.DOTALL)
            year_match = re.search(r'<PubDate>.*?<Year>(\d{4})</Year>', xml_text, re.DOTALL)
            doi_match = re.search(r'<ArticleId IdType="doi">(.+?)</ArticleId>', xml_text)

            # Extract NCT IDs from abstract/references
            nct_ids = set(re.findall(r'NCT\d{8}', xml_text))

            # Also get references that might have NCT IDs
            ref_pmids = re.findall(r'<ArticleId IdType="pubmed">(\d+)</ArticleId>', xml_text)

            title = title_match.group(1) if title_match else ""
            abstract = abstract_match.group(1) if abstract_match else ""
            year = int(year_match.group(1)) if year_match else 0
            doi = doi_match.group(1) if doi_match else ""

            # Clean HTML tags
            title = re.sub(r'<[^>]+>', '', title)
            abstract = re.sub(r'<[^>]+>', '', abstract)

            time.sleep(0.4)

            return {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "year": year,
                "doi": doi,
                "nct_ids_found": nct_ids,
                "reference_pmids": ref_pmids[:20]  # Limit
            }

        except Exception as e:
            print(f"  Error fetching {pmid}: {e}")
            return None

    def extract_pico_from_title(self, title: str) -> Tuple[str, str, str]:
        """Extract population, intervention, comparator from Cochrane title"""

        # Cochrane titles often follow pattern:
        # "[Intervention] for [Condition/Population]"
        # "[Intervention] versus [Comparator] for [Condition]"

        title_lower = title.lower()
        population = ""
        intervention = ""
        comparator = ""

        # Pattern: "X for Y"
        match = re.search(r'^(.+?)\s+for\s+(.+?)(?:\s+in\s+|\s*$)', title_lower)
        if match:
            intervention = match.group(1).strip()
            population = match.group(2).strip()

        # Pattern: "X versus Y for Z"
        match = re.search(r'^(.+?)\s+(?:versus|vs\.?|compared to|or)\s+(.+?)\s+for\s+(.+)', title_lower)
        if match:
            intervention = match.group(1).strip()
            comparator = match.group(2).strip()
            population = match.group(3).strip()

        # Clean up
        intervention = re.sub(r'^\w+\s+of\s+', '', intervention)  # Remove "Effect of"

        return population, intervention, comparator

    def search_included_trials_in_pubmed(self, intervention: str, condition: str) -> Set[str]:
        """Search for RCTs that might be included in a Cochrane review"""

        query = f'"{intervention}"[Title/Abstract] AND "{condition}"[Title/Abstract] AND randomized controlled trial[pt]'

        url = f"{self.PUBMED_API}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": 200,
            "retmode": "json",
            "email": self.email
        }

        nct_ids = set()

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            pmids = data.get("esearchresult", {}).get("idlist", [])
            time.sleep(0.4)

            # Fetch details for each to find NCT IDs
            for pmid in pmids[:50]:  # Limit
                url = f"{self.PUBMED_API}/efetch.fcgi"
                params = {
                    "db": "pubmed",
                    "id": pmid,
                    "retmode": "xml",
                    "email": self.email
                }
                response = self.session.get(url, params=params, timeout=30)
                found = set(re.findall(r'NCT\d{8}', response.text))
                nct_ids.update(found)
                time.sleep(0.3)

        except Exception as e:
            print(f"  Search error: {e}")

        return nct_ids

    def validate_nct_ids(self, nct_ids: Set[str]) -> Set[str]:
        """Validate that NCT IDs exist in CT.gov"""
        valid = set()

        for nct_id in nct_ids:
            try:
                url = f"{self.CTGOV_API}/{nct_id}"
                response = self.session.get(url, params={"fields": "NCTId"}, timeout=10)
                if response.status_code == 200:
                    valid.add(nct_id)
                time.sleep(0.2)
            except:
                pass

        return valid

    def build_gold_standard(
        self,
        conditions: List[str],
        max_reviews_per_condition: int = 10,
        output_path: str = "data/cochrane_gold_standard.json"
    ) -> List[CochraneReview]:
        """Build complete gold standard from Cochrane reviews"""

        print("=" * 70)
        print("Building Cochrane Gold Standard")
        print("=" * 70)

        all_reviews = []

        for condition in conditions:
            print(f"\n{'='*50}")
            print(f"Condition: {condition}")
            print('='*50)

            # Search for Cochrane reviews
            print(f"  Searching PubMed for Cochrane reviews...")
            pmids = self.search_cochrane_reviews(condition, max_results=max_reviews_per_condition)
            print(f"  Found {len(pmids)} reviews")

            for i, pmid in enumerate(pmids):
                print(f"\n  [{i+1}/{len(pmids)}] Processing PMID {pmid}...")

                # Get review details
                details = self.get_review_details(pmid)
                if not details:
                    continue

                title = details["title"]
                print(f"    Title: {title[:60]}...")

                # Extract PICO from title
                population, intervention, comparator = self.extract_pico_from_title(title)

                if not intervention:
                    print(f"    Could not extract intervention, skipping")
                    continue

                print(f"    Intervention: {intervention}")
                print(f"    Population: {population}")

                # Collect NCT IDs
                nct_ids = details["nct_ids_found"]
                print(f"    NCT IDs in abstract: {len(nct_ids)}")

                # Search for more included trials
                if intervention and population:
                    more_ncts = self.search_included_trials_in_pubmed(intervention, condition)
                    nct_ids.update(more_ncts)
                    print(f"    NCT IDs from related RCTs: {len(more_ncts)}")

                # Validate NCT IDs
                if nct_ids:
                    valid_ncts = self.validate_nct_ids(nct_ids)
                    print(f"    Valid NCT IDs: {len(valid_ncts)}")
                else:
                    valid_ncts = set()

                if len(valid_ncts) < 2:
                    print(f"    Too few trials, skipping")
                    continue

                # Create review object
                review = CochraneReview(
                    pmid=pmid,
                    cochrane_id=f"CD{pmid[-6:]}",  # Approximate
                    title=title,
                    population=population or condition,
                    intervention=intervention,
                    comparator=comparator,
                    outcome="",
                    included_nct_ids=valid_ncts,
                    publication_year=details["year"],
                    doi=details["doi"]
                )

                all_reviews.append(review)
                print(f"    Added review with {len(valid_ncts)} trials")

        # Save to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        output_data = {
            "version": "1.0",
            "created": datetime.now(timezone.utc).isoformat(),
            "source": "Cochrane Database via PubMed",
            "total_reviews": len(all_reviews),
            "total_trials": sum(len(r.included_nct_ids) for r in all_reviews),
            "reviews": [
                {
                    "review_id": r.cochrane_id,
                    "pmid": r.pmid,
                    "title": r.title,
                    "pico": {
                        "population": r.population,
                        "intervention": r.intervention,
                        "comparator": r.comparator,
                        "outcome": r.outcome
                    },
                    "included_nct_ids": list(r.included_nct_ids),
                    "year": r.publication_year,
                    "doi": r.doi
                }
                for r in all_reviews
            ]
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        print(f"\n{'='*70}")
        print(f"Gold Standard Built")
        print(f"  Reviews: {len(all_reviews)}")
        print(f"  Trials: {sum(len(r.included_nct_ids) for r in all_reviews)}")
        print(f"  Saved to: {output_file}")
        print("=" * 70)

        return all_reviews


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build Cochrane Gold Standard")
    parser.add_argument("-o", "--output", default="data/cochrane_gold_standard.json",
                       help="Output file path")
    parser.add_argument("-n", "--max-reviews", type=int, default=10,
                       help="Max reviews per condition")
    parser.add_argument("-e", "--email", default="researcher@example.com",
                       help="Email for PubMed API")

    args = parser.parse_args()

    # Conditions to search
    conditions = [
        "type 2 diabetes",
        "heart failure",
        "breast cancer",
        "depression",
        "rheumatoid arthritis",
        "asthma",
        "stroke",
        "hypertension",
        "chronic obstructive pulmonary disease",
        "atrial fibrillation"
    ]

    builder = CochraneGoldStandardBuilder(email=args.email)
    builder.build_gold_standard(
        conditions=conditions,
        max_reviews_per_condition=args.max_reviews,
        output_path=args.output
    )


if __name__ == "__main__":
    main()
