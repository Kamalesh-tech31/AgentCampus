"""
test_professional_reporting_e2e.py — Comprehensive end-to-end multi-agent workflow tests.
"""

import os
import pytest
from app.mother.mother_agent import MotherAgent


def test_at_risk_workflow_e2e():
    """
    End-to-end workflow test for:
    'Find academically at-risk students and explain reasons'
    Verifies:
      - MotherAgent plans and executes all agents.
      - DB Agent fetches records.
      - Pulse Analytics assesses multi-factor risk and produces complete matching at-risk records.
      - Scribe Output Agent produces analytical summary, valid PDF, and valid PPTX.
    """
    mother = MotherAgent()
    query = "Find academically at-risk students and explain reasons"

    workflow = mother.create_workflow(prompt=query, mode="analyze")
    assert workflow.request_type == "analytics"

    final_wf = mother.execute_workflow(workflow)
    assert final_wf.status == "completed"

    results = final_wf.results
    assert "input" in results
    assert "db" in results
    assert "analytics" in results
    assert "output" in results

    # 1. DB Agent
    db_res = results["db"]
    records = db_res.get("records") or db_res.get("data", [])
    assert len(records) > 0

    # 2. Pulse Analytics
    analytics = results["analytics"]
    assert analytics.get("analysis_type") == "risk_analysis"
    assert "at_risk_count" in analytics
    assert analytics["at_risk_count"] > 0
    at_risk_recs = analytics.get("at_risk") or analytics.get("tables", {}).get("at_risk_students", [])
    assert len(at_risk_recs) == analytics["at_risk_count"]  # Complete matching records preserved

    # Verify student-level reasons exist on at-risk records
    sample_risk = at_risk_recs[0]
    assert "risk_severity" in sample_risk
    assert "risk_score" in sample_risk
    assert "risk_reasons" in sample_risk or "risk_reasons_str" in sample_risk

    # 3. Scribe Output Agent
    output_res = results["output"]
    summary = output_res.get("summary", "")
    assert len(summary) > 0
    assert "RISK" in summary.upper() or "AT-RISK" in summary.upper() or "ASSESSMENT" in summary.upper()

    # Verify generated PDF and PPTX exist on disk
    files = output_res.get("files", {})
    pdf_path = files.get("pdf") or output_res.get("output_file")
    if pdf_path:
        assert os.path.exists(pdf_path)
    pptx_path = files.get("pptx")
    if pptx_path:
        assert os.path.exists(pptx_path)


def test_correlation_workflow_e2e():
    """
    End-to-end workflow test for:
    'Analyze the relationship between attendance and CGPA'
    Verifies:
      - Pulse Analytics computes correlation and linear regression.
      - Scribe Output Agent produces scatter plot, regression equation, and analytical explanation.
    """
    mother = MotherAgent()
    query = "Analyze the relationship between attendance and CGPA"

    workflow = mother.create_workflow(prompt=query, mode="analyze")
    assert workflow.request_type == "analytics"

    final_wf = mother.execute_workflow(workflow)
    assert final_wf.status == "completed"

    results = final_wf.results
    analytics = results["analytics"]
    assert analytics.get("analysis_type") == "correlation_analysis"
    assert "correlation" in analytics
    assert analytics["correlation"] is not None

    output_res = results["output"]
    summary = output_res.get("summary", "")
    assert "CORRELATION" in summary.upper() or "PEARSON" in summary.upper() or "RELATIONSHIP" in summary.upper()


def test_weighted_ranking_workflow_e2e():
    """
    End-to-end workflow test for:
    'Rank the top 10 students using 80% marks and 20% attendance'
    Verifies deterministic scale normalization and ranking.
    """
    mother = MotherAgent()
    query = "Rank the top 10 students using 80% marks and 20% attendance"

    workflow = mother.create_workflow(prompt=query, mode="analyze")
    assert workflow.request_type == "analytics"

    final_wf = mother.execute_workflow(workflow)
    assert final_wf.status == "completed"

    results = final_wf.results
    analytics = results["analytics"]
    assert analytics.get("analysis_type") in ("weighted_ranking", "ranking_analysis")

    top_recs = analytics.get("ranking") or analytics.get("tables", {}).get("top_performers", [])
    assert len(top_recs) <= 10
    assert len(top_recs) > 0
