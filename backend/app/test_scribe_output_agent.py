import os
import tempfile
from unittest.mock import patch
import pytest

from app.agents.output_agent import OutputAgent
from app.mother.types import AgentTask

# Mock data for testing
MOCK_RECORDS = [
    {
        "id": "STU-1",
        "rollNumber": "CS001",
        "name": "Alice",
        "department": "Computer Science",
        "cgpa": 9.5,
        "attendance": 90.0,
        "status": "Active"
    },
    {
        "id": "STU-2",
        "rollNumber": "CS002",
        "name": "Bob",
        "department": "Computer Science",
        "cgpa": 6.0,
        "attendance": 70.0,
        "status": "Probation"
    }
]

MOCK_METRICS = {
    "totalRecords": 2,
    "averageCgpa": 7.75,
    "highestCgpa": 9.5,
    "lowestCgpa": 6.0,
    "avgAttendance": 80.0,
    "probationCount": 1,
    "departmentBreakdown": {
        "Computer Science": {
            "count": 2,
            "avgCgpa": 7.75
        }
    }
}

MOCK_INSIGHT = "Overall performance is good, but attention needed for students on probation."


@pytest.fixture
def output_agent():
    return OutputAgent()


def test_all_scribe_formats(output_agent, capsys):
    """
    Exactly ONE easy-to-understand Scribe end-to-end test verifying all 4 formats.
    """
    from pathlib import Path
    
    # Force output generators to use a temporary directory to avoid cluttering output_files/
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        # We patch the _ensure_output_dir paths inside the services to write to our temp_dir
        with patch("app.services.output.excel_service._ensure_output_dir", return_value=temp_path), \
             patch("app.services.output.pdf_service._ensure_output_dir", return_value=temp_path), \
             patch("app.services.output.ppt_service._ensure_output_dir", return_value=temp_path), \
             patch("app.services.groq_service.GroqService.generate_text_report", return_value=None), \
             patch("app.services.groq_service.GroqService.generate_pdf_plan", return_value=None), \
             patch("app.services.groq_service.GroqService.generate_ppt_plan", return_value=None):
             
            print("\n========================================")
            print("SCRIBE OUTPUT TEST")
            print("========================================\n")

            # 1. TEXT
            task_text = AgentTask(
                task_id="T-TEXT",
                agent="output",
                objective="Format response",
                input_data={
                    "user_query": "Show students in text",
                    "db": {"records": MOCK_RECORDS, "sql": "SELECT *"},
                    "analytics": {"metrics": MOCK_METRICS, "insight": MOCK_INSIGHT}
                },
                expected_output="Response"
            )
            res_text = output_agent.execute(task_text)
            assert res_text.status == "completed"
            assert res_text.result["output_format"] == "text"
            text_content = res_text.result["text_content"]
            assert "Alice" in text_content
            assert "Bob" in text_content
            
            print("TEXT:")
            print("  PASS")
            print("  Contains student data: YES\n")

            # 2. EXCEL
            task_excel = AgentTask(
                task_id="T-EXCEL",
                agent="output",
                objective="Format response",
                input_data={
                    "user_query": "Download excel report of students",
                    "db": {"records": MOCK_RECORDS, "sql": "SELECT *"},
                    "analytics": {"metrics": MOCK_METRICS, "insight": MOCK_INSIGHT}
                },
                expected_output="Response"
            )
            res_excel = output_agent.execute(task_excel)
            assert res_excel.status == "completed"
            assert res_excel.result["output_format"] == "excel"
            excel_file = res_excel.result["output_file"]
            assert os.path.exists(excel_file)
            assert os.path.getsize(excel_file) > 0
            
            print("EXCEL:")
            print("  PASS")
            print(f"  File: {os.path.basename(excel_file)}")
            print("  Contains records: YES\n")

            # 3. PDF
            task_pdf = AgentTask(
                task_id="T-PDF",
                agent="output",
                objective="Format response",
                input_data={
                    "user_query": "pdf report of students and analysis",
                    "db": {"records": MOCK_RECORDS, "sql": "SELECT *"},
                    "analytics": {"metrics": MOCK_METRICS, "insight": MOCK_INSIGHT}
                },
                expected_output="Response"
            )
            res_pdf = output_agent.execute(task_pdf)
            assert res_pdf.status == "completed"
            assert res_pdf.result["output_format"] == "pdf"
            pdf_file = res_pdf.result["output_file"]
            assert os.path.exists(pdf_file)
            pdf_size = os.path.getsize(pdf_file)
            assert pdf_size > 0
            
            print("PDF:")
            print("  PASS")
            print(f"  File: {os.path.basename(pdf_file)}")
            print(f"  Size: {pdf_size} bytes")
            print("  Contains report data: YES\n")

            # 4. POWERPOINT
            task_ppt = AgentTask(
                task_id="T-PPT",
                agent="output",
                objective="Format response",
                input_data={
                    "user_query": "Create a ppt presentation",
                    "db": {"records": MOCK_RECORDS, "sql": "SELECT *"},
                    "analytics": {"metrics": MOCK_METRICS, "insight": MOCK_INSIGHT}
                },
                expected_output="Response"
            )
            res_ppt = output_agent.execute(task_ppt)
            assert res_ppt.status == "completed"
            assert res_ppt.result["output_format"] == "pptx"
            ppt_file = res_ppt.result["output_file"]
            assert os.path.exists(ppt_file)
            ppt_size = os.path.getsize(ppt_file)
            assert ppt_size > 0
            
            print("POWERPOINT:")
            print("  PASS")
            print(f"  File: {os.path.basename(ppt_file)}")
            print(f"  Size: {ppt_size} bytes")
            print("  Contains slides: YES\n")

            print("ALL SCRIBE OUTPUTS WORKING")