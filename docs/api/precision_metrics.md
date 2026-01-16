# Precision Metrics

The `precision_metrics` module provides comprehensive metrics for systematic review search strategy evaluation, including precision, recall, NNS (Number Needed to Screen), F1 scores, and diagnostic accuracy measures.

## Module Overview

```python
from precision_metrics import (
    PrecisionCalculator,
    ScreeningEfficiencyAnalyzer,
    ValidationMetrics,
    StrategyResult,
    generate_precision_report,
    export_metrics_csv,
    create_roc_data,
)
```

## PrecisionCalculator Class

Calculate precision and related metrics for search strategies.

### `calculate_precision(relevant_found, total_retrieved)`

Calculate precision (positive predictive value).

**Formula:** `Precision = TP / (TP + FP) = Relevant Found / Total Retrieved`

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `relevant_found` | `int` | Number of relevant studies found (true positives) |
| `total_retrieved` | `int` | Total studies retrieved by the search |

**Returns:** `float` - Precision between 0.0 and 1.0

**Example:**

```python
from precision_metrics import PrecisionCalculator

calc = PrecisionCalculator()

# Search retrieved 500 records, 50 were relevant
precision = calc.calculate_precision(relevant_found=50, total_retrieved=500)
print(f"Precision: {precision:.2%}")  # Output: Precision: 10.00%
```

---

### `calculate_nns(total_retrieved, relevant_found)`

Calculate Number Needed to Screen (NNS).

**Formula:** `NNS = Total Retrieved / Relevant Found = 1 / Precision`

**Interpretation:** Average number of records to screen to find one relevant study. Lower NNS indicates more efficient screening.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `total_retrieved` | `int` | Total studies retrieved |
| `relevant_found` | `int` | Number of relevant studies found |

**Returns:** `float` - NNS value (returns `inf` if no relevant studies found)

**Example:**

```python
from precision_metrics import PrecisionCalculator

calc = PrecisionCalculator()

nns = calc.calculate_nns(total_retrieved=500, relevant_found=50)
print(f"NNS: {nns:.1f}")  # Output: NNS: 10.0
# Interpretation: Screen 10 records to find 1 relevant study
```

---

### `calculate_f1_score(precision, recall)`

Calculate F1 score (harmonic mean of precision and recall).

**Formula:** `F1 = 2 * (precision * recall) / (precision + recall)`

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `precision` | `float` | Precision score (0.0 to 1.0) |
| `recall` | `float` | Recall/sensitivity score (0.0 to 1.0) |

**Returns:** `float` - F1 score between 0.0 and 1.0

**Example:**

```python
from precision_metrics import PrecisionCalculator

calc = PrecisionCalculator()

f1 = calc.calculate_f1_score(precision=0.10, recall=0.95)
print(f"F1 Score: {f1:.3f}")  # Output: F1 Score: 0.181
```

---

### `calculate_specificity(true_negatives, false_positives)`

Calculate specificity (true negative rate).

**Formula:** `Specificity = TN / (TN + FP)`

**Example:**

```python
from precision_metrics import PrecisionCalculator

calc = PrecisionCalculator()

specificity = calc.calculate_specificity(true_negatives=9500, false_positives=450)
print(f"Specificity: {specificity:.4f}")
```

## ScreeningEfficiencyAnalyzer Class

Analyze screening workload and efficiency for systematic reviews.

### `estimate_screening_time(nns, time_per_abstract_minutes)`

Estimate screening time based on NNS.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `nns` | `float` | *required* | Number Needed to Screen |
| `time_per_abstract_minutes` | `float` | `2.0` | Time to screen one abstract |

**Returns:** `float` - Hours to find one relevant study

**Example:**

```python
from precision_metrics import ScreeningEfficiencyAnalyzer

analyzer = ScreeningEfficiencyAnalyzer()

hours = analyzer.estimate_screening_time(nns=50)
print(f"Hours per relevant study: {hours:.1f}")  # Output: 1.7 hours
```

---

### `calculate_workload_reduction(strategy_a_count, strategy_b_count)`

Calculate percentage workload reduction between two strategies.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `strategy_a_count` | `int` | Records from baseline strategy |
| `strategy_b_count` | `int` | Records from alternative strategy |

**Returns:** `float` - Percentage reduction (positive = B requires less screening)

**Example:**

```python
from precision_metrics import ScreeningEfficiencyAnalyzer

analyzer = ScreeningEfficiencyAnalyzer()

# Strategy A retrieves 1000, Strategy B retrieves 600
reduction = analyzer.calculate_workload_reduction(1000, 600)
print(f"Workload reduction: {reduction:.1f}%")  # Output: 40.0%
```

---

