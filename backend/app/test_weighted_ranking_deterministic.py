"""
test_weighted_ranking_deterministic.py

Automated unit tests for calculate_weighted_ranking, scale normalization,
and tie handling in Pulse analytics engine.
"""

import pytest
from app.services.pulse.analytics_tools import calculate_weighted_ranking
from app.services.pulse.result_builder import build_pulse_result
from app.contracts.orchestration import OrchestrationMetrics


SAMPLE_STUDENTS = [
    {
        "id": "1",
        "name": "Aarav Sharma",
        "rollNumber": "21CS001",
        "department": "Computer Science",
        "cgpa": 8.82,
        "attendance": 96.0,
        "status": "Active",
    },
    {
        "id": "2",
        "name": "Diya Patel",
        "rollNumber": "21EC002",
        "department": "Electronics",
        "cgpa": 9.50,
        "attendance": 85.0,
        "status": "Active",
    },
    {
        "id": "3",
        "name": "Rohan Iyer",
        "rollNumber": "21ME003",
        "department": "Mechanical",
        "cgpa": 8.90,
        "attendance": 62.0,
        "status": "Active",
    },
    {
        "id": "4",
        "name": "Ananya Sen",
        "rollNumber": "21CS004",
        "department": "Computer Science",
        "cgpa": 8.90,
        "attendance": 62.0,
        "status": "Active",
    },
    {
        "id": "5",
        "name": "Vikram Malhotra",
        "rollNumber": "21EE005",
        "department": "Electrical",
        "cgpa": 7.20,
        "attendance": 90.0,
        "status": "Active",
    },
]


def test_aarav_sharma_weighted_score():
    """
    Verify calculation on Aarav Sharma:
    CGPA 8.82 -> Academic Score = 88.20 -> Academic Contribution (0.80) = 70.56
    Attendance 96 -> Attendance Contribution (0.20) = 19.20
    Weighted Score = 70.56 + 19.20 = 89.76
    """
    res = calculate_weighted_ranking(SAMPLE_STUDENTS, weights={"cgpa": 0.80, "attendance": 0.20}, top_n=5)

    assert "ranking" in res
    ranked = res["ranking"]
    assert len(ranked) == 5

    # Find Aarav Sharma
    aarav = next(r for r in ranked if r["name"] == "Aarav Sharma")
    assert aarav["academic_score"] == 88.20
    assert aarav["academic_contribution"] == 70.56
    assert aarav["attendance_contribution"] == 19.20
    assert aarav["_weighted_score"] == 89.76


def test_diya_patel_score():
    """
    Diya Patel:
    CGPA 9.50 -> Academic Score = 95.00 -> Academic Contrib (0.80) = 76.00
    Attendance 85 -> Attendance Contrib (0.20) = 17.00
    Weighted Score = 76.00 + 17.00 = 93.00
    """
    res = calculate_weighted_ranking(SAMPLE_STUDENTS, weights={"cgpa": 0.80, "attendance": 0.20}, top_n=5)
    diya = next(r for r in res["ranking"] if r["name"] == "Diya Patel")
    assert diya["academic_score"] == 95.00
    assert diya["academic_contribution"] == 76.00
    assert diya["attendance_contribution"] == 17.00
    assert diya["_weighted_score"] == 93.00
    assert diya["rank"] == 1


def test_tie_detection_and_resolution():
    """
    Rohan Iyer and Ananya Sen have identical scores:
    CGPA 8.90, Attendance 62.0 -> Score = 83.60
    Both should be detected as tied.
    Tie-breaking rule should order them deterministically.
    """
    res = calculate_weighted_ranking(SAMPLE_STUDENTS, weights={"cgpa": 0.80, "attendance": 0.20}, top_n=5)

    ties = res.get("ties", [])
    assert len(ties) >= 1
    tie_83_6 = next(t for t in ties if abs(t["weighted_score"] - 83.60) < 0.01)
    assert tie_83_6["count"] == 2
    assert any("Ananya Sen" in s for s in tie_83_6["students"])
    assert any("Rohan Iyer" in s for s in tie_83_6["students"])


def test_custom_weights():
    """
    Test 50% CGPA and 50% Attendance.
    Aarav: (88.2 * 0.5 = 44.1) + (96 * 0.5 = 48) = 92.10
    """
    res = calculate_weighted_ranking(SAMPLE_STUDENTS, weights={"cgpa": 0.50, "attendance": 0.50}, top_n=5)
    aarav = next(r for r in res["ranking"] if r["name"] == "Aarav Sharma")
    assert aarav["_weighted_score"] == 92.10


def test_empty_records():
    res = calculate_weighted_ranking([], weights={"cgpa": 0.80, "attendance": 0.20}, top_n=10)
    assert res["total_records"] == 0
    assert res["ranking"] == []
