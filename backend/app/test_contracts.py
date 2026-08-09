from app.mother.types import AgentTask, AgentResult
from app.mother.state import WorkflowState


def test_agent_task():

    task = AgentTask(
        task_id="TASK-001",
        agent="db",
        objective="Retrieve student records",
        input_data={
            "query": "top students"
        },
        expected_output="student records",
    )

    assert task.agent == "db"
    assert task.status == "pending"


def test_agent_result():

    result = AgentResult(
        task_id="TASK-001",
        agent="db",
        status="completed",
        result={
            "count": 3
        },
    )

    assert result.status == "completed"
    assert result.result["count"] == 3


def test_workflow_state():

    state = WorkflowState(
        workflow_id="WF-001",
        user_query="Show top students",
    )

    assert state.status == "planning"
    assert state.task_history == []