### `compare_screening_burden(strategies_results)`

Compare and rank strategies by screening burden.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `strategies_results` | `List[StrategyResult]` | List of strategy results to compare |

**Returns:** `List[Dict]` - Sorted by NNS (most efficient first)

**Example:**

```python
from precision_metrics import ScreeningEfficiencyAnalyzer, StrategyResult

analyzer = ScreeningEfficiencyAnalyzer()

results = [
    StrategyResult("S1", "Condition Only", 1000, 50),
    StrategyResult("S3", "RCT Filter", 300, 45),
    StrategyResult("S7", "Completed", 200, 40),
]

ranked = analyzer.compare_screening_burden(results)

for r in ranked:
    print(f"{r['rank']}. {r['strategy_id']}: NNS={r['nns']:.1f}, Precision={r['precision']:.2%}")
```

## ValidationMetrics Class

Comprehensive diagnostic accuracy metrics.

### `full_metrics(true_positives, false_positives, false_negatives, true_negatives)`

Calculate all diagnostic accuracy metrics from a 2x2 confusion matrix.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `true_positives` | `int` | Relevant studies correctly retrieved (TP) |
| `false_positives` | `int` | Irrelevant studies incorrectly retrieved (FP) |
| `false_negatives` | `int` | Relevant studies missed (FN) |
| `true_negatives` | `int` | Irrelevant studies correctly not retrieved (TN) |

**Returns:** `Dict[str, float]` containing:

| Metric | Description |
|--------|-------------|
| `sensitivity` | True positive rate (recall) |
| `specificity` | True negative rate |
| `precision` | Positive predictive value |
| `npv` | Negative predictive value |
| `f1_score` | Harmonic mean of precision and recall |
| `accuracy` | Overall accuracy |
| `nns` | Number Needed to Screen |
| `lr_positive` | Positive likelihood ratio |
| `lr_negative` | Negative likelihood ratio |
| `dor` | Diagnostic Odds Ratio |

**Example:**

```python
from precision_metrics import ValidationMetrics

validator = ValidationMetrics()

# Example: S3 strategy results
metrics = validator.full_metrics(
    true_positives=45,
    false_positives=255,
    false_negatives=5,
    true_negatives=9695
)

print(f"Sensitivity: {metrics['sensitivity']:.4f}")
print(f"Specificity: {metrics['specificity']:.4f}")
print(f"Precision:   {metrics['precision']:.4f}")
print(f"F1 Score:    {metrics['f1_score']:.4f}")
print(f"DOR:         {metrics['dor']:.2f}")
```

---

### `confusion_matrix_from_results(found_ncts, known_ncts, total_searched)`

Construct confusion matrix from search results and gold standard.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `found_ncts` | `Set[str]` | NCT IDs retrieved by the search |
| `known_ncts` | `Set[str]` | NCT IDs known to be relevant (gold standard) |
| `total_searched` | `int` | Total records in the database searched |

**Returns:** `Dict[str, int]` - Confusion matrix values

**Example:**

```python
from precision_metrics import ValidationMetrics

validator = ValidationMetrics()

found = {"NCT00000001", "NCT00000002", "NCT00000003", "NCT00000004", "NCT00000005"}
known = {"NCT00000001", "NCT00000002", "NCT00000006"}

cm = validator.confusion_matrix_from_results(found, known, total_searched=10000)

print(f"TP: {cm['true_positives']}")   # 2 (found and relevant)
print(f"FP: {cm['false_positives']}")  # 3 (found but not relevant)
print(f"FN: {cm['false_negatives']}")  # 1 (relevant but not found)
print(f"TN: {cm['true_negatives']}")   # 9994 (not found, not relevant)
```

---

### `calculate_likelihood_ratios(sensitivity, specificity)`

Calculate positive and negative likelihood ratios.

**Returns:** `Tuple[float, float]` - (LR+, LR-)

**Interpretation:**

| LR+ Value | Interpretation |
|-----------|----------------|
| > 10 | Strong evidence for relevance if found |
| 5-10 | Moderate evidence for relevance |
| < 5 | Weak evidence |

| LR- Value | Interpretation |
|-----------|----------------|
| < 0.1 | Strong evidence against relevance if not found |
| 0.1-0.2 | Moderate evidence against relevance |
| > 0.2 | Weak evidence |

**Example:**

```python
from precision_metrics import ValidationMetrics

validator = ValidationMetrics()

lr_pos, lr_neg = validator.calculate_likelihood_ratios(
    sensitivity=0.90,
    specificity=0.97
)

print(f"LR+: {lr_pos:.2f}")
print(f"LR-: {lr_neg:.4f}")
```

## Report Generation

