import os
import time
import logging
from typing import Dict, Any, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_live_schema_cache: Optional[Dict[str, Dict[str, str]]] = None
_cache_timestamp: float = 0.0
CACHE_TTL_SECONDS: float = 120.0  # 2-minute in-memory cache


DEFAULT_SCHEMA: Dict[str, Dict[str, str]] = {
    "students": {
        "id": "text",
        "roll_number": "text",
        "name": "text",
        "department": "text",
        "cgpa": "numeric",
        "semester": "integer",
        "attendance": "numeric",
        "email": "text",
        "status": "text",
        "backlogs": "integer",
        "project_title": "text",
    },
    "courses": {
        "id": "text",
        "course_code": "text",
        "course_name": "text",
        "department": "text",
        "credits": "integer",
    },
}


def get_live_schema(force_refresh: bool = False) -> Dict[str, Dict[str, str]]:
    """
    Queries live database schema (via Supabase OpenAPI specification / information_schema).
    Caches the schema in memory for ~2 minutes (CACHE_TTL_SECONDS).
    Returns a mapping of table_name -> {column_name: column_type}.
    """
    global _live_schema_cache, _cache_timestamp

    now = time.time()
    if not force_refresh and _live_schema_cache is not None and (now - _cache_timestamp < CACHE_TTL_SECONDS):
        return _live_schema_cache

    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "")

    if not supabase_url or not supabase_key or "placeholder" in supabase_url:
        logger.warning("[SchemaRegistry] SUPABASE_URL or SUPABASE_KEY missing or placeholder; using default schema.")
        return DEFAULT_SCHEMA


    try:
        url = f"{supabase_url.rstrip('/')}/rest/v1/"
        headers = {
            "apiKey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
        }
        response = httpx.get(url, headers=headers, timeout=30.0)

        if response.status_code == 200:
            spec = response.json()
            definitions = spec.get("definitions", {})

            schema: Dict[str, Dict[str, str]] = {}
            for table_name, table_def in definitions.items():
                properties = table_def.get("properties", {})
                table_fields: Dict[str, str] = {}
                for col_name, col_props in properties.items():
                    col_type = col_props.get("format") or col_props.get("type") or "text"
                    table_fields[col_name] = col_type
                schema[table_name] = table_fields

            if schema:
                _live_schema_cache = schema
                _cache_timestamp = now
                logger.info(f"[SchemaRegistry] Live schema updated ({len(schema)} tables discovered: {list(schema.keys())})")
                return schema
    except Exception as exc:
        logger.error(f"[SchemaRegistry] Exception fetching live schema: {exc}")

    # Fallback to PostgREST table column inspection if OpenAPI endpoint is slow/unavailable
    if _live_schema_cache:
        return _live_schema_cache

    try:
        from app.db.client import supabase
        schema = {}
        for tbl in ("students", "courses", "enrollments", "history"):
            res = supabase.table(tbl).select("*").limit(1).execute()
            if res.data:
                schema[tbl] = {k: "numeric" if isinstance(v, (int, float)) else "text" for k, v in res.data[0].items()}
            else:
                schema[tbl] = {"id": "text", "name": "text", "department": "text", "cgpa": "numeric", "status": "text"}
        _live_schema_cache = schema
        _cache_timestamp = now
        return schema
    except Exception:
        return {}


def invalidate_schema_cache() -> None:
    """Invalidates the in-memory schema cache so the next call fetches fresh schema."""
    global _live_schema_cache, _cache_timestamp
    _live_schema_cache = None
    _cache_timestamp = 0.0
    logger.info("[SchemaRegistry] In-memory schema cache invalidated.")


import difflib

