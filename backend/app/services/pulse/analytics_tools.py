"""
analytics_tools.py — Deterministic Python analytics functions for Pulse.

All functions are GENERIC — they operate on dynamic fields and datasets.
None of them assume specific column names like "cgpa" or "department".

The LLM Planner selects and parameterises these tools at runtime.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_numeric_values(records: list[dict], field: str) -> list[float]:
    """Extract non-null numeric values for a given field."""
    values = []
    for rec in records:
        val = rec.get(field)
        if val is not None:
            try:
                values.append(float(val))
            except (TypeError, ValueError):
                pass
    return values


def _safe_round(value: float, digits: int = 4) -> float:
    return round(value, digits)


# ── Basic Numeric Analysis ─────────────────────────────────────────────────────

def count_records(records: list[dict], **_) -> dict:
    """Return total number of records."""
    return {"count": len(records)}


def calculate_average(records: list[dict], field: str, **_) -> dict:
    """Calculate arithmetic mean of a numeric field."""
    values = _get_numeric_values(records, field)
    if not values:
        return {"field": field, "average": None, "error": f"No numeric values found for '{field}'"}
    avg = _safe_round(sum(values) / len(values))
    return {"field": field, "average": avg, "count": len(values)}


def calculate_min(records: list[dict], field: str, **_) -> dict:
    """Find the minimum value of a numeric field."""
    values = _get_numeric_values(records, field)
    if not values:
        return {"field": field, "min": None, "error": f"No numeric values for '{field}'"}
    return {"field": field, "min": _safe_round(min(values))}


def calculate_max(records: list[dict], field: str, **_) -> dict:
    """Find the maximum value of a numeric field."""
    values = _get_numeric_values(records, field)
    if not values:
        return {"field": field, "max": None, "error": f"No numeric values for '{field}'"}
    return {"field": field, "max": _safe_round(max(values))}


def calculate_median(records: list[dict], field: str, **_) -> dict:
    """Calculate the median of a numeric field."""
    values = sorted(_get_numeric_values(records, field))
    if not values:
        return {"field": field, "median": None, "error": f"No numeric values for '{field}'"}
    n = len(values)
    if n % 2 == 1:
        median = values[n // 2]
    else:
        median = (values[n // 2 - 1] + values[n // 2]) / 2
    return {"field": field, "median": _safe_round(median)}


def calculate_sum(records: list[dict], field: str, **_) -> dict:
    """Calculate the sum of a numeric field."""
    values = _get_numeric_values(records, field)
    if not values:
        return {"field": field, "sum": None, "error": f"No numeric values for '{field}'"}
    return {"field": field, "sum": _safe_round(sum(values))}


def calculate_standard_deviation(records: list[dict], field: str, **_) -> dict:
    """Calculate population standard deviation of a numeric field."""
    values = _get_numeric_values(records, field)
    if len(values) < 2:
        return {"field": field, "std_dev": None, "error": "Need at least 2 values"}
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return {"field": field, "std_dev": _safe_round(math.sqrt(variance)), "mean": _safe_round(mean)}


# ── Data Analysis ──────────────────────────────────────────────────────────────

def filter_records(records: list[dict], field: str, operator: str, value: Any, **_) -> dict:
    """
    Filter records by a condition.
    operator: one of "eq", "ne", "gt", "gte", "lt", "lte", "contains", "not_contains"
    """
    ops = {
        "eq": lambda a, b: a == b,
        "ne": lambda a, b: a != b,
        "gt": lambda a, b: float(a) > float(b),
        "gte": lambda a, b: float(a) >= float(b),
        "lt": lambda a, b: float(a) < float(b),
        "lte": lambda a, b: float(a) <= float(b),
        "contains": lambda a, b: str(b).lower() in str(a).lower(),
        "not_contains": lambda a, b: str(b).lower() not in str(a).lower(),
    }
    op_fn = ops.get(operator)
    if op_fn is None:
        return {"error": f"Unknown operator '{operator}'", "filtered_records": []}
    try:
        filtered = [r for r in records if op_fn(r.get(field), value)]
    except (TypeError, ValueError) as exc:
        return {"error": str(exc), "filtered_records": []}
    return {"field": field, "operator": operator, "value": value, "filtered_records": filtered, "count": len(filtered)}


def sort_records(records: list[dict], field: str, order: str = "desc", limit: Optional[int] = None, **_) -> dict:
    """Sort records by a field. order: 'asc' or 'desc'. Optional limit."""
    try:
        sorted_records = sorted(records, key=lambda r: (r.get(field) is None, r.get(field)), reverse=(order == "desc"))
    except TypeError:
        return {"error": f"Cannot sort field '{field}'", "sorted_records": records}
    if limit:
        sorted_records = sorted_records[:limit]
    return {"field": field, "order": order, "sorted_records": sorted_records, "count": len(sorted_records)}


def group_analysis(records: list[dict], group_by: str, metrics: list[str] = None, numeric_fields: list[str] = None, **_) -> dict:
    """
    Group records by a categorical field and compute stats per group.
    metrics: list of operations to run e.g. ["average", "min", "max", "count"]
    numeric_fields: which numeric fields to apply those metrics to (auto-detected if None)
    """
    if metrics is None:
        metrics = ["average", "min", "max", "count"]

    # Group records
    groups: dict[str, list[dict]] = {}
    for rec in records:
        key = str(rec.get(group_by, "Unknown"))
        groups.setdefault(key, []).append(rec)

    # Auto-detect numeric fields if not supplied
    if not numeric_fields:
        sample = records[0] if records else {}
        numeric_fields = [
            k for k, v in sample.items()
            if k != group_by and k != "id" and isinstance(v, (int, float))
        ]

    result: dict[str, Any] = {}
    for group_name, group_records in groups.items():
        group_stats: dict[str, Any] = {"count": len(group_records)}
        for nf in numeric_fields:
            vals = _get_numeric_values(group_records, nf)
            if not vals:
                continue
            field_stats: dict[str, Any] = {}
            if "average" in metrics:
                field_stats["average"] = _safe_round(sum(vals) / len(vals))
            if "min" in metrics:
                field_stats["min"] = _safe_round(min(vals))
            if "max" in metrics:
                field_stats["max"] = _safe_round(max(vals))
            if "sum" in metrics:
                field_stats["sum"] = _safe_round(sum(vals))
            group_stats[nf] = field_stats
        result[group_name] = group_stats

    return {"group_by": group_by, "groups": result, "group_count": len(result)}


def calculate_distribution(records: list[dict], field: str, bins: Optional[int] = None, **_) -> dict:
    """
    Calculate value distribution.
    For categorical: frequency counts.
    For numeric: histogram bins or percentile buckets.
    """
    values = [rec.get(field) for rec in records if rec.get(field) is not None]
    if not values:
        return {"field": field, "distribution": {}, "error": f"No values for '{field}'"}

    # Try numeric distribution
    numeric_vals = _get_numeric_values(records, field)
    if numeric_vals:
        if bins is None:
            bins = min(5, len(set(numeric_vals)))
        min_val, max_val = min(numeric_vals), max(numeric_vals)
        if min_val == max_val:
            return {"field": field, "distribution": {str(min_val): len(numeric_vals)}, "type": "numeric"}
        bin_size = (max_val - min_val) / bins
        distribution: dict[str, int] = {}
        for v in numeric_vals:
            bin_idx = min(int((v - min_val) / bin_size), bins - 1)
            low = _safe_round(min_val + bin_idx * bin_size, 2)
            high = _safe_round(min_val + (bin_idx + 1) * bin_size, 2)
            label = f"{low}–{high}"
            distribution[label] = distribution.get(label, 0) + 1
        return {"field": field, "distribution": distribution, "type": "numeric", "bins": bins}
    else:
        # Categorical frequency
        freq: dict[str, int] = {}
        for v in values:
            freq[str(v)] = freq.get(str(v), 0) + 1
        return {"field": field, "distribution": freq, "type": "categorical"}


def calculate_correlation(records: list[dict], field1: str, field2: str, **_) -> dict:
    """
    Calculate Pearson correlation coefficient between two numeric fields.
    Returns value between -1 (inverse) and 1 (direct).
    """
    pairs = []
    for rec in records:
        v1, v2 = rec.get(field1), rec.get(field2)
        if v1 is not None and v2 is not None:
            try:
                pairs.append((float(v1), float(v2)))
            except (TypeError, ValueError):
                pass

    if len(pairs) < 2:
        return {"field1": field1, "field2": field2, "correlation": None, "error": "Need at least 2 paired values"}

    x_vals = [p[0] for p in pairs]
    y_vals = [p[1] for p in pairs]
    n = len(pairs)
    mean_x = sum(x_vals) / n
    mean_y = sum(y_vals) / n

    numerator = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    denom_x = math.sqrt(sum((x - mean_x) ** 2 for x in x_vals))
    denom_y = math.sqrt(sum((y - mean_y) ** 2 for y in y_vals))

    if denom_x == 0 or denom_y == 0:
        return {"field1": field1, "field2": field2, "correlation": None, "error": "Zero variance in one field"}

    r = numerator / (denom_x * denom_y)
    strength = "strong" if abs(r) >= 0.7 else "moderate" if abs(r) >= 0.4 else "weak"
    direction = "positive" if r > 0 else "negative"

    return {
        "field1": field1,
        "field2": field2,
        "correlation": _safe_round(r),
        "strength": strength,
        "direction": direction,
        "sample_size": n,
    }


def detect_outliers(records: list[dict], field: str, method: str = "iqr", **_) -> dict:
    """
    Detect outliers using IQR (interquartile range) or Z-score method.
    method: "iqr" or "zscore"
    """
    values = _get_numeric_values(records, field)
    if len(values) < 4:
        return {"field": field, "outliers": [], "error": "Need at least 4 values for outlier detection"}

    sorted_vals = sorted(values)
    n = len(sorted_vals)

    if method == "iqr":
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[(3 * n) // 4]
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outlier_records = [r for r in records if r.get(field) is not None and (float(r[field]) < lower or float(r[field]) > upper)]
    else:  # zscore
        mean = sum(values) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in values) / n)
        if std == 0:
            return {"field": field, "outliers": [], "note": "All values identical"}
        outlier_records = [r for r in records if r.get(field) is not None and abs((float(r[field]) - mean) / std) > 2.5]

    return {"field": field, "method": method, "outlier_count": len(outlier_records), "outliers": outlier_records}


# ── Ranking ────────────────────────────────────────────────────────────────────

def rank_records(records: list[dict], field: str, order: str = "desc", **_) -> dict:
    """Rank all records by a field and add 'rank' key."""
    try:
        sorted_recs = sorted(records, key=lambda r: (r.get(field) is None, r.get(field)), reverse=(order == "desc"))
    except TypeError:
        return {"error": f"Cannot rank by field '{field}'", "ranked_records": records}
    ranked = [{**rec, "rank": i + 1} for i, rec in enumerate(sorted_recs)]
    return {"field": field, "order": order, "ranked_records": ranked}


def top_n_records(records: list[dict], field: str, n: int = 5, **_) -> dict:
    """Return top N records by a numeric field."""
    result = sort_records(records, field, order="desc", limit=n)
    return {"field": field, "n": n, "top_records": result.get("sorted_records", [])}


def bottom_n_records(records: list[dict], field: str, n: int = 5, **_) -> dict:
    """Return bottom N records by a numeric field."""
    result = sort_records(records, field, order="asc", limit=n)
    return {"field": field, "n": n, "bottom_records": result.get("sorted_records", [])}


def compare_groups(records: list[dict], group_by: str, compare_field: str, metrics: list[str] = None, **_) -> dict:
    """
    Compare two or more groups on a specific numeric field.
    Returns group stats and a ranked comparison.
    """
    if metrics is None:
        metrics = ["average", "min", "max", "count"]
    ga = group_analysis(records, group_by=group_by, metrics=metrics, numeric_fields=[compare_field])
    groups_data = ga.get("groups", {})

    # Build ranked comparison
    ranking = sorted(
        [(gname, gdata.get(compare_field, {}).get("average")) for gname, gdata in groups_data.items() if gdata.get(compare_field)],
        key=lambda x: (x[1] is None, x[1]),
        reverse=True,
    )

    return {
        "group_by": group_by,
        "compare_field": compare_field,
        "groups": groups_data,
        "ranking": [{"group": g, "average": v} for g, v in ranking],
    }


# ── Tool Registry ──────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, callable] = {
    "count_records": count_records,
    "calculate_average": calculate_average,
    "calculate_min": calculate_min,
    "calculate_max": calculate_max,
    "calculate_median": calculate_median,
    "calculate_sum": calculate_sum,
    "calculate_standard_deviation": calculate_standard_deviation,
    "filter_records": filter_records,
    "sort_records": sort_records,
    "group_analysis": group_analysis,
    "calculate_distribution": calculate_distribution,
    "calculate_correlation": calculate_correlation,
    "detect_outliers": detect_outliers,
    "rank_records": rank_records,
    "top_n_records": top_n_records,
    "bottom_n_records": bottom_n_records,
    "compare_groups": compare_groups,
}


def run_tool(tool_name: str, records: list[dict], parameters: dict) -> dict:
    """Execute a named tool with given parameters and records."""
    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        return {"error": f"Unknown tool: '{tool_name}'", "available_tools": list(TOOL_REGISTRY.keys())}
    try:
        return fn(records, **parameters)
    except Exception as exc:
        logger.error(f"[PulseTool] Error running '{tool_name}': {exc}")
        return {"error": str(exc), "tool": tool_name}
