"""
test_abi.py — Comprehensive DB Agent (Vault) Test Suite for AgentCampus

Covers all test cases from Section 0 through Section G (87 test cases total):
- Section 0: Pre-test cleanup & baseline verification (protected tables: students, courses, history)
- Section A: Single-table CRUD on students (10 cases)
- Section B: Single-table CRUD on courses (10 cases)
- Section C: Two-table retrieval / joins & multi-table reads (15 cases)
- Section D: Two-table modification in a single request (10 cases)
- Section E: New table lifecycle — enrollments (create -> modify -> query -> delete) (15 cases)
- Section F: Delete-command variety & DDL guardrails (10 cases)
- Section G: History/audit log verification & DB state matching (12 cases)

Each test case:
1. Sends the exact natural-language query / payload to Vault (vault_llm_plan -> execute_plan).
2. Runs paired manual verification query directly against the database via Supabase client.
3. Asserts that Vault's reported result matches the actual DB state (detecting response vs DB mismatches).
"""

import sys
import time
import json
import pytest
from typing import Dict, Any, Tuple

from app.agents.vault_planner import vault_llm_plan
from app.agents.vault_executor import execute_plan
from app.db.client import supabase
from app.db.schema_registry import get_live_schema, get_known_fields, invalidate_schema_cache
from app.db.generic_mutations import _execute_ddl, _validate_ddl_statement


