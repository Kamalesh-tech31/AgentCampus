"""
planner_service.py — LLM-powered Analysis Planner for Pulse.

Converts the user's natural-language request into a structured execution plan.
The plan specifies which analytics_tools to run and with what parameters.

Uses PULSE_GROQ_API_KEY and PULSE_GROQ_MODEL independently from Scribe.

Returns None gracefully if the LLM is unavailable, allowing Python-only fallback.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Execution strategy types returned by the LLM
STRATEGY_TOOL_BASED = "tool_based"
STRATEGY_HYBRID = "hybrid"
STRATEGY_LLM_REASONING = "llm_reasoning"

_AVAILABLE_TOOLS_DESC = """
Available analytics tools (use only these):
- count_records — total count of records
- calculate_average(field) — arithmetic mean of a numeric field
- calculate_min(field) — minimum value
- calculate_max(field) — maximum value
- calculate_median(field) — median value
- calculate_sum(field) — sum of values
- calculate_standard_deviation(field) — std deviation
- filter_records(field, operator, value) — operator: eq/ne/gt/gte/lt/lte/contains
- sort_records(field, order, limit) — order: asc/desc
- group_analysis(group_by, metrics, numeric_fields) — stats per group
- calculate_distribution(field, bins) — value frequency distribution
- calculate_correlation(field1, field2) — Pearson correlation coefficient
- detect_outliers(field, method) — method: iqr or zscore
- calculate_weighted_ranking(weights, top_n) — deterministic multi-criteria composite ranking with scale normalization (e.g. weights={"cgpa": 0.80, "attendance": 0.20}, top_n=10)
- rank_records(field, order) — rank all records by single field
- top_n_records(field, n) — top N by single numeric field
- bottom_n_records(field, n) — bottom N by single numeric field
- compare_groups(group_by, compare_field, metrics) — compare group means
- find_at_risk_records(rules) — identify records needing attention
- rank_risk_severity() — rank records by combined risk
"""


def _build_planning_prompt(user_request: str, dataset_summary: str) -> str:
    return f"""You are a data analysis planner for an academic performance analytics system.

Your job is to convert the user's analysis request into a precise execution plan.

Dataset profile:
{dataset_summary}

{_AVAILABLE_TOOLS_DESC}

Execution strategies:
- "tool_based": The request can be fully answered with Python analytics tools.
- "hybrid": Run Python tools first, then the LLM interprets the numerical results.
- "llm_reasoning": The request is too open-ended or qualitative for tools alone.

GUIDELINES FOR TOOL SELECTION:
1. If the user asks to "rank", "top N students", or gives weighted criteria (e.g. "Rank the top 10 students using 80% marks and 20% attendance"):
   Use tool: "calculate_weighted_ranking", parameters: {{"weights": {{"cgpa": 0.80, "attendance": 0.20}}, "top_n": 10}}, strategy: "hybrid".
2. If comparing departments/groups:
   Use tool: "compare_groups", parameters: {{"group_by": "department", "compare_field": "cgpa"}}, strategy: "hybrid".
3. If asking for averages/statistics:
   Use tools: "calculate_average", "calculate_min", "calculate_max", strategy: "tool_based".
4. If asking for at-risk/probation students:
   Use tool: "find_at_risk_records", strategy: "hybrid".

Respond ONLY with a valid JSON object. No text outside JSON.

JSON format:
{{
  "analysis_goal": "brief_label",
  "strategy": "tool_based|hybrid|llm_reasoning",
  "operations": [
    {{
      "tool": "tool_name",
      "parameters": {{...}}
    }}
  ],
  "reasoning": "brief explanation of why this plan was chosen"
}}

User request:
{user_request}

Respond ONLY with the JSON plan:"""


def get_analysis_plan(user_request: str, dataset_profile: dict) -> Optional[dict]:
    """
    Ask the LLM to create a structured analysis plan.

    Returns:
        Parsed plan dict or None if LLM is unavailable or returns invalid output.
    """
    api_key = os.getenv("PULSE_GROQ_API_KEY")
    model = os.getenv("PULSE_GROQ_MODEL", "llama-3.3-70b-versatile")

    if not api_key:
        logger.info("[PulsePlanner] PULSE_GROQ_API_KEY not set — returning None for deterministic fallback.")
        return None

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
    except Exception as exc:
        logger.error(f"[PulsePlanner] Failed to initialise Groq client: {exc}")
        return None

    dataset_summary = dataset_profile.get("summary_text", "Unknown dataset")
    numeric_cols = dataset_profile.get("numeric_columns", [])
    categorical_cols = dataset_profile.get("categorical_columns", [])
    full_summary = (
        f"{dataset_summary}\n"
        f"Numeric columns: {', '.join(numeric_cols) or 'none'}\n"
        f"Categorical columns: {', '.join(categorical_cols) or 'none'}"
    )

    prompt = _build_planning_prompt(user_request, full_summary)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a precise JSON-only data analysis planner."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        raw = response.choices[0].message.content
        plan = json.loads(raw)

        # Validate required keys
        if "strategy" not in plan or "operations" not in plan:
            logger.warning("[PulsePlanner] LLM returned incomplete plan — missing 'strategy' or 'operations'.")
            return None

        if plan["strategy"] not in (STRATEGY_TOOL_BASED, STRATEGY_HYBRID, STRATEGY_LLM_REASONING):
            logger.warning(f"[PulsePlanner] Unknown strategy '{plan['strategy']}' — defaulting to hybrid.")
            plan["strategy"] = STRATEGY_HYBRID

        logger.info(f"[PulsePlanner] Plan received. Strategy: {plan['strategy']}, Operations: {len(plan.get('operations', []))}")
        return plan

    except json.JSONDecodeError as exc:
        logger.error(f"[PulsePlanner] LLM returned non-JSON output: {exc}")
        return None
    except Exception as exc:
        logger.error(f"[PulsePlanner] LLM API error: {exc}")
        return None
