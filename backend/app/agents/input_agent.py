"""
InputAgent — translates natural-language user queries into structured query
specifications consumed by downstream agents (DBAgent, AnalyticsAgent).

Supports three input modes:
  1. Natural language text query  (original mode)
  2. Path to an Excel file (.xlsx) containing a student table or NL query
  3. Path to a PDF file   (.pdf)  containing a student table or NL query
  4. Path to an image     (.png/.jpg/.jpeg) — OCR via Groq Vision API

Pipeline:
  Raw query / file path
    → [if file] parse file → extract records or NL query
    → normalize → detect operation → extract entities → extract filters
    → extract sort → extract limit → extract fields → extract analytics hints
    → validate → structured result

Must NOT: query DB · execute SQL · compute analytics · generate final output ·
           replace MotherAgent · make additional LLM calls (except Vision for images).
"""
import logging
import re
from typing import Optional, Dict

from app.agents.base import BaseAgent
from app.agents.file_parser import is_supported_file, parse_file, SUPPORTED_EXTENSIONS
from app.mother.types import AgentTask, AgentResult
from app.services.groq_service import GroqService

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Domain constants  (authoritative — edit here when data model changes)
# ─────────────────────────────────────────────────────────────────────────────

CANONICAL_DEPARTMENTS = [
    "Computer Science",
    "Electronics",
    "Mechanical",
    "Civil",
    "Data Science",
    "AI & ML",
]

# All aliases → canonical department name.  Longest aliases checked first.
DEPARTMENT_ALIASES: dict[str, str] = {
    # Computer Science
    "computer science": "Computer Science",
    "computer sciences": "Computer Science",
    "comp sci": "Computer Science",
    "c.s.e.": "Computer Science",
    "c.s.": "Computer Science",
    "cse": "Computer Science",
    "cs": "Computer Science",
    # Electronics
    "electronics and communication": "Electronics",
    "electronics": "Electronics",
    "ece": "Electronics",
    "e.c.": "Electronics",
    "ec": "Electronics",
    # Mechanical
    "mechanical engineering": "Mechanical",
    "mechanical": "Mechanical",
    "mech": "Mechanical",
    "m.e.": "Mechanical",
    "me": "Mechanical",
    # Civil
    "civil engineering": "Civil",
    "civil": "Civil",
    "c.e.": "Civil",
    "ce": "Civil",
    # Data Science
    "data sciences": "Data Science",
    "data science": "Data Science",
    "ds": "Data Science",
    # AI & ML
    "artificial intelligence": "AI & ML",
    "machine learning": "AI & ML",
    "ai and ml": "AI & ML",
    "ai & ml": "AI & ML",
    "ai ml": "AI & ML",
    "aiml": "AI & ML",
    "ai": "AI & ML",
    "ml": "AI & ML",
}

# Fields that exist in StudentRecord (authoritative)
KNOWN_FIELDS: set[str] = {
    "id",
    "roll_number",
    "name",
    "department",
    "cgpa",
    "semester",
    "attendance",
    "email",
    "status",
    "backlogs",
    "project_title",
}

# User-facing aliases → canonical field name
FIELD_ALIASES: dict[str, str] = {
    "student id": "id",
    "student_id": "id",
    "roll number": "roll_number",
    "rollnumber": "roll_number",
    "roll no": "roll_number",
    "gpa": "cgpa",
    "grade": "cgpa",
    "grades": "cgpa",
    "attend": "attendance",
    "project": "project_title",
    "project title": "project_title",
    "backlog": "backlogs",
    "sem": "semester",
}

# Fields on which sorting makes sense
SORTABLE_FIELDS: set[str] = {"cgpa", "attendance", "backlogs", "semester"}

# Supported comparison operators
VALID_OPERATORS: set[str] = {">", ">=", "<", "<=", "="}

# Number words → integers
NUMBER_WORDS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
}


# ─────────────────────────────────────────────────────────────────────────────
# Text normalisation helpers
# ─────────────────────────────────────────────────────────────────────────────


def normalize_prompt(query: str) -> str:
    """Return whitespace-collapsed, lowercased copy for pattern matching."""
    return " ".join(query.lower().split())


def _parse_numeric(token: str) -> Optional[float]:
    """Parse a token as a number, stripping trailing '%'."""
    token = token.rstrip("%").strip()
    try:
        return float(token)
    except ValueError:
        return None


def _resolve_number(token: str) -> Optional[float]:
    """Try numeric parse, then number-word lookup."""
    v = _parse_numeric(token)
    if v is not None:
        return v
    w = NUMBER_WORDS.get(token.strip().lower())
    return float(w) if w is not None else None


# ─────────────────────────────────────────────────────────────────────────────
# Department extraction
# ─────────────────────────────────────────────────────────────────────────────


def extract_department(query_lower: str) -> Optional[str]:
    """
    Return the canonical department name if one is detected, else None.
    Accepts both already-lowercased input and mixed-case input (lowercases internally).
    Checks full canonical names first (longest first to avoid partial matches),
    then the alias table.  Never invents departments outside CANONICAL_DEPARTMENTS.
    """
    q = query_lower.lower()  # tolerate mixed-case input

    # Full canonical names, longest first
    for dept in sorted(CANONICAL_DEPARTMENTS, key=len, reverse=True):
        if dept.lower() in q:
            return dept

    # Alias table, longest alias first (prevents "ai" from matching inside "aiml")
    for alias in sorted(DEPARTMENT_ALIASES, key=len, reverse=True):
        pattern = r"(?<![a-z])" + re.escape(alias) + r"(?![a-z&])"
        if re.search(pattern, q):
            return DEPARTMENT_ALIASES[alias]

    return None


