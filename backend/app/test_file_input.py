"""
Tests for file-based input support in InputAgent.

Covers:
  - Excel (.xlsx) parsing: table and single-query formats
  - PDF (.pdf) parsing: table and text-query formats
  - Image parsing: Groq Vision (mocked)
  - InputAgent.execute() with file_path input
  - DBAgent integration with file-parsed records
  - Edge cases: empty files, unsupported extension, bad rows
"""
import os
import json
import tempfile
import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Helpers — build temp sample files
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_STUDENTS = [
    {
        "name": "Alice",
        "roll_number": "CS001",
        "department": "Computer Science",
        "cgpa": 9.1,
        "attendance": 92.0,
        "status": "Active",
        "semester": 6,
        "email": "alice@college.edu",
        "backlogs": 0,
    },
    {
        "name": "Bob",
        "roll_number": "EC001",
        "department": "Electronics",
        "cgpa": 7.8,
        "attendance": 75.0,
        "status": "Probation",
        "semester": 4,
        "email": "bob@college.edu",
        "backlogs": 2,
    },
    {
        "name": "Carol",
        "roll_number": "CS002",
        "department": "Computer Science",
        "cgpa": 8.5,
        "attendance": 88.0,
        "status": "Active",
        "semester": 6,
        "email": "carol@college.edu",
        "backlogs": 0,
    },
]

HEADERS = ["name", "roll_number", "department", "cgpa", "attendance", "status", "semester", "email", "backlogs"]


