#!/usr/bin/env python3
"""
RIS Export Module for CT.gov Studies

Provides export functionality for ClinicalTrials.gov study data to various
reference manager formats:
- RIS format (EndNote, Zotero, Mendeley compatible)
- CSV with full metadata
- EndNote XML format

Usage:
    from ris_export import RISExporter
    from ctgov_search import CTGovSearcher

    searcher = CTGovSearcher()
    result = searcher.search("diabetes", return_studies=True)

    exporter = RISExporter()
    exporter.export_ris(result.studies, "diabetes_studies.ris")
    exporter.export_csv(result.studies, "diabetes_studies.csv")
    exporter.export_endnote_xml(result.studies, "diabetes_studies.xml")

CLI Usage:
    python ris_export.py --condition "diabetes" --output studies.ris
    python ris_export.py --condition "diabetes" --format csv --output studies.csv
    python ris_export.py --nct NCT03702452 NCT00400712 --format xml --output studies.xml
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from xml.dom import minidom


def extract_year(study: Dict[str, Any]) -> str:
    """
    Extract the study start year from a CT.gov study record.

    Args:
        study: CT.gov study dictionary from API response.

    Returns:
        Year as string, or empty string if not available.
    """
    status_module = study.get("protocolSection", {}).get("statusModule", {})

    # Try startDateStruct first
    start_date = status_module.get("startDateStruct", {})
    if start_date:
        date_str = start_date.get("date", "")
        if date_str:
            # Format: "YYYY-MM-DD" or "YYYY-MM" or "YYYY"
            match = re.match(r"(\d{4})", date_str)
            if match:
                return match.group(1)

    # Fallback to studyFirstSubmitDate
    first_submit = status_module.get("studyFirstSubmitDate", "")
    if first_submit:
        match = re.match(r"(\d{4})", first_submit)
        if match:
            return match.group(1)

    return ""


def get_conditions(study: Dict[str, Any]) -> List[str]:
    """
    Extract conditions/diseases from a CT.gov study record.

    Args:
        study: CT.gov study dictionary from API response.

    Returns:
        List of condition strings.
    """
    conditions_module = study.get("protocolSection", {}).get("conditionsModule", {})
    conditions = conditions_module.get("conditions", [])
    return conditions if conditions else []


def get_interventions(study: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Extract interventions from a CT.gov study record.

    Args:
        study: CT.gov study dictionary from API response.

    Returns:
        List of (type, name) tuples for each intervention.
    """
    arms_module = study.get("protocolSection", {}).get("armsInterventionsModule", {})
    interventions = arms_module.get("interventions", [])

    result = []
    for intervention in interventions:
        int_type = intervention.get("type", "")
        int_name = intervention.get("name", "")
        if int_name:
            result.append((int_type, int_name))

    return result


def get_start_date(study: Dict[str, Any]) -> str:
    """
    Extract the full start date from a CT.gov study record.

    Args:
        study: CT.gov study dictionary from API response.

    Returns:
        Start date string, or empty string if not available.
    """
    status_module = study.get("protocolSection", {}).get("statusModule", {})
    start_date = status_module.get("startDateStruct", {})
    return start_date.get("date", "")


