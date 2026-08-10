import pytest
from app.mother.mother_agent import MotherAgent
from app.agents.registry import AgentRegistry
from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult


def test_read_workflow_execution():
    mother = MotherAgent()
    workflow = mother.create_workflow("Show top 10 CS students")

    assert workflow.request_type == "read"
    assert workflow.plan is not None
    assert len(workflow.plan.steps) == 3
    assert [s.agent for s in workflow.plan.steps] == ["input", "db", "output"]

    # Execute workflow loop
    result_workflow = mother.execute_workflow(workflow)

    assert result_workflow.status == "completed"
    execution_order = [t.agent for t in result_workflow.task_history]
    assert execution_order == ["input", "db", "output"]
    assert result_workflow.final_result is not None
    assert "summary" in result_workflow.final_result.model_dump(by_alias=True)

    event_types = [e.type for e in result_workflow.events]
    assert "TASK_CREATED" in event_types
    assert "PLAN_UPDATED" in event_types
    assert "RESULT_READY" in event_types


def test_analytics_workflow_execution():
    mother = MotherAgent()
    workflow = mother.create_workflow("Calculate average CGPA and statistics for Data Science")

    assert workflow.request_type == "analytics"
    assert [s.agent for s in workflow.plan.steps] == ["input", "db", "analytics", "output"]

    result_workflow = mother.execute_workflow(workflow)

    assert result_workflow.status == "completed"
    execution_order = [t.agent for t in result_workflow.task_history]
    assert execution_order == ["input", "db", "analytics", "output"]


def test_write_workflow_execution():
    mother = MotherAgent()
    workflow = mother.create_workflow("Update student CGPA for 21CS001 to 9.9")

    assert workflow.request_type == "write"
    assert [s.agent for s in workflow.plan.steps] == ["input", "db", "output"]

    result_workflow = mother.execute_workflow(workflow)

    assert result_workflow.status == "completed"
    execution_order = [t.agent for t in result_workflow.task_history]
    assert execution_order == ["input", "db", "output"]


def test_unknown_agent_handling():
    mother = MotherAgent()
    workflow = mother.create_workflow("Show students")

    # Override next agent to an unregistered agent
    mother.determine_next_agent = lambda wf: "nonexistent_agent"

    result_workflow = mother.execute_workflow(workflow)

    assert result_workflow.status == "failed"
    failed_events = [e for e in result_workflow.events if e.type == "AGENT_FAILED"]
    assert len(failed_events) > 0
    assert "Unknown agent" in failed_events[0].message


class FailingAgent(BaseAgent):
    name = "db"

    def execute(self, task: AgentTask) -> AgentResult:
        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status="failed",
            error="Database connection error",
        )


def test_agent_failure_handling():
    registry = AgentRegistry()

    class CustomRegistry(AgentRegistry):
        def get(self, agent_name: str) -> BaseAgent:
            if agent_name == "db":
                return FailingAgent()
            return super().get(agent_name)

    mother = MotherAgent(registry=CustomRegistry())
    workflow = mother.create_workflow("Show students")

    result_workflow = mother.execute_workflow(workflow)

    assert result_workflow.status == "failed"
    failed_events = [e for e in result_workflow.events if e.type == "AGENT_FAILED"]
    assert len(failed_events) > 0
    assert "Database connection error" in failed_events[0].message


def test_status_contract_alignment():
    mother = MotherAgent()
    workflow = mother.create_workflow("Show students")
    result_workflow = mother.execute_workflow(workflow)

    assert result_workflow.status == "completed"
    for step in result_workflow.plan.steps:
        assert step.status == "complete"
