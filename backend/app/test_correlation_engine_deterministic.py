"""
test_correlation_engine_deterministic.py — Automated tests for deterministic correlation and regression.
"""

import pytest
from app.services.pulse.analytics_tools import calculate_correlation


def test_calculate_correlation_linear_fit_and_statistics():
    """
    Verify Pearson r, linear regression slope/intercept, and scatter points generation.
    """
    records = [
        {"name": "Student 1", "cgpa": 6.0, "attendance": 60.0},
        {"name": "Student 2", "cgpa": 7.0, "attendance": 70.0},
        {"name": "Student 3", "cgpa": 8.0, "attendance": 80.0},
        {"name": "Student 4", "cgpa": 9.0, "attendance": 90.0},
    ]

    res = calculate_correlation(records, field1="attendance", field2="cgpa")

    assert res["analysis_type"] == "correlation_analysis"
    assert res["correlation"] == 1.0
    assert res["r_squared"] == 1.0
    assert res["strength"] == "very strong"
    assert res["direction"] == "positive"
    assert res["sample_size"] == 4

    reg = res["regression"]
    assert reg["slope"] == 0.1
    assert reg["intercept"] == 0.0
    assert "CGPA = (0.1000 × Attendance) + 0.0000" in reg["formula"]

    # Scatter points
    assert len(res["scatter_points"]) == 4
    assert res["scatter_points"][0]["x"] == 60.0
    assert res["scatter_points"][0]["y"] == 6.0

    # Interpretation & causation limitation
    assert "Correlation reflects statistical association and does not imply direct causation" in res["interpretation"]