def study_to_ris(study: Dict[str, Any]) -> str:
    """
    Convert a CT.gov study record to RIS format.

    The RIS format is a standardized tag format used by reference managers
    like EndNote, Zotero, and Mendeley.

    Args:
        study: CT.gov study dictionary from API response.

    Returns:
        RIS formatted string for the study.
    """
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    description = protocol.get("descriptionModule", {})
    status_module = protocol.get("statusModule", {})
    design_module = protocol.get("designModule", {})
    sponsor_module = protocol.get("sponsorCollaboratorsModule", {})

    nct_id = identification.get("nctId", "")
    brief_title = identification.get("briefTitle", "")
    official_title = identification.get("officialTitle", "")
    brief_summary = description.get("briefSummary", "")
    overall_status = status_module.get("overallStatus", "")
    phases = design_module.get("phases", [])
    lead_sponsor = sponsor_module.get("leadSponsor", {}).get("name", "")

    conditions = get_conditions(study)
    interventions = get_interventions(study)
    year = extract_year(study)

    # Build RIS record
    lines = [
        "TY  - CLRT",  # Clinical Trial type
        f"TI  - {brief_title}",
        f"AN  - {nct_id}",
    ]

    # Add author (lead sponsor)
    if lead_sponsor:
        lines.append(f"AU  - {lead_sponsor}")

    # Add year
    if year:
        lines.append(f"PY  - {year}")

    # Add abstract (brief summary)
    if brief_summary:
        # Clean up the summary - remove newlines for RIS format
        clean_summary = " ".join(brief_summary.split())
        lines.append(f"AB  - {clean_summary}")

    # Add URL
    if nct_id:
        lines.append(f"UR  - https://clinicaltrials.gov/study/{nct_id}")

    # Add keywords (conditions)
    if conditions:
        lines.append(f"KW  - {'; '.join(conditions)}")

    # Add notes for status and phase
    if overall_status:
        lines.append(f"N1  - Status: {overall_status}")

    if phases:
        lines.append(f"N1  - Phase: {'; '.join(phases)}")

    # Add official title as secondary title if different
    if official_title and official_title != brief_title:
        lines.append(f"T2  - {official_title}")

    # Add interventions as custom fields
    for int_type, int_name in interventions:
        lines.append(f"N1  - Intervention ({int_type}): {int_name}")

    # Add database name
    lines.append("DB  - ClinicalTrials.gov")

    # End record
    lines.append("ER  - ")
    lines.append("")  # Blank line between records

    return "\n".join(lines)


def studies_to_ris(studies: List[Dict[str, Any]]) -> str:
    """
    Convert multiple CT.gov study records to RIS format.

    Args:
        studies: List of CT.gov study dictionaries from API response.

    Returns:
        RIS formatted string containing all studies.
    """
    ris_records = [study_to_ris(study) for study in studies]
    return "\n".join(ris_records)


def study_to_csv_row(study: Dict[str, Any]) -> Dict[str, str]:
    """
    Convert a CT.gov study record to a CSV row dictionary.

    Args:
        study: CT.gov study dictionary from API response.

    Returns:
        Dictionary with column names as keys and values as strings.
    """
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    description = protocol.get("descriptionModule", {})
    status_module = protocol.get("statusModule", {})
    design_module = protocol.get("designModule", {})
    sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
    eligibility_module = protocol.get("eligibilityModule", {})

    conditions = get_conditions(study)
    interventions = get_interventions(study)

    # Format interventions as "Type: Name; Type: Name"
    intervention_str = "; ".join(
        [f"{int_type}: {int_name}" for int_type, int_name in interventions]
    )

    return {
        "NCT_ID": identification.get("nctId", ""),
        "Title": identification.get("briefTitle", ""),
        "Official_Title": identification.get("officialTitle", ""),
        "Status": status_module.get("overallStatus", ""),
        "Phase": "; ".join(design_module.get("phases", [])),
        "Conditions": "; ".join(conditions),
        "Interventions": intervention_str,
        "Start_Date": get_start_date(study),
        "Completion_Date": status_module.get("completionDateStruct", {}).get("date", ""),
        "Enrollment": str(design_module.get("enrollmentInfo", {}).get("count", "")),
        "Study_Type": design_module.get("studyType", ""),
        "Allocation": design_module.get("designInfo", {}).get("allocation", ""),
        "Lead_Sponsor": sponsor_module.get("leadSponsor", {}).get("name", ""),
        "Brief_Summary": description.get("briefSummary", ""),
        "URL": f"https://clinicaltrials.gov/study/{identification.get('nctId', '')}",
        "Eligibility_Criteria": eligibility_module.get("eligibilityCriteria", ""),
        "Gender": eligibility_module.get("sex", ""),
        "Min_Age": eligibility_module.get("minimumAge", ""),
        "Max_Age": eligibility_module.get("maximumAge", ""),
    }