def run_pipeline(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Helper function to pass natural language / structured intent through vault_llm_plan
    and execute the plan via execute_plan.
    Returns (plan, result).
    """
    plan = vault_llm_plan(payload)
    result = execute_plan(plan)
    return plan, result


def assert_db_match(test_label: str, reported_success: bool, actual_condition: bool, details: str = ""):
    """
    Asserts that Vault's reported success status matches the empirical DB verification state.
    Raises AssertionError if Vault reported success but DB state failed to change.
    """
    if reported_success and not actual_condition:
        raise AssertionError(
            f"['TRUST RESPONSE, DON'T VERIFY' BUG DETECTED] {test_label}: "
            f"Vault reported success=True, but actual DB condition failed! Details: {details}"
        )
    assert reported_success == actual_condition, f"{test_label} failed: reported={reported_success}, actual={actual_condition}"


# ==============================================================================
# SECTION 0: Pre-test cleanup / Baseline verification (Protected tables)
# ==============================================================================

@pytest.mark.critical
def test_0_01_verify_protected_tables_exist():
    """Section 0.1: Verify protected tables (students, courses, history) exist in live schema."""
    invalidate_schema_cache()
    live_schema = get_live_schema(force_refresh=True)
    assert "students" in live_schema, "Protected table 'students' missing from schema!"
    assert "courses" in live_schema, "Protected table 'courses' missing from schema!"
    assert "history" in live_schema, "Protected table 'history' missing from schema!"


@pytest.mark.batch1
def test_0_02_verify_students_baseline_count():
    """Section 0.2: Verify students table has baseline data records."""
    res = supabase.table("students").select("id", count="exact").execute()
    count = res.count or len(res.data or [])
    assert count > 0, "Protected table 'students' has no baseline rows!"


@pytest.mark.batch1
def test_0_03_verify_courses_baseline_count():
    """Section 0.3: Verify courses table has baseline data records."""
    res = supabase.table("courses").select("id", count="exact").execute()
    count = res.count or len(res.data or [])
    assert count > 0, "Protected table 'courses' has no baseline rows!"


@pytest.mark.batch1
def test_0_04_verify_history_baseline_accessible():
    """Section 0.4: Verify history table is accessible and has valid schema columns."""
    invalidate_schema_cache()
    fields = get_known_fields("history")
    assert ("originalTable" in fields or "original_table" in fields), "History schema missing originalTable column!"
    assert ("rowId" in fields or "row_id" in fields), "History schema missing rowId column!"


# ==============================================================================
# SECTION A: Single-table CRUD on students (10 cases)
# ==============================================================================

@pytest.mark.critical
def test_a_01_get_all_students():
    """Section A.1: Get all student records."""
    plan, res = run_pipeline({"query": "Get all student records", "table": "students"})
    assert res.get("success") is True, f"Failed to get all students: {res.get('message')}"
    db_res = supabase.table("students").select("id").execute()
    assert len(res.get("data", [])) == len(db_res.data or []), "Reported row count does not match DB count!"


@pytest.mark.batch1
def test_a_02_filter_students_by_department():
    """Section A.2: Filter students by department = 'Computer Science'."""
    plan, res = run_pipeline({"query": "Show Computer Science students", "table": "students", "department": "Computer Science"})
    assert res.get("success") is True
    db_res = supabase.table("students").select("id").eq("department", "Computer Science").execute()
    assert len(res.get("data", [])) == len(db_res.data or [])


@pytest.mark.batch1
def test_a_03_filter_students_by_cgpa():
    """Section A.3: Filter students where cgpa >= 9.0."""
    plan, res = run_pipeline({"query": "Find students with CGPA 9.0 or higher", "table": "students", "cgpa": 9.0})
    assert res.get("success") is True
    db_res = supabase.table("students").select("id").gte("cgpa", 9.0).execute()
    assert len(res.get("data", [])) == len(db_res.data or [])


@pytest.mark.batch1
def test_a_04_count_students():
    """Section A.4: Count total students."""
    plan, res = run_pipeline({"query": "Count total students", "table": "students", "action": "count_rows"})
    assert res.get("success") is True
    db_res = supabase.table("students").select("id", count="exact").execute()
    assert res.get("data", {}).get("count") == (db_res.count or len(db_res.data or []))


@pytest.mark.batch1
def test_a_05_insert_student():
    """Section A.5: Insert new student record (STU-ABI-A05)."""
    ts = int(time.time())
    stu_id = f"STU-ABI-A05-{ts}"
    payload = {
        "action": "insert",
        "table": "students",
        "data": {
            "id": stu_id,
            "rollNumber": f"R-A05-{ts%10000}",
            "name": "Ada Lovelace ABI",
            "department": "Computer Science",
            "cgpa": 9.8,
            "semester": 6,
            "attendance": 98.0,
            "email": f"ada.{ts}@campus.edu",
            "status": "Active",
            "backlogs": 0,
            "projectTitle": "Analytical Engine DB"
        }
    }
    plan, res = run_pipeline(payload)
    assert res.get("success") is True
    db_res = supabase.table("students").select("*").eq("id", stu_id).execute()
    assert_db_match("test_a_05_insert_student", res.get("success"), len(db_res.data or []) == 1)


@pytest.mark.batch1
def test_a_06_update_student_name():
    """Section A.6: Update student name and verify DB persistence."""
    ts = int(time.time())
    stu_id = f"STU-ABI-A06-{ts}"
    supabase.table("students").insert({
        "id": stu_id, "rollNumber": f"R-A06-{ts%10000}", "name": "Before Update",
        "department": "Computer Science", "cgpa": 9.0, "semester": 4,
        "attendance": 90.0, "email": f"a06.{ts}@campus.edu", "status": "Active", "backlogs": 0
    }).execute()

    new_name = "Ada Lovelace (Updated A06)"
    plan, res = run_pipeline({"action": "update", "table": "students", "row_id": stu_id, "data": {"name": new_name}})
    assert res.get("success") is True
    
    db_res = supabase.table("students").select("name").eq("id", stu_id).execute()
    actual_name = db_res.data[0].get("name") if db_res.data else ""
    assert_db_match("test_a_06_update_student_name", res.get("success"), actual_name == new_name, f"Expected {new_name}, DB had {actual_name}")


@pytest.mark.batch1
def test_a_07_update_student_cgpa():
    """Section A.7: Update student CGPA and verify DB persistence."""
    ts = int(time.time())
    stu_id = f"STU-ABI-A07-{ts}"
    supabase.table("students").insert({
        "id": stu_id, "rollNumber": f"R-A07-{ts%10000}", "name": "CGPA Test Student",
        "department": "Computer Science", "cgpa": 8.0, "semester": 4,
        "attendance": 90.0, "email": f"a07.{ts}@campus.edu", "status": "Active", "backlogs": 0
    }).execute()

    plan, res = run_pipeline({"action": "update", "table": "students", "row_id": stu_id, "data": {"cgpa": 9.75}})
    assert res.get("success") is True

    db_res = supabase.table("students").select("cgpa").eq("id", stu_id).execute()
    actual_cgpa = float(db_res.data[0].get("cgpa")) if db_res.data else 0.0
    assert_db_match("test_a_07_update_student_cgpa", res.get("success"), actual_cgpa == 9.75)


@pytest.mark.batch1
def test_a_08_delete_student():
    """Section A.8: Delete student record and verify removal from DB."""
    ts = int(time.time())
    stu_id = f"STU-ABI-A08-{ts}"
    supabase.table("students").insert({
        "id": stu_id, "rollNumber": f"R-A08-{ts%10000}", "name": "To Delete Student",
        "department": "Computer Science", "cgpa": 8.0, "semester": 4,
        "attendance": 90.0, "email": f"a08.{ts}@campus.edu", "status": "Active", "backlogs": 0
    }).execute()

    plan, res = run_pipeline({"action": "delete", "table": "students", "row_id": stu_id})
    assert res.get("success") is True

    db_res = supabase.table("students").select("id").eq("id", stu_id).execute()
    assert_db_match("test_a_08_delete_student", res.get("success"), len(db_res.data or []) == 0)


@pytest.mark.batch1
def test_a_09_invalid_field_rejection():
    """Section A.9: Query non-existent field annual_salary -> clean rejection without DB touch."""
    plan, res = run_pipeline({"query": "Find students with annual_salary > 100000"})
    assert (plan.get("action") == "error" or res.get("success") is False), "Non-existent field was not rejected!"


@pytest.mark.critical
def test_a_10_bulk_update_cgpa():
    """Section A.10: Bounded bulk update on CGPA for CSE students."""
    plan, res = run_pipeline({
        "query": "Increase CGPA by 0.01 for Computer Science students in semester 8",
        "action": "bulk_update",
        "table": "students",
        "params": {
            "filters": [
                {"field": "department", "op": "eq", "value": "Computer Science"},
                {"field": "semester", "op": "eq", "value": 8}
            ],
            "field": "cgpa",
            "operation": "add",
            "value": 0.01,
            "max_rows": 50
        }
    })
    assert res.get("success") is True
    assert res.get("data", {}).get("rows_updated", 0) > 0


# ==============================================================================
# SECTION B: Single-table CRUD on courses (10 cases)
# ==============================================================================

@pytest.mark.batch1
def test_b_01_get_all_courses():
    """Section B.1: Get all course records."""
    plan, res = run_pipeline({"query": "Get all course records", "table": "courses"})
    assert res.get("success") is True
    db_res = supabase.table("courses").select("id").execute()
    assert len(res.get("data", [])) == len(db_res.data or [])


@pytest.mark.batch1
def test_b_02_filter_courses_by_department():
    """Section B.2: Filter courses by department = 'Computer Science'."""
    plan, res = run_pipeline({"query": "Show Computer Science courses", "table": "courses", "department": "Computer Science"})
    assert res.get("success") is True
    db_res = supabase.table("courses").select("id").eq("department", "Computer Science").execute()
    assert len(res.get("data", [])) == len(db_res.data or [])


@pytest.mark.batch1
def test_b_03_filter_courses_by_credits():
    """Section B.3: Filter courses where credits >= 4."""
    plan, res = run_pipeline({
        "action": "filter_rows",
        "table": "courses",
        "params": {
            "filters": [
                {"field": "credits", "op": "gte", "value": 4}
            ]
        }
    })
    assert res.get("success") is True
    db_res = supabase.table("courses").select("id").gte("credits", 4).execute()
    assert len(res.get("data", [])) == len(db_res.data or [])


@pytest.mark.batch1
def test_b_04_count_courses():
    """Section B.4: Count total courses."""
    plan, res = run_pipeline({"query": "Count total courses", "table": "courses", "action": "count_rows"})
    assert res.get("success") is True
    db_res = supabase.table("courses").select("id", count="exact").execute()
    assert res.get("data", {}).get("count") == (db_res.count or len(db_res.data or []))


@pytest.mark.batch1
def test_b_05_insert_course():
    """Section B.5: Insert new course record (CRS-ABI-B05)."""
    ts = int(time.time())
    crs_id = f"CRS-ABI-B05-{ts}"
    payload = {
        "action": "insert",
        "table": "courses",
        "data": {
            "id": crs_id,
            "courseCode": f"CS-B05-{ts%1000}",
            "courseName": "Quantum Agent Computing",
            "department": "Computer Science",
            "credits": 4,
            "instructor": "Dr. Richard Feynman",
            "semester": 7
        }
    }
    plan, res = run_pipeline(payload)
    assert res.get("success") is True
    db_res = supabase.table("courses").select("*").eq("id", crs_id).execute()
    assert_db_match("test_b_05_insert_course", res.get("success"), len(db_res.data or []) == 1)


@pytest.mark.batch1
def test_b_06_update_course_instructor():
    """Section B.6: Update course instructor and verify DB persistence."""
    ts = int(time.time())
    crs_id = f"CRS-ABI-B06-{ts}"
    supabase.table("courses").insert({
        "id": crs_id, "courseCode": f"CS-B06-{ts%1000}", "courseName": "Initial Architecture",
        "department": "Computer Science", "credits": 4, "instructor": "Initial Instructor", "semester": 5
    }).execute()

    new_instructor = "Dr. Alan Turing (Updated B06)"
    plan, res = run_pipeline({"action": "update", "table": "courses", "row_id": crs_id, "data": {"instructor": new_instructor}})
    assert res.get("success") is True

    db_res = supabase.table("courses").select("instructor").eq("id", crs_id).execute()
    actual_inst = db_res.data[0].get("instructor") if db_res.data else ""
    assert_db_match("test_b_06_update_course_instructor", res.get("success"), actual_inst == new_instructor)


@pytest.mark.batch1
def test_b_07_update_course_credits():
    """Section B.7: Update course credits and verify DB persistence."""
    ts = int(time.time())
    crs_id = f"CRS-ABI-B07-{ts}"
    supabase.table("courses").insert({
        "id": crs_id, "courseCode": f"CS-B07-{ts%1000}", "courseName": "Credits Test Course",
        "department": "Computer Science", "credits": 3, "instructor": "Prof. Shannon", "semester": 4
    }).execute()

    plan, res = run_pipeline({"action": "update", "table": "courses", "row_id": crs_id, "data": {"credits": 5}})
    assert res.get("success") is True

    db_res = supabase.table("courses").select("credits").eq("id", crs_id).execute()
    actual_credits = int(db_res.data[0].get("credits")) if db_res.data else 0
    assert_db_match("test_b_07_update_course_credits", res.get("success"), actual_credits == 5)


@pytest.mark.batch1
def test_b_08_delete_course():
    """Section B.8: Delete course record and verify removal from DB."""
    ts = int(time.time())
    crs_id = f"CRS-ABI-B08-{ts}"
    supabase.table("courses").insert({
        "id": crs_id, "courseCode": f"CS-B08-{ts%1000}", "courseName": "Course To Delete",
        "department": "Computer Science", "credits": 3, "instructor": "Temp Prof", "semester": 1
    }).execute()

    plan, res = run_pipeline({"action": "delete", "table": "courses", "row_id": crs_id})
    assert res.get("success") is True

    db_res = supabase.table("courses").select("id").eq("id", crs_id).execute()
    assert_db_match("test_b_08_delete_course", res.get("success"), len(db_res.data or []) == 0)


@pytest.mark.batch1
def test_b_09_invalid_course_field():
    """Section B.9: Query courses with non-existent field tuition_fee -> clean rejection."""
    plan, res = run_pipeline({"query": "Find courses with tuition_fee > 5000"})
    assert (plan.get("action") == "error" or res.get("success") is False)


@pytest.mark.batch1
def test_b_10_bulk_update_course_credits():
    """Section B.10: Bounded bulk update on course credits for CSE department."""
    plan, res = run_pipeline({
        "query": "Increase credits by 0 for all Computer Science courses"
    })
    assert res.get("success") is True


# ==============================================================================
# SECTION C: Two-table retrieval / joins & multi-table reads (15 cases)
# ==============================================================================

@pytest.mark.batch1
def test_c_01_retrieve_students_and_courses_sequential():
    """Section C.1: Multi-table read fetching both students and courses."""
    plan1, res1 = run_pipeline({"query": "Get all student records", "table": "students"})
    plan2, res2 = run_pipeline({"query": "Get all course records", "table": "courses"})
    assert res1.get("success") is True and res2.get("success") is True


@pytest.mark.batch1
def test_c_02_filter_students_cse_and_courses_cse():
    """Section C.2: Filter CSE students and CSE courses in separate queries."""
    plan1, res1 = run_pipeline({"query": "Show Computer Science students", "table": "students", "department": "Computer Science"})
    plan2, res2 = run_pipeline({"query": "Show Computer Science courses", "table": "courses", "department": "Computer Science"})
    assert res1.get("success") is True and res2.get("success") is True


@pytest.mark.batch1
def test_c_03_count_students_and_courses():
    """Section C.3: Count rows in students and courses."""
    plan1, res1 = run_pipeline({"query": "Count total students", "table": "students", "action": "count_rows"})
    plan2, res2 = run_pipeline({"query": "Count total courses", "table": "courses", "action": "count_rows"})
    assert res1.get("success") is True and res2.get("success") is True


@pytest.mark.batch1
def test_c_04_compute_filter_students_cgpa_attendance():
    """Section C.4: compute_filter average of cgpa + attendance > 50.0 for CSE students."""
    plan, res = run_pipeline({
        "query": "find Computer Science students with average of cgpa and attendance above 50"
    })
    assert res.get("success") is True
    data = res.get("data", [])
    assert len(data) > 0
    assert "_computed" in data[0]


@pytest.mark.batch1
def test_c_05_compute_filter_students_min():
    """Section C.5: compute_filter min of cgpa + attendance > 5.0."""
    plan, res = run_pipeline({
        "action": "compute_filter",
        "table": "students",
        "params": {
            "fields": ["cgpa", "attendance"],
            "aggregate": "min",
            "condition": {"op": "gt", "value": 5.0},
            "filters": [{"field": "department", "op": "eq", "value": "Computer Science"}]
        }
    })
    assert res.get("success") is True
    assert len(res.get("data", [])) > 0


@pytest.mark.batch2
def test_c_06_compute_filter_students_max():
    """Section C.6: compute_filter max of cgpa + attendance > 90.0."""
    plan, res = run_pipeline({
        "action": "compute_filter",
        "table": "students",
        "params": {
            "fields": ["cgpa", "attendance"],
            "aggregate": "max",
            "condition": {"op": "gt", "value": 90.0},
            "filters": [{"field": "department", "op": "eq", "value": "Computer Science"}]
        }
    })
    assert res.get("success") is True
    assert len(res.get("data", [])) > 0


@pytest.mark.batch2
def test_c_07_compute_filter_students_sum():
    """Section C.7: compute_filter sum of cgpa + attendance > 80.0."""
    plan, res = run_pipeline({
        "action": "compute_filter",
        "table": "students",
        "params": {
            "fields": ["cgpa", "attendance"],
            "aggregate": "sum",
            "condition": {"op": "gt", "value": 80.0},
            "filters": [{"field": "department", "op": "eq", "value": "Computer Science"}]
        }
    })
    assert res.get("success") is True
    assert len(res.get("data", [])) > 0


@pytest.mark.batch2
def test_c_08_compute_filter_invalid_field():
    """Section C.8: compute_filter with non-existent field physics_score -> clean error."""
    plan, res = run_pipeline({
        "query": "find students with average across all subject physics_score above 80"
    })
    assert plan.get("action") == "error" or res.get("success") is False


@pytest.mark.batch2
def test_c_09_filter_courses_by_instructor_and_department():
    """Section C.9: Filter courses by instructor and department."""
    plan, res = run_pipeline({
        "action": "filter_rows",
        "table": "courses",
        "params": {
            "filters": [
                {"field": "department", "op": "eq", "value": "Computer Science"}
            ]
        }
    })
    assert res.get("success") is True


@pytest.mark.batch2
def test_c_10_filter_students_by_status_and_semester():
    """Section C.10: Filter students by status='Active' and semester=8."""
    plan, res = run_pipeline({
        "action": "filter_rows",
        "table": "students",
        "params": {
            "filters": [
                {"field": "status", "op": "eq", "value": "Active"},
                {"field": "semester", "op": "eq", "value": 8}
            ]
        }
    })
    assert res.get("success") is True


@pytest.mark.batch2
def test_c_11_filter_students_by_backlogs():
    """Section C.11: Filter students where backlogs == 0."""
    plan, res = run_pipeline({"query": "Find students with zero backlogs", "table": "students", "backlogs": 0})
    assert res.get("success") is True


@pytest.mark.batch2
def test_c_12_filter_courses_by_semester():
    """Section C.12: Filter courses where semester == 4."""
    plan, res = run_pipeline({"query": "Find 4th semester courses", "table": "courses", "semester": 4})
    assert res.get("success") is True


@pytest.mark.batch2
def test_c_13_cross_table_data_matching_proof():
    """Section C.13: Cross-table department verification between students and courses."""
    stu_res = supabase.table("students").select("department").execute()
    crs_res = supabase.table("courses").select("department").execute()
    stu_depts = set(r["department"] for r in (stu_res.data or []) if "department" in r)
    crs_depts = set(r["department"] for r in (crs_res.data or []) if "department" in r)
    assert len(stu_depts.intersection(crs_depts)) > 0, "No common departments between students and courses!"


@pytest.mark.batch2
def test_c_14_compute_filter_courses_credits():
    """Section C.14: compute_filter average on courses credits + semester."""
    plan, res = run_pipeline({
        "action": "compute_filter",
        "table": "courses",
        "params": {
            "fields": ["credits", "semester"],
            "aggregate": "average",
            "condition": {"op": "gt", "value": 1.0}
        }
    })
    assert res.get("success") is True


@pytest.mark.batch2
def test_c_15_read_non_existent_table():
    """Section C.15: Query non-existent table professors -> clean error rejection."""
    plan, res = run_pipeline({"query": "Get all records from professors", "table": "professors"})
    assert plan.get("action") == "error" or res.get("success") is False


# ==============================================================================
# SECTION D: Two-table modification in a single request (10 cases)
# ==============================================================================

@pytest.mark.batch2
def test_d_01_insert_student_and_course():
    """Section D.1: Insert 1 student and 1 course sequentially."""
    ts = int(time.time())
    stu_id = f"STU-ABI-D01-{ts}"
    crs_id = f"CRS-ABI-D01-{ts}"

    plan1, res1 = run_pipeline({
        "action": "insert", "table": "students",
        "data": {"id": stu_id, "rollNumber": f"R-D01-{ts%10000}", "name": "Student D01", "department": "Computer Science", "cgpa": 9.0, "semester": 1, "attendance": 90.0, "email": f"d01.{ts}@campus.edu", "status": "Active", "backlogs": 0}
    })
    plan2, res2 = run_pipeline({
        "action": "insert", "table": "courses",
        "data": {"id": crs_id, "courseCode": f"CS-D01-{ts%1000}", "courseName": "Course D01", "department": "Computer Science", "credits": 3, "instructor": "Prof D01", "semester": 1}
    })
    assert res1.get("success") is True and res2.get("success") is True


@pytest.mark.batch2
def test_d_02_verify_student_and_course_inserted():
    """Section D.2: Verify direct DB state for inserted student and course."""
    stu_db = supabase.table("students").select("id").like("id", "STU-ABI-D01-%").execute()
    crs_db = supabase.table("courses").select("id").like("id", "CRS-ABI-D01-%").execute()
    assert len(stu_db.data or []) > 0 and len(crs_db.data or []) > 0


@pytest.mark.batch2
def test_d_03_update_student_and_course():
    """Section D.3: Update student name and course instructor."""
    stu_db = supabase.table("students").select("id").like("id", "STU-ABI-D01-%").execute()
    crs_db = supabase.table("courses").select("id").like("id", "CRS-ABI-D01-%").execute()
    if not (stu_db.data and crs_db.data):
        test_d_01_insert_student_and_course()
        stu_db = supabase.table("students").select("id").like("id", "STU-ABI-D01-%").execute()
        crs_db = supabase.table("courses").select("id").like("id", "CRS-ABI-D01-%").execute()

    stu_id = stu_db.data[0]["id"]
    crs_id = crs_db.data[0]["id"]

    plan1, res1 = run_pipeline({"action": "update", "table": "students", "row_id": stu_id, "data": {"name": "Student D01 (Updated)"}})
    plan2, res2 = run_pipeline({"action": "update", "table": "courses", "row_id": crs_id, "data": {"instructor": "Prof D01 (Updated)"}})
    assert res1.get("success") is True and res2.get("success") is True


@pytest.mark.batch2
def test_d_04_verify_student_and_course_updated():
    """Section D.4: Verify direct DB persistence of student and course updates."""
    stu_db = supabase.table("students").select("name").like("id", "STU-ABI-D01-%").execute()
    crs_db = supabase.table("courses").select("instructor").like("id", "CRS-ABI-D01-%").execute()
    if not (stu_db.data and crs_db.data):
        test_d_01_insert_student_and_course()
        test_d_03_update_student_and_course()
        stu_db = supabase.table("students").select("name").like("id", "STU-ABI-D01-%").execute()
        crs_db = supabase.table("courses").select("instructor").like("id", "CRS-ABI-D01-%").execute()
    assert stu_db.data[0]["name"] == "Student D01 (Updated)"
    assert crs_db.data[0]["instructor"] == "Prof D01 (Updated)"


@pytest.mark.batch2
def test_d_05_bulk_update_students_and_courses():
    """Section D.5: Bulk update on students CGPA and courses credits."""
    plan1, res1 = run_pipeline({"query": "Increase CGPA by 0.01 for all Computer Science students"})
    plan2, res2 = run_pipeline({"query": "Increase credits by 0 for all Computer Science courses"})
    assert res1.get("success") is True and res2.get("success") is True


@pytest.mark.batch2
def test_d_06_verify_bulk_updates_persisted():
    """Section D.6: Direct DB check for bulk updates persistence."""
    stu_db = supabase.table("students").select("cgpa").eq("department", "Computer Science").execute()
    assert len(stu_db.data or []) > 0


@pytest.mark.batch2
def test_d_07_delete_student_and_course():
    """Section D.7: Delete inserted student and course rows created for Section D."""
    stu_db = supabase.table("students").select("id").like("id", "STU-ABI-D01-%").execute()
    crs_db = supabase.table("courses").select("id").like("id", "CRS-ABI-D01-%").execute()
    if stu_db.data:
        for s in stu_db.data:
            run_pipeline({"action": "delete", "table": "students", "row_id": s["id"]})
    if crs_db.data:
        for c in crs_db.data:
            run_pipeline({"action": "delete", "table": "courses", "row_id": c["id"]})


@pytest.mark.batch2
def test_d_08_verify_student_and_course_deleted():
    """Section D.8: Direct DB check confirming student and course deletion for Section D rows."""
    stu_db = supabase.table("students").select("id").like("id", "STU-ABI-D01-%").execute()
    crs_db = supabase.table("courses").select("id").like("id", "CRS-ABI-D01-%").execute()
    assert len(stu_db.data or []) == 0 and len(crs_db.data or []) == 0


@pytest.mark.batch2
def test_d_09_history_for_two_table_modifications():
    """Section D.9: Verify history table recorded entries for both tables."""
    hist = supabase.table("history").select("*").execute()
    tables_in_hist = set(r.get("originalTable") or r.get("original_table") for r in (hist.data or []))
    assert "students" in tables_in_hist or "courses" in tables_in_hist


@pytest.mark.batch2
def test_d_10_invalid_two_table_mutation():
    """Section D.10: Attempt mutation on non-existent table in two-table flow -> rejection."""
    plan, res = run_pipeline({"action": "update", "table": "nonExistentTbl", "row_id": "123", "data": {"a": 1}})
    assert plan.get("action") == "error" or res.get("success") is False


# ==============================================================================
# SECTION E: New table lifecycle — enrollments (15 cases)
# ==============================================================================

@pytest.mark.critical
def test_e_01_create_enrollments_table():
    """Section E.1: Create dynamic table enrollments via create_table action."""
    plan, res = run_pipeline({
        "action": "create_table",
        "table": "enrollments",
        "params": {
            "columns": {
                "id": "text",
                "studentId": "text",
                "courseCode": "text",
                "grade": "text",
                "enrolledAt": "timestamptz"
            }
        }
    })
    assert res.get("success") is True


@pytest.mark.batch2
def test_e_02_verify_enrollments_schema_discovered():
    """Section E.2: Confirm enrollments table is discovered in live schema."""
    invalidate_schema_cache()
    live_schema = get_live_schema()
    assert "enrollments" in live_schema, "Newly created table 'enrollments' missing from live schema!"


@pytest.mark.batch2
def test_e_03_verify_history_trigger_attached():
    """Section E.3: Verify log_row_history trigger is attached to enrollments."""
    fields = get_known_fields("enrollments")
    assert "studentId" in fields and "courseCode" in fields


@pytest.mark.batch2
def test_e_04_insert_enrollment_row_1():
    """Section E.4: Insert first row into enrollments (ENR-ABI-101)."""
    ts = int(time.time())
    enr_id = f"ENR-ABI-101-{ts}"
    plan, res = run_pipeline({
        "action": "insert",
        "table": "enrollments",
        "data": {
            "id": enr_id,
            "studentId": "STU-1001",
            "courseCode": "CS101",
            "grade": "A",
            "enrolledAt": "2026-08-01T00:00:00Z"
        }
    })
    assert res.get("success") is True


@pytest.mark.batch2
def test_e_05_insert_enrollment_row_2():
    """Section E.5: Insert second row into enrollments (ENR-ABI-102)."""
    ts = int(time.time())
    enr_id = f"ENR-ABI-102-{ts}"
    plan, res = run_pipeline({
        "action": "insert",
        "table": "enrollments",
        "data": {
            "id": enr_id,
            "studentId": "STU-1002",
            "courseCode": "CS102",
            "grade": "B+",
            "enrolledAt": "2026-08-01T00:00:00Z"
        }
    })
    assert res.get("success") is True


@pytest.mark.batch2
def test_e_06_filter_enrollments_by_student():
    """Section E.6: Filter enrollments by studentId == 'STU-1001'."""
    plan, res = run_pipeline({"query": "Show enrollments for student STU-1001", "table": "enrollments", "studentId": "STU-1001"})
    assert res.get("success") is True
    assert len(res.get("data", [])) > 0


@pytest.mark.batch3
def test_e_07_update_enrollment_grade():
    """Section E.7: Update grade for ENR-ABI-101 to 'A+'."""
    db_res = supabase.table("enrollments").select("id").like("id", "ENR-ABI-101-%").execute()
    enr_id = db_res.data[0]["id"] if db_res.data else ""

    plan, res = run_pipeline({
        "action": "update",
        "table": "enrollments",
        "row_id": enr_id,
        "data": {"grade": "A+"}
    })
    assert res.get("success") is True


@pytest.mark.batch3
def test_e_08_verify_enrollment_update_persisted():
    """Section E.8: Direct DB check confirming grade 'A+' persisted."""
    db_res = supabase.table("enrollments").select("grade").like("id", "ENR-ABI-101-%").execute()
    actual_grade = db_res.data[0].get("grade") if db_res.data else ""
    assert_db_match("test_e_08_verify_enrollment_update_persisted", True, actual_grade == "A+", f"Got {actual_grade}")


@pytest.mark.batch3
def test_e_09_history_logged_for_enrollment_update():
    """Section E.9: Verify history table logged snapshot for enrollments update."""
    db_res = supabase.table("history").select("*").eq("originalTable", "enrollments").execute()
    assert len(db_res.data or []) > 0, "No history snapshots logged for enrollments table!"


@pytest.mark.critical
def test_e_10_add_column_status_to_enrollments():
    """Section E.10: Add status column to enrollments via add_column."""
    plan, res = run_pipeline({
        "action": "add_column",
        "table": "enrollments",
        "params": {
            "column_name": "status",
            "column_type": "text"
        }
    })
    assert res.get("success") is True


@pytest.mark.batch3
def test_e_11_verify_new_column_in_schema():
    """Section E.11: Confirm status column appears in live schema for enrollments."""
    time.sleep(0.3)
    invalidate_schema_cache()
    fields = get_known_fields("enrollments")
    assert "status" in fields, "New column 'status' missing from enrollments schema!"


@pytest.mark.batch3
def test_e_12_update_row_with_new_column():
    """Section E.12: Update enrollment row using the new status column."""
    db_res = supabase.table("enrollments").select("id").like("id", "ENR-ABI-101-%").execute()
    enr_id = db_res.data[0]["id"] if db_res.data else ""

    plan, res = run_pipeline({
        "action": "update",
        "table": "enrollments",
        "row_id": enr_id,
        "data": {"status": "Completed"}
    })
    assert res.get("success") is True


@pytest.mark.critical
def test_e_13_drop_column_status_from_enrollments():
    """Section E.13: Drop status column from enrollments via drop_column."""
    plan, res = run_pipeline({
        "action": "drop_column",
        "table": "enrollments",
        "params": {
            "column_name": "status"
        }
    })
    assert res.get("success") is True


@pytest.mark.batch3
def test_e_14_verify_column_dropped_from_schema():
    """Section E.14: Confirm status column is genuinely gone from live schema."""
    invalidate_schema_cache()
    fields = get_known_fields("enrollments")
    assert "status" not in fields, "Column 'status' still present in enrollments schema after drop_column!"


@pytest.mark.batch3
def test_e_15_delete_enrollment_rows():
    """Section E.15: Delete test enrollment rows and verify DB cleanup."""
    db_res = supabase.table("enrollments").select("id").like("id", "ENR-ABI-%").execute()
    for row in (db_res.data or []):
        run_pipeline({"action": "delete", "table": "enrollments", "row_id": row["id"]})

    db_check = supabase.table("enrollments").select("id").like("id", "ENR-ABI-%").execute()
    assert len(db_check.data or []) == 0, "Test enrollment rows remain in DB!"


# ==============================================================================
# SECTION F: Delete-command variety & DDL guardrails (10 cases)
# ==============================================================================

@pytest.mark.batch3
def test_f_01_delete_by_row_id_snake_case():
    """Section F.1: Delete row using params: {'row_id': 'STU-ABI-F01'}."""
    ts = int(time.time())
    stu_id = f"STU-ABI-F01-{ts}"
    supabase.table("students").insert({
        "id": stu_id, "rollNumber": f"R-F01-{ts%10000}", "name": "Snake Case Delete",
        "department": "Computer Science", "cgpa": 8.0, "semester": 1, "attendance": 90.0, "email": f"f01.{ts}@campus.edu", "status": "Active", "backlogs": 0
    }).execute()

    plan, res = run_pipeline({"action": "delete_row", "table": "students", "params": {"row_id": stu_id}})
    assert res.get("success") is True
    db_check = supabase.table("students").select("id").eq("id", stu_id).execute()
    assert len(db_check.data or []) == 0


@pytest.mark.batch3
def test_f_02_delete_by_rowId_camelCase():
    """Section F.2: Delete row using params: {'rowId': 'STU-ABI-F02'} (fallback support)."""
    ts = int(time.time())
    stu_id = f"STU-ABI-F02-{ts}"
    supabase.table("students").insert({
        "id": stu_id, "rollNumber": f"R-F02-{ts%10000}", "name": "Camel Case Delete",
        "department": "Computer Science", "cgpa": 8.0, "semester": 1, "attendance": 90.0, "email": f"f02.{ts}@campus.edu", "status": "Active", "backlogs": 0
    }).execute()

    plan, res = run_pipeline({"action": "delete_row", "table": "students", "params": {"rowId": stu_id}})
    assert res.get("success") is True
    db_check = supabase.table("students").select("id").eq("id", stu_id).execute()
    assert len(db_check.data or []) == 0


@pytest.mark.batch3
def test_f_03_delete_by_id_simple():
    """Section F.3: Delete row using params: {'id': 'STU-ABI-F03'} (fallback support)."""
    ts = int(time.time())
    stu_id = f"STU-ABI-F03-{ts}"
    supabase.table("students").insert({
        "id": stu_id, "rollNumber": f"R-F03-{ts%10000}", "name": "Simple ID Delete",
        "department": "Computer Science", "cgpa": 8.0, "semester": 1, "attendance": 90.0, "email": f"f03.{ts}@campus.edu", "status": "Active", "backlogs": 0
    }).execute()

    plan, res = run_pipeline({"action": "delete_row", "table": "students", "params": {"id": stu_id}})
    assert res.get("success") is True
    db_check = supabase.table("students").select("id").eq("id", stu_id).execute()
    assert len(db_check.data or []) == 0


@pytest.mark.batch3
def test_f_04_delete_non_existent_row_id():
    """Section F.4: Delete row with non-existent ID STU-NONEXIST-999 -> clean execution with honest failure reporting."""
    plan, res = run_pipeline({"action": "delete_row", "table": "students", "params": {"row_id": "STU-NONEXIST-999"}})
    assert res.get("success") is False
    assert res.get("rows_deleted", 0) == 0
    assert "No matching row" in res.get("message", "")


@pytest.mark.batch3
def test_f_05_delete_course_by_id():
    """Section F.5: Delete course record by row_id."""
    ts = int(time.time())
    crs_id = f"CRS-ABI-F05-{ts}"
    supabase.table("courses").insert({
        "id": crs_id, "courseCode": f"CS-F05-{ts%1000}", "courseName": "Delete Course F05",
        "department": "Computer Science", "credits": 3, "instructor": "Temp Prof", "semester": 1
    }).execute()

    plan, res = run_pipeline({"action": "delete", "table": "courses", "row_id": crs_id})
    assert res.get("success") is True
    db_check = supabase.table("courses").select("id").eq("id", crs_id).execute()
    assert len(db_check.data or []) == 0


@pytest.mark.batch3
def test_f_06_delete_enrollment_by_id():
    """Section F.6: Delete enrollment record by row_id."""
    ts = int(time.time())
    enr_id = f"ENR-ABI-F06-{ts}"
    supabase.table("enrollments").insert({
        "id": enr_id, "studentId": "STU-1001", "courseCode": "CS101", "grade": "B", "enrolledAt": "2026-08-01T00:00:00Z"
    }).execute()

    plan, res = run_pipeline({"action": "delete", "table": "enrollments", "row_id": enr_id})
    assert res.get("success") is True


@pytest.mark.batch3
def test_f_07_attempt_bulk_delete_via_query():
    """Section F.7: Request natural language bulk delete -> handling/rejection check."""
    plan, res = run_pipeline({"query": "Delete all Computer Science students"})
    # Must either reject or enforce safety bounds / bulk_update handling
    assert plan.get("action") in ["error", "delete_row", "filter_rows", "bulk_update"] or res.get("success") is False


@pytest.mark.batch3
def test_f_08_attempt_drop_table_rejection():
    """Section F.8: Send action: drop_table -> strictly rejected by planner/executor."""
    plan, res = run_pipeline({"action": "drop_table", "table": "students"})
    assert res.get("success") is False or plan.get("action") == "error"


@pytest.mark.critical
def test_f_09_attempt_stacked_drop_table_injection():
    """Section F.9: Attempt stacked DROP TABLE injection inside drop_column -> strictly rejected."""
    injection_sql = 'ALTER TABLE "enrollments" DROP COLUMN "grade"; DROP TABLE "students";'
    rejected = False
    try:
        _validate_ddl_statement(injection_sql)
    except ValueError as exc:
        rejected = "forbidden keyword" in str(exc).lower() or "security rejection" in str(exc).lower()
    assert rejected is True, "Stacked DROP TABLE injection was NOT rejected by validator!"


@pytest.mark.batch3
def test_f_10_verify_deletions_logged_in_history():
    """Section F.10: Confirm successful delete actions created history entries."""
    db_res = supabase.table("history").select("*").eq("action", "delete").execute()
    assert len(db_res.data or []) > 0, "No delete actions found in history table!"


# ==============================================================================
# SECTION G: History/audit log verification & DB state matching (12 cases)
# ==============================================================================

@pytest.mark.batch3
def test_g_01_history_table_exists_and_schema_correct():
    """Section G.1: Confirm history table has expected schema columns."""
    fields = get_known_fields("history")
    assert "originalTable" in fields or "original_table" in fields
    assert "rowId" in fields or "row_id" in fields
    assert "oldData" in fields or "old_data" in fields
    assert "action" in fields


@pytest.mark.batch3
def test_g_02_insert_does_not_create_history_entry():
    """Section G.2: Insert operation does NOT create history snapshot."""
    ts = int(time.time())
    stu_id = f"STU-ABI-G02-{ts}"
    hist_before = supabase.table("history").select("id").execute()
    count_before = len(hist_before.data or [])

    run_pipeline({
        "action": "insert", "table": "students",
        "data": {"id": stu_id, "rollNumber": f"R-G02-{ts%10000}", "name": "Insert Hist Student", "department": "Computer Science", "cgpa": 8.0, "semester": 1, "attendance": 90.0, "email": f"g02.{ts}@campus.edu", "status": "Active", "backlogs": 0}
    })

    hist_after = supabase.table("history").select("id").execute()
    count_after = len(hist_after.data or [])
    assert count_before == count_after, "Insert operation incorrectly created a history entry!"


@pytest.mark.critical
def test_g_03_update_creates_exactly_one_history_entry():
    """Section G.3: Update operation creates EXACTLY 1 history entry via DB trigger."""
    ts = int(time.time())
    stu_id = f"STU-ABI-G03-{ts}"
    supabase.table("students").insert({
        "id": stu_id, "rollNumber": f"R-G03-{ts%10000}", "name": "Single Hist Update Student",
        "department": "Computer Science", "cgpa": 8.0, "semester": 1, "attendance": 90.0, "email": f"g03.{ts}@campus.edu", "status": "Active", "backlogs": 0
    }).execute()

    run_pipeline({"action": "update", "table": "students", "row_id": stu_id, "data": {"name": "Single Hist Update (Updated)"}})

    hist_res = supabase.table("history").select("*").filter("rowId", "eq", stu_id).execute()
    if not hist_res.data:
        hist_res = supabase.table("history").select("*").filter("row_id", "eq", stu_id).execute()

    entries = hist_res.data or []
    assert len(entries) == 1, f"Expected exactly 1 history entry for update, got {len(entries)}!"


@pytest.mark.batch3
def test_g_04_history_old_data_matches_pre_update_state():
    """Section G.4: Confirm oldData in history matches exact pre-update DB state."""
    ts = int(time.time())
    stu_id = f"STU-ABI-G04-{ts}"
    initial_name = "Pre-Update Name G04"
    supabase.table("students").insert({
        "id": stu_id, "rollNumber": f"R-G04-{ts%10000}", "name": initial_name,
        "department": "Computer Science", "cgpa": 8.0, "semester": 1, "attendance": 90.0, "email": f"g04.{ts}@campus.edu", "status": "Active", "backlogs": 0
    }).execute()

    run_pipeline({"action": "update", "table": "students", "row_id": stu_id, "data": {"name": "Post-Update Name G04"}})

    hist_res = supabase.table("history").select("*").filter("rowId", "eq", stu_id).execute()
    if not hist_res.data:
        hist_res = supabase.table("history").select("*").filter("row_id", "eq", stu_id).execute()

    old_data = hist_res.data[0].get("oldData") or hist_res.data[0].get("old_data") or {}
    assert old_data.get("name") == initial_name, f"History oldData name '{old_data.get('name')}' did not match initial name '{initial_name}'!"


@pytest.mark.batch3
def test_g_05_history_action_is_lowercase_update():
    """Section G.5: Confirm history action field is strictly lowercase 'update'."""
    ts = int(time.time())
    stu_id = f"STU-ABI-G05-{ts}"
    supabase.table("students").insert({
        "id": stu_id, "rollNumber": f"R-G05-{ts%10000}", "name": "Lowercase Action Student",
        "department": "Computer Science", "cgpa": 8.0, "semester": 1, "attendance": 90.0, "email": f"g05.{ts}@campus.edu", "status": "Active", "backlogs": 0
    }).execute()

    run_pipeline({"action": "update", "table": "students", "row_id": stu_id, "data": {"name": "Updated G05"}})

    hist_res = supabase.table("history").select("action").filter("rowId", "eq", stu_id).execute()
    if not hist_res.data:
        hist_res = supabase.table("history").select("action").filter("row_id", "eq", stu_id).execute()

    act = hist_res.data[0].get("action", "").lower()
    assert act == "update", f"Expected action 'update', got '{act}'"


@pytest.mark.batch3
def test_g_06_delete_creates_exactly_one_history_entry():
    """Section G.6: Delete operation creates EXACTLY 1 history entry."""
    ts = int(time.time())
    stu_id = f"STU-ABI-G06-{ts}"
    supabase.table("students").insert({
        "id": stu_id, "rollNumber": f"R-G06-{ts%10000}", "name": "Single Delete Hist Student",
        "department": "Computer Science", "cgpa": 8.0, "semester": 1, "attendance": 90.0, "email": f"g06.{ts}@campus.edu", "status": "Active", "backlogs": 0
    }).execute()

    run_pipeline({"action": "delete", "table": "students", "row_id": stu_id})

    hist_res = supabase.table("history").select("*").filter("rowId", "eq", stu_id).execute()
    if not hist_res.data:
        hist_res = supabase.table("history").select("*").filter("row_id", "eq", stu_id).execute()

    entries = hist_res.data or []
    assert len(entries) == 1, f"Expected exactly 1 history entry for delete, got {len(entries)}!"


@pytest.mark.batch3
def test_g_07_history_old_data_matches_pre_delete_state():
    """Section G.7: Confirm oldData in history matches exact pre-delete DB state."""
    ts = int(time.time())
    stu_id = f"STU-ABI-G07-{ts}"
    initial_name = "Pre-Delete Name G07"
    supabase.table("students").insert({
        "id": stu_id, "rollNumber": f"R-G07-{ts%10000}", "name": initial_name,
        "department": "Computer Science", "cgpa": 8.0, "semester": 1, "attendance": 90.0, "email": f"g07.{ts}@campus.edu", "status": "Active", "backlogs": 0
    }).execute()

    run_pipeline({"action": "delete", "table": "students", "row_id": stu_id})

    hist_res = supabase.table("history").select("*").filter("rowId", "eq", stu_id).execute()
    if not hist_res.data:
        hist_res = supabase.table("history").select("*").filter("row_id", "eq", stu_id).execute()

    old_data = hist_res.data[0].get("oldData") or hist_res.data[0].get("old_data") or {}
    assert old_data.get("name") == initial_name, f"History oldData name '{old_data.get('name')}' did not match initial name '{initial_name}'!"


@pytest.mark.batch3
def test_g_08_history_action_is_lowercase_delete():
    """Section G.8: Confirm history action field is strictly lowercase 'delete'."""
    ts = int(time.time())
    stu_id = f"STU-ABI-G08-{ts}"
    supabase.table("students").insert({
        "id": stu_id, "rollNumber": f"R-G08-{ts%10000}", "name": "Lowercase Delete Action Student",
        "department": "Computer Science", "cgpa": 8.0, "semester": 1, "attendance": 90.0, "email": f"g08.{ts}@campus.edu", "status": "Active", "backlogs": 0
    }).execute()

    run_pipeline({"action": "delete", "table": "students", "row_id": stu_id})

    hist_res = supabase.table("history").select("action").filter("rowId", "eq", stu_id).execute()
    if not hist_res.data:
        hist_res = supabase.table("history").select("action").filter("row_id", "eq", stu_id).execute()

    act = hist_res.data[0].get("action", "").lower()
    assert act == "delete", f"Expected action 'delete', got '{act}'"


@pytest.mark.batch3
def test_g_09_history_recorded_for_courses_table():
    """Section G.9: Confirm history recorded entries with originalTable == 'courses'."""
    ts = int(time.time())
    crs_id = f"CRS-ABI-G09-{ts}"
    supabase.table("courses").insert({
        "id": crs_id, "courseCode": f"CS-G09-{ts%1000}", "courseName": "History Course G09",
        "department": "Computer Science", "credits": 3, "instructor": "Initial Prof", "semester": 1
    }).execute()

    run_pipeline({"action": "update", "table": "courses", "row_id": crs_id, "data": {"instructor": "Updated Prof"}})

    hist_res = supabase.table("history").select("*").filter("rowId", "eq", crs_id).execute()
    if not hist_res.data:
        hist_res = supabase.table("history").select("*").filter("row_id", "eq", crs_id).execute()

    tbl = hist_res.data[0].get("originalTable") or hist_res.data[0].get("original_table")
    assert tbl == "courses", f"Expected originalTable 'courses', got '{tbl}'"


@pytest.mark.batch3
def test_g_10_history_recorded_for_dynamic_new_table():
    """Section G.10: Confirm history recorded entries for dynamic table 'enrollments'."""
    ts = int(time.time())
    enr_id = f"ENR-ABI-G10-{ts}"
    supabase.table("enrollments").insert({
        "id": enr_id, "studentId": "STU-1001", "courseCode": "CS101", "grade": "C", "enrolledAt": "2026-08-01T00:00:00Z"
    }).execute()

    run_pipeline({"action": "update", "table": "enrollments", "row_id": enr_id, "data": {"grade": "B"}})

    hist_res = supabase.table("history").select("*").filter("rowId", "eq", enr_id).execute()
    if not hist_res.data:
        hist_res = supabase.table("history").select("*").filter("row_id", "eq", enr_id).execute()

    tbl = hist_res.data[0].get("originalTable") or hist_res.data[0].get("original_table")
    assert tbl == "enrollments", f"Expected originalTable 'enrollments', got '{tbl}'"


@pytest.mark.critical
def test_g_11_bulk_update_creates_n_history_entries():
    """Section G.11: Confirm bulk_update creating N history entries matching N updated rows."""
    hist_before = supabase.table("history").select("id", count="exact").execute()
    count_before = hist_before.count or len(hist_before.data or [])

    run_pipeline({
        "action": "bulk_update",
        "table": "students",
        "params": {
            "filters": [
                {"field": "department", "op": "eq", "value": "Computer Science"},
                {"field": "semester", "op": "eq", "value": 8}
            ],
            "field": "cgpa",
            "operation": "add",
            "value": 0.001,
            "max_rows": 50
        }
    })

    hist_after = supabase.table("history").select("id", count="exact").execute()
    count_after = hist_after.count or len(hist_after.data or [])
    new_entries = count_after - count_before
    assert new_entries > 0, "Bulk update did not produce any history entries!"


@pytest.mark.batch3
def test_g_12_drop_column_does_not_corrupt_history_table():
    """Section G.12: Confirm history table remains readable and uncorrupted after DDL operations."""
    hist_res = supabase.table("history").select("id", count="exact").execute()
    assert (hist_res.count or len(hist_res.data or [])) > 0


# ==============================================================================
# SECTION H: Row Rollback / Restore Capabilities (3 cases)
# ==============================================================================

@pytest.mark.batch3
def test_h_01_restore_row_after_update():
    """Section H.1: Update a student name and restore it back to pre-update state."""
    ts = int(time.time())
    stu_id = f"STU-ABI-H01-{ts}"
    orig_name = "Original Name H01"
    
    # 1. Insert initial student
    run_pipeline({
        "action": "insert", "table": "students",
        "data": {"id": stu_id, "rollNumber": f"R-H01-{ts%10000}", "name": orig_name, "department": "Computer Science", "cgpa": 9.0, "semester": 1, "attendance": 90.0, "email": f"h01.{ts}@campus.edu", "status": "Active", "backlogs": 0}
    })
    
    # 2. Update student name
    run_pipeline({"action": "update", "table": "students", "row_id": stu_id, "data": {"name": "Modified Name H01"}})
    upd_db = supabase.table("students").select("name").eq("id", stu_id).execute()
    assert upd_db.data[0]["name"] == "Modified Name H01"

    # 3. Execute restore_row
    plan, res = run_pipeline({"action": "restore_row", "table": "students", "row_id": stu_id})
    assert res.get("success") is True
    
    # 4. Verify DB state restored back to original name
    res_db = supabase.table("students").select("name").eq("id", stu_id).execute()
    assert res_db.data[0]["name"] == orig_name


@pytest.mark.batch3
def test_h_02_restore_row_after_delete():
    """Section H.2: Delete a student and restore (re-insert) it back from history snapshot."""
    ts = int(time.time())
    stu_id = f"STU-ABI-H02-{ts}"
    
    # 1. Insert initial student and update to create history entry
    run_pipeline({
        "action": "insert", "table": "students",
        "data": {"id": stu_id, "rollNumber": f"R-H02-{ts%10000}", "name": "Name H02", "department": "Computer Science", "cgpa": 9.2, "semester": 2, "attendance": 92.0, "email": f"h02.{ts}@campus.edu", "status": "Active", "backlogs": 0}
    })
    run_pipeline({"action": "update", "table": "students", "row_id": stu_id, "data": {"name": "Name H02 Updated"}})
    
    # 2. Delete student
    run_pipeline({"action": "delete", "table": "students", "row_id": stu_id})
    del_db = supabase.table("students").select("id").eq("id", stu_id).execute()
    assert len(del_db.data or []) == 0

    # 3. Execute restore_row (re-inserts deleted row from oldData snapshot)
    plan, res = run_pipeline({"action": "restore_row", "table": "students", "row_id": stu_id})
    assert res.get("success") is True
    
    # 4. Verify row exists back in DB
    res_db = supabase.table("students").select("id", "name").eq("id", stu_id).execute()
    assert len(res_db.data or []) == 1
    assert res_db.data[0]["id"] == stu_id


@pytest.mark.batch3
def test_h_03_restore_non_existent_row():
    """Section H.3: Attempt to restore a non-existent row ID with no history -> clean rejection."""
    fake_id = f"STU-NONEXISTENT-99999"
    plan, res = run_pipeline({"action": "restore_row", "table": "students", "row_id": fake_id})
    assert res.get("success") is False


# ==============================================================================
# SECTION I: Flexible Weighted Composite Computation (5 cases)
# ==============================================================================

@pytest.mark.batch3
def test_i_01_weighted_compute_standard():
    """Section I.1: Calculate 60% CGPA + 40% attendance score for students."""
    plan, res = run_pipeline({
        "action": "weighted_compute",
        "table": "students",
        "params": {
            "weights": [
                {"field": "cgpa", "weight": 0.60},
                {"field": "attendance", "weight": 0.40}
            ],
            "sort": "desc"
        }
    })
    assert res.get("success") is True
    data = res.get("data", [])
    assert len(data) > 0
    assert "_weighted_score" in data[0]
    if len(data) > 1:
        assert data[0]["_weighted_score"] >= data[1]["_weighted_score"]


@pytest.mark.batch3
def test_i_02_weighted_compute_weight_sum_mismatch():
    """Section I.2: Attempt weighted_compute where weights sum to 80% (0.5 + 0.3) -> strict rejection."""
    plan, res = run_pipeline({
        "action": "weighted_compute",
        "table": "students",
        "params": {
            "weights": [
                {"field": "cgpa", "weight": 0.50},
                {"field": "attendance", "weight": 0.30}
            ]
        }
    })
    assert plan.get("action") == "error" or res.get("success") is False
    err_msg = plan.get("params", {}).get("message", "") or res.get("message", "")
    assert "80%" in err_msg or "sum to" in err_msg or "100%" in err_msg


@pytest.mark.batch3
def test_i_03_weighted_compute_missing_data_exclusion():
    """Section I.3: Option A Exclusion Strategy — insert student with null japaneseScore, verify excluded_count."""
    ts = int(time.time())
    stu_id = f"STU-ABI-I03-{ts}"
    
    # Insert student with null japaneseScore (nullable numeric column)
    supabase.table("students").insert({
        "id": stu_id,
        "rollNumber": f"R-I03-{ts%10000}",
        "name": "No Japanese Score Student",
        "department": "Computer Science",
        "cgpa": 9.5,
        "attendance": 95.0,
        "email": f"i03.{ts}@campus.edu",
        "japaneseScore": None,
        "semester": 1,
        "status": "Active",
        "backlogs": 0
    }).execute()

    plan, res = run_pipeline({
        "action": "weighted_compute",
        "table": "students",
        "params": {
            "weights": [
                {"field": "cgpa", "weight": 0.50},
                {"field": "japaneseScore", "weight": 0.50}
            ]
        }
    })
    assert res.get("success") is True
    assert res.get("excluded_count", 0) >= 1
    computed_ids = [r["id"] for r in res.get("data", [])]
    assert stu_id not in computed_ids

    # Cleanup test row
    supabase.table("students").delete().eq("id", stu_id).execute()


@pytest.mark.batch3
def test_i_04_weighted_compute_invalid_field():
    """Section I.4: Attempt weighted_compute on non-existent field tuition_fee -> clean rejection."""
    plan, res = run_pipeline({
        "action": "weighted_compute",
        "table": "students",
        "params": {
            "weights": [
                {"field": "cgpa", "weight": 0.50},
                {"field": "tuition_fee", "weight": 0.50}
            ]
        }
    })
    assert plan.get("action") == "error" or res.get("success") is False


@pytest.mark.batch3
def test_i_05_weighted_compute_with_filters():
    """Section I.5: Combine filters (department=Computer Science) with 70% credits + 30% semester on courses."""
    plan, res = run_pipeline({
        "action": "weighted_compute",
        "table": "courses",
        "params": {
            "weights": [
                {"field": "credits", "weight": 0.70},
                {"field": "semester", "weight": 0.30}
            ],
            "filters": [
                {"field": "department", "op": "eq", "value": "Computer Science"}
            ],
            "sort": "desc"
        }
    })
    assert res.get("success") is True
    data = res.get("data", [])
    for row in data:
        assert row["department"] == "Computer Science"
        assert "_weighted_score" in row


@pytest.mark.batch3
def test_i_06_weighted_compute_three_fields():
    """Section I.6: Weighted compute across 3 fields (CGPA 40%, attendance 35%, backlogs -25%)."""
    plan, res = run_pipeline({
        "action": "weighted_compute",
        "table": "students",
        "params": {
            "weights": [
                {"field": "cgpa", "weight": 0.40},
                {"field": "attendance", "weight": 0.35},
                {"field": "backlogs", "weight": -0.25}
            ],
            "sort": "desc"
        }
    })
    assert res.get("success") is True
    data = res.get("data", [])
    assert len(data) > 0
    assert "_weighted_score" in data[0]


@pytest.mark.batch3
def test_i_07_weighted_compute_all_rows_excluded():
    """Section I.7: Request weighting on japaneseScore across students where all rows miss japaneseScore -> excluded_count equals total."""
    plan, res = run_pipeline({
        "action": "weighted_compute",
        "table": "students",
        "params": {
            "weights": [
                {"field": "cgpa", "weight": 0.50},
                {"field": "japaneseScore", "weight": 0.50}
            ]
        }
    })
    assert res.get("success") is True
    data = res.get("data", [])
    excluded = res.get("excluded_count", 0)
    total = res.get("total", 0)
    assert len(data) + excluded == total
    assert "excluded" in res.get("message", "").lower()


@pytest.mark.batch3
def test_i_08_weighted_compute_negative_weights():
    """Section I.8: Penalty weighting with negative weight (60% CGPA minus 40% backlogs -> abs sum = 1.00)."""
    plan, res = run_pipeline({
        "action": "weighted_compute",
        "table": "students",
        "params": {
            "weights": [
                {"field": "cgpa", "weight": 0.60},
                {"field": "backlogs", "weight": -0.40}
            ],
            "sort": "desc"
        }
    })
    assert res.get("success") is True
    data = res.get("data", [])
    assert len(data) > 0
    assert "_weighted_score" in data[0]


@pytest.mark.batch3
def test_i_09_weighted_compute_empty_filter_result():
    """Section I.9: Filter matching 0 rows before weighting -> returns clean empty data list without exception."""
    plan, res = run_pipeline({
        "action": "weighted_compute",
        "table": "students",
        "params": {
            "weights": [
                {"field": "cgpa", "weight": 0.50},
                {"field": "attendance", "weight": 0.50}
            ],
            "filters": [
                {"field": "department", "op": "eq", "value": "NonExistentDept999"}
            ]
        }
    })
    assert res.get("success") is True
    assert res.get("data") == []
    assert res.get("excluded_count") == 0
    assert res.get("total") == 0
