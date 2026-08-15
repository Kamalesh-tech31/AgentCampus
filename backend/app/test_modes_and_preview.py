import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mother.mother_agent import MotherAgent
from app.services.student_service import student_service
from app.contracts import OrchestrationResult
from app.db.schema_registry import get_database_preview, resolve_column_name


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mother():
    return MotherAgent()


def test_explore_mode_no_pulse(mother, client):
    """
    Explore Mode:
    - User Query: 'Show the top 10 CSE students'
    - Mode: 'explore'
    - Flow: Mother -> Input -> DB -> Scribe (Text)
    - Pulse must NOT run.
    """
    # 1. Via MotherAgent directly
    wf = mother.create_workflow("Show the top 10 CSE students", mode="explore")
    assert wf.mode == "explore"
    assert wf.request_type == "read"
    assert [s.agent for s in wf.plan.steps] == ["input", "db", "output"]

    result_wf = mother.execute_workflow(wf)
    assert result_wf.status == "completed"
    executed = [t.agent for t in result_wf.task_history if t.status == "completed"]
    assert executed == ["input", "db", "output"]
    assert "analytics" not in executed

    res = result_wf.final_result
    assert res.mode == "explore"
    assert res.data is not None
    assert len(res.data) > 0

    # 2. Via Synchronous HTTP API
    resp = client.post("/api/orchestrate", json={
        "mode": "explore",
        "user_query": "Show the top 10 CSE students"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "explore"
    assert data["outputFormat"] == "text"
    assert len(data["data"]) > 0


def test_modify_mode_safe_mutation_and_live_refresh(mother, client):
    """
    Modify Mode (Safe single record update):
    - User Query: "Change Rahul's CGPA to 9.2"
    - Mode: 'modify'
    - Flow: Mother -> Input -> DB -> Scribe
    - Mutation executes without requiring confirmation.
    - Live Database Preview immediately reflects the new CGPA.
    """
    resp = client.post("/api/orchestrate", json={
        "mode": "modify",
        "user_query": "Change Rahul's CGPA to 9.2",
        "confirmed": False
    })
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["mode"] == "modify"
    assert res_data.get("requiresConfirmation") is False

    # Check that live DB / student service state is updated immediately
    students = student_service.get_students()
    rahul = next((s for s in students if "rahul" in s.name.lower()), None)
    assert rahul is not None
    assert rahul.cgpa == 9.2

    # Verify that GET /api/database/preview also shows Rahul with 9.2
    preview_resp = client.get("/api/database/preview")
    assert preview_resp.status_code == 200
    preview_data = preview_resp.json()
    students_table = next((t for t in preview_data["tables"] if t["name"] == "students"), None)
    assert students_table is not None
    assert students_table["rowCount"] > 0


def test_modify_mode_destructive_requires_confirmation(mother, client):
    """
    Modify Mode (Destructive bulk deletion):
    - User Query: 'Delete all students with CGPA below 5'
    - Mode: 'modify', confirmed=False
    - Backend must return requires_confirmation=True with affected_records count and warning.
    - When user confirms (confirmed=True), mutation proceeds.
    """
    # 1. Unconfirmed request
    resp_unconfirmed = client.post("/api/orchestrate", json={
        "mode": "modify",
        "user_query": "Delete all students with CGPA below 5",
        "confirmed": False
    })
    assert resp_unconfirmed.status_code == 200
    data_unconfirmed = resp_unconfirmed.json()
    assert data_unconfirmed["mode"] == "modify"
    assert data_unconfirmed["requiresConfirmation"] is True
    assert data_unconfirmed["confirmationDetails"] is not None
    assert "affected_records" in data_unconfirmed["confirmationDetails"]
    assert "warning" in data_unconfirmed["confirmationDetails"]

    # 2. Confirmed request
    resp_confirmed = client.post("/api/orchestrate", json={
        "mode": "modify",
        "user_query": "Delete all students with CGPA below 5",
        "confirmed": True
    })
    assert resp_confirmed.status_code == 200
    data_confirmed = resp_confirmed.json()
    assert data_confirmed["requiresConfirmation"] is False


def test_analyze_mode_runs_pulse_and_scribe(mother, client):
    """
    Analyze Mode:
    - User Query: 'Rank the top 10 using 80% marks and 20% LeetCode count'
    - Mode: 'analyze'
    - Flow: Mother -> Input -> DB -> Pulse -> Scribe
    - Pulse performs ranking analysis and Scribe formats output.
    """
    resp = client.post("/api/orchestrate", json={
        "mode": "analyze",
        "user_query": "Rank the top 10 using 80% marks and 20% LeetCode count"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "analyze"
    assert data["execution"] is not None
    agents_executed = [a["agent"] for a in data["execution"]["agents"]]
    assert "analytics" in agents_executed
    assert "output" in agents_executed


def test_analyze_mode_pdf_generation(client):
    """
    Analyze Mode with PDF Request:
    - User Query: 'Create a detailed report explaining the academic performance'
    - Mode: 'analyze'
    - Output format must be 'pdf' and output_file must exist.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        with patch("app.services.output.pdf_service._ensure_output_dir", return_value=temp_path):
            resp = client.post("/api/orchestrate", json={
                "mode": "analyze",
                "user_query": "Create a detailed report explaining the academic performance in PDF"
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["mode"] == "analyze"
            assert data["outputFormat"] == "pdf"
            assert data["outputFile"] is not None
            assert os.path.exists(data["outputFile"])
            assert os.path.getsize(data["outputFile"]) > 0


def test_database_preview_and_tables_api(client):
    """
    Database Preview API:
    - GET /api/database/preview returns tables, columns with types, sample records, and row count.
    - GET /api/database/tables returns list of table names.
    """
    resp = client.get("/api/database/preview?sample_size=3")
    assert resp.status_code == 200
    data = resp.json()
    assert "tables" in data
    assert len(data["tables"]) > 0

    students_tbl = next((t for t in data["tables"] if t["name"] == "students"), None)
    assert students_tbl is not None
    assert len(students_tbl["columns"]) > 0
    assert any(c["name"] in ("cgpa", "name", "department") for c in students_tbl["columns"])
    assert len(students_tbl["sampleRecords"]) <= 3
    assert students_tbl["rowCount"] > 0

    tables_resp = client.get("/api/database/tables")
    assert tables_resp.status_code == 200
    tables = tables_resp.json()
    assert "students" in tables


def test_column_name_validation_and_suggestions(client):
    """
    Column Name Validation API:
    - Exact column returns valid=True
    - Domain synonyms / fuzzy match return valid=False with suggestion
    """
    # 1. Exact match
    resp1 = client.post("/api/database/validate-column", json={
        "table": "students",
        "column": "cgpa"
    })
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["valid"] is True
    assert data1["resolvedColumn"] == "cgpa"

    # 2. Synonym match 'marks' -> 'cgpa'
    resp2 = client.post("/api/database/validate-column", json={
        "table": "students",
        "column": "marks"
    })
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["valid"] is False
    assert data2["suggestion"] == "cgpa"

    # 3. Synonym match 'dept' -> 'department'
    resp3 = client.post("/api/database/validate-column", json={
        "table": "students",
        "column": "dept"
    })
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["valid"] is False
    assert data3["suggestion"] == "department"


def test_file_download_endpoint(client):
    """
    File Download API:
    - GET /api/files/download/{file_name} serves files from output_files directory.
    """
    out_dir = Path(__file__).resolve().parent.parent / "output_files"
    out_dir.mkdir(parents=True, exist_ok=True)
    dummy_file = out_dir / "test_download.pdf"
    dummy_file.write_bytes(b"%PDF-1.4 dummy pdf content")

    try:
        resp = client.get("/api/files/download/test_download.pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content == b"%PDF-1.4 dummy pdf content"

        # Not found test
        resp_404 = client.get("/api/files/download/non_existent.pdf")
        assert resp_404.status_code == 404
    finally:
        if dummy_file.exists():
            dummy_file.unlink()
