#!/usr/bin/env python3
"""
Forest Plot Generator for Strategy Validation Results
Creates publication-quality forest plots showing drug-specific recall with 95% CIs

Author: Mahmood Ahmad
Version: 1.0
"""

import json
import math
from pathlib import Path
from typing import List, Tuple, Dict


def wilson_ci(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score confidence interval"""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denom
    margin = z * math.sqrt((p * (1-p) + z**2 / (4*n)) / n) / denom
    return (max(0, center - margin), min(1, center + margin))


def generate_html_forest_plot(results: List[Dict], strategy: str = "S4_Combined", output_path: str = "forest_plot.html"):
    """Generate an interactive HTML forest plot"""

    # Sort by recall
    sorted_results = sorted(
        [r for r in results if strategy in r.get("strategies", {}) or f"{strategy}" in r],
        key=lambda x: (
            x.get("strategies", {}).get(strategy, {}).get("metrics", {}).get("recall", 0) or
            x.get(strategy, {}).get("recall", 0)
        ),
        reverse=True
    )

    html = """<!DOCTYPE html>
<html>
<head>
    <title>Forest Plot - CT.gov Search Strategy Validation</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 {
            color: #333;
            border-bottom: 2px solid #007acc;
            padding-bottom: 10px;
        }
        .forest-container {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow-x: auto;
        }
        .forest-row {
            display: flex;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }
        .forest-row:hover {
            background: #f9f9f9;
        }
        .drug-name {
            width: 200px;
            font-weight: 500;
            color: #333;
        }
        .drug-condition {
            width: 250px;
            font-size: 12px;
            color: #666;
        }
        .ci-container {
            flex: 1;
            position: relative;
            height: 24px;
            min-width: 400px;
        }
        .ci-axis {
            position: absolute;
            top: 50%;
            left: 0;
            right: 0;
            height: 1px;
            background: #ddd;
        }
        .ci-line {
            position: absolute;
            top: 50%;
            height: 2px;
            background: #007acc;
            transform: translateY(-50%);
        }
        .ci-point {
            position: absolute;
            top: 50%;
            width: 10px;
            height: 10px;
            background: #007acc;
            border-radius: 50%;
            transform: translate(-50%, -50%);
        }
        .ci-point.low {
            background: #dc3545;
        }
        .ci-point.medium {
            background: #ffc107;
        }
        .ci-point.high {
            background: #28a745;
        }
        .recall-text {
            width: 150px;
            text-align: right;
            font-family: monospace;
            font-size: 13px;
        }
        .axis-labels {
            display: flex;
            padding: 5px 0;
            margin-left: 450px;
        }
        .axis-label {
            flex: 1;
            text-align: center;
            font-size: 11px;
            color: #666;
        }
        .reference-line {
            position: absolute;
            top: 0;
            bottom: 0;
            width: 2px;
            background: rgba(0, 122, 204, 0.3);
        }
        .header-row {
            display: flex;
            font-weight: bold;
            padding: 10px 0;
            border-bottom: 2px solid #333;
            background: #f8f9fa;
        }
        .summary {
            margin-top: 20px;
            padding: 15px;
            background: #e8f4fc;
            border-radius: 8px;
        }
        .legend {
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .legend-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }
        .therapeutic-area {
            font-size: 11px;
            color: #888;
            margin-top: 2px;
        }
    </style>
</head>
<body>
    <h1>Forest Plot: Drug-Specific Recall</h1>
    <p>Strategy: <strong>""" + strategy + """</strong> | Sorted by recall (descending)</p>

    <div class="legend">
        <div class="legend-item">
            <div class="legend-dot" style="background: #28a745;"></div>
            <span>Recall ≥80%</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #ffc107;"></div>
            <span>Recall 50-79%</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #dc3545;"></div>
            <span>Recall <50%</span>
        </div>
    </div>

    <div class="forest-container">
        <div class="header-row">
            <div class="drug-name">Drug</div>
            <div class="drug-condition">Condition</div>
            <div class="ci-container">
                <div style="display: flex; justify-content: space-between;">
                    <span>0%</span>
                    <span>25%</span>
                    <span>50%</span>
                    <span>75%</span>
                    <span>100%</span>
                </div>
            </div>
            <div class="recall-text">Recall (95% CI)</div>
        </div>
"""

    for r in sorted_results:
        drug = r.get("drug", "Unknown")
        condition = r.get("condition", "")[:30]

        # Get metrics - handle both old and new format
        if "strategies" in r and strategy in r["strategies"]:
            metrics = r["strategies"][strategy].get("metrics", {})
            gold = r.get("gold_standard", {}).get("total", 0)
        else:
            metrics = r.get(strategy, {})
            gold = r.get("gold", 0)

        recall = metrics.get("recall", 0)
        tp = metrics.get("tp", 0)

        # Calculate CI
        total = tp + metrics.get("fn", gold - tp if gold else 0)
        ci_low, ci_high = wilson_ci(tp, total) if total > 0 else (0, 0)

        # Color class
        if recall >= 0.8:
            color_class = "high"
        elif recall >= 0.5:
            color_class = "medium"
        else:
            color_class = "low"

        # Positions (as percentages)
        point_pos = recall * 100
        ci_low_pos = ci_low * 100
        ci_high_pos = ci_high * 100

        html += f"""
        <div class="forest-row">
            <div class="drug-name">{drug}</div>
            <div class="drug-condition">{condition}</div>
            <div class="ci-container">
                <div class="ci-axis"></div>
                <div class="reference-line" style="left: 75%;"></div>
                <div class="ci-line" style="left: {ci_low_pos}%; width: {ci_high_pos - ci_low_pos}%;"></div>
                <div class="ci-point {color_class}" style="left: {point_pos}%;"></div>
            </div>
            <div class="recall-text">{recall*100:.0f}% ({ci_low*100:.0f}-{ci_high*100:.0f}%)</div>
        </div>
"""

    # Calculate overall
    total_tp = sum(
        r.get("strategies", {}).get(strategy, {}).get("metrics", {}).get("tp", 0) or
        r.get(strategy, {}).get("tp", 0)
        for r in sorted_results
    )
    total_n = sum(
        (r.get("strategies", {}).get(strategy, {}).get("metrics", {}).get("tp", 0) or r.get(strategy, {}).get("tp", 0)) +
        (r.get("strategies", {}).get(strategy, {}).get("metrics", {}).get("fn", 0) or r.get(strategy, {}).get("fn", 0))
        for r in sorted_results
    )

    overall_recall = total_tp / total_n if total_n > 0 else 0
    overall_ci = wilson_ci(total_tp, total_n)

    # Count drugs by recall category
    def get_recall(r):
        return (r.get("strategies", {}).get(strategy, {}).get("metrics", {}).get("recall", 0) or
                r.get(strategy, {}).get("recall", 0))

    drugs_high_recall = sum(1 for r in sorted_results if get_recall(r) >= 0.8)
    drugs_low_recall = sum(1 for r in sorted_results if get_recall(r) < 0.5)

    html += f"""
        <div class="forest-row" style="background: #f0f7ff; font-weight: bold; border-top: 2px solid #333;">
            <div class="drug-name">OVERALL</div>
            <div class="drug-condition">Pooled estimate</div>
            <div class="ci-container">
                <div class="ci-axis"></div>
                <div class="ci-line" style="left: {overall_ci[0]*100}%; width: {(overall_ci[1]-overall_ci[0])*100}%; background: #333;"></div>
                <div class="ci-point" style="left: {overall_recall*100}%; background: #333; width: 14px; height: 14px;"></div>
            </div>
            <div class="recall-text">{overall_recall*100:.1f}% ({overall_ci[0]*100:.1f}-{overall_ci[1]*100:.1f}%)</div>
        </div>
    </div>

    <div class="summary">
        <h3>Summary Statistics</h3>
        <p><strong>Total drugs tested:</strong> {len(sorted_results)}</p>
        <p><strong>Overall recall:</strong> {overall_recall*100:.1f}% (95% CI: {overall_ci[0]*100:.1f}%-{overall_ci[1]*100:.1f}%)</p>
        <p><strong>Drugs with recall ≥80%:</strong> {drugs_high_recall}</p>
        <p><strong>Drugs with recall &lt;50%:</strong> {drugs_low_recall}</p>
    </div>

    <script>
        // Add tooltips on hover
        document.querySelectorAll('.ci-point').forEach(point => {{
            point.style.cursor = 'pointer';
            point.title = 'Click for details';
        }});
    </script>
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Forest plot saved to {output_path}")


def generate_ascii_forest_plot(results: List[Dict], strategy: str = "S4_Combined"):
    """Generate ASCII forest plot for terminal/markdown"""

    sorted_results = sorted(
        [r for r in results if strategy in r.get("strategies", {}) or f"{strategy}" in r],
        key=lambda x: (
            x.get("strategies", {}).get(strategy, {}).get("metrics", {}).get("recall", 0) or
            x.get(strategy, {}).get("recall", 0)
        ),
        reverse=True
    )

    print("\n" + "=" * 100)
    print(f"FOREST PLOT: {strategy}")
    print("=" * 100)
    print(f"{'Drug':<20} {'Recall':>8} {'95% CI':>15} {'Plot (0%':<40}100%)")
    print("-" * 100)

    for r in sorted_results[:30]:  # Top 30
        drug = r.get("drug", "Unknown")[:18]

        if "strategies" in r and strategy in r["strategies"]:
            metrics = r["strategies"][strategy].get("metrics", {})
            gold = r.get("gold_standard", {}).get("total", 0)
        else:
            metrics = r.get(strategy, {})
            gold = r.get("gold", 0)

        recall = metrics.get("recall", 0)
        tp = metrics.get("tp", 0)
        total = tp + metrics.get("fn", gold - tp if gold else 0)
        ci_low, ci_high = wilson_ci(tp, total) if total > 0 else (0, 0)

        # ASCII bar
        bar_width = 40
        point_pos = int(recall * bar_width)
        ci_low_pos = int(ci_low * bar_width)
        ci_high_pos = int(ci_high * bar_width)

        bar = [' '] * bar_width
        for i in range(ci_low_pos, min(ci_high_pos + 1, bar_width)):
            bar[i] = '-'
        if 0 <= point_pos < bar_width:
            bar[point_pos] = 'O'

        bar_str = ''.join(bar)

        print(f"{drug:<20} {recall*100:>7.0f}% ({ci_low*100:>3.0f}-{ci_high*100:>3.0f}%) |{bar_str}|")

    print("-" * 100)


def load_and_plot(results_file: str, output_dir: str = "output"):
    """Load results and generate plots"""

    with open(results_file) as f:
        data = json.load(f)

    results = data.get("results_by_drug", [])

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate HTML forest plot
    generate_html_forest_plot(
        results,
        strategy="S4_Combined",
        output_path=str(output_path / "forest_plot_combined.html")
    )

    # Generate for each strategy
    for strat in ["S1_Basic", "S2_AREA", "S4_Combined"]:
        generate_html_forest_plot(
            results,
            strategy=strat,
            output_path=str(output_path / f"forest_plot_{strat.lower()}.html")
        )

    # ASCII plot
    generate_ascii_forest_plot(results, "S4_Combined")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        results_file = sys.argv[1]
    else:
        results_file = "output/strategy_comparison_final.json"

    load_and_plot(results_file)
