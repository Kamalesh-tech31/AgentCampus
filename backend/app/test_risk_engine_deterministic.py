"""
test_risk_engine_deterministic.py — Automated tests for deterministic risk engine.
"""

import pytest
from app.services.pulse.risk_service import (
    calculate_student_risk,
    evaluate_risk,
    DEFAULT_THRESHOLDS,
)


def test_student_level_exact_reason_derivation():
    """
    Verify student reasons are derived factually from their actual data.
    """
    # Student 1: Low CGPA + Low Attendance + Probation + Backlogs
    student_a = {
        "id": "STU-001",
        "rollNumber": "21CS001",
        "name": "Amit Kumar",
        "department": "Computer Science",
        "cgpa": 5.2,
        "attendance": 62.0,
        "status": "Probation",
        "backlogs": 2,
    }
    evaluated_a = calculate_student_risk(student_a, DEFAULT_THRESHOLDS)
    assert evaluated_a["is_at_risk"] is True
    assert evaluated_a["risk_severity"] == "Critical"
    assert evaluated_a["risk_score"] >= 60.0

    reasons_a = evaluated_a["risk_reasons"]
    assert any("CGPA is 5.20" in r for r in reasons_a)
    assert any("Attendance is 62.0%" in r for r in reasons_a)
    assert any("probation" in r.lower() for r in reasons_a)
    assert any("2 active backlog" in r for r in reasons_a)

    # Student 2: Only Low Attendance, Active status, 0 backlogs
    student_b = {
        "id": "STU-002",
        "rollNumber": "21CS002",
        "name": "Bhavna Patel",
        "department": "Computer Science",
        "cgpa": 7.8,
        "attendance": 68.0,
        "status": "Active",
        "backlogs": 0,
    }
    evaluated_b = calculate_student_risk(student_b, DEFAULT_THRESHOLDS)
    assert evaluated_b["is_at_risk"] is True
    assert evaluated_b["risk_severity"] in ("Moderate", "Low")
    reasons_b = evaluated_b["risk_reasons"]
    assert len(reasons_b) == 1
    assert "Attendance is 68.0%" in reasons_b[0]
    assert not any("probation" in r.lower() for r in reasons_b)
    assert not any("backlog" in r.lower() for r in reasons_b)
    assert not any("cgpa" in r.lower() for r in reasons_b)

    # Student 3: Safe student
    student_c = {
        "id": "STU-003",
        "rollNumber": "21CS003",
        "name": "Chetan Sharma",
        "department": "Information Technology",
        "cgpa": 8.9,
        "attendance": 92.0,
        "status": "Active",
        "backlogs": 0,
    }
    evaluated_c = calculate_student_risk(student_c, DEFAULT_THRESHOLDS)
    assert evaluated_c["is_at_risk"] is False
    assert evaluated_c["risk_severity"] == "Safe"
    assert evaluated_c["risk_score"] == 0.0
    assert len(evaluated_c["risk_reasons"]) == 0


def test_evaluate_risk_cohort_aggregation_and_all_records_preservation():
    """
    Verify complete record retention and cohort statistical aggregation.
    """
    records = []
    # Create 89 at-risk students
    for i in range(1, 90):
        records.append({
            "id": f"STU-{i:03d}",
            "rollNumber": f"21CS{i:03d}",
            "name": f"Student {i}",
            "department": "Computer Science" if i % 2 == 0 else "Electronics",
            "cgpa": 5.0 + (i * 0.01),  # all < 6.5
            "attendance": 60.0 + (i * 0.1),  # all < 75.0
            "status": "Probation" if i <= 15 else "Active",
            "backlogs": 1 if i <= 20 else 0,
        })
    # Create 11 safe students
    for i in range(90, 101):
        records.append({
            "id": f"STU-{i:03d}",
            "rollNumber": f"21CS{i:03d}",
            "name": f"Student {i}",
            "department": "Information Technology",
            "cgpa": 8.5,
            "attendance": 90.0,
            "status": "Active",
            "backlogs": 0,
        })

    assert len(records) == 100

    result = evaluate_risk(records)

    # 1. Complete at-risk student records preserved (ALL 89 records)
    at_risk_list = result["at_risk"]
    assert len(at_risk_list) == 89
    assert result["at_risk_count"] == 89
    assert result["safe_count"] == 11
    assert result["at_risk_percentage"] == 89.0

    # 2. Ranking and sorting
    assert at_risk_list[0]["risk_rank"] == 1
    assert at_risk_list[-1]["risk_rank"] == 89

    # 3. Factor frequencies
    factors = result["factor_frequencies"]
    assert factors["Low CGPA (< 6.5)"] == 89
    assert factors["Low Attendance (< 75%)"] == 89
    assert factors["Academic Probation"] == 15
    assert factors["Active Backlogs"] == 20
    assert factors["Multiple Risk Factors (2+)"] == 89

    # 4. Department analysis
    dept_analysis = result["department_analysis"]
    assert len(dept_analysis) >= 2
    cs_dept = next((d for d in dept_analysis if d["department"] == "Computer Science"), None)
    assert cs_dept is not None
    assert cs_dept["at_risk_count"] > 0

    # 5. Dominant pattern & recommendations
    assert "Dual Academic & Attendance Deficit is dominant" in result["dominant_risk_pattern"]
    assert len(result["data_driven_recommendations"]) >= 3
