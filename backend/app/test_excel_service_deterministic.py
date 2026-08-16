"""
test_excel_service_deterministic.py — Unit test for Excel export with Pulse tables and charts.
"""

import os
import pytest
from app.services.output.excel_service import generate_excel


def test_generate_excel_with_pulse_at_risk_data(tmp_path):
    records = [{"id": "1", "rollNumber": "21CS001", "name": "Alice", "cgpa": 5.4, "attendance": 65.0}]
    pulse_data = {
        "analysis_type": "risk_analysis",
        "at_risk": [
            {
                "rollNumber": "21CS001",
                "name": "Alice",
                "department": "Computer Science",
                "cgpa": 5.4,
                "attendance": 65.0,
                "risk_score": 62.0,
                "risk_severity": "Critical",
                "risk_reasons_str": "CGPA is 5.40 (< 6.50), Attendance is 65.0% (< 75.0%)",
            }
        ],
        "department_analysis": [
            {
                "department": "Computer Science",
                "total_students": 1,
                "at_risk_count": 1,
                "risk_percentage": 100.0,
                "avg_cgpa": 5.4,
                "avg_attendance": 65.0,
            }
        ],
    }

    res = generate_excel(
        records=records,
        metrics=None,
        insight="Alice is critically at risk.",
        file_stem="test_risk_report",
        pulse_data=pulse_data,
    )

    assert "file_path" in res
    assert os.path.exists(res["file_path"])
    assert res["file_name"].endswith(".xlsx")
    assert res["sheet_count"] >= 2
