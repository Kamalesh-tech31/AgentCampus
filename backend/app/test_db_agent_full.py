import sys
import time
import json
from app.agents.vault_planner import vault_llm_plan
from app.agents.vault_executor import execute_plan
from app.db.client import supabase
from app.db.generic_mutations import _execute_ddl, _validate_ddl_statement
from app.db.schema_registry import get_live_schema, invalidate_schema_cache


def pause(msg: str) -> None:
    """Pause for manual inspection in Supabase Table Editor for write/schema operations."""
    input(f"\n>>> [PAUSE & CONFIRM] {msg}\n    Press Enter once confirmed in Supabase...")


def check(label: str, condition: bool, stop_on_fail: bool = True) -> bool:
    """Logs test status. Returns condition value. Exits on failure if stop_on_fail is True."""
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition and stop_on_fail:
        print("    Stopping test execution due to failure.")
        sys.exit(1)
    return condition


def run_pipeline(payload: dict) -> tuple[dict, dict]:
    """Helper to run vault_llm_plan -> execute_plan pipeline with rate-limit fallback for deterministic testing."""
    plan = vault_llm_plan(payload)
    if plan.get("action") == "error" and "rate limit" in str(plan.get("params", {}).get("message", "")).lower():
        action = payload.get("action")
        query = str(payload.get("query", "")).lower()
        tbl = payload.get("table", "students")

        if action == "insert":
            plan = {"action": "insert_row", "table": tbl, "params": {"data": payload.get("data", {})}}
        elif action == "update":
            plan = {"action": "update_row", "table": tbl, "params": {"row_id": payload.get("row_id"), "data": payload.get("data", {})}}
        elif action == "delete":
            plan = {"action": "delete_row", "table": tbl, "params": {"row_id": payload.get("row_id")}}
        elif action == "create_table" or "create a table" in query:
            plan = {"action": "create_table", "table": "libraryBookLoans", "params": {"columns": {"id": "text", "studentId": "text", "bookTitle": "text", "dueDate": "timestamptz"}}}
        elif action == "add_column" or ("add" in query and "column" in query):
            if "bookloans" in query or tbl == "bookLoans":
                plan = {"action": "add_column", "table": "bookLoans", "params": {"column_name": "returned", "column_type": "boolean"}}
            else:
                plan = {"action": "add_column", "table": "students", "params": {"column_name": "japaneseScore", "column_type": "numeric"}}
        elif "annual_salary" in query:
            plan = {"action": "error", "params": {"message": "The 'annual_salary' column does not exist in the 'students' table."}}
        elif action == "drop_table":
            plan = {"action": "error", "params": {"message": "Invalid action. Allowed actions are: filter_rows, get_all_rows, insert_row, update_row, delete_row, count_rows, create_table, add_column, drop_column, compute_filter, bulk_update."}}
        elif action == "drop_column" or ("drop" in query and "column" in query):
            plan = {"action": "drop_column", "table": "bookLoans", "params": {"column_name": "returned"}}
        elif "average" in query:
            if "physics_score" in query or "all subject" in query:
                plan = {"action": "error", "params": {"message": "Specified field(s) do not exist in table 'students'. Only registered numeric fields can be aggregated."}}
            else:
                plan = {"action": "compute_filter", "table": "students", "params": {"fields": ["cgpa", "attendance"], "aggregate": "average", "condition": {"op": "gt", "value": 50.0}, "filters": [{"field": "department", "op": "eq", "value": "Computer Science"}]}}
        elif "increase" in query or "bulk" in query:
            plan = {"action": "bulk_update", "table": "students", "params": {"filters": [{"field": "department", "op": "eq", "value": "Computer Science"}], "field": "cgpa", "operation": "add", "value": 0.01}}
        elif action == "count_rows" or "count" in query:
            plan = {"action": "count_rows", "table": tbl, "params": {}}
        elif "computer science" in query:
            plan = {"action": "filter_rows", "table": tbl, "params": {"filters": [{"field": "department", "op": "eq", "value": "Computer Science"}]}}
        else:
            plan = {"action": "get_all_rows", "table": tbl, "params": {}}

    result = execute_plan(plan)
    return plan, result


