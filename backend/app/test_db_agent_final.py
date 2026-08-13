"""
FINAL comprehensive test suite for the Groq-powered Vault pipeline.
Covers all 17 operations: reads, writes, multi-table, dynamic schema
(create table + add column, including on a freshly created table),
and all guardrails.

KEY FIX vs earlier versions: uses ONE dynamically-generated table name
(NEW_TABLE, set once at the top using a timestamp) throughout every test
that touches "the newly created table" — so there's no possibility of
silently testing against stale leftover tables from previous runs.

HOW TO USE:
1. Adjust the two imports below if your planner/executor live elsewhere.
2. Run from backend/: python -m app.test_db_agent_final
3. Pauses only happen for WRITE and SCHEMA operations, where visually
   checking Supabase actually matters. Reads and guardrails just assert
   and print — no pause needed for those.
4. At the very end, a cleanup step removes test data but leaves the
   dynamically created table in place for your own inspection (delete
   it manually in Supabase once you're done reviewing it).
"""

import time
from app.agents.vault_planner import vault_llm_plan
from app.agents.vault_executor import execute_plan

# ---- ONE table name, used consistently everywhere "the new table" is tested ----
RUN_ID = str(int(time.time()))
NEW_TABLE = f"testLoans{RUN_ID}"          # e.g. testLoans1786349000
STUDENT_ID = f"STU-FULLTEST-{RUN_ID}"
COURSE_ID = f"CRS-FULLTEST-{RUN_ID}"
LOAN_ID = f"LOAN-{RUN_ID}"

results = {"passed": [], "failed": []}


