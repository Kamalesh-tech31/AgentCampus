import pytest
from app.mother.mother_agent import MotherAgent
from app.agents.input_agent import InputAgent
from app.agents.db_agent import DBAgent
from app.agents.analytics_agent import AnalyticsAgent
from app.agents.output_agent import OutputAgent
from app.mother.types import AgentTask
from app.contracts import StudentRecord, OrchestrationMetrics, OrchestrationResult


def test_individual_input_agent():
    agent = InputAgent()
    task = AgentTask(
        task_id="T1",
        agent="input",
        objective="Parse intent",
        input_data={"user_query": "Show top 10 Computer Science students"},
        expected_output="Structured intent",
    )
    res = agent.execute(task)
    assert res.status == "completed"
    intent = res.result.get("structured_intent", {})
    assert intent.get("department") == "Computer Science"
    assert intent.get("limit") == 10


def test_individual_db_agent():
    agent = DBAgent()
    task = AgentTask(
        task_id="T2",
        agent="db",
        objective="Query students",
        input_data={
            "input": {
                "structured_intent": {
                    "department": "Computer Science",
                    "min_cgpa": 9.0,
                    "limit": 5,
                }
            }
        },
        expected_output="Records",
    )
    res = agent.execute(task)
    assert res.status == "completed"
    assert "sql" in res.result
    assert "SELECT * FROM students WHERE department = 'Computer Science'" in res.result["sql"]
    assert len(res.result["records"]) > 0
    # Verify records validate as StudentRecord contract
    for r in res.result["records"]:
        StudentRecord.model_validate(r)


def test_individual_analytics_agent():
    agent = AnalyticsAgent()
    records = [
        {"id": "S1", "rollNumber": "1", "name": "A", "department": "Computer Science", "cgpa": 9.5, "semester": 8, "attendance": 90, "email": "a@c.edu", "status": "Active", "backlogs": 0},
        {"id": "S2", "rollNumber": "2", "name": "B", "department": "Computer Science", "cgpa": 8.5, "semester": 8, "attendance": 80, "email": "b@c.edu", "status": "Active", "backlogs": 0},
    ]
    task = AgentTask(
        task_id="T3",
        agent="analytics",
        objective="Compute metrics",
        input_data={"db": {"records": records}},
        expected_output="Metrics",
    )
    res = agent.execute(task)
    assert res.status == "completed"
    metrics_raw = res.result.get("metrics")
    metrics = OrchestrationMetrics.model_validate(metrics_raw)
    assert metrics.total_records == 2
    assert metrics.average_cgpa == 9.0
    assert metrics.highest_cgpa == 9.5


def test_individual_output_agent():
    agent = OutputAgent()
    records = [
        {"id": "S1", "rollNumber": "1", "name": "A", "department": "Computer Science", "cgpa": 9.5, "semester": 8, "attendance": 90, "email": "a@c.edu", "status": "Active", "backlogs": 0}
    ]
    metrics = {"totalRecords": 1, "averageCgpa": 9.5, "highestCgpa": 9.5}
    task = AgentTask(
        task_id="T4",
        agent="output",
        objective="Format response",
        input_data={"db": {"records": records, "sql": "SELECT * FROM students;"}, "analytics": {"metrics": metrics}},
        expected_output="Response",
    )
    res = agent.execute(task)
    assert res.status == "completed"
    result_raw = res.result.get("result")
    result = OrchestrationResult.model_validate(result_raw)
    assert result.affected_count == 1
    assert result.metrics is not None
    assert result.metrics.average_cgpa == 9.5


def test_full_read_workflow_with_mock_agents():
    mother = MotherAgent()
    workflow = mother.create_workflow("Show Computer Science students")

    # Read workflow intent
    assert workflow.request_type == "read"
    assert [s.agent for s in workflow.plan.steps] == ["input", "db", "output"]

    # Execute workflow using MotherAgent and mock agents
    result_workflow = mother.execute_workflow(workflow)

    assert result_workflow.status == "completed"
    executed_agents = [t.agent for t in result_workflow.task_history if t.status == "completed"]

    # Verify execution order: Input -> DB -> Output (Analytics NOT executed)
    assert executed_agents == ["input", "db", "output"]
    assert "analytics" not in executed_agents

    # Verify final result structure
    assert result_workflow.final_result is not None
    res = result_workflow.final_result
    assert res.query_executed is not None
    assert "SELECT * FROM students WHERE department = 'Computer Science'" in res.query_executed


def test_full_analytics_workflow_with_mock_agents():
    mother = MotherAgent()
    workflow = mother.create_workflow("Compute average CGPA and highest CGPA for Data Science")

    assert workflow.request_type == "analytics"
    assert [s.agent for s in workflow.plan.steps] == ["input", "db", "analytics", "output"]

    result_workflow = mother.execute_workflow(workflow)

    assert result_workflow.status == "completed"
    executed_agents = [t.agent for t in result_workflow.task_history if t.status == "completed"]

    # Verify execution order: Input -> DB -> Analytics -> Output
    assert executed_agents == ["input", "db", "analytics", "output"]

    # Verify analytics output results
    assert "analytics" in result_workflow.results
    analytics_out = result_workflow.results["analytics"]
    assert "metrics" in analytics_out
    metrics = OrchestrationMetrics.model_validate(analytics_out["metrics"])
    assert metrics.total_records > 0
    assert metrics.average_cgpa is not None
