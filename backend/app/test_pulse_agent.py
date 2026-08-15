"""
test_pulse_agent.py — Independent unit tests for the Pulse Analytics Agent (Parts 1 + 2).

Tests run WITHOUT: MotherAgent, Vault, Scribe, full orchestration, or real Groq API calls.
All LLM calls are mocked where required.
"""

import os
import pytest
from unittest.mock import patch

from app.agents.analytics_agent import AnalyticsAgent
from app.mother.types import AgentTask

# ── Sample Data ────────────────────────────────────────────────────────────────

SAMPLE_RECORDS = [
    {"name": "Arun Kumar",   "department": "CSE", "marks": 92, "attendance": 95, "cgpa": 9.2, "status": "Active"},
    {"name": "Priya Sharma", "department": "CSE", "marks": 88, "attendance": 91, "cgpa": 8.8, "status": "Active"},
    {"name": "Rahul Singh",  "department": "ECE", "marks": 45, "attendance": 65, "cgpa": 5.4, "status": "Probation"},
    {"name": "Neha Patel",   "department": "CSE", "marks": 78, "attendance": 85, "cgpa": 7.8, "status": "Active"},
    {"name": "Vikram Rao",   "department": "ECE", "marks": 55, "attendance": 70, "cgpa": 6.1, "status": "Active"},
]

# Dynamic dataset with completely different column names (tests no hardcoding)
CUSTOM_RECORDS = [
    {"employee": "Alice",  "division": "Engineering", "score": 88.5, "hours": 42, "rating": 4.5},
    {"employee": "Bob",    "division": "Marketing",   "score": 62.0, "hours": 38, "rating": 3.0},
    {"employee": "Carol",  "division": "Engineering", "score": 91.0, "hours": 45, "rating": 4.8},
    {"employee": "David",  "division": "HR",          "score": 55.0, "hours": 35, "rating": 2.8},
    {"employee": "Eve",    "division": "Marketing",   "score": 77.0, "hours": 40, "rating": 3.9},
]


def make_task(query: str, records=None) -> AgentTask:
    if records is None:
        records = SAMPLE_RECORDS
    return AgentTask(
        task_id="PULSE-TEST",
        agent="analytics",
        objective="Analyse data",
        input_data={
            "user_query": query,
            "db": {"records": records},
        },
        expected_output="AnalyticsResult",
    )


@pytest.fixture
def agent():
    return AnalyticsAgent()


# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT CONTRACT
# ══════════════════════════════════════════════════════════════════════════════

def test_output_contract_keys_present(agent):
    """Every required output contract key must be present."""
    task = make_task("Summarise the data")
    res = agent.execute(task)
    assert res.status == "completed"
    r = res.result
    required_keys = [
        "summary", "analysis_type", "metrics", "insight",
        "findings", "insights", "tables", "chart_data",
        "records_analyzed", "columns_analyzed",
        "analysis_plan", "raw_results",
    ]
    for key in required_keys:
        assert key in r, f"Missing required output key: '{key}'"


def test_output_contract_types(agent):
    """Output fields must have correct types."""
    res = agent.execute(make_task("Analyse all students"))
    r = res.result
    assert isinstance(r["summary"], str)
    assert isinstance(r["analysis_type"], str)
    assert isinstance(r["metrics"], dict)
    assert isinstance(r["findings"], list)
    assert isinstance(r["insights"], list)
    assert isinstance(r["tables"], dict)
    assert isinstance(r["chart_data"], dict)
    assert isinstance(r["records_analyzed"], int)
    assert isinstance(r["columns_analyzed"], list)
    assert isinstance(r["analysis_plan"], dict)
    assert isinstance(r["raw_results"], list)


def test_records_analyzed_count(agent):
    """records_analyzed must equal actual record count."""
    res = agent.execute(make_task("Summarise", records=SAMPLE_RECORDS))
    assert res.result["records_analyzed"] == len(SAMPLE_RECORDS)


def test_columns_analyzed_present(agent):
    """columns_analyzed must list the columns found in the dataset."""
    res = agent.execute(make_task("Summarise"))
    cols = res.result["columns_analyzed"]
    assert "cgpa" in cols
    assert "department" in cols


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY METRICS (backward compat)
# ══════════════════════════════════════════════════════════════════════════════

def test_legacy_metrics_always_present(agent):
    """OrchestrationMetrics must always be present for backward compatibility."""
    res = agent.execute(make_task("Summarise the data"))
    assert res.status == "completed"
    metrics = res.result["metrics"]
    assert metrics["totalRecords"] == 5
    assert metrics["averageCgpa"] > 0
    assert metrics["highestCgpa"] == 9.2
    assert metrics["lowestCgpa"] == 5.4
    assert metrics["probationCount"] == 1
    assert "departmentBreakdown" in metrics


def test_empty_records(agent):
    """Empty record list must not crash; must return zero metrics."""
    res = agent.execute(make_task("Summarise", records=[]))
    assert res.status == "completed"
    assert res.result["metrics"]["totalRecords"] == 0
    assert "No records" in res.result["insight"]


# ══════════════════════════════════════════════════════════════════════════════
# DATASET PROFILER (Part 2 enhanced)
# ══════════════════════════════════════════════════════════════════════════════

def test_dataset_profiler_basic():
    from app.services.pulse.dataset_profiler import profile_dataset
    profile = profile_dataset(SAMPLE_RECORDS)
    assert profile["record_count"] == 5
    assert "cgpa" in profile["numeric_columns"]
    assert "department" in profile["categorical_columns"]
    assert "marks" in profile["numeric_columns"]
    assert "attendance" in profile["numeric_columns"]


def test_dataset_profiler_missing_values():
    """Profiler must count missing values correctly."""
    from app.services.pulse.dataset_profiler import profile_dataset
    records_with_gaps = [
        {"name": "Alice", "cgpa": 9.0, "department": "CSE"},
        {"name": "Bob",   "cgpa": None, "department": "ECE"},  # cgpa missing
        {"name": "Carol", "cgpa": 7.5},                         # department missing
    ]
    profile = profile_dataset(records_with_gaps)
    assert profile["columns"]["cgpa"]["missing"] == 1
    assert profile["columns"]["department"]["missing"] == 1


def test_dataset_profiler_numeric_stats():
    """Profiler must compute min/max/mean/std_dev for numeric columns."""
    from app.services.pulse.dataset_profiler import profile_dataset
    profile = profile_dataset(SAMPLE_RECORDS)
    cgpa_stats = profile["columns"]["cgpa"]["stats"]
    assert cgpa_stats["min"] == 5.4
    assert cgpa_stats["max"] == 9.2
    assert 7.0 < cgpa_stats["mean"] < 8.0


def test_dataset_profiler_llm_sample_capped():
    """LLM sample must never exceed 10 records."""
    from app.services.pulse.dataset_profiler import profile_dataset
    big_records = [{"cgpa": float(i), "dept": "X"} for i in range(100)]
    profile = profile_dataset(big_records)
    assert len(profile["llm_sample"]) <= 10


def test_dataset_profiler_empty():
    from app.services.pulse.dataset_profiler import profile_dataset
    profile = profile_dataset([])
    assert profile["record_count"] == 0
    assert profile["numeric_columns"] == []
    assert profile["llm_sample"] == []


def test_dataset_profiler_column_list():
    """column_list must include all non-id columns in order."""
    from app.services.pulse.dataset_profiler import profile_dataset
    profile = profile_dataset(SAMPLE_RECORDS)
    assert "name" in profile["column_list"]
    assert "department" in profile["column_list"]
    assert "id" not in profile["column_list"]


# ══════════════════════════════════════════════════════════════════════════════
# PLAN VALIDATOR (security)
# ══════════════════════════════════════════════════════════════════════════════

def test_validator_rejects_unknown_tool():
    from app.services.pulse.plan_validator import validate_plan
    from app.services.pulse.dataset_profiler import profile_dataset
    profile = profile_dataset(SAMPLE_RECORDS)
    bad_plan = {
        "strategy": "tool_based",
        "operations": [{"tool": "exec_arbitrary_code", "parameters": {}}],
    }
    cleaned, errors = validate_plan(bad_plan, profile)
    assert len(cleaned["operations"]) == 0
    assert any("exec_arbitrary_code" in e for e in errors)


def test_validator_warns_unknown_column():
    from app.services.pulse.plan_validator import validate_plan
    from app.services.pulse.dataset_profiler import profile_dataset
    profile = profile_dataset(SAMPLE_RECORDS)
    plan_with_bad_col = {
        "strategy": "tool_based",
        "operations": [{"tool": "calculate_average", "parameters": {"field": "nonexistent_column"}}],
    }
    cleaned, errors = validate_plan(plan_with_bad_col, profile)
    # Op is kept but a warning is emitted
    assert len(cleaned["operations"]) == 1
    assert any("nonexistent_column" in e for e in errors)