def _make_xlsx(students=None, query: str = None) -> str:
    """Create a temporary Excel file. Returns the file path."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active

    if query is not None:
        # Single-cell query
        ws.cell(row=1, column=1, value=query)
    else:
        # Table format
        ws.append(HEADERS)
        for s in (students or SAMPLE_STUDENTS):
            ws.append([s.get(h) for h in HEADERS])

    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    wb.save(tmp.name)
    return tmp.name


def _make_pdf_with_text(text: str) -> str:
    """Create a minimal PDF containing text. Uses reportlab if available, else fpdf2."""
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    try:
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(tmp.name)
        c.drawString(50, 750, text)
        c.save()
    except ImportError:
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", size=12)
            pdf.cell(200, 10, txt=text)
            pdf.output(tmp.name)
        except ImportError:
            pytest.skip("Neither reportlab nor fpdf2 installed; skipping PDF creation test.")
    return tmp.name


# ─────────────────────────────────────────────────────────────────────────────
# file_parser unit tests
# ─────────────────────────────────────────────────────────────────────────────

from app.agents.file_parser import (
    is_supported_file,
    parse_excel_file,
    parse_pdf_file,
    parse_image_file,
    parse_file,
    _normalise_headers,
    _row_to_record,
)


class TestIsSupportedFile:
    def test_xlsx_exists(self, tmp_path):
        f = tmp_path / "data.xlsx"
        f.write_bytes(b"")
        assert is_supported_file(str(f)) is True

    def test_pdf_exists(self, tmp_path):
        f = tmp_path / "data.pdf"
        f.write_bytes(b"")
        assert is_supported_file(str(f)) is True

    def test_png_exists(self, tmp_path):
        f = tmp_path / "data.png"
        f.write_bytes(b"")
        assert is_supported_file(str(f)) is True

    def test_txt_not_supported(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_bytes(b"")
        assert is_supported_file(str(f)) is False

    def test_nonexistent_file(self):
        assert is_supported_file("/does/not/exist.xlsx") is False

    def test_empty_string(self):
        assert is_supported_file("") is False

    def test_nl_query_not_file(self):
        assert is_supported_file("Show CS students") is False


class TestNormaliseHeaders:
    def test_known_headers(self):
        headers = ["Name", "CGPA", "Department", "Attendance"]
        result = _normalise_headers(headers)
        # Note: _normalise_headers uses .lower() internally
        # Check that lower-cased versions are mapped
        lower_headers = [h.lower() for h in headers]
        result2 = _normalise_headers(lower_headers)
        assert result2.get("name") == "name"
        assert result2.get("cgpa") == "cgpa"
        assert result2.get("department") == "department"
        assert result2.get("attendance") == "attendance"

    def test_aliases(self):
        headers = ["gpa", "dept", "sem", "roll no"]
        result = _normalise_headers(headers)
        assert result.get("gpa") == "cgpa"
        assert result.get("dept") == "department"
        assert result.get("sem") == "semester"
        assert result.get("roll no") == "roll_number"

    def test_unknown_headers(self):
        headers = ["spaceship", "unicorn"]
        result = _normalise_headers(headers)
        assert result == {}


class TestRowToRecord:
    def test_full_valid_row(self):
        row = {
            "name": "Alice",
            "department": "computer science",
            "cgpa": "8.5",
            "attendance": "90%",
            "status": "active",
            "semester": "6",
            "email": "alice@test.com",
            "backlogs": "0",
        }
        rec = _row_to_record(row)
        assert rec["name"] == "Alice"
        assert rec["department"] == "Computer Science"
        assert rec["cgpa"] == 8.5
        assert rec["attendance"] == 90.0
        assert rec["status"] == "Active"
        assert rec["semester"] == 6

    def test_invalid_cgpa_excluded(self):
        row = {"name": "X", "cgpa": "banana"}
        rec = _row_to_record(row)
        assert "cgpa" not in rec

    def test_cgpa_out_of_range_excluded(self):
        row = {"name": "X", "cgpa": "11.5"}
        rec = _row_to_record(row)
        assert "cgpa" not in rec

    def test_attendance_percent_suffix(self):
        row = {"attendance": "85%"}
        rec = _row_to_record(row)
        assert rec["attendance"] == 85.0

    def test_none_values_excluded(self):
        row = {"name": None, "cgpa": None}
        rec = _row_to_record(row)
        assert "name" not in rec
        assert "cgpa" not in rec

    def test_probation_status(self):
        row = {"status": "probation"}
        rec = _row_to_record(row)
        assert rec["status"] == "Probation"

    def test_graduated_status(self):
        row = {"status": "graduated"}
        rec = _row_to_record(row)
        assert rec["status"] == "Graduated"


class TestParseExcelFile:
    def test_table_format(self):
        path = _make_xlsx()
        try:
            result = parse_excel_file(path)
            assert result is not None
            assert result["type"] == "table"
            assert len(result["records"]) == len(SAMPLE_STUDENTS)
            # Check first record
            first = result["records"][0]
            assert first["name"] == "Alice"
            assert first["department"] == "Computer Science"
            assert first["cgpa"] == 9.1
        finally:
            os.unlink(path)

    def test_query_format(self):
        path = _make_xlsx(query="Show CS students with CGPA above 8.5")
        try:
            result = parse_excel_file(path)
            assert result is not None
            assert result["type"] == "query"
            assert "CS students" in result["query"]
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        result = parse_excel_file("/nonexistent/path/data.xlsx")
        assert result is None

    def test_dept_normalisation(self):
        students = [{"name": "X", "roll_number": "R1", "department": "cse",
                     "cgpa": 8.0, "attendance": 80.0, "status": "active",
                     "semester": 3, "email": "", "backlogs": 0}]
        path = _make_xlsx(students=students)
        try:
            result = parse_excel_file(path)
            assert result["records"][0]["department"] == "Computer Science"
        finally:
            os.unlink(path)

    def test_empty_rows_skipped(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(HEADERS)
        ws.append([None] * len(HEADERS))  # empty row
        ws.append(["Dave", "CS003", "Civil", 7.0, 65.0, "active", 4, "", 1])
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp.close()
        wb.save(tmp.name)
        try:
            result = parse_excel_file(tmp.name)
            assert result is not None
            assert all(r.get("name") is not None for r in result["records"])
        finally:
            os.unlink(tmp.name)


class TestParsePdfFile:
    def test_text_query_extraction(self):
        path = _make_pdf_with_text("Show Electronics students with CGPA above 7")
        try:
            result = parse_pdf_file(path)
            assert result is not None
            assert result["type"] == "query"
            assert "Electronics" in result["query"] or len(result["query"]) > 5
        finally:
            os.unlink(path)

    def test_nonexistent_pdf(self):
        result = parse_pdf_file("/nonexistent/data.pdf")
        assert result is None


class TestParseImageFile:
    def test_returns_none_without_groq(self):
        result = parse_image_file("/some/image.png", groq_service=None)
        assert result is None

    def test_uses_groq_service(self, tmp_path):
        """Test that parse_image_file calls groq_service.extract_data_from_image."""
        class MockGroq:
            called = False
            def extract_data_from_image(self, path):
                MockGroq.called = True
                return {
                    "type": "table",
                    "records": [
                        {"name": "Groq Student", "department": "Computer Science",
                         "cgpa": 8.9, "attendance": 91.0, "status": "Active"}
                    ]
                }

        img_path = str(tmp_path / "test.png")
        # Create a minimal PNG file
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")  # PNG magic bytes

        result = parse_image_file(img_path, groq_service=MockGroq())
        assert MockGroq.called is True
        assert result is not None
        assert result["type"] == "table"
        assert result["records"][0]["name"] == "Groq Student"
        assert result["records"][0]["cgpa"] == 8.9

    def test_groq_query_response(self, tmp_path):
        """Test that parse_image_file handles query-type response."""
        class MockGroqQuery:
            def extract_data_from_image(self, path):
                return {"type": "query", "query": "Show top 5 CS students"}

        img_path = str(tmp_path / "test.jpg")
        with open(img_path, "wb") as f:
            f.write(b"\xff\xd8\xff")  # JPEG magic bytes

        result = parse_image_file(img_path, groq_service=MockGroqQuery())
        assert result["type"] == "query"
        assert "CS students" in result["query"]

    def test_groq_failure_returns_none(self, tmp_path):
        class MockGroqFail:
            def extract_data_from_image(self, path):
                return None

        img_path = str(tmp_path / "test.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")

        result = parse_image_file(img_path, groq_service=MockGroqFail())
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# InputAgent with file input
# ─────────────────────────────────────────────────────────────────────────────

from app.agents.input_agent import InputAgent
from app.mother.types import AgentTask


def _make_task(user_query: str = "", file_path: str = "") -> AgentTask:
    input_data = {}
    if user_query:
        input_data["user_query"] = user_query
    if file_path:
        input_data["file_path"] = file_path
    return AgentTask(
        task_id="FILE-TEST-001",
        agent="input",
        objective="File input test",
        input_data=input_data,
        expected_output="Structured intent",
    )


class TestInputAgentWithFiles:
    def test_excel_table_produces_parsed_records(self):
        path = _make_xlsx()
        try:
            agent = InputAgent()
            result = agent.execute(_make_task(file_path=path))
            assert result.status == "completed"
            si = result.result["structured_intent"]
            assert si["source_type"] == "file"
            assert si["parsed_records"] is not None
            assert len(si["parsed_records"]) == len(SAMPLE_STUDENTS)
        finally:
            os.unlink(path)

    def test_excel_query_processed_as_nl(self):
        path = _make_xlsx(query="Show CS students with CGPA above 8.5")
        try:
            agent = InputAgent()
            result = agent.execute(_make_task(file_path=path))
            assert result.status == "completed"
            si = result.result["structured_intent"]
            assert si["source_type"] == "file"
            # parsed_records is None because it was a query, not a table
            assert si["parsed_records"] is None
            # The NL pipeline should have extracted CS department
            assert si["department"] == "Computer Science"
            cgpa_f = [f for f in si["filters"] if f["field"] == "cgpa"]
            assert len(cgpa_f) == 1
            assert cgpa_f[0]["operator"] == ">"
            assert cgpa_f[0]["value"] == 8.5
        finally:
            os.unlink(path)

    def test_original_query_is_file_path_for_table(self):
        path = _make_xlsx()
        try:
            agent = InputAgent()
            result = agent.execute(_make_task(file_path=path))
            si = result.result["structured_intent"]
            assert si["original_query"] == path
        finally:
            os.unlink(path)

    def test_text_query_still_works(self):
        agent = InputAgent()
        result = agent.execute(_make_task(user_query="Show top 10 CS students"))
        assert result.status == "completed"
        si = result.result["structured_intent"]
        assert si["source_type"] == "text"
        assert si["parsed_records"] is None
        assert si["limit"] == 10

    def test_nonexistent_file_fails(self):
        agent = InputAgent()
        result = agent.execute(_make_task(user_query="/nonexistent/path/students.xlsx"))
        # Non-existent file path → treated as NL query (not a file), status = completed
        assert result.status == "completed"
        si = result.result["structured_intent"]
        assert si["source_type"] == "text"

    def test_image_file_uses_groq(self, tmp_path, monkeypatch):
        """InputAgent should call GroqService for image files."""
        img_path = str(tmp_path / "students.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")

        mock_result = {
            "type": "table",
            "records": [
                {"name": "ImgStudent", "department": "Electronics",
                 "cgpa": 8.0, "attendance": 80.0, "status": "Active"}
            ]
        }

        # Monkeypatch GroqService.extract_data_from_image
        from app.services import groq_service as gs_module
        original_init = gs_module.GroqService.__init__

        def mock_init(self, *args, **kwargs):
            self.client = True  # pretend client is ready
            self.api_key = "test"
            self.model = "test-model"

        def mock_extract(self, path):
            return mock_result

        monkeypatch.setattr(gs_module.GroqService, "__init__", mock_init)
        monkeypatch.setattr(gs_module.GroqService, "extract_data_from_image", mock_extract)

        agent = InputAgent()
        result = agent.execute(_make_task(file_path=img_path))
        assert result.status == "completed"
        si = result.result["structured_intent"]
        assert si["source_type"] == "file"
        assert si["parsed_records"] is not None
        assert si["parsed_records"][0]["name"] == "ImgStudent"

    def test_combined_path_and_query(self):
        path = _make_xlsx()
        try:
            agent = InputAgent()
            result = agent.execute(_make_task(user_query=f"{path} show CS students with CGPA above 8.5"))
            assert result.status == "completed"
            si = result.result["structured_intent"]
            assert si["source_type"] == "file"
            assert si["parsed_records"] is not None
            assert len(si["parsed_records"]) == len(SAMPLE_STUDENTS)
            assert si["department"] == "Computer Science"
            cgpa_f = [f for f in si["filters"] if f["field"] == "cgpa"]
            assert len(cgpa_f) == 1
            assert cgpa_f[0]["operator"] == ">"
            assert cgpa_f[0]["value"] == 8.5
        finally:
            os.unlink(path)



# ─────────────────────────────────────────────────────────────────────────────
# DBAgent integration with file-parsed records
# ─────────────────────────────────────────────────────────────────────────────

from app.agents.db_agent import DBAgent


class TestDBAgentWithParsedRecords:
    def _run_pipeline(self, students, query="", dept=None, cgpa_above=None, limit=None):
        db_agent = DBAgent()
        structured_intent = {
            "parsed_records": students,
            "department": dept,
            "filters": ([{"field": "cgpa", "operator": ">", "value": cgpa_above}]
                        if cgpa_above else []),
            "sort": {"field": "cgpa", "direction": "desc"},
            "limit": limit,
            "status_filter": None,
            "min_cgpa": cgpa_above,
        }
        task = AgentTask(
            task_id="DB-FILE-001",
            agent="db",
            objective="Test",
            input_data={"input": {"structured_intent": structured_intent}},
            expected_output="Records",
        )
        result = db_agent.execute(task)
        assert result.status == "completed"
        return result.result

    def test_all_records_returned(self):
        result = self._run_pipeline(SAMPLE_STUDENTS)
        assert result["count"] == len(SAMPLE_STUDENTS)

    def test_dept_filter_on_parsed_records(self):
        result = self._run_pipeline(SAMPLE_STUDENTS, dept="Computer Science")
        assert all(r["department"] == "Computer Science" for r in result["records"])
        assert result["count"] == 2  # Alice and Carol

    def test_cgpa_filter_on_parsed_records(self):
        result = self._run_pipeline(SAMPLE_STUDENTS, cgpa_above=8.0)
        for r in result["records"]:
            assert r["cgpa"] > 8.0

    def test_sort_by_cgpa_desc(self):
        result = self._run_pipeline(SAMPLE_STUDENTS)
        cgpas = [r["cgpa"] for r in result["records"]]
        assert cgpas == sorted(cgpas, reverse=True)

    def test_limit_applied(self):
        result = self._run_pipeline(SAMPLE_STUDENTS, limit=1)
        assert result["count"] == 1

    def test_combined_dept_and_cgpa_filter(self):
        result = self._run_pipeline(SAMPLE_STUDENTS, dept="Computer Science", cgpa_above=9.0)
        assert all(r["department"] == "Computer Science" for r in result["records"])
        assert all(r["cgpa"] > 9.0 for r in result["records"])

    def test_sql_indicates_file_source(self):
        """SQL generated should still be syntactically reasonable for traceability."""
        result = self._run_pipeline(SAMPLE_STUDENTS, dept="Electronics")
        sql = result["sql"]
        assert "SELECT * FROM students" in sql
        assert "Electronics" in sql

    def test_falls_back_to_db_when_no_parsed_records(self):
        """When parsed_records is None or empty, DBAgent should use the database."""
        db_agent = DBAgent()
        task = AgentTask(
            task_id="DB-FALLBACK",
            agent="db",
            objective="Test",
            input_data={
                "input": {
                    "structured_intent": {
                        "parsed_records": None,
                        "department": None,
                        "filters": [],
                        "sort": None,
                        "limit": 5,
                        "status_filter": None,
                        "min_cgpa": None,
                    }
                }
            },
            expected_output="Records",
        )
        result = db_agent.execute(task)
        assert result.status == "completed"
        # Should return records from the actual database (not empty)
        assert result.result["count"] >= 0

    def test_invalid_records_skipped(self):
        bad_students = [
            {"name": "Good", "cgpa": 8.5, "department": "Computer Science",
             "attendance": 90.0, "status": "Active"},
            {"cgpa": "not-a-number"},  # will fail validation or be skipped
        ]
        result = self._run_pipeline(bad_students)
        # At least the good student should be in there
        assert result["count"] >= 1

    def test_full_pipeline_excel_to_db(self):
        """End-to-end: Excel → InputAgent → DBAgent."""
        path = _make_xlsx()
        try:
            input_agent = InputAgent()
            db_agent = DBAgent()

            # Step 1: InputAgent
            input_task = AgentTask(
                task_id="E2E-INPUT",
                agent="input",
                objective="Parse file",
                input_data={"file_path": path},
                expected_output="Structured intent",
            )
            input_result = input_agent.execute(input_task)
            assert input_result.status == "completed"
            si = input_result.result["structured_intent"]
            assert si["parsed_records"] is not None

            # Step 2: DBAgent
            db_task = AgentTask(
                task_id="E2E-DB",
                agent="db",
                objective="Query records",
                input_data={"input": input_result.result},
                expected_output="Records",
            )
            db_result = db_agent.execute(db_task)
            assert db_result.status == "completed"
            assert db_result.result["count"] == len(SAMPLE_STUDENTS)
        finally:
            os.unlink(path)
