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

        elif tool in ("find_at_risk_records",) and "at_risk_count" in result:
            findings.append(
                f"At-risk records identified: {result['at_risk_count']} out of "
                f"{result.get('total_records', '?')}"
            )

        elif tool == "count_records" and "count" in result:
            findings.append(f"Total records: {result['count']}")

        elif tool in ("top_n_records", "bottom_n_records"):
            field = result.get("field", "field")
            n = result.get("n", "?")
            label = "Top" if tool == "top_n_records" else "Bottom"
            findings.append(f"{label} {n} records by {field}: {len(result.get('top_records') or result.get('bottom_records', []))} returned")

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

        if tool == "group_analysis" and "groups" in result:
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

        elif tool == "find_at_risk_records" and "at_risk" in result:
            tables["at_risk_students"] = result["at_risk"]

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

    Chart types:
      - bar: group labels + values
      - scatter: x/y pairs
      - histogram: bin labels + counts
      - pie: category + count
    """
    chart_data: dict[str, dict] = {}

    for entry in raw_results:
        tool = entry.get("tool", "")
        result = entry.get("result", {})

        if "error" in result:
            continue

        if tool in ("group_analysis", "compare_groups") and "groups" in result:
            grp_by = result.get("group_by", "group")
            # Find first numeric field with average data
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

        elif tool == "calculate_correlation" and result.get("correlation") is not None:
            chart_data["correlation_info"] = {
                "type": "scatter_meta",
                "field1": result.get("field1"),
                "field2": result.get("field2"),
                "correlation": result.get("correlation"),
                "direction": result.get("direction"),
                "strength": result.get("strength"),
            }

        elif tool == "find_at_risk_records" and "at_risk_count" in result:
            total = result.get("total_records", 1)
            at_risk = result.get("at_risk_count", 0)
            chart_data["risk_pie"] = {
                "type": "pie",
                "title": "At-Risk vs Safe Students",
                "labels": ["At Risk", "Safe"],
                "values": [at_risk, total - at_risk],
            }

    return chart_data


def _infer_analysis_type(plan: dict) -> str:
    """Derive a short human-readable analysis type from the plan."""
    goal = plan.get("analysis_goal", "general_analysis").lower()
    tools_used = [op.get("tool", "") for op in plan.get("operations", [])]

    if "compare" in goal or "compare_groups" in tools_used:
        return "group_comparison"
    if "risk" in goal or "find_at_risk_records" in tools_used:
        return "risk_analysis"
    if "correlation" in goal or "calculate_correlation" in tools_used:
        return "correlation_analysis"
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

    Args:
        records:          Original input records
        dataset_profile:  Profile from dataset_profiler
        plan:             Validated execution plan
        raw_results:      List of {tool, parameters, result} dicts
        insight:          Human-readable insight string (LLM or deterministic)
        legacy_metrics:   OrchestrationMetrics model instance (for backward compat)

    Returns:
        Complete Pulse result dict ready for Scribe consumption.
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

    return {
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
