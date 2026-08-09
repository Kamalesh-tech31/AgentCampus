import pytest
from app.mother.mother_agent import MotherAgent
from app.orchestration.adapter import CrewAdapter
from app.orchestration.crew_flow import AgentCampusFlow
from app.contracts import OrchestrationEvent, DynamicPlan


def test_crewai_executes_exact_mother_plan_read_query():
    mother = MotherAgent()
    workflow = mother.create_workflow("Show top 10 Computer Science students")

    # Authoritative MotherAgent plan for read query: input -> db -> output
    assert workflow.request_type == "read"
    assert [s.agent for s in workflow.plan.steps] == ["input", "db", "output"]

    # Execute workflow using CrewAdapter / CrewAI Flow
    adapter = CrewAdapter()
    result_workflow = adapter.run_workflow(workflow)

    assert result_workflow.status == "completed"
    executed_agents = [t.agent for t in result_workflow.task_history if t.status == "completed"]
    assert executed_agents == ["input", "db", "output"]


def test_analytics_not_executed_when_absent_from_mother_plan():
    mother = MotherAgent()

    # Read query prompt has NO analytics requirement
    workflow = mother.create_workflow("Show list of students in Mechanical department")
    assert "analytics" not in [s.agent for s in workflow.plan.steps]

    # Execute via CrewAI Flow
    adapter = CrewAdapter()
    result_workflow = adapter.run_workflow(workflow)

    assert result_workflow.status == "completed"
    executed_agents = [t.agent for t in result_workflow.task_history if t.status == "completed"]
    assert "analytics" not in executed_agents
    assert executed_agents == ["input", "db", "output"]


def test_crewai_executes_analytics_when_present_in_mother_plan():
    mother = MotherAgent()

    # Analytics query prompt
    workflow = mother.create_workflow("Compute average CGPA and highest CGPA for AI & ML")
    assert "analytics" in [s.agent for s in workflow.plan.steps]

    adapter = CrewAdapter()
    result_workflow = adapter.run_workflow(workflow)

    assert result_workflow.status == "completed"
    executed_agents = [t.agent for t in result_workflow.task_history if t.status == "completed"]
    assert executed_agents == ["input", "db", "analytics", "output"]


def test_mother_to_crewadapter_to_crewai_contract_events():
    mother = MotherAgent()
    workflow = mother.create_workflow("Find students with attendance > 90")

    # Execute via MotherAgent delegating to CrewAdapter
    result_workflow = mother.execute_workflow(workflow, use_crew=True)

    assert result_workflow.status == "completed"
    assert result_workflow.final_result is not None

    # Verify every event is a valid contract-compliant OrchestrationEvent
    assert len(result_workflow.events) > 0
    for event in result_workflow.events:
        assert isinstance(event, OrchestrationEvent)
        # Verify JSON dump complies with Pydantic contract
        dumped = event.model_dump(mode="json", by_alias=True)
        assert "type" in dumped
        assert "taskId" in dumped

    event_types = [e.type for e in result_workflow.events]
    assert "TASK_CREATED" in event_types
    assert "PLAN_UPDATED" in event_types
    assert "AGENT_STARTED" in event_types
    assert "AGENT_COMPLETED" in event_types
    assert "RESULT_READY" in event_types
