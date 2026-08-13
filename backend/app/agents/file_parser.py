"""
File parsing utilities for InputAgent.

Supports:
  - Excel   (.xlsx)  via openpyxl
  - PDF     (.pdf)   via pdfplumber
  - Images  (.png / .jpg / .jpeg) via Groq Vision API

Returns either:
  {"type": "table",  "records": [...]}   — list of student dicts extracted from file
  {"type": "query",  "query":  "..."}    — a NL query string found inside the file

Security: file contents are never executed as SQL. Only structured values are returned.
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".xlsx", ".pdf", ".png", ".jpg", ".jpeg"}

# ─────────────────────────────────────────────────────────────────────────────
# Header / value normalisation helpers
# ─────────────────────────────────────────────────────────────────────────────

_HEADER_ALIASES: dict[str, str] = {
    "name": "name",
    "student name": "name",
    "student_name": "name",
    "full name": "name",
    "roll number": "roll_number",
    "rollnumber": "roll_number",
    "roll no": "roll_number",
    "roll": "roll_number",
    "roll_number": "roll_number",
    "department": "department",
    "dept": "department",
    "branch": "department",
    "cgpa": "cgpa",
    "gpa": "cgpa",
    "grade": "cgpa",
    "grades": "cgpa",
    "attendance": "attendance",
    "attend": "attendance",
    "attendance %": "attendance",
    "attendance%": "attendance",
    "status": "status",
    "student status": "status",
    "semester": "semester",
    "sem": "semester",
    "email": "email",
    "email id": "email",
    "mail": "email",
    "backlogs": "backlogs",
    "backlog": "backlogs",
    "no. of backlogs": "backlogs",
    "project": "project_title",
    "project title": "project_title",
    "projecttitle": "project_title",
    "project_title": "project_title",
    "id": "id",
    "student id": "id",
    "student_id": "id",
}

_DEPT_ALIASES: dict[str, str] = {
    "computer science": "Computer Science",
    "computer sciences": "Computer Science",
    "cs": "Computer Science",
    "cse": "Computer Science",
    "comp sci": "Computer Science",
    "electronics": "Electronics",
    "ec": "Electronics",
    "ece": "Electronics",
    "electronics and communication": "Electronics",
    "mechanical": "Mechanical",
    "mechanical engineering": "Mechanical",
    "mech": "Mechanical",
    "me": "Mechanical",
    "civil": "Civil",
    "civil engineering": "Civil",
    "ce": "Civil",
    "data science": "Data Science",
    "data sciences": "Data Science",
    "ds": "Data Science",
    "ai & ml": "AI & ML",
    "ai and ml": "AI & ML",
    "ai": "AI & ML",
    "ml": "AI & ML",
    "aiml": "AI & ML",
    "artificial intelligence": "AI & ML",
    "machine learning": "AI & ML",
}

_STATUS_MAP = {
    "active": "Active",
    "probation": "Probation",
    "on probation": "Probation",
    "graduated": "Graduated",
    "graduate": "Graduated",
}


def _normalise_dept(val: str) -> Optional[str]:
    return _DEPT_ALIASES.get(val.strip().lower())


def _normalise_headers(headers: list[str]) -> dict[str, str]:
    """Map raw column header strings → canonical StudentRecord field names."""
    mapping: dict[str, str] = {}
    for raw in headers:
        canonical = _HEADER_ALIASES.get(raw.strip().lower())
        if canonical:
            mapping[raw] = canonical
    return mapping


def _row_to_record(row_dict: dict) -> dict:
    """Convert a canonical-key row dict to a clean student record dict."""
    record: dict = {}

    if "name" in row_dict and row_dict["name"] is not None:
        record["name"] = str(row_dict["name"]).strip()

    if "roll_number" in row_dict and row_dict["roll_number"] is not None:
        record["roll_number"] = str(row_dict["roll_number"]).strip()

    if "id" in row_dict and row_dict["id"] is not None:
        record["id"] = str(row_dict["id"]).strip()

    if "department" in row_dict and row_dict["department"] is not None:
        dept = _normalise_dept(str(row_dict["department"]))
        if dept:
            record["department"] = dept

    if "cgpa" in row_dict and row_dict["cgpa"] is not None:
        try:
            cgpa = float(row_dict["cgpa"])
            if 0.0 <= cgpa <= 10.0:
                record["cgpa"] = round(cgpa, 2)
        except (ValueError, TypeError):
            pass

    if "attendance" in row_dict and row_dict["attendance"] is not None:
        try:
            att = float(str(row_dict["attendance"]).rstrip("%").strip())
            if 0.0 <= att <= 100.0:
                record["attendance"] = round(att, 2)
        except (ValueError, TypeError):
            pass

    if "status" in row_dict and row_dict["status"] is not None:
        record["status"] = _STATUS_MAP.get(
            str(row_dict["status"]).strip().lower(), "Active"
        )

    if "semester" in row_dict and row_dict["semester"] is not None:
        try:
            sem = int(float(str(row_dict["semester"])))
            if 1 <= sem <= 8:
                record["semester"] = sem
        except (ValueError, TypeError):
            pass

    if "email" in row_dict and row_dict["email"] is not None:
        record["email"] = str(row_dict["email"]).strip()

    if "backlogs" in row_dict and row_dict["backlogs"] is not None:
        try:
            record["backlogs"] = max(0, int(float(str(row_dict["backlogs"]))))
        except (ValueError, TypeError):
            pass

    if "project_title" in row_dict and row_dict["project_title"] is not None:
        pt = str(row_dict["project_title"]).strip()
        if pt:
            record["project_title"] = pt

    return record


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────


def is_supported_file(value: str) -> bool:
    """Return True if value is a path to a supported file type that exists on disk."""
    if not value:
        return False
    stripped = value.strip().strip('"').strip("'")
    ext = os.path.splitext(stripped)[1].lower()
    return ext in SUPPORTED_EXTENSIONS and os.path.exists(stripped)


def parse_file(file_path: str, groq_service=None, query: Optional[str] = None) -> Optional[dict]:
    """
    Dispatch to the appropriate parser based on file extension.
    Returns {"type": "table", "records": [...]} or {"type": "query", "query": "..."}.
    Returns None on failure.
    """
    file_path = file_path.strip().strip('"').strip("'")
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".xlsx":
        return parse_excel_file(file_path)
    elif ext == ".pdf":
        return parse_pdf_file(file_path)
    elif ext in (".png", ".jpg", ".jpeg"):
        return parse_image_file(file_path, groq_service, query)
    else:
        logger.warning("Unsupported file extension '%s' in: %s", ext, file_path)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Excel parser
# ─────────────────────────────────────────────────────────────────────────────


def parse_excel_file(file_path: str) -> Optional[dict]:
    """
    Parse an .xlsx file.
    - Single non-empty cell  → {"type": "query",  "query": "..."}
    - Header row + data rows → {"type": "table",  "records": [...]}
    """
    try:
        import openpyxl  # already installed (crewai dependency)

        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))

        if not rows:
            logger.warning("Excel file is empty: %s", file_path)
            return None

        # Filter fully-empty rows
        non_empty = [r for r in rows if any(c is not None for c in r)]
        if not non_empty:
            return None

        # Single-cell query?
        all_cells = [c for r in non_empty for c in r if c is not None]
        if len(all_cells) == 1:
            query = str(all_cells[0]).strip()
            logger.info("Excel detected as NL query: '%s'", query[:80])
            return {"type": "query", "query": query}

        # Table format: first non-empty row is the header row
        headers = [str(h).strip() if h is not None else "" for h in non_empty[0]]
        header_map = _normalise_headers(headers)

        if not header_map:
            # No recognised headers — join all text as a query
            full_text = " ".join(str(c) for c in all_cells)
            logger.info("Excel: no headers found, treating content as query.")
            return {"type": "query", "query": full_text.strip()}

        records: list[dict] = []
        for row in non_empty[1:]:
            if not any(c is not None for c in row):
                continue
            row_dict: dict = {}
            for i, val in enumerate(row):
                if i < len(headers) and headers[i] in header_map:
                    row_dict[header_map[headers[i]]] = val
            rec = _row_to_record(row_dict)
            if rec:
                records.append(rec)

        logger.info(
            "Excel parsed as table: %d records from '%s'", len(records), file_path
        )
        return {"type": "table", "records": records}

    except ImportError:
        logger.error("openpyxl is not installed; cannot parse Excel files.")
        return None
    except Exception as exc:
        logger.error("Error parsing Excel file '%s': %s", file_path, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PDF parser
# ─────────────────────────────────────────────────────────────────────────────


def parse_pdf_file(file_path: str) -> Optional[dict]:
    """
    Parse a .pdf file using pdfplumber.
    Tries tables first; falls back to raw text extraction.
    """
    try:
        import pdfplumber  # already installed (crewai dependency)

        with pdfplumber.open(file_path) as pdf:
            all_tables: list[list[list]] = []
            text_lines: list[str] = []

            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)
                text = page.extract_text()
                if text:
                    text_lines.extend(text.splitlines())

        # ── Table path ──
        for table in all_tables:
            if not table or len(table) < 2:
                continue

            headers = [str(h).strip() if h else "" for h in table[0]]
            header_map = _normalise_headers(headers)
            if not header_map:
                continue

            records: list[dict] = []
            for row in table[1:]:
                if not any(c for c in row):
                    continue
                row_dict: dict = {}
                for i, val in enumerate(row):
                    if i < len(headers) and headers[i] in header_map:
                        row_dict[header_map[headers[i]]] = val
                rec = _row_to_record(row_dict)
                if rec:
                    records.append(rec)

            if records:
                logger.info(
                    "PDF parsed as table: %d records from '%s'", len(records), file_path
                )
                return {"type": "table", "records": records}

        # ── Text / query path ──
        full_text = " ".join(ln.strip() for ln in text_lines if ln.strip())
        if full_text:
            logger.info("PDF parsed as text query from '%s'", file_path)
            return {"type": "query", "query": full_text}

        logger.warning("PDF appears to be empty: %s", file_path)
        return None

    except ImportError:
        logger.error("pdfplumber is not installed; cannot parse PDF files.")
        return None
    except Exception as exc:
        logger.error("Error parsing PDF file '%s': %s", file_path, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Image parser (Groq Vision)
# ─────────────────────────────────────────────────────────────────────────────


def parse_image_file(file_path: str, groq_service=None, query: Optional[str] = None) -> Optional[dict]:
    """
    Parse an image file (.png / .jpg / .jpeg) using Groq Vision API.
    Returns {"type": "table", "records": [...]} or {"type": "query", "query": "..."}.
    Requires a configured GroqService instance.
    """
    if groq_service is None:
        logger.warning(
            "No GroqService provided for image parsing; cannot extract from image."
        )
        return None

    result = groq_service.extract_data_from_image(file_path, query)
    if not result:
        return None

    data_type = result.get("type")

    if data_type == "table":
        raw_records = result.get("records") or []
        normalised: list[dict] = []
        for r in raw_records:
            rec: dict = {}
            if r.get("name"):
                rec["name"] = str(r["name"]).strip()
            if r.get("roll_number"):
                rec["roll_number"] = str(r["roll_number"]).strip()
            if r.get("department"):
                dept = _normalise_dept(str(r["department"]))
                rec["department"] = dept or str(r["department"])
            if r.get("cgpa") is not None:
                try:
                    cgpa = float(r["cgpa"])
                    if 0.0 <= cgpa <= 10.0:
                        rec["cgpa"] = round(cgpa, 2)
                except (ValueError, TypeError):
                    pass
            if r.get("attendance") is not None:
                try:
                    att = float(str(r["attendance"]).rstrip("%"))
                    if 0.0 <= att <= 100.0:
                        rec["attendance"] = round(att, 2)
                except (ValueError, TypeError):
                    pass
            if r.get("status"):
                rec["status"] = _STATUS_MAP.get(
                    str(r["status"]).strip().lower(), "Active"
                )
            if r.get("semester") is not None:
                try:
                    sem = int(r["semester"])
                    if 1 <= sem <= 8:
                        rec["semester"] = sem
                except (ValueError, TypeError):
                    pass
            if r.get("email"):
                rec["email"] = str(r["email"]).strip()
            if r.get("backlogs") is not None:
                try:
                    rec["backlogs"] = max(0, int(r["backlogs"]))
                except (ValueError, TypeError):
                    pass
            if r.get("project_title"):
                rec["project_title"] = str(r["project_title"]).strip()
            normalised.append(rec)

        logger.info("Image parsed as table: %d records", len(normalised))
        return {"type": "table", "records": normalised}

    elif data_type == "query":
        query = str(result.get("query", "")).strip()
        if query:
            logger.info("Image parsed as NL query: '%s'", query[:80])
            return {"type": "query", "query": query}

    logger.warning("Groq Vision returned unrecognised type: %s", data_type)
    return None
