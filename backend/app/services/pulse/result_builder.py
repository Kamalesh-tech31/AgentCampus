"""
result_builder.py — Builds the structured Pulse analytics output contract.

This module constructs the final result dict that Pulse returns.
It is designed so Scribe can easily consume it for Text, Excel, PDF, and PPT output.

Output contract shape:
{
    "summary": str,                 # Short human-readable analytics summary
    "analysis_type": str,           # e.g. "group_comparison", "risk_analysis"
    "metrics": dict,                # OrchestrationMetrics (legacy compat)
    "findings": list[str],          # Key factual findings as bullet strings
    "insights": list[str],          # LLM-generated or deterministic insights
    "tables": dict,                 # Named tables ready for Scribe rendering
    "chart_data": dict,             # Data Scribe can use to draw charts
    "records_analyzed": int,        # Total input record count
    "columns_analyzed": list[str],  # Column names that were examined
    "analysis_plan": dict,          # The execution plan used
    "raw_results": list[dict],      # Individual tool outputs (for debugging)
}
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _extract_findings(raw_results: list[dict], dataset_profile: dict) -> list[str]:
    """Derive concise factual findings from raw tool results."""
    findings: list[str] = []

    for entry in raw_results:
        tool = entry.get("tool", "")
        result = entry.get("result", {})

        if "error" in result:
            continue  # Skip errored tools silently

        if tool == "calculate_average" and result.get("average") is not None:
            findings.append(
                f"Average {result['field']}: {result['average']} "
                f"(from {result.get('count', '?')} records)"
            )

        elif tool == "calculate_min" and result.get("min") is not None:
            findings.append(f"Minimum {result['field']}: {result['min']}")

        elif tool == "calculate_max" and result.get("max") is not None:
            findings.append(f"Maximum {result['field']}: {result['max']}")

        elif tool == "calculate_median" and result.get("median") is not None:
            findings.append(f"Median {result['field']}: {result['median']}")

        elif tool == "calculate_standard_deviation" and result.get("std_dev") is not None:
            findings.append(
                f"Standard deviation of {result['field']}: {result['std_dev']} "
                f"(mean: {result.get('mean', '?')})"
            )

        elif tool == "calculate_correlation" and result.get("correlation") is not None:
            findings.append(
                f"Correlation between {result['field1']} and {result['field2']}: "
                f"{result['correlation']} ({result.get('strength', '')} {result.get('direction', '')})"
            )

        elif tool in ("group_analysis", "compare_groups") and "groups" in result:
            grp_by = result.get("group_by", "group")
            for grp_name, grp_data in result["groups"].items():
                cnt = grp_data.get("count", "?")
                findings.append(f"Group '{grp_name}' ({grp_by}): {cnt} records")

        elif tool in ("evaluate_risk", "find_at_risk_records") and "at_risk_count" in result:
            total = result.get("total_records", dataset_profile.get("record_count", 0))
            at_risk = result.get("at_risk_count", 0)
            pct = result.get("at_risk_percentage", round((at_risk / max(1, total)) * 100.0, 1))
            findings.append(f"At-risk students identified: {at_risk} out of {total} ({pct}% of cohort)")
            if result.get("dominant_risk_pattern"):
                findings.append(f"Dominant Pattern: {result['dominant_risk_pattern']}")
            if result.get("severity_distribution"):
                sev = result["severity_distribution"]
                crit_count = sev.get("Critical", 0)
                high_count = sev.get("High", 0)
                if crit_count > 0 or high_count > 0:
                    findings.append(f"High Severity Breakdown: {crit_count} Critical, {high_count} High priority students")

        elif tool == "calculate_correlation" and result.get("correlation") is not None:
            f1 = result.get("field1_label", result.get("field1", "Field 1"))
            f2 = result.get("field2_label", result.get("field2", "Field 2"))
            r_val = result.get("correlation", 0.0)
            r_sq = result.get("r_squared", round(r_val ** 2, 4))
            strength = result.get("strength", "")
            direction = result.get("direction", "")
            findings.append(f"Correlation between {f1} and {f2}: r = {r_val} ({strength} {direction}, R² = {r_sq})")
            if result.get("regression", {}).get("formula"):
                findings.append(f"Fitted Model: {result['regression']['formula']}")
            findings.append("Note: Statistical correlation indicates association, not causation.")

        elif tool == "count_records" and "count" in result:
            findings.append(f"Total records: {result['count']}")

        elif tool in ("top_n_records", "bottom_n_records"):
            field = result.get("field", "field")
            n = result.get("n", "?")
            label = "Top" if tool == "top_n_records" else "Bottom"
            findings.append(f"{label} {n} records by {field}: {len(result.get('top_records') or result.get('bottom_records', []))} returned")

        elif tool == "calculate_weighted_ranking" and "ranking" in result:
            top_n = result.get("top_n", 10)
            formula = result.get("formula", "")
            stats = result.get("statistics", {})
            findings.append(f"Ranked top {top_n} students using {formula}")
            if stats.get("highest_weighted_score") is not None:
                findings.append(f"Highest weighted score: {stats['highest_weighted_score']:.2f}, Average: {stats.get('average_weighted_score', 0):.2f}")
            if result.get("ties"):
                findings.append(f"Ties detected: {len(result['ties'])} score collision(s) handled via deterministic tie-breaking.")

        elif tool == "detect_outliers" and "outlier_count" in result:
            findings.append(
                f"Outliers in {result.get('field', '?')} ({result.get('method', 'iqr')} method): "
                f"{result['outlier_count']} detected"
            )

    return findings


def _build_tables(raw_results: list[dict]) -> dict:
    """
    Extract named tables from tool results for Scribe to render.
    Tables are lists of dicts (row-oriented).
    """
    tables: dict[str, list[dict]] = {}

    for entry in raw_results:
        tool = entry.get("tool", "")
        result = entry.get("result", {})

        if "error" in result:
            continue

        if tool in ("evaluate_risk", "find_at_risk_records") and "at_risk" in result:
            # Build complete at-risk students table with explicit student-level reasons
            raw_at_risk = result["at_risk"]
            formatted_risk = []
            for i, r in enumerate(raw_at_risk):
                formatted_risk.append({
                    "risk_rank": r.get("risk_rank", i + 1),
                    "rollNumber": r.get("rollNumber", ""),
                    "name": r.get("name", ""),
                    "department": r.get("department", ""),
                    "cgpa": r.get("cgpa"),
                    "attendance": r.get("attendance"),
                    "status": r.get("status", ""),
                    "backlogs": r.get("backlogs", 0),
                    "risk_score": r.get("risk_score", 0.0),
                    "risk_severity": r.get("risk_severity", "Moderate"),
                    "risk_reasons_str": r.get("risk_reasons_str", "Low academic indicators"),
                })
            tables["at_risk_students"] = formatted_risk

            # Add department risk summary table if available
            if result.get("department_analysis"):
                tables["department_risk"] = result["department_analysis"]

            # Add severity summary table if available
            if result.get("severity_distribution"):
                sev_rows = [
                    {"severity": k, "count": v, "percentage": f"{round((v / max(1, result.get('total_records', 100))) * 100, 1)}%"}
                    for k, v in result["severity_distribution"].items()
                ]
                tables["severity_summary"] = sev_rows

        elif tool == "calculate_weighted_ranking" and "ranking" in result:
            # Build clean top performers table with contribution columns
            top_recs = result["ranking"]
            formatted_top = []
            for r in top_recs:
                row = {
                    "rank": r.get("rank"),
                    "name": r.get("name"),
                    "rollNumber": r.get("rollNumber"),
                    "department": r.get("department"),
                    "cgpa": r.get("cgpa"),
                    "attendance": r.get("attendance"),
                    "academic_score": r.get("academic_score"),
                    "academic_contribution": r.get("academic_contribution"),
                    "attendance_contribution": r.get("attendance_contribution"),
                    "weighted_score": r.get("_weighted_score"),
                }
                if r.get("is_tied"):
                    row["is_tied"] = True
                formatted_top.append(row)
            tables["top_performers"] = formatted_top

        elif tool == "group_analysis" and "groups" in result:
            grp_by = result.get("group_by", "group")
            rows = []
            for grp_name, grp_data in result["groups"].items():
                row = {grp_by: grp_name, "count": grp_data.get("count", 0)}
                for field, stats in grp_data.items():
                    if field == "count":
                        continue
                    if isinstance(stats, dict):
                        row[f"{field}_avg"] = stats.get("average")
                        row[f"{field}_min"] = stats.get("min")
                        row[f"{field}_max"] = stats.get("max")
                rows.append(row)
            tables["group_summary"] = rows

        elif tool == "top_n_records" and "top_records" in result:
            tables["top_performers"] = result["top_records"]

        elif tool == "bottom_n_records" and "bottom_records" in result:
            tables["bottom_performers"] = result["bottom_records"]

        elif tool == "rank_records" and "ranked_records" in result:
            tables["ranked_records"] = result["ranked_records"]

        elif tool == "filter_records" and "filtered_records" in result:
            tables["filtered_records"] = result["filtered_records"]

    return tables


def _build_chart_data(raw_results: list[dict], dataset_profile: dict) -> dict:
    """
    Extract chart-ready data from tool results.
    Scribe decides how to render this.
    """
    chart_data: dict[str, dict] = {}

    for entry in raw_results:
        tool = entry.get("tool", "")
        result = entry.get("result", {})

        if "error" in result:
            continue

        if tool in ("evaluate_risk", "find_at_risk_records") and "at_risk_count" in result:
            # 1. Severity pie/donut chart
            sev_dist = result.get("severity_distribution", {})
            if sev_dist:
                chart_data["risk_severity_pie"] = {
                    "type": "pie",
                    "title": "Cohort Risk Severity Breakdown",
                    "labels": list(sev_dist.keys()),
                    "values": list(sev_dist.values()),
                }
            else:
                total = result.get("total_records", 1)
                at_risk = result.get("at_risk_count", 0)
                chart_data["risk_pie"] = {
                    "type": "pie",
                    "title": "At-Risk vs Safe Students",
                    "labels": ["At Risk", "Safe"],
                    "values": [at_risk, total - at_risk],
                }

            # 2. Risk factor frequency horizontal bar chart
            factor_freqs = result.get("factor_frequencies", {})
            if factor_freqs:
                chart_data["risk_factors_bar"] = {
                    "type": "bar",
                    "title": "Risk Factor Prevalence Across Cohort",
                    "x_label": "Risk Indicator",
                    "y_label": "Number of Students",
                    "labels": list(factor_freqs.keys()),
                    "values": list(factor_freqs.values()),
                }

            # 3. Department risk comparison bar chart
            dept_analysis = result.get("department_analysis", [])
            if dept_analysis:
                chart_data["department_risk_bar"] = {
                    "type": "bar",
                    "title": "At-Risk Students by Department",
                    "x_label": "Department",
                    "y_label": "At-Risk Count",
                    "labels": [d["department"] for d in dept_analysis],
                    "values": [d["at_risk_count"] for d in dept_analysis],
                }

        elif tool == "calculate_correlation" and result.get("correlation") is not None:
            chart_data["scatter_plot"] = {
                "type": "scatter",
                "title": f"{result.get('field2_label', result.get('field2'))} vs {result.get('field1_label', result.get('field1'))} Correlation",
                "x_label": result.get("field1_label", result.get("field1")),
                "y_label": result.get("field2_label", result.get("field2")),
                "correlation": result.get("correlation"),
                "r_squared": result.get("r_squared"),
                "regression": result.get("regression", {}),
                "points": result.get("scatter_points", []),
            }

        elif tool == "calculate_weighted_ranking" and "ranking" in result:
            top_recs = result["ranking"]
            chart_data["ranking_bar"] = {
                "type": "bar",
                "title": f"Top {len(top_recs)} Students by Weighted Score",
                "x_label": "Student",
                "y_label": "Weighted Score",
                "labels": [f"{r.get('name', r.get('rollNumber'))}" for r in top_recs],
                "values": [r.get("_weighted_score", 0.0) for r in top_recs],
                "ranks": [r.get("rank") for r in top_recs],
            }

        elif tool in ("group_analysis", "compare_groups") and "groups" in result:
            grp_by = result.get("group_by", "group")
            labels = list(result["groups"].keys())
            for grp_name, grp_data in result["groups"].items():
                for field, stats in grp_data.items():
                    if field == "count":
                        continue
                    if isinstance(stats, dict) and "average" in stats:
                        chart_data["group_bar"] = {
                            "type": "bar",
                            "title": f"{field.title()} by {grp_by.title()}",
                            "x_label": grp_by,
                            "y_label": field,
                            "labels": labels,
                            "values": [
                                result["groups"][g].get(field, {}).get("average")
                                for g in labels
                            ],
                        }
                        break
                if "group_bar" in chart_data:
                    break

        elif tool == "calculate_distribution" and "distribution" in result:
            dist = result["distribution"]
            chart_data["distribution_chart"] = {
                "type": "bar" if result.get("type") == "numeric" else "pie",
                "title": f"{result.get('field', 'Field').title()} Distribution",
                "labels": list(dist.keys()),
                "values": list(dist.values()),
            }

    return chart_data


def _infer_analysis_type(plan: dict) -> str:
    """Derive a short human-readable analysis type from the plan."""
    goal = plan.get("analysis_goal", "general_analysis").lower()
    tools_used = [op.get("tool", "") for op in plan.get("operations", [])]

    if "evaluate_risk" in tools_used or "find_at_risk_records" in tools_used or "risk" in goal:
        return "risk_analysis"
    if "calculate_correlation" in tools_used or "correlation" in goal or "relationship" in goal:
        return "correlation_analysis"
    if "calculate_weighted_ranking" in tools_used or "weighted" in goal:
        return "weighted_ranking"
    if "compare" in goal or "compare_groups" in tools_used:
        return "group_comparison"
    if "trend" in goal:
        return "trend_analysis"
    if "rank" in goal or "top_n_records" in tools_used or "bottom_n_records" in tools_used:
        return "ranking_analysis"
    if "distribution" in goal or "calculate_distribution" in tools_used:
        return "distribution_analysis"
    if plan.get("strategy") == "llm_reasoning":
        return "open_ended_analysis"
    return "general_summary"


def build_pulse_result(
    records: list[dict],
    dataset_profile: dict,
    plan: dict,
    raw_results: list[dict],
    insight: str,
    legacy_metrics: Any,
) -> dict:
    """
    Build the complete Pulse output contract.
    """
    findings = _extract_findings(raw_results, dataset_profile)
    tables = _build_tables(raw_results)
    chart_data = _build_chart_data(raw_results, dataset_profile)
    analysis_type = _infer_analysis_type(plan)

    # Build a concise summary (1–2 sentences)
    n = dataset_profile.get("record_count", len(records))
    summary_parts = [f"Analysed {n} records across {len(dataset_profile.get('column_list', []))} columns."]
    if findings:
        summary_parts.append(findings[0])
    summary = " ".join(summary_parts)

    # Extract metadata payloads if available
    extra_meta = {}
    for entry in raw_results:
        tool_name = entry.get("tool")
        res_dict = entry.get("result", {})
        if not isinstance(res_dict, dict):
            continue

        if tool_name == "calculate_weighted_ranking":
            extra_meta.update({
                "formula": res_dict.get("formula"),
                "weights": res_dict.get("weights"),
                "top_n": res_dict.get("top_n"),
                "ties": res_dict.get("ties", []),
                "has_cutoff_tie": res_dict.get("has_cutoff_tie", False),
                "cutoff_tie_details": res_dict.get("cutoff_tie_details"),
                "tie_breaking_rule": res_dict.get("tie_breaking_rule"),
                "statistics": res_dict.get("statistics", {}),
                "ranking": res_dict.get("ranking", []),
            })

        elif tool_name in ("evaluate_risk", "find_at_risk_records"):
            extra_meta.update({
                "at_risk": res_dict.get("at_risk", []),  # All matching records preserved
                "at_risk_count": res_dict.get("at_risk_count"),
                "safe_count": res_dict.get("safe_count"),
                "at_risk_percentage": res_dict.get("at_risk_percentage"),
                "severity_distribution": res_dict.get("severity_distribution", {}),
                "factor_frequencies": res_dict.get("factor_frequencies", {}),
                "department_analysis": res_dict.get("department_analysis", []),
                "dominant_risk_pattern": res_dict.get("dominant_risk_pattern"),
                "data_driven_recommendations": res_dict.get("data_driven_recommendations", []),
                "thresholds_used": res_dict.get("thresholds_used", {}),
            })

        elif tool_name == "calculate_correlation":
            extra_meta.update({
                "field1": res_dict.get("field1"),
                "field2": res_dict.get("field2"),
                "field1_label": res_dict.get("field1_label"),
                "field2_label": res_dict.get("field2_label"),
                "correlation": res_dict.get("correlation"),
                "r_squared": res_dict.get("r_squared"),
                "strength": res_dict.get("strength"),
                "direction": res_dict.get("direction"),
                "regression": res_dict.get("regression", {}),
                "interpretation": res_dict.get("interpretation"),
                "scatter_points": res_dict.get("scatter_points", []),
            })

    result_contract = {
        # ── Core contract ──────────────────────────────────────────────────────
        "summary": summary,
        "analysis_type": analysis_type,

        # ── Legacy contract (backward compat with Scribe + existing tests) ────
        "metrics": legacy_metrics.model_dump(by_alias=True),
        "insight": insight,

        # ── Structured findings and insights ──────────────────────────────────
        "findings": findings,
        "insights": [insight] if insight else [],

        # ── Tabular data for Scribe ────────────────────────────────────────────
        "tables": tables,

        # ── Chart data for Scribe ─────────────────────────────────────────────
        "chart_data": chart_data,

        # ── Metadata ──────────────────────────────────────────────────────────
        "records_analyzed": n,
        "columns_analyzed": dataset_profile.get("column_list", []),

        # ── Execution tracing ─────────────────────────────────────────────────
        "analysis_plan": plan,
        "raw_results": raw_results,
    }

    if extra_meta:
        result_contract.update(extra_meta)

    return result_contract
