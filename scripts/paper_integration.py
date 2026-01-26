#!/usr/bin/env python3
"""
Paper Data Integration Module
Downloads open access PDFs and extracts data for registry-paper reconciliation.

Features:
- PubMed search for papers linked to NCT IDs
- CrossRef metadata lookup
- Unpaywall API for open access PDF links
- PDF download and text extraction
- Retraction checking via CrossRef

Author: Mahmood Ahmad
Version: 4.1
"""

import requests
import json
import re
import os
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
import xml.etree.ElementTree as ET


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PaperMetadata:
    """Metadata for a published paper"""
    doi: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    title: str = ""
    authors: List[str] = field(default_factory=list)
    journal: str = ""
    publication_date: str = ""
    abstract: str = ""
    nct_ids: List[str] = field(default_factory=list)
    is_open_access: bool = False
    pdf_url: Optional[str] = None
    is_retracted: bool = False
    retraction_doi: Optional[str] = None
    retraction_date: Optional[str] = None


@dataclass
class ExtractedPaperData:
    """Data extracted from paper for reconciliation"""
    doi: str
    nct_id: str
    reported_sample_size: Optional[int] = None
    reported_primary_outcome: Optional[str] = None
    reported_secondary_outcomes: List[str] = field(default_factory=list)
    reported_follow_up: Optional[str] = None
    reported_results: Dict = field(default_factory=dict)
    extraction_method: str = "abstract"  # "abstract", "full_text", "manual"


# =============================================================================
# PUBMED INTEGRATION
# =============================================================================

class PubMedIntegration:
    """Search and fetch papers from PubMed"""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, email: str = "research@example.com"):
        self.email = email
        self.session = requests.Session()

    def find_papers_for_nct(self, nct_id: str) -> List[PaperMetadata]:
        """Find published papers that cite an NCT ID"""
        papers = []

        # Search for NCT ID in any field
        query = f'"{nct_id}"[All Fields]'

        search_url = f"{self.BASE_URL}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": 50,
            "retmode": "json",
            "email": self.email
        }

        try:
            response = self.session.get(search_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            pmids = data.get("esearchresult", {}).get("idlist", [])
            if pmids:
                papers = self._fetch_papers(pmids)

        except Exception as e:
            print(f"PubMed search error: {e}")

        return papers

    def _fetch_papers(self, pmids: List[str]) -> List[PaperMetadata]:
        """Fetch paper details from PubMed"""
        papers = []

        fetch_url = f"{self.BASE_URL}/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "email": self.email
        }

        try:
            response = self.session.get(fetch_url, params=params, timeout=60)
            response.raise_for_status()

            root = ET.fromstring(response.content)

            for article in root.findall(".//PubmedArticle"):
                paper = self._parse_article(article)
                if paper:
                    papers.append(paper)

        except Exception as e:
            print(f"PubMed fetch error: {e}")

        return papers

    def _parse_article(self, article) -> Optional[PaperMetadata]:
        """Parse PubMed article XML"""
        try:
            # PMID
            pmid_elem = article.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else None

            # Title
            title_elem = article.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else ""

            # Abstract
            abstract_parts = article.findall(".//AbstractText")
            abstract = " ".join(part.text or "" for part in abstract_parts)

            # Authors
            authors = []
            for author in article.findall(".//Author"):
                lastname = author.find("LastName")
                forename = author.find("ForeName")
                if lastname is not None and forename is not None:
                    authors.append(f"{forename.text} {lastname.text}")

            # Journal
            journal_elem = article.find(".//Journal/Title")
            journal = journal_elem.text if journal_elem is not None else ""

            # Publication date
            pub_date = article.find(".//PubDate")
            if pub_date is not None:
                year = pub_date.find("Year")
                month = pub_date.find("Month")
                year_str = year.text if year is not None else ""
                month_str = month.text if month is not None else ""
                publication_date = f"{year_str}-{month_str}" if month_str else year_str
            else:
                publication_date = ""

            # DOI
            doi = None
            for art_id in article.findall(".//ArticleId"):
                if art_id.get("IdType") == "doi":
                    doi = art_id.text
                    break

            # PMC ID
            pmcid = None
            for art_id in article.findall(".//ArticleId"):
                if art_id.get("IdType") == "pmc":
                    pmcid = art_id.text
                    break

            # Extract NCT IDs from abstract and databank
            nct_ids = []
            for accession in article.findall(".//AccessionNumber"):
                if accession.text and accession.text.startswith("NCT"):
                    nct_ids.append(accession.text)

            # Also search abstract
            nct_matches = re.findall(r'NCT\d{8}', abstract)
            nct_ids.extend(nct_matches)
            nct_ids = list(set(nct_ids))

            # Check for retraction
            is_retracted = False
            for pub_type in article.findall(".//PublicationType"):
                if pub_type.text and "Retract" in pub_type.text:
                    is_retracted = True
                    break

            return PaperMetadata(
                doi=doi,
                pmid=pmid,
                pmcid=pmcid,
                title=title,
                authors=authors[:5],
                journal=journal,
                publication_date=publication_date,
                abstract=abstract,
                nct_ids=nct_ids,
                is_retracted=is_retracted
            )

        except Exception:
            return None