# ─────────────────────────────────────────────────────────────────────────────
# CGPA filter extraction
# ─────────────────────────────────────────────────────────────────────────────


def extract_cgpa_filter(query_lower: str) -> list[dict]:
    """
    Returns a list of CGPA filter dicts, each shaped as:
      {"field": "cgpa", "operator": ">", "value": 8.5}

    Supports: >, >=, <, <=, =, between X and Y.
    Returns [] when no CGPA condition is found.
    Marks out-of-domain values with a "validation_error" key (0 ≤ cgpa ≤ 10).
    """
    # ── Between ──
    between = re.search(
        r"\bcgpa\s+between\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)\b",
        query_lower,
    )
    if between:
        lo, hi = float(between.group(1)), float(between.group(2))
        if not (0.0 <= lo <= 10.0 and 0.0 <= hi <= 10.0 and lo <= hi):
            logger.warning("Invalid CGPA between range: %s–%s", lo, hi)
            return [
                {
                    "field": "cgpa",
                    "operator": ">=",
                    "value": lo,
                    "validation_error": f"CGPA range {lo}–{hi} is invalid (must be 0–10, lo ≤ hi)",
                }
            ]
        return [
            {"field": "cgpa", "operator": ">=", "value": lo},
            {"field": "cgpa", "operator": "<=", "value": hi},
        ]

    # ── Ordered operator patterns (longer / more specific first) ──
    patterns = [
        # cgpa <phrase> <value>
        (r"\bcgpa\s*(?:greater\s+than\s+or\s+equal\s+to|>=|at\s+least|no\s+less\s+than)\s*(\d+(?:\.\d+)?)\b", ">="),
        (r"\bcgpa\s*(?:less\s+than\s+or\s+equal\s+to|<=|at\s+most|no\s+more\s+than)\s*(\d+(?:\.\d+)?)\b", "<="),
        (r"\bcgpa\s*(?:greater\s+than|above|more\s+than|over|>)\s*(\d+(?:\.\d+)?)\b", ">"),
        (r"\bcgpa\s*(?:less\s+than|below|under|fewer\s+than|<)\s*(\d+(?:\.\d+)?)\b", "<"),
        (r"\bcgpa\s*(?:equal\s+to|exactly|=)\s*(\d+(?:\.\d+)?)\b", "="),
        # Reversed: <phrase> <value> cgpa
        (r"\b(?:at\s+least|>=)\s+(\d+(?:\.\d+)?)\s+cgpa\b", ">="),
        (r"\b(?:at\s+most|<=)\s+(\d+(?:\.\d+)?)\s+cgpa\b", "<="),
        (r"\b(?:above|greater\s+than|more\s+than|over)\s+(\d+(?:\.\d+)?)\s+cgpa\b", ">"),
        (r"\b(?:below|less\s+than|under)\s+(\d+(?:\.\d+)?)\s+cgpa\b", "<"),
    ]

    for pat, op in patterns:
        m = re.search(pat, query_lower)
        if m:
            val = float(m.group(1))
            if not (0.0 <= val <= 10.0):
                logger.warning("CGPA value out of domain [0,10]: %s", val)
                return [
                    {
                        "field": "cgpa",
                        "operator": op,
                        "value": val,
                        "validation_error": f"CGPA value {val} is outside valid range 0–10",
                    }
                ]
            return [{"field": "cgpa", "operator": op, "value": val}]

    return []


# ─────────────────────────────────────────────────────────────────────────────
# Attendance filter extraction
# ─────────────────────────────────────────────────────────────────────────────


def extract_attendance_filter(query_lower: str) -> list[dict]:
    """
    Returns a list of attendance filter dicts.
    Attendance in StudentRecord is stored as float 0–100 (percentage).
    '80%' → 80.0  (NOT 0.80).
    """
    # ── Between ──
    between = re.search(
        r"\battendance\s+between\s+(\d+(?:\.\d+)?)%?\s+and\s+(\d+(?:\.\d+)?)%?\b",
        query_lower,
    )
    if between:
        lo, hi = float(between.group(1)), float(between.group(2))
        if not (0.0 <= lo <= 100.0 and 0.0 <= hi <= 100.0 and lo <= hi):
            logger.warning("Invalid attendance between range: %s–%s", lo, hi)
            return [
                {
                    "field": "attendance",
                    "operator": ">=",
                    "value": lo,
                    "validation_error": f"Attendance range {lo}–{hi} is invalid",
                }
            ]
        return [
            {"field": "attendance", "operator": ">=", "value": lo},
            {"field": "attendance", "operator": "<=", "value": hi},
        ]

    patterns = [
        (r"\battendance\s*(?:greater\s+than\s+or\s+equal\s+to|>=|at\s+least)\s*(\d+(?:\.\d+)?)%?\b", ">="),
        (r"\battendance\s*(?:less\s+than\s+or\s+equal\s+to|<=|at\s+most)\s*(\d+(?:\.\d+)?)%?\b", "<="),
        (r"\battendance\s*(?:above|greater\s+than|more\s+than|over|>)\s*(\d+(?:\.\d+)?)%?\b", ">"),
        (r"\battendance\s*(?:below|less\s+than|under|<)\s*(\d+(?:\.\d+)?)%?\b", "<"),
        (r"\battendance\s*(?:equal\s+to|=)\s*(\d+(?:\.\d+)?)%?\b", "="),
        # Reversed
        (r"\b(?:at\s+least|>=)\s+(\d+(?:\.\d+)?)%?\s+attendance\b", ">="),
        (r"\b(?:at\s+most|<=)\s+(\d+(?:\.\d+)?)%?\s+attendance\b", "<="),
        (r"\b(?:above|greater\s+than|more\s+than|over)\s+(\d+(?:\.\d+)?)%?\s+attendance\b", ">"),
        (r"\b(?:below|less\s+than|under)\s+(\d+(?:\.\d+)?)%?\s+attendance\b", "<"),
    ]

    for pat, op in patterns:
        m = re.search(pat, query_lower)
        if m:
            val = float(m.group(1))
            if not (0.0 <= val <= 100.0):
                logger.warning("Attendance value out of domain [0,100]: %s", val)
                return [
                    {
                        "field": "attendance",
                        "operator": op,
                        "value": val,
                        "validation_error": f"Attendance {val} is outside 0–100",
                    }
                ]
            return [{"field": "attendance", "operator": op, "value": val}]

    return []


