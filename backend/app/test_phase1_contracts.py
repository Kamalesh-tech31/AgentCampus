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
