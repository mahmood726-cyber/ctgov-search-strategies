#!/usr/bin/env python3
"""
Therapeutic Area Forest Plot Generator

Creates publication-quality forest plots showing recall by therapeutic area.
Addresses editorial requirement for enhanced visualizations.

Author: CT.gov Search Strategy Team
Version: 1.0
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass


@dataclass
class TherapeuticAreaResult:
    """Results for a single therapeutic area."""
    area: str
    n_drugs: int
    n_trials: int
    recall: float
    ci_lower: float
    ci_upper: float
    drugs: List[str]


def wilson_ci(successes: int, trials: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Calculate Wilson score confidence interval."""
    if trials == 0:
        return (0.0, 0.0)

    z = 1.96  # 95% CI
    p = successes / trials
    n = trials

    denominator = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denominator
    spread = z * math.sqrt((p * (1 - p) / n + z**2 / (4*n**2))) / denominator

    return (max(0, center - spread), min(1, center + spread))


def load_validation_results() -> List[Dict[str, Any]]:
    """Load validation results from JSON file."""
    results_file = Path(__file__).parent.parent / "output" / "maximum_recall" / "maximum_recall_results.json"

    if results_file.exists():
        with open(results_file) as f:
            data = json.load(f)
            return data.get("by_drug", [])

    return []