# ─────────────────────────────────────────────────────────────────────────────
# Status / probation filter
# ─────────────────────────────────────────────────────────────────────────────


def extract_status_filter(query_lower: str) -> Optional[str]:
    """
    Detects StudentStatus: 'Active' | 'Probation' | 'Graduated'.
    Returns None if no status condition is detected.
    'not on probation' → 'Active' (only supported negation).
    """
    if re.search(r"\bnot\s+on\s+probation\b|\bno\s+probation\b|\bnot\s+probationary\b", query_lower):
        return "Active"
    if re.search(r"\bon\s+probation\b|\bprobation\b|\bprobationary\b", query_lower):
        return "Probation"
    if re.search(r"\bgraduated?\b", query_lower):
        return "Graduated"
    if re.search(r"\bactive\s+students?\b", query_lower):
        return "Active"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Limit / Top-N extraction
# ─────────────────────────────────────────────────────────────────────────────


def extract_limit(query_lower: str) -> Optional[int]:
    """
    Returns positive integer limit, or None if no limit phrase is detected.
    Handles digits and number words.  Rejects zero, negative, non-numeric.

    Patterns handled:
      'top 10', 'first 5', 'show 20', 'limit to 10', 'give me 15',
      'the 10 students', 'top ten', 'find the lowest 5',
      'show the 10 students with highest attendance'
    """
    # Pattern 1: trigger word directly followed by number
    # e.g. "top 10", "first 5", "show 20", "give me 15"
    m = re.search(
        r"\b(?:top|first|limit\s+to|limit|show|give\s+me|fetch|find|get)\s+(\d+)\b",
        query_lower,
    )
    if m:
        val = int(m.group(1))
        if val <= 0:
            logger.warning("Invalid limit (<= 0): %s", val)
            return None
        return val

    # Pattern 2: "the <N> students" — e.g. "show the 10 students with highest"
    m = re.search(r"\bthe\s+(\d+)\s+students?\b", query_lower)
    if m:
        val = int(m.group(1))
        if val > 0:
            return val

    # Pattern 3: standalone digit before a field phrase — e.g. "lowest 5 electronics"
    # Covers "find the lowest 5 electronics students by cgpa"
    m = re.search(r"\b(?:lowest|highest|top|first)\s+(\d+)\b", query_lower)
    if m:
        val = int(m.group(1))
        if val > 0:
            return val

    # Pattern 4: Number words with trigger word
    trigger = {"top", "first", "show", "limit", "fetch", "find", "get"}
    words = query_lower.split()
    for i, w in enumerate(words):
        if w in trigger and i + 1 < len(words):
            nw = NUMBER_WORDS.get(words[i + 1])
            if nw is not None:
                if nw <= 0:
                    logger.warning("Invalid limit from word (<=0): %s", nw)
                    return None
                return nw

    # Pattern 5: Singular phrases for a single top/best/lowest student -> limit = 1
    if re.search(r"\b(?:the\s+)?(?:top|best|highest|lowest|worst|first)\s+student\b", query_lower) or re.search(r"\btopper\b", query_lower):
        return 1

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Sort extraction
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_field(raw: str) -> Optional[str]:
    """Map a user-facing field token to a canonical StudentRecord field name."""
    raw = raw.strip().lower()
    # Direct hit
    if raw in KNOWN_FIELDS:
        return raw
    # Underscore variant
    underscored = raw.replace(" ", "_")
    if underscored in KNOWN_FIELDS:
        return underscored
    # Alias lookup (spaces and underscores)
    return FIELD_ALIASES.get(raw) or FIELD_ALIASES.get(raw.replace("_", " "))


_SORT_FIELD_PAT = r"(cgpa|gpa|attendance|backlogs?|semester)"