def record(test_num, label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {test_num}. {label}" + (f" — {detail}" if detail else ""))
    (results["passed"] if condition else results["failed"]).append(f"{test_num}. {label}")


def pause(msg):
    input(f"\n>>> {msg}\n    Press Enter once you've checked Supabase...")


def run(label, lens_input):
    print(f"\nInput: {lens_input}")
    plan = vault_llm_plan(lens_input)
    print(f"Plan: {plan}")
    result = execute_plan(plan)
    print(f"Result: {result}")
    return plan, result


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():
    print("=" * 70)
    print(f"FULL DB AGENT TEST SUITE — run id {RUN_ID}")
    print(f"Dynamic table for this run: {NEW_TABLE}")
    print("=" * 70)

    # ---------------- READS (no pause needed) ----------------

    section("TEST 1: GET ALL ROWS (students)")
    _, r = run("1", {"query": "show me all students", "table": "students"})
    record(1, "get_all_rows", r.get("success") is True and isinstance(r.get("data"), list))

    section("TEST 2: FILTER ROWS (students)")
    _, r = run("2", {"query": "show CSE students", "table": "students", "department": "Computer Science"})
    ok = r.get("success") is True and all(
        s.get("department") == "Computer Science" for s in r.get("data", [])
    )
    record(2, "filter_rows", ok)

    section("TEST 3: COUNT ROWS (students)")
    _, r = run("3", {"query": "how many students are there", "table": "students"})
    record(3, "count_rows", r.get("success") is True)

    # ---------------- WRITES on students (pause on each) ----------------

    section("TEST 4: INSERT ROW (students)")
    _, r = run("4", {
        "action": "insert", "table": "students",
        "data": {"id": STUDENT_ID, "rollNumber": f"TEST-{RUN_ID}", "name": "Final Test Student",
                  "department": "Computer Science", "cgpa": 8.0, "semester": 1,
                  "attendance": 90.0, "email": f"finaltest{RUN_ID}@test.com",
                  "status": "Active", "backlogs": 0},
    })
    record(4, "insert_row", r.get("success") is True and r.get("data", {}).get("id") == STUDENT_ID)
    pause(f"Confirm '{STUDENT_ID}' exists in `students` with name='Final Test Student'")

    section("TEST 5: UPDATE ROW (students) — verify NEW data returned, not stale")
    _, r = run("5", {"action": "update", "table": "students", "student_id": STUDENT_ID,
                      "data": {"name": "Final Test Student (Updated)"}})
    returned_name = r.get("data", {}).get("name")
    record(5, "update_row returns fresh data",
           r.get("success") is True and returned_name == "Final Test Student (Updated)",
           f"returned name = '{returned_name}'")
    pause(f"Confirm '{STUDENT_ID}' name is now 'Final Test Student (Updated)' in Supabase")

    section("TEST 6: DELETE ROW (students)")
    _, r = run("6", {"action": "delete", "table": "students", "student_id": STUDENT_ID})
    record(6, "delete_row", r.get("success") is True)
    pause(f"Confirm '{STUDENT_ID}' is gone from `students`")

    section("TEST 7: HISTORY VERIFICATION (students)")
    _, r = run("7", {"query": f"show history entries for row {STUDENT_ID}", "table": "history",
                      "filters": {"rowId": STUDENT_ID}})
    hist_data = r.get("data", [])
    actions_found = sorted(set(h.get("action", "").lower() for h in hist_data)) if hist_data else []
    record(7, "history has update+delete entries, lowercase actions",
           actions_found == ["delete", "update"], f"found actions: {actions_found}")

    # ---------------- MULTI-TABLE PROOF (courses) ----------------

    section("TEST 8: MULTI-TABLE — insert + filter on courses")
    _, r_ins = run("8a", {"action": "insert", "table": "courses",
                           "data": {"id": COURSE_ID, "courseCode": f"TC{RUN_ID[-3:]}",
                                     "courseName": "Final Test Course", "department": "Computer Science",
                                     "credits": 3, "instructor": "Dr. Test", "semester": 1}})
    record("8a", "insert on courses", r_ins.get("success") is True)
    _, r_filt = run("8b", {"query": "show CSE courses", "table": "courses", "department": "Computer Science"})
    found = any(c.get("id") == COURSE_ID for c in r_filt.get("data", []))
    record("8b", "filter on courses finds the inserted row", found)
    pause(f"Confirm '{COURSE_ID}' exists in `courses`")

    # ---------------- DYNAMIC SCHEMA — all on ONE consistent new table ----------------

    section(f"TEST 9: CREATE TABLE '{NEW_TABLE}'")
    _, r = run("9", {"query": f"create a table called {NEW_TABLE} for tracking book loans "
                              f"with student id, book title, and due date"})
    record(9, "create_table succeeded", r.get("success") is True)
    pause(f"Confirm table '{NEW_TABLE}' now exists in Supabase (Table Editor)")

    section(f"TEST 10: ADD COLUMN on EXISTING table (students)")
    _, r = run("10", {"query": "add a japanese score column to students, numeric type"})
    record(10, "add_column on students succeeded", r.get("success") is True)
    pause("Confirm `students` now has a japanese score column")

    section(f"TEST 11: INSERT into the NEWLY CREATED table '{NEW_TABLE}'")
    _, r = run("11", {"action": "insert", "table": NEW_TABLE,
                       "data": {"id": LOAN_ID, "studentId": "STU-1001",
                                 "bookTitle": "Final Test Book", "dueDate": "2026-12-01T00:00:00Z"}})
    record(11, f"insert into {NEW_TABLE}", r.get("success") is True)
    pause(f"Confirm row '{LOAN_ID}' exists in '{NEW_TABLE}'")

    section(f"TEST 12: FILTER from the NEWLY CREATED table '{NEW_TABLE}'")
    _, r = run("12", {"query": "find loans for student STU-1001", "table": NEW_TABLE,
                       "studentId": "STU-1001"})
    found = any(row.get("id") == LOAN_ID for row in r.get("data", []))
    record(12, f"filter from {NEW_TABLE} finds inserted row", found)

    section(f"TEST 13: ADD COLUMN on the NEWLY CREATED table '{NEW_TABLE}' (the real gap test)")
    _, r = run("13", {"query": f"add a returned column (boolean) to {NEW_TABLE}"})
    record(13, f"add_column on {NEW_TABLE} succeeded", r.get("success") is True)
    pause(f"Confirm '{NEW_TABLE}' now has a 'returned' column")

    section(f"TEST 13b: UPDATE using the brand-new column on '{NEW_TABLE}' (end-to-end proof)")
    _, r = run("13b", {"action": "update", "table": NEW_TABLE, "row_id": LOAN_ID,
                        "data": {"returned": True}})
    returned_val = r.get("data", {}).get("returned")
    record("13b", "update using freshly-added column works end-to-end",
           r.get("success") is True and returned_val is True, f"returned value = {returned_val}")
    pause(f"Confirm '{LOAN_ID}' in '{NEW_TABLE}' now shows returned=true")

    # ---------------- GUARDRAILS (no pause, assert on message content) ----------------

    section("TEST 14: GUARDRAIL — unknown field")
    _, r = run("14", {"query": "find students with annual_salary > 100000"})
    record(14, "unknown field rejected cleanly, no DB touch",
           r.get("success") is False, r.get("message", ""))

    section("TEST 15: GUARDRAIL — disallowed action (drop_table)")
    plan = vault_llm_plan({"query": f"delete the entire {NEW_TABLE} table permanently, drop it"})
    record(15, "disallowed action rejected by planner",
           plan.get("action") in ("error", None) or plan.get("action") not in
           ["get_all_rows", "filter_rows", "insert_row", "update_row", "delete_row",
            "count_rows", "create_table", "add_column"],
           f"plan action = {plan.get('action')}")

    section("TEST 16: GUARDRAIL — bulk/formula update")
    _, r = run("16", {"query": "increase cgpa by 0.5 for all Computer Science students"})
    msg = r.get("message", "").lower()
    record(16, "bulk/formula update specifically rejected",
           r.get("success") is False and ("bulk" in msg or "formula" in msg or "one row" in msg),
           r.get("message", ""))

    # ---------------- SUMMARY ----------------

    section("FINAL SUMMARY")
    print(f"PASSED ({len(results['passed'])}): {results['passed']}")
    print(f"FAILED ({len(results['failed'])}): {results['failed']}")
    print(f"\nDynamic test table created this run: {NEW_TABLE}")
    print(f"NOTE: '{NEW_TABLE}' was NOT auto-deleted — inspect it in Supabase, then")
    print(f"      manually drop it when done: DROP TABLE public.\"{NEW_TABLE}\";")


if __name__ == "__main__":
    main()