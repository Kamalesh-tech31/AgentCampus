"""
llm_interpreter.py — LLM-powered result interpreter for Pulse.

Takes raw calculation results from analytics_tools and the user's original
request, and synthesises a human-readable, contextual insight string.

Uses PULSE_GROQ_API_KEY and PULSE_GROQ_MODEL independently from Scribe.

Falls back to a deterministic summary if the LLM is unavailable.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _build_interpretation_prompt(user_request: str, raw_results: list[dict], dataset_summary: str) -> str:
    # Sanitize and compact raw_results to stay well within TPM/token limits (e.g. max 12,000 TPM)
    compact_results = []
    for entry in raw_results:
        # entry can be a result dict directly or a wrapper {"tool": ..., "result": ...}
        res = entry.get("result", entry) if isinstance(entry, dict) else entry
        if not isinstance(res, dict):
            compact_results.append(res)
            continue

        tool_name = entry.get("tool") if isinstance(entry, dict) and "tool" in entry else None
        # Compact at-risk results: send compact aggregates + top 6 priority cases (avoids massive token payloads)
        if "at_risk" in res or "at_risk_count" in res:
            at_risk_list = res.get("at_risk", [])
            compact_at_risk = [
                {
                    "rank": s.get("risk_rank", i + 1),
                    "name": s.get("name"),
                    "rollNumber": s.get("rollNumber"),
                    "department": s.get("department"),
                    "cgpa": s.get("cgpa"),
                    "attendance": s.get("attendance"),
                    "status": s.get("status"),
                    "backlogs": s.get("backlogs"),
                    "risk_score": s.get("risk_score"),
                    "risk_severity": s.get("risk_severity"),
                    "risk_reasons": s.get("risk_reasons", []),
                }
                for i, s in enumerate(at_risk_list[:6])
            ]
            compact_dict = {
                "at_risk_count": res.get("at_risk_count", len(at_risk_list)),
                "total_records": res.get("total_records"),
                "safe_count": res.get("safe_count"),
                "at_risk_percentage": res.get("at_risk_percentage"),
                "severity_distribution": res.get("severity_distribution", {}),
                "factor_frequencies": res.get("factor_frequencies", {}),
                "dominant_risk_pattern": res.get("dominant_risk_pattern"),
                "department_analysis": res.get("department_analysis", []),
                "top_priority_at_risk_students": compact_at_risk,
            }
            compact_results.append({"tool": tool_name or "evaluate_risk", "result": compact_dict})

        elif "correlation" in res and res.get("correlation") is not None:
            compact_dict = {
                "field1": res.get("field1_label", res.get("field1")),
                "field2": res.get("field2_label", res.get("field2")),
                "correlation": res.get("correlation"),
                "r_squared": res.get("r_squared"),
                "strength": res.get("strength"),
                "direction": res.get("direction"),
                "sample_size": res.get("sample_size"),
                "regression": res.get("regression", {}),
                "field1_stats": res.get("field1_stats", {}),
                "field2_stats": res.get("field2_stats", {}),
                "interpretation": res.get("interpretation"),
            }
            compact_results.append({"tool": tool_name or "calculate_correlation", "result": compact_dict})

        elif "ranking" in res and "formula" in res:
            rank_list = res.get("ranking", [])
            compact_ranked = [
                {
                    "rank": s.get("rank"),
                    "name": s.get("name"),
                    "rollNumber": s.get("rollNumber"),
                    "department": s.get("department"),
                    "cgpa": s.get("cgpa"),
                    "attendance": s.get("attendance"),
                    "academic_score": s.get("academic_score"),
                    "academic_contribution": s.get("academic_contribution"),
                    "attendance_contribution": s.get("attendance_contribution"),
                    "weighted_score": s.get("_weighted_score"),
                }
                for s in rank_list[:12]
            ]
            compact_dict = {
                "formula": res.get("formula"),
                "weights": res.get("weights"),
                "total_records": res.get("total_records"),
                "top_n": res.get("top_n"),
                "ties_count": len(res.get("ties", [])),
                "tie_breaking_rule": res.get("tie_breaking_rule"),
                "statistics": res.get("statistics", {}),
                "top_ranked_students": compact_ranked,
            }
            compact_results.append({"tool": tool_name, "result": compact_dict} if tool_name else compact_dict)
        elif "ranked_records" in res:
            ranked_list = res.get("ranked_records", [])
            compact_ranked = [
                {
                    "name": s.get("name"),
                    "rollNumber": s.get("rollNumber"),
                    "department": s.get("department"),
                    "cgpa": s.get("cgpa"),
                    "attendance": s.get("attendance"),
                    "risk_rank": s.get("risk_rank"),
                    "risk_severity": s.get("risk_severity"),
                }
                for s in ranked_list[:12]
            ]
            compact_dict = {
                "at_risk_count": res.get("at_risk_count"),
                "total_records": res.get("total_records"),
                "top_ranked_students": compact_ranked,
            }
            compact_results.append({"tool": tool_name, "result": compact_dict} if tool_name else compact_dict)
        elif "filtered_records" in res:
            flt_list = res.get("filtered_records", [])
            compact_flt = [
                {
                    "name": s.get("name"),
                    "rollNumber": s.get("rollNumber"),
                    "department": s.get("department"),
                    "cgpa": s.get("cgpa"),
                    "attendance": s.get("attendance"),
                    "status": s.get("status"),
                }
                for s in flt_list[:8]
            ]
            compact_dict = {
                "filter_applied": {k: v for k, v in res.items() if k != "filtered_records"},
                "matched_count": len(flt_list),
                "sample_records": compact_flt,
            }
            compact_results.append({"tool": tool_name, "result": compact_dict} if tool_name else compact_dict)
        elif "top_records" in res or "bottom_records" in res:
            rec_list = res.get("top_records") or res.get("bottom_records", [])
            compact_list = [
                {
                    "name": s.get("name"),
                    "rollNumber": s.get("rollNumber"),
                    "department": s.get("department"),
                    "cgpa": s.get("cgpa"),
                    "attendance": s.get("attendance"),
                }
                for s in rec_list[:8]
            ]
            compact_dict = {
                "field": res.get("field"),
                "n": res.get("n"),
                "count": len(rec_list),
                "records": compact_list,
            }
            compact_results.append({"tool": tool_name, "result": compact_dict} if tool_name else compact_dict)
        else:
            compact_results.append(entry)

    results_json = json.dumps(compact_results, indent=2, default=str)
    return f"""You are an academic data analyst providing clear, actionable insights.