def extract_sort(query_lower: str) -> Optional[dict]:
    """
    Returns {"field": str, "direction": "asc"|"desc"} or None.

    Priority (first match wins):
    1. Explicit "sort/order by <field> [asc|desc]"
    2. "highest/best/maximum <field>" → desc
    3. "lowest/worst/minimum <field>" → asc
    4. "<field> descending/ascending"
    5. "descending/ascending <field>"
    6. "top N students by <field>" → desc
    7. "top [N] students" (no field) → cgpa desc  (documented default)
    """
    dir_map = {
        "ascending": "asc",
        "asc": "asc",
        "descending": "desc",
        "desc": "desc",
    }

    # 0. "lowest N ... by field" → field asc  (must check before generic sort-by)
    m = re.search(
        r"\blowest\s+\d+\s+\w+\s+(?:students?\s+)?by\s+" + _SORT_FIELD_PAT + r"\b",
        query_lower,
    )
    if m:
        field = _resolve_field(m.group(1))
        if field and field in SORTABLE_FIELDS:
            return {"field": field, "direction": "asc"}

    # 0b. "highest N ... by field" → field desc
    m = re.search(
        r"\bhighest\s+\d+\s+\w+\s+(?:students?\s+)?by\s+" + _SORT_FIELD_PAT + r"\b",
        query_lower,
    )
    if m:
        field = _resolve_field(m.group(1))
        if field and field in SORTABLE_FIELDS:
            return {"field": field, "direction": "desc"}

    # 1. Explicit sort/order by
    m = re.search(
        r"\b(?:sort|order)\s+(?:\w+\s+)*?by\s+" + _SORT_FIELD_PAT + r"\s*(ascending|descending|asc|desc)?\b",
        query_lower,
    )
    if m:
        field = _resolve_field(m.group(1))
        if field and field in SORTABLE_FIELDS:
            raw_dir = m.group(2) or "desc"
            return {"field": field, "direction": dir_map.get(raw_dir, "desc")}

    # 2. highest/best/maximum <field>
    m = re.search(r"\b(?:highest|best|maximum|max)\s+" + _SORT_FIELD_PAT + r"\b", query_lower)
    if m:
        field = _resolve_field(m.group(1))
        if field and field in SORTABLE_FIELDS:
            return {"field": field, "direction": "desc"}

    # 3. lowest/worst/minimum <field>
    m = re.search(r"\b(?:lowest|worst|minimum|min)\s+" + _SORT_FIELD_PAT + r"\b", query_lower)
    if m:
        field = _resolve_field(m.group(1))
        if field and field in SORTABLE_FIELDS:
            return {"field": field, "direction": "asc"}

    # 4. <field> descending/ascending
    m = re.search(_SORT_FIELD_PAT + r"\s+(ascending|descending|asc|desc)\b", query_lower)
    if m:
        field = _resolve_field(m.group(1))
        if field and field in SORTABLE_FIELDS:
            return {"field": field, "direction": dir_map.get(m.group(2), "desc")}

    # 5. descending/ascending [by] <field>
    m = re.search(r"\b(ascending|descending|asc|desc)\s+(?:by\s+)?" + _SORT_FIELD_PAT + r"\b", query_lower)
    if m:
        field = _resolve_field(m.group(2))
        if field and field in SORTABLE_FIELDS:
            return {"field": field, "direction": dir_map.get(m.group(1), "desc")}

    # 5b. "based on [the] <field>" / "ranked by [the] <field>" / "according to <field>"
    m = re.search(r"\b(?:based\s+on(?:\s+the)?|ranked\s+by(?:\s+the)?|according\s+to(?:\s+the)?|sorted\s+by(?:\s+the)?)\s+" + _SORT_FIELD_PAT + r"\s*(ascending|descending|asc|desc)?\b", query_lower)
    if m:
        field = _resolve_field(m.group(1))
        if field and field in SORTABLE_FIELDS:
            raw_dir = m.group(2) or "desc"
            return {"field": field, "direction": dir_map.get(raw_dir, "desc")}

    # 6. "top N students by <field>"
    m = re.search(r"\btop\s+(?:\d+\s+)?students?\s+by\s+" + _SORT_FIELD_PAT + r"\b", query_lower)
    if m:
        field = _resolve_field(m.group(1))
        if field and field in SORTABLE_FIELDS:
            return {"field": field, "direction": "desc"}

    # 7. bare "top [N] students" → cgpa desc (documented default)
    if re.search(r"\btop\s+(?:\d+\s+)?students?\b", query_lower):
        return {"field": "cgpa", "direction": "desc"}

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Field selection extraction
# ─────────────────────────────────────────────────────────────────────────────


def extract_fields(query_lower: str) -> list[str]:
    """
    Extracts requested output fields from phrases like:
      'show only name and cgpa'
      'display only student name, department and cgpa'
    Returns [] if no explicit field selection or all fields implied.
    Only returns fields present in KNOWN_FIELDS.
    """
    m = re.search(
        r"\b(?:show\s+only|show\s+just|display\s+only|display\s+just|select\s+only|select\s+just|give\s+me\s+only|columns?|fields?)\s+"
        r"([a-z_\s,]+?)(?:\s+for|\s+of|\s+from|\s+where|\s+with|\s+based\s+on|$)",
        query_lower,
    )
    if not m:
        return []

    raw = m.group(1)
    tokens = re.split(r"[,\s]*\band\b[,\s]*|[,\s]+", raw)
    fields: list[str] = []
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        field = _resolve_field(tok)
        if field and field in KNOWN_FIELDS:
            fields.append(field)

    # Deduplicate, preserving order
    return list(dict.fromkeys(fields))


# ─────────────────────────────────────────────────────────────────────────────
# Vault Contract Mapping Helpers
# ─────────────────────────────────────────────────────────────────────────────

from app.db.schema import get_table_columns


def normalize_field_name(name: str) -> str:
    """Removes spaces, underscores, and hyphens and lowercases for fuzzy normalization."""
    return name.lower().replace(" ", "").replace("_", "").replace("-", "")


def find_matching_column(phrase: str, real_columns: Dict[str, str]) -> Optional[str]:
    """
    Explicit case-insensitive & spacing/underscore tolerant matching.
    Lowercases both the query phrase and real column name before comparing.
    E.g. 'phone number', 'Phone Number', 'phone_number', 'phoneNumber', 'PHONENUMBER'
    all match a real database column named 'phoneNumber'.
    """
    if not phrase or not real_columns:
        return None

    clean_phrase = normalize_field_name(phrase)
    if not clean_phrase:
        return None

    for col in real_columns.keys():
        # Explicit lowercasing comparison step
        if col.lower() == phrase.lower():
            return col
        if normalize_field_name(col) == clean_phrase:
            return col

    return None


