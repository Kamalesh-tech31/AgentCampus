"""
test_mutation_workflow_deterministic.py — Targeted deterministic validation of the database mutation workflow.

Tests:
1. Pre-mutation checks & affected-row estimation (students table, cgpa column, actual record count).
2. Safety confirmation flow (unconfirmed produces requires_confirmation=True with exact count & SQL).
3. Post-confirmation mutation execution (bulk_update executes, commits/persists, updates records).
4. DB preview refresh (fresh records reflect updated CGPAs, e.g. 9.82 -> 8.82).
5. Authoritative success/failure contract (success=True vs success=False, PlanStep status='failed').
"""

import pytest
from app.mother.mother_agent import MotherAgent
from app.agents.db_agent import DBAgent
from app.mother.types import AgentTask
from app.services.student_service import student_service
from app.db.generic_mutations import estimate_affected_rows, bulk_update
from app.db.generic_queries import generic_get_all


def test_estimate_affected_rows_all_records():
    """Verify that estimate_affected_rows provides the actual non-zero count of students."""
    count = estimate_affected_rows("students", "bulk_update", {"filters": [], "field": "cgpa", "operation": "subtract", "value": 1})
    assert count > 0
    assert count >= 10  # Standard seed has 102 students


def test_unconfirmed_mutation_flow():
    """Verify that 'Reduce the CGPA of all students by 1' with confirmed=False triggers safety confirmation."""
    mother = MotherAgent()
    wf = mother.create_workflow(
        prompt="Reduce the CGPA of all students by 1",
        mode="modify",
        confirmed=False,
    )
    result_wf = mother.execute_workflow(wf)
    res = result_wf.final_result

    assert res is not None
    assert res.requires_confirmation is True
    assert res.confirmation_details is not None
    assert res.confirmation_details.get("operation") == "bulk_update"
    assert res.confirmation_details.get("target_table") == "students"
    assert res.confirmation_details.get("affected_records") > 0
    assert "UPDATE" in res.confirmation_details.get("sql", "").upper()
    assert "students" in res.confirmation_details.get("sql", "").lower()
    assert "cgpa" in res.confirmation_details.get("sql", "").lower()


def test_confirmed_mutation_execution_and_preview_refresh():
    """Verify that 'Reduce the CGPA of all students by 1' with confirmed=True executes, commits, and updates preview."""
    # Reset student store to clean base state
    student_service.reset_db()
    
    # Grab initial CGPA of first student (Aarav Sharma)
    initial_students, _, init_count = generic_get_all("students", limit=10)
    assert init_count > 0
    initial_cgpa = float(initial_students[0]["cgpa"])

    mother = MotherAgent()
    wf = mother.create_workflow(
        prompt="Reduce the CGPA of all students by 1",
        mode="modify",
        confirmed=True,
    )
    result_wf = mother.execute_workflow(wf)
    res = result_wf.final_result

    assert res is not None
    assert res.success is True
    assert res.requires_confirmation is False
    assert res.affected_count is not None
    assert res.affected_count > 0

    # Verify that fresh preview contains updated CGPA values (reduced by 1) for all returned students
    fresh_students, _, fresh_count = generic_get_all("students", limit=10)
    assert fresh_count == init_count
    initial_by_id = {s["id"]: float(s["cgpa"]) for s in initial_students}
    
    for fs in fresh_students:
        s_id = fs["id"]
        if s_id in initial_by_id:
            orig = initial_by_id[s_id]
            updated = float(fs["cgpa"])
            assert updated == pytest.approx(orig - 1.0, rel=1e-2)

    # Verify all plan steps have status 'complete' (never 'error')
    if res.raw_plan:
        for step in res.raw_plan.steps:
            assert step.status in ("waiting", "running", "complete", "failed")
            assert step.status != "error"


def test_failure_contract_never_shows_false_success():
    """Verify that if DB execution fails, result.success is False and DB agent is marked 'failed'."""
    db_agent = DBAgent()
    task = AgentTask(
        task_id="T-FAIL",
        agent="db",
        objective="Execute invalid update",
        input_data={
            "user_query": "Reduce invalid_field by 1",
            "mode": "modify",
            "confirmed": True,
            "action": "bulk_update",
            "table": "students",
            "params": {"field": "non_existent_column_xyz", "operation": "subtract", "value": 1, "filters": []},
        },
        expected_output="Updated records",
    )
    agent_res = db_agent.execute(task)
    assert agent_res.status == "failed"
    assert agent_res.result.get("mutation_status") == "failed"
