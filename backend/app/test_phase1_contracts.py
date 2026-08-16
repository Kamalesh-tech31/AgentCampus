import pytest
from pydantic import ValidationError
from app.contracts import (
    StudentRecord,
    StudentListResponse,
    ResetDbResponse,
    AgentInfo,
    ActivityLog,
    AgentState,
    PlanStep,
    DynamicPlan,
    DepartmentMetric,
    OrchestrationMetrics,
    OrchestrationResult,
    OrchestrationEvent,
    Turn,
    ChatThread,
    HistoryItem,
    OrchestrationRequest,
)


def test_student_record_validation():
    # Test valid creation using Python snake_case
    student = StudentRecord(
        id="STU-001",
        roll_number="CS2026-01",
        name="Aarav Sharma",
        department="Computer Science",
        cgpa=9.2,
        semester=6,
        attendance=95.0,
        email="aarav@campus.edu",
        status="Active",
        backlogs=0,
        project_title="AI Agent Campus",
    )
    assert student.id == "STU-001"
    assert student.roll_number == "CS2026-01"

    # Test camelCase JSON dump
    data = student.model_dump(mode="json", by_alias=True)
    assert data["rollNumber"] == "CS2026-01"
    assert data["projectTitle"] == "AI Agent Campus"
    assert "roll_number" not in data

    # Test constructing from camelCase dict
    from_dict = StudentRecord.model_validate(
        {
            "id": "STU-002",
            "rollNumber": "ECE2026-02",
            "name": "Bhavna Patel",
            "department": "Electronics",
            "cgpa": 8.5,
            "semester": 4,
            "attendance": 88.0,
            "email": "bhavna@campus.edu",
            "status": "Active",
            "backlogs": 0,
        }
    )
    assert from_dict.roll_number == "ECE2026-02"
    assert from_dict.project_title is None


def test_student_record_constraints():
    # Invalid department
    with pytest.raises(ValidationError):
        StudentRecord(
            id="STU-003",
            roll_number="123",
            name="Test",
            department="Biology",  # Not in enum
            cgpa=8.0,
            semester=1,
            attendance=80.0,
            email="test@campus.edu",
            status="Active",
            backlogs=0,
        )

    # Invalid CGPA > 10.0
    with pytest.raises(ValidationError):
        StudentRecord(
            id="STU-003",
            roll_number="123",
            name="Test",
            department="Civil",
            cgpa=10.5,
            semester=1,
            attendance=80.0,
            email="test@campus.edu",
            status="Active",
            backlogs=0,
        )


def test_student_responses():
    student = StudentRecord(
        id="STU-001",
        roll_number="CS2026-01",
        name="Aarav",
        department="Computer Science",
        cgpa=9.0,
        semester=5,
        attendance=90.0,
        email="a@campus.edu",
        status="Active",
        backlogs=0,
    )
    res = StudentListResponse(students=[student], total=1)
    dumped = res.model_dump(mode="json", by_alias=True)
    assert len(dumped["students"]) == 1
    assert dumped["students"][0]["rollNumber"] == "CS2026-01"

    reset_res = ResetDbResponse(message="Reset complete", students=[student])
    assert reset_res.message == "Reset complete"


def test_agent_contracts():
    info = AgentInfo(
        id="db",
        name="Database Agent",
        role="SQL executor",
        badge="DB",
        model="groq-llama3-70b",
        color="blue",
    )
    assert info.id == "db"

    log = ActivityLog(
        id="log-1",
        timestamp="10:00 AM",
        agent_id="db",
        level="working",
        message="Running SQL query...",
    )
    log_dump = log.model_dump(mode="json", by_alias=True)
    assert log_dump["agentId"] == "db"

    state = AgentState(
        id="db",
        name="Database Agent",
        role="SQL executor",
        badge="DB",
        model="groq-llama3-70b",
        status="running",
        status_message="Querying students",
        logs=[log],
    )
    state_dump = state.model_dump(mode="json", by_alias=True)
    assert state_dump["statusMessage"] == "Querying students"
    assert len(state_dump["logs"]) == 1


