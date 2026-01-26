#!/usr/bin/env python3
"""
PRISMA 2020 Flow Diagram Generator for Systematic Reviews

Generates PRISMA-compliant flow diagrams for systematic review search results.
Supports multiple output formats:
- SVG (scalable vector graphics)
- PNG (raster image via svglib/reportlab)
- HTML (interactive with D3.js)
- LaTeX/TikZ (for academic papers)
- Text/Markdown (for simple documentation)

Based on PRISMA 2020 Statement:
Page MJ, McKenzie JE, Bossuyt PM, et al. The PRISMA 2020 statement: an updated
guideline for reporting systematic reviews. BMJ 2021;372:n71. doi: 10.1136/bmj.n71

Example:
    >>> from prisma_generator import PRISMAGenerator, PRISMAData
    >>>
    >>> data = PRISMAData(
    ...     databases={"ClinicalTrials.gov": 1500, "WHO ICTRP": 300},
    ...     registers={"FDA Drugs@FDA": 50},
    ...     duplicates_removed=200,
    ...     records_screened=1650,
    ...     records_excluded=1200,
    ...     reports_sought=450,
    ...     reports_not_retrieved=10,
    ...     reports_assessed=440,
    ...     reports_excluded_reasons={"Not RCT": 300, "Wrong population": 80, "Wrong intervention": 30},
    ...     studies_included=30
    ... )
    >>>
    >>> generator = PRISMAGenerator()
    >>> svg = generator.generate_svg(data)
    >>> generator.save("prisma_flowchart", data, formats=["svg", "html"])
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Tuple


# PRISMA 2020 Box Labels (Official terminology)
PRISMA_LABELS: Final[Dict[str, str]] = {
    "identification_databases": "Records identified from databases",
    "identification_registers": "Records identified from registers",
    "identification_other": "Records identified from other sources",
    "duplicates_removed": "Records removed before screening",
    "duplicates_detail": "Duplicate records removed",
    "automation_removed": "Records marked as ineligible by automation tools",
    "other_removed": "Records removed for other reasons",
    "records_screened": "Records screened",
    "records_excluded": "Records excluded",
    "reports_sought": "Reports sought for retrieval",
    "reports_not_retrieved": "Reports not retrieved",
    "reports_assessed": "Reports assessed for eligibility",
    "reports_excluded": "Reports excluded",
    "studies_included": "Studies included in review",
    "reports_of_studies": "Reports of included studies"
}

# Color scheme matching PRISMA 2020 template
PRISMA_COLORS: Final[Dict[str, str]] = {
    "identification": "#E8F4FD",  # Light blue for identification phase
    "screening": "#FFF3CD",        # Light yellow for screening
    "included": "#D4EDDA",         # Light green for included
    "excluded": "#F8D7DA",         # Light red for excluded
    "border": "#333333",
    "text": "#333333",
    "arrow": "#666666"
}


@dataclass
class PRISMAData:
    """
    Container for PRISMA flow diagram data.

    Follows PRISMA 2020 terminology and structure for systematic reviews
    of clinical trials.

    Attributes:
        databases: Dict mapping database names to record counts
        registers: Dict mapping register names to record counts
        other_sources: Dict mapping other source names to record counts
        duplicates_removed: Number of duplicate records removed
        automation_removed: Records removed by automation (optional)
        other_reasons_removed: Records removed for other reasons (optional)
        records_screened: Total records screened after deduplication
        records_excluded: Records excluded during title/abstract screening
        reports_sought: Reports sought for full-text retrieval
        reports_not_retrieved: Reports that could not be retrieved
        reports_assessed: Reports assessed for eligibility
        reports_excluded_reasons: Dict mapping exclusion reason to count
        studies_included: Final number of studies included
        reports_of_studies: Number of reports (if different from studies)
        search_date: Date the search was conducted
        condition: Condition/topic being reviewed
    """
    databases: Dict[str, int] = field(default_factory=dict)
    registers: Dict[str, int] = field(default_factory=dict)
    other_sources: Dict[str, int] = field(default_factory=dict)
    duplicates_removed: int = 0
    automation_removed: int = 0
    other_reasons_removed: int = 0
    records_screened: int = 0
    records_excluded: int = 0
    reports_sought: int = 0
    reports_not_retrieved: int = 0
    reports_assessed: int = 0
    reports_excluded_reasons: Dict[str, int] = field(default_factory=dict)
    studies_included: int = 0
    reports_of_studies: int = 0
    search_date: str = ""
    condition: str = ""

    def __post_init__(self) -> None:
        """Set defaults and calculate derived values."""
        if not self.search_date:
            self.search_date = datetime.now().strftime("%Y-%m-%d")
        if self.reports_of_studies == 0:
            self.reports_of_studies = self.studies_included

    @property
    def total_identified(self) -> int:
        """Total records identified from all sources."""
        return (
            sum(self.databases.values()) +
            sum(self.registers.values()) +
            sum(self.other_sources.values())
        )

    @property
    def total_removed_before_screening(self) -> int:
        """Total records removed before screening."""
        return self.duplicates_removed + self.automation_removed + self.other_reasons_removed

    @property
    def total_reports_excluded(self) -> int:
        """Total reports excluded with reasons."""
        return sum(self.reports_excluded_reasons.values())

    def validate(self) -> List[str]:
        """
        Validate data consistency and return list of warnings.

        Returns:
            List of warning messages (empty if valid)
        """
        warnings = []

        # Check flow consistency
        expected_screened = self.total_identified - self.total_removed_before_screening
        if self.records_screened != expected_screened and self.records_screened > 0:
            warnings.append(
                f"Records screened ({self.records_screened}) doesn't match "
                f"identified ({self.total_identified}) - removed ({self.total_removed_before_screening})"
            )

        expected_sought = self.records_screened - self.records_excluded
        if self.reports_sought != expected_sought and self.reports_sought > 0:
            warnings.append(
                f"Reports sought ({self.reports_sought}) doesn't match "
                f"screened ({self.records_screened}) - excluded ({self.records_excluded})"
            )

        expected_assessed = self.reports_sought - self.reports_not_retrieved
        if self.reports_assessed != expected_assessed and self.reports_assessed > 0:
            warnings.append(
                f"Reports assessed ({self.reports_assessed}) doesn't match "
                f"sought ({self.reports_sought}) - not retrieved ({self.reports_not_retrieved})"
            )

        expected_included = self.reports_assessed - self.total_reports_excluded
        if self.studies_included != expected_included and self.studies_included > 0:
            warnings.append(
                f"Studies included ({self.studies_included}) doesn't match "
                f"assessed ({self.reports_assessed}) - excluded ({self.total_reports_excluded})"
            )

        return warnings

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "databases": self.databases,
            "registers": self.registers,
            "other_sources": self.other_sources,
            "duplicates_removed": self.duplicates_removed,
            "automation_removed": self.automation_removed,
            "other_reasons_removed": self.other_reasons_removed,
            "records_screened": self.records_screened,
            "records_excluded": self.records_excluded,
            "reports_sought": self.reports_sought,
            "reports_not_retrieved": self.reports_not_retrieved,
            "reports_assessed": self.reports_assessed,
            "reports_excluded_reasons": self.reports_excluded_reasons,
            "studies_included": self.studies_included,
            "reports_of_studies": self.reports_of_studies,
            "search_date": self.search_date,
            "condition": self.condition,
            "total_identified": self.total_identified,
            "total_removed_before_screening": self.total_removed_before_screening,
            "total_reports_excluded": self.total_reports_excluded
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PRISMAData":
        """Create PRISMAData from dictionary."""
        return cls(
            databases=data.get("databases", {}),
            registers=data.get("registers", {}),
            other_sources=data.get("other_sources", {}),
            duplicates_removed=data.get("duplicates_removed", 0),
            automation_removed=data.get("automation_removed", 0),
            other_reasons_removed=data.get("other_reasons_removed", 0),
            records_screened=data.get("records_screened", 0),
            records_excluded=data.get("records_excluded", 0),
            reports_sought=data.get("reports_sought", 0),
            reports_not_retrieved=data.get("reports_not_retrieved", 0),
            reports_assessed=data.get("reports_assessed", 0),
            reports_excluded_reasons=data.get("reports_excluded_reasons", {}),
            studies_included=data.get("studies_included", 0),
            reports_of_studies=data.get("reports_of_studies", 0),
            search_date=data.get("search_date", ""),
            condition=data.get("condition", "")
        )


class PRISMAGenerator:
    """
    Generator for PRISMA 2020 flow diagrams.

    Produces publication-ready flow diagrams in multiple formats
    following the PRISMA 2020 guidelines for systematic reviews.

    Example:
        >>> generator = PRISMAGenerator()
        >>> data = PRISMAData(databases={"CT.gov": 1000}, studies_included=50)
        >>> svg = generator.generate_svg(data)
        >>> generator.save("flowchart", data, formats=["svg", "html", "md"])
    """

    # SVG dimensions
    WIDTH: Final[int] = 900
    HEIGHT: Final[int] = 1100
    BOX_WIDTH: Final[int] = 200
    BOX_HEIGHT: Final[int] = 80
    MARGIN: Final[int] = 50

    def __init__(
        self,
        colors: Optional[Dict[str, str]] = None,
        font_family: str = "Arial, sans-serif",
        font_size: int = 12
    ) -> None:
        """
        Initialize the PRISMA generator.

        Args:
            colors: Optional custom color scheme
            font_family: Font family for text
            font_size: Base font size in pixels
        """
        self.colors = colors or PRISMA_COLORS.copy()
        self.font_family = font_family
        self.font_size = font_size

    def generate_svg(self, data: PRISMAData, title: Optional[str] = None) -> str:
        """
        Generate PRISMA 2020 flow diagram as SVG.

        Args:
            data: PRISMAData with all counts
            title: Optional title for the diagram

        Returns:
            SVG string
        """
        if title is None:
            title = f"PRISMA 2020 Flow Diagram: {data.condition}" if data.condition else "PRISMA 2020 Flow Diagram"

        # Build SVG
        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.WIDTH} {self.HEIGHT}" '
            f'width="{self.WIDTH}" height="{self.HEIGHT}">',
            '<defs>',
            '  <style>',
            f'    .box {{ fill: white; stroke: {self.colors["border"]}; stroke-width: 1.5; }}',
            f'    .box-id {{ fill: {self.colors["identification"]}; }}',
            f'    .box-screen {{ fill: {self.colors["screening"]}; }}',
            f'    .box-include {{ fill: {self.colors["included"]}; }}',
            f'    .box-exclude {{ fill: {self.colors["excluded"]}; }}',
            f'    .text {{ font-family: {self.font_family}; font-size: {self.font_size}px; '
            f'fill: {self.colors["text"]}; text-anchor: middle; }}',
            f'    .text-small {{ font-size: {self.font_size - 2}px; }}',
            f'    .text-bold {{ font-weight: bold; }}',
            f'    .text-left {{ text-anchor: start; }}',
            f'    .arrow {{ fill: none; stroke: {self.colors["arrow"]}; stroke-width: 2; '
            f'marker-end: url(#arrowhead); }}',
            '  </style>',
            '  <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">',
            f'    <polygon points="0 0, 10 3.5, 0 7" fill="{self.colors["arrow"]}" />',
            '  </marker>',
            '</defs>',
        ]

        # Title
        svg_parts.append(
            f'<text x="{self.WIDTH // 2}" y="30" class="text text-bold" '
            f'style="font-size: 16px;">{html.escape(title)}</text>'
        )

        # Phase labels (left side)
        svg_parts.extend([
            '<text x="15" y="150" class="text text-bold text-left" '
            'transform="rotate(-90 15 150)">Identification</text>',
            '<text x="15" y="450" class="text text-bold text-left" '
            'transform="rotate(-90 15 450)">Screening</text>',
            '<text x="15" y="850" class="text text-bold text-left" '
            'transform="rotate(-90 15 850)">Included</text>',
        ])

        # =====================================================================
        # IDENTIFICATION PHASE
        # =====================================================================
        y_id = 70

        # Databases box (left)
        db_x = 100
        db_text = self._format_sources(data.databases, "Databases")
        svg_parts.append(self._create_box(
            db_x, y_id, self.BOX_WIDTH + 50, self.BOX_HEIGHT + 20,
            db_text, "box-id"
        ))

        # Registers box (right)
        reg_x = 500
        reg_text = self._format_sources(data.registers, "Registers")
        if data.other_sources:
            reg_text += "\n" + self._format_sources(data.other_sources, "Other")
        svg_parts.append(self._create_box(
            reg_x, y_id, self.BOX_WIDTH + 50, self.BOX_HEIGHT + 20,
            reg_text, "box-id"
        ))

        # =====================================================================
        # DUPLICATES REMOVED
        # =====================================================================
        y_dup = 200
        dup_text = f"Records removed before screening\n(n = {data.total_removed_before_screening:,})"
        if data.duplicates_removed > 0:
            dup_text += f"\n  Duplicates: {data.duplicates_removed:,}"
        if data.automation_removed > 0:
            dup_text += f"\n  Automation: {data.automation_removed:,}"

        svg_parts.append(self._create_box(
            300, y_dup, self.BOX_WIDTH + 100, self.BOX_HEIGHT,
            dup_text, "box-exclude"
        ))

        # Arrow from databases to duplicates
        svg_parts.append(f'<path class="arrow" d="M {db_x + 125} {y_id + 90} L {db_x + 125} {y_dup - 10} L 300 {y_dup - 10} L 300 {y_dup}" />')
        # Arrow from registers to duplicates
        svg_parts.append(f'<path class="arrow" d="M {reg_x + 125} {y_id + 90} L {reg_x + 125} {y_dup - 10} L 500 {y_dup - 10} L 500 {y_dup}" />')

        # =====================================================================
        # SCREENING PHASE
        # =====================================================================
        y_screen = 320

        # Records screened box
        screen_text = f"Records screened\n(n = {data.records_screened:,})"
        svg_parts.append(self._create_box(
            150, y_screen, self.BOX_WIDTH + 50, self.BOX_HEIGHT,
            screen_text, "box-screen"
        ))

        # Records excluded box
        excl_text = f"Records excluded\n(n = {data.records_excluded:,})"
        svg_parts.append(self._create_box(
            500, y_screen, self.BOX_WIDTH + 50, self.BOX_HEIGHT,
            excl_text, "box-exclude"
        ))

        # Arrows
        svg_parts.append(f'<path class="arrow" d="M 350 {y_dup + 80} L 350 {y_screen - 10} L 275 {y_screen - 10} L 275 {y_screen}" />')
        svg_parts.append(f'<path class="arrow" d="M 350 {y_screen + 40} L 500 {y_screen + 40}" />')

        # =====================================================================
        # RETRIEVAL PHASE
        # =====================================================================
        y_ret = 440

        # Reports sought
        ret_text = f"Reports sought for retrieval\n(n = {data.reports_sought:,})"
        svg_parts.append(self._create_box(
            150, y_ret, self.BOX_WIDTH + 50, self.BOX_HEIGHT,
            ret_text, "box-screen"
        ))

        # Reports not retrieved
        not_ret_text = f"Reports not retrieved\n(n = {data.reports_not_retrieved:,})"
        svg_parts.append(self._create_box(
            500, y_ret, self.BOX_WIDTH + 50, self.BOX_HEIGHT,
            not_ret_text, "box-exclude"
        ))

        # Arrows
        svg_parts.append(f'<path class="arrow" d="M 275 {y_screen + 80} L 275 {y_ret}" />')
        svg_parts.append(f'<path class="arrow" d="M 350 {y_ret + 40} L 500 {y_ret + 40}" />')

        # =====================================================================
        # ELIGIBILITY PHASE
        # =====================================================================
        y_elig = 560

        # Reports assessed
        elig_text = f"Reports assessed for eligibility\n(n = {data.reports_assessed:,})"
        svg_parts.append(self._create_box(
            150, y_elig, self.BOX_WIDTH + 50, self.BOX_HEIGHT,
            elig_text, "box-screen"
        ))

        # Reports excluded with reasons
        excl_reasons_text = f"Reports excluded\n(n = {data.total_reports_excluded:,})"
        for reason, count in list(data.reports_excluded_reasons.items())[:4]:
            excl_reasons_text += f"\n  {reason}: {count:,}"

        excl_height = self.BOX_HEIGHT + len(data.reports_excluded_reasons) * 15
        svg_parts.append(self._create_box(
            500, y_elig, self.BOX_WIDTH + 100, min(excl_height, 180),
            excl_reasons_text, "box-exclude"
        ))

        # Arrows
        svg_parts.append(f'<path class="arrow" d="M 275 {y_ret + 80} L 275 {y_elig}" />')
        svg_parts.append(f'<path class="arrow" d="M 350 {y_elig + 40} L 500 {y_elig + 40}" />')

        # =====================================================================
        # INCLUDED PHASE
        # =====================================================================
        y_incl = 780

        # Studies included
        incl_text = f"Studies included in review\n(n = {data.studies_included:,})"
        if data.reports_of_studies != data.studies_included:
            incl_text += f"\nReports of studies: {data.reports_of_studies:,}"

        svg_parts.append(self._create_box(
            300, y_incl, self.BOX_WIDTH + 100, self.BOX_HEIGHT + 20,
            incl_text, "box-include"
        ))

        # Final arrow
        svg_parts.append(f'<path class="arrow" d="M 275 {y_elig + 80} L 275 {y_incl - 50} L 350 {y_incl - 50} L 350 {y_incl}" />')

        # =====================================================================
        # FOOTER
        # =====================================================================
        svg_parts.append(
            f'<text x="{self.WIDTH // 2}" y="{self.HEIGHT - 30}" class="text text-small" '
            f'style="fill: #666;">Search date: {data.search_date} | Generated with CTGov Search Strategies</text>'
        )

        svg_parts.append('</svg>')

        return '\n'.join(svg_parts)

    def _format_sources(self, sources: Dict[str, int], label: str) -> str:
        """Format database/register sources for display."""
        total = sum(sources.values())
        text = f"Records identified from {label.lower()}\n(n = {total:,})"
        for name, count in sources.items():
            text += f"\n  {name}: {count:,}"
        return text

    def _create_box(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        text: str,
        css_class: str = ""
    ) -> str:
        """Create an SVG box with text."""
        lines = text.split('\n')

        parts = [
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
            f'class="box {css_class}" rx="5" />'
        ]

        # Center text vertically
        line_height = self.font_size + 4
        start_y = y + (height - len(lines) * line_height) // 2 + self.font_size

        for i, line in enumerate(lines):
            line_y = start_y + i * line_height
            css = "text text-small" if line.strip().startswith('  ') else "text"
            parts.append(
                f'<text x="{x + width // 2}" y="{line_y}" class="{css}">'
                f'{html.escape(line.strip())}</text>'
            )

        return '\n'.join(parts)

    def generate_html(self, data: PRISMAData, title: Optional[str] = None) -> str:
        """
        Generate interactive HTML with embedded SVG.

        Args:
            data: PRISMAData with all counts
            title: Optional title

        Returns:
            Complete HTML document string
        """
        svg = self.generate_svg(data, title)

        html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PRISMA Flow Diagram: {html.escape(data.condition or "Systematic Review")}</title>
    <style>
        body {{
            font-family: {self.font_family};
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .diagram-container {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .diagram-container svg {{
            width: 100%;
            height: auto;
        }}
        .metadata {{
            margin-top: 20px;
            padding: 15px;
            background: #e9ecef;
            border-radius: 5px;
        }}
        .metadata h3 {{ margin-top: 0; }}
        .metadata table {{ width: 100%; border-collapse: collapse; }}
        .metadata td, .metadata th {{
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        .export-buttons {{
            margin-top: 15px;
        }}
        .export-buttons button {{
            padding: 8px 16px;
            margin-right: 10px;
            cursor: pointer;
            border: none;
            border-radius: 4px;
            background: #4f46e5;
            color: white;
        }}
        .export-buttons button:hover {{
            background: #4338ca;
        }}
    </style>
</head>
<body>
    <div class="diagram-container">
        {svg}
    </div>

    <div class="metadata">
        <h3>Flow Diagram Summary</h3>
        <table>
            <tr><th>Metric</th><th>Count</th></tr>
            <tr><td>Records identified</td><td>{data.total_identified:,}</td></tr>
            <tr><td>Records after deduplication</td><td>{data.records_screened:,}</td></tr>
            <tr><td>Records screened</td><td>{data.records_screened:,}</td></tr>
            <tr><td>Records excluded</td><td>{data.records_excluded:,}</td></tr>
            <tr><td>Full-text assessed</td><td>{data.reports_assessed:,}</td></tr>
            <tr><td>Studies included</td><td>{data.studies_included:,}</td></tr>
        </table>

        <div class="export-buttons">
            <button onclick="downloadSVG()">Download SVG</button>
            <button onclick="window.print()">Print/PDF</button>
        </div>
    </div>

    <script>
        function downloadSVG() {{
            const svg = document.querySelector('svg');
            const svgData = new XMLSerializer().serializeToString(svg);
            const blob = new Blob([svgData], {{type: 'image/svg+xml'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'prisma_flowchart.svg';
            a.click();
            URL.revokeObjectURL(url);
        }}
    </script>
</body>
</html>'''
        return html_template

    def generate_markdown(self, data: PRISMAData) -> str:
        """
        Generate text-based PRISMA flow diagram in Markdown.

        Args:
            data: PRISMAData with all counts

        Returns:
            Markdown string representation
        """
        md = f'''# PRISMA 2020 Flow Diagram

**Condition:** {data.condition or "Not specified"}
**Search Date:** {data.search_date}

---

## Identification

### Records identified from databases (n = {sum(data.databases.values()):,})
'''
        for db, count in data.databases.items():
            md += f"- {db}: {count:,}\n"

        if data.registers:
            md += f"\n### Records identified from registers (n = {sum(data.registers.values()):,})\n"
            for reg, count in data.registers.items():
                md += f"- {reg}: {count:,}\n"

        md += f'''
### Records removed before screening (n = {data.total_removed_before_screening:,})
- Duplicate records: {data.duplicates_removed:,}
'''
        if data.automation_removed > 0:
            md += f"- Automation removed: {data.automation_removed:,}\n"

        md += f'''
---

## Screening

| Stage | Included | Excluded |
|-------|----------|----------|
| Records screened | {data.records_screened:,} | {data.records_excluded:,} |
| Reports sought | {data.reports_sought:,} | {data.reports_not_retrieved:,} not retrieved |
| Reports assessed | {data.reports_assessed:,} | {data.total_reports_excluded:,} excluded |

### Exclusion reasons
'''
        for reason, count in data.reports_excluded_reasons.items():
            md += f"- {reason}: {count:,}\n"

        md += f'''
---

## Included

**Studies included in review: {data.studies_included:,}**

'''
        if data.reports_of_studies != data.studies_included:
            md += f"Reports of included studies: {data.reports_of_studies:,}\n"

        md += "\n---\n*Generated with CTGov Search Strategies PRISMA Generator*\n"

        return md

    def generate_latex(self, data: PRISMAData) -> str:
        """
        Generate LaTeX/TikZ code for PRISMA flow diagram.

        Args:
            data: PRISMAData with all counts

        Returns:
            LaTeX string for inclusion in academic papers
        """
        latex = r'''\begin{figure}[htbp]
\centering
\begin{tikzpicture}[
    node distance=1.5cm,
    box/.style={rectangle, draw, minimum width=4cm, minimum height=1cm, text centered, rounded corners},
    id/.style={box, fill=blue!10},
    screen/.style={box, fill=yellow!10},
    include/.style={box, fill=green!10},
    exclude/.style={box, fill=red!10},
    arrow/.style={->, >=stealth, thick}
]
'''

        latex += f'''
% Identification
\\node[id] (db) {{Records from databases\\\\(n = {sum(data.databases.values()):,})}};
\\node[id, right=of db] (reg) {{Records from registers\\\\(n = {sum(data.registers.values()):,})}};

% Duplicates
\\node[exclude, below=of db, xshift=2cm] (dup) {{Duplicates removed\\\\(n = {data.duplicates_removed:,})}};

% Screening
\\node[screen, below=of dup] (screen) {{Records screened\\\\(n = {data.records_screened:,})}};
\\node[exclude, right=of screen] (excl1) {{Records excluded\\\\(n = {data.records_excluded:,})}};

% Retrieval
\\node[screen, below=of screen] (sought) {{Reports sought\\\\(n = {data.reports_sought:,})}};
\\node[exclude, right=of sought] (notret) {{Not retrieved\\\\(n = {data.reports_not_retrieved:,})}};

% Eligibility
\\node[screen, below=of sought] (assess) {{Reports assessed\\\\(n = {data.reports_assessed:,})}};
\\node[exclude, right=of assess] (excl2) {{Reports excluded\\\\(n = {data.total_reports_excluded:,})}};

% Included
\\node[include, below=of assess] (incl) {{Studies included\\\\(n = {data.studies_included:,})}};

% Arrows
\\draw[arrow] (db) -- (dup);
\\draw[arrow] (reg) -- (dup);
\\draw[arrow] (dup) -- (screen);
\\draw[arrow] (screen) -- (excl1);
\\draw[arrow] (screen) -- (sought);
\\draw[arrow] (sought) -- (notret);
\\draw[arrow] (sought) -- (assess);
\\draw[arrow] (assess) -- (excl2);
\\draw[arrow] (assess) -- (incl);

\\end{{tikzpicture}}
\\caption{{PRISMA 2020 flow diagram. Search date: {data.search_date}}}
\\label{{fig:prisma}}
\\end{{figure}}
'''
        return latex

    def save(
        self,
        filename: str,
        data: PRISMAData,
        formats: Optional[List[str]] = None,
        output_dir: Optional[Path] = None
    ) -> List[str]:
        """
        Save PRISMA diagram in multiple formats.

        Args:
            filename: Base filename (without extension)
            data: PRISMAData with all counts
            formats: List of formats to generate (svg, html, md, tex, json)
            output_dir: Output directory (defaults to current)

        Returns:
            List of created file paths
        """
        if formats is None:
            formats = ["svg", "html", "md"]

        if output_dir is None:
            output_dir = Path(".")
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        created_files = []

        for fmt in formats:
            if fmt == "svg":
                content = self.generate_svg(data)
                filepath = output_dir / f"{filename}.svg"
            elif fmt == "html":
                content = self.generate_html(data)
                filepath = output_dir / f"{filename}.html"
            elif fmt in ("md", "markdown"):
                content = self.generate_markdown(data)
                filepath = output_dir / f"{filename}.md"
            elif fmt in ("tex", "latex"):
                content = self.generate_latex(data)
                filepath = output_dir / f"{filename}.tex"
            elif fmt == "json":
                content = json.dumps(data.to_dict(), indent=2)
                filepath = output_dir / f"{filename}.json"
            else:
                continue

            filepath.write_text(content, encoding="utf-8")
            created_files.append(str(filepath))

        return created_files


def main() -> None:
    """Demo usage of the PRISMA generator."""
    print("=" * 70)
    print("  PRISMA 2020 Flow Diagram Generator - Demo")
    print("=" * 70)

    # Create sample data for a diabetes systematic review
    data = PRISMAData(
        condition="Type 2 Diabetes Treatment RCTs",
        databases={
            "ClinicalTrials.gov": 2547,
            "WHO ICTRP": 892,
            "Cochrane CENTRAL": 1203
        },
        registers={
            "EU Clinical Trials Register": 412,
            "ISRCTN": 156
        },
        duplicates_removed=1842,
        automation_removed=0,
        records_screened=3368,
        records_excluded=2890,
        reports_sought=478,
        reports_not_retrieved=23,
        reports_assessed=455,
        reports_excluded_reasons={
            "Not randomized": 187,
            "Wrong population": 94,
            "Wrong intervention": 67,
            "Wrong outcome": 45,
            "Protocol only": 12
        },
        studies_included=50,
        reports_of_studies=62
    )

    # Validate data
    warnings = data.validate()
    if warnings:
        print("\nData validation warnings:")
        for w in warnings:
            print(f"  - {w}")

    # Generate outputs
    generator = PRISMAGenerator()

    print(f"\nGenerating PRISMA diagram for: {data.condition}")
    print(f"  Total identified: {data.total_identified:,}")
    print(f"  Studies included: {data.studies_included:,}")

    # Generate and display markdown
    md = generator.generate_markdown(data)
    print("\n--- Markdown Output ---")
    print(md[:1500] + "...\n")

    # Save all formats
    output_dir = Path(__file__).parent / "output"
    files = generator.save(
        "prisma_diabetes_example",
        data,
        formats=["svg", "html", "md", "tex", "json"],
        output_dir=output_dir
    )

    print("\nFiles created:")
    for f in files:
        print(f"  - {f}")

    print("\n" + "=" * 70)
    print("  Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