def test_validator_caps_numeric_parameter():
    from app.services.pulse.plan_validator import validate_plan
    from app.services.pulse.dataset_profiler import profile_dataset
    profile = profile_dataset(SAMPLE_RECORDS)
    plan = {
        "strategy": "tool_based",
        "operations": [{"tool": "top_n_records", "parameters": {"field": "cgpa", "n": 99999}}],
    }
    cleaned, errors = validate_plan(plan, profile)
    assert cleaned["operations"][0]["parameters"]["n"] == 1000
    assert any("capped" in e for e in errors)


def test_validator_rejects_invalid_strategy():
    from app.services.pulse.plan_validator import validate_plan
    from app.services.pulse.dataset_profiler import profile_dataset
    profile = profile_dataset(SAMPLE_RECORDS)
    plan = {
        "strategy": "run_os_command",
        "operations": [],
    }
    cleaned, errors = validate_plan(plan, profile)
    assert cleaned["strategy"] == "hybrid"
    assert any("Unknown strategy" in e for e in errors)


def test_validator_passes_valid_plan():
    from app.services.pulse.plan_validator import validate_plan
    from app.services.pulse.dataset_profiler import profile_dataset
    profile = profile_dataset(SAMPLE_RECORDS)
    plan = {
        "strategy": "tool_based",
        "operations": [
            {"tool": "calculate_average", "parameters": {"field": "cgpa"}},
            {"tool": "group_analysis", "parameters": {"group_by": "department", "metrics": ["average", "count"]}},
        ],
    }
    cleaned, errors = validate_plan(plan, profile)
    assert len(cleaned["operations"]) == 2
    assert not any("error" in e.lower() for e in errors)


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS TOOLS
# ══════════════════════════════════════════════════════════════════════════════

def test_calculate_average():
    from app.services.pulse.analytics_tools import calculate_average
    result = calculate_average(SAMPLE_RECORDS, "cgpa")
    assert result["field"] == "cgpa"
    assert abs(result["average"] - 7.46) < 0.1


def test_calculate_min_max():
    from app.services.pulse.analytics_tools import calculate_min, calculate_max
    assert calculate_min(SAMPLE_RECORDS, "cgpa")["min"] == 5.4
    assert calculate_max(SAMPLE_RECORDS, "cgpa")["max"] == 9.2


def test_calculate_median():
    from app.services.pulse.analytics_tools import calculate_median
    result = calculate_median(SAMPLE_RECORDS, "cgpa")
    assert result["median"] is not None


def test_filter_records():
    from app.services.pulse.analytics_tools import filter_records
    result = filter_records(SAMPLE_RECORDS, "cgpa", "lt", 7.0)
    assert result["count"] == 2  # Rahul (5.4) and Vikram (6.1)


def test_group_analysis():
    from app.services.pulse.analytics_tools import group_analysis
    result = group_analysis(SAMPLE_RECORDS, group_by="department", metrics=["average", "count"])
    groups = result["groups"]
    assert "CSE" in groups
    assert "ECE" in groups
    assert groups["CSE"]["count"] == 3
    assert groups["ECE"]["count"] == 2


def test_calculate_correlation():
    from app.services.pulse.analytics_tools import calculate_correlation
    result = calculate_correlation(SAMPLE_RECORDS, "attendance", "cgpa")
    assert result["correlation"] is not None
    assert -1.0 <= result["correlation"] <= 1.0
    assert result["direction"] in ("positive", "negative")


def test_top_n_records():
    from app.services.pulse.analytics_tools import top_n_records
    result = top_n_records(SAMPLE_RECORDS, field="cgpa", n=2)
    top = result["top_records"]
    assert len(top) == 2
    assert top[0]["name"] == "Arun Kumar"


def test_bottom_n_records():
    from app.services.pulse.analytics_tools import bottom_n_records
    result = bottom_n_records(SAMPLE_RECORDS, field="cgpa", n=1)
    assert result["bottom_records"][0]["name"] == "Rahul Singh"