def study_to_endnote_xml(study: Dict[str, Any]) -> ET.Element:
    """
    Convert a CT.gov study record to EndNote XML format.

    Args:
        study: CT.gov study dictionary from API response.

    Returns:
        ElementTree Element representing the EndNote XML record.
    """
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    description = protocol.get("descriptionModule", {})
    status_module = protocol.get("statusModule", {})
    design_module = protocol.get("designModule", {})
    sponsor_module = protocol.get("sponsorCollaboratorsModule", {})

    conditions = get_conditions(study)
    interventions = get_interventions(study)
    year = extract_year(study)
    nct_id = identification.get("nctId", "")

    # Create record element
    record = ET.Element("record")

    # Reference type (Clinical Trial)
    ref_type = ET.SubElement(record, "ref-type", name="Clinical Trial")
    ref_type.text = "47"  # EndNote code for clinical trial

    # Contributors (authors)
    lead_sponsor = sponsor_module.get("leadSponsor", {}).get("name", "")
    if lead_sponsor:
        contributors = ET.SubElement(record, "contributors")
        authors = ET.SubElement(contributors, "authors")
        author = ET.SubElement(authors, "author")
        author.text = lead_sponsor

    # Titles
    titles = ET.SubElement(record, "titles")
    title = ET.SubElement(titles, "title")
    title.text = identification.get("briefTitle", "")

    official_title = identification.get("officialTitle", "")
    if official_title:
        secondary_title = ET.SubElement(titles, "secondary-title")
        secondary_title.text = official_title

    # Year
    if year:
        dates = ET.SubElement(record, "dates")
        year_elem = ET.SubElement(dates, "year")
        year_elem.text = year

    # Abstract
    brief_summary = description.get("briefSummary", "")
    if brief_summary:
        abstract = ET.SubElement(record, "abstract")
        abstract.text = brief_summary

    # URLs
    if nct_id:
        urls = ET.SubElement(record, "urls")
        related_urls = ET.SubElement(urls, "related-urls")
        url = ET.SubElement(related_urls, "url")
        url.text = f"https://clinicaltrials.gov/study/{nct_id}"

    # Accession number
    if nct_id:
        accession = ET.SubElement(record, "accession-num")
        accession.text = nct_id

    # Keywords (conditions)
    if conditions:
        keywords = ET.SubElement(record, "keywords")
        for condition in conditions:
            keyword = ET.SubElement(keywords, "keyword")
            keyword.text = condition

    # Notes (status, phase, interventions)
    notes_list = []
    overall_status = status_module.get("overallStatus", "")
    if overall_status:
        notes_list.append(f"Status: {overall_status}")

    phases = design_module.get("phases", [])
    if phases:
        notes_list.append(f"Phase: {'; '.join(phases)}")

    for int_type, int_name in interventions:
        notes_list.append(f"Intervention ({int_type}): {int_name}")

    if notes_list:
        notes = ET.SubElement(record, "notes")
        notes.text = "\n".join(notes_list)

    # Database
    database = ET.SubElement(record, "database")
    database.text = "ClinicalTrials.gov"

    return record