def test_invalid_agent_type():
    with pytest.raises(ValidationError):
        AgentInfo(
            id="unknown_agent",  # Invalid agent type
            name="Unknown",
            role="None",
            badge="UNK",
            model="test",
            color="red",
        )


def test_orchestration_plan_contracts():
    step = PlanStep(
        id="step-1",
        step_number=1,
        agent="input",
        action="Parse input",
        description="Parsing user intent",
        status="complete",
        live_message="Intent parsed successfully",
    )
    step_dump = step.model_dump(mode="json", by_alias=True)
    assert step_dump["stepNumber"] == 1
    assert step_dump["liveMessage"] == "Intent parsed successfully"

    plan = DynamicPlan(
        task_id="task-101",
        title="Query High CGPA Students",
        intent="List top students",
        request_type="read",
        steps=[step],
    )
    plan_dump = plan.model_dump(mode="json", by_alias=True)
    assert plan_dump["taskId"] == "task-101"
    assert plan_dump["requestType"] == "read"


def test_orchestration_result_and_event():
    dept_metric = DepartmentMetric(count=10, avg_cgpa=8.7)
    metrics = OrchestrationMetrics(
        total_records=10,
        average_cgpa=8.7,
        department_breakdown={"Computer Science": dept_metric},
    )
    result = OrchestrationResult(
        summary="Found 10 students",
        query_executed="SELECT * FROM students WHERE cgpa > 8.0",
        metrics=metrics,
    )
    res_dump = result.model_dump(mode="json", by_alias=True)
    assert res_dump["queryExecuted"] == "SELECT * FROM students WHERE cgpa > 8.0"
    assert res_dump["metrics"]["departmentBreakdown"]["Computer Science"]["avgCgpa"] == 8.7

    event = OrchestrationEvent(
        type="RESULT_READY",
        task_id="task-101",
        timestamp=1700000000.0,
        result=result,
    )
    event_dump = event.model_dump(mode="json", by_alias=True)
    assert event_dump["type"] == "RESULT_READY"
    assert event_dump["taskId"] == "task-101"
    assert event_dump["result"]["summary"] == "Found 10 students"


def test_turn_and_chat_thread():
    log = ActivityLog(
        id="l1",
        timestamp="12:00",
        agent_id="input",
        level="info",
        message="Started",
    )
    state = AgentState(
        id="input",
        name="Input Agent",
        role="Parser",
        badge="IN",
        model="flash",
        status="complete",
        status_message="Done",
        logs=[log],
    )
    turn = Turn(
        id="turn-1",
        timestamp="12:00 PM",
        prompt="Show top students",
        status="complete",
        agents={"input": state},
    )
    turn_dump = turn.model_dump(mode="json", by_alias=True)
    assert "agents" in turn_dump
    assert turn_dump["agents"]["input"]["status"] == "complete"

    thread = ChatThread(
        id="chat-1",
        title="Top Students Query",
        created_at="12:00 PM",
        updated_at="12:01 PM",
        turns=[turn],
    )
    thread_dump = thread.model_dump(mode="json", by_alias=True)
    assert thread_dump["createdAt"] == "12:00 PM"
    assert len(thread_dump["turns"]) == 1


def test_history_item_and_orchestration_request():
    req = OrchestrationRequest(prompt="Find students with CGPA > 9.0")
    req_dump = req.model_dump(mode="json", by_alias=True)
    assert req_dump["prompt"] == "Find students with CGPA > 9.0"

    hist = HistoryItem(
        id="hist-1",
        timestamp="12:00 PM",
        prompt="Find students with CGPA > 9.0",
        plan_title="Filter CGPA",
        status="complete",
        result_summary="Found 5 students",
    )
    hist_dump = hist.model_dump(mode="json", by_alias=True)
    assert hist_dump["planTitle"] == "Filter CGPA"
    assert hist_dump["resultSummary"] == "Found 5 students"


