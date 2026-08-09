import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.contracts import OrchestrationEvent, OrchestrationResult, StudentRecord
from app.mother.mother_agent import MotherAgent
from app.orchestration.adapter import CrewAdapter

client = TestClient(app)


def _parse_sse(text: str) -> list[OrchestrationEvent]:
    """Parse SSE response text into a list of OrchestrationEvent models."""
    events = []
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        if chunk.startswith("data: "):
            json_str = chunk[6:]
            events.append(OrchestrationEvent.model_validate_json(json_str))
    return events


def test_e2e_read_query_sse():
    """Read query: verify SSE stream order for Input → DB → Output (no analytics)."""
    response = client.post(
        "/api/orchestrate/stream",
        json={"prompt": "Show top 10 Computer Science students"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = _parse_sse(response.text)
    assert len(events) >= 5

    event_types = [e.type for e in events]
    assert "TASK_CREATED" in event_types
    assert "PLAN_UPDATED" in event_types
    assert "AGENT_STARTED" in event_types
    assert "AGENT_COMPLETED" in event_types
    assert "RESULT_READY" in event_types

    # Verify analytics did NOT run
    analytics_events = [e for e in events if e.agent_id == "analytics"]
    assert len(analytics_events) == 0, "Analytics must not run for a read query"

    # Verify execution order of completions: input → db → output
    completed_agents = [e.agent_id for e in events if e.type == "AGENT_COMPLETED"]
    assert completed_agents == ["input", "db", "output"]


def test_e2e_analytics_query_sse():
    """Analytics query: verify Input → DB → Analytics → Output in SSE stream."""
    response = client.post(
        "/api/orchestrate/stream",
        json={"prompt": "Calculate average CGPA for Computer Science"},
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)

    completed_agents = [e.agent_id for e in events if e.type == "AGENT_COMPLETED"]
    assert "analytics" in completed_agents
    assert completed_agents == ["input", "db", "analytics", "output"]


def test_e2e_result_contains_student_data():
    """RESULT_READY payload must contain valid summary and query_executed."""
    response = client.post(
        "/api/orchestrate/stream",
        json={"prompt": "Show Computer Science students"},
    )
    events = _parse_sse(response.text)
    result_events = [e for e in events if e.type == "RESULT_READY"]

    assert len(result_events) == 1
    result = result_events[0].result
    assert result is not None
    assert isinstance(result.summary, str) and len(result.summary) > 0
    assert result.query_executed is not None
    assert "SELECT" in result.query_executed


def test_e2e_sse_format_compliance():
    """Every SSE line must deserialize into a valid OrchestrationEvent contract model."""
    response = client.post(
        "/api/orchestrate/stream",
        json={"prompt": "Show students"},
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert len(events) > 0

    for event in events:
        assert isinstance(event, OrchestrationEvent)
        dumped = event.model_dump(mode="json", by_alias=True)
        assert "type" in dumped
        assert "taskId" in dumped
        assert "timestamp" in dumped


def test_e2e_no_crewai_in_sse_payload():
    """No CrewAI class names or internal types may appear in the SSE JSON data payloads."""
    # These must never appear in the actual JSON event payloads (data: lines)
    crewai_markers = ["crewai", "FlowState", "kickoff", "AgentCampusFlow"]
    response = client.post(
        "/api/orchestrate/stream",
        json={"prompt": "Show top students"},
    )
    # Examine only the actual SSE data payloads — not stdout/stderr captured by test runner
    events = _parse_sse(response.text)
    for event in events:
        json_payload = event.model_dump_json(by_alias=True)
        for marker in crewai_markers:
            assert marker not in json_payload, (
                f"CrewAI internal term '{marker}' leaked into SSE JSON payload"
            )


def test_e2e_mother_to_crewai_to_agents():
    """
    Critical integration test proving the full request path:
    HTTP → FastAPI → MotherAgent → CrewAdapter → AgentCampusFlow → agents → OrchestrationEvents → SSE
    """
    # Step 1: Verify MotherAgent produces correct plan
    mother = MotherAgent()
    workflow = mother.create_workflow("Show top 10 Computer Science students")
    assert workflow.request_type == "read"
    assert [s.agent for s in workflow.plan.steps] == ["input", "db", "output"]

    # Step 2: Verify CrewAdapter executes MotherAgent's exact plan
    adapter = CrewAdapter()
    result_workflow = adapter.run_workflow(workflow)
    assert result_workflow.status == "completed"
    executed_agents = [t.agent for t in result_workflow.task_history if t.status == "completed"]
    assert executed_agents == ["input", "db", "output"]
    assert "analytics" not in executed_agents

    # Step 3: Verify the HTTP → SSE path produces matching results
    response = client.post(
        "/api/orchestrate/stream",
        json={"prompt": "Show top 10 Computer Science students"},
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    completed_agents_http = [e.agent_id for e in events if e.type == "AGENT_COMPLETED"]
    assert completed_agents_http == ["input", "db", "output"]

    # Step 4: Verify final result is contract-compliant
    result_event = next(e for e in events if e.type == "RESULT_READY")
    assert result_event.result is not None
    dumped = result_event.result.model_dump(mode="json", by_alias=True)
    assert "summary" in dumped
    assert "queryExecuted" in dumped


def test_students_endpoint_after_reset():
    """Verify /api/students returns valid StudentRecord data after reset."""
    # Reset
    reset_res = client.post("/api/students/reset")
    assert reset_res.status_code == 200

    # Fetch
    get_res = client.get("/api/students")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["total"] > 0
    assert len(data["students"]) == data["total"]

    # Validate each record against contract
    for raw in data["students"]:
        StudentRecord.model_validate(raw)