The user asked: "{user_request}"

Dataset context:
{dataset_summary}

Python analytics tools produced the following raw results:
{results_json}

Your job:
1. Directly answer the user's question based ONLY on the data above.
2. Highlight the most important findings (e.g. risk factors breakdown, dominant vulnerability pattern, correlation coefficients, regression model, ranking formulas, or group differences).
3. Keep it concise, structured, and informative.
4. Do NOT invent numbers or facts not present in the results.
5. If something is unclear or data is insufficient, say so honestly.
6. Output plain text — no JSON, no code, no markdown headers.

Write your insight:"""


def _deterministic_summary(raw_results: list[dict]) -> str:
    """Build a basic readable summary from raw tool results without the LLM."""
    parts = []
    for result in raw_results:
        if not isinstance(result, dict):
            continue
        if "error" in result:
            parts.append(f"Analysis error: {result['error']}")
            continue

        # Risk Analysis
        if "at_risk_count" in result or "at_risk" in result:
            at_risk = result.get("at_risk_count", len(result.get("at_risk", [])))
            total = result.get("total_records", "?")
            pct = result.get("at_risk_percentage", "?")
            pat = result.get("dominant_risk_pattern", "")
            sev = result.get("severity_distribution", {})
            crit = sev.get("Critical", 0)
            high = sev.get("High", 0)
            risk_str = f"Academic Risk Assessment: {at_risk} of {total} students ({pct}%) meet at-risk criteria."
            if crit > 0 or high > 0:
                risk_str += f" Priority Breakdown: {crit} Critical, {high} High priority."
            if pat:
                risk_str += f" {pat}"
            parts.append(risk_str)

        # Correlation Analysis
        elif "correlation" in result and result.get("correlation") is not None:
            f1 = result.get("field1_label", result.get("field1", "?"))
            f2 = result.get("field2_label", result.get("field2", "?"))
            r = result["correlation"]
            r_sq = result.get("r_squared", round(r ** 2, 4))
            strength = result.get("strength", "")
            direction = result.get("direction", "")
            reg = result.get("regression", {}).get("formula", "")
            corr_str = f"Correlation between {f1} and {f2}: r = {r} ({strength} {direction}, R² = {r_sq})."
            if reg:
                corr_str += f" Linear Model: {reg}."
            corr_str += " Note: Correlation indicates statistical association, not causation."
            parts.append(corr_str)

        # Weighted Ranking
        elif "ranking" in result and "formula" in result:
            top_n = result.get("top_n", 10)
            formula = result.get("formula", "")
            top_records = result.get("ranking", [])
            top_performers_str = ", ".join(
                f"{r.get('rank', i+1)}. {r.get('name', r.get('rollNumber'))} ({r.get('_weighted_score', 0):.2f})"
                for i, r in enumerate(top_records[:5])
            )
            parts.append(
                f"Top {top_n} students ranked using {formula}. Leading performers: {top_performers_str}."
            )
            if result.get("ties"):
                parts.append(f"Identified {len(result['ties'])} score collision(s) resolved via tie-breaking.")

        # Average
        elif "average" in result and "field" in result:
            parts.append(f"Average {result['field']}: {result['average']}")

        # Groups
        elif "groups" in result and "group_by" in result:
            grp_by = result["group_by"]
            for grp_name, grp_data in result["groups"].items():
                cnt = grp_data.get("count", "?")
                parts.append(f"Group '{grp_name}' ({grp_by}): {cnt} records")

        # Top / bottom N
        elif "top_records" in result:
            field = result.get("field", "field")
            parts.append(f"Top {result.get('n', '')} by {field}: {len(result['top_records'])} records listed")

        elif "bottom_records" in result:
            field = result.get("field", "field")
            parts.append(f"Bottom {result.get('n', '')} by {field}: {len(result['bottom_records'])} records listed")

        # Distribution
        elif "distribution" in result:
            dist = result["distribution"]
            top_bucket = max(dist, key=dist.get) if dist else "N/A"
            parts.append(f"Most common {result.get('field', '')} range: {top_bucket}")

        # Count
        elif "count" in result and len(result) <= 2:
            parts.append(f"Total records: {result['count']}")

    return " | ".join(parts) if parts else "Analysis complete — no specific findings to summarise."


def interpret_results(
    user_request: str,
    raw_results: list[dict],
    dataset_profile: dict,
) -> str:
    """
    Generate a human-readable insight from raw analytics tool results.

    Tries PULSE_GROQ_API_KEY for LLM interpretation.
    Falls back to deterministic summary if unavailable.
    """
    api_key = os.getenv("PULSE_GROQ_API_KEY")
    model = os.getenv("PULSE_GROQ_MODEL", "llama-3.3-70b-versatile")
    dataset_summary = dataset_profile.get("summary_text", "Unknown dataset")

    if not api_key:
        logger.info("[PulseInterpreter] PULSE_GROQ_API_KEY not set — using deterministic summary.")
        return _deterministic_summary(raw_results)

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
    except Exception as exc:
        logger.warning(f"[PulseInterpreter] Failed to init Groq: {exc} — using deterministic fallback.")
        return _deterministic_summary(raw_results)

    prompt = _build_interpretation_prompt(user_request, raw_results, dataset_summary)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise, factual academic data analyst."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        insight = response.choices[0].message.content
        if insight:
            logger.info("[PulseInterpreter] LLM insight generated successfully.")
            return insight.strip()
        else:
            logger.warning("[PulseInterpreter] Empty LLM response — using deterministic fallback.")
            return _deterministic_summary(raw_results)
    except Exception as exc:
        logger.error(f"[PulseInterpreter] LLM error: {exc} — using deterministic fallback.")
        return _deterministic_summary(raw_results)


def llm_reasoning_analysis(
    user_request: str,
    records: list[dict],
    dataset_profile: dict,
) -> str:
    """
    Directly ask the LLM to reason about a request that cannot be handled
    by deterministic tools alone. Uses a data-sample to prevent hallucination.
    """
    api_key = os.getenv("PULSE_GROQ_API_KEY")
    model = os.getenv("PULSE_GROQ_MODEL", "llama-3.3-70b-versatile")

    if not api_key:
        return "LLM reasoning unavailable (PULSE_GROQ_API_KEY not configured). Please rephrase your request as a specific calculation."

    dataset_summary = dataset_profile.get("summary_text", "Unknown dataset")
    # Pass up to 20 records as context (not all, to avoid token limits)
    sample = records[:20]
    sample_json = json.dumps(sample, indent=2, default=str)

    prompt = f"""You are an academic data analyst. The user has asked a complex question.

Dataset description: {dataset_summary}

Sample records (up to 20 shown):
{sample_json}

User question: "{user_request}"

STRICT RULES:
1. Only use information visible in the sample records above.
2. Do NOT invent statistics, names, or numbers not present in the data.
3. If the sample is too small to draw reliable conclusions, say so clearly.
4. Provide a direct, honest, factual answer.

Your analysis:"""

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a precise and honest academic data analyst."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        result = response.choices[0].message.content
        return result.strip() if result else "No analysis could be generated for this request."
    except Exception as exc:
        logger.error(f"[PulseInterpreter] LLM reasoning error: {exc}")
        return f"LLM reasoning failed: {exc}. Try rephrasing as a specific calculation."