def test_plan_step_status_values():
    """Verify that PlanStep accepts only 'waiting', 'running', 'complete', 'failed'."""
    for valid_status in ["waiting", "running", "complete", "failed"]:
        step = PlanStep(
            id="step-1",
            step_number=1,
            agent="db",
            action="Query Database",
            description="Executing SQL query",
            status=valid_status,
        )
        assert step.status == valid_status

    # Verify that status='error' is rejected by validation
    with pytest.raises(ValidationError):
        PlanStep(
            id="step-2",
            step_number=2,
            agent="db",
            action="Query Database",
            description="Executing SQL query",
            status="error",
        )


def test_deterministic_plan_step_failure_propagation():
    """Verify that when an execution step fails, PlanStep status is updated to 'failed' (not 'error')."""
    from app.mother.mother_agent import MotherAgent
    from app.contracts import DynamicPlan, PlanStep
    from app.mother.state import WorkflowState
    from app.mother.types import AgentResult
    from unittest.mock import MagicMock

    mother = MotherAgent()
    step1 = PlanStep(id="s1", step_number=1, agent="input", action="Parse", description="Parse query", status="waiting")
    step2 = PlanStep(id="s2", step_number=2, agent="db", action="Query", description="Query db", status="waiting")
    step3 = PlanStep(id="s3", step_number=3, agent="output", action="Format", description="Format output", status="waiting")

    wf = WorkflowState(
        workflow_id="wf-test-fail",
        user_query="test failure query",
        mode="modify",
        confirmed=True,
        plan=DynamicPlan(
            task_id="wf-test-fail",
            title="Test Fail Workflow",
            intent="Test Fail",
            request_type="write",
            steps=[step1, step2, step3],
        ),
    )

    # Mock input agent success, db agent failure
    mock_input = MagicMock()
    mock_input.execute.return_value = AgentResult(task_id="1", agent="input", status="completed", result={"raw_query": "test"})
    mock_db = MagicMock()
    mock_db.execute.return_value = AgentResult(task_id="2", agent="db", status="failed", error="Database connection error", result={})

    mother.registry.register("input", mock_input)
    mother.registry.register("db", mock_db)

    res_wf = mother.execute_workflow(wf, use_crew=False)
    assert res_wf.status == "failed"
    assert res_wf.final_result is not None
    assert res_wf.final_result.success is False
    assert res_wf.final_result.error_type == "AGENT_EXECUTION_ERROR"

    # Step 1 should be 'complete', Step 2 should be 'failed', Step 3 should remain 'waiting'
    steps_dict = {s.agent: s.status for s in res_wf.plan.steps}
    assert steps_dict["input"] == "complete"
    assert steps_dict["db"] == "failed"
    assert steps_dict["output"] == "waiting"


def test_estimate_affected_rows_bulk_update_real_count():
    """Verify that estimate_affected_rows for bulk_update queries the real database row count and does not return 0."""
    from app.db.generic_mutations import estimate_affected_rows, bulk_update
    from app.services.student_service import student_service

    total_students = len(student_service.get_students())
    assert total_students > 0

    # 1. Table-wide bulk update (e.g. "reduce all student CGPA by 1") -> should match all students
    est_all = estimate_affected_rows(
        table="students",
        action="bulk_update",
        params={"field": "cgpa", "operation": "subtract", "value": 1.0, "filters": []}
    )
    assert est_all == total_students
    assert est_all > 0

    # 2. Filtered bulk update (e.g. Computer Science students) -> should match CS students only
    cs_students = [s for s in student_service.get_students() if s.department == "Computer Science"]
    est_cs = estimate_affected_rows(
        table="students",
        action="bulk_update",
        params={
            "field": "cgpa",
            "operation": "subtract",
            "value": 1.0,
            "filters": [{"field": "department", "op": "eq", "value": "Computer Science"}]
        }
    )
    assert est_cs == len(cs_students)
    assert est_cs > 0

    # 3. Execution of bulk update actually modifies rows and returns true affected count
    res = bulk_update(
        table="students",
        filters=[{"field": "department", "op": "eq", "value": "Computer Science"}],
        field="cgpa",
        operation="subtract",
        value=0.5,
    )
    assert res["success"] is True
    assert res["rows_updated"] == len(cs_students)


