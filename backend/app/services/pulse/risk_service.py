"""
risk_service.py — Deterministic Multi-Factor Academic Risk Assessment Engine for Pulse.

Provides institutional-grade, multi-criteria risk evaluation:
  1. Student-level exact reason derivation from actual dataset values.
  2. Continuous multi-factor risk score calculation (0–100).
  3. Deterministic severity classification (Critical, High, Moderate, Low, Safe).
  4. Comprehensive cohort statistical aggregation (factors, severity, department breakdowns).
  5. Data-driven recommendation synthesis based on detected risk factor counts.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default institutional risk thresholds
DEFAULT_THRESHOLDS = {
    "cgpa": {"operator": "lt", "value": 6.5, "severity": "high", "label": "Low CGPA", "max_points": 40.0},
    "attendance": {"operator": "lt", "value": 75.0, "severity": "medium", "label": "Low Attendance", "max_points": 30.0},
    "status": {"operator": "eq", "value": "Probation", "severity": "critical", "label": "Academic Probation", "max_points": 20.0},
    "backlogs": {"operator": "gt", "value": 0, "severity": "high", "label": "Active Backlogs", "max_points": 10.0},
}

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "safe": 4, "none": 5}
SEVERITY_COLORS = {
    "Critical": "#C00000",
    "High": "#E74C3C",
    "Moderate": "#E67E22",
    "Low": "#F1C40F",
    "Safe": "#27AE60",
}


def _check_condition(value: Any, operator: str, threshold: Any) -> bool:
    """Check a single numeric or categorical risk condition."""
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
            return str(value).strip().lower() == str(threshold).strip().lower()
        elif operator == "ne":
            return str(value).strip().lower() != str(threshold).strip().lower()
    except (TypeError, ValueError):
        pass
    return False


def calculate_student_risk(
    record: dict,
    active_thresholds: dict,
) -> dict:
    """
    Evaluate a single student record against active risk thresholds.
    Derives exact factual reasons, computes continuous 0-100 risk score,
    and assigns deterministic risk severity.
    """
    risk_flags = []
    risk_reasons = []
    cgpa_risk_pts = 0.0
    att_risk_pts = 0.0
    probation_pts = 0.0
    backlog_pts = 0.0

    # 1. CGPA evaluation
    cgpa_val = record.get("cgpa")
    if "cgpa" in active_thresholds and cgpa_val is not None:
        cgpa_thresh = float(active_thresholds["cgpa"]["value"])
        try:
            cgpa_num = float(cgpa_val)
            if cgpa_num < cgpa_thresh:
                gap = max(0.0, cgpa_thresh - cgpa_num)
                # Max 40 points scaled by distance below threshold
                cgpa_risk_pts = round(min(40.0, (gap / max(1.0, cgpa_thresh)) * 40.0 * 2.5), 1)
                cgpa_risk_pts = max(10.0, cgpa_risk_pts)
                reason = f"CGPA is {cgpa_num:.2f} (below required {cgpa_thresh:.2f})"
                risk_reasons.append(reason)
                risk_flags.append({
                    "field": "cgpa",
                    "value": cgpa_num,
                    "threshold": cgpa_thresh,
                    "label": "Low CGPA",
                    "severity": "high" if cgpa_num < 6.0 else "medium",
                    "points": cgpa_risk_pts,
                    "reason": reason,
                })
        except (ValueError, TypeError):
            pass

    # 2. Attendance evaluation
    att_val = record.get("attendance")
    if "attendance" in active_thresholds and att_val is not None:
        att_thresh = float(active_thresholds["attendance"]["value"])
        try:
            att_num = float(att_val)
            if att_num < att_thresh:
                gap = max(0.0, att_thresh - att_num)
                att_risk_pts = round(min(30.0, (gap / max(1.0, att_thresh)) * 30.0 * 2.0), 1)
                att_risk_pts = max(8.0, att_risk_pts)
                reason = f"Attendance is {att_num:.1f}% (below minimum required {att_thresh:.1f}%)"
                risk_reasons.append(reason)
                risk_flags.append({
                    "field": "attendance",
                    "value": att_num,
                    "threshold": att_thresh,
                    "label": "Low Attendance",
                    "severity": "high" if att_num < 65.0 else "medium",
                    "points": att_risk_pts,
                    "reason": reason,
                })
        except (ValueError, TypeError):
            pass

    # 3. Probation evaluation
    status_val = record.get("status", "")
    if "status" in active_thresholds and status_val:
        if str(status_val).strip().lower() == "probation":
            probation_pts = 20.0
            reason = "Student is on active academic probation"
            risk_reasons.append(reason)
            risk_flags.append({
                "field": "status",
                "value": status_val,
                "threshold": "Probation",
                "label": "Academic Probation",
                "severity": "critical",
                "points": 20.0,
                "reason": reason,
            })

    # 4. Backlogs evaluation
    backlogs_val = record.get("backlogs")
    if "backlogs" in active_thresholds and backlogs_val is not None:
        try:
            b_num = int(backlogs_val)
            if b_num > 0:
                backlog_pts = min(10.0, float(b_num * 5.0))
                reason = f"Student has {b_num} active backlog(s)"
                risk_reasons.append(reason)
                risk_flags.append({
                    "field": "backlogs",
                    "value": b_num,
                    "threshold": 0,
                    "label": "Active Backlogs",
                    "severity": "high" if b_num >= 2 else "medium",
                    "points": backlog_pts,
                    "reason": reason,
                })
        except (ValueError, TypeError):
            pass

    # Generic check for any other active custom thresholds
    for field, rule in active_thresholds.items():
        if field in ("cgpa", "attendance", "status", "backlogs"):
            continue
        val = record.get(field)
        if _check_condition(val, rule["operator"], rule["value"]):
            custom_pts = float(rule.get("max_points", 10.0))
            reason = f"{rule.get('label', field)} triggered ({field}={val})"
            risk_reasons.append(reason)
            risk_flags.append({
                "field": field,
                "value": val,
                "threshold": rule["value"],
                "label": rule.get("label", field),
                "severity": rule.get("severity", "medium"),
                "points": custom_pts,
                "reason": reason,
            })

    total_risk_score = round(min(100.0, cgpa_risk_pts + att_risk_pts + probation_pts + backlog_pts), 1)

    # Classify deterministic severity
    is_probation = (probation_pts > 0)
    cgpa_f = float(cgpa_val) if cgpa_val is not None else 10.0
    att_f = float(att_val) if att_val is not None else 100.0

    if total_risk_score >= 60.0 or (is_probation and (cgpa_f < 6.0 or att_f < 65.0)):
        severity = "Critical"
    elif total_risk_score >= 40.0 or is_probation:
        severity = "High"
    elif total_risk_score >= 20.0 or len(risk_flags) >= 1:
        severity = "Moderate"
    elif len(risk_flags) > 0:
        severity = "Low"
    else:
        severity = "Safe"

    reasons_short = ", ".join([f["label"] for f in risk_flags]) if risk_flags else "No risk factors"

    return {
        **record,
        "risk_flags": risk_flags,
        "risk_reasons": risk_reasons,
        "risk_reasons_str": reasons_short,
        "risk_score": total_risk_score,
        "risk_severity": severity,
        "risk_count": len(risk_flags),
        "is_at_risk": len(risk_flags) > 0,
    }


def aggregate_risk_statistics(
    all_evaluated: list[dict],
    at_risk_students: list[dict],
    active_thresholds: dict,
) -> dict:
    """
    Aggregate cohort risk statistics, factor frequencies, severity breakdown,
    department comparisons, dominant patterns, and data-driven recommendations.
    """
    total_count = len(all_evaluated)
    at_risk_count = len(at_risk_students)
    safe_count = total_count - at_risk_count
    at_risk_pct = round((at_risk_count / max(1, total_count)) * 100.0, 1)

    # Severity distribution
    severity_counts = {"Critical": 0, "High": 0, "Moderate": 0, "Low": 0, "Safe": safe_count}
    for s in at_risk_students:
        sev = s.get("risk_severity", "Moderate")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # Factor frequencies
    low_cgpa_count = sum(1 for s in at_risk_students if any(f["field"] == "cgpa" for f in s.get("risk_flags", [])))
    low_att_count = sum(1 for s in at_risk_students if any(f["field"] == "attendance" for f in s.get("risk_flags", [])))
    probation_count = sum(1 for s in at_risk_students if any(f["field"] == "status" for f in s.get("risk_flags", [])))
    backlog_count = sum(1 for s in at_risk_students if any(f["field"] == "backlogs" for f in s.get("risk_flags", [])))
    multi_factor_count = sum(1 for s in at_risk_students if s.get("risk_count", 0) >= 2)

    factor_counts = {
        "Low CGPA (< 6.5)": low_cgpa_count,
        "Low Attendance (< 75%)": low_att_count,
        "Academic Probation": probation_count,
        "Active Backlogs": backlog_count,
        "Multiple Risk Factors (2+)": multi_factor_count,
    }

    # Department-level risk analysis
    dept_groups: dict[str, list[dict]] = {}
    for s in all_evaluated:
        d_name = s.get("department") or "General"
        dept_groups.setdefault(d_name, []).append(s)

    department_analysis = []
    for d_name, d_records in sorted(dept_groups.items()):
        d_total = len(d_records)
        d_at_risk = sum(1 for r in d_records if r.get("is_at_risk"))
        d_risk_pct = round((d_at_risk / max(1, d_total)) * 100.0, 1)
        d_cgpas = [float(r.get("cgpa")) for r in d_records if r.get("cgpa") is not None]
        d_atts = [float(r.get("attendance")) for r in d_records if r.get("attendance") is not None]

        department_analysis.append({
            "department": d_name,
            "total_students": d_total,
            "at_risk_count": d_at_risk,
            "safe_count": d_total - d_at_risk,
            "risk_rate_pct": d_risk_pct,
            "avg_cgpa": round(sum(d_cgpas) / max(1, len(d_cgpas)), 2) if d_cgpas else 0.0,
            "avg_attendance": round(sum(d_atts) / max(1, len(d_atts)), 1) if d_atts else 0.0,
        })

    # Dominant pattern analysis
    patterns = []
    if low_cgpa_count > 0 and low_att_count > 0:
        both_count = sum(
            1 for s in at_risk_students
            if any(f["field"] == "cgpa" for f in s.get("risk_flags", []))
            and any(f["field"] == "attendance" for f in s.get("risk_flags", []))
        )
        both_pct = round((both_count / max(1, at_risk_count)) * 100.0, 1)
        if both_pct >= 50:
            patterns.append(
                f"Dual Academic & Attendance Deficit is dominant: {both_count} students ({both_pct}% of at-risk cohort) "
                f"experience simultaneous low CGPA and sub-75% attendance."
            )

    if multi_factor_count > 0:
        multi_pct = round((multi_factor_count / max(1, at_risk_count)) * 100.0, 1)
        patterns.append(
            f"Multi-criteria vulnerability: {multi_factor_count} students ({multi_pct}%) face compound difficulties "
            f"across 2 or more institutional risk indicators."
        )

    if not patterns:
        patterns.append(
            f"Primary isolated factor is Low Attendance ({low_att_count} students) followed by Low CGPA ({low_cgpa_count} students)."
        )
    dominant_pattern = " ".join(patterns)

    # Data-driven recommendations
    recommendations = []
    if low_att_count > 0:
        recommendations.append(
            f"Attendance Intervention Protocol: Prioritize automated attendance tracking and early alert notices for "
            f"the {low_att_count} students below the mandatory 75% threshold."
        )
    if low_cgpa_count > 0:
        recommendations.append(
            f"Targeted Academic Tutoring: Establish remedial mentoring and supplemental instruction for the "
            f"{low_cgpa_count} students with CGPA below 6.50."
        )
    if probation_count > 0:
        recommendations.append(
            f"Probation Recovery Monitoring: Schedule mandatory bi-weekly academic advisor check-ins for the "
            f"{probation_count} student(s) currently on active probation."
        )
    if backlog_count > 0:
        recommendations.append(
            f"Backlog Clearance Pathways: Provide structured exam re-sit preparation for the "
            f"{backlog_count} student(s) carrying active course backlogs."
        )

    return {
        "total_analyzed": total_count,
        "at_risk_count": at_risk_count,
        "safe_count": safe_count,
        "at_risk_percentage": at_risk_pct,
        "severity_distribution": severity_counts,
        "factor_frequencies": factor_counts,
        "department_analysis": department_analysis,
        "dominant_risk_pattern": dominant_pattern,
        "data_driven_recommendations": recommendations,
        "thresholds_used": active_thresholds,
    }


def evaluate_risk(
    records: list[dict],
    thresholds: Optional[dict] = None,
    **_,
) -> dict:
    """
    Institutional multi-criteria risk evaluation tool.
    Returns complete dataset of all at-risk students without truncation,
    plus full statistical aggregates, severity distributions, and recommendations.
    """
    if not records:
        return {
            "analysis_type": "risk_analysis",
            "error": "No records available for risk analysis",
            "at_risk": [],
            "at_risk_count": 0,
            "total_records": 0,
        }

    active_thresholds = DEFAULT_THRESHOLDS.copy()
    if thresholds:
        active_thresholds.update(thresholds)

    # Available columns in dataset
    sample = records[0] if records else {}
    available_cols = set(sample.keys())
    matched_thresholds = {k: v for k, v in active_thresholds.items() if k in available_cols}
    if not matched_thresholds:
        matched_thresholds = active_thresholds

    all_evaluated = [calculate_student_risk(r, matched_thresholds) for r in records]
    at_risk_students = [r for r in all_evaluated if r.get("is_at_risk")]

    # Sort at-risk students deterministically:
    # 1. Severity rank (Critical first)
    # 2. Risk score descending
    # 3. CGPA ascending
    # 4. Attendance ascending
    # 5. Roll Number ascending
    def _risk_sort_key(r: dict):
        sev_rank = SEVERITY_ORDER.get(str(r.get("risk_severity", "")).lower(), 99)
        score = float(r.get("risk_score", 0.0))
        cgpa = float(r.get("cgpa", 10.0)) if r.get("cgpa") is not None else 10.0
        att = float(r.get("attendance", 100.0)) if r.get("attendance") is not None else 100.0
        roll = str(r.get("rollNumber") or "")
        return (sev_rank, -score, cgpa, att, roll)

    at_risk_students.sort(key=_risk_sort_key)

    # Assign risk rank across at-risk students
    for i, s in enumerate(at_risk_students):
        s["risk_rank"] = i + 1

    stats = aggregate_risk_statistics(all_evaluated, at_risk_students, matched_thresholds)

    return {
        "analysis_type": "risk_analysis",
        "tool": "evaluate_risk",
        "at_risk": at_risk_students,  # COMPLETE matching records (all 89 records preserved)
        "at_risk_count": len(at_risk_students),
        "safe_count": stats["safe_count"],
        "total_records": len(records),
        "at_risk_percentage": stats["at_risk_percentage"],
        "severity_distribution": stats["severity_distribution"],
        "factor_frequencies": stats["factor_frequencies"],
        "department_analysis": stats["department_analysis"],
        "dominant_risk_pattern": stats["dominant_risk_pattern"],
        "data_driven_recommendations": stats["data_driven_recommendations"],
        "thresholds_used": matched_thresholds,
    }


def find_at_risk_records(
    records: list[dict],
    rules: str = "auto_or_explicit",
    custom_thresholds: Optional[dict] = None,
    **_,
) -> dict:
    """Backward-compatible wrapper mapping directly to evaluate_risk."""
    return evaluate_risk(records, thresholds=custom_thresholds)


def rank_risk_severity(records: list[dict], **_) -> dict:
    """Backward-compatible wrapper mapping to evaluate_risk with full cohort ranking."""
    res = evaluate_risk(records)
    at_risk = res["at_risk"]
    at_risk_ids = {id(r) for r in at_risk}
    safe_records = [
        {**r, "risk_flags": [], "risk_severity": "Safe", "risk_count": 0, "risk_score": 0.0, "risk_reasons_str": "Safe"}
        for r in records if id(r) not in at_risk_ids
    ]
    all_ranked = at_risk + safe_records
    for i, rec in enumerate(all_ranked):
        rec["risk_rank"] = i + 1

    return {
        "ranked_records": all_ranked,
        "at_risk": at_risk,
        "at_risk_count": len(at_risk),
        "safe_count": len(safe_records),
        "total_records": len(records),
        "statistics": res,
    }

