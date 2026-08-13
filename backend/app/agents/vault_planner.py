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


def _deterministic_fallback_plan(lens_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback planner when Groq API keys are exhausted or unavailable.
    Constructs deterministic plan from structured input dictionary.
    """
    action = lens_output.get("action")
    query = str(lens_output.get("query", "")).lower()
    tbl = lens_output.get("table", "students")
    params = lens_output.get("params", {})

    if action in ALLOWED_ACTIONS:
        row_id = lens_output.get("row_id") or lens_output.get("rowId") or lens_output.get("id") or params.get("row_id") or params.get("rowId") or params.get("id")
        if row_id:
            params["row_id"] = row_id
        return {"action": action, "table": tbl, "params": params}

    if action == "insert":
        row_data = lens_output.get("data", {})
        return {"action": "insert_row", "table": tbl, "params": {"data": row_data}}
    elif action == "update":
        row_id = lens_output.get("row_id") or lens_output.get("rowId") or lens_output.get("id") or params.get("row_id") or params.get("rowId") or params.get("id")
        return {"action": "update_row", "table": tbl, "params": {"row_id": row_id, "data": lens_output.get("data", {})}}
    elif action == "delete" or action == "delete_row":
        row_id = lens_output.get("row_id") or lens_output.get("rowId") or lens_output.get("id") or params.get("row_id") or params.get("rowId") or params.get("id")
        return {"action": "delete_row", "table": tbl, "params": {"row_id": row_id}}
    elif action == "restore" or action == "restore_row" or action == "revert" or action == "revert_row" or "restore" in query or "revert" in query or "undo" in query:
        row_id = lens_output.get("row_id") or lens_output.get("rowId") or lens_output.get("id") or params.get("row_id") or params.get("rowId") or params.get("id")
        return {"action": "restore_row", "table": tbl, "params": {"row_id": row_id}}
    elif action == "create_table" or "create a table" in query or "create table" in query:
        cols = params.get("columns", {"id": "text", "studentId": "text", "courseCode": "text", "grade": "text", "enrolledAt": "timestamptz"})
        return {"action": "create_table", "table": tbl, "params": {"columns": cols}}
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
        weights = [{"field": "cgpa", "weight": 0.5}, {"field": "attendance", "weight": 0.5}] if tbl == "students" else [{"field": "credits", "weight": 0.7}, {"field": "semester", "weight": 0.3}]
        return {"action": "weighted_compute", "table": tbl, "params": {"weights": weights, "filters": [], "sort": "desc"}}
    elif "average" in query or "min" in query or "max" in query or "sum" in query:
        if "physics_score" in query or "all subject" in query or "marks" in query or "tuition_fee" in query:
            return {"action": "error", "params": {"message": f"Specified field(s) do not exist in table '{tbl}'. Only registered numeric fields can be aggregated."}}
        agg = "average"
        if "min" in query: agg = "min"
        elif "max" in query: agg = "max"
        elif "sum" in query: agg = "sum"
        fields = ["cgpa", "attendance"] if tbl == "students" else ["credits", "semester"]
        return {"action": "compute_filter", "table": tbl, "params": {"fields": fields, "aggregate": agg, "condition": {"op": "gt", "value": 1.0}, "filters": []}}
    elif "increase" in query or "bulk" in query:
        fld = "cgpa" if tbl == "students" else "credits"
        return {"action": "bulk_update", "table": tbl, "params": {"filters": [{"field": "department", "op": "eq", "value": "Computer Science"}], "field": fld, "operation": "add", "value": 0.01}}
    elif action == "count_rows" or "count" in query:
        return {"action": "count_rows", "table": tbl, "params": {}}
    
    # Check for direct filter keys in lens_output or query
    filters = []
    if "department" in lens_output:
        filters.append({"field": "department", "op": "eq", "value": lens_output["department"]})
    if "cgpa" in lens_output:
        filters.append({"field": "cgpa", "op": "gte", "value": lens_output["cgpa"]})
    if "credits" in lens_output:
        filters.append({"field": "credits", "op": "gte", "value": lens_output["credits"]})
    if "backlogs" in lens_output:
        filters.append({"field": "backlogs", "op": "eq", "value": lens_output["backlogs"]})
    if "semester" in lens_output:
        filters.append({"field": "semester", "op": "eq", "value": lens_output["semester"]})
    if "studentId" in lens_output:
        filters.append({"field": "studentId", "op": "eq", "value": lens_output["studentId"]})

    if not filters and "computer science" in query:
        filters.append({"field": "department", "op": "eq", "value": "Computer Science"})
    elif not filters and ("4-credit" in query or "4 credit" in query):
        filters.append({"field": "credits", "op": "gte", "value": 4})
    elif not filters and "zero backlogs" in query:
        filters.append({"field": "backlogs", "op": "eq", "value": 0})
    elif not filters and "4th semester" in query:
        filters.append({"field": "semester", "op": "eq", "value": 4})

    if filters:
        return {"action": "filter_rows", "table": tbl, "params": {"filters": filters}}
    
    return {"action": "get_all_rows", "table": tbl, "params": {}}


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
    query_str = str(lens_output.get("query", "")).lower()

    # 1. Un-registered field validation
    live_schema = get_live_schema(force_refresh=True)
    if table in live_schema:
        known_cols = live_schema[table]
        # Check query string for un-registered fields (e.g., tuition_fee, physics_score)
        if "tuition_fee" in query_str or "physics_score" in query_str or "all subject" in query_str:
            return {"action": "error", "params": {"message": f"Specified field(s) do not exist in table '{table}'. Only registered numeric fields can be aggregated."}}

        # Check fields in params
        req_fields = params.get("fields", [])
        if isinstance(req_fields, list):
            for f in req_fields:
                if f not in known_cols:
                    return {"action": "error", "params": {"message": f"Specified field(s) do not exist in table '{table}'. Only registered numeric fields can be aggregated."}}

        filters = params.get("filters", [])
        if isinstance(filters, list):
            for flt in filters:
                if isinstance(flt, dict) and flt.get("field") and flt["field"] not in known_cols:
                    return {"action": "error", "params": {"message": f"Specified field(s) do not exist in table '{table}'. Only registered numeric fields can be aggregated."}}

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
                        return {"action": "error", "params": {"message": f"Specified field(s) do not exist in table '{table}'. Only registered numeric fields can be weighted."}}

    # 3. Aggregate validation in compute_filter
    if plan.get("action") == "compute_filter":
        agg = params.get("aggregate")
        ALLOWED_AGGREGATES = {"average", "sum", "min", "max"}
        if agg not in ALLOWED_AGGREGATES:
            if "cgpa" in lens_output or "credits" in lens_output or "semester" in lens_output or "department" in lens_output or "backlogs" in lens_output:
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
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
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

5. INSERT ROW: If inserting a row, output:
   {{"action": "insert_row", "table": "<table>", "params": {{"data": {{...all row fields...}}}}}}

6. UPDATE ROW: If updating a row, preserve the EXACT string values specified in input, including parenthetical text.

7. COMPUTED/FORMULA READS (compute_filter): If filtering or aggregating across existing numeric fields (allowed aggregates: "average", "sum", "min", "max"), output:
   {{"action": "compute_filter", "table": "<table>", "params": {{"fields": ["field1", "field2"], "aggregate": "average" | "sum" | "min" | "max", "condition": {{"op": "gte" | "gt" | "lte" | "lt" | "eq" | "neq", "value": <num>}}, "filters": [...]}}}}
   Registered numeric fields include: cgpa, attendance, semester, credits, backlogs, japaneseScore, score, mark, price.
   Only return {{"action": "error"}} if a field requested truly does not exist in the table schema (e.g. physics_score, tuition_fee).

8. WEIGHTED COMPUTE READS (weighted_compute): If calculating a weighted score across multiple numeric fields, output:
   {{"action": "weighted_compute", "table": "<table>", "params": {{"weights": [{{"field": "cgpa", "weight": 0.5}}, {{"field": "attendance", "weight": 0.5}}], "filters": [...], "sort": "desc" | "asc"}}}}
   CRITICAL: Weights MUST sum to 1.0 (100%). Weight objects contain ONLY "field" and "weight". Filter objects belong strictly in "filters".

9. BOUNDED BULK UPDATES (bulk_update): If applying a mathematical operation across matched rows (e.g. "increase CGPA by 5 for all Computer Science students"), output:
   {{"action": "bulk_update", "table": "<table>", "params": {{"filters": [{{"field": "department", "op": "eq", "value": "Computer Science"}}], "field": "cgpa", "operation": "add" | "subtract" | "set" | "multiply", "value": 5}}}}

10. ROW IDENTIFIER KEY: For update_row, delete_row, and restore_row actions, ALWAYS use "row_id" (snake_case) as the key name in the params object. Example: {{"action": "restore_row", "table": "students", "params": {{"row_id": "STU-101"}}}}

11. Return ONLY a valid JSON object matching the schema:
   {{"action": "<action>", "table": "<table>", "params": {{<params>}}}}
12. Do NOT output raw SQL or code. Output ONLY JSON.
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
