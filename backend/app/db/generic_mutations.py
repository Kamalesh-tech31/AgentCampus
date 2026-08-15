import re
import uuid
import json
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from app.db.client import supabase
from app.db.schema_registry import get_known_fields, get_live_schema

logger = logging.getLogger(__name__)

# Strict Regexes for allowed DDL operations:
# 1. CREATE TABLE "table" ("col" type, ...)
# 2. ALTER TABLE "table" ADD COLUMN "col" type
# 3. ALTER TABLE "table" DROP COLUMN "col"
CREATE_TABLE_REGEX = re.compile(
    r'^\s*CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+public\."([a-zA-Z0-9_]+)"\s*\((.*)\)\s*;?\s*$',
    re.IGNORECASE | re.DOTALL,
)

ADD_COLUMN_REGEX = re.compile(
    r'^\s*ALTER\s+TABLE\s+public\."([a-zA-Z0-9_]+)"\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+"([a-zA-Z0-9_]+)"\s+([a-zA-Z0-9_\(\)\s]+)\s*;?\s*$',
    re.IGNORECASE,
)

DROP_COLUMN_REGEX = re.compile(
    r'^\s*ALTER\s+TABLE\s+public\."([a-zA-Z0-9_]+)"\s+DROP\s+COLUMN\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?"([a-zA-Z0-9_]+)"\s*;?\s*$',
    re.IGNORECASE,
)


def _quote_ident(ident: str) -> str:
    """Safely quote double-quoted PostgreSQL identifiers."""
    clean = ident.replace('"', "")
    return f'"{clean}"'


def _validate_ddl_statement(sql: str) -> None:
    """
    Hardened validation enforcing that DDL statements match ONLY allowed regex patterns
    (CREATE TABLE, ALTER TABLE ... ADD COLUMN, ALTER TABLE ... DROP COLUMN)
    and strictly reject DROP TABLE, TRUNCATE, and DELETE FROM statements.
    """
    sql_clean = sql.strip()
    sql_upper = sql_clean.upper()

    # Rejection of forbidden statements
    if "DROP TABLE" in sql_upper:
        raise ValueError("Security Rejection: DROP TABLE statements are strictly forbidden.")
    if "TRUNCATE" in sql_upper:
        raise ValueError("Security Rejection: TRUNCATE statements are strictly forbidden.")
    if "DELETE FROM" in sql_upper:
        raise ValueError("Security Rejection: DELETE FROM SQL statements are strictly forbidden via DDL pathway.")

    m_create = CREATE_TABLE_REGEX.match(sql_clean)
    m_add = ADD_COLUMN_REGEX.match(sql_clean)
    m_drop = DROP_COLUMN_REGEX.match(sql_clean)

    if not (m_create or m_add or m_drop):
        raise ValueError(
            f"Security Rejection: DDL statement does not match allowed CREATE TABLE, ADD COLUMN, or DROP COLUMN patterns. Input: {sql_clean[:100]}"
        )


def _execute_ddl(sql: str) -> Dict[str, Any]:
    """Executes a validated DDL statement via Supabase RPC exec_sql pathway."""
    _validate_ddl_statement(sql)
    res = supabase.rpc("exec_sql", {"sql_query": sql}).execute()

    # Notify PostgREST to reload schema cache & invalidate local in-memory cache
    try:
        supabase.rpc("exec_sql", {"sql_query": "NOTIFY pgrst, 'reload schema';"}).execute()
    except Exception:
        pass

    time.sleep(0.5)
    from app.db.schema_registry import invalidate_schema_cache
    invalidate_schema_cache()

    # Empirical state verification for DDL execution
    res_data = res.data or {}
    if isinstance(res_data, dict) and res_data.get("success") is False:
        err_msg = res_data.get("error", "Unknown DB error")
        raise RuntimeError(f"Database DDL Execution Error: {err_msg}")

    return {"success": True, "sql": sql, "response": res_data}