def extract_table(query: str, query_lower: str) -> str:
    """
    Extracts target database table name from user query.
    Defaults to 'students' if no specific table is mentioned.
    Normalizes casing and singular/plural variants against known tables:
    ('students', 'courses', 'enrollments', 'history').
    """
    # 1. CREATE TABLE path (preserve exact behavior for dynamic table creation e.g. "bookLoans")
    m_create = re.search(r"\btable\s+(?:called\s+|named\s+)?([a-zA-Z0-9_]+)\b", query, re.IGNORECASE)
    if m_create:
        tbl_candidate = m_create.group(1).strip()
        tbl_cand_lower = tbl_candidate.lower().rstrip("s")
        if tbl_cand_lower not in ("student", "course", "enrollment", "history", "called", "named"):
            return tbl_candidate

    # 2. Known table map for case-insensitive & singular/plural tolerance
    known_map = {
        "student": "students", "students": "students",
        "course": "courses", "courses": "courses",
        "enrollment": "enrollments", "enrollments": "enrollments",
        "history": "history", "histories": "history",
    }

    # 3. Explicit target prepositions (from student, in course, into enrollments, etc.)
    m_target = re.search(r"\b(?:to|from|into|in|on)\s+(?:table\s+)?([a-zA-Z0-9_]+)\b", query, re.IGNORECASE)
    if m_target:
        candidate = m_target.group(1).strip()
        cand_lower = candidate.lower()
        if cand_lower in known_map:
            return known_map[cand_lower]
        dept_shortcodes = {"cse", "cs", "ece", "ec", "mech", "ce", "ds", "aiml", "ai", "ml", "computer", "electronics", "mechanical", "civil", "data", "science", "the", "department", "probation"}
        if cand_lower not in dept_shortcodes:
            if candidate[0].isupper() or any(c.isupper() for c in candidate[1:]):
                return candidate

    # 4. Keyword presence check against query_lower
    if "course" in query_lower:
        return "courses"
    if "enrollment" in query_lower:
        return "enrollments"
    if "history" in query_lower:
        return "history"
    if "student" in query_lower:
        return "students"

    return "students"


def extract_row_id(query: str, query_lower: str, filters: list[dict]) -> Optional[str]:
    """
    Extracts row identifier (e.g. STU-1001, ENR-101, CRS-101, 101) from query or filters.
    """
    for f in filters:
        if isinstance(f, dict) and f.get("field") in ("id", "rowId", "row_id") and f.get("value"):
            return str(f["value"])

    m_id = re.search(r"\b([A-Z]{2,4}-(?:[A-Z]{2,4}-)?\d+)\b", query)
    if m_id:
        return m_id.group(1)

    m_num = re.search(r"\b(?:id|rowId|row_id)\s+([A-Za-z0-9-]+)\b", query, re.IGNORECASE)
    if m_num:
        val = m_num.group(1).strip()
        if val.lower() not in ("with", "has", "is", "where", "cgpa", "in", "from", "on", "a", "the"):
            return val

    if not any(query_lower.startswith(prefix) for prefix in ("add ", "insert ", "create ")):
        m_stu = re.search(r"\b(?:student|course|enrollment)\s+([A-Za-z0-9-]*\d+[A-Za-z0-9-]*)\b", query, re.IGNORECASE)
        if m_stu:
            return m_stu.group(1).strip()

    return None


def extract_data(query: str, query_lower: str, parsed_records: Optional[list], table: str = "students") -> dict:
    """
    Constructs a data dictionary for insert_row / update_row actions using dynamic column discovery.
    Fuzzy-matches query phrasing against live schema columns.
    """
    if parsed_records and isinstance(parsed_records, list) and len(parsed_records) > 0:
        if isinstance(parsed_records[0], dict):
            return dict(parsed_records[0])

    data: dict = {}
    cols = get_table_columns(table)
    if not cols:
        cols = get_table_columns("students")

    # 1. Dynamic extraction for any column present in live schema (newly discovered or standard)
    # E.g. "update phone number for STU-1001 to 9876543210", "bloodGroup is O+"
    for col_name, col_type in cols.items():
        if col_name == "id":
            continue

        # Variations of column phrasing (e.g. "phone number", "phone_number", "phoneNumber")
        phrasings = [
            col_name,
            col_name.lower(),
            re.sub(r"([A-Z])", r" \1", col_name).lower().strip(),
            col_name.replace("_", " ").lower(),
        ]
        phrasings = list(dict.fromkeys(phrasings))

        for phrase in phrasings:
            pattern = (
                r"\b(?:set\s+|update\s+)?" + re.escape(phrase) +
                r"\s+(?:for|to|is|=|\s+)\s*([A-Za-z0-9_+\-@.]+)"
            )
            m = re.search(pattern, query_lower, re.IGNORECASE)
            if m:
                val_str = m.group(1).strip().rstrip(".,;!?")
                if val_str.lower() not in ("for", "to", "is", "where", "students", "student", "courses"):
                    matched_real_col = find_matching_column(phrase, cols) or col_name
                    if col_type in ("numeric", "float", "number", "int", "integer"):
                        try:
                            data[matched_real_col] = float(val_str) if "." in val_str else int(val_str)
                        except ValueError:
                            data[matched_real_col] = val_str
                    else:
                        data[matched_real_col] = val_str
                    break

    # 2. Entity extractions as baseline
    col_name_matched = find_matching_column("name", cols)
    if col_name_matched and col_name_matched not in data:
        m_name = re.search(r"\b(?:student|name)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", query)
        if m_name:
            candidate_name = m_name.group(1).strip()
            if candidate_name.lower() not in ("computer science", "electronics", "mechanical", "civil", "data science", "ai & ml", "top", "with"):
                data[col_name_matched] = candidate_name

    col_dept_matched = find_matching_column("department", cols)
    if col_dept_matched and col_dept_matched not in data:
        dept = extract_department(query_lower)
        if dept:
            data[col_dept_matched] = dept

    col_cgpa_matched = find_matching_column("cgpa", cols)
    if col_cgpa_matched and col_cgpa_matched not in data:
        m_cgpa = re.search(r"\bcgpa\s+(?:to\s+|=?\s*)(\d+(?:\.\d+)?)\b", query_lower)
        if m_cgpa:
            try:
                data[col_cgpa_matched] = float(m_cgpa.group(1))
            except ValueError:
                pass

    col_status_matched = find_matching_column("status", cols)
    if col_status_matched and col_status_matched not in data:
        status = extract_status_filter(query_lower)
        if status:
            data[col_status_matched] = status

    return data