def test_compare_groups():
    from app.services.pulse.analytics_tools import compare_groups
    result = compare_groups(SAMPLE_RECORDS, group_by="department", compare_field="cgpa")
    ranking = result["ranking"]
    assert len(ranking) == 2
    assert ranking[0]["group"] == "CSE"


def test_missing_field_returns_error():
    from app.services.pulse.analytics_tools import calculate_average
    result = calculate_average(SAMPLE_RECORDS, "nonexistent_field")
    assert result["average"] is None
    assert "error" in result


def test_unknown_tool_returns_error():
    from app.services.pulse.analytics_tools import run_tool
    result = run_tool("does_not_exist", SAMPLE_RECORDS, {})
    assert "error" in result


# ══════════════════════════════════════════════════════════════════════════════
# RISK SERVICE
# ══════════════════════════════════════════════════════════════════════════════

def test_find_at_risk_records():
    from app.services.pulse.risk_service import find_at_risk_records
    result = find_at_risk_records(SAMPLE_RECORDS)
    assert result["at_risk_count"] >= 2
    at_risk_names = [r["name"] for r in result["at_risk"]]
    assert "Rahul Singh" in at_risk_names


def test_rank_risk_severity():
    from app.services.pulse.risk_service import rank_risk_severity
    result = rank_risk_severity(SAMPLE_RECORDS)
    assert "ranked_records" in result
    assert result["ranked_records"][0]["risk_rank"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# RESULT BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def test_result_builder_produces_all_keys():
    from app.services.pulse.result_builder import build_pulse_result
    from app.services.pulse.dataset_profiler import profile_dataset
    from app.agents.analytics_agent import _build_legacy_metrics

    profile = profile_dataset(SAMPLE_RECORDS)
    plan = {"analysis_goal": "test", "strategy": "tool_based", "operations": [], "reasoning": "test"}
    metrics = _build_legacy_metrics(SAMPLE_RECORDS)
    result = build_pulse_result(SAMPLE_RECORDS, profile, plan, [], "Test insight.", metrics)

    required_keys = [
        "summary", "analysis_type", "metrics", "insight",
        "findings", "insights", "tables", "chart_data",
        "records_analyzed", "columns_analyzed", "analysis_plan", "raw_results",
    ]
    for key in required_keys:
        assert key in result, f"Missing key: {key}"


def test_result_builder_with_group_tool():
    from app.services.pulse.result_builder import build_pulse_result
    from app.services.pulse.dataset_profiler import profile_dataset
    from app.agents.analytics_agent import _build_legacy_metrics

    profile = profile_dataset(SAMPLE_RECORDS)
    plan = {"analysis_goal": "group", "strategy": "tool_based", "operations": [], "reasoning": ""}
    metrics = _build_legacy_metrics(SAMPLE_RECORDS)
    raw_results = [{
        "tool": "group_analysis",
        "parameters": {"group_by": "department"},
        "result": {
            "group_by": "department",
            "groups": {
                "CSE": {"count": 3, "cgpa": {"average": 8.6}},
                "ECE": {"count": 2, "cgpa": {"average": 5.75}},
            },
        },
    }]
    result = build_pulse_result(SAMPLE_RECORDS, profile, plan, raw_results, "Groups analysed.", metrics)
    assert "group_summary" in result["tables"]
    assert "group_bar" in result["chart_data"]


def test_result_builder_with_risk_tool():
    from app.services.pulse.result_builder import build_pulse_result
    from app.services.pulse.dataset_profiler import profile_dataset
    from app.agents.analytics_agent import _build_legacy_metrics

    profile = profile_dataset(SAMPLE_RECORDS)
    plan = {"analysis_goal": "risk", "strategy": "tool_based", "operations": [], "reasoning": ""}
    metrics = _build_legacy_metrics(SAMPLE_RECORDS)
    raw_results = [{
        "tool": "find_at_risk_records",
        "parameters": {},
        "result": {
            "at_risk": [SAMPLE_RECORDS[2]],
            "at_risk_count": 1,
            "safe_count": 4,
            "total_records": 5,
            "thresholds_used": {},
        },
    }]
    result = build_pulse_result(SAMPLE_RECORDS, profile, plan, raw_results, "1 at risk.", metrics)
    assert "at_risk_students" in result["tables"]
    assert "risk_pie" in result["chart_data"]


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO TESTS (end-to-end with mocked LLM)
# ══════════════════════════════════════════════════════════════════════════════

def test_scenario_simple_average(agent):
    """Test 1: Simple deterministic request — average CGPA."""
    mock_plan = {
        "analysis_goal": "average_cgpa",
        "strategy": "tool_based",
        "operations": [{"tool": "calculate_average", "parameters": {"field": "cgpa"}}],
        "reasoning": "Simple average request",
    }
    with patch("app.services.pulse.planner_service.get_analysis_plan", return_value=mock_plan), \
         patch("app.services.pulse.llm_interpreter.interpret_results", return_value="Average CGPA is 7.46."):
        res = agent.execute(make_task("What is the average CGPA?"))

    assert res.status == "completed"
    assert res.result["metrics"]["totalRecords"] == 5
    raw = res.result["raw_results"]
    assert any(r["tool"] == "calculate_average" for r in raw)
    assert any("Average cgpa" in f for f in res.result["findings"])


def test_scenario_group_comparison(agent):
    """Test 2: Group comparison — Compare CSE and ECE."""
    mock_plan = {
        "analysis_goal": "department_comparison",
        "strategy": "hybrid",
        "operations": [
            {"tool": "compare_groups", "parameters": {"group_by": "department", "compare_field": "cgpa"}},
        ],
        "reasoning": "Compare group means",
    }
    with patch("app.services.pulse.planner_service.get_analysis_plan", return_value=mock_plan), \
         patch("app.services.pulse.llm_interpreter.interpret_results", return_value="CSE outperforms ECE."):
        res = agent.execute(make_task("Compare CSE and ECE performance"))

    assert res.status == "completed"
    assert res.result["analysis_type"] == "group_comparison"
    assert "CSE outperforms ECE" in res.result["insight"]


def test_scenario_risk_analysis(agent):
    """Test 3: Risk analysis — identify students needing attention."""
    mock_plan = {
        "analysis_goal": "risk_analysis",
        "strategy": "tool_based",
        "operations": [{"tool": "find_at_risk_records", "parameters": {"rules": "auto_or_explicit"}}],
        "reasoning": "Find at-risk records",
    }
    with patch("app.services.pulse.planner_service.get_analysis_plan", return_value=mock_plan), \
         patch("app.services.pulse.llm_interpreter.interpret_results", return_value="2 students need attention."):
        res = agent.execute(make_task("Identify students who need attention"))

    assert res.status == "completed"
    assert res.result["analysis_type"] == "risk_analysis"
    assert "at_risk_students" in res.result["tables"]
    assert "risk_pie" in res.result["chart_data"]
    assert any("At-risk" in f for f in res.result["findings"])


def test_scenario_complex_open_ended(agent):
    """Test 4: Complex open-ended — LLM reasoning strategy."""
    mock_plan = {
        "analysis_goal": "open_ended_complex_analysis",
        "strategy": "llm_reasoning",
        "operations": [],
        "reasoning": "Too complex for tools",
    }
    with patch("app.services.pulse.planner_service.get_analysis_plan", return_value=mock_plan), \
         patch("app.services.pulse.llm_interpreter.llm_reasoning_analysis",
               return_value="Multiple factors contribute to poor performance including low attendance."):
        res = agent.execute(make_task("Analyse the data and identify the most important hidden problems"))

    assert res.status == "completed"
    assert res.result["raw_results"] == []
    assert "Multiple factors" in res.result["insight"]


def test_scenario_dynamic_dataset(agent):
    """Test 5: Dynamic dataset with completely different column names — no hardcoding."""
    mock_plan = {
        "analysis_goal": "general_summary",
        "strategy": "tool_based",
        "operations": [
            {"tool": "calculate_average", "parameters": {"field": "score"}},
            {"tool": "group_analysis", "parameters": {"group_by": "division", "metrics": ["average", "count"]}},
        ],
        "reasoning": "General summary for custom dataset",
    }
    with patch("app.services.pulse.planner_service.get_analysis_plan", return_value=mock_plan), \
         patch("app.services.pulse.llm_interpreter.interpret_results", return_value="Engineering scores highest."):
        res = agent.execute(make_task("Summarise employee performance", records=CUSTOM_RECORDS))

    assert res.status == "completed"
    assert res.result["records_analyzed"] == 5
    assert "score" in res.result["columns_analyzed"]
    assert "division" in res.result["columns_analyzed"]
    # Must not crash just because cgpa/department are absent
    assert res.result["metrics"]["totalRecords"] == 5


def test_scenario_missing_api_key(agent):
    """Test 6: Missing PULSE_GROQ_API_KEY — deterministic fallback must still work."""
    env = os.environ.copy()
    env.pop("PULSE_GROQ_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        res = agent.execute(make_task("Compare CSE and ECE performance"))

    assert res.status == "completed"
    assert res.result["metrics"]["totalRecords"] == 5
    assert res.result["insight"] != ""
    assert isinstance(res.result["findings"], list)


def test_scenario_invalid_llm_plan_rejected(agent):
    """Test 7: Invalid LLM plan must be rejected safely — agent must not crash."""
    invalid_plan = {
        "strategy": "tool_based",
        "operations": [
            {"tool": "__import__('os').system('rm -rf /')", "parameters": {}},
            {"tool": "calculate_average", "parameters": {"field": "cgpa"}},
        ],
    }
    with patch("app.services.pulse.planner_service.get_analysis_plan", return_value=invalid_plan), \
         patch("app.services.pulse.llm_interpreter.interpret_results", return_value="Safe result."):
        res = agent.execute(make_task("What is average CGPA?"))

    assert res.status == "completed"
    # The dangerous tool must have been removed; only calculate_average should survive
    executed_tools = [r["tool"] for r in res.result["raw_results"]]
    assert "__import__" not in " ".join(executed_tools)
    assert "calculate_average" in executed_tools


# ══════════════════════════════════════════════════════════════════════════════
# LLM PLANNER (no-API-key path)
# ══════════════════════════════════════════════════════════════════════════════

def test_planner_returns_none_without_api_key():
    from app.services.pulse.planner_service import get_analysis_plan
    from app.services.pulse.dataset_profiler import profile_dataset
    profile = profile_dataset(SAMPLE_RECORDS)
    env = os.environ.copy()
    env.pop("PULSE_GROQ_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        plan = get_analysis_plan("Average CGPA?", profile)
    assert plan is None


# ══════════════════════════════════════════════════════════════════════════════
# MOCKED FULL PIPELINE (tool_based with LLM mocked)
# ══════════════════════════════════════════════════════════════════════════════

def test_full_pipeline_with_mocked_llm(agent):
    """Full pipeline: profiler → planner (mocked) → validator → tools → interpreter (mocked) → result."""
    mock_plan = {
        "analysis_goal": "comprehensive",
        "strategy": "tool_based",
        "operations": [
            {"tool": "calculate_average", "parameters": {"field": "cgpa"}},
            {"tool": "find_at_risk_records", "parameters": {"rules": "auto_or_explicit"}},
            {"tool": "group_analysis", "parameters": {"group_by": "department", "metrics": ["average", "count"]}},
        ],
        "reasoning": "Comprehensive analysis",
    }
    with patch("app.services.pulse.planner_service.get_analysis_plan", return_value=mock_plan), \
         patch("app.services.pulse.llm_interpreter.interpret_results", return_value="Comprehensive insight."):
        res = agent.execute(make_task("Comprehensive analysis of all students"))

    assert res.status == "completed"
    r = res.result
    assert r["records_analyzed"] == 5
    assert len(r["raw_results"]) == 3
    assert "Comprehensive insight" in r["insight"]
    assert r["metrics"]["totalRecords"] == 5
    assert len(r["findings"]) > 0
    # Tables and chart_data must be populated from tool results
    assert "at_risk_students" in r["tables"]
    assert "group_summary" in r["tables"]
    assert "risk_pie" in r["chart_data"]
    assert "group_bar" in r["chart_data"]


def test_agent_with_llm_reasoning_strategy(agent):
    """Test agent handles llm_reasoning strategy gracefully."""
    mock_plan = {
        "analysis_goal": "open_ended_reasoning",
        "strategy": "llm_reasoning",
        "operations": [],
        "reasoning": "Request too complex for tools",
    }
    with patch("app.services.pulse.planner_service.get_analysis_plan", return_value=mock_plan), \
         patch("app.services.pulse.llm_interpreter.llm_reasoning_analysis", return_value="Mocked reasoning insight"):
        res = agent.execute(make_task("Explain all hidden reasons for poor performance"))

    assert res.status == "completed"
    assert res.result["raw_results"] == []
    assert "Mocked reasoning insight" in res.result["insight"]
