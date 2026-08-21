"""
test_scope_leakage_deterministic.py — Deterministic verification that request scope is strictly enforced.
Verifies:
1. "Show the top 10 CSE students based on the CGPA" executes strictly as a read/ranking workflow.
2. Exactly <= 10 records are returned, filtered by Computer Science, sorted by CGPA descending.
3. Unsolicited AT-RISK students (49 identified) analysis is completely eliminated.
4. Analytics agent is skipped when not requested.
5. Scribe output is concise, matched to the question.
6. Explicit at-risk queries still execute risk evaluation when requested.
"""

import pytest
from app.mother.mother_agent import MotherAgent
from app.agents.input_agent import InputAgent
from app.agents.db_agent import DBAgent
from app.agents.output_agent import OutputAgent
from app.mother.types import AgentTask


def test_input_agent_ranking_query_scope():
    """Verify InputAgent extracts exact scope for 'Show the top 10 CSE students based on the CGPA'."""
    agent = InputAgent()
    task = AgentTask(
        task_id="T-SCOPE-1",
        workflow_id="WF-SCOPE-1",
        agent="input",
        objective="Parse user query",
        input_data={"user_query": "Show the top 10 CSE students based on the CGPA"},
    )
    res = agent.execute(task)
    assert res.status == "completed"
    si = res.result["structured_intent"]

    assert si["operation"] == "read"
    assert si["department"] == "Computer Science"
    assert si["limit"] == 10
    assert si["sort"] == {"field": "cgpa", "direction": "desc"}
    assert si["action"] == "filter_rows"
    assert any(f.get("field") == "department" and f.get("value") == "Computer Science" for f in si["params"]["filters"])


def test_mother_agent_plan_read_ranking_no_analytics():
    """Verify MotherAgent classifies ranking query as 'read' and skips analytics agent in plan."""
    mother = MotherAgent()
    query = "Show the top 10 CSE students based on the CGPA"

    workflow = mother.create_workflow(prompt=query)
    assert workflow.request_type == "read"
    assert workflow.plan is not None

    plan_agents = [s.agent for s in workflow.plan.steps]
    assert "input" in plan_agents
    assert "db" in plan_agents
    assert "output" in plan_agents
    assert "analytics" not in plan_agents, "Analytics agent must NOT be in plan for a read ranking query"


def test_db_agent_returns_at_most_10_records():
    """Verify DB Agent executes query dynamically with limit 10 and returns at most 10 CSE records."""
    input_agent = InputAgent()
    db_agent = DBAgent()

    task_in = AgentTask(
        task_id="T-SCOPE-2A",
        workflow_id="WF-SCOPE-2",
        agent="input",
        objective="Parse user query",
        input_data={"user_query": "Show the top 10 CSE students based on the CGPA"},
    )
    res_in = input_agent.execute(task_in)

    task_db = AgentTask(
        task_id="T-SCOPE-2B",
        workflow_id="WF-SCOPE-2",
        agent="db",
        objective="Execute DB query",
        input_data={"user_query": "Show the top 10 CSE students based on the CGPA", "input": res_in.result},
    )
    res_db = db_agent.execute(task_db)
    assert res_db.status == "completed"

    records = res_db.result.get("records", [])
    assert len(records) <= 10
    assert len(records) > 0

    # Verify all records belong to Computer Science
    for r in records:
        assert r.get("department") == "Computer Science"

    # Verify sorting is descending by CGPA
    cgpas = [float(r.get("cgpa", 0)) for r in records]
    assert cgpas == sorted(cgpas, reverse=True)


def test_end_to_end_no_at_risk_leakage():
    """Verify full workflow output for top 10 CSE students contains NO at-risk section."""
    mother = MotherAgent()
    query = "Show the top 10 CSE students based on the CGPA"

    workflow = mother.create_workflow(prompt=query)
    final_wf = mother.execute_workflow(workflow)
    assert final_wf.status == "completed"

    # Analytics must not have run
    executed_agents = [t.agent for t in final_wf.task_history if t.status == "completed"]
    assert "analytics" not in executed_agents

    # Verify final result records count
    final_res = final_wf.final_result
    assert final_res is not None
    assert final_res.data is not None
    assert len(final_res.data) <= 10

    # Verify Scribe summary / text content
    summary = final_res.summary
    assert "AT-RISK STUDENTS" not in summary.upper()
    assert "49 IDENTIFIED" not in summary.upper()
    assert "EARLY INTERVENTION" not in summary.upper()


def test_explicit_risk_query_still_works():
    """Verify that when the user EXPLICITLY asks for at-risk students, risk evaluation runs."""
    mother = MotherAgent()
    query = "Find academically at-risk students and explain reasons"

    workflow = mother.create_workflow(prompt=query)
    assert workflow.request_type == "analytics"

    final_wf = mother.execute_workflow(workflow)
    assert final_wf.status == "completed"

    executed_agents = [t.agent for t in final_wf.task_history if t.status == "completed"]
    assert "analytics" in executed_agents

    summary = final_wf.final_result.summary
    assert "AT-RISK" in summary.upper() or "RISK" in summary.upper()


def test_top_single_student_query():
    """Verify 'show me the top student based on the cgpa' returns exactly 1 student and no error."""
    mother = MotherAgent()
    query = "show me the top student based on the cgpa"

    workflow = mother.create_workflow(prompt=query)
    assert workflow.request_type == "read"

    final_wf = mother.execute_workflow(workflow)
    assert final_wf.status == "completed"
    assert final_wf.final_result is not None
    assert final_wf.final_result.data is not None
    assert len(final_wf.final_result.data) == 1

    summary = final_wf.final_result.summary
    assert "AT-RISK" not in summary.upper()
    assert "DB AGENT FAILED" not in summary.upper()

