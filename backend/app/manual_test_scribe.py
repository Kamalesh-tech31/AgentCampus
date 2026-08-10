import os
import sys

# Ensure the backend directory is in the path for absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.output_agent import OutputAgent
from app.mother.types import AgentTask

# 1. Sample Data
MOCK_RECORDS = [
    {
        "id": "STU-001",
        "name": "Arun Kumar",
        "department": "Computer Science",
        "marks": 92.5,
        "attendance": 95.0,
        "cgpa": 9.2,
        "status": "Active"
    },
    {
        "id": "STU-002",
        "name": "Priya Sharma",
        "department": "Mechanical Engineering",
        "marks": 88.0,
        "attendance": 91.0,
        "cgpa": 8.8,
        "status": "Active"
    },
    {
        "id": "STU-003",
        "name": "Vikram Singh",
        "department": "Electrical Engineering",
        "marks": 55.0,
        "attendance": 65.0,
        "cgpa": 5.5,
        "status": "Probation"
    },
    {
        "id": "STU-004",
        "name": "Neha Patel",
        "department": "Computer Science",
        "marks": 78.0,
        "attendance": 85.0,
        "cgpa": 7.8,
        "status": "Active"
    }
]

MOCK_ANALYTICS = {
    "totalRecords": 4,
    "averageCgpa": 7.82,
    "highestCgpa": 9.2,
    "lowestCgpa": 5.5,
    "probationCount": 1,
    "departmentBreakdown": {
        "Computer Science": {"count": 2, "avgCgpa": 8.5},
        "Mechanical Engineering": {"count": 1, "avgCgpa": 8.8},
        "Electrical Engineering": {"count": 1, "avgCgpa": 5.5}
    }
}
MOCK_INSIGHT = "Overall performance is stable. However, attendance correlates strongly with CGPA. One student in Electrical Engineering is on probation and requires academic support."

def _verify_and_get_path(res, expected_format):
    if res.status != "completed":
        print(f"FAILED: Status is {res.status}")
        return None
    
    if "result" not in res.__dict__:
        print(f"FAILED: 'result' field not found in AgentResult")
        return None
        
    payload = res.result
    
    if payload.get("output_format") != expected_format:
        print(f"FAILED: Expected format {expected_format}, got {payload.get('output_format')}")
        return None
        
    output_file = payload.get("output_file")
    if not output_file or not os.path.exists(output_file):
        print(f"FAILED: Output file {output_file} does not exist.")
        return None
        
    size = os.path.getsize(output_file)
    if size == 0:
        print(f"FAILED: Output file {output_file} is 0 bytes.")
        return None
        
    return os.path.abspath(output_file)


def run_manual_test():
    # Ensure output directory exists in the real backend path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(base_dir, "output_files")
    os.makedirs(output_dir, exist_ok=True)
    
    # We will pass a specific prefix in the user_query, but the service generates timestamped files by default.
    # We rely on the absolute path returned by the service.
    
    agent = OutputAgent()
    
    print("\n========================================")
    print("SCRIBE MANUAL VISUAL TEST")
    print("========================================\n")

    # --- TEXT ---
    task_text = AgentTask(
        task_id="MANUAL-TEXT",
        agent="output",
        objective="Format response",
        input_data={
            "user_query": "Give me a student performance summary in text",
            "db": {"records": MOCK_RECORDS},
            "analytics": {"metrics": MOCK_ANALYTICS, "insight": MOCK_INSIGHT}
        },
        expected_output="Response"
    )
    res_text = agent.execute(task_text)
    print("TEXT RESPONSE:")
    if res_text.status == "completed" and res_text.result.get("output_format") == "text":
        print(res_text.result.get("text_content", "No text content found."))
    else:
        print("FAILED to generate text.")
    print("\n" + "-"*40 + "\n")

    # --- EXCEL ---
    task_excel = AgentTask(
        task_id="MANUAL-EXCEL",
        agent="output",
        objective="Format response",
        input_data={
            "user_query": "Create an Excel report of student performance",
            "db": {"records": MOCK_RECORDS},
            "analytics": {"metrics": MOCK_ANALYTICS, "insight": MOCK_INSIGHT}
        },
        expected_output="Response"
    )
    res_excel = agent.execute(task_excel)
    excel_path = _verify_and_get_path(res_excel, "excel")
    print("EXCEL GENERATED:")
    print(f"[{excel_path}]" if excel_path else "FAILED")
    print("\n" + "-"*40 + "\n")

    # --- PDF ---
    task_pdf = AgentTask(
        task_id="MANUAL-PDF",
        agent="output",
        objective="Format response",
        input_data={
            "user_query": "Create a PDF report of student performance",
            "db": {"records": MOCK_RECORDS},
            "analytics": {"metrics": MOCK_ANALYTICS, "insight": MOCK_INSIGHT}
        },
        expected_output="Response"
    )
    res_pdf = agent.execute(task_pdf)
    pdf_path = _verify_and_get_path(res_pdf, "pdf")
    print("PDF GENERATED:")
    print(f"[{pdf_path}]" if pdf_path else "FAILED")
    print("\n" + "-"*40 + "\n")

    # --- POWERPOINT ---
    task_ppt = AgentTask(
        task_id="MANUAL-PPT",
        agent="output",
        objective="Format response",
        input_data={
            "user_query": "Create a PowerPoint presentation of student performance",
            "db": {"records": MOCK_RECORDS},
            "analytics": {"metrics": MOCK_ANALYTICS, "insight": MOCK_INSIGHT}
        },
        expected_output="Response"
    )
    res_ppt = agent.execute(task_ppt)
    ppt_path = _verify_and_get_path(res_ppt, "pptx")
    print("POWERPOINT GENERATED:")
    print(f"[{ppt_path}]" if ppt_path else "FAILED")
    
    print("\n========================================")
    print("OPEN backend/output_files/ TO INSPECT")
    print("========================================\n")


if __name__ == "__main__":
    run_manual_test()
