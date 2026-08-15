import pytest
from unittest.mock import MagicMock, patch
from app.services.groq_service import GroqService, GroqPlanPayload, GroqStep
from app.mother.mother_agent import MotherAgent
from app.mother.state import WorkflowState


def test_missing_groq_configuration(monkeypatch):
    """When MOTHER_GROQ_API_KEY is absent, GroqService returns None and MotherAgent falls back safely."""
    monkeypatch.delenv("MOTHER_GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    service = GroqService(api_key=None)
    assert service.client is None

    plan = service.generate_plan("Show top 10 CS students")
    assert plan is None

    mother = MotherAgent(groq_service=service)
    workflow = mother.create_workflow("Show top 10 CS students")
    assert workflow.plan is not None
    assert workflow.plan.request_type == "read"
    assert [s.agent for s in workflow.plan.steps] == ["input", "db", "output"]


def test_groq_service_mock_response():
    """Mock Groq client returning valid JSON matching schema."""
    mock_payload_json = """{
        "title": "Top CS Students",
        "intent": "Fetch top 10 CS students",
        "request_type": "read",
        "steps": [
            {"agent": "input", "action": "Intent Parsing", "description": "Parse parameters"},
            {"agent": "db", "action": "Database Query", "description": "Execute SQL"},
            {"agent": "output", "action": "Format Output", "description": "Format summary"}
        ]
    }"""

    service = GroqService(api_key="fake-key-for-testing")
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = mock_payload_json

    service.client = MagicMock()
    service.client.chat.completions.create.return_value = mock_completion

    res = service.generate_plan("Show top CS students")
    assert res is not None
    assert isinstance(res, GroqPlanPayload)
    assert res.request_type == "read"
    assert len(res.steps) == 3
    assert [s.agent for s in res.steps] == ["input", "db", "output"]


def test_mother_agent_groq_plan_generation():
    """MotherAgent using mocked GroqService produces LLM-driven DynamicPlan."""
    service = GroqService(api_key="fake-key")

    read_json = """{
        "title": "CS Students",
        "intent": "Retrieve Computer Science student list",
        "request_type": "read",
        "steps": [
            {"agent": "input", "action": "Parse", "description": "Parse query"},
            {"agent": "db", "action": "Query DB", "description": "Run SELECT"},
            {"agent": "output", "action": "Format", "description": "Render table"}
        ]
    }"""

    mock_comp = MagicMock()
    mock_comp.choices = [MagicMock()]
    mock_comp.choices[0].message.content = read_json
    service.client = MagicMock()
    service.client.chat.completions.create.return_value = mock_comp

    mother = MotherAgent(groq_service=service)
    wf = mother.create_workflow("Show CS students")

    assert wf.plan.title == "CS Students"
    assert wf.plan.intent == "Retrieve Computer Science student list"
    assert wf.plan.request_type == "read"
    assert [s.agent for s in wf.plan.steps] == ["input", "db", "output"]


def test_groq_generated_analytics_plan():
    """Groq payload with analytics produces request_type='analytics' and 4 steps."""
    service = GroqService(api_key="fake-key")

    analytics_json = """{
        "title": "Avg CGPA Analysis",
        "intent": "Calculate average CGPA for CS department",
        "request_type": "analytics",
        "steps": [
            {"agent": "input", "action": "Parse Intent", "description": "Parse request"},
            {"agent": "db", "action": "Fetch Records", "description": "Query CS students"},
            {"agent": "analytics", "action": "Compute Stats", "description": "Calculate average CGPA"},
            {"agent": "output", "action": "Format Output", "description": "Format metrics response"}
        ]
    }"""

    mock_comp = MagicMock()
    mock_comp.choices = [MagicMock()]
    mock_comp.choices[0].message.content = analytics_json
    service.client = MagicMock()
    service.client.chat.completions.create.return_value = mock_comp

    mother = MotherAgent(groq_service=service)
    wf = mother.create_workflow("Calculate average CGPA for CS")

    assert wf.plan.request_type == "analytics"
    assert [s.agent for s in wf.plan.steps] == ["input", "db", "analytics", "output"]


def test_invalid_groq_plan():
    """Invalid agent name in Groq payload causes rejection and fallback to deterministic plan."""
    service = GroqService(api_key="fake-key")

    invalid_json = """{
        "title": "Hacked Plan",
        "intent": "Malicious execution",
        "request_type": "read",
        "steps": [
            {"agent": "input", "action": "Parse", "description": "Parse"},
            {"agent": "unauthorized_agent", "action": "Hack", "description": "Invalid agent"}
        ]
    }"""

    mock_comp = MagicMock()
    mock_comp.choices = [MagicMock()]
    mock_comp.choices[0].message.content = invalid_json
    service.client = MagicMock()
    service.client.chat.completions.create.return_value = mock_comp

    # GroqService rejects invalid agent
    plan = service.generate_plan("Test query")
    assert plan is None

    # MotherAgent falls back safely
    mother = MotherAgent(groq_service=service)
    wf = mother.create_workflow("Show students")
    assert wf.plan is not None
    assert [s.agent for s in wf.plan.steps] == ["input", "db", "output"]


def test_groq_api_failure_fallback():
    """Groq client throwing an exception falls back to deterministic synthesis gracefully."""
    service = GroqService(api_key="fake-key")
    service.client = MagicMock()
    service.client.chat.completions.create.side_effect = Exception("API rate limit exceeded")

    mother = MotherAgent(groq_service=service)
    wf = mother.create_workflow("Show top students")

    assert wf.plan is not None
    assert wf.plan.request_type == "read"
    assert [s.agent for s in wf.plan.steps] == ["input", "db", "output"]
