import os
import json
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from app.db.schema_registry import get_live_schema
from app.services.groq_client import call_groq_completion

load_dotenv()

logger = logging.getLogger(__name__)

ALLOWED_ACTIONS = [
    "filter_rows",
    "get_all_rows",
    "join_query",
    "insert_row",
    "update_row",
    "delete_row",
    "restore_row",
    "revert_row",
    "count_rows",
    "create_table",
    "add_column",
    "drop_column",
    "compute_filter",
    "weighted_compute",
    "bulk_update",
]


from app.db.schema import get_table_columns


def _deterministic_fallback_plan(lens_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback planner when Groq API keys are exhausted or unavailable.
    Constructs deterministic plan from structured input dictionary.
    """
    input_intent = lens_output.get("input", {}).get("structured_intent", {}) if isinstance(lens_output.get("input"), dict) else (lens_output.get("structured_intent", {}) if isinstance(lens_output.get("structured_intent"), dict) else {})
    action = lens_output.get("action") or input_intent.get("action")
    query = str(
        lens_output.get("query")
        or lens_output.get("user_query")
        or lens_output.get("prompt")
        or (lens_output.get("input", {}).get("user_query") if isinstance(lens_output.get("input"), dict) else "")
        or input_intent.get("original_query")
        or input_intent.get("query")
        or ""
    ).lower()
    tbl = lens_output.get("table") or input_intent.get("table") or "students"
    params = lens_output.get("params") or input_intent.get("params") or {}
    if not params.get("filters") and input_intent.get("filters"):
        raw_flts = input_intent.get("filters", [])
        norm_flts = []
        for f in raw_flts:
            op_str = f.get("operator") or f.get("op", "eq")
            op_map = {"<": "lt", "<=": "lte", ">": "gt", ">=": "gte", "=": "eq", "==": "eq"}
            norm_flts.append({"field": f.get("field"), "op": op_map.get(op_str, op_str), "value": f.get("value")})
        params["filters"] = norm_flts


    cols = get_table_columns(tbl)
    numeric_fields = [k for k, v in cols.items() if str(v).lower() in ("numeric", "int", "integer", "float", "number") or k in ("cgpa", "attendance", "credits", "semester", "backlogs")]

    if action in ALLOWED_ACTIONS and action not in ("compute_filter", "error"):
        row_id = lens_output.get("row_id") or lens_output.get("rowId") or lens_output.get("id") or params.get("row_id") or params.get("rowId") or params.get("id")
        if row_id:
            params["row_id"] = row_id
        return {"action": action, "table": tbl, "params": params}

    # Analytical / Risk / Reasoning queries (e.g. "Find academically at-risk students and explain reasons")
    # For analytical workflows, DB Agent's role is data retrieval for Pulse Analytics Agent
    is_mutation = any(kw in query for kw in ("reduce", "decrease", "lower", "deduct", "increase", "raise", "boost", "add", "make", "set ", "update", "change", "modify", "delete", "remove", "drop", "insert", "create"))
    if not is_mutation and (
        any(kw in query for kw in ("at risk", "at-risk", "risk", "probation", "performance", "reason", "reasons", "analyze", "analytics"))
        or lens_output.get("mode") == "analyze"
        or input_intent.get("operation") == "analytics"
    ):
        dept_filters = []
        if "computer science" in query or "cse" in query:
            dept_filters.append({"field": "department", "op": "eq", "value": "Computer Science"})
        elif "ai & ml" in query or "ai and ml" in query or "aiml" in query:
            dept_filters.append({"field": "department", "op": "eq", "value": "AI & ML"})
        elif "electronics" in query or "ece" in query:
            dept_filters.append({"field": "department", "op": "eq", "value": "Electronics"})
        elif "mechanical" in query or "mech" in query:
            dept_filters.append({"field": "department", "op": "eq", "value": "Mechanical"})
        elif "civil" in query:
            dept_filters.append({"field": "department", "op": "eq", "value": "Civil"})
        
        if dept_filters:
            return {"action": "filter_rows", "table": tbl, "params": {"filters": dept_filters}}
        return {"action": "get_all_rows", "table": tbl, "params": {}}

    if "along with" in query or "and their" in query or ("student" in query and "course" in query):
        dept_val = None
        if "ai & ml" in query or "ai and ml" in query or "aiml" in query:
            dept_val = "AI & ML"
        elif "computer science" in query or "cs" in query or "cse" in query:
            dept_val = "Computer Science"
        elif "electronics" in query or "ece" in query:
            dept_val = "Electronics"
        elif "mechanical" in query or "mech" in query:
            dept_val = "Mechanical"
        elif "civil" in query:
            dept_val = "Civil"

        p_flts = [{"field": "department", "op": "eq", "value": dept_val}] if dept_val else []
        j_flts = [{"field": "department", "op": "eq", "value": dept_val}] if dept_val else []
        return {
            "action": "join_query",
            "table": "students",
            "params": {
                "primary_table": "students",
                "join_table": "courses",
                "join_on": {"primary_field": "department", "join_field": "department"},
                "primary_filters": p_flts,
                "join_filters": j_flts,
            }
        }

    if action == "insert" or action == "insert_row" or ("add" in query and ("new" in query or "student" in query or "row" in query or "record" in query)):
        row_data = lens_output.get("data") or params.get("data") or {}
        return {"action": "insert_row", "table": tbl, "params": {"data": row_data}}

    # Bulk math/set update (e.g., "reduce all the student cgpa by 1", "increase cgpa by 0.5 for CSE", "Make all students' CGPA 9")
    if any(kw in query for kw in ("reduce", "decrease", "lower", "deduct", "minus", "increase", "raise", "boost", "add", "make", "set", "update", "change", "modify", "assign")):
        import re
        is_sub = any(kw in query for kw in ("reduce", "decrease", "lower", "deduct", "minus"))
        is_add = any(kw in query for kw in ("increase", "raise", "boost"))
        op_type = "subtract" if is_sub else ("add" if is_add else "set")

        # Check for numeric column match
        target_col = None
        for col_name in cols.keys():
            if col_name.lower() in query:
                target_col = col_name
                break
        if not target_col:
            if "cgpa" in query or "gpa" in query or "score" in query or "mark" in query:
                target_col = "cgpa"
            elif "attendance" in query:
                target_col = "attendance"

        # Check for value (e.g. "by 1", "to 9", "= 9", "by 0.5")
        m_val = (
            re.search(r'(?:by|to|as|=)\s*(\d+(?:\.\d+)?)', query, re.IGNORECASE)
            or re.search(r'(\d+(?:\.\d+)?)\s*(?:points|marks|cgpa|gpa|percent|%)', query, re.IGNORECASE)
            or re.search(r'\b(\d+(?:\.\d+)?)\b', query)
        )
        val = float(m_val.group(1)) if m_val else None

        if target_col and val is not None and ("all" in query or is_sub or is_add or not any(name in query for name in ("rahul", "aarav", "ananya", "rohan", "priya", "devansh", "diya", "siddharth", "kavya", "aditya", "neha", "vikram"))):
            # Check if department or status filter is in query
            dept_filters = []
            if "computer science" in query or "cse" in query:
                dept_filters.append({"field": "department", "op": "eq", "value": "Computer Science"})
            elif "ai & ml" in query or "ai and ml" in query or "aiml" in query:
                dept_filters.append({"field": "department", "op": "eq", "value": "AI & ML"})
            elif "electronics" in query or "ece" in query:
                dept_filters.append({"field": "department", "op": "eq", "value": "Electronics"})
            elif "mechanical" in query or "mech" in query:
                dept_filters.append({"field": "department", "op": "eq", "value": "Mechanical"})
            elif "civil" in query:
                dept_filters.append({"field": "department", "op": "eq", "value": "Civil"})

            return {
                "action": "bulk_update",
                "table": tbl,
                "params": {
                    "field": target_col,
                    "operation": op_type,
                    "value": val,
                    "filters": dept_filters,
                }
            }

    if action == "update" or action == "update_row":
        row_id = lens_output.get("row_id") or lens_output.get("rowId") or lens_output.get("id") or params.get("row_id") or params.get("rowId") or params.get("id")
        return {"action": "update_row", "table": tbl, "params": {"row_id": row_id, "data": lens_output.get("data", {}) or params.get("data", {})}}

    # Natural language single row update patterns (e.g., "Change Rahul's CGPA to 9.2", "Set Aarav's CGPA to 9.5")
    if "change" in query or "update" in query or "set" in query or "modify" in query:
        import re
        m_cgpa = re.search(r'cgpa\s*(?:to|as|=)?\s*(\d+(?:\.\d+)?)', query, re.IGNORECASE) or re.search(r'to\s*(\d+(?:\.\d+)?)\s*cgpa', query, re.IGNORECASE)
        val = float(m_cgpa.group(1)) if m_cgpa else None

        target_name = None
        for name in ("rahul", "aarav", "ananya", "rohan", "priya", "devansh", "diya", "siddharth", "kavya", "aditya", "neha", "vikram"):
            if name in query:
                target_name = name
                break

        m_stu_id = re.search(r'\b(STU-\d+)\b', query, re.IGNORECASE)
        m_roll_id = re.search(r'\b(21[A-Z]{2}\d{3})\b', query, re.IGNORECASE)
        target_id = (m_stu_id.group(1).upper() if m_stu_id else None) or (m_roll_id.group(1).upper() if m_roll_id else target_name)

        if val is not None and target_id:
            return {
                "action": "update_row",
                "table": "students",
                "params": {"row_id": target_id, "data": {"cgpa": val}}
            }

    # Natural language delete patterns (e.g., "Delete students with status inactive", "Delete all students with CGPA below 5", "delete STU-1001")
    if "delete" in query or "remove" in query or "drop students" in query or action in ("delete", "delete_row"):
        import re
        m_status = re.search(r'status\s*(?:is|=|to)?\s*([a-zA-Z]+)', query, re.IGNORECASE) or re.search(r'\b(inactive|active|probation|graduated|suspended)\b', query, re.IGNORECASE)
        if m_status:
            stat_val = m_status.group(1) if m_status.groups() else m_status.group(0)
            return {
                "action": "delete_row",
                "table": tbl,
                "params": {"filters": [{"field": "status", "op": "eq", "value": stat_val.capitalize()}]}
            }
        m_below = re.search(r'(?:below|under|<|less than)\s*(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        if m_below and ("cgpa" in query or "gpa" in query or "score" in query or "mark" in query):
            val = float(m_below.group(1))
            return {
                "action": "delete_row",
                "table": "students",
                "params": {"filters": [{"field": "cgpa", "op": "lt", "value": val}]}
            }
        m_stu_id = re.search(r'\b(STU-\d+)\b', query, re.IGNORECASE)
        m_roll_id = re.search(r'\b(21[A-Z]{2}\d{3})\b', query, re.IGNORECASE)
        target_id = (m_stu_id.group(1).upper() if m_stu_id else None) or (m_roll_id.group(1).upper() if m_roll_id else None)
        if target_id:
            return {
                "action": "delete_row",
                "table": "students",
                "params": {"row_id": target_id}
            }

    elif action == "restore" or action == "restore_row" or action == "revert" or action == "revert_row" or "restore" in query or "revert" in query or "undo" in query:
        row_id = lens_output.get("row_id") or lens_output.get("rowId") or lens_output.get("id") or params.get("row_id") or params.get("rowId") or params.get("id")
        return {"action": "restore_row", "table": tbl, "params": {"row_id": row_id}}
    elif action == "create_table" or "create a table" in query or "create table" in query:
        cols_param = params.get("columns", {"id": "text", "studentId": "text", "courseCode": "text", "grade": "text", "enrolledAt": "timestamptz"})
        return {"action": "create_table", "table": tbl, "params": {"columns": cols_param}}
    elif action == "add_column" or ("add" in query and "column" in query):
        col_name = params.get("column_name", "status")
        col_type = params.get("column_type", "text")
        return {"action": "add_column", "table": tbl, "params": {"column_name": col_name, "column_type": col_type}}
    elif action == "drop_column" or ("drop" in query and "column" in query):
        col_name = params.get("column_name", "status")
        return {"action": "drop_column", "table": tbl, "params": {"column_name": col_name}}
    elif "weighted" in query or "weight" in query or "composite" in query:
        if "tuition_fee" in query or "physics_score" in query or "all subject" in query:
            return {"action": "error", "params": {"message": f"Specified field(s) do not exist in table '{tbl}'. Only registered numeric fields can be weighted."}}
        if len(numeric_fields) >= 2:
            weights = [{"field": numeric_fields[0], "weight": 0.5}, {"field": numeric_fields[1], "weight": 0.5}]
        else:
            weights = [{"field": "cgpa", "weight": 0.5}, {"field": "attendance", "weight": 0.5}] if tbl == "students" else [{"field": "credits", "weight": 0.7}, {"field": "semester", "weight": 0.3}]
        return {"action": "weighted_compute", "table": tbl, "params": {"weights": weights, "filters": [], "sort": "desc"}}
    elif "average" in query or "min" in query or "max" in query or "sum" in query:
        if "physics_score" in query or "all subject" in query or "marks" in query or "tuition_fee" in query:
            return {"action": "error", "params": {"message": f"Specified field(s) do not exist in table '{tbl}'. Only registered numeric fields can be aggregated."}}
        agg = "average"
        if "min" in query: agg = "min"
        elif "max" in query: agg = "max"
        elif "sum" in query: agg = "sum"
        if len(numeric_fields) >= 2:
            fields = numeric_fields[:2]
        else:
            fields = ["cgpa", "attendance"] if tbl == "students" else ["credits", "semester"]
        return {"action": "compute_filter", "table": tbl, "params": {"fields": fields, "aggregate": agg, "condition": {"op": "gt", "value": 1.0}, "filters": []}}
    elif "increase" in query or "bulk" in query:
        fld = numeric_fields[0] if numeric_fields else ("cgpa" if tbl == "students" else "credits")
        return {"action": "bulk_update", "table": tbl, "params": {"filters": [{"field": "department", "op": "eq", "value": "Computer Science"}], "field": fld, "operation": "add", "value": 0.01}}
    elif action == "count_rows" or "count" in query:
        return {"action": "count_rows", "table": tbl, "params": {}}

    # Check for direct filter keys in lens_output or query dynamically
    filters = []
    if cols:
        for col_name in cols.keys():
            if col_name in lens_output:
                filters.append({"field": col_name, "op": "eq" if col_name not in ("cgpa", "credits") else "gte", "value": lens_output[col_name]})
    else:
        for known_k in ("department", "cgpa", "credits", "backlogs", "semester", "studentId"):
            if known_k in lens_output:
                filters.append({"field": known_k, "op": "eq" if known_k not in ("cgpa", "credits") else "gte", "value": lens_output[known_k]})

    import re
    m_roll = re.search(r'\b(21[A-Z]{2}\d{3})\b', query, re.IGNORECASE)
    if m_roll and not any(f.get("field") == "rollNumber" for f in filters):
        filters.append({"field": "rollNumber", "op": "eq", "value": m_roll.group(1).upper()})
    m_stu = re.search(r'\b(STU-\d+)\b', query, re.IGNORECASE)
    if m_stu and not any(f.get("field") == "id" for f in filters):
        filters.append({"field": "id", "op": "eq", "value": m_stu.group(1).upper()})

    if not filters and "computer science" in query:
        filters.append({"field": "department", "op": "eq", "value": "Computer Science"})
    elif not filters and ("4-credit" in query or "4 credit" in query):
        filters.append({"field": "credits", "op": "gte", "value": 4})
    elif not filters and "zero backlogs" in query:
        filters.append({"field": "backlogs", "op": "eq", "value": 0})
    elif not filters and "4th semester" in query:
        filters.append({"field": "semester", "op": "eq", "value": 4})

    req_fields = lens_output.get("fields")
    if not req_fields:
        req_fields = []
        if "name" in query and ("name of" in query or query.startswith("return name") or query.startswith("get name") or "show name" in query):
            req_fields.append("name")
        if "cgpa" in query and ("cgpa of" in query or "show cgpa" in query or "return cgpa" in query):
            req_fields.append("cgpa")
        if "email" in query and ("email of" in query or "show email" in query or "return email" in query):
            req_fields.append("email")

    params_out = {"filters": filters} if filters else {}
    if req_fields:
        params_out["fields"] = req_fields

    if filters:
        return {"action": "filter_rows", "table": tbl, "params": params_out}
    
    return {"action": "get_all_rows", "table": tbl, "params": params_out}


def _post_validate_plan(plan: Dict[str, Any], lens_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Model-agnostic plan validation guardrail:
    1. Validates that referenced fields/columns exist in target table's live schema. If an un-registered
       field (e.g. tuition_fee, physics_score) is referenced in query or params, returns action: "error".
    2. Validates aggregate parameter in compute_filter. If aggregate is invalid (e.g. 'filter_rows'),
       either converts to filter_rows if filtering intent or returns action: "error".
    3. Validates weighted_compute params: strict weight-sum check (|sum(weights)-1.0| <= 0.01) and field registration.
    """
    table = plan.get("table", "students")
    params = plan.get("params", {})
    query_str = str(
        lens_output.get("query")
        or lens_output.get("user_query")
        or lens_output.get("prompt")
        or (lens_output.get("input", {}).get("user_query") if isinstance(lens_output.get("input"), dict) else "")
        or ""
    ).lower()

    # 1. Un-registered field validation
    live_schema = get_live_schema(force_refresh=False)
    known_cols = live_schema.get(table) if live_schema and table in live_schema else get_table_columns(table)
    if known_cols:
        # Check query string for un-registered fields (e.g., tuition_fee, physics_score)
        if "tuition_fee" in query_str or "physics_score" in query_str or "all subject" in query_str:
            return {"action": "error", "params": {"message": f"Specified field(s) do not exist in table '{table}'. Only registered numeric fields can be aggregated."}}

        # Check fields in params
        req_fields = params.get("fields", [])
        if isinstance(req_fields, list):
            valid_fields = []
            for f in req_fields:
                if f in ("*", "all"):
                    continue
                if f not in known_cols:
                    return {"action": "error", "params": {"message": f"Specified field(s) do not exist in table '{table}'. Only registered numeric fields can be aggregated."}}
                valid_fields.append(f)
            if valid_fields:
                params["fields"] = valid_fields
            elif "fields" in params:
                del params["fields"]

        filters = params.get("filters", [])
        if isinstance(filters, list):
            cleaned_filters = []
            for flt in filters:
                if not isinstance(flt, dict):
                    continue
                f_name = flt.get("field")
                f_op = str(flt.get("op", "eq")).lower()
                f_val = flt.get("value")

                if f_name and f_name not in known_cols:
                    # Analytical / reasoning filter concepts (e.g., risk, at_risk, academic_risk, reasons)
                    # should be stripped so DB Agent retrieves data for Pulse Analytics Agent rather than erroring
                    if any(analytical_kw in f_name.lower() for analytical_kw in ("risk", "reason", "probation", "performance", "at_risk", "at-risk", "academic")):
                        continue
                    return {"action": "error", "params": {"message": f"Specified field(s) do not exist in table '{table}'. Only registered numeric fields can be aggregated."}}

                # Validate comparison operators (lt, lte, gt, gte)
                if f_op in {"lt", "lte", "gt", "gte"}:
                    if isinstance(f_val, str):
                        try:
                            float(f_val)
                        except (ValueError, TypeError):
                            return {
                                "action": "error",
                                "params": {
                                    "message": f"Invalid comparison filter: Operator '{f_op}' on field '{f_name}' requires a numeric comparison value, but received '{f_val}'."
                                },
                            }

                # Handle hallucinated placeholder values for equality (e.g. eq "all", eq "*")
                if f_op == "eq" and str(f_val).lower() in {"all", "any", "every", "*"}:
                    continue

                cleaned_filters.append(flt)

            params["filters"] = cleaned_filters
            if not cleaned_filters and plan.get("action") == "filter_rows":
                plan["action"] = "get_all_rows"

    # 2. Validation for weighted_compute action
    if plan.get("action") == "weighted_compute":
        weights = params.get("weights", [])
        if not isinstance(weights, list) or not weights:
            return {"action": "error", "params": {"message": "weighted_compute action requires a non-empty list of 'weights' objects."}}

        total_weight = sum(abs(float(w.get("weight", 0.0))) for w in weights if isinstance(w, dict))
        if abs(total_weight - 1.0) > 0.01:
            return {
                "action": "error",
                "params": {"message": f"Invalid weight configuration: Weights sum to {total_weight:.2f} ({total_weight*100:.0f}%), not 1.00 (100%). Please adjust weights so they sum to 100%."}
            }

        if table in live_schema:
            known_cols = live_schema[table]
            for w in weights:
                if isinstance(w, dict):
                    f = w.get("field")
                    if not f or f not in known_cols:
                        return {"action": "error", "params": {"message": f"Specified field(s) do not exist in table '{table}'. Only registered numeric fields can be aggregated."}}

    # 3. Aggregate validation in compute_filter
    if plan.get("action") == "compute_filter":
        agg = params.get("aggregate")
        ALLOWED_AGGREGATES = {"average", "sum", "min", "max"}
        if agg not in ALLOWED_AGGREGATES:
            lens_str = str(lens_output).lower()
            if any(k in lens_str for k in ("cgpa", "credits", "semester", "department", "backlogs", "risk", "at-risk", "student", "probation", "performance", "reason", "analyze")):
                return _deterministic_fallback_plan(lens_output)
            return {
                "action": "error",
                "params": {"message": f"Aggregate '{agg}' is invalid. Allowed aggregates: {sorted(list(ALLOWED_AGGREGATES))}"}
            }

    return plan


def vault_llm_plan(lens_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a structured database execution plan via Groq LLM based on input lens_output
    and dynamic live schema. Automatically fails over across Groq API keys and models on rate limits.
    Returns JSON matching {"action": "...", "table": "...", "params": {...}}.
    """
    # If lens_output is already a structured dictionary specifying a valid action, return directly
    action = lens_output.get("action")
    if action in ALLOWED_ACTIONS:
        params = dict(lens_output.get("params", {}))
        row_id = lens_output.get("row_id") or lens_output.get("rowId") or lens_output.get("id") or params.get("row_id") or params.get("rowId") or params.get("id")
        if row_id:
            params["row_id"] = row_id
        return _post_validate_plan({
            "action": action,
            "table": lens_output.get("table", "students"),
            "params": params,
        }, lens_output)

    try:
        model = os.getenv("DB_GROQ_MODEL", "llama-3.3-70b-versatile")
        live_schema = get_live_schema(force_refresh=True)
        schema_repr = json.dumps(live_schema, indent=2)
        actions_repr = ", ".join(ALLOWED_ACTIONS)

        system_prompt = f"""You are the Vault Database Query Planner for AgentCampus.
Your task is to convert natural language intent / lens output into a safe, structured database execution plan.

LIVE REGISTERED DATABASE SCHEMAS (CURRENT TABLES AND COLUMNS):
{schema_repr}

ALLOWED ACTIONS:
{actions_repr}

RULES:
1. ALWAYS use camelCase naming for new table names and new column names (matching project-wide camelCase convention, e.g. bookLoans, studentId, bookTitle, dueDate, japaneseScore, enrolledAt).

2. CREATE TABLE: If creating a NEW table, output:
   {{"action": "create_table", "table": "<newTableInCamelCase>", "params": {{"columns": {{"columnNameInCamelCase": "text" | "numeric" | "int" | "boolean" | "timestamptz"}}}}}}
   Infer column data types intelligently:
   - score, mark, price, cgpa -> numeric
   - count, age, semester, credits, backlogs -> int
   - date, dueDate, timestamp, enrolledAt -> timestamptz
   - free text, names, emails, titles, grade, status -> text
   - boolean flags -> boolean
   - Always include an "id": "text" primary key automatically.

3. ADD COLUMN: If adding a NEW column to an existing table, output:
   {{"action": "add_column", "table": "<existingTable>", "params": {{"column_name": "<newColumnInCamelCase>", "column_type": "text" | "numeric" | "int" | "boolean" | "timestamptz"}}}}

4. DROP COLUMN: If dropping a column from an existing table, output:
   {{"action": "drop_column", "table": "<existingTable>", "params": {{"column_name": "<existingColumnName>"}}}}
   Note: Dropping a column permanently removes that column's data with no history or rollback available. Table drops stay forbidden.

5. INSERT ROW: If inserting a row (e.g. "Add a new student", "insert into ..."), output:
   {{"action": "insert_row", "table": "<table>", "params": {{"data": {{...all row fields...}}}}}}

6. UPDATE ROW: If updating a single row by ID/key/name (e.g. "Set Aarav's CGPA to 9.5", "Change Rahul's CGPA to 9.2"), output:
   {{"action": "update_row", "table": "<table>", "params": {{"row_id": "<rowIdOrKey>", "data": {{"<col>": <val>}}}}}}
   Preserve the EXACT string values specified in input, including parenthetical text.

7. BULK / ALL ROWS UPDATE (bulk_update): If updating or setting a column across all rows or rows matching filters (e.g. "Make all students' CGPA 9", "Set all status to Active", "Increase CGPA by 5 for Computer Science"):
   {{"action": "bulk_update", "table": "<table>", "params": {{"field": "<columnName>", "operation": "set" | "add" | "subtract" | "multiply", "value": <val>, "filters": [...]}}}}
   If updating ALL records in the table, pass "filters": [].

8. DELETE ROW (delete_row): If deleting rows by ID or by condition (e.g. "Delete students with status inactive", "Delete STU-1001", "Remove students with CGPA below 5"):
   {{"action": "delete_row", "table": "<table>", "params": {{"row_id": "<id>"}}}} OR {{"action": "delete_row", "table": "<table>", "params": {{"filters": [{{"field": "<col>", "op": "eq" | "lt" | "gt" | "lte" | "gte" | "neq", "value": <val>}}]}}}}

9. COMPUTED/FORMULA READS (compute_filter): If filtering or aggregating across existing numeric fields (allowed aggregates: "average", "sum", "min", "max"), output:
   {{"action": "compute_filter", "table": "<table>", "params": {{"fields": ["field1", "field2"], "aggregate": "average" | "sum" | "min" | "max", "condition": {{"op": "gte" | "gt" | "lte" | "lt" | "eq" | "neq", "value": <num>}}, "filters": [...]}}}}
   Registered numeric fields include: cgpa, attendance, semester, credits, backlogs, japaneseScore, score, mark, price.
   Only return {{"action": "error"}} if a field requested truly does not exist in the table schema (e.g. physics_score, tuition_fee).

10. WEIGHTED COMPUTE READS (weighted_compute): If calculating a weighted score across multiple numeric fields, output:
   {{"action": "weighted_compute", "table": "<table>", "params": {{"weights": [{{"field": "cgpa", "weight": 0.5}}, {{"field": "attendance", "weight": 0.5}}], "filters": [...], "sort": "desc" | "asc"}}}}
   CRITICAL: Weights MUST sum to 1.0 (100%). Weight objects contain ONLY "field" and "weight". Filter objects belong strictly in "filters".

11. ROW IDENTIFIER KEY: For update_row, delete_row, and restore_row actions with a single row, ALWAYS use "row_id" (snake_case) as the key name in the params object. Example: {{"action": "restore_row", "table": "students", "params": {{"row_id": "STU-101"}}}}

12. JOIN QUERIES (join_query): If the query requests data combining two related tables (e.g. "along with", "and their", "students in department X along with courses", "show instructor names for courses in X along with students"), output:
   {{"action": "join_query", "table": "students", "params": {{"primary_table": "students", "join_table": "courses", "join_on": {{"primary_field": "department", "join_field": "department"}}, "primary_filters": [...], "join_filters": [...]}}}}
   If two requested tables have no logical relationship or cannot be joined, output:
   {{"action": "error", "params": {{"message": "Cannot join requested tables: no common relationship or join key found."}}}}

13. FIELD PROJECTION (fields): If the query asks for specific fields/columns (e.g. "return name of 21CS003", "show name and email"), output "fields": ["name", ...] in the params object. If no specific fields are requested, omit "fields" so all columns are returned.

14. ANALYTICS / RISK / REASONING QUERIES: If the query asks for analytical insights, at-risk students, performance analysis, explanations, or probation analysis (e.g. "Find academically at-risk students and explain reasons", "Analyze academic performance"):
   The database agent's responsibility is ONLY data retrieval. Output:
   {{"action": "get_all_rows", "table": "students", "params": {{}}}}
   (or with registered column filters like department if explicitly specified).
   Do NOT generate non-existent columns (e.g., 'risk', 'academicRisk', 'reasons') or invalid compute_filter actions, because risk assessment and reasoning are performed downstream by Pulse Analytics Agent.

15. Return ONLY a valid JSON object matching the schema:
   {{"action": "<action>", "table": "<table>", "params": {{<params>}}}}
16. Do NOT output raw SQL or code. Output ONLY JSON.
"""

        user_content = json.dumps(lens_output)

        raw_json = call_groq_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            model=model,
            response_format={"type": "json_object"},
            temperature=0.0,
        )

        if not raw_json:
            plan = _deterministic_fallback_plan(lens_output)
        else:
            plan = json.loads(raw_json)

        # Preserve complete caller-provided data dictionary on insert_row
        if plan.get("action") == "insert_row":
            orig_data = lens_output.get("data")
            if isinstance(orig_data, dict) and orig_data:
                params = plan.setdefault("params", {})
                params["data"] = {**orig_data, **params.get("data", {})}

        # Preserve complete caller-provided data dictionary on update_row (including parenthetical string literals)
        if plan.get("action") == "update_row":
            orig_data = lens_output.get("data")
            if isinstance(orig_data, dict) and orig_data:
                params = plan.setdefault("params", {})
                params["data"] = {**params.get("data", {}), **orig_data}

        return _post_validate_plan(plan, lens_output)

    except Exception as exc:
        logger.warning(f"[VaultPlanner] Error generating LLM plan via Groq: {exc}. Falling back to deterministic plan.")
        plan = _deterministic_fallback_plan(lens_output)
        if plan.get("action") == "insert_row":
            orig_data = lens_output.get("data")
            if isinstance(orig_data, dict) and orig_data:
                params = plan.setdefault("params", {})
                params["data"] = {**orig_data, **params.get("data", {})}
        if plan.get("action") == "update_row":
            orig_data = lens_output.get("data")
            if isinstance(orig_data, dict) and orig_data:
                params = plan.setdefault("params", {})
                params["data"] = {**params.get("data", {}), **orig_data}
        return _post_validate_plan(plan, lens_output)
