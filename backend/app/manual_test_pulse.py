"""
manual_test_pulse.py — Manual visual demo for the Pulse Analytics Agent.

Run from the backend directory:
    python app/manual_test_pulse.py

Purpose:
  - Uses sample student data and several user requests.
  - Prints detected columns, analysis plan, tools selected,
    calculations performed, final metrics, findings, and insights.
  - Makes it easy to see exactly what Pulse is doing internally.

Does NOT use: MotherAgent, Vault, Scribe, database, or real Groq API calls.
"""

import json
import os
import sys
from pprint import pformat

# Ensure the backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.analytics_agent import AnalyticsAgent
from app.mother.types import AgentTask

# ── Sample Data ────────────────────────────────────────────────────────────────

SAMPLE_RECORDS = [
    {"name": "Arun Kumar",   "department": "CSE", "marks": 92, "attendance": 95, "cgpa": 9.2, "status": "Active"},
    {"name": "Priya Sharma", "department": "CSE", "marks": 88, "attendance": 91, "cgpa": 8.8, "status": "Active"},
    {"name": "Rahul Singh",  "department": "ECE", "marks": 45, "attendance": 65, "cgpa": 5.4, "status": "Probation"},
    {"name": "Neha Patel",   "department": "CSE", "marks": 78, "attendance": 85, "cgpa": 7.8, "status": "Active"},
    {"name": "Vikram Rao",   "department": "ECE", "marks": 55, "attendance": 70, "cgpa": 6.1, "status": "Active"},
    {"name": "Meena Raj",    "department": "ME",  "marks": 70, "attendance": 80, "cgpa": 7.2, "status": "Active"},
    {"name": "Suresh Kumar", "department": "ME",  "marks": 40, "attendance": 60, "cgpa": 4.9, "status": "Probation"},
]

DIVIDER = "=" * 60
SUB_DIV = "-" * 40


def _print_section(title: str, content):
    print(f"\n{SUB_DIV}")
    print(f"  {title}")
    print(SUB_DIV)
    if isinstance(content, (dict, list)):
        print(json.dumps(content, indent=2, default=str))
    else:
        print(content)


def run_query(agent: AnalyticsAgent, query: str, records=None, label=""):
    if records is None:
        records = SAMPLE_RECORDS

    print(f"\n{DIVIDER}")
    print(f"  QUERY: {query}")
    if label:
        print(f"  ({label})")
    print(DIVIDER)

    task = AgentTask(
        task_id=f"MANUAL-{label.upper().replace(' ', '_') or 'TEST'}",
        agent="analytics",
        objective="Analyse data",
        input_data={
            "user_query": query,
            "db": {"records": records},
        },
        expected_output="AnalyticsResult",
    )

    res = agent.execute(task)

    if res.status != "completed":
        print(f"\n  ERROR: {res.error}")
        return

    r = res.result

    # ── Dataset profile ──────────────────────────────────────────────────────
    print("\n  DETECTED COLUMNS:")
    cols = r.get("columns_analyzed", [])
    print(f"    All: {cols}")

    # Re-run profiler for display (agent result doesn't store the raw profile)
    from app.services.pulse.dataset_profiler import profile_dataset
    profile = profile_dataset(records)
    print(f"    Numeric:      {profile['numeric_columns']}")
    print(f"    Categorical:  {profile['categorical_columns']}")
    for col, info in profile["columns"].items():
        if info["missing"] > 0:
            print(f"    [MISSING] {col}: {info['missing']} missing values")

    # ── Analysis plan ────────────────────────────────────────────────────────
    plan = r.get("analysis_plan", {})
    _print_section("ANALYSIS PLAN", {
        "goal":     plan.get("analysis_goal"),
        "strategy": plan.get("strategy"),
        "reasoning": plan.get("reasoning", ""),
    })

    # ── Tools selected and executed ──────────────────────────────────────────
    tools_run = [entry["tool"] for entry in r.get("raw_results", [])]
    print(f"\n  TOOLS SELECTED:  {tools_run if tools_run else '(none — LLM reasoning strategy)'}")

    # ── Per-tool calculation results ─────────────────────────────────────────
    for entry in r.get("raw_results", []):
        tool = entry["tool"]
        result = entry["result"]
        if "error" in result:
            print(f"\n  [{tool}] ERROR: {result['error']}")
            continue
        # Show a brief summary of each tool's result
        brief = {k: v for k, v in result.items() if k not in ("outliers", "at_risk", "ranked_records", "sorted_records", "filtered_records", "top_records", "bottom_records") or not isinstance(v, list) or len(v) <= 3}
        _print_section(f"TOOL: {tool}", brief)

    # ── Final metrics ────────────────────────────────────────────────────────
    _print_section("FINAL METRICS (legacy contract)", r.get("metrics", {}))

    # ── Findings ─────────────────────────────────────────────────────────────
    findings = r.get("findings", [])
    print(f"\n  FINDINGS ({len(findings)}):")
    for i, f in enumerate(findings, 1):
        print(f"    {i}. {f}")

    # ── Insights ─────────────────────────────────────────────────────────────
    print(f"\n  INSIGHT:")
    print(f"    {r.get('insight', 'No insight generated.')}")

    # ── Tables ───────────────────────────────────────────────────────────────
    tables = r.get("tables", {})
    if tables:
        print(f"\n  TABLES ({len(tables)} available for Scribe):")
        for tname, rows in tables.items():
            print(f"    - {tname}: {len(rows)} rows")

    # ── Chart data ───────────────────────────────────────────────────────────
    charts = r.get("chart_data", {})
    if charts:
        print(f"\n  CHART DATA ({len(charts)} charts available for Scribe):")
        for cname, cdata in charts.items():
            print(f"    - {cname}: type={cdata.get('type')}, title='{cdata.get('title')}'")

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n  SUMMARY: {r.get('summary', '')}")
    print(f"  ANALYSIS TYPE: {r.get('analysis_type', '')}")


