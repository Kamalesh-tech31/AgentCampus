"""
InputAgent — translates natural-language user queries into structured query
specifications consumed by downstream agents (DBAgent, AnalyticsAgent).

Pipeline:
  Raw query → normalize → detect operation → extract entities →
  extract filters → extract comparisons → extract sort → extract limit →
  extract fields → extract analytics hints → validate → structured result

Must NOT: query DB · execute SQL · compute analytics · generate final output ·
           replace MotherAgent · make additional LLM calls.
"""
import logging
import re
from typing import Optional

from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult

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
      'give me student name, department and cgpa'
    Returns [] if no explicit field selection or all fields implied.
    Only returns fields present in KNOWN_FIELDS.
    """
    m = re.search(
        r"\b(?:show\s+only|show\s+just|display\s+only|give\s+me|show\s+me)\s+"
        r"([a-z_\s,]+?)(?:\s+for|\s+of|\s+from|\s+where|\s+with|$)",
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
    analytics_kw = [
        "average", "avg", "highest", "lowest", "metrics", "percentile",
        "analytics", "distribution", "statistic", "breakdown",
        "calculate", "compute", "how many", "count",
    ]
    if any(kw in query_lower for kw in analytics_kw):
        return "analytics"

    write_kw = ["update", "delete", "insert", "add student", "modify", "set cgpa", "change"]
    if any(kw in query_lower for kw in write_kw):
        return "write"

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

    def execute(self, task: AgentTask) -> AgentResult:
        query: str = task.input_data.get("user_query", "")

        logger.info("InputAgent started — task_id=%s", task.task_id)

        # ── Reject empty / whitespace-only queries ──
        if not query or not query.strip():
            logger.warning("InputAgent received empty query — task_id=%s", task.task_id)
            return AgentResult(
                task_id=task.task_id,
                agent=self.name,
                status="failed",
                error="Empty or whitespace-only query received.",
            )

        query_lower = normalize_prompt(query)
        logger.info("InputAgent normalised query: '%s'", query_lower[:200])

        # ── Extract all structured components ──
        operation = detect_operation(query_lower)
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

        # Collect all filter conditions
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

        # ── Default sort when a limit is specified (top-N implies ordering) ──
        if limit is not None and sort is None:
            sort = {"field": "cgpa", "direction": "desc"}
            logger.info("Default sort applied (cgpa desc) because limit=%s given", limit)

        # ── Backward-compatible min_cgpa for DBAgent ──
        min_cgpa = _derive_min_cgpa(cgpa_filters)

        # ── Security note ──
        # Raw query is preserved only for traceability in original_query.
        # No raw user text is used as executable SQL.

        structured_intent: dict = {
            # ── Core ──
            "operation": operation,
            "original_query": query,
            # ── Department ──
            "department": department,
            # ── Unified filter list ──
            # Each entry: {"field": str, "operator": str, "value": float}
            # Invalid entries carry a "validation_error" key and are skipped by DBAgent.
            "filters": all_filters,
            # ── Sort spec ──
            "sort": sort,
            # ── Limit ──
            "limit": limit,
            # ── Field selection ──
            "fields": fields if fields else None,
            # ── Status / probation ──
            "status_filter": status_filter,
            # ── Analytics parameters (MotherAgent decides if AnalyticsAgent runs) ──
            "analytics_hint": analytics_hint,
            # ── Ambiguity ──
            "ambiguous": ambiguous,
            "ambiguity_reason": ambiguity_reason,
            # ── Backward-compatibility keys (existing DBAgent + tests depend on these) ──
            "intent": "student_update" if operation == "write" else "student_query",
            "min_cgpa": min_cgpa,
        }

        logger.info(
            "InputAgent completed — operation=%s dept=%s "
            "filters=%s sort=%s limit=%s fields=%s",
            operation,
            department,
            all_filters,
            sort,
            limit,
            fields or None,
        )

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status="completed",
            result={"structured_intent": structured_intent},
        )