"""
analytics_agent.py — Pulse / Analytics Agent (Coordinator)

Responsibility:
  Receives structured table records and a user analysis request.
  Produces a structured analytics result for downstream consumers (Scribe).

Architecture:
  1. Dataset Profiler   — inspect available columns dynamically
  2. LLM Planner        — convert user request → analysis plan (PULSE_GROQ_*)
  3. Analytics Tools    — execute deterministic Python calculations
  4. LLM Interpreter    — convert calculation results → human insight
  5. Legacy Metrics     — always compute the OrchestrationMetrics contract
                          for backward compatibility with existing consumers

DO NOT:
  - Query the database
  - Call other agents
  - Modify orchestration or API routes

Fallback guarantee:
  If PULSE_GROQ_API_KEY is missing or any LLM call fails, the agent still
  produces complete metrics and a deterministic insight summary.

Output contract (result dict) — Scribe-ready:
  {
    "summary": "...",           # Short analytics summary
    "analysis_type": "...",     # e.g. group_comparison, risk_analysis
    "metrics": { ... },         # OrchestrationMetrics (backward compat)
    "insight": "...",           # Human-readable insight string
    "findings": [ ... ],        # Factual bullet findings
    "insights": [ ... ],        # Insight strings list
    "tables": { ... },          # Named row-oriented tables for Scribe
    "chart_data": { ... },      # Chart-ready data for Scribe
    "records_analyzed": int,    # Total record count
    "columns_analyzed": [...],  # Column names examined
    "analysis_plan": { ... },   # Execution plan used
    "raw_results": [ ... ]      # Individual tool outputs
  }
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult
from app.contracts import OrchestrationMetrics, DepartmentMetric

logger = logging.getLogger(__name__)


# ── Legacy Metrics Builder ─────────────────────────────────────────────────────
# Preserved exactly as before for backward compatibility with existing tests/consumers.

def _build_legacy_metrics(records: List[Dict[str, Any]]) -> OrchestrationMetrics:
    """Compute the OrchestrationMetrics contract from raw records."""
    if not records:
        return OrchestrationMetrics(
            total_records=0,
            average_cgpa=0.0,
            highest_cgpa=0.0,
            lowest_cgpa=0.0,
            avg_attendance=0.0,
            probation_count=0,
            department_breakdown={},
        )

    total_records = len(records)
    cgpa_list = [float(r.get("cgpa", 0.0)) for r in records if r.get("cgpa") is not None]
    attendance_list = [float(r.get("attendance", 0.0)) for r in records if r.get("attendance") is not None]
    probation_count = sum(1 for r in records if r.get("status") == "Probation")

    avg_cgpa = round(sum(cgpa_list) / len(cgpa_list), 2) if cgpa_list else 0.0
    highest_cgpa = round(max(cgpa_list), 2) if cgpa_list else 0.0
    lowest_cgpa = round(min(cgpa_list), 2) if cgpa_list else 0.0
    avg_attendance = round(sum(attendance_list) / len(attendance_list), 2) if attendance_list else 0.0

    dept_counts: Dict[str, list] = {}
    for r in records:
        d = r.get("department", "Unknown")
        cg = r.get("cgpa", 0.0)
        dept_counts.setdefault(d, []).append(float(cg) if cg is not None else 0.0)

    dept_breakdown: Dict[str, DepartmentMetric] = {}
    for dept, c_list in dept_counts.items():
        dept_breakdown[dept] = DepartmentMetric(
            count=len(c_list),
            avg_cgpa=round(sum(c_list) / len(c_list), 2),
        )

    return OrchestrationMetrics(
        total_records=total_records,
        average_cgpa=avg_cgpa,
        highest_cgpa=highest_cgpa,
        lowest_cgpa=lowest_cgpa,
        avg_attendance=avg_attendance,
        probation_count=probation_count,
        department_breakdown=dept_breakdown,
    )


# ── Deterministic Fallback Plan ────────────────────────────────────────────────

def _build_deterministic_plan(
    user_request: str,
    numeric_cols: list[str],
    categorical_cols: list[str],
) -> dict:
    """
    Build an accurate deterministic analysis plan when no LLM planner is available.
    Detects user intent dynamically from query keywords.
    """
    q = user_request.lower()

    # 1. Risk Analysis Intent
    if any(k in q for k in ("risk", "at-risk", "probation", "backlog", "weak", "fail", "reasons")):
        return {
            "analysis_goal": "risk_analysis",
            "strategy": "hybrid",
            "operations": [
                {"tool": "evaluate_risk", "parameters": {}},
            ],
            "reasoning": "Deterministic plan: user requested student risk identification and reasoning.",
        }

    # 2. Correlation Analysis Intent
    if any(k in q for k in ("correlation", "relationship", "relate", "versus", " vs ", "scatter", "associate")):
        f1 = "attendance" if "attendance" in numeric_cols else (numeric_cols[0] if numeric_cols else "attendance")
        f2 = "cgpa" if "cgpa" in numeric_cols else (numeric_cols[1] if len(numeric_cols) > 1 else "cgpa")
        return {
            "analysis_goal": "correlation_analysis",
            "strategy": "hybrid",
            "operations": [
                {"tool": "calculate_correlation", "parameters": {"field1": f1, "field2": f2}},
            ],
            "reasoning": "Deterministic plan: user requested bivariate correlation analysis.",
        }

    # 3. Weighted Multi-Criteria Ranking Intent
    if any(k in q for k in ("weighted", "composite", "criteria rank", "multi-criteria", "80%", "70%")) or ("rank" in q and "attendance" in q and "cgpa" in q):
        top_n = 10
        import re
        top_match = re.search(r"top\s+(\d+)", q)
        if top_match:
            top_n = int(top_match.group(1))

        return {
            "analysis_goal": "weighted_ranking",
            "strategy": "hybrid",
            "operations": [
                {
                    "tool": "calculate_weighted_ranking",
                    "parameters": {"weights": {"cgpa": 0.80, "attendance": 0.20}, "top_n": top_n},
                }
            ],
            "reasoning": "Deterministic plan: user requested multi-criteria weighted ranking.",
        }

    # 4. Department Comparison Intent
    if any(k in q for k in ("compare", "department", "by dept", "across dept")):
        grp_col = "department" if "department" in categorical_cols else (categorical_cols[0] if categorical_cols else "department")
        cmp_col = "cgpa" if "cgpa" in numeric_cols else (numeric_cols[0] if numeric_cols else "cgpa")
        return {
            "analysis_goal": "group_comparison",
            "strategy": "hybrid",
            "operations": [
                {"tool": "compare_groups", "parameters": {"group_by": grp_col, "compare_field": cmp_col}},
            ],
            "reasoning": "Deterministic plan: user requested group comparison.",
        }

    # 5. General Summary Fallback
    ops = [{"tool": "count_records", "parameters": {}}]
    for col in numeric_cols[:3]:
        ops.append({"tool": "calculate_average", "parameters": {"field": col}})
        ops.append({"tool": "calculate_min", "parameters": {"field": col}})
        ops.append({"tool": "calculate_max", "parameters": {"field": col}})

    if categorical_cols:
        primary_cat = categorical_cols[0]
        ops.append({
            "tool": "group_analysis",
            "parameters": {"group_by": primary_cat, "metrics": ["average", "min", "max", "count"]},
        })

    # Only include risk evaluation if risk is explicitly asked for
    if any(k in q for k in ("risk", "at-risk", "probation", "probationary", "intervention", "low-performing", "failing")):
        ops.append({"tool": "evaluate_risk", "parameters": {}})

    return {
        "analysis_goal": "general_summary",
        "strategy": "tool_based",
        "operations": ops,
        "reasoning": "Deterministic fallback — generic overview across numeric and categorical columns.",
    }


class AnalyticsAgent(BaseAgent):
    """
    Pulse / Analytics Agent.

    Backward compatible: always emits OrchestrationMetrics + insight.
    Enhanced: runs a hybrid LLM+Python analysis pipeline when PULSE_GROQ_API_KEY is set.
    """

    name = "analytics"

    def execute(self, task: AgentTask) -> AgentResult:
        try:
            return self._execute_safe(task)
        except Exception as exc:
            logger.exception(f"[Pulse] Unhandled error: {exc}")
            return AgentResult(
                task_id=task.task_id,
                agent=self.name,
                status="failed",
                error=f"Pulse agent encountered an unexpected error: {exc}",
            )

    def _execute_safe(self, task: AgentTask) -> AgentResult:
        # ── Extract records ───────────────────────────────────────────────────
        db_result = task.input_data.get("db", {})
        records: List[Dict[str, Any]] = (
            db_result.get("records") if isinstance(db_result, dict) else []
        ) or task.input_data.get("records", [])

        user_request: str = str(task.input_data.get("user_query", "Summarise the data."))

        logger.info(f"[Pulse] Request: '{user_request[:60]}...'  |  Records: {len(records)}")

        # ── Always compute legacy metrics (backward compat) ───────────────────
        metrics = _build_legacy_metrics(records)

        if not records:
            return AgentResult(
                task_id=task.task_id,
                agent=self.name,
                status="completed",
                result={
                    "metrics": metrics.model_dump(by_alias=True),
                    "insight": "No records available for analysis.",
                    "analysis_plan": None,
                    "raw_results": [],
                },
            )

        # ── Step 1: Profile dataset ───────────────────────────────────────────
        from app.services.pulse.dataset_profiler import profile_dataset
        dataset_profile = profile_dataset(records)
        logger.info(f"[Pulse] Profile: {dataset_profile['summary_text']}")

        # ── Step 2: LLM Planner → get analysis plan ───────────────────────────
        from app.services.pulse.planner_service import get_analysis_plan
        plan = get_analysis_plan(user_request, dataset_profile)

        if plan is None:
            logger.info("[Pulse] No LLM plan — using deterministic fallback plan.")
            plan = _build_deterministic_plan(
                user_request,
                dataset_profile["numeric_columns"],
                dataset_profile["categorical_columns"],
            )

        # ── Step 3: Validate plan (security + structural integrity) ──────────
        from app.services.pulse.plan_validator import validate_plan
        plan, validation_errors = validate_plan(plan, dataset_profile)
        if validation_errors:
            for err in validation_errors:
                logger.warning(f"[Pulse] Plan validation: {err}")

        # ── Step 4: Execute operations using analytics tools ──────────────────
        from app.services.pulse.analytics_tools import run_tool
        from app.services.pulse.risk_service import evaluate_risk, find_at_risk_records, rank_risk_severity
        from app.services.pulse.planner_service import STRATEGY_LLM_REASONING

        strategy = plan.get("strategy", "tool_based")
        raw_results: list[dict] = []

        if strategy == STRATEGY_LLM_REASONING:
            # Skip Python tools — let LLM reason directly
            logger.info("[Pulse] Strategy: llm_reasoning — skipping Python tools.")
            raw_results = []
        else:
            for op in plan.get("operations", []):
                tool_name = op.get("tool", "")
                params = op.get("parameters", {})

                # Route risk tools to risk_service
                if tool_name in ("evaluate_risk", "find_at_risk_records"):
                    result = evaluate_risk(records, **params)
                elif tool_name == "rank_risk_severity":
                    result = rank_risk_severity(records)
                else:
                    result = run_tool(tool_name, records, params)

                raw_results.append({"tool": tool_name, "parameters": params, "result": result})
                logger.info(f"[Pulse] Tool '{tool_name}' completed.")

        # ── Step 5: Interpret results ──────────────────────────────────────────
        from app.services.pulse.llm_interpreter import interpret_results, llm_reasoning_analysis

        if strategy == STRATEGY_LLM_REASONING:
            insight = llm_reasoning_analysis(user_request, records, dataset_profile)
        elif raw_results:
            results_only = [r["result"] for r in raw_results]
            insight = interpret_results(user_request, results_only, dataset_profile)
        else:
            insight = (
                f"Analysed {metrics.total_records} records. "
                f"Average CGPA: {metrics.average_cgpa}. "
                f"Highest: {metrics.highest_cgpa}. "
                f"Probation: {metrics.probation_count}."
            )

        # ── Step 6: Build structured Scribe-ready output ───────────────────────
        from app.services.pulse.result_builder import build_pulse_result
        pulse_result = build_pulse_result(
            records=records,
            dataset_profile=dataset_profile,
            plan=plan,
            raw_results=raw_results,
            insight=insight,
            legacy_metrics=metrics,
        )

        logger.info("[Pulse] Analysis complete.")

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status="completed",
            result=pulse_result,
        )