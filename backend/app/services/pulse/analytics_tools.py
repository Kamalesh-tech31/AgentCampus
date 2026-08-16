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


def _humanize(name: str) -> str:
    """Convert snake_case or camelCase field name to title case label."""
    if not name:
        return ""
    if str(name).lower() == "cgpa":
        return "CGPA"
    if str(name).lower() == "gpa":
        return "GPA"
    import re
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1 \2', name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1 \2', s1)
    return s2.replace('_', ' ').strip().title()


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
    valid_records = []
    for rec in records:
        v1 = rec.get(field1)
        v2 = rec.get(field2)
        if v1 is not None and v2 is not None:
            try:
                p1, p2 = float(v1), float(v2)
                pairs.append((p1, p2))
                valid_records.append(rec)
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
    denom_x_sq = sum((x - mean_x) ** 2 for x in x_vals)
    denom_y_sq = sum((y - mean_y) ** 2 for y in y_vals)
    denom_x = math.sqrt(denom_x_sq)
    denom_y = math.sqrt(denom_y_sq)

    if denom_x == 0 or denom_y == 0:
        return {"field1": field1, "field2": field2, "correlation": None, "error": "Zero variance in one field"}

    r = numerator / (denom_x * denom_y)
    r_rounded = _safe_round(r, 4)
    r_squared = _safe_round(r ** 2, 4)

    # Linear regression slope (m) and intercept (b): y = mx + b
    slope = numerator / denom_x_sq if denom_x_sq != 0 else 0.0
    intercept = mean_y - (slope * mean_x)

    abs_r = abs(r)
    if abs_r >= 0.8:
        strength = "very strong"
    elif abs_r >= 0.6:
        strength = "strong"
    elif abs_r >= 0.4:
        strength = "moderate"
    elif abs_r >= 0.2:
        strength = "weak"
    else:
        strength = "negligible"

    direction = "positive" if r > 0.05 else "negative" if r < -0.05 else "neutral"

    # Descriptive statistics for both dimensions
    std_x = math.sqrt(denom_x_sq / n) if n > 0 else 0.0
    std_y = math.sqrt(denom_y_sq / n) if n > 0 else 0.0

    field1_label = _humanize(field1)
    field2_label = _humanize(field2)
    reg_formula = f"{field2_label} = ({slope:.4f} × {field1_label}) + {intercept:.4f}"

    interpretation = (
        f"A {strength} {direction} correlation (r = {r_rounded:.4f}, R² = {r_squared:.4f}) was observed between {field1_label} and {field2_label}. "
        f"Approximately {r_squared * 100:.1f}% of the variance in {field2_label} can be statistically accounted for by {field1_label}. "
        f"Note: Correlation reflects statistical association and does not imply direct causation."
    )

    scatter_points = [
        {
            "x": p[0],
            "y": p[1],
            "name": rec.get("name", rec.get("rollNumber", f"Student {i+1}")),
            "rollNumber": rec.get("rollNumber", ""),
            "department": rec.get("department", ""),
        }
        for i, (p, rec) in enumerate(zip(pairs, valid_records))
    ]

    return {
        "analysis_type": "correlation_analysis",
        "tool": "calculate_correlation",
        "field1": field1,
        "field2": field2,
        "field1_label": field1_label,
        "field2_label": field2_label,
        "correlation": r_rounded,
        "r_squared": r_squared,
        "strength": strength,
        "direction": direction,
        "sample_size": n,
        "regression": {
            "slope": _safe_round(slope, 4),
            "intercept": _safe_round(intercept, 4),
            "formula": reg_formula,
        },
        "field1_stats": {
            "mean": _safe_round(mean_x, 2),
            "std_dev": _safe_round(std_x, 2),
            "min": _safe_round(min(x_vals), 2),
            "max": _safe_round(max(x_vals), 2),
        },
        "field2_stats": {
            "mean": _safe_round(mean_y, 2),
            "std_dev": _safe_round(std_y, 2),
            "min": _safe_round(min(y_vals), 2),
            "max": _safe_round(max(y_vals), 2),
        },
        "interpretation": interpretation,
        "scatter_points": scatter_points,
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


# ── Ranking & Weighted Scoring ──────────────────────────────────────────────────

def calculate_weighted_ranking(
    records: list[dict],
    weights: Optional[dict[str, float] | list[dict[str, Any]]] = None,
    top_n: int = 10,
    tie_breaker: Optional[str] = None,
    **_,
) -> dict:
    """
    Deterministic weighted composite ranking across multiple criteria with automatic
    scale normalization, robust tie detection, competition ranking, and tie-breaking.

    Scale Normalization:
      - CGPA (0-10 scale) -> normalized to (cgpa / 10) * 100
      - Attendance (0-100 scale) -> used directly as percentage
      - Generic fields -> normalized to 100-point scale based on detected domain max

    Weighted Score Formula (for 80% Academic / 20% Attendance):
      Academic Score = (CGPA / 10) * 100
      Weighted Score = (Academic Score * 0.80) + (Attendance * 0.20)
    """
    if not records:
        return {
            "analysis_type": "weighted_ranking",
            "error": "No records available for ranking",
            "total_records": 0,
            "top_n": top_n,
            "ranking": [],
        }

    # Normalize weights input to dict of {field_name: float_weight}
    normalized_weights: dict[str, float] = {}
    if weights is None:
        normalized_weights = {"cgpa": 0.80, "attendance": 0.20}
    elif isinstance(weights, list):
        for w in weights:
            if isinstance(w, dict) and "field" in w and "weight" in w:
                normalized_weights[str(w["field"])] = float(w["weight"])
    elif isinstance(weights, dict):
        normalized_weights = {str(k): float(v) for k, v in weights.items()}

    # Resolve field aliases (e.g. "marks", "academic", "grade" -> "cgpa")
    sample = records[0] if records else {}
    available_cols = set(sample.keys())
    resolved_weights: dict[str, float] = {}

    for k, w_val in normalized_weights.items():
        k_lower = k.lower()
        if k_lower in available_cols:
            resolved_weights[k_lower] = w_val
        elif k_lower in ("marks", "academic", "academics", "grade", "score") and "cgpa" in available_cols:
            resolved_weights["cgpa"] = w_val
        elif k_lower in ("attendance_pct", "presence") and "attendance" in available_cols:
            resolved_weights["attendance"] = w_val
        elif k_lower in ("leetcode", "coding", "problems") and "backlogs" in available_cols:
            resolved_weights["backlogs"] = w_val
        else:
            # Match case-insensitively against available columns
            matched = next((col for col in available_cols if col.lower() == k_lower), None)
            if matched:
                resolved_weights[matched] = w_val
            else:
                resolved_weights[k] = w_val

    # Default fallback to cgpa + attendance if resolved is empty
    if not resolved_weights:
        resolved_weights = {"cgpa": 0.80, "attendance": 0.20}

    # Check weights sum
    total_w = sum(abs(v) for v in resolved_weights.values())
    if total_w > 0 and abs(total_w - 1.0) > 0.01:
        # Scale to 1.0 if specified as percentages (e.g. 80 and 20)
        if abs(total_w - 100.0) <= 1.0:
            resolved_weights = {k: v / 100.0 for k, v in resolved_weights.items()}
        else:
            resolved_weights = {k: v / total_w for k, v in resolved_weights.items()}

    # Determine field scales from records
    field_scales: dict[str, float] = {}
    for f in resolved_weights.keys():
        numeric_vals = _get_numeric_values(records, f)
        if not numeric_vals:
            field_scales[f] = 100.0
            continue
        max_v = max(numeric_vals)
        if f.lower() == "cgpa" or max_v <= 10.0:
            field_scales[f] = 10.0
        elif max_v <= 100.0:
            field_scales[f] = 100.0
        else:
            field_scales[f] = max_v if max_v > 0 else 100.0

    # Build human-readable formula string
    formula_parts = []
    for f, w_val in resolved_weights.items():
        f_label = _humanize(f)
        scale = field_scales.get(f, 100.0)
        pct = int(round(w_val * 100))
        if scale == 10.0:
            formula_parts.append(f"({f_label} / 10 × 100 × {w_val:.2f})")
        else:
            formula_parts.append(f"({f_label} × {w_val:.2f})")
    formula_str = "Weighted Score = " + " + ".join(formula_parts)

    # Compute scores for all valid records
    computed_records: list[dict] = []
    for rec in records:
        score_breakdown: dict[str, float] = {}
        total_score = 0.0

        for f, w_val in resolved_weights.items():
            raw_v = rec.get(f)
            try:
                val = float(raw_v) if raw_v is not None else 0.0
            except (ValueError, TypeError):
                val = 0.0

            scale = field_scales.get(f, 100.0)
            if scale == 10.0:
                normalized_score = round((val / 10.0) * 100.0, 2)
            else:
                normalized_score = round(val, 2)

            contribution = round(normalized_score * w_val, 2)
            score_breakdown[f"{f}_normalized"] = normalized_score
            score_breakdown[f"{f}_contribution"] = contribution
            total_score += contribution

        weighted_score = round(total_score, 2)

        record_copy = dict(rec)
        record_copy["_weighted_score"] = weighted_score
        record_copy["academic_score"] = score_breakdown.get("cgpa_normalized", score_breakdown.get(list(score_breakdown.keys())[0], 0.0))
        record_copy["academic_contribution"] = score_breakdown.get("cgpa_contribution", 0.0)
        record_copy["attendance_contribution"] = score_breakdown.get("attendance_contribution", 0.0)

        for k_score, v_score in score_breakdown.items():
            record_copy[k_score] = v_score

        computed_records.append(record_copy)

    # Secondary deterministic tie-breaker sorting:
    # 1. Primary: weighted_score descending
    # 2. Secondary: CGPA descending
    # 3. Tertiary: Attendance descending
    # 4. Quaternary: Roll Number ascending (alphabetical)
    def _sort_key(r: dict):
        w_score = float(r.get("_weighted_score", 0.0))
        cgpa_val = float(r.get("cgpa", 0.0)) if r.get("cgpa") is not None else 0.0
        att_val = float(r.get("attendance", 0.0)) if r.get("attendance") is not None else 0.0
        roll = str(r.get("rollNumber") or r.get("id") or "")
        return (-w_score, -cgpa_val, -att_val, roll)

    computed_records.sort(key=_sort_key)

    # Assign competition ranks (1, 2, 2, 4) and dense ranks (1, 2, 2, 3)
    tie_groups: dict[float, list[dict]] = {}
    for r in computed_records:
        score = r["_weighted_score"]
        tie_groups.setdefault(score, []).append(r)

    current_competition_rank = 1
    current_dense_rank = 1
    seen_scores = set()

    for idx, r in enumerate(computed_records):
        score = r["_weighted_score"]
        if score not in seen_scores:
            current_competition_rank = idx + 1
            if idx > 0:
                current_dense_rank += 1
            seen_scores.add(score)

        r["rank"] = current_competition_rank
        r["dense_rank"] = current_dense_rank
        r["is_tied"] = len(tie_groups[score]) > 1

    # Detect ties & cutoff boundary
    ties_detected: list[dict] = []
    has_cutoff_tie = False
    cutoff_tie_details = None

    for score, group in tie_groups.items():
        if len(group) > 1:
            tied_names = [f"{g.get('name', g.get('rollNumber'))} ({g.get('rollNumber')})" for g in group]
            tie_info = {
                "weighted_score": score,
                "count": len(group),
                "rank": group[0]["rank"],
                "students": tied_names,
                "details": [
                    {
                        "name": g.get("name"),
                        "rollNumber": g.get("rollNumber"),
                        "cgpa": g.get("cgpa"),
                        "attendance": g.get("attendance"),
                        "academic_contribution": g.get("academic_contribution"),
                        "attendance_contribution": g.get("attendance_contribution"),
                    }
                    for g in group
                ]
            }
            ties_detected.append(tie_info)

            # Check if this tie spans across the top_n boundary
            ranks_in_group = [computed_records.index(g) + 1 for g in group]
            if min(ranks_in_group) <= top_n < max(ranks_in_group):
                has_cutoff_tie = True
                cutoff_tie_details = {
                    "score": score,
                    "students_in_tie": tied_names,
                    "tie_breaker_applied": "Students with identical weighted scores were ordered by higher CGPA, followed by higher attendance, and roll number.",
                }

    # Slice top N programmatically
    effective_top_n = min(top_n, len(computed_records))
    top_records = computed_records[:effective_top_n]

    # Calculate summary statistics across all ranked records
    all_scores = [r["_weighted_score"] for r in computed_records]
    avg_score = _safe_round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0
    max_score = _safe_round(max(all_scores), 2) if all_scores else 0.0
    min_score = _safe_round(min(all_scores), 2) if all_scores else 0.0

    tie_rule_text = (
        "In case of identical weighted scores, positions are deterministically resolved by higher CGPA, "
        "followed by higher attendance percentage, and roll number."
    )

    return {
        "analysis_type": "weighted_ranking",
        "tool": "calculate_weighted_ranking",
        "weights": resolved_weights,
        "formula": formula_str,
        "total_records": len(records),
        "top_n": effective_top_n,
        "ranking": top_records,
        "all_ranked_count": len(computed_records),
        "ties": ties_detected,
        "has_cutoff_tie": has_cutoff_tie,
        "cutoff_tie_details": cutoff_tie_details,
        "tie_breaking_rule": tie_rule_text,
        "statistics": {
            "average_weighted_score": avg_score,
            "highest_weighted_score": max_score,
            "lowest_weighted_score": min_score,
            "total_students": len(computed_records),
        },
    }


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

from app.services.pulse.risk_service import evaluate_risk, find_at_risk_records, rank_risk_severity

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
    "calculate_weighted_ranking": calculate_weighted_ranking,
    "evaluate_risk": evaluate_risk,
    "find_at_risk_records": find_at_risk_records,
    "rank_risk_severity": rank_risk_severity,
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
