"""
dataset_profiler.py — Dynamic dataset inspection for Pulse.

Inspects a list of record dicts and produces a structured profile describing:
  - Available column names
  - Inferred data type per column (numeric, categorical, boolean, unknown)
  - Non-null count and missing-value count per column
  - Summary statistics for numeric columns (min, max, mean)
  - A compact text summary for feeding to the LLM planner
  - A representative data sample (capped) safe to send to the LLM

Pulse uses this profile so it never assumes fixed column names.
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

# Max records to include in the LLM-safe sample
_LLM_SAMPLE_SIZE = 10


def _infer_type(samples: list[Any]) -> str:
    """Infer broad type from a list of sample values."""
    non_null = [v for v in samples if v is not None and v != ""]
    if not non_null:
        return "unknown"
    if all(isinstance(v, bool) for v in non_null):
        return "boolean"
    if all(isinstance(v, (int, float)) for v in non_null):
        return "numeric"
    # Check if string values look like numbers
    numeric_strings = sum(
        1 for v in non_null[:20]
        if _can_be_float(v)
    )
    if numeric_strings == len(non_null[:20]) and len(non_null) > 0:
        return "numeric"
    return "categorical"


def _can_be_float(v: Any) -> bool:
    try:
        float(str(v))
        return True
    except (ValueError, TypeError):
        return False


def _numeric_stats(values: list[float]) -> dict:
    """Compute basic summary stats for a numeric column."""
    if not values:
        return {}
    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n if n > 1 else 0.0
    return {
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "mean": round(mean, 4),
        "std_dev": round(math.sqrt(variance), 4),
        "count": n,
    }


def profile_dataset(records: list[dict]) -> dict:
    """
    Analyse a list of record dicts and return a comprehensive structured profile.

    Returns:
        {
            "record_count": int,
            "columns": {
                "cgpa": {
                    "type": "numeric",
                    "non_null": 42,
                    "missing": 0,
                    "stats": {"min": 5.4, "max": 9.2, "mean": 7.5, "std_dev": 1.1, "count": 42}
                },
                "department": {
                    "type": "categorical",
                    "non_null": 42,
                    "missing": 0,
                    "unique_values": ["CSE", "ECE", "ME"]
                },
                ...
            },
            "numeric_columns": ["cgpa", "marks", "attendance"],
            "categorical_columns": ["department", "status", "name"],
            "column_list": ["name", "department", "marks", "attendance", "cgpa"],
            "summary_text": "42 records with columns: cgpa (numeric), ...",
            "llm_sample": [ ...up to 10 records... ]
        }
    """
    if not records:
        return {
            "record_count": 0,
            "columns": {},
            "column_list": [],
            "numeric_columns": [],
            "categorical_columns": [],
            "summary_text": "Empty dataset — no records provided.",
            "llm_sample": [],
        }

    # Collect all unique keys across all records (preserve order, skip "id")
    all_keys: list[str] = []
    seen: set[str] = set()
    for rec in records:
        for k in rec.keys():
            if k not in seen and k != "id":
                seen.add(k)
                all_keys.append(k)

    columns: dict[str, dict] = {}
    numeric_cols: list[str] = []
    categorical_cols: list[str] = []
    n = len(records)

    for key in all_keys:
        raw_samples = [rec.get(key) for rec in records]
        non_null_count = sum(1 for v in raw_samples if v is not None and v != "")
        missing_count = n - non_null_count
        col_type = _infer_type(raw_samples)

        col_info: dict = {
            "type": col_type,
            "non_null": non_null_count,
            "missing": missing_count,
        }

        if col_type == "numeric":
            numeric_vals = [float(v) for v in raw_samples if v is not None and _can_be_float(v)]
            col_info["stats"] = _numeric_stats(numeric_vals)
            numeric_cols.append(key)
        elif col_type == "categorical":
            unique_vals = list({str(v) for v in raw_samples if v is not None and v != ""})[:20]
            col_info["unique_values"] = sorted(unique_vals)
            categorical_cols.append(key)

        columns[key] = col_info

    # Build a concise text summary for the LLM
    col_descriptions = ", ".join(
        f"{k} ({v['type']})" for k, v in columns.items()
    )
    missing_info = ", ".join(
        f"{k}: {v['missing']} missing"
        for k, v in columns.items()
        if v["missing"] > 0
    )
    summary_parts = [f"{n} records with columns: {col_descriptions}."]
    if missing_info:
        summary_parts.append(f"Missing values — {missing_info}.")

    # LLM-safe sample (evenly spaced, capped at _LLM_SAMPLE_SIZE)
    if n <= _LLM_SAMPLE_SIZE:
        llm_sample = records[:]
    else:
        step = n // _LLM_SAMPLE_SIZE
        llm_sample = [records[i * step] for i in range(_LLM_SAMPLE_SIZE)]

    return {
        "record_count": n,
        "columns": columns,
        "column_list": all_keys,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "summary_text": " ".join(summary_parts),
        "llm_sample": llm_sample,
    }