class RISExporter:
    """
    Export CT.gov study data to various reference manager formats.

    Supports:
    - RIS format (EndNote, Zotero, Mendeley)
    - CSV with full metadata
    - EndNote XML format
    """

    def __init__(self) -> None:
        """Initialize the RISExporter."""
        pass

    def export_ris(
        self, studies: List[Dict[str, Any]], filepath: str
    ) -> int:
        """
        Export studies to RIS format file.

        Args:
            studies: List of CT.gov study dictionaries.
            filepath: Output file path.

        Returns:
            Number of studies exported.
        """
        ris_content = studies_to_ris(studies)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(ris_content)
        return len(studies)

    def export_csv(
        self, studies: List[Dict[str, Any]], filepath: str
    ) -> int:
        """
        Export studies to CSV format with full metadata.

        Args:
            studies: List of CT.gov study dictionaries.
            filepath: Output file path.

        Returns:
            Number of studies exported.
        """
        if not studies:
            return 0

        # Get column headers from first study
        fieldnames = [
            "NCT_ID",
            "Title",
            "Official_Title",
            "Status",
            "Phase",
            "Conditions",
            "Interventions",
            "Start_Date",
            "Completion_Date",
            "Enrollment",
            "Study_Type",
            "Allocation",
            "Lead_Sponsor",
            "Brief_Summary",
            "URL",
            "Eligibility_Criteria",
            "Gender",
            "Min_Age",
            "Max_Age",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for study in studies:
                row = study_to_csv_row(study)
                writer.writerow(row)

        return len(studies)

    def export_endnote_xml(
        self, studies: List[Dict[str, Any]], filepath: str
    ) -> int:
        """
        Export studies to EndNote XML format.

        Args:
            studies: List of CT.gov study dictionaries.
            filepath: Output file path.

        Returns:
            Number of studies exported.
        """
        # Create XML structure
        xml_root = ET.Element("xml")
        records = ET.SubElement(xml_root, "records")

        for study in studies:
            record = study_to_endnote_xml(study)
            records.append(record)

        # Pretty print the XML
        xml_str = ET.tostring(xml_root, encoding="unicode")
        pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ")

        # Remove the extra XML declaration from minidom
        lines = pretty_xml.split("\n")
        if lines[0].startswith("<?xml"):
            lines = lines[1:]
        pretty_xml = "\n".join(lines)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(pretty_xml)

        return len(studies)

    def export_ris_string(self, studies: List[Dict[str, Any]]) -> str:
        """
        Convert studies to RIS format string (without saving to file).

        Args:
            studies: List of CT.gov study dictionaries.

        Returns:
            RIS formatted string.
        """
        return studies_to_ris(studies)


def main() -> int:
    """
    CLI entry point for RIS export functionality.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Export CT.gov study data to reference manager formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Export diabetes studies to RIS:
    python ris_export.py --condition "diabetes" --output diabetes.ris

  Export to CSV format:
    python ris_export.py --condition "diabetes" --format csv --output diabetes.csv

  Export specific NCT IDs to EndNote XML:
    python ris_export.py --nct NCT03702452 NCT00400712 --format xml --output studies.xml

  Export with specific search strategy:
    python ris_export.py --condition "diabetes" --strategy S3 --output rcts.ris
        """,
    )

    parser.add_argument(
        "--condition", "-c",
        type=str,
        help="Medical condition to search for",
    )
    parser.add_argument(
        "--nct",
        type=str,
        nargs="+",
        help="Specific NCT IDs to export",
    )
    parser.add_argument(
        "--strategy", "-s",
        type=str,
        default="S1",
        help="Search strategy (S1-S10, default: S1)",
    )
    parser.add_argument(
        "--format", "-f",
        type=str,
        choices=["ris", "csv", "xml"],
        default="ris",
        help="Output format (default: ris)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        required=True,
        help="Output file path",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=1000,
        help="Maximum number of results to export (default: 1000)",
    )

    args = parser.parse_args()

    if not args.condition and not args.nct:
        parser.error("Either --condition or --nct must be provided")

    # Import here to avoid circular imports
    from ctgov_search import CTGovSearcher

    searcher = CTGovSearcher()
    exporter = RISExporter()

    try:
        # Get studies
        if args.nct:
            print(f"Fetching {len(args.nct)} studies by NCT ID...")
            result = searcher.search_by_nct_ids(args.nct)
        else:
            print(f"Searching for '{args.condition}' using strategy {args.strategy}...")
            result = searcher.search(
                args.condition,
                strategy=args.strategy,
                page_size=min(args.max_results, 1000),
                return_studies=True,
            )

        if result.error:
            print(f"Error: {result.error}", file=sys.stderr)
            return 1

        studies = result.studies
        if not studies:
            print("No studies found.", file=sys.stderr)
            return 1

        print(f"Found {len(studies)} studies")

        # Export based on format
        if args.format == "ris":
            count = exporter.export_ris(studies, args.output)
        elif args.format == "csv":
            count = exporter.export_csv(studies, args.output)
        elif args.format == "xml":
            count = exporter.export_endnote_xml(studies, args.output)
        else:
            print(f"Unknown format: {args.format}", file=sys.stderr)
            return 1

        print(f"Exported {count} studies to {args.output}")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