### `generate_precision_report(condition, strategies_results, known_ncts, total_database_size)`

Generate a comprehensive markdown precision report.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `condition` | `str` | *required* | Medical condition |
| `strategies_results` | `List[StrategyResult]` | *required* | Strategy results |
| `known_ncts` | `Set[str]` | *required* | Gold standard NCT IDs |
| `total_database_size` | `Optional[int]` | `None` | Total records for specificity |

**Returns:** `str` - Markdown-formatted report

**Example:**

```python
from precision_metrics import generate_precision_report, StrategyResult

results = [
    StrategyResult("S1", "Condition Only", 1000, 48, {"NCT..."}),
    StrategyResult("S3", "RCT Filter", 300, 45, {"NCT..."}),
]

known = {"NCT00000001", "NCT00000002", "..."}

report = generate_precision_report(
    condition="heart failure",
    strategies_results=results,
    known_ncts=known,
    total_database_size=10000
)

# Save report
with open("precision_report.md", "w") as f:
    f.write(report)
```

## ROC Data Generation

### `create_roc_data(strategies_results, known_ncts, total_database_size)`

Create ROC curve data for plotting strategy performance.

**Returns:** `Dict` containing:

- `points`: List of (strategy_id, fpr, tpr) coordinates
- `auc_estimates`: Dict mapping strategy_id to rough AUC estimate

**Example:**

```python
from precision_metrics import create_roc_data, StrategyResult

results = [...]  # Your strategy results

roc = create_roc_data(results, known_ncts, total_database_size=10000)

# Plot ROC points
for point in roc['points']:
    print(f"{point['strategy_id']}: FPR={point['fpr']:.3f}, TPR={point['tpr']:.3f}")

# AUC estimates
for strategy, auc in roc['auc_estimates'].items():
    print(f"{strategy} AUC: {auc:.3f}")
```

## Complete Workflow Example

```python
from precision_metrics import (
    PrecisionCalculator,
    ScreeningEfficiencyAnalyzer,
    ValidationMetrics,
    StrategyResult,
    generate_precision_report,
)

def evaluate_search_strategies():
    """Complete precision analysis workflow."""

    # Initialize calculators
    calc = PrecisionCalculator()
    analyzer = ScreeningEfficiencyAnalyzer()
    validator = ValidationMetrics()

    # Gold standard: 50 known relevant RCTs
    known_relevant = {f"NCT{str(i).zfill(8)}" for i in range(1, 51)}

    # Strategy results (from CTGovSearcher)
    strategies = [
        StrategyResult("S1", "Condition Only", 1000, 48),
        StrategyResult("S3", "RCT Filter", 300, 45),
        StrategyResult("S7", "Completed", 200, 40),
    ]

    # 1. Calculate precision and NNS for each strategy
    print("=" * 60)
    print("PRECISION ANALYSIS")
    print("=" * 60)

    for strat in strategies:
        precision = calc.calculate_precision(strat.relevant_found, strat.total_retrieved)
        nns = calc.calculate_nns(strat.total_retrieved, strat.relevant_found)
        recall = strat.relevant_found / len(known_relevant)
        f1 = calc.calculate_f1_score(precision, recall)

        print(f"\n{strat.strategy_id} - {strat.strategy_name}:")
        print(f"  Retrieved: {strat.total_retrieved:,}")
        print(f"  Precision: {precision:.2%}")
        print(f"  Recall: {recall:.2%}")
        print(f"  F1: {f1:.3f}")
        print(f"  NNS: {nns:.1f}")

    # 2. Rank by screening efficiency
    print("\n" + "=" * 60)
    print("EFFICIENCY RANKING")
    print("=" * 60)

    ranked = analyzer.compare_screening_burden(strategies)
    for r in ranked:
        hours = analyzer.estimate_screening_time(r['nns'])
        print(f"{r['rank']}. {r['strategy_id']}: NNS={r['nns']:.1f}, {hours:.1f} hrs/relevant")

    # 3. Full diagnostic metrics for best strategy
    print("\n" + "=" * 60)
    print("DIAGNOSTIC METRICS (S3)")
    print("=" * 60)

    tp, fp, fn = 45, 255, 5
    tn = 10000 - tp - fp - fn

    metrics = validator.full_metrics(tp, fp, fn, tn)
    print(f"  Sensitivity: {metrics['sensitivity']:.4f}")
    print(f"  Specificity: {metrics['specificity']:.4f}")
    print(f"  LR+: {metrics['lr_positive']:.2f}")
    print(f"  LR-: {metrics['lr_negative']:.4f}")
    print(f"  DOR: {metrics['dor']:.2f}")


if __name__ == "__main__":
    evaluate_search_strategies()
```
