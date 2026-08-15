import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from app.mother.mother_agent import MotherAgent
from app.orchestration.adapter import CrewAdapter
from app.contracts import StudentRecord, OrchestrationResult, OrchestrationMetrics


@pytest.fixture
def mother():
    return MotherAgent()


def test_e2e_flow_read_query_no_pulse(mother):
    """
    Scenario 1:
    Request: 'Show all CSE students.'
    Expected Flow: Mother -> Input -> DB -> Scribe -> Text
    Pulse must NOT run.
    """
    wf = mother.create_workflow("Show all CSE students.")
    assert wf.request_type == "read"
    assert [s.agent for s in wf.plan.steps] == ["input", "db", "output"]

    result_wf = mother.execute_workflow(wf)
    assert result_wf.status == "completed"

    executed_agents = [t.agent for t in result_wf.task_history if t.status == "completed"]
    assert executed_agents == ["input", "db", "output"]
    assert "analytics" not in executed_agents

    # Verify final result structure
    res = result_wf.final_result
    assert isinstance(res, OrchestrationResult)
    assert res.output_format == "text"
    assert res.data is not None
    assert len(res.data) > 0
    assert all(s.department == "Computer Science" for s in res.data)


def test_e2e_flow_analytics_query_text(mother):
    """
    Scenario 2:
    Request: 'Calculate the average CGPA of CSE students.'
    Expected Flow: Mother -> Input -> DB -> Pulse -> Scribe -> Text
    """
    wf = mother.create_workflow("Calculate the average CGPA of CSE students.")
    assert wf.request_type == "analytics"
    assert [s.agent for s in wf.plan.steps] == ["input", "db", "analytics", "output"]

    result_wf = mother.execute_workflow(wf)
    assert result_wf.status == "completed"

    executed_agents = [t.agent for t in result_wf.task_history if t.status == "completed"]
    assert executed_agents == ["input", "db", "analytics", "output"]

    # Verify Pulse analysis ran and data moved to Scribe
    pulse_res = result_wf.results.get("analytics", {})
    assert "metrics" in pulse_res
    assert "summary" in pulse_res
    assert pulse_res.get("records_analyzed", 0) > 0

    res = result_wf.final_result
    assert res.output_format == "text"
    assert res.metrics is not None
    assert res.metrics.average_cgpa is not None
    assert res.metrics.average_cgpa > 0


def test_e2e_flow_at_risk_query_text(mother):
    """
    Scenario 3:
    Request: 'Find students who are academically at risk.'
    Expected Flow: Mother -> Input -> DB -> Pulse -> Scribe -> Text
    """
    wf = mother.create_workflow("Find students who are academically at risk.")
    assert wf.request_type == "analytics"
    assert [s.agent for s in wf.plan.steps] == ["input", "db", "analytics", "output"]

    result_wf = mother.execute_workflow(wf)
    assert result_wf.status == "completed"

    executed_agents = [t.agent for t in result_wf.task_history if t.status == "completed"]
    assert executed_agents == ["input", "db", "analytics", "output"]

    pulse_res = result_wf.results.get("analytics", {})
    assert "tables" in pulse_res or "findings" in pulse_res

    res = result_wf.final_result
    assert res.output_format == "text"
    assert "at_risk" in str(pulse_res) or "probation" in str(pulse_res).lower() or res.metrics is not None


def test_e2e_flow_at_risk_pdf_report(mother):
    """
    Scenario 4:
    Request: 'Create a PDF report showing students who are academically at risk.'
    Expected Flow: Mother -> Input -> DB -> Pulse -> Scribe -> PDF
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        with patch("app.services.output.pdf_service._ensure_output_dir", return_value=temp_path):
            wf = mother.create_workflow("Create a PDF report showing students who are academically at risk.")
            assert wf.request_type == "analytics"
            assert [s.agent for s in wf.plan.steps] == ["input", "db", "analytics", "output"]

            result_wf = mother.execute_workflow(wf)
            assert result_wf.status == "completed"

            executed_agents = [t.agent for t in result_wf.task_history if t.status == "completed"]
            assert executed_agents == ["input", "db", "analytics", "output"]

            res = result_wf.final_result
            assert res.output_format == "pdf"
            assert res.output_file is not None
            assert res.output_file.endswith(".pdf")
            assert os.path.exists(res.output_file)
            assert os.path.getsize(res.output_file) > 0


def test_e2e_flow_excel_export_no_pulse(mother):
    """
    Scenario 5:
    Request: 'Create an Excel file containing all CSE students.'
    Expected Flow: Mother -> Input -> DB -> Scribe -> Excel
    Pulse should not run unless analysis is required.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        with patch("app.services.output.excel_service._ensure_output_dir", return_value=temp_path):
            wf = mother.create_workflow("Create an Excel file containing all CSE students.")
            assert wf.request_type == "read"
            assert [s.agent for s in wf.plan.steps] == ["input", "db", "output"]

            result_wf = mother.execute_workflow(wf)
            assert result_wf.status == "completed"

            executed_agents = [t.agent for t in result_wf.task_history if t.status == "completed"]
            assert executed_agents == ["input", "db", "output"]
            assert "analytics" not in executed_agents

            res = result_wf.final_result
            assert res.output_format == "excel"
            assert res.output_file is not None
            assert res.output_file.endswith(".xlsx")
            assert os.path.exists(res.output_file)
            assert os.path.getsize(res.output_file) > 0


def test_e2e_flow_ppt_presentation(mother):
    """
    Scenario 6:
    Request: 'Create a PowerPoint presentation analyzing student performance.'
    Expected Flow: Mother -> Input -> DB -> Pulse -> Scribe -> PPT
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        with patch("app.services.output.ppt_service._ensure_output_dir", return_value=temp_path):
            wf = mother.create_workflow("Create a PowerPoint presentation analyzing student performance.")
            assert wf.request_type == "analytics"
            assert [s.agent for s in wf.plan.steps] == ["input", "db", "analytics", "output"]

            result_wf = mother.execute_workflow(wf)
            assert result_wf.status == "completed"

            executed_agents = [t.agent for t in result_wf.task_history if t.status == "completed"]
            assert executed_agents == ["input", "db", "analytics", "output"]

            res = result_wf.final_result
            assert res.output_format == "pptx"
            assert res.output_file is not None
            assert res.output_file.endswith(".pptx")
            assert os.path.exists(res.output_file)
            assert os.path.getsize(res.output_file) > 0


def test_e2e_flow_via_crew_adapter(mother):
    """
    Scenario 7:
    Verify execution via CrewAdapter / Flow abstraction for complete Mother integration.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        with patch("app.services.output.pdf_service._ensure_output_dir", return_value=temp_path):
            wf = mother.create_workflow("Analyze the academic performance of CSE students and create a PDF report.")
            adapter = CrewAdapter()
            result_wf = adapter.run_workflow(wf)

            assert result_wf.status == "completed"
            executed_agents = [t.agent for t in result_wf.task_history if t.status == "completed"]
            assert executed_agents == ["input", "db", "analytics", "output"]

            res = result_wf.final_result
            assert res.output_format == "pdf"
            assert res.output_file is not None
            assert os.path.exists(res.output_file)