def _validate_payload_keys(table: str, data: Dict[str, Any]) -> None:
    """Validates that all keys in data payload exist in the registered schema for table."""
    known = get_known_fields(table)
    invalid_keys = [k for k in data.keys() if k not in known]
    if invalid_keys:
        raise ValueError(
            f"Unknown fields for table '{table}': {invalid_keys}. "
            f"Allowed fields: {list(known.keys())}"
        )


def create_table(table_name: str, columns: Dict[str, str]) -> Dict[str, Any]:
    """
    Creates a new dynamic table with double-quoted identifiers:
    CREATE TABLE IF NOT EXISTS public."tableName" ("id" text PRIMARY KEY, "col" type, ...)
    """
    if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
        raise ValueError(f"Invalid table name identifier: '{table_name}'")

    col_defs = ['"id" text PRIMARY KEY']
    for col_name, col_type in columns.items():
        if col_name.lower() == "id":
            continue
        if not re.match(r"^[a-zA-Z0-9_]+$", col_name):
            raise ValueError(f"Invalid column name identifier: '{col_name}'")

        pg_type = "text"
        ct = col_type.lower()
        if ct in ("numeric", "float", "number"):
            pg_type = "numeric"
        elif ct in ("int", "integer"):
            pg_type = "int4"
        elif ct in ("boolean", "bool"):
            pg_type = "boolean"
        elif ct in ("timestamp", "timestamptz", "date"):
            pg_type = "timestamptz"

        col_defs.append(f"{_quote_ident(col_name)} {pg_type}")

    sql = f'CREATE TABLE IF NOT EXISTS public.{_quote_ident(table_name)} ({", ".join(col_defs)});'
    return _execute_ddl(sql)


def add_column(table_name: str, column_name: str, column_type: str) -> Dict[str, Any]:
    """
    Adds a new column to an existing table:
    ALTER TABLE public."tableName" ADD COLUMN IF NOT EXISTS "columnName" type;
    """
    if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
        raise ValueError(f"Invalid table name identifier: '{table_name}'")
    if not re.match(r"^[a-zA-Z0-9_]+$", column_name):
        raise ValueError(f"Invalid column name identifier: '{column_name}'")

    pg_type = "text"
    ct = column_type.lower()
    if ct in ("numeric", "float", "number"):
        pg_type = "numeric"
    elif ct in ("int", "integer"):
        pg_type = "int4"
    elif ct in ("boolean", "bool"):
        pg_type = "boolean"
    elif ct in ("timestamp", "timestamptz", "date"):
        pg_type = "timestamptz"

    sql = f'ALTER TABLE public.{_quote_ident(table_name)} ADD COLUMN IF NOT EXISTS {_quote_ident(column_name)} {pg_type};'
    return _execute_ddl(sql)


def drop_column(table_name: str, column_name: str) -> Dict[str, Any]:
    """
    Drops a column from an existing table:
    ALTER TABLE public."tableName" DROP COLUMN IF NOT EXISTS "columnName";
    """
    if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
        raise ValueError(f"Invalid table name identifier: '{table_name}'")
    if not re.match(r"^[a-zA-Z0-9_]+$", column_name):
        raise ValueError(f"Invalid column name identifier: '{column_name}'")

    sql = f'ALTER TABLE public.{_quote_ident(table_name)} DROP COLUMN IF EXISTS {_quote_ident(column_name)};'
    result = _execute_ddl(sql)

    # Allow brief pause for PostgREST schema cache reload before empirical check
    time.sleep(0.3)
    live_schema = get_live_schema(force_refresh=True)
    if table_name in live_schema and column_name in live_schema[table_name]:
        raise RuntimeError(
            f"Empirical State Verification Failed: Column '{column_name}' still present in table '{table_name}' after DROP COLUMN execution!"
        )

    return result


