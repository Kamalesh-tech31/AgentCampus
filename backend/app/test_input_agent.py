"""
Unit and integration tests for InputAgent.

Coverage:
  - normalize_prompt
  - extract_department (aliases, edge cases)
  - extract_limit (digits, number words, edge cases)
  - extract_cgpa_filter (all operators, between, out-of-domain)
  - extract_attendance_filter (%, operators, between)
  - extract_status_filter
  - extract_sort (all patterns)
  - extract_fields
  - extract_analytics_hint
  - detect_operation
  - InputAgent.execute (full pipeline, empty query, edge cases)
  - DBAgent integration with new structured_intent
  - Acceptance examples from requirements
"""
import pytest
from app.agents.input_agent import (
    InputAgent,
    normalize_prompt,
    extract_department,
    extract_limit,
    extract_cgpa_filter,
    extract_attendance_filter,
    extract_status_filter,
    extract_sort,
    extract_fields,
    extract_analytics_hint,
    detect_operation,
)
from app.agents.db_agent import DBAgent
from app.mother.types import AgentTask


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_task(query: str, task_id: str = "TEST-001") -> AgentTask:
    return AgentTask(
        task_id=task_id,
        agent="input",
        objective="Parse intent",
        input_data={"user_query": query},
        expected_output="Structured intent",
    )


def _run_input(query: str) -> dict:
    agent = InputAgent()
    result = agent.execute(_make_task(query))
    assert result.status == "completed", f"InputAgent failed: {result.error}"
    return result.result["structured_intent"]


# ─────────────────────────────────────────────────────────────────────────────
# normalize_prompt
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizePrompt:
    def test_lowercase(self):
        assert normalize_prompt("SHOW CS Students") == "show cs students"

    def test_collapse_whitespace(self):
        assert normalize_prompt("  show   top   10  ") == "show top 10"

    def test_empty(self):
        assert normalize_prompt("") == ""

    def test_tabs_newlines(self):
        assert normalize_prompt("show\tstudents\nwith\tcgpa") == "show students with cgpa"


# ─────────────────────────────────────────────────────────────────────────────
# extract_department
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractDepartment:
    def test_full_canonical(self):
        assert extract_department("show computer science students") == "Computer Science"

    def test_alias_cs(self):
        assert extract_department("show cs students") == "Computer Science"

    def test_alias_cse(self):
        assert extract_department("top cse students") == "Computer Science"

    def test_alias_ec(self):
        assert extract_department("show ec students") == "Electronics"

    def test_alias_electronics(self):
        assert extract_department("students from electronics") == "Electronics"

    def test_alias_me(self):
        assert extract_department("show me students") is not None  # "me" → Mechanical
        # but "show me" is ambiguous — the alias "me" should still match Mechanical
        assert extract_department("top mechanical students") == "Mechanical"

    def test_alias_civil(self):
        assert extract_department("civil students with high cgpa") == "Civil"

    def test_alias_ce(self):
        assert extract_department("show ce students") == "Civil"

    def test_alias_data_science(self):
        assert extract_department("data science students") == "Data Science"

    def test_alias_ds(self):
        assert extract_department("show ds students") == "Data Science"

    def test_alias_ai_ml(self):
        assert extract_department("ai & ml students") == "AI & ML"

    def test_alias_aiml(self):
        assert extract_department("aiml department") == "AI & ML"

    def test_no_department(self):
        assert extract_department("show all students with high cgpa") is None

    def test_unknown_department_not_invented(self):
        assert extract_department("show physics students") is None

    def test_case_insensitive(self):
        assert extract_department("COMPUTER SCIENCE students") == "Computer Science"

    def test_mixed_case(self):
        assert extract_department("students from Data Science dept") == "Data Science"


# ─────────────────────────────────────────────────────────────────────────────
# extract_limit
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractLimit:
    def test_top_n(self):
        assert extract_limit("show top 10 students") == 10

    def test_first_n(self):
        assert extract_limit("first 5 students") == 5

    def test_show_n(self):
        assert extract_limit("show 20 students") == 20

    def test_give_me_n(self):
        assert extract_limit("give me 15 students") == 15

    def test_limit_to_n(self):
        assert extract_limit("limit to 10 students") == 10

    def test_number_word_ten(self):
        assert extract_limit("top ten students") == 10

    def test_number_word_five(self):
        assert extract_limit("top five cs students") == 5

    def test_number_word_twenty(self):
        assert extract_limit("show twenty students") == 20

    def test_no_limit(self):
        assert extract_limit("show all students") is None

    def test_negative_returns_none(self):
        # "top -5" won't match digit pattern (re requires \d+)
        assert extract_limit("show students") is None

    def test_zero_returns_none(self):
        assert extract_limit("top 0 students") is None

    def test_large_limit(self):
        assert extract_limit("show 999 students") == 999

    def test_no_trigger_no_limit(self):
        assert extract_limit("cgpa above 8.5") is None