# Common domain synonyms and column aliases mapping
COLUMN_SYNONYMS: Dict[str, str] = {
    "leetcode": "leetcode_count",
    "leet_code": "leetcode_count",
    "leetcodecount": "leetcode_count",
    "marks": "cgpa",
    "mark": "cgpa",
    "score": "cgpa",
    "gpa": "cgpa",
    "grade": "cgpa",
    "dept": "department",
    "branch": "department",
    "major": "department",
    "roll": "roll_number",
    "rollno": "roll_number",
    "roll_no": "roll_number",
    "rollnumber": "roll_number",
    "mail": "email",
    "email_id": "email",
    "sem": "semester",
    "backlog": "backlogs",
    "project": "project_title",
    "attendance_percentage": "attendance",
    "attendance_pct": "attendance",
    "leetcode": "leetcode_count",
    "leetcod": "leetcode_count",
    "leet_code": "leetcode_count",
    "coding_score": "leetcode_count",
}



def resolve_column_name(table: str, candidate: str) -> Dict[str, Any]:
    """
    Validates and resolves a candidate column name against the live schema for table.
    Supports exact match, camelCase/snake_case matching, synonym mapping, and fuzzy suggestions.
    Returns: {"valid": bool, "column": Optional[str], "suggestion": Optional[str]}
    """
    try:
        known = get_known_fields(table)
    except Exception:
        known = DEFAULT_SCHEMA.get(table, {})

    cand_clean = candidate.strip()
    cand_lower = cand_clean.lower().replace(" ", "_").replace("-", "_")

    # 1. Exact match in known fields
    if cand_clean in known:
        return {"valid": True, "column": cand_clean, "suggestion": None}

    # 2. Case-insensitive or snake/camel match
    for k in known.keys():
        k_norm = k.lower().replace("_", "")
        if cand_lower.replace("_", "") == k_norm:
            return {"valid": True, "column": k, "suggestion": None}

    # 3. Check known synonyms
    if cand_lower in COLUMN_SYNONYMS:
        target = COLUMN_SYNONYMS[cand_lower]
        for k in known.keys():
            if k.lower() == target.lower() or k.lower().replace("_", "") == target.lower().replace("_", ""):
                return {"valid": False, "column": None, "suggestion": k}
        return {"valid": False, "column": None, "suggestion": target}

    # 4. Fuzzy match using difflib with strict similarity cutoff
    matches = difflib.get_close_matches(cand_clean, list(known.keys()), n=1, cutoff=0.6)
    if matches:
        return {"valid": False, "column": None, "suggestion": matches[0]}

    return {"valid": False, "column": None, "suggestion": None}



def get_known_fields(table: str) -> Dict[str, str]:
    """
    Returns dictionary of fields and types for table from live schema.
    Raises ValueError if table is not found in live schema.
    """
    schema = get_live_schema()
    if table not in schema:
        raise ValueError(
            f"Table '{table}' is not registered in the database schema. "
            f"Available tables: {list(schema.keys())}"
        )
    return schema[table]


def get_database_preview(sample_size: int = 5) -> Dict[str, Any]:
    """
    Provides a live database preview across available tables:
    - Table names
    - Column names & types
    - Real sample records
    - Total row counts
    Never uses permanently stale data.
    """
    schema = get_live_schema(force_refresh=True)
    tables_preview = []

    for tbl, cols in schema.items():
        columns_list = [{"name": c_name, "type": c_type} for c_name, c_type in cols.items()]
        sample_records: list = []
        row_count: int = 0

        # Try fetching real records from Supabase
        try:
            from app.db.client import supabase
            res = supabase.table(tbl).select("*", count="exact").limit(sample_size).execute()
            sample_records = res.data or []
            row_count = res.count if res.count is not None else len(sample_records)
        except Exception:
            pass

        # If Supabase returned nothing or offline, fallback to in-memory student service
        if not sample_records and tbl == "students":
            from app.services.student_service import student_service
            all_students = student_service.get_students()
            row_count = len(all_students)
            sample_records = [s.model_dump(by_alias=True) for s in all_students[:sample_size]]

        tables_preview.append({
            "name": tbl,
            "columns": columns_list,
            "sample_records": sample_records,
            "row_count": row_count,
        })

    return {"tables": tables_preview}