def derive_action(
    operation: str,
    query_lower: str,
    filters: list[dict],
    row_id: Optional[str],
    data: dict,
    parsed_records: Optional[list] = None,
) -> str:
    """
    Derives Vault-compliant action from query semantics and operation classification.
    """
    if re.search(r"\bcreate\s+(?:a\s+)?table\b", query_lower):
        return "create_table"
    if re.search(r"\badd\s+(?:a\s+)?(?:[a-zA-Z0-9_]+\s+)?column\b", query_lower):
        return "add_column"
    if re.search(r"\bdrop\s+(?:a\s+)?column\b", query_lower):
        return "drop_column"

    if operation == "write":
        if any(kw in query_lower for kw in ("delete", "remove")):
            return "delete_row"
        if any(kw in query_lower for kw in ("restore", "revert", "undo")):
            return "restore_row"
        if any(kw in query_lower for kw in ("increase", "decrease", "reduce", "lower", "deduct", "multiply", "bulk")):
            return "bulk_update"
        if row_id or any(kw in query_lower for kw in ("update", "set ", "change")):
            return "update_row"
        return "insert_row"

    if operation == "analytics":
        if any(kw in query_lower for kw in ("how many", "count")):
            return "count_rows"
        if any(kw in query_lower for kw in ("weighted", "weight", "composite")):
            return "weighted_compute"
        return "compute_filter"

    if filters or extract_department(query_lower) or extract_status_filter(query_lower):
        return "filter_rows"

    return "get_all_rows"


def build_params(
    action: str,
    query: str,
    table: str,
    row_id: Optional[str],
    data: dict,
    filters: list[dict],
    sort: Optional[dict],
    limit: Optional[int],
    department: Optional[str] = None,
    status_filter: Optional[str] = None,
    fields: Optional[list[str]] = None,
) -> dict:
    """
    Builds Vault-compliant params payload for structured_intent.
    """
    params: dict = {}

    if action == "create_table":
        cols: dict = {"id": "text"}
        if "student id" in query.lower() or "studentid" in query.lower():
            cols["studentId"] = "text"
        if "book title" in query.lower() or "booktitle" in query.lower() or "title" in query.lower():
            cols["bookTitle"] = "text"
        if "due date" in query.lower() or "duedate" in query.lower() or "date" in query.lower():
            cols["dueDate"] = "timestamptz"
        if len(cols) == 1:
            cols = {"id": "text", "studentId": "text", "courseCode": "text", "grade": "text", "enrolledAt": "timestamptz"}
        params["columns"] = cols

    elif action == "add_column":
        m_col = re.search(r"\badd\s+(?:a\s+)?([a-zA-Z0-9_]+)\s+column\b", query, re.IGNORECASE)
        col_name = m_col.group(1).strip() if m_col else "status"
        if col_name.lower() in ("a", "new", "the"):
            m_col2 = re.search(r"\bcolumn\s+(?:called\s+|named\s+)?([a-zA-Z0-9_]+)\b", query, re.IGNORECASE)
            col_name = m_col2.group(1).strip() if m_col2 else "status"
        params["column_name"] = col_name
        params["column_type"] = "boolean" if col_name.lower() in ("returned", "active", "passed") else "text"

    elif action == "drop_column":
        m_col = re.search(r"\bdrop\s+(?:column\s+)?([a-zA-Z0-9_]+)\b", query, re.IGNORECASE)
        params["column_name"] = m_col.group(1).strip() if m_col else "status"

    elif action in ("insert_row", "update_row"):
        params["data"] = data
        if row_id:
            params["row_id"] = row_id

    elif action in ("delete_row", "restore_row"):
        if row_id:
            params["row_id"] = row_id

    elif action in ("filter_rows", "get_all_rows"):
        all_flts = []
        if department:
            all_flts.append({"field": "department", "op": "eq", "value": department})
        if status_filter:
            all_flts.append({"field": "status", "op": "eq", "value": status_filter})
        for f in filters:
            if "validation_error" not in f:
                all_flts.append(f)
        if all_flts:
            params["filters"] = all_flts
        if sort:
            params["sort"] = sort
        if limit:
            params["limit"] = limit
        if fields:
            params["fields"] = fields

    return params


# ─────────────────────────────────────────────────────────────────────────────
# Analytics hint extraction
# ─────────────────────────────────────────────────────────────────────────────


