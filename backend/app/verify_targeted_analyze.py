"""
verify_targeted_analyze.py — Targeted verification script for:
"Find academically at-risk students and explain reasons"
"""

import os
import sys
from app.mother.mother_agent import MotherAgent


def main():
    print("==================================================")
    print("TARGETED ANALYZE WORKFLOW VERIFICATION")
    print("Query: 'Find academically at-risk students and explain reasons'")
    print("==================================================")

    mother = MotherAgent()
    query = "Find academically at-risk students and explain reasons"

    # Step 1: Create Workflow
    workflow = mother.create_workflow(prompt=query, mode="analyze")
    print(f"1. Workflow Created: ID={workflow.workflow_id}, Mode={workflow.mode}, RequestType={workflow.request_type}")
    print("   Plan Steps:")
    for step in workflow.plan.steps:
        print(f"     Step {step.step_number}: [{step.agent.upper()}] {step.action} - {step.description} (status={step.status})")

    # Step 2: Execute Workflow
    print("\n2. Executing Workflow...")
    final_wf = mother.execute_workflow(workflow)
    print(f"   Workflow Final Status: {final_wf.status.upper()}")

    # Step 3: Inspect Execution Results
    res = final_wf.results
    print("\n3. Agent Execution Results:")
    for agent_name in ("input", "db", "analytics", "output"):
        if agent_name in res:
            agent_data = res[agent_name]
            print(f"   • {agent_name.upper()} Agent: Completed")
            if agent_name == "db":
                recs = agent_data.get("records") or []
                print(f"     - Records fetched from DB: {len(recs)}")
            elif agent_name == "analytics":
                print(f"     - Analysis Type: {agent_data.get('analysis_type')}")
                print(f"     - Total Analyzed: {agent_data.get('records_analyzed', agent_data.get('total_records'))}")
                print(f"     - At-Risk Count: {agent_data.get('at_risk_count')}")
                print(f"     - Dominant Pattern: {agent_data.get('dominant_risk_pattern')}")
            elif agent_name == "output":
                print(f"     - Summary length: {len(agent_data.get('summary', ''))} chars")
                files = agent_data.get("files", {})
                for ftype, fpath in files.items():
                    print(f"     - Generated {ftype.upper()}: {fpath} (exists={os.path.exists(fpath)})")
        else:
            print(f"   • {agent_name.upper()} Agent: NOT IN RESULTS")

    # Step 4: Verify Final Result
    final_res = final_wf.final_result
    print("\n4. Final Orchestration Result:")
    if final_res:
        print(f"   Success: {final_res.success}")
        print(f"   Mode: {final_res.mode}")
        print(f"   Output Format: {final_res.output_format}")
        print(f"   Output File: {final_res.output_file}")
        print("   Summary Preview:")
        for line in final_res.summary.splitlines()[:12]:
            print(f"     {line}")
    else:
        print("   [!] Final result is None!")

    print("==================================================")


if __name__ == "__main__":
    main()
