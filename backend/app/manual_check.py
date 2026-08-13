import json
import logging
from dotenv import load_dotenv

# Load environment variables (.env with GROQ_API_KEY, SUPABASE_URL, SUPABASE_KEY)
load_dotenv()

# Configure readable stdout logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

print("=" * 70)
print("1. TESTING VAULT DB AGENT DIRECT PIPELINE (Text / NL Query)")
print("=" * 70)

from app.agents.vault_planner import vault_llm_plan
from app.agents.vault_executor import execute_plan

query_text = (
    "Add a new library loan: student STU-1001 borrowed "
    "'Test Manual Check Book', due 2026-09-15, not yet returned"
)

print(f"\n[Input Query]: {query_text}\n")

# Step A: Synthesize structured plan via Vault Planner
plan = vault_llm_plan({"query": query_text})
print("[Synthesized Plan JSON]:")
print(json.dumps(plan, indent=2))

# Step B: Execute synthesized plan via Vault Executor against live schema
execution_result = execute_plan(plan)
print("\n[Execution Result JSON]:")
print(json.dumps(execution_result, indent=2, default=str))


print("\n" + "=" * 70)
print("2. TESTING MOTHER AGENT FULL MULTI-AGENT PIPELINE")
print("=" * 70)

from app.mother.mother_agent import MotherAgent

mother = MotherAgent()
workflow = mother.create_workflow(query_text)
completed_workflow = mother.execute_workflow(workflow)

print("\n[MotherAgent Final Status]:", completed_workflow.status)
print("[MotherAgent Final Result]:")
if completed_workflow.final_result:
    print(json.dumps(completed_workflow.final_result.model_dump(), indent=2, default=str))
else:
    print(json.dumps(completed_workflow.results, indent=2, default=str))


print("\n" + "=" * 70)
print("3. SAMPLE CODE: HOW TO TEST IMAGE / FILE INPUT VIA INPUT AGENT")
print("=" * 70)
print("""
To test an image or file (Excel/PDF) query manually:

from app.agents.input_agent import InputAgent
from app.mother.types import AgentTask

input_agent = InputAgent()
task = AgentTask(
    task_id="MANUAL-TEST-01",
    agent="input",
    objective="Parse image query",
    input_data={"user_query": "C:/path/to/sample_image.png Show CSE students"},
    expected_output="Structured intent"
)

result = input_agent.execute(task)
print(json.dumps(result.result, indent=2))
""")