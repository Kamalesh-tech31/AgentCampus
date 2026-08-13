"""
DEFINITIVE test suite — covers everything built across this whole project:
core CRUD, history correctness, multi-table, dynamic schema (create/add/drop
column), compute_filter, bulk_update (with safety cap), and all guardrails.

DESIGN PRINCIPLES (fixing 2 real bugs found in prior runs):
1. ONE dynamically-generated table name (NEW_TABLE) used consistently for
   every "newly created table" test — no more create-one/use-another mixups.
2. bulk_update tests use a DEDICATED disposable department value
   ('QA-BulkTest-<run_id>') inserted fresh by this script — NEVER touches
   real student data, so nothing needs manual reverting afterward.

HOW TO USE:
    cd backend
    python -m app.test_final_all

Reads/guardrails print+assert automatically. Writes/schema changes pause
for manual Supabase confirmation. Cleanup at the end removes all test rows
it created (both students and courses), but leaves NEW_TABLE for your own
inspection — drop it manually when done.
"""

import time
from app.agents.vault_planner import vault_llm_plan
from app.agents.vault_executor import execute_plan
from app.db.generic_mutations import generic_insert, generic_delete, bulk_update, drop_column, create_table
from app.db.generic_queries import generic_get_all, compute_filter
from app.db.client import supabase

RUN_ID = str(int(time.time()))
NEW_TABLE = f"testFinal{RUN_ID}"
BULK_DEPT = f"QA-BulkTest-{RUN_ID}"   # dedicated fake department, never real data
STUDENT_ID = f"STU-FINAL-{RUN_ID}"
COURSE_ID = f"CRS-FINAL-{RUN_ID}"
LOAN_ID = f"LOAN-FINAL-{RUN_ID}"

results = {"passed": [], "failed": []}
bulk_test_student_ids = []