def extract_analytics_hint(query_lower: str) -> Optional[dict]:
    """
    Extracts analytics parameters for AnalyticsAgent.
    Does NOT compute any value — only identifies what to compute.
    Returns e.g. {"metric": "average", "field": "cgpa"} or None.
    """
    metric_keywords: dict[str, list[str]] = {
        "average": ["average", "avg", "mean"],
        "highest": ["highest", "maximum", "max top"],
        "lowest": ["lowest", "minimum", "min bottom"],
        "count": ["count", "how many", "number of", "total number"],
        "distribution": ["distribution", "breakdown", "spread"],
    }
    field_keywords: dict[str, list[str]] = {
        "cgpa": ["cgpa", "gpa", "grade"],
        "attendance": ["attendance", "attend"],
    }

    detected_metric: Optional[str] = None
    for metric, kws in metric_keywords.items():
        for kw in kws:
            if kw in query_lower:
                detected_metric = metric
                break
        if detected_metric:
            break

    if not detected_metric:
        return None

    detected_field: Optional[str] = None
    for field, kws in field_keywords.items():
        for kw in kws:
            if kw in query_lower:
                detected_field = field
                break
        if detected_field:
            break

    hint: dict = {"metric": detected_metric}
    if detected_field:
        hint["field"] = detected_field
    return hint


# ─────────────────────────────────────────────────────────────────────────────
# Operation detection  (mirrors MotherAgent.classify_intent — not a replacement)
# ─────────────────────────────────────────────────────────────────────────────


def detect_operation(query_lower: str) -> str:
    """
    Returns 'read' | 'analytics' | 'write'.
    Mirrors MotherAgent classification for local structuring only.
    Does NOT replace MotherAgent's classification or Groq.
    """
    write_kw = [
        "update", "delete", "insert", "add", "create", "modify", "set ", "change",
        "remove", "drop", "borrow", "loan", "record", "register", "save",
    ]
    if any(kw in query_lower for kw in write_kw):
        return "write"

    # Ranking/top-N queries are read queries, not statistical analytics
    is_ranking = any(
        rk in query_lower for rk in ("top ", "top-", "highest ", "lowest ", "best ")
    ) and any(
        ent in query_lower for ent in ("student", "students", "record", "records", "cse", "cs", "ece", "mech", "civil")
    ) and not any(
        stat in query_lower for stat in ("average", "avg", "mean", "calculate", "compute", "count", "how many", "distribution")
    )

    if not is_ranking:
        analytics_kw = [
            "average", "avg", "highest", "lowest", "metrics", "percentile",
            "analytics", "distribution", "statistic", "breakdown",
            "calculate", "compute", "how many", "count", "at risk", "at-risk", "risk", "probation",
        ]
        if any(kw in query_lower for kw in analytics_kw):
            return "analytics"

    return "read"


# ─────────────────────────────────────────────────────────────────────────────
# Validation helpers
# ─────────────────────────────────────────────────────────────────────────────


def _has_validation_errors(filters: list[dict]) -> bool:
    return any("validation_error" in f for f in filters)


def _derive_min_cgpa(cgpa_filters: list[dict]) -> Optional[float]:
    """Backward-compat: derive min_cgpa from the first >= or > cgpa condition."""
    for f in cgpa_filters:
        if f.get("operator") in (">=", ">") and "validation_error" not in f:
            return f["value"]
    return None