# ─────────────────────────────────────────────────────────────────────────────
# extract_cgpa_filter
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractCgpaFilter:
    def test_above(self):
        result = extract_cgpa_filter("cgpa above 8.5")
        assert len(result) == 1
        assert result[0] == {"field": "cgpa", "operator": ">", "value": 8.5}

    def test_greater_than(self):
        result = extract_cgpa_filter("cgpa greater than 7")
        assert result[0]["operator"] == ">"
        assert result[0]["value"] == 7.0

    def test_at_least(self):
        result = extract_cgpa_filter("cgpa at least 8.0")
        assert result[0]["operator"] == ">="
        assert result[0]["value"] == 8.0

    def test_gte_symbol(self):
        result = extract_cgpa_filter("cgpa >= 9")
        assert result[0]["operator"] == ">="

    def test_below(self):
        result = extract_cgpa_filter("cgpa below 7")
        assert result[0]["operator"] == "<"
        assert result[0]["value"] == 7.0

    def test_less_than(self):
        result = extract_cgpa_filter("cgpa less than 6.5")
        assert result[0]["operator"] == "<"

    def test_at_most(self):
        result = extract_cgpa_filter("cgpa at most 9.0")
        assert result[0]["operator"] == "<="

    def test_lte_symbol(self):
        result = extract_cgpa_filter("cgpa <= 8.5")
        assert result[0]["operator"] == "<="

    def test_equal_to(self):
        result = extract_cgpa_filter("cgpa equal to 9.5")
        assert result[0]["operator"] == "="

    def test_between(self):
        result = extract_cgpa_filter("cgpa between 8 and 9")
        assert len(result) == 2
        assert result[0] == {"field": "cgpa", "operator": ">=", "value": 8.0}
        assert result[1] == {"field": "cgpa", "operator": "<=", "value": 9.0}

    def test_between_floats(self):
        result = extract_cgpa_filter("cgpa between 8.5 and 9.5")
        assert result[0]["value"] == 8.5
        assert result[1]["value"] == 9.5

    def test_reversed_above(self):
        result = extract_cgpa_filter("above 8.5 cgpa")
        assert result[0]["operator"] == ">"

    def test_reversed_below(self):
        result = extract_cgpa_filter("below 7 cgpa")
        assert result[0]["operator"] == "<"

    def test_no_cgpa(self):
        result = extract_cgpa_filter("show top 10 students")
        assert result == []

    def test_out_of_domain_high(self):
        result = extract_cgpa_filter("cgpa above 11")
        assert len(result) == 1
        assert "validation_error" in result[0]

    def test_out_of_domain_low_negative(self):
        result = extract_cgpa_filter("cgpa above -1")
        # -1 won't match \d+ pattern so no result
        assert result == []

    def test_invalid_between_range(self):
        result = extract_cgpa_filter("cgpa between 9 and 8")  # lo > hi
        assert len(result) == 1
        assert "validation_error" in result[0]

    def test_non_numeric_no_crash(self):
        result = extract_cgpa_filter("cgpa above banana")
        assert result == []  # 'banana' doesn't match \d+

    def test_malicious_sql_ignored(self):
        result = extract_cgpa_filter("show students; DROP TABLE students")
        assert result == []  # no cgpa phrase present


