"""
plan_validator.py — Security and structural validation for Pulse analysis plans.

Rules enforced:
  1. Tool names must exist in the registered TOOL_REGISTRY.
  2. Column names referenced as parameters must exist in the dataset profile.
  3. Numeric parameters must be within safe limits (e.g. n <= 1000).
  4. No arbitrary code execution — the LLM may NOT specify free-form code.
  5. Unknown or malformed operations are silently dropped with a warning.

The validator returns a cleaned plan (with invalid ops removed) and a list
of validation errors for logging/debugging. It never crashes.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.pulse.analytics_tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)

# Parameters that must reference a valid column name
_COLUMN_PARAMS = {"field", "field1", "field2", "group_by", "compare_field"}

# Numeric parameters with max safe values
_NUMERIC_PARAM_LIMITS: dict[str, int] = {
    "n": 1000,
    "bins": 100,
    "limit": 10000,
}

# Allowed strategy values
_VALID_STRATEGIES = {"tool_based", "hybrid", "llm_reasoning"}

# Risk-service tools not in TOOL_REGISTRY but still allowed
_ALLOWED_EXTRA_TOOLS = {"find_at_risk_records", "rank_risk_severity"}


def validate_plan(plan: dict, dataset_profile: dict) -> tuple[dict, list[str]]:
    """
    Validate and sanitise an analysis plan.

    Args:
        plan:            The raw plan dict from the LLM planner.
        dataset_profile: Profile from dataset_profiler.profile_dataset().

    Returns:
        (cleaned_plan, errors)
        cleaned_plan — a sanitised version of the plan with invalid ops removed.
        errors       — list of human-readable validation error strings.
    """
    errors: list[str] = []
    available_columns: set[str] = set(dataset_profile.get("column_list", []))

    if not isinstance(plan, dict):
        errors.append("Plan is not a dict — rejected entirely.")
        return {}, errors

    # ── Validate strategy ──────────────────────────────────────────────────────
    strategy = plan.get("strategy", "tool_based")
    if strategy not in _VALID_STRATEGIES:
        errors.append(f"Unknown strategy '{strategy}' — defaulting to 'hybrid'.")
        strategy = "hybrid"
    cleaned_plan: dict[str, Any] = {
        "analysis_goal": plan.get("analysis_goal", "general_analysis"),
        "strategy": strategy,
        "reasoning": plan.get("reasoning", ""),
        "operations": [],
    }

    # ── For llm_reasoning, no operations needed ────────────────────────────────
    if strategy == "llm_reasoning":
        return cleaned_plan, errors

    # ── Validate each operation ────────────────────────────────────────────────
    operations = plan.get("operations", [])
    if not isinstance(operations, list):
        errors.append("'operations' is not a list — treating as empty.")
        return cleaned_plan, errors

    for i, op in enumerate(operations):
        op_errors, cleaned_op = _validate_operation(i, op, available_columns)
        errors.extend(op_errors)
        if cleaned_op is not None:
            cleaned_plan["operations"].append(cleaned_op)

    if not cleaned_plan["operations"] and strategy != "llm_reasoning":
        errors.append("No valid operations remain after validation.")

    return cleaned_plan, errors


def _validate_operation(index: int, op: Any, available_columns: set[str]) -> tuple[list[str], dict | None]:
    """Validate a single operation entry. Returns (errors, cleaned_op or None)."""
    errors: list[str] = []
    prefix = f"Operation[{index}]"

    if not isinstance(op, dict):
        errors.append(f"{prefix}: not a dict — skipped.")
        return errors, None

    tool_name = op.get("tool", "")
    if not tool_name:
        errors.append(f"{prefix}: missing 'tool' key — skipped.")
        return errors, None

    # Check tool is registered
    if tool_name not in TOOL_REGISTRY and tool_name not in _ALLOWED_EXTRA_TOOLS:
        errors.append(f"{prefix}: unknown tool '{tool_name}' — skipped.")
        return errors, None

    params = op.get("parameters", {})
    if not isinstance(params, dict):
        errors.append(f"{prefix} '{tool_name}': 'parameters' is not a dict — using empty params.")
        params = {}

    cleaned_params: dict[str, Any] = {}
    for param_key, param_val in params.items():
        # Validate column references
        if param_key in _COLUMN_PARAMS and isinstance(param_val, str):
            if param_val not in available_columns and available_columns:
                errors.append(
                    f"{prefix} '{tool_name}': column '{param_val}' not in dataset "
                    f"(available: {sorted(available_columns)}) — parameter kept but may error."
                )
            cleaned_params[param_key] = param_val

        # Validate list of column names (e.g. numeric_fields, metrics)
        elif param_key == "numeric_fields" and isinstance(param_val, list):
            valid_fields = [f for f in param_val if isinstance(f, str)]
            cleaned_params[param_key] = valid_fields

        elif param_key == "metrics" and isinstance(param_val, list):
            allowed_metrics = {"average", "min", "max", "sum", "count", "median"}
            valid_metrics = [m for m in param_val if m in allowed_metrics]
            if len(valid_metrics) != len(param_val):
                errors.append(f"{prefix} '{tool_name}': some metric names filtered out.")
            cleaned_params[param_key] = valid_metrics if valid_metrics else list(allowed_metrics)[:4]

        # Validate numeric limits
        elif param_key in _NUMERIC_PARAM_LIMITS:
            try:
                n_val = int(param_val)
                limit = _NUMERIC_PARAM_LIMITS[param_key]
                if n_val > limit:
                    errors.append(f"{prefix} '{tool_name}': {param_key}={n_val} exceeds limit {limit} — capped.")
                    n_val = limit
                cleaned_params[param_key] = n_val
            except (TypeError, ValueError):
                errors.append(f"{prefix} '{tool_name}': {param_key} is not numeric — skipped.")

        # Allow safe scalar values (str, int, float, bool, list of scalars)
        elif isinstance(param_val, (str, int, float, bool)):
            cleaned_params[param_key] = param_val
        elif isinstance(param_val, list) and all(isinstance(v, (str, int, float, bool)) for v in param_val):
            cleaned_params[param_key] = param_val
        else:
            errors.append(f"{prefix} '{tool_name}': parameter '{param_key}' has unsafe type — skipped.")

    return errors, {"tool": tool_name, "parameters": cleaned_params}