# ─────────────────────────────────────────────────────────────────────────────
def extract_file_path_from_query(query: str) -> tuple[Optional[str], str]:
    """
    Looks for a supported file path in the query string.
    Returns (extracted_file_path, remaining_query_text).
    Supports absolute/relative paths, quotes, and space-containing paths.
    """
    import os

    # Quoted path pattern (single or double quotes)
    ext_pattern = r"\.(?:xlsx|pdf|png|jpg|jpeg)\b"
    quoted_match = re.search(r'["\']([^"\']+' + ext_pattern + r')["\']', query, re.IGNORECASE)
    if quoted_match:
        path = quoted_match.group(1).strip()
        if os.path.exists(path):
            remaining = query.replace(quoted_match.group(0), "").strip()
            return path, remaining

    # Unquoted path pattern
    words = query.split()
    for i, w in enumerate(words):
        clean_w = w.strip().rstrip('.,;!?')
        if any(clean_w.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            if os.path.exists(clean_w):
                words_copy = list(words)
                words_copy.pop(i)
                remaining = " ".join(words_copy)
                return clean_w, remaining
            
            # Check backwards for spaces in path (e.g., C:\My Documents\data.xlsx)
            for j in range(i):
                candidate = " ".join(words[j:i+1]).strip().rstrip('.,;!?')
                if os.path.exists(candidate):
                    words_copy = list(words)
                    del words_copy[j:i+1]
                    remaining = " ".join(words_copy)
                    return candidate, remaining



    return None, query


# ─────────────────────────────────────────────────────────────────────────────
# Main InputAgent
# ─────────────────────────────────────────────────────────────────────────────


class InputAgent(BaseAgent):
    """
    Translates natural-language user queries into a structured query
    specification for downstream agents.

    Output key: ``structured_intent`` inside AgentResult.result.
    All keys in structured_intent are backward-compatible with existing
    DBAgent and test contracts.
    """

    name = "input"

    def execute(self, task: AgentTask) -> AgentResult:  # noqa: C901
        raw_input: str = task.input_data.get("user_query", "")
        explicit_file_path: str = task.input_data.get("file_path", "")

        logger.info("InputAgent started — task_id=%s", task.task_id)

        # ── Reject empty / whitespace-only input ──
        if not raw_input or not raw_input.strip():
            if not explicit_file_path:
                logger.warning("InputAgent received empty input — task_id=%s", task.task_id)
                return AgentResult(
                    task_id=task.task_id,
                    agent=self.name,
                    status="failed",
                    error="Empty or whitespace-only query received.",
                )

        # ── Detect or retrieve file path ──
        parsed_records: Optional[list] = None
        source_type: str = "text"
        file_path = None
        remaining_query = raw_input

        if explicit_file_path:
            file_path = explicit_file_path
        else:
            file_path, remaining_query = extract_file_path_from_query(raw_input)

        if file_path:
            logger.info("InputAgent detected file input: '%s'", file_path)
            source_type = "file"

            # Initialise GroqService only for image files
            import os
            ext = os.path.splitext(file_path)[1].lower()
            groq_svc = (
                GroqService(
                    api_key=os.getenv("INPUT_GROQ_API_KEY"),
                    model=os.getenv("INPUT_GROQ_MODEL", "qwen/qwen3.6-27b"),
                )
                if ext in (".png", ".jpg", ".jpeg")
                else None
            )

            parsed = parse_file(file_path, groq_service=groq_svc, query=remaining_query)

            if parsed is None:
                return AgentResult(
                    task_id=task.task_id,
                    agent=self.name,
                    status="failed",
                    error=f"Failed to parse file: '{file_path}'. Check format and content.",
                )

            if parsed["type"] == "table":
                # File contained a student table → attach records, use remaining query text
                parsed_records = parsed["records"]
                raw_input = remaining_query if remaining_query.strip() else "show all parsed records"
                logger.info(
                    "File parsed as table — %d records attached, remaining query: '%s'",
                    len(parsed_records),
                    raw_input,
                )
            else:
                # File contained a NL query → use it as the actual query
                file_query = parsed["query"]
                raw_input = f"{file_query} {remaining_query}".strip()
                logger.info(
                    "File parsed as NL query: '%s'", raw_input[:120]
                )
        else:
            raw_input = remaining_query

        # ── NL pipeline (runs for both text queries and file-derived queries) ──
        query = raw_input
        query_lower = normalize_prompt(query)
        logger.info("InputAgent normalised query: '%s'", query_lower[:200])

        operation = detect_operation(query_lower)

        # ── Safeguard: Align operation with MotherAgent's request_type if passed ──
        mother_request_type = task.input_data.get("request_type") or task.input_data.get("requestType")
        if mother_request_type and isinstance(mother_request_type, str):
            mother_req_lower = mother_request_type.lower()
            if mother_req_lower in ("read", "write", "analytics", "complex") and operation != mother_req_lower:
                target_op = "write" if mother_req_lower == "complex" else mother_req_lower
                logger.warning(
                    "InputAgent operation mismatch — InputAgent classified as '%s', "
                    "but MotherAgent specified request_type='%s'. Aligning operation to '%s'.",
                    operation,
                    mother_request_type,
                    target_op,
                )
                operation = target_op
        department = extract_department(query_lower)
        cgpa_filters = extract_cgpa_filter(query_lower)
        attendance_filters = extract_attendance_filter(query_lower)
        status_filter = extract_status_filter(query_lower)
        sort = extract_sort(query_lower)
        limit = extract_limit(query_lower)
        fields = extract_fields(query_lower)
        analytics_hint = (
            extract_analytics_hint(query_lower) if operation == "analytics" else None
        )

        all_filters = cgpa_filters + attendance_filters

        # ── Ambiguity detection ──
        ambiguous = False
        ambiguity_reason: Optional[str] = None
        if re.search(r"\bbest\s+students?\b", query_lower) and sort is None:
            ambiguous = True
            ambiguity_reason = (
                "'best students' is ambiguous — defaulting to cgpa desc "
                "(no explicit ranking field specified)."
            )
            sort = {"field": "cgpa", "direction": "desc"}
            logger.info("Ambiguous query resolved with default: %s", ambiguity_reason)

        if limit is not None and sort is None:
            sort = {"field": "cgpa", "direction": "desc"}
            logger.info("Default sort applied (cgpa desc) because limit=%s given", limit)

        min_cgpa = _derive_min_cgpa(cgpa_filters)

        # ── Vault Contract Mapping ──
        table = extract_table(query, query_lower)
        row_id = extract_row_id(query, query_lower, all_filters)
        data = extract_data(query, query_lower, parsed_records, table=table)
        action = derive_action(operation, query_lower, all_filters, row_id, data, parsed_records)
        params = build_params(action, query, table, row_id, data, all_filters, sort, limit, department=department, status_filter=status_filter, fields=fields)

        structured_intent: dict = {
            # ── Vault Input Contract Keys ──
            "action": action,
            "table": table,
            "data": data,
            "row_id": row_id,
            "query": query,
            "params": params,

            # ── Core InputAgent Keys ──
            "operation": operation,
            "original_query": (
                file_path if source_type == "file" else query
            ),
            "source_type": source_type,     # "text" | "file"
            "parsed_records": parsed_records,
            "department": department,
            "filters": all_filters,
            "sort": sort,
            "limit": limit,
            "fields": fields if fields else None,
            "status_filter": status_filter,
            "analytics_hint": analytics_hint,
            "ambiguous": ambiguous,
            "ambiguity_reason": ambiguity_reason,
            "intent": "student_update" if operation == "write" else "student_query",
            "min_cgpa": min_cgpa,
        }

        logger.info(
            "InputAgent completed — source=%s operation=%s dept=%s "
            "filters=%s sort=%s limit=%s parsed_records=%s",
            source_type,
            operation,
            department,
            all_filters,
            sort,
            limit,
            len(parsed_records) if parsed_records else None,
        )

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status="completed",
            result={"structured_intent": structured_intent},
        )