# =============================================================================
# CROSSREF INTEGRATION
# =============================================================================

class CrossRefIntegration:
    """CrossRef API for DOI lookup and retraction checking"""

    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, email: str = "research@example.com"):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"PaperIntegration/4.1 (mailto:{email})"
        })

    def get_by_doi(self, doi: str) -> Optional[PaperMetadata]:
        """Get paper metadata by DOI"""
        try:
            url = f"{self.BASE_URL}/{doi}"
            response = self.session.get(url, timeout=30)

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json().get("message", {})

            # Check for retraction
            is_retracted = False
            retraction_doi = None

            # Check update-to field for retractions
            for update in data.get("update-to", []):
                if update.get("type") == "retraction":
                    is_retracted = True
                    retraction_doi = update.get("DOI")
                    break

            # Also check relation field
            for relation in data.get("relation", {}).get("is-retracted-by", []):
                is_retracted = True
                retraction_doi = relation.get("id")
                break

            return PaperMetadata(
                doi=doi,
                title=data.get("title", [""])[0] if data.get("title") else "",
                authors=[
                    f"{a.get('given', '')} {a.get('family', '')}"
                    for a in data.get("author", [])[:5]
                ],
                journal=data.get("container-title", [""])[0] if data.get("container-title") else "",
                publication_date="-".join(map(str, data.get("published-print", {}).get("date-parts", [[]])[0])),
                is_retracted=is_retracted,
                retraction_doi=retraction_doi
            )

        except Exception as e:
            print(f"CrossRef error: {e}")
            return None

    def check_retraction(self, doi: str) -> Tuple[bool, Optional[str]]:
        """Check if a DOI has been retracted"""
        paper = self.get_by_doi(doi)
        if paper:
            return paper.is_retracted, paper.retraction_doi
        return False, None


# =============================================================================
# UNPAYWALL - OPEN ACCESS PDF LINKS
# =============================================================================

class UnpaywallIntegration:
    """Unpaywall API for finding open access PDFs"""

    BASE_URL = "https://api.unpaywall.org/v2"

    def __init__(self, email: str = "research@example.com"):
        self.email = email
        self.session = requests.Session()

    def get_oa_link(self, doi: str) -> Optional[str]:
        """Get open access PDF URL for a DOI"""
        try:
            url = f"{self.BASE_URL}/{doi}"
            params = {"email": self.email}

            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            # Check if open access
            if not data.get("is_oa"):
                return None

            # Get best OA location
            best_oa = data.get("best_oa_location", {})
            pdf_url = best_oa.get("url_for_pdf")

            if not pdf_url:
                # Try URL for landing page
                pdf_url = best_oa.get("url")

            return pdf_url

        except Exception as e:
            print(f"Unpaywall error: {e}")
            return None


# =============================================================================
# PDF DOWNLOADER
# =============================================================================

class PDFDownloader:
    """Download and store PDFs"""

    def __init__(self, download_dir: str = "data/papers"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def download(self, url: str, filename: str) -> Optional[str]:
        """Download PDF and return local path"""
        try:
            # Sanitize filename
            safe_filename = re.sub(r'[^\w\-.]', '_', filename)
            if not safe_filename.endswith('.pdf'):
                safe_filename += '.pdf'

            local_path = self.download_dir / safe_filename

            # Skip if already downloaded
            if local_path.exists():
                return str(local_path)

            response = self.session.get(url, timeout=60, stream=True)
            response.raise_for_status()

            # Check content type
            content_type = response.headers.get('Content-Type', '')
            if 'pdf' not in content_type.lower() and 'octet-stream' not in content_type.lower():
                print(f"Warning: Content type is {content_type}, may not be PDF")

            # Download
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return str(local_path)

        except Exception as e:
            print(f"PDF download error: {e}")
            return None


# =============================================================================
# DATA EXTRACTION FROM ABSTRACTS
# =============================================================================

class AbstractExtractor:
    """Extract trial data from paper abstracts"""

    # Patterns for extracting data
    SAMPLE_SIZE_PATTERNS = [
        r'(\d+)\s*(?:patients?|participants?|subjects?)\s*(?:were|was)?\s*(?:randomized|enrolled|recruited)',
        r'(?:n\s*=\s*|N\s*=\s*)(\d+)',
        r'(?:total of|totaling)\s*(\d+)\s*(?:patients?|participants?)',
        r'(?:randomized|enrolled)\s*(\d+)\s*(?:patients?|participants?)',
    ]

    FOLLOW_UP_PATTERNS = [
        r'(?:follow[- ]?up|followed for)\s*(?:of\s*)?(\d+)\s*(weeks?|months?|years?)',
        r'(\d+)[- ]?(week|month|year)\s*(?:follow[- ]?up|trial|study)',
        r'at\s*(\d+)\s*(weeks?|months?|years?)',
    ]

    def extract_from_abstract(self, abstract: str, nct_id: str) -> ExtractedPaperData:
        """Extract trial data from abstract text"""
        data = ExtractedPaperData(
            doi="",
            nct_id=nct_id,
            extraction_method="abstract"
        )

        if not abstract:
            return data

        abstract_lower = abstract.lower()

        # Extract sample size
        for pattern in self.SAMPLE_SIZE_PATTERNS:
            match = re.search(pattern, abstract_lower)
            if match:
                try:
                    data.reported_sample_size = int(match.group(1))
                    break
                except ValueError:
                    pass

        # Extract follow-up duration
        for pattern in self.FOLLOW_UP_PATTERNS:
            match = re.search(pattern, abstract_lower)
            if match:
                data.reported_follow_up = f"{match.group(1)} {match.group(2)}"
                break

        # Extract primary outcome (look for "primary outcome" or "primary endpoint")
        primary_match = re.search(
            r'(?:primary\s+(?:outcome|endpoint|end[- ]?point)[:\s]+)([^.]+)',
            abstract_lower
        )
        if primary_match:
            data.reported_primary_outcome = primary_match.group(1).strip()[:100]

        return data


# =============================================================================
# UNIFIED PAPER INTEGRATION
# =============================================================================

class PaperIntegration:
    """Unified paper integration for registry-paper reconciliation"""

    def __init__(self, email: str = "research@example.com", download_dir: str = "data/papers"):
        self.pubmed = PubMedIntegration(email)
        self.crossref = CrossRefIntegration(email)
        self.unpaywall = UnpaywallIntegration(email)
        self.downloader = PDFDownloader(download_dir)
        self.extractor = AbstractExtractor()

    def get_papers_for_trial(self, nct_id: str, download_pdf: bool = False) -> List[PaperMetadata]:
        """Get all papers linked to a trial"""
        papers = self.pubmed.find_papers_for_nct(nct_id)

        # Enrich with CrossRef data
        for paper in papers:
            if paper.doi:
                # Check retraction status
                is_retracted, retraction_doi = self.crossref.check_retraction(paper.doi)
                paper.is_retracted = is_retracted
                paper.retraction_doi = retraction_doi

                # Get OA link
                pdf_url = self.unpaywall.get_oa_link(paper.doi)
                if pdf_url:
                    paper.is_open_access = True
                    paper.pdf_url = pdf_url

                    # Download PDF if requested
                    if download_pdf:
                        filename = f"{nct_id}_{paper.doi.replace('/', '_')}"
                        local_path = self.downloader.download(pdf_url, filename)
                        if local_path:
                            print(f"  Downloaded: {local_path}")

            time.sleep(0.5)  # Rate limiting

        return papers

    def extract_data_for_reconciliation(self, nct_id: str) -> List[ExtractedPaperData]:
        """Extract data from papers for registry reconciliation"""
        extracted = []

        papers = self.get_papers_for_trial(nct_id)

        for paper in papers:
            data = self.extractor.extract_from_abstract(paper.abstract, nct_id)
            data.doi = paper.doi or ""
            extracted.append(data)

        return extracted

    def check_retraction_status(self, nct_id: str) -> List[Tuple[str, bool, Optional[str]]]:
        """Check retraction status for all papers linked to a trial"""
        results = []

        papers = self.pubmed.find_papers_for_nct(nct_id)

        for paper in papers:
            if paper.doi:
                is_retracted, retraction_doi = self.crossref.check_retraction(paper.doi)
                results.append((paper.doi, is_retracted, retraction_doi))

                if is_retracted:
                    print(f"  RETRACTED: {paper.doi}")
            else:
                # Check PubMed retraction flag
                results.append((paper.pmid or "unknown", paper.is_retracted, None))

        return results


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Paper Data Integration")
    parser.add_argument("nct_id", help="NCT ID to find papers for")
    parser.add_argument("--download", action="store_true",
                       help="Download open access PDFs")
    parser.add_argument("--check-retractions", action="store_true",
                       help="Check for retracted papers")
    parser.add_argument("--extract", action="store_true",
                       help="Extract data from abstracts")
    parser.add_argument("-o", "--output", help="Output JSON file")
    parser.add_argument("--email", default="research@example.com",
                       help="Email for API access")

    args = parser.parse_args()

    integration = PaperIntegration(email=args.email)

    print(f"Finding papers for {args.nct_id}...")

    if args.check_retractions:
        print("\nChecking retraction status...")
        retractions = integration.check_retraction_status(args.nct_id)
        retracted_count = sum(1 for _, is_ret, _ in retractions if is_ret)
        print(f"\nTotal papers: {len(retractions)}, Retracted: {retracted_count}")

    elif args.extract:
        print("\nExtracting data from abstracts...")
        extracted = integration.extract_data_for_reconciliation(args.nct_id)
        for data in extracted:
            print(f"\nDOI: {data.doi}")
            print(f"  Sample size: {data.reported_sample_size}")
            print(f"  Primary outcome: {data.reported_primary_outcome}")
            print(f"  Follow-up: {data.reported_follow_up}")

    else:
        papers = integration.get_papers_for_trial(args.nct_id, download_pdf=args.download)

        print(f"\nFound {len(papers)} papers:")
        for paper in papers:
            print(f"\n  Title: {paper.title[:60]}...")
            print(f"  DOI: {paper.doi}")
            print(f"  Journal: {paper.journal}")
            print(f"  Open Access: {paper.is_open_access}")
            print(f"  Retracted: {paper.is_retracted}")
            if paper.pdf_url:
                print(f"  PDF URL: {paper.pdf_url}")

        if args.output:
            output = {
                "nct_id": args.nct_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "papers": [asdict(p) for p in papers]
            }
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2)
            print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
