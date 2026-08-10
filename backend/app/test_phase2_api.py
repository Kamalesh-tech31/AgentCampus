import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.contracts import StudentListResponse, ResetDbResponse, OrchestrationEvent

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_students_endpoint():
    response = client.get("/api/students")
    assert response.status_code == 200
    data = response.json()
    assert "students" in data
    assert "total" in data
    assert len(data["students"]) > 0

    # Validate against Pydantic contract
    parsed = StudentListResponse.model_validate(data)
    assert len(parsed.students) == data["total"]
    assert parsed.students[0].roll_number is not None


def test_students_reset_endpoint():
    response = client.post("/api/students/reset")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "students" in data

    parsed = ResetDbResponse.model_validate(data)
    assert parsed.message == "Database reset successfully"
    assert len(parsed.students) > 0


def test_orchestrate_stream_endpoint():
    response = client.post(
        "/api/orchestrate/stream",
        json={"prompt": "Show top 10 Computer Science students"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    content = response.text
    assert "data: " in content

    # Parse stream lines into OrchestrationEvent models
    events = []
    for line in content.split("\n\n"):
        line = line.strip()
        if line.startswith("data: "):
            json_str = line[6:]
            event = OrchestrationEvent.model_validate_json(json_str)
            events.append(event)

    assert len(events) >= 5
    event_types = [e.type for e in events]
    assert "TASK_CREATED" in event_types
    assert "AGENT_STARTED" in event_types
    assert "RESULT_READY" in event_types