def main():
    agent = AnalyticsAgent()

    print(f"\n{'#'*60}")
    print("  PULSE ANALYTICS AGENT — MANUAL VISUAL DEMO")
    print(f"{'#'*60}")
    print(f"  Records: {len(SAMPLE_RECORDS)}")
    print(f"  PULSE_GROQ_API_KEY: {'SET' if os.getenv('PULSE_GROQ_API_KEY') else 'NOT SET (deterministic fallback)'}")
    print(f"  PULSE_GROQ_MODEL: {os.getenv('PULSE_GROQ_MODEL', 'not set')}")

    # ── Demo 1: Simple average ────────────────────────────────────────────────
    run_query(agent,
        query="What is the average CGPA?",
        label="DEMO 1: Simple average",
    )

    # ── Demo 2: Group comparison ──────────────────────────────────────────────
    run_query(agent,
        query="Compare CSE and ECE performance",
        label="DEMO 2: Group comparison",
    )

    # ── Demo 3: Risk analysis ─────────────────────────────────────────────────
    run_query(agent,
        query="Identify students who need immediate attention",
        label="DEMO 3: Risk analysis",
    )

    # ── Demo 4: Correlation ───────────────────────────────────────────────────
    run_query(agent,
        query="Is low attendance related to low marks?",
        label="DEMO 4: Correlation analysis",
    )

    # ── Demo 5: Ranking ───────────────────────────────────────────────────────
    run_query(agent,
        query="Show the top 3 students by CGPA",
        label="DEMO 5: Ranking / Top N",
    )

    # ── Demo 6: Dynamic dataset (different column names) ──────────────────────
    custom_records = [
        {"employee": "Alice",  "division": "Engineering", "score": 88.5, "hours": 42, "rating": 4.5},
        {"employee": "Bob",    "division": "Marketing",   "score": 62.0, "hours": 38, "rating": 3.0},
        {"employee": "Carol",  "division": "Engineering", "score": 91.0, "hours": 45, "rating": 4.8},
        {"employee": "David",  "division": "HR",          "score": 55.0, "hours": 35, "rating": 2.8},
        {"employee": "Eve",    "division": "Marketing",   "score": 77.0, "hours": 40, "rating": 3.9},
    ]
    run_query(agent,
        query="Analyse employee performance across divisions",
        records=custom_records,
        label="DEMO 6: Dynamic dataset (custom columns)",
    )

    print(f"\n{'#'*60}")
    print("  MANUAL DEMO COMPLETE")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    main()
