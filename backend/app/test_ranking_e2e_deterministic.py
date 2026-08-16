"""
test_ranking_e2e_deterministic.py — Real end-to-end integration test for
"Rank the top 10 students using 80% marks and 20% attendance".
"""

import pytest
import os
from app.mother.mother_agent import MotherAgent
from app.agents.input_agent import InputAgent
from app.agents.db_agent import DBAgent
from app.agents.analytics_agent import AnalyticsAgent
from app.agents.output_agent import OutputAgent


def test_full_ranking_flow_e2e():
    """
    Run the full end-to-end ranking workflow:
    'Rank the top 10 students using 80% marks and 20% attendance'
    """
    mother = MotherAgent()
    query = "Rank the top 10 students using 80% marks and 20% attendance"

    # Create and execute workflow through MotherAgent
    workflow = mother.create_workflow(prompt=query, mode="analyze")
    assert workflow.request_type == "analytics"

    final_wf = mother.execute_workflow(workflow)
    assert final_wf.status == "completed"

    # Step-by-step verification of results
    results = final_wf.results
    assert "input" in results
    assert "db" in results
    assert "analytics" in results
    assert "output" in results

    # 1. DB Agent retrieved records
    db_res = results["db"]
    records = db_res.get("records") or db_res.get("data", [])
    assert len(records) > 0

    # 2. Pulse Analytics computed deterministic weighted ranking
    analytics = results["analytics"]
    assert analytics.get("analysis_type") in ("weighted_ranking", "ranking_analysis")
    assert "formula" in analytics or "tables" in analytics

    top_performers = analytics.get("ranking") or analytics.get("tables", {}).get("top_performers", [])
    assert len(top_performers) <= 10
    assert len(top_performers) > 0

    # Verify Aarav Sharma if in top performers
    aarav = next((r for r in top_performers if r.get("name") == "Aarav Sharma"), None)
    if aarav:
        assert aarav.get("academic_score") == 88.20
        assert aarav.get("academic_contribution") == 70.56
        assert aarav.get("attendance_contribution") == 19.20
        assert aarav.get("_weighted_score") == 89.76

    # 3. Scribe Output Agent produced clean summary
    output_res = results["output"]
    summary_text = output_res.get("summary", "")
    assert len(summary_text) > 0
    assert "PERFORMERS" in summary_text.upper() or "WEIGHTED" in summary_text.upper() or "RANK" in summary_text.upper() or "80%" in summary_text