def generic_insert(table: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts a row into table:
    1. Retains caller-provided 'id' if present, auto-generating UUID fallback only if missing.
    2. Validates keys against schema.
    3. Executes insert and verifies inserted state in DB.
    """
    record = dict(data)

    # Retain caller-provided 'id' if present; fallback to UUID only if genuinely missing
    if "id" not in record or not record["id"]:
        record["id"] = f"{table[:3].upper()}-{str(uuid.uuid4())[:8]}"

    _validate_payload_keys(table, record)
    response = supabase.table(table).insert(record).execute()
    inserted = response.data[0] if response.data else record

    # Empirical DB state verification
    verify = supabase.table(table).select("*").eq("id", record["id"]).execute()
    if not verify.data:
        raise RuntimeError(f"Insert verification failed: Row '{record['id']}' not found in '{table}' after insert.")

    return inserted


def _resolve_row_id(table: str, row_id: str) -> tuple[str, str]:
    """
    Resolves caller-provided row_id to the exact database column and primary key 'id'.
    Primary path: checks eq("id", row_id). If matched, returns ("id", row_id).
    Secondary fallback path:
      - 'students' table: fallback to eq("rollNumber", row_id), eq("roll_number", row_id), or name match.
      - 'courses' table: fallback to eq("courseCode", row_id), eq("course_code", row_id), or name match.
    Returns (match_column_name, primary_id_val).
    If no match is found, returns ("id", row_id) so caller produces consistent "Row not found" error.
    """
    try:
        res = supabase.table(table).select("id").eq("id", row_id).execute()
        if res.data and len(res.data) > 0:
            return ("id", res.data[0]["id"])
    except Exception:
        pass

    if table.lower() == "students":
        for col in ("rollNumber", "roll_number"):
            try:
                res_fb = supabase.table(table).select("id", col).eq(col, row_id).execute()
                if res_fb.data and len(res_fb.data) > 0:
                    real_id = res_fb.data[0]["id"]
                    return (col, real_id)
            except Exception:
                pass
        try:
            res_name = supabase.table(table).select("id", "name").ilike("name", f"%{row_id}%").execute()
            if res_name.data and len(res_name.data) > 0:
                real_id = res_name.data[0]["id"]
                return ("name", real_id)
        except Exception:
            pass

        # In-memory student service fallback
        try:
            from app.services.student_service import student_service
            for s in student_service.get_students():
                if s.id == row_id:
                    return ("id", s.id)
                if s.roll_number == row_id:
                    return ("rollNumber", s.id)
                if s.name and row_id.lower() in s.name.lower():
                    return ("name", s.id)
        except Exception:
            pass

    elif table.lower() == "courses":
        for col in ("courseCode", "course_code", "course_name", "courseName"):
            try:
                res_fb = supabase.table(table).select("id", col).ilike(col, f"%{row_id}%").execute()
                if res_fb.data and len(res_fb.data) > 0:
                    real_id = res_fb.data[0]["id"]
                    return (col, real_id)
            except Exception:
                pass

    return ("id", row_id)



def generic_update(table: str, row_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates a row in table identified by row_id (or natural key fallback rollNumber / courseCode):
    1. Resolves row_id to primary key id.
    2. Validates keys against schema.
    3. Executes update.
    4. Verifies updated fields empirically in DB.
    """
    match_col, real_id = _resolve_row_id(table, row_id)
    _validate_payload_keys(table, data)
    response = supabase.table(table).update(data).eq("id", real_id).execute()
    updated = response.data[0] if response.data else data

    # Empirical DB state verification
    verify = supabase.table(table).select("*").eq("id", real_id).execute()
    if not verify.data:
        raise RuntimeError(f"Update verification failed: Row '{row_id}' not found in '{table}' after update.")

    v_row = verify.data[0]
    for k, v in data.items():
        v_actual = v_row.get(k)
        if isinstance(v, (float, int)) and isinstance(v_actual, (float, int)):
            if abs(float(v) - float(v_actual)) > 1e-4:
                logger.warning(f"[GenericMutations] DB state mismatch for key {k}: expected {v}, got {v_actual}")
        elif str(v_actual) != str(v):
            logger.warning(f"[GenericMutations] DB state mismatch for key {k}: expected '{v}', got '{v_actual}'")

    return updated


def generic_delete(
    table: str,
    row_id: Optional[str] = None,
    filters: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Deletes row(s) from table:
    - If row_id is provided: resolves row_id and deletes the target row.
    - If filters is provided: applies filters and deletes matching rows.
    Verifies the actual number of rows deleted from Supabase.
    Returns: {"success": bool, "deleted": bool, "rows_deleted": int, "data": List[Dict], "message": str}
    """
    schema = get_known_fields(table)

    if not row_id and not filters:
        raise ValueError(f"Delete operation on table '{table}' requires either 'row_id' or 'filters'.")

    if row_id:
        match_col, real_id = _resolve_row_id(table, row_id)
        # Verify if target row actually exists
        exists_check = supabase.table(table).select("id").eq("id", real_id).execute()
        if not exists_check.data:
            return {
                "success": False,
                "deleted": False,
                "rows_deleted": 0,
                "data": [],
                "message": f"No matching row found to delete in table '{table}' with {match_col}='{row_id}'.",
            }

        res = supabase.table(table).delete(count="exact").eq("id", real_id).execute()
        deleted_rows = res.data or []
        rows_deleted = res.count if res.count is not None else len(deleted_rows)

        if rows_deleted == 0:
            return {
                "success": False,
                "deleted": False,
                "rows_deleted": 0,
                "data": [],
                "message": f"No matching row found to delete in table '{table}' with {match_col}='{row_id}'.",
            }

        # Empirical DB state verification
        verify = supabase.table(table).select("id").eq("id", real_id).execute()
        if verify.data and len(verify.data) > 0:
            raise RuntimeError(f"Delete verification failed: Row '{row_id}' still present in '{table}' after deletion.")

        return {
            "success": True,
            "deleted": True,
            "rows_deleted": rows_deleted,
            "data": deleted_rows,
            "message": f"Successfully deleted {rows_deleted} row(s) from {table}.",
        }

    # Filter-based deletion
    query = supabase.table(table).delete(count="exact")
    allowed_ops = {"eq", "neq", "gt", "gte", "lt", "lte", "like", "ilike", "is_", "in_"}
    for f in filters:
        f_field = f.get("field")
        f_op = f.get("op", "eq")
        f_val = f.get("value")
        if not f_field or f_field not in schema:
            raise ValueError(f"Field '{f_field}' is not registered for table '{table}'.")
        if f_op not in allowed_ops:
            raise ValueError(f"Operator '{f_op}' is not allowed.")
        filter_func = getattr(query, f_op)
        query = filter_func(f_field, f_val)

    res = query.execute()
    deleted_rows = res.data or []
    rows_deleted = res.count if res.count is not None else len(deleted_rows)

    if rows_deleted == 0:
        return {
            "success": False,
            "deleted": False,
            "rows_deleted": 0,
            "data": [],
            "message": f"No matching row(s) found to delete in table '{table}'.",
        }

    return {
        "success": True,
        "deleted": True,
        "rows_deleted": rows_deleted,
        "data": deleted_rows,
        "message": f"Successfully deleted {rows_deleted} row(s) from {table}.",
    }


def estimate_affected_rows(table: str, action: str, params: Dict[str, Any]) -> int:
    """
    Estimates the number of rows that would be affected by a mutation before executing it.
    Used for safety confirmation on destructive or bulk operations.
    """
    if action in ("insert_row", "restore_row", "revert_row"):
        return 1

    row_id = params.get("row_id") or params.get("rowId") or params.get("id")
    if row_id:
        return 1

    filters = params.get("filters", [])
    if not filters and "field" in params:
        filters = [{"field": params["field"], "op": params.get("op", "eq"), "value": params.get("value")}]

    if not filters and action == "delete_row":
        try:
            from app.db.client import supabase
            res = supabase.table(table).select("id", count="exact").execute()
            if res.count is not None:
                return res.count
        except Exception:
            pass
        from app.services.student_service import student_service
        return len(student_service.get_students())

    if filters:
        try:
            from app.db.client import supabase
            query = supabase.table(table).select("id", count="exact")
            for f in filters:
                field = f.get("field")
                op = f.get("op", "eq")
                val = f.get("value")
                if field and hasattr(query, op):
                    query = getattr(query, op)(field, val)
            res = query.execute()
            if res.count is not None and res.count > 0:
                return res.count
        except Exception:
            pass

        # In-memory estimate fallback for students
        if table == "students":
            from app.services.student_service import student_service
            students = student_service.get_students()
            count = 0
            for s in students:
                s_dict = s.model_dump(by_alias=True)
                match = True
                for f in filters:
                    fld = f.get("field")
                    op = f.get("op", "eq")
                    val = f.get("value")
                    actual_val = s_dict.get(fld, getattr(s, fld, None))
                    if actual_val is None:
                        match = False
                        break
                    try:
                        if op == "eq" and str(actual_val).lower() != str(val).lower():
                            match = False
                        elif op == "lt" and not (float(actual_val) < float(val)):
                            match = False
                        elif op == "lte" and not (float(actual_val) <= float(val)):
                            match = False
                        elif op == "gt" and not (float(actual_val) > float(val)):
                            match = False
                        elif op == "gte" and not (float(actual_val) >= float(val)):
                            match = False
                        elif op == "neq" and str(actual_val).lower() == str(val).lower():
                            match = False
                    except (ValueError, TypeError):
                        match = False
                if match:
                    count += 1
            return count

    return 1



def bulk_update(
    table: str,
    filters: List[Dict[str, Any]],
    field: str,
    operation: str,
    value: Any,
    max_rows: int = 50,
) -> Dict[str, Any]:
    """
    Executes a bounded bulk mathematical update across matched rows in table:
    1. Validates field exists and operation is allowed.
    2. Fetches target rows using count='exact'.
    3. Safety guardrail: if matched count exceeds max_rows (default 50), rejects operation.
    4. Computes math in Python and updates each row via generic_update.
    """
    schema = get_known_fields(table)
    if field not in schema:
        raise ValueError(f"Field '{field}' does not exist in table '{table}'.")

    col_type = str(schema[field]).lower()
    is_int_field = col_type in ("int", "integer", "int2", "int4", "int8", "int32", "int64") or field in (
        "credits", "semester", "backlogs", "count", "age"
    )

    query = supabase.table(table).select("*", count="exact")
    for f in filters:
        f_field = f.get("field")
        f_op = f.get("op", "eq")
        f_val = f.get("value")
        if f_field and f_field in schema:
            filter_func = getattr(query, f_op)
            query = filter_func(f_field, f_val)

    response = query.execute()
    rows = response.data or []
    total_matched = response.count if response.count is not None else len(rows)

    if total_matched > max_rows:
        return {
            "success": False,
            "rows_updated": 0,
            "message": f"This would affect {total_matched} rows, which exceeds the safety limit of {max_rows}. Please narrow your filter.",
        }

    updated_count = 0
    for row in rows:
        row_id = row.get("id")
        current_val = row.get(field, 0)
        try:
            current_val = float(current_val)
        except (ValueError, TypeError):
            current_val = 0.0

        num_val = float(value)
        if operation == "add":
            new_val = current_val + num_val
        elif operation == "subtract":
            new_val = current_val - num_val
        elif operation == "set":
            new_val = num_val
        elif operation == "multiply":
            new_val = current_val * num_val
        else:
            raise ValueError(f"Operation '{operation}' is not supported for bulk_update.")

        if is_int_field or (isinstance(new_val, float) and new_val.is_integer()):
            new_val = int(new_val)

        generic_update(table, row_id, {field: new_val})
        updated_count += 1

    return {
        "success": True,
        "rows_updated": updated_count,
        "message": f"Bulk update successfully updated {updated_count} rows in table '{table}'.",
    }


def generic_bulk_insert(table: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Inserts multiple rows into table at once after schema validation."""
    get_known_fields(table)
    if not records:
        return []
    for record in records:
        _validate_payload_keys(table, record)
    response = supabase.table(table).insert(records).execute()
    return response.data or []


def generic_restore(table: str, row_id: str) -> Dict[str, Any]:
    """
    Restores/reverts a row to its pre-update or pre-delete state using the most recent 'oldData' snapshot in history table:
    1. Resolves row_id to primary key id.
    2. Looks up the most recent history entry for row_id on table.
    3. Reads 'oldData' from that history record.
    4. Validates 'oldData' fields against live schema (filters out columns dropped since history entry).
    5. If row exists in live table (pre-update revert), updates row with oldData.
    6. If row does not exist in live table (pre-delete revert), re-inserts oldData back into live table.
    7. Returns dict with success status, restored row data, and clear message.
    """
    match_col, target_id = _resolve_row_id(table, row_id)
    search_ids = list(dict.fromkeys([row_id, target_id]))

    # 1. Fetch most recent history entry for row_id or target_id on table
    history_records = []
    for sid in search_ids:
        try:
            hist_res = (
                supabase.table("history")
                .select("*")
                .eq("rowId", sid)
                .order("timestamp", desc=True)
                .execute()
            )
        except Exception:
            hist_res = (
                supabase.table("history")
                .select("*")
                .eq("rowId", sid)
                .order("id", desc=True)
                .execute()
            )
        if hist_res.data:
            history_records.extend(hist_res.data)
            break

    history_records = hist_res.data or []
    if not history_records:
        raise ValueError(f"No history audit entry found for row '{row_id}' in table '{table}'. Cannot restore.")

    # Filter to matching table if specified
    matching_entries = [
        h for h in history_records
        if str(h.get("originalTable") or h.get("original_table") or "").lower() == table.lower()
    ]
    latest_entry = matching_entries[0] if matching_entries else history_records[0]

    old_data = latest_entry.get("oldData") or latest_entry.get("old_data") or {}

    if isinstance(old_data, str):
        try:
            old_data = json.loads(old_data)
        except Exception:
            pass

    if not isinstance(old_data, dict) or not old_data:
        raise ValueError(f"History entry for row '{row_id}' contains no pre-modification 'oldData' snapshot.")

    # 2. Filter old_data fields against current live schema
    live_schema = get_live_schema(force_refresh=True)
    if table not in live_schema:
        raise ValueError(f"Table '{table}' does not exist in live schema.")

    known_cols = live_schema[table]
    valid_data = {k: v for k, v in old_data.items() if k in known_cols and v is not None}

    if not valid_data:
        raise ValueError(f"No valid schema fields found in history snapshot for table '{table}'.")

    # Ensure row_id is preserved
    valid_data["id"] = row_id

    # 3. Check if row exists in live table
    existing = supabase.table(table).select("id").eq("id", row_id).execute()
    row_exists = bool(existing.data and len(existing.data) > 0)

    if row_exists:
        # Pre-update restore: update existing row
        restored = generic_update(table, row_id, valid_data)
        action_desc = "updated back to pre-modification state"
    else:
        # Pre-delete restore: re-insert deleted row
        restored = generic_insert(table, valid_data)
        action_desc = "re-inserted back to pre-deletion state"

    return {
        "success": True,
        "restored_row": restored,
        "action": "restore",
        "message": f"Successfully restored row '{row_id}' in table '{table}' ({action_desc})."
    }