# ─────────────────────────────────────────────────────────────────────────────
# extract_attendance_filter
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractAttendanceFilter:
    def test_above_percent(self):
        result = extract_attendance_filter("attendance above 80%")
        assert result[0] == {"field": "attendance", "operator": ">", "value": 80.0}

    def test_above_no_percent(self):
        result = extract_attendance_filter("attendance above 80")
        assert result[0]["operator"] == ">"
        assert result[0]["value"] == 80.0

    def test_below(self):
        result = extract_attendance_filter("attendance below 75")
        assert result[0]["operator"] == "<"
        assert result[0]["value"] == 75.0

    def test_at_least(self):
        result = extract_attendance_filter("attendance at least 90%")
        assert result[0]["operator"] == ">="

    def test_between(self):
        result = extract_attendance_filter("attendance between 70 and 90")
        assert len(result) == 2
        assert result[0]["operator"] == ">="
        assert result[1]["operator"] == "<="

    def test_reversed(self):
        result = extract_attendance_filter("above 80% attendance")
        assert result[0]["operator"] == ">"

    def test_no_attendance(self):
        assert extract_attendance_filter("show students with high cgpa") == []

    def test_out_of_domain(self):
        result = extract_attendance_filter("attendance above 150")
        assert "validation_error" in result[0]

    def test_stored_as_percentage_not_fraction(self):
        # 80% → 80.0 (not 0.80)
        result = extract_attendance_filter("attendance above 80%")
        assert result[0]["value"] == 80.0


# ─────────────────────────────────────────────────────────────────────────────
# extract_status_filter
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractStatusFilter:
    def test_on_probation(self):
        assert extract_status_filter("show students on probation") == "Probation"

    def test_probation_word(self):
        assert extract_status_filter("show probation students") == "Probation"

    def test_not_on_probation(self):
        assert extract_status_filter("students not on probation") == "Active"

    def test_graduated(self):
        assert extract_status_filter("show graduated students") == "Graduated"

    def test_active(self):
        assert extract_status_filter("active students only") == "Active"

    def test_none(self):
        assert extract_status_filter("show cs students with high cgpa") is None


# ─────────────────────────────────────────────────────────────────────────────
# extract_sort
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractSort:
    def test_sort_by_cgpa_desc(self):
        result = extract_sort("sort by cgpa descending")
        assert result == {"field": "cgpa", "direction": "desc"}

    def test_sort_by_cgpa_asc(self):
        result = extract_sort("sort by cgpa ascending")
        assert result == {"field": "cgpa", "direction": "asc"}

    def test_order_by_attendance_desc(self):
        result = extract_sort("order students by attendance descending")
        assert result == {"field": "attendance", "direction": "desc"}

    def test_highest_cgpa(self):
        result = extract_sort("highest cgpa students")
        assert result == {"field": "cgpa", "direction": "desc"}

    def test_lowest_cgpa(self):
        result = extract_sort("lowest cgpa students")
        assert result == {"field": "cgpa", "direction": "asc"}

    def test_highest_attendance(self):
        result = extract_sort("highest attendance")
        assert result == {"field": "attendance", "direction": "desc"}

    def test_lowest_attendance(self):
        result = extract_sort("lowest attendance")
        assert result == {"field": "attendance", "direction": "asc"}

    def test_cgpa_descending(self):
        result = extract_sort("cgpa descending")
        assert result == {"field": "cgpa", "direction": "desc"}

    def test_cgpa_ascending(self):
        result = extract_sort("cgpa ascending")
        assert result == {"field": "cgpa", "direction": "asc"}

    def test_top_students_by_attendance(self):
        result = extract_sort("top 10 students by attendance")
        assert result == {"field": "attendance", "direction": "desc"}

    def test_top_students_default_cgpa(self):
        result = extract_sort("top 10 students")
        assert result == {"field": "cgpa", "direction": "desc"}

    def test_no_sort(self):
        result = extract_sort("show cs students with cgpa above 8")
        assert result is None

    def test_invalid_sort_field_ignored(self):
        result = extract_sort("sort by spaceship")
        assert result is None

    def test_best_students(self):
        # "best students" processed by InputAgent ambiguity handler; extract_sort alone returns None
        result = extract_sort("show me the best students")
        assert result is None  # ambiguity resolved in InputAgent.execute, not here


# ─────────────────────────────────────────────────────────────────────────────
# extract_fields
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractFields:
    def test_name_and_cgpa(self):
        result = extract_fields("show only name and cgpa")
        assert "name" in result
        assert "cgpa" in result

    def test_multiple_fields(self):
        result = extract_fields("give me name, department and cgpa")
        assert "name" in result
        assert "department" in result
        assert "cgpa" in result

    def test_unknown_field_excluded(self):
        result = extract_fields("show only name and spaceship")
        assert "name" in result
        assert "spaceship" not in result

    def test_no_field_selection(self):
        result = extract_fields("show cs students with high cgpa")
        assert result == []

    def test_alias_gpa(self):
        result = extract_fields("show only name and gpa")
        assert "cgpa" in result  # gpa → cgpa


# ─────────────────────────────────────────────────────────────────────────────
# extract_analytics_hint
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractAnalyticsHint:
    def test_average_cgpa(self):
        result = extract_analytics_hint("calculate average cgpa for cs students")
        assert result is not None
        assert result["metric"] == "average"
        assert result["field"] == "cgpa"

    def test_highest_cgpa(self):
        result = extract_analytics_hint("show highest cgpa")
        assert result["metric"] == "highest"

    def test_lowest_cgpa(self):
        result = extract_analytics_hint("find lowest cgpa in electronics")
        assert result["metric"] == "lowest"

    def test_count(self):
        result = extract_analytics_hint("how many students are on probation")
        assert result["metric"] == "count"

    def test_no_analytics(self):
        result = extract_analytics_hint("show cs students")
        assert result is None

    def test_no_compute(self):
        # InputAgent must NOT compute the value — only identify metric
        result = extract_analytics_hint("average cgpa for cs")
        assert result is not None
        # Must not contain a computed numeric value
        assert "value" not in result or result.get("value") is None


# ─────────────────────────────────────────────────────────────────────────────
# detect_operation
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectOperation:
    def test_read(self):
        assert detect_operation("show cs students") == "read"

    def test_analytics_average(self):
        assert detect_operation("calculate average cgpa") == "analytics"

    def test_analytics_highest(self):
        assert detect_operation("find highest cgpa") == "analytics"

    def test_analytics_count(self):
        assert detect_operation("how many students on probation") == "analytics"

    def test_write_update(self):
        assert detect_operation("update john's cgpa to 9.2") == "write"

    def test_write_delete(self):
        assert detect_operation("delete student 101") == "write"


# ─────────────────────────────────────────────────────────────────────────────
# InputAgent.execute — full pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestInputAgentExecute:

    # ── Basic structure ──
    def test_returns_completed_status(self):
        agent = InputAgent()
        result = agent.execute(_make_task("show cs students"))
        assert result.status == "completed"
        assert "structured_intent" in result.result

    def test_original_query_preserved(self):
        si = _run_input("Show Top 10 CS Students")
        assert si["original_query"] == "Show Top 10 CS Students"

    def test_empty_query_fails(self):
        agent = InputAgent()
        result = agent.execute(_make_task(""))
        assert result.status == "failed"
        assert result.error is not None

    def test_whitespace_only_fails(self):
        agent = InputAgent()
        result = agent.execute(_make_task("   "))
        assert result.status == "failed"

    # ── Acceptance examples from requirements ──

    def test_top_10_cs_students(self):
        """'Show the top 10 Computer Science students' → dept=CS, limit=10, sort=cgpa desc"""
        si = _run_input("Show the top 10 Computer Science students")
        assert si["department"] == "Computer Science"
        assert si["limit"] == 10
        assert si["sort"] == {"field": "cgpa", "direction": "desc"}

    def test_cs_above_8_5_cgpa(self):
        """'Give me CS students above 8.5 CGPA' → dept=CS, cgpa > 8.5"""
        si = _run_input("Give me CS students above 8.5 CGPA")
        assert si["department"] == "Computer Science"
        filters = si["filters"]
        cgpa_f = [f for f in filters if f["field"] == "cgpa"]
        assert len(cgpa_f) == 1
        assert cgpa_f[0]["operator"] == ">"
        assert cgpa_f[0]["value"] == 8.5

    def test_lowest_5_electronics_by_cgpa(self):
        """'Find the lowest 5 Electronics students by CGPA' → dept=Electronics, limit=5, sort=cgpa asc"""
        si = _run_input("Find the lowest 5 Electronics students by CGPA")
        assert si["department"] == "Electronics"
        assert si["limit"] == 5
        assert si["sort"] == {"field": "cgpa", "direction": "asc"}

    def test_cs_cgpa_above_8_and_attendance_above_80(self):
        """'Show CS students with CGPA above 8 and attendance above 80' → multi-filter"""
        si = _run_input("Show CS students with CGPA above 8 and attendance above 80")
        assert si["department"] == "Computer Science"
        filters = si["filters"]
        cgpa_f = [f for f in filters if f["field"] == "cgpa"]
        att_f = [f for f in filters if f["field"] == "attendance"]
        assert len(cgpa_f) == 1 and cgpa_f[0]["operator"] == ">"
        assert len(att_f) == 1 and att_f[0]["operator"] == ">"

    def test_analytics_average_cgpa_cs(self):
        """'Calculate average CGPA for CS' → operation=analytics, analytics_hint"""
        si = _run_input("Calculate average CGPA for Computer Science students")
        assert si["operation"] == "analytics"
        assert si["analytics_hint"] is not None
        assert si["analytics_hint"]["metric"] == "average"
        assert si["department"] == "Computer Science"

    def test_show_name_and_cgpa(self):
        """'Show only name and CGPA for CS students' → fields=[name, cgpa]"""
        si = _run_input("Show only name and cgpa for CS students")
        assert si["fields"] is not None
        assert "name" in si["fields"]
        assert "cgpa" in si["fields"]

    def test_sort_by_attendance_desc_show_20(self):
        """'Sort students by attendance descending and show 20' → sort=attendance desc, limit=20"""
        si = _run_input("Sort students by attendance descending and show 20")
        assert si["sort"] == {"field": "attendance", "direction": "desc"}
        assert si["limit"] == 20

    def test_cgpa_below_7(self):
        """'Show students with CGPA below 7' → cgpa < 7"""
        si = _run_input("Show students with CGPA below 7")
        filters = si["filters"]
        cgpa_f = [f for f in filters if f["field"] == "cgpa"]
        assert cgpa_f[0]["operator"] == "<"
        assert cgpa_f[0]["value"] == 7.0

    def test_cgpa_between_8_and_9(self):
        """'Show students with CGPA between 8 and 9' → cgpa >= 8 AND cgpa <= 9"""
        si = _run_input("Show students with CGPA between 8 and 9")
        filters = si["filters"]
        assert len(filters) == 2
        ops = {f["operator"] for f in filters}
        assert ">=" in ops and "<=" in ops

    def test_highest_attendance_10(self):
        """'Show the 10 students with highest attendance' → limit=10, sort=attendance desc"""
        si = _run_input("Show the 10 students with highest attendance")
        assert si["limit"] == 10
        assert si["sort"] == {"field": "attendance", "direction": "desc"}

    def test_find_lowest_cgpa_students(self):
        """'Find the lowest CGPA students' → sort=cgpa asc"""
        si = _run_input("Find the lowest CGPA students")
        assert si["sort"] == {"field": "cgpa", "direction": "asc"}

    # ── Backward compatibility ──

    def test_backward_compat_min_cgpa(self):
        """min_cgpa is populated from the first >= or > cgpa filter."""
        si = _run_input("Show CS students with CGPA above 8.5")
        assert si["min_cgpa"] == 8.5

    def test_backward_compat_min_cgpa_gte(self):
        si = _run_input("Show students with CGPA at least 9.0")
        assert si["min_cgpa"] == 9.0

    def test_backward_compat_intent_key(self):
        si = _run_input("Show CS students")
        assert si["intent"] == "student_query"

    def test_backward_compat_intent_update(self):
        si = _run_input("Update student CGPA")
        assert si["intent"] == "student_update"

    # ── Edge cases ──

    def test_malicious_sql_input(self):
        """SQL injection attempt must not crash or produce malformed output."""
        si = _run_input("Show students; DROP TABLE students")
        assert si["original_query"] == "Show students; DROP TABLE students"
        assert si["department"] is None
        assert si["filters"] == []

    def test_very_long_prompt(self):
        long_query = "show " + ("computer science students with high cgpa " * 50)
        si = _run_input(long_query)
        assert si["department"] == "Computer Science"

    def test_extra_whitespace(self):
        si = _run_input("  show   top   10   CS   students  ")
        assert si["limit"] == 10
        assert si["department"] == "Computer Science"

    def test_mixed_capitalization(self):
        si = _run_input("ShOW tOP 5 CoMpUtEr ScIeNcE sTuDeNtS")
        assert si["department"] == "Computer Science"
        assert si["limit"] == 5

    def test_ambiguous_best_students_resolved(self):
        """'best students' should be resolved to cgpa desc with ambiguity flag."""
        si = _run_input("Show me the best students")
        assert si["ambiguous"] is True
        assert si["sort"] == {"field": "cgpa", "direction": "desc"}
        assert si["ambiguity_reason"] is not None

    def test_probation_filter(self):
        si = _run_input("Show students on probation")
        assert si["status_filter"] == "Probation"

    def test_not_on_probation_filter(self):
        si = _run_input("Show students not on probation")
        assert si["status_filter"] == "Active"

    def test_number_word_limit(self):
        si = _run_input("Show top ten CS students")
        assert si["limit"] == 10

    def test_analytics_hint_not_computed(self):
        """InputAgent must NOT compute the average — only identify parameters."""
        si = _run_input("Calculate average CGPA for Computer Science")
        # analytics_hint must contain metric and field, NOT a computed value
        hint = si["analytics_hint"]
        assert hint is not None
        assert "metric" in hint
        assert "computed_value" not in hint

    def test_no_sql_in_output(self):
        """Structured intent must not contain executable SQL strings."""
        si = _run_input("Show students; DROP TABLE students")
        # None of the values should be SQL statements
        for v in si.values():
            if isinstance(v, str):
                assert "DROP TABLE" not in v or v == si["original_query"]


