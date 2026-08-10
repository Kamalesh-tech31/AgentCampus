from app.agents.registry import AgentRegistry
from app.mother.types import AgentTask


def test_registry():

    registry = AgentRegistry()

    assert registry.list_agents() == [
        "input",
        "db",
        "analytics",
        "output",
    ]


def test_input_agent():

    registry = AgentRegistry()

    task = AgentTask(
        task_id="TASK-001",
        agent="input",
        objective="Understand request",
        input_data={
            "user_query": "Show top students"
        },
        expected_output="Structured request",
    )

    result = registry.get("input").execute(task)

    assert result.status == "completed"
    assert "structured_intent" in result.result