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
    results_json = json.dumps(raw_results, indent=2, default=str)
    return f"""You are an academic data analyst providing clear, actionable insights.

The user asked: "{user_request}"

Dataset context:
{dataset_summary}

Python analytics tools produced the following raw results:
{results_json}

Your job:
1. Directly answer the user's question based ONLY on the data above.
2. Highlight the most important findings.
3. Keep it concise unless the question explicitly asks for a detailed explanation.
4. Do NOT invent numbers or facts not present in the results.
5. If something is unclear or data is insufficient, say so honestly.
6. Output plain text — no JSON, no code, no markdown headers.

Write your insight:"""


def _deterministic_summary(raw_results: list[dict]) -> str:
    """Build a basic readable summary from raw tool results without the LLM."""
    parts = []
    for result in raw_results:
        if "error" in result:
            parts.append(f"Analysis error: {result['error']}")
            continue

        # Average
        if "average" in result and "field" in result:
            parts.append(f"Average {result['field']}: {result['average']}")

        # Correlation
        if "correlation" in result and result["correlation"] is not None:
            f1, f2 = result.get("field1", "?"), result.get("field2", "?")
            r = result["correlation"]
            strength = result.get("strength", "")
            direction = result.get("direction", "")
            parts.append(f"Correlation between {f1} and {f2}: {r} ({strength} {direction})")

        # Groups
        if "groups" in result and "group_by" in result:
            grp_by = result["group_by"]
            for grp_name, grp_data in result["groups"].items():
                cnt = grp_data.get("count", "?")
                parts.append(f"Group '{grp_name}' ({grp_by}): {cnt} records")

        # At-risk
        if "at_risk_count" in result:
            parts.append(
                f"At-risk records: {result['at_risk_count']} out of {result.get('total_records', '?')}"
            )

        # Top / bottom N
        if "top_records" in result:
            field = result.get("field", "field")
            parts.append(f"Top {result.get('n', '')} by {field}: {len(result['top_records'])} records listed")

        if "bottom_records" in result:
            field = result.get("field", "field")
            parts.append(f"Bottom {result.get('n', '')} by {field}: {len(result['bottom_records'])} records listed")

        # Distribution
        if "distribution" in result:
            dist = result["distribution"]
            top_bucket = max(dist, key=dist.get) if dist else "N/A"
            parts.append(f"Most common {result.get('field', '')} range: {top_bucket}")

        # Count
        if "count" in result and len(result) <= 2:
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