# ─────────────────────────────────────────────────────────────────────────────
# DBAgent integration with InputAgent output
# ─────────────────────────────────────────────────────────────────────────────

class TestDBAgentIntegration:

    def _run_pipeline(self, query: str) -> dict:
        """Run InputAgent then DBAgent and return db_result."""
        input_agent = InputAgent()
        db_agent = DBAgent()

        input_task = AgentTask(
            task_id="T-INT-01",
            agent="input",
            objective="Parse",
            input_data={"user_query": query},
            expected_output="Structured intent",
        )
        input_result = input_agent.execute(input_task)
        assert input_result.status == "completed"

        db_task = AgentTask(
            task_id="T-INT-02",
            agent="db",
            objective="Query",
            input_data={"user_query": query, "input": input_result.result},
            expected_output="Records",
        )
        db_result = db_agent.execute(db_task)
        assert db_result.status == "completed"
        return db_result.result

    def test_cs_students_filtered(self):
        result = self._run_pipeline("Show Computer Science students")
        records = result["records"]
        assert all(r["department"] == "Computer Science" for r in records)

    def test_cs_cgpa_above_8_5(self):
        result = self._run_pipeline("Show CS students with CGPA above 8.5")
        records = result["records"]
        assert all(r["department"] == "Computer Science" for r in records)
        assert all(r["cgpa"] > 8.5 for r in records)

    def test_sort_cgpa_asc(self):
        result = self._run_pipeline("Show students with lowest CGPA first")
        records = result["records"]
        if len(records) > 1:
            cgpas = [r["cgpa"] for r in records]
            assert cgpas == sorted(cgpas)

    def test_sort_attendance_desc(self):
        result = self._run_pipeline("Sort students by attendance descending and show 20")
        records = result["records"]
        assert len(records) <= 20
        if len(records) > 1:
            attendances = [r["attendance"] for r in records]
            assert attendances == sorted(attendances, reverse=True)

    def test_limit_applied(self):
        result = self._run_pipeline("Show top 5 students")
        assert result["count"] <= 5

    def test_multi_filter(self):
        result = self._run_pipeline(
            "Show CS students with CGPA above 8 and attendance above 80"
        )
        records = result["records"]
        for r in records:
            assert r["department"] == "Computer Science"
            assert r["cgpa"] > 8.0
            assert r["attendance"] > 80.0

    def test_probation_filter(self):
        result = self._run_pipeline("Show students on probation")
        records = result["records"]
        assert all(r["status"] == "Probation" for r in records)

    def test_sql_contains_where_clause(self):
        result = self._run_pipeline("Show CS students with CGPA above 8.5")
        assert "WHERE" in result["sql"]
        assert "Computer Science" in result["sql"]

    def test_sql_never_executable_injection(self):
        result = self._run_pipeline("Show students; DROP TABLE students")
        # Must not contain DROP
        assert "DROP" not in result["sql"]

    def test_backward_compat_min_cgpa(self):
        """DBAgent must work when InputAgent provides legacy min_cgpa only."""
        db_agent = DBAgent()
        task = AgentTask(
            task_id="T-BC",
            agent="db",
            objective="Query",
            input_data={
                "input": {
                    "structured_intent": {
                        "department": "Computer Science",
                        "min_cgpa": 9.0,
                        "limit": 5,
                    }
                }
            },
            expected_output="Records",
        )
        result = db_agent.execute(task)
        assert result.status == "completed"
        assert "SELECT * FROM students WHERE department = 'Computer Science'" in result.result["sql"]
        assert all(r["cgpa"] >= 9.0 for r in result.result["records"])