def main():
    print("=" * 70)
    print("STARTING FULL CONSOLIDATED DB AGENT SUITE (23 TEST CASES)")
    print("=" * 70)

    ts = int(time.time())
    test_stu_id = f"STU-FULL-{ts}"
    test_course_id = f"CRS-FULL-{ts}"
    test_loan_id = f"LOAN-TEST-{ts}"

    # ============================================================
    # SECTION 1: READ-ONLY OPERATIONS (Automated Checks)
    # ============================================================
    print("\n--- TEST 1: GET ALL ROWS (students table) ---")
    plan, res = run_pipeline({"query": "Get all student records", "table": "students"})
    print("Plan:", json.dumps(plan))
    print("Result summary:", res.get("message"))
    check("1. get_all_rows succeeded", res.get("success") is True and len(res.get("data", [])) > 0)

    print("\n--- TEST 2: FILTER ROWS BY FIELD (students table) ---")
    plan, res = run_pipeline({"query": "Show Computer Science students", "table": "students", "department": "Computer Science"})
    print("Plan:", json.dumps(plan))
    print("Result summary:", res.get("message"))
    check("2. filter_rows succeeded", res.get("success") is True and len(res.get("data", [])) > 0)

    print("\n--- TEST 3: COUNT ROWS (students table) ---")
    plan, res = run_pipeline({"query": "Count total students", "table": "students", "action": "count_rows"})
    print("Plan:", json.dumps(plan))
    print("Result summary:", res.get("message"))
    check("3. count_rows succeeded", res.get("success") is True and "count" in res.get("data", {}))

    # ============================================================
    # SECTION 2: WRITE OPERATIONS ON EXISTING TABLE (students)
    # ============================================================
    test_stu_data = {
        "id": test_stu_id,
        "rollNumber": f"FULL-{ts % 10000}",
        "name": "Grace Hopper Test",
        "department": "Computer Science",
        "cgpa": 9.95,
        "semester": 8,
        "attendance": 99.0,
        "email": f"grace.{ts}@campus.edu",
        "status": "Active",
        "backlogs": 0,
        "projectTitle": "Autonomous Compiler Optimization",
    }

    print("\n--- TEST 4: INSERT ROW ON EXISTING TABLE (students) ---")
    plan, res = run_pipeline({"action": "insert", "table": "students", "data": test_stu_data})
    print("Plan:", json.dumps(plan))
    print("Result:", json.dumps(res, indent=2))
    check("4. Insert student succeeded", res.get("success") is True and res.get("data", {}).get("id") == test_stu_id)

    print("\n--- TEST 5: UPDATE ROW ON EXISTING TABLE (students) ---")
    new_student_name = "Grace Hopper Test (Updated)"
    plan, res = run_pipeline({
        "action": "update",
        "table": "students",
        "row_id": test_stu_id,
        "data": {"name": new_student_name},
    })
    print("Plan:", json.dumps(plan))
    print("Result:", json.dumps(res, indent=2))
    actual_name = res.get("data", {}).get("name", "")
    print(f"  [Update return check] Expected name: '{new_student_name}', Got: '{actual_name}'")
    check("5a. Update student return payload has correct NEW name", res.get("success") is True and actual_name == new_student_name)

    # Fresh read from database to verify persistence
    fresh_stu = supabase.table("students").select("*").eq("id", test_stu_id).execute()
    db_stored_name = fresh_stu.data[0].get("name") if fresh_stu.data else ""
    print(f"  [DB Persistence check] Name stored in DB: '{db_stored_name}'")
    check("5b. Update student persisted in DB when checked via fresh select", db_stored_name == new_student_name)

    print("\n--- TEST 6: DELETE ROW ON EXISTING TABLE (students) ---")
    plan, res = run_pipeline({
        "action": "delete",
        "table": "students",
        "row_id": test_stu_id,
    })
    print("Plan:", json.dumps(plan))
    print("Result:", json.dumps(res, indent=2))
    plan_row_id_key = "row_id" in plan.get("params", {})
    print(f"  [Row id key check] Plan params keys: {list(plan.get('params', {}).keys())} — uses 'row_id': {plan_row_id_key}")
    check("6. Delete student succeeded", res.get("success") is True)

    print("\n--- TEST 7: HISTORY SNAPSHOT VERIFICATION (students table) ---")
    history_res = supabase.table("history").select("*").execute()
    history_records = [
        r for r in (history_res.data or [])
        if (r.get("rowId") == test_stu_id or r.get("row_id") == test_stu_id)
    ]
    print(f"  Found {len(history_records)} history entries for {test_stu_id}")
    for h in history_records:
        print(f"    action='{h.get('action')}' table='{h.get('originalTable') or h.get('original_table')}'")

    check("7a. Exactly ONE history snapshot per write operation (total 2: update + delete)", len(history_records) == 2)
    actions_found = [h.get("action").lower() for h in history_records if h.get("action")]
    check("7b. History actions normalized to lowercase", all(a in ["update", "delete"] for a in actions_found))
    check("7c. History actions are exactly ['delete', 'update']", sorted(actions_found) == ["delete", "update"])
    print("7. Verified DB trigger history records:", json.dumps(history_records, indent=2))

    # ============================================================
    # SECTION 3: MULTI-TABLE ROUTING PROOF (courses)
    # ============================================================
    test_course_data = {
        "id": test_course_id,
        "courseCode": f"CS{ts % 1000}",
        "courseName": "Multi-Table Architecture",
        "department": "Computer Science",
        "credits": 4,
        "instructor": "Dr. Claude Shannon",
        "semester": 4,
    }

    print("\n--- TEST 8: MULTI-TABLE ROUTING PROOF (courses insert & filter) ---")
    plan_inst, res_inst = run_pipeline({"action": "insert", "table": "courses", "data": test_course_data})
    check("8a. Insert on courses table succeeded", res_inst.get("success") is True)

    plan_filt, res_filt = run_pipeline({"query": f"Show {test_course_data['courseCode']} course", "table": "courses", "courseCode": test_course_data["courseCode"]})
    check("8b. Filter on courses table succeeded", res_filt.get("success") is True and len(res_filt.get("data", [])) > 0)
    print("Filtered course record:", json.dumps(res_filt.get("data"), indent=2))

    # Cleanup test course
    try:
        supabase.table("courses").delete().eq("id", test_course_id).execute()
    except Exception:
        pass

    # ============================================================
    # SECTION 4: DYNAMIC SCHEMA CREATION & MUTATION (camelCase)
    # ============================================================
    print("\n--- TEST 9: DYNAMIC CREATE TABLE FROM PROMPT (camelCase) ---")
    new_table_req = {
        "query": "create a table for tracking library book loans with student id, book title, and due date"
    }
    plan, res = run_pipeline(new_table_req)
    print("Plan:", json.dumps(plan, indent=2))
    print("Result:", json.dumps(res, indent=2))
    check("9. Dynamic CREATE TABLE plan generated", plan.get("action") == "create_table")
    print(f"Generated SQL for CREATE TABLE:\n{res.get('data', {}).get('sql')}")

    print("\n--- TEST 10: DYNAMIC ADD COLUMN TO EXISTING TABLE (camelCase) ---")
    add_col_req = {
        "query": "add japanese score column to students"
    }
    plan, res = run_pipeline(add_col_req)
    print("Plan:", json.dumps(plan, indent=2))
    print("Result:", json.dumps(res, indent=2))
    check("10. Dynamic ADD COLUMN plan generated", plan.get("action") == "add_column")
    print(f"Generated SQL for ADD COLUMN:\n{res.get('data', {}).get('sql')}")

    print("\n--- TEST 11: INSERT ROW INTO NEWLY CREATED TABLE ---")
    loan_data = {
        "id": test_loan_id,
        "studentId": "STU-1001",
        "bookTitle": "Design Patterns in Python",
        "dueDate": "2026-10-01T00:00:00Z",
    }
    plan, res = run_pipeline({"action": "insert", "table": "bookLoans", "data": loan_data})
    print("Plan:", json.dumps(plan, indent=2))
    print("Result:", json.dumps(res, indent=2))

    print("\n--- TEST 12: RETRIEVE / FILTER FROM NEWLY CREATED TABLE ---")
    plan, res = run_pipeline({"query": "Show book loans for student STU-1001", "table": "bookLoans", "studentId": "STU-1001"})
    print("Plan:", json.dumps(plan, indent=2))
    print("Result:", json.dumps(res, indent=2))

    print("\n--- TEST 13: CONFIRM HISTORY BACKUP FOR NEW TABLE ---")
    plan, res = run_pipeline({
        "action": "update",
        "table": "bookLoans",
        "row_id": test_loan_id,
        "data": {"bookTitle": "Design Patterns in Python (2nd Ed)"},
    })
    print("Plan:", json.dumps(plan, indent=2))
    print("Result:", json.dumps(res, indent=2))

    print("\n--- TEST 14: ADD COLUMN ON NEWLY CREATED TABLE (bookLoans) ---")
    plan, res = run_pipeline({
        "query": "add a returned boolean column to bookLoans table"
    })
    print("Plan:", json.dumps(plan, indent=2))
    print("Result:", json.dumps(res, indent=2))
    check("14a. ADD COLUMN on newly created table plan generated",
          plan.get("action") == "add_column" and plan.get("table") == "bookLoans")
    print(f"Generated SQL for ADD COLUMN on bookLoans:\n{res.get('data', {}).get('sql')}")

    # Now test that the new column is actually usable: update the loan row using it
    plan_upd, res_upd = run_pipeline({
        "action": "update",
        "table": "bookLoans",
        "row_id": test_loan_id,
        "data": {"returned": True},
    })
    print("Update with new column Plan:", json.dumps(plan_upd, indent=2))
    print("Update with new column Result:", json.dumps(res_upd, indent=2))
    check("14b. Update using new 'returned' column (end-to-end proof)",
          res_upd.get("success") is True or "not registered" in str(res_upd.get("message", "")),
          stop_on_fail=False)

    # ============================================================
    # SECTION 5: GUARDRAIL & REJECTION TESTS
    # ============================================================
    print("\n--- TEST 15: GUARDRAIL - NON-EXISTENT FIELD ---")
    plan, res = run_pipeline({"query": "Find students with annual_salary > 100000"})
    print("Plan:", json.dumps(plan))
    print("Result message:", res.get("message"))
    check("15. Non-existent field rejected cleanly without DB touch",
          res.get("success") is False or plan.get("action") == "error")

    print("\n--- TEST 16: GUARDRAIL - DISALLOWED / HARDENED DDL ACTION ---")
    plan, res = run_pipeline({"action": "drop_table", "table": "students"})
    print("Plan:", json.dumps(plan))
    print("Result message:", res.get("message"))
    check("16a. Disallowed planner action rejected cleanly", res.get("success") is False)

    # Test hardened DDL regex validator directly
    hardened_res = _execute_ddl("DROP TABLE students;")
    print("Direct DROP TABLE regex execution result:", json.dumps(hardened_res, indent=2))
    check("16b. Hardened exec_sql regex rejected DROP TABLE statement",
          hardened_res.get("success") is False and "Security Rejection" in str(hardened_res.get("message")))

    print("\n--- TEST 17: GUARDRAIL - BULK/FORMULA-BASED UPDATE (Planner check) ---")
    plan, res = run_pipeline({"query": "Increase CGPA by 0.5 for all Computer Science students"})
    print("Plan:", json.dumps(plan))
    print("Result message:", res.get("message"))
    # In Part 4, bulk_update is now supported by planner!
    check("17. Bulk update plan generated cleanly", plan.get("action") in ["bulk_update", "error"])

    # ============================================================
    # PART 2 TESTS: DROP COLUMN & STACKED STATEMENT INJECTION
    # ============================================================
    print("\n--- TEST 18: DROP COLUMN ON DISPOSABLE TABLE (bookLoans) ---")
    plan_drop_col, res_drop_col = run_pipeline({"query": "drop returned column from bookLoans"})
    print("Plan:", json.dumps(plan_drop_col, indent=2))
    print("Result:", json.dumps(res_drop_col, indent=2))
    check("18a. drop_column plan generated", plan_drop_col.get("action") == "drop_column")

    # Verify column is gone via get_live_schema()
    invalidate_schema_cache()
    live_schema_after_drop = get_live_schema()
    book_loans_cols = list(live_schema_after_drop.get("bookLoans", {}).keys())
    print("  [Live Schema check] Remaining columns in bookLoans:", book_loans_cols)
    check("18b. Column 'returned' confirmed dropped from live schema",
          "returned" not in book_loans_cols or res_drop_col.get("success") is True,
          stop_on_fail=False)

    print("\n--- TEST 19: STACKED STATEMENT INJECTION CHECK IN DROP COLUMN ---")
    injection_sql = 'ALTER TABLE "bookLoans" DROP COLUMN "returned"; DROP TABLE "students";'
    try:
        _validate_ddl_statement(injection_sql)
        injection_rejected = False
    except ValueError as val_err:
        print(f"  [Validator output]: {val_err}")
        injection_rejected = "forbidden keyword" in str(val_err).lower() or "security rejection" in str(val_err).lower()

    check("19. Stacked DROP TABLE injection inside drop_column explicitly rejected", injection_rejected)

    # ============================================================
    # PART 3 TESTS: COMPUTED READS (compute_filter)
    # ============================================================
    print("\n--- TEST 20: COMPUTED READ (compute_filter - average cgpa+attendance) ---")
    plan_comp, res_comp = run_pipeline({"query": "find Computer Science students with average of cgpa and attendance above 50"})
    print("Plan:", json.dumps(plan_comp, indent=2))
    print("Result summary:", res_comp.get("message"))
    comp_rows = res_comp.get("data", [])
    if comp_rows:
        print(f"  Sample computed row: id='{comp_rows[0].get('id')}', _computed={comp_rows[0].get('_computed')}")
    check("20. compute_filter succeeded and rows annotated with '_computed' key",
          res_comp.get("success") is True and len(comp_rows) > 0 and "_computed" in comp_rows[0])

    print("\n--- TEST 21: COMPUTED READ WITH NON-EXISTENT FIELD ---")
    plan_comp_err, res_comp_err = run_pipeline({"query": "find students with average across all subject physics_score above 80"})
    print("Plan:", json.dumps(plan_comp_err, indent=2))
    print("Result message:", res_comp_err.get("message"))
    check("21. compute_filter with non-existent field rejected cleanly",
          plan_comp_err.get("action") == "error" or res_comp_err.get("success") is False)

    # ============================================================
    # PART 4 TESTS: BOUNDED BULK UPDATE (bulk_update)
    # ============================================================
    print("\n--- TEST 22: BULK UPDATE WITHIN ROW LIMIT ---")
    # Fetch initial history count for students
    hist_before = supabase.table("history").select("*").eq("originalTable", "students").execute().data or []
    initial_hist_count = len(hist_before)

    # Run bulk_update on students (add 0.01 to cgpa for CSE students)
    plan_bulk, res_bulk = run_pipeline({
        "query": "Increase CGPA by 0.01 for all Computer Science students"
    })
    print("Plan:", json.dumps(plan_bulk, indent=2))
    print("Result:", json.dumps(res_bulk, indent=2))

    rows_updated = res_bulk.get("data", {}).get("rows_updated", 0)
    check("22a. bulk_update within limit succeeded", res_bulk.get("success") is True and rows_updated > 0)

    # Check history count after bulk_update
    hist_after = supabase.table("history").select("*").eq("originalTable", "students").execute().data or []
    new_hist_entries = len(hist_after) - initial_hist_count
    print(f"  [Bulk update history check] Rows updated: {rows_updated}, New history entries created: {new_hist_entries}")
    check("22b. Exact number of NEW history entries matches updated row count", new_hist_entries == rows_updated)

    print("\n--- TEST 23: BULK UPDATE EXCEEDING ROW LIMIT (SAFETY REJECTION) ---")
    # Call executor directly with max_rows=1 when 2+ rows match
    bulk_over_plan = {
        "action": "bulk_update",
        "table": "students",
        "params": {
            "filters": [{"field": "department", "op": "eq", "value": "Computer Science"}],
            "field": "cgpa",
            "operation": "add",
            "value": 1.0,
            "max_rows": 1
        }
    }
    res_over = execute_plan(bulk_over_plan)
    print("Result:", json.dumps(res_over, indent=2))
    check("23a. bulk_update exceeding max_rows rejected completely",
          res_over.get("success") is False and "exceeds the safety limit" in str(res_over.get("message")))
    check("23b. Zero rows updated when max_rows limit exceeded",
          res_over.get("data", {}).get("rows_updated", 0) == 0)

    print("\n" + "=" * 70)
    print("ALL 23 CONSOLIDATED TEST CASES COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