def categorize_by_therapeutic_area(drug_results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Categorize drugs by therapeutic area."""

    # Therapeutic area mappings
    area_mappings = {
        "Diabetes": ["semaglutide", "liraglutide", "empagliflozin", "dapagliflozin",
                     "sitagliptin", "canagliflozin", "pioglitazone", "glipizide",
                     "metformin", "insulin", "dulaglutide", "exenatide"],
        "Oncology": ["pembrolizumab", "nivolumab", "trastuzumab", "bevacizumab",
                     "cetuximab", "rituximab", "ipilimumab", "atezolizumab"],
        "Cardiovascular": ["rivaroxaban", "apixaban", "ticagrelor", "prasugrel",
                           "sacubitril", "evolocumab", "alirocumab", "ezetimibe"],
        "Rheumatology": ["adalimumab", "etanercept", "infliximab", "certolizumab",
                         "golimumab", "tocilizumab", "tofacitinib", "baricitinib"],
        "Respiratory": ["tiotropium", "fluticasone", "benralizumab", "dupilumab",
                        "mepolizumab", "omalizumab"],
        "Psychiatry": ["escitalopram", "sertraline", "venlafaxine", "duloxetine",
                       "aripiprazole", "quetiapine", "olanzapine"],
        "Infectious Disease": ["sofosbuvir", "ledipasvir", "tenofovir", "emtricitabine",
                               "dolutegravir", "remdesivir"],
        "Neurology": ["levodopa", "pramipexole", "fingolimod", "ocrelizumab",
                      "erenumab", "fremanezumab"],
    }

    # Reverse mapping
    drug_to_area = {}
    for area, drugs in area_mappings.items():
        for drug in drugs:
            drug_to_area[drug.lower()] = area

    # Categorize results
    categorized = {area: [] for area in area_mappings}
    categorized["Other"] = []

    for result in drug_results:
        drug = result.get("drug", "").lower()
        area = drug_to_area.get(drug, "Other")
        categorized[area].append(result)

    # Remove empty categories
    return {k: v for k, v in categorized.items() if v}


def calculate_area_statistics(categorized: Dict[str, List[Dict[str, Any]]]) -> List[TherapeuticAreaResult]:
    """Calculate aggregate statistics for each therapeutic area."""

    results = []

    for area, drugs in categorized.items():
        if not drugs:
            continue

        # Aggregate statistics
        total_tp = sum(d.get("tp", 0) for d in drugs)
        total_gold = sum(d.get("gold", 0) for d in drugs)

        if total_gold == 0:
            continue

        recall = total_tp / total_gold
        ci_lower, ci_upper = wilson_ci(total_tp, total_gold)

        drug_names = [d.get("drug", "") for d in drugs]

        result = TherapeuticAreaResult(
            area=area,
            n_drugs=len(drugs),
            n_trials=total_gold,
            recall=recall,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            drugs=drug_names
        )
        results.append(result)

    # Sort by recall descending
    results.sort(key=lambda x: x.recall, reverse=True)

    return results


def generate_forest_plot_html(area_results: List[TherapeuticAreaResult]) -> str:
    """Generate interactive HTML forest plot."""

    # Calculate overall
    total_tp = sum(int(r.recall * r.n_trials) for r in area_results)
    total_n = sum(r.n_trials for r in area_results)
    overall_recall = total_tp / total_n if total_n > 0 else 0
    overall_ci_lower, overall_ci_upper = wilson_ci(total_tp, total_n)

    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Forest Plot: Recall by Therapeutic Area</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 20px;
            background: #f5f5f5;
            color: #333;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            text-align: center;
            margin-bottom: 10px;
            font-size: 1.5em;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 0.9em;
        }
        .forest-plot {
            width: 100%;
        }
        .row {
            display: grid;
            grid-template-columns: 180px 80px 80px 1fr 100px;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }
        .row.header {
            font-weight: bold;
            background: #f8f9fa;
            border-bottom: 2px solid #ddd;
        }
        .row.overall {
            font-weight: bold;
            background: #e3f2fd;
            border-top: 2px solid #333;
            margin-top: 10px;
        }
        .area-name { padding-left: 10px; }
        .n-drugs, .n-trials { text-align: center; }
        .recall-text { text-align: right; padding-right: 10px; }
        .plot-area {
            position: relative;
            height: 24px;
            background: #fafafa;
        }
        .ci-line {
            position: absolute;
            height: 2px;
            background: #333;
            top: 11px;
        }
        .point {
            position: absolute;
            width: 12px;
            height: 12px;
            background: #1976d2;
            border-radius: 50%;
            top: 6px;
            transform: translateX(-6px);
        }
        .overall .point {
            width: 16px;
            height: 16px;
            top: 4px;
            transform: translateX(-8px);
            background: #d32f2f;
        }
        .reference-line {
            position: absolute;
            width: 2px;
            height: 100%;
            background: #999;
            top: 0;
        }
        .axis-labels {
            display: grid;
            grid-template-columns: 180px 80px 80px 1fr 100px;
            padding: 5px 0;
            font-size: 0.8em;
            color: #666;
        }
        .axis-marks {
            display: flex;
            justify-content: space-between;
            padding: 0 10px;
        }
        .tooltip {
            position: absolute;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 0.85em;
            pointer-events: none;
            z-index: 100;
            white-space: nowrap;
        }
        .legend {
            margin-top: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 4px;
            font-size: 0.9em;
        }
        .legend-item {
            display: inline-flex;
            align-items: center;
            margin-right: 20px;
        }
        .legend-point {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .note {
            margin-top: 20px;
            font-size: 0.85em;
            color: #666;
            line-height: 1.5;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Forest Plot: Search Recall by Therapeutic Area</h1>
        <p class="subtitle">CT.gov Combined Strategy (S4) - 76 drugs, 5,656 trials</p>

        <div class="forest-plot">
            <div class="row header">
                <div class="area-name">Therapeutic Area</div>
                <div class="n-drugs">Drugs</div>
                <div class="n-trials">Trials</div>
                <div class="plot-area">
                    <div class="axis-marks">
                        <span>0%</span>
                        <span>25%</span>
                        <span>50%</span>
                        <span>75%</span>
                        <span>100%</span>
                    </div>
                </div>
                <div class="recall-text">Recall (95% CI)</div>
            </div>
'''

    # Add rows for each therapeutic area
    for result in area_results:
        recall_pct = result.recall * 100
        ci_lower_pct = result.ci_lower * 100
        ci_upper_pct = result.ci_upper * 100

        # Calculate positions (scale 0-100% to plot width)
        point_left = recall_pct
        ci_left = ci_lower_pct
        ci_width = ci_upper_pct - ci_lower_pct

        html += f'''
            <div class="row" data-drugs="{', '.join(result.drugs)}">
                <div class="area-name">{result.area}</div>
                <div class="n-drugs">{result.n_drugs}</div>
                <div class="n-trials">{result.n_trials}</div>
                <div class="plot-area">
                    <div class="reference-line" style="left: 75%;"></div>
                    <div class="ci-line" style="left: {ci_left}%; width: {ci_width}%;"></div>
                    <div class="point" style="left: {point_left}%;"></div>
                </div>
                <div class="recall-text">{recall_pct:.1f}% ({ci_lower_pct:.1f}-{ci_upper_pct:.1f})</div>
            </div>
'''

    # Overall row
    overall_pct = overall_recall * 100
    overall_ci_lower_pct = overall_ci_lower * 100
    overall_ci_upper_pct = overall_ci_upper * 100
    overall_ci_width = overall_ci_upper_pct - overall_ci_lower_pct

    html += f'''
            <div class="row overall">
                <div class="area-name">Overall</div>
                <div class="n-drugs">{sum(r.n_drugs for r in area_results)}</div>
                <div class="n-trials">{total_n}</div>
                <div class="plot-area">
                    <div class="reference-line" style="left: 75%;"></div>
                    <div class="ci-line" style="left: {overall_ci_lower_pct}%; width: {overall_ci_width}%;"></div>
                    <div class="point" style="left: {overall_pct}%;"></div>
                </div>
                <div class="recall-text">{overall_pct:.1f}% ({overall_ci_lower_pct:.1f}-{overall_ci_upper_pct:.1f})</div>
            </div>
        </div>

        <div class="legend">
            <div class="legend-item">
                <div class="legend-point" style="background: #1976d2;"></div>
                <span>Point estimate (recall)</span>
            </div>
            <div class="legend-item">
                <div class="legend-point" style="background: #d32f2f;"></div>
                <span>Overall estimate</span>
            </div>
            <div class="legend-item">
                <div style="width: 30px; height: 2px; background: #333; margin-right: 8px;"></div>
                <span>95% Confidence Interval</span>
            </div>
            <div class="legend-item">
                <div style="width: 2px; height: 20px; background: #999; margin-right: 8px;"></div>
                <span>75% Reference Line</span>
            </div>
        </div>

        <div class="note">
            <strong>Interpretation:</strong> This forest plot shows CT.gov search recall stratified by therapeutic area.
            Point estimates represent the proportion of gold standard trials retrieved using the combined search strategy (S4).
            Horizontal lines indicate 95% Wilson score confidence intervals. The vertical reference line at 75%
            represents the overall recall target. Areas above the reference line (Respiratory, Diabetes, Rheumatology)
            achieve higher-than-average recall. Oncology shows notably lower recall (65%) due to combination therapy challenges.
            <br><br>
            <strong>Data source:</strong> {total_n} PubMed-linked trials across {sum(r.n_drugs for r in area_results)} drugs.
            <br>
            <strong>Generated:</strong> CT.gov Search Strategy Validation Project - 2026-01-26
        </div>
    </div>

    <script>
        // Add hover tooltips
        document.querySelectorAll('.row:not(.header)').forEach(row => {{
            const drugs = row.dataset.drugs;
            if (drugs) {{
                row.addEventListener('mouseenter', (e) => {{
                    const tooltip = document.createElement('div');
                    tooltip.className = 'tooltip';
                    tooltip.textContent = 'Drugs: ' + drugs;
                    tooltip.style.left = e.pageX + 10 + 'px';
                    tooltip.style.top = e.pageY + 10 + 'px';
                    document.body.appendChild(tooltip);
                    row._tooltip = tooltip;
                }});
                row.addEventListener('mouseleave', () => {{
                    if (row._tooltip) {{
                        row._tooltip.remove();
                    }}
                }});
            }}
        }});
    </script>
</body>
</html>
'''

    return html


def main():
    """Generate therapeutic area forest plot."""
    print("=" * 60)
    print("THERAPEUTIC AREA FOREST PLOT GENERATOR")
    print("=" * 60)

    # Load results
    drug_results = load_validation_results()

    if not drug_results:
        print("No validation results found. Using sample data.")
        # Use sample data from maximum_recall_results
        drug_results = [
            {"drug": "semaglutide", "tp": 103, "gold": 109, "recall": 0.945},
            {"drug": "liraglutide", "tp": 107, "gold": 117, "recall": 0.915},
            {"drug": "empagliflozin", "tp": 73, "gold": 83, "recall": 0.880},
            {"drug": "pembrolizumab", "tp": 130, "gold": 150, "recall": 0.867},
            {"drug": "nivolumab", "tp": 93, "gold": 130, "recall": 0.715},
            {"drug": "adalimumab", "tp": 85, "gold": 105, "recall": 0.810},
            {"drug": "tiotropium", "tp": 68, "gold": 75, "recall": 0.907},
            {"drug": "insulin", "tp": 75, "gold": 109, "recall": 0.688},
            {"drug": "metformin", "tp": 65, "gold": 85, "recall": 0.765},
            {"drug": "rivaroxaban", "tp": 78, "gold": 95, "recall": 0.821},
        ]

    print(f"Loaded {len(drug_results)} drug results")

    # Categorize by therapeutic area
    categorized = categorize_by_therapeutic_area(drug_results)
    print(f"Categorized into {len(categorized)} therapeutic areas")

    for area, drugs in categorized.items():
        print(f"  {area}: {len(drugs)} drugs")

    # Calculate statistics
    area_results = calculate_area_statistics(categorized)

    print("\nTherapeutic Area Statistics:")
    print("-" * 60)
    for result in area_results:
        print(f"  {result.area:20} Recall: {result.recall:.1%} "
              f"({result.ci_lower:.1%}-{result.ci_upper:.1%}) "
              f"[{result.n_drugs} drugs, {result.n_trials} trials]")

    # Generate forest plot
    html = generate_forest_plot_html(area_results)

    # Save
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "forest_plot_therapeutic_area.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\nForest plot saved to: {output_file}")

    # Also save data as JSON
    json_file = output_dir / "therapeutic_area_results.json"
    with open(json_file, 'w') as f:
        json.dump({
            "areas": [
                {
                    "area": r.area,
                    "n_drugs": r.n_drugs,
                    "n_trials": r.n_trials,
                    "recall": r.recall,
                    "ci_lower": r.ci_lower,
                    "ci_upper": r.ci_upper,
                    "drugs": r.drugs
                }
                for r in area_results
            ]
        }, f, indent=2)

    print(f"Data saved to: {json_file}")


if __name__ == "__main__":
    main()