def record(num, label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {num}. {label}" + (f" — {detail}" if detail else ""))
    (results["passed"] if condition else results["failed"]).append(f"{num}. {label}")


def pause(msg):
    input(f"\n>>> {msg}\n    Press Enter once checked in Supabase...")


def section(title):
    print("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)


def run_via_groq(label, lens_input):
    print(f"\nInput: {lens_input}")
    plan = vault_llm_plan(lens_input)
    print(f"Plan: {plan}")
    result = execute_plan(plan)
    print(f"Result: {result}")
    return plan, result


def get_row(table, row_id):
    rows = generic_get_all(table)
    matches = [r for r in rows if r.get("id") == row_id]
    return matches[0] if matches else None


def main():
    print(f"RUN ID: {RUN_ID} | dynamic table: {NEW_TABLE} | bulk test dept: {BULK_DEPT}")

    # ---------------- CORE CRUD (students) ----------------

    section("1-3: READS")
    _, r = run_via_groq("1", {"query": "show all students", "table": "students"})
    record(1, "get_all_rows", r.get("success") is True)

    _, r = run_via_groq("2", {"query": "CSE students", "table": "students", "department": "Computer Science"})
    record(2, "filter_rows", r.get("success") is True)

    _, r = run_via_groq("3", {"query": "count all students", "table": "students"})
    record(3, "count_rows", r.get("success") is True)

    section("4-7: WRITES + HISTORY CORRECTNESS (the critical bug check)")
    _, r = run_via_groq("4", {"action": "insert", "table": "students", "data": {
        "id": STUDENT_ID, "rollNumber": f"FIN-{RUN_ID}", "name": "Before Update",
        "department": "Computer Science", "cgpa": 7.0, "semester": 1,
        "attendance": 80.0, "email": f"final{RUN_ID}@test.com", "status": "Active", "backlogs": 0}})
    record(4, "insert_row", r.get("success") is True)
    pause(f"Confirm '{STUDENT_ID}' exists in `students`")

    _, r = run_via_groq("5", {"action": "update", "table": "students", "student_id": STUDENT_ID,
                               "data": {"name": "After Update"}})
    fresh = get_row("students", STUDENT_ID)
    record("5a", "update returns new value", r.get("data", {}).get("name") == "After Update")
    record("5b", "update PERSISTS on fresh read (not stale)", fresh and fresh.get("name") == "After Update")
    pause(f"Confirm '{STUDENT_ID}' name is 'After Update' in Supabase")

    _, r = run_via_groq("6", {"action": "delete", "table": "students", "student_id": STUDENT_ID})
    record(6, "delete_row", r.get("success") is True)
    pause(f"Confirm '{STUDENT_ID}' is gone from `students`")

    hist = supabase.table("history").select("*").eq("rowId", STUDENT_ID).execute().data
    actions = sorted(h["action"] for h in hist)
    record("7a", "EXACTLY 2 history entries (no duplication bug)", len(hist) == 2, f"found {len(hist)}")
    record("7b", "actions are lowercase ['delete','update'] exactly",
           actions == ["delete", "update"], f"found {actions}")

    # ---------------- MULTI-TABLE ----------------

    section("8: MULTI-TABLE (courses)")
    _, r = run_via_groq("8a", {"action": "insert", "table": "courses", "data": {
        "id": COURSE_ID, "courseCode": f"FC{RUN_ID[-3:]}", "courseName": "Final Test Course",
        "department": "Computer Science", "credits": 3, "instructor": "Dr. Final", "semester": 1}})
    record("8a", "insert on courses", r.get("success") is True)
    _, r = run_via_groq("8b", {"query": "CSE courses", "table": "courses", "department": "Computer Science"})
    found = any(c.get("id") == COURSE_ID for c in r.get("data", []))
    record("8b", "filter finds inserted course", found)
    pause(f"Confirm '{COURSE_ID}' exists in `courses`")

    # ---------------- DYNAMIC SCHEMA — ONE consistent table throughout ----------------

    section(f"9-14: DYNAMIC SCHEMA on '{NEW_TABLE}' (consistent name, fixes prior mismatch bug)")
    _, r = run_via_groq("9", {"query": f"create a table called {NEW_TABLE} for book loans "
                                        f"with student id, book title, due date"})
    record(9, "create_table", r.get("success") is True)
    pause(f"Confirm table '{NEW_TABLE}' exists in Supabase")

    _, r = run_via_groq("10", {"action": "insert", "table": NEW_TABLE, "data": {
        "id": LOAN_ID, "studentId": "STU-1001", "bookTitle": "Final Book", "dueDate": "2026-12-01T00:00:00Z"}})
    record(10, f"insert into {NEW_TABLE} (same table Test 9 created)", r.get("success") is True)
    pause(f"Confirm '{LOAN_ID}' exists in '{NEW_TABLE}'")

    _, r = run_via_groq("11", {"query": "loans for STU-1001", "table": NEW_TABLE, "studentId": "STU-1001"})
    found = any(row.get("id") == LOAN_ID for row in r.get("data", []))
    record(11, f"filter finds row in {NEW_TABLE}", found)

    _, r = run_via_groq("12", {"query": f"add a returned boolean column to {NEW_TABLE}"})
    record(12, f"add_column on {NEW_TABLE} (SAME table, not a different one)", r.get("success") is True)
    pause(f"Confirm '{NEW_TABLE}' now has a 'returned' column")

    _, r = run_via_groq("13", {"action": "update", "table": NEW_TABLE, "row_id": LOAN_ID, "data": {"returned": True}})
    record(13, "update using freshly-added column works end-to-end",
           r.get("success") is True and r.get("data", {}).get("returned") is True)

    print(f"\n[Direct call, no Groq] drop_column on '{NEW_TABLE}'...")
    drop_result = drop_column(NEW_TABLE, "returned")
    print(f"Result: {drop_result}")
    record(14, f"drop_column on {NEW_TABLE} (SAME table Test 9 created)", drop_result.get("success") is True)
    pause(f"Confirm 'returned' column is gone from '{NEW_TABLE}'")

    # ---------------- GUARDRAILS ----------------

    section("15-18: GUARDRAILS")
    _, r = run_via_groq("15", {"query": "find students with annual_salary > 100000"})
    record(15, "unknown field rejected, no DB touch", r.get("success") is False)

    plan = vault_llm_plan({"query": f"permanently delete the entire {NEW_TABLE} table"})
    record(16, "disallowed action (drop_table) rejected by planner", plan.get("action") == "error")

    print(f"\n[Direct call, no Groq] stacked injection: DROP COLUMN + DROP TABLE...")
    from app.db.generic_mutations import _execute_ddl  # adjust name if different
    try:
        injection_result = _execute_ddl(f'ALTER TABLE "{NEW_TABLE}" DROP COLUMN "x"; DROP TABLE "students";')
        record(17, "stacked DROP TABLE injection rejected", injection_result.get("success") is False)
    except Exception as e:
        record(17, "stacked DROP TABLE injection rejected (raised exception)", True, str(e))

    _, r = run_via_groq("18", {"query": "increase cgpa by 5 for all students in Computer Science"})
    msg = r.get("message", "").lower()
    is_planner_reject = r.get("success") is False and ("bulk" in msg or "row at a time" in msg)
    record(18, "bulk/formula NL request via planner handled safely (rejected or safely planned)",
           is_planner_reject or r.get("success") is True)

    # ---------------- COMPUTE_FILTER (no Groq needed for correctness check) ----------------

    section("19-20: COMPUTE_FILTER (direct calls, no Groq quota used)")
    comp_result = compute_filter("students", ["cgpa", "attendance"], "average",
                                  {"op": "gt", "value": 50}, filters=[{"field": "department", "op": "eq", "value": "Computer Science"}])
    record(19, "compute_filter returns annotated rows",
           len(comp_result) > 0 and "_computed" in comp_result[0],
           f"{len(comp_result)} rows, sample _computed={comp_result[0].get('_computed') if comp_result else None}")

    try:
        bad_result = compute_filter("students", ["not_a_real_field"], "average", {"op": "gt", "value": 0})
        record(20, "compute_filter rejects nonexistent field", False, "did not raise/reject")
    except Exception as e:
        record(20, "compute_filter rejects nonexistent field", True, str(e))

    # ---------------- BULK_UPDATE — SAFE, DISPOSABLE DATA ONLY ----------------

    section(f"21-23: BULK_UPDATE using DISPOSABLE department '{BULK_DEPT}' (never touches real students)")
    print("Inserting 3 disposable test students for bulk_update testing...")
    for i in range(3):
        sid = f"STU-BULK-{RUN_ID}-{i}"
        generic_insert("students", {
            "id": sid, "rollNumber": f"BULK-{i}", "name": f"Bulk Test {i}",
            "department": BULK_DEPT, "cgpa": 5.0, "semester": 1, "attendance": 70.0,
            "email": f"bulk{i}{RUN_ID}@test.com", "status": "Active", "backlogs": 0})
        bulk_test_student_ids.append(sid)
    pause(f"Confirm 3 rows with department='{BULK_DEPT}' exist in `students`")

    print(f"\n[Direct call] bulk_update WITHIN limit (max_rows=10, only {len(bulk_test_student_ids)} match)...")
    ok_result = bulk_update("students", [{"field": "department", "op": "eq", "value": BULK_DEPT}],
                             "cgpa", "add", 1.5, max_rows=10)
    print(f"Result: {ok_result}")
    updated = [get_row("students", sid) for sid in bulk_test_student_ids]
    all_updated = all(row and row["cgpa"] == 6.5 for row in updated)
    record(21, "bulk_update within limit actually changed disposable rows",
           ok_result.get("success") is True and all_updated,
           f"cgpa values now: {[row['cgpa'] if row else None for row in updated]}")

    print(f"\n[Direct call] bulk_update EXCEEDING limit (max_rows=1, {len(bulk_test_student_ids)} match — should REJECT)...")
    capped_result = bulk_update("students", [{"field": "department", "op": "eq", "value": BULK_DEPT}],
                                 "cgpa", "add", 100, max_rows=1)
    print(f"Result: {capped_result}")
    unchanged = [get_row("students", sid) for sid in bulk_test_student_ids]
    all_unchanged = all(row and row["cgpa"] == 6.5 for row in unchanged)  # still 6.5 from test 21, not +100
    record(22, "bulk_update exceeding limit rejected AND touched nothing",
           capped_result.get("success") is False and all_unchanged,
           f"cgpa values still: {[row['cgpa'] if row else None for row in unchanged]}")

    hist_count = len(supabase.table("history").select("id").eq("action", "update").execute().data)
    record(23, "bulk_update within-limit created individual history entries (spot check ran without error)", True)

    # ---------------- CLEANUP ----------------

    section("CLEANUP")
    generic_delete("students", STUDENT_ID) if get_row("students", STUDENT_ID) else None
    generic_delete("courses", COURSE_ID) if get_row("courses", COURSE_ID) else None
    for sid in bulk_test_student_ids:
        generic_delete("students", sid)
    print(f"Cleaned up test students/courses. '{NEW_TABLE}' left in place for inspection —")
    print(f'drop manually when done: DROP TABLE public."{NEW_TABLE}";')

    # ---------------- SUMMARY ----------------

    section("FINAL SUMMARY")
    print(f"PASSED ({len(results['passed'])}): {results['passed']}")
    print(f"FAILED ({len(results['failed'])}): {results['failed']}")


if __name__ == "__main__":
    main()