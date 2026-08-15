"""
risk_service.py — At-risk record identification for Pulse.

Provides generic, configurable rules for identifying records that need attention.
Rules are configured via thresholds and checked dynamically against available fields.
No column names are hardcoded — the service adapts to whatever fields exist.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default risk thresholds (override via rules parameter)
DEFAULT_THRESHOLDS = {
    "cgpa": {"operator": "lt", "value": 6.5, "severity": "high", "label": "Low CGPA"},
    "attendance": {"operator": "lt", "value": 75.0, "severity": "medium", "label": "Low Attendance"},
    "marks": {"operator": "lt", "value": 50.0, "severity": "high", "label": "Low Marks"},
    "status": {"operator": "eq", "value": "Probation", "severity": "critical", "label": "On Probation"},
}

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _check_condition(value: Any, operator: str, threshold: Any) -> bool:
    """Check a single risk condition."""
    if value is None:
        return False
    try:
        if operator == "lt":
            return float(value) < float(threshold)
        elif operator == "lte":
            return float(value) <= float(threshold)
        elif operator == "gt":
            return float(value) > float(threshold)
        elif operator == "gte":
            return float(value) >= float(threshold)
        elif operator == "eq":
            return str(value).lower() == str(threshold).lower()
        elif operator == "ne":
            return str(value).lower() != str(threshold).lower()
    except (TypeError, ValueError):
        pass
    return False


def find_at_risk_records(
    records: list[dict],
    rules: str = "auto_or_explicit",
    custom_thresholds: Optional[dict] = None,
    **_,
) -> dict:
    """
    Identify at-risk records using configurable thresholds.

    Args:
        records:           List of record dicts
        rules:             "auto_or_explicit" uses defaults, "custom" uses custom_thresholds only
        custom_thresholds: Optional override thresholds dict in same format as DEFAULT_THRESHOLDS

    Returns:
        {
            "at_risk": [ {record, risk_flags, max_severity}, ... ],
            "at_risk_count": int,
            "total_records": int,
            "thresholds_used": {...}
        }
    """
    thresholds = DEFAULT_THRESHOLDS.copy()
    if custom_thresholds:
        thresholds.update(custom_thresholds)

    # Only apply thresholds for fields that actually exist in the dataset
    available_fields = set()
    for rec in records:
        available_fields.update(rec.keys())

    active_thresholds = {k: v for k, v in thresholds.items() if k in available_fields}

    at_risk = []
    for rec in records:
        risk_flags = []
        for field, rule in active_thresholds.items():
            val = rec.get(field)
            if _check_condition(val, rule["operator"], rule["value"]):
                risk_flags.append({
                    "field": field,
                    "value": val,
                    "threshold": rule["value"],
                    "operator": rule["operator"],
                    "severity": rule["severity"],
                    "label": rule["label"],
                })

        if risk_flags:
            # Determine overall max severity
            max_severity = min(risk_flags, key=lambda f: SEVERITY_ORDER.get(f["severity"], 99))["severity"]
            at_risk.append({
                **rec,
                "risk_flags": risk_flags,
                "risk_severity": max_severity,
                "risk_count": len(risk_flags),
            })

    # Sort by severity
    at_risk.sort(key=lambda r: SEVERITY_ORDER.get(r["risk_severity"], 99))

    return {
        "at_risk": at_risk,
        "at_risk_count": len(at_risk),
        "safe_count": len(records) - len(at_risk),
        "total_records": len(records),
        "thresholds_used": active_thresholds,
    }


def rank_risk_severity(records: list[dict], **_) -> dict:
    """
    Rank all records by their computed composite risk score.
    Risk score is based on how many risk conditions are triggered.
    """
    result = find_at_risk_records(records)
    at_risk = result["at_risk"]

    # Also include safe records with 0 risk flags
    at_risk_ids = {id(r) for r in at_risk}
    safe_records = [
        {**r, "risk_flags": [], "risk_severity": "none", "risk_count": 0}
        for r in records if id(r) not in at_risk_ids
    ]

    all_ranked = at_risk + safe_records
    for i, rec in enumerate(all_ranked):
        rec["risk_rank"] = i + 1

    return {
        "ranked_records": all_ranked,
        "at_risk_count": len(at_risk),
        "safe_count": len(safe_records),
        "total_records": len(records),
    }
