from typing import Dict, Any, List
from app.db.client import supabase
from app.db.schema_registry import get_known_fields, get_live_schema
from app.db.generic_queries import generic_filter, generic_get_all, compute_filter, generic_weighted_compute, ALLOWED_OPERATORS
from app.db.generic_mutations import (
    generic_insert,
    generic_update,
    generic_delete,
    generic_restore,
    create_table,
    add_column,
    drop_column,
    bulk_update,
)

ALLOWED_ACTIONS = {
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
}


def execute_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes a structured database query plan returned by vault_llm_plan.
    Re-validates action, table, and params against live schema before execution.
    Returns consistent response shape: {"success": bool, "data": ..., "message": ...}.
    """
    try:
        action = plan.get("action")
        if not action:
            return {"success": False, "data": None, "message": "Plan is missing 'action' field."}

        if action == "error":
            error_msg = plan.get("params", {}).get("message", "Query planner generated error.")
            return {"success": False, "data": None, "message": error_msg}

        if action not in ALLOWED_ACTIONS:
            return {
                "success": False,
                "data": None,
                "message": f"Invalid action '{action}'. Allowed actions: {sorted(list(ALLOWED_ACTIONS))}",
            }

        table = plan.get("table")
        if not table:
            return {"success": False, "data": None, "message": "Plan is missing 'table' field."}

        params = plan.get("params", {})

        # DDL Action 1: CREATE TABLE
        if action == "create_table":
            columns = params.get("columns", {})
            res = create_table(table, columns)
            return {"success": res.get("success", False), "data": res, "message": res.get("message")}

        # DDL Action 2: ADD COLUMN
        elif action == "add_column":
            col_name = params.get("column_name")
            col_type = params.get("column_type", "text")
            if not col_name:
                return {"success": False, "data": None, "message": "add_column action requires 'column_name' param."}
            res = add_column(table, col_name, col_type)
            return {"success": res.get("success", False), "data": res, "message": res.get("message")}

        # DDL Action 3: DROP COLUMN
        elif action == "drop_column":
            col_name = params.get("column_name")
            if not col_name:
                return {"success": False, "data": None, "message": "drop_column action requires 'column_name' param."}
            res = drop_column(table, col_name)
            return {"success": res.get("success", False), "data": res, "message": res.get("message")}

        # For data operations, re-validate table exists in live schema
        known_fields = get_known_fields(table)

        if action == "get_all_rows":
            limit = params.get("limit")
            records, truncated, total = generic_get_all(table, limit=limit)
            msg = f"Fetched {len(records)} rows from {table}." if not truncated else f"Fetched {len(records)} rows from {table} (total: {total}, truncated: true)."
            return {"success": True, "data": records, "truncated": truncated, "total": total, "message": msg}

        elif action == "filter_rows":
            limit = params.get("limit")
            filters = params.get("filters", [])

            # Support single filter param format
            if not filters and "field" in params:
                filters = [{"field": params["field"], "op": params.get("op", "eq"), "value": params.get("value")}]

            if not filters:
                records, truncated, total = generic_get_all(table, limit=limit)
                msg = f"No filters provided; fetched {len(records)} rows from {table}." if not truncated else f"No filters provided; fetched {len(records)} rows from {table} (total: {total}, truncated: true)."
                return {"success": True, "data": records, "truncated": truncated, "total": total, "message": msg}

            query = supabase.table(table).select("*", count="exact")
            for f in filters:
                field = f.get("field")
                op = f.get("op", "eq")
                val = f.get("value")

                if not field or field not in known_fields:
                    return {
                        "success": False,
                        "data": None,
                        "message": f"Field '{field}' is not registered for table '{table}'. Allowed fields: {list(known_fields.keys())}",
                    }

                if op not in ALLOWED_OPERATORS:
                    return {
                        "success": False,
                        "data": None,
                        "message": f"Operator '{op}' is not allowed. Allowed operators: {sorted(list(ALLOWED_OPERATORS))}",
                    }

                filter_func = getattr(query, op)
                query = filter_func(field, val)

            if limit is not None:
                query = query.limit(limit)
                
            res = query.execute()
            records = res.data or []
            total = res.count if res.count is not None else len(records)
            truncated = (total > len(records))
            msg = f"Filtered {len(records)} rows from {table}." if not truncated else f"Filtered {len(records)} rows from {table} (total: {total}, truncated: true)."
            return {"success": True, "data": records, "truncated": truncated, "total": total, "message": msg}

        elif action == "compute_filter":
            fields = params.get("fields", [])
            aggregate = params.get("aggregate", "average")
            condition = params.get("condition", {})
            filters = params.get("filters", [])
            limit = params.get("limit")

            computed_rows, truncated, total = compute_filter(
                table=table,
                fields=fields,
                aggregate=aggregate,
                condition=condition,
                filters=filters,
                limit=limit,
            )
            msg = f"Computed filter returned {len(computed_rows)} matching rows from {table}." if not truncated else f"Computed filter returned {len(computed_rows)} matching rows from {table} (total: {total}, truncated: true)."
            return {
                "success": True,
                "data": computed_rows,
                "truncated": truncated,
                "total": total,
                "message": msg,
            }

        elif action == "weighted_compute":
            weights = params.get("weights", [])
            filters = params.get("filters", [])
            sort = params.get("sort", "desc")
            limit = params.get("limit")

            res = generic_weighted_compute(
                table=table,
                weights=weights,
                filters=filters,
                sort=sort,
                limit=limit,
            )
            return res

        elif action == "insert_row":
            row_data = params.get("data", {})
            orig_id = plan.get("id") or plan.get("row_id") or plan.get("rowId") or (plan.get("data", {}) if isinstance(plan.get("data"), dict) else {}).get("id")
            if orig_id and ("id" not in row_data or not row_data["id"]):
                row_data["id"] = orig_id
            inserted = generic_insert(table, row_data)
            return {"success": True, "data": inserted, "message": f"Inserted row into {table}."}

        elif action == "update_row":
            row_id = params.get("row_id") or params.get("rowId") or params.get("id")
            row_data = params.get("data", {})
            if not row_id:
                return {"success": False, "data": None, "message": "update_row action requires 'row_id' param."}
            updated = generic_update(table, row_id, row_data)
            return {"success": True, "data": updated, "message": f"Updated row {row_id} in {table}."}

        elif action == "bulk_update":
            filters = params.get("filters", [])
            field = params.get("field")
            operation = params.get("operation")
            value = params.get("value")
            max_rows = params.get("max_rows", 50)

            if not field or field not in known_fields:
                return {
                    "success": False,
                    "data": None,
                    "message": f"Field '{field}' is not registered for table '{table}'. Allowed fields: {list(known_fields.keys())}",
                }

            if operation not in {"add", "subtract", "set", "multiply"}:
                return {
                    "success": False,
                    "data": None,
                    "message": f"Operation '{operation}' is not allowed. Allowed operations: ['add', 'subtract', 'set', 'multiply']",
                }

            res = bulk_update(
                table=table,
                filters=filters,
                field=field,
                operation=operation,
                value=value,
                max_rows=max_rows,
            )
            return {
                "success": res.get("success", False),
                "data": res,
                "message": res.get("message"),
            }

        elif action == "delete_row":
            row_id = params.get("row_id") or params.get("rowId") or params.get("id")
            if not row_id:
                return {"success": False, "data": None, "message": "delete_row action requires 'row_id' param."}
            deleted = generic_delete(table, row_id)
            return {"success": True, "data": {"deleted": deleted, "row_id": row_id}, "message": f"Deleted row {row_id} from {table}."}

        elif action == "restore_row" or action == "revert_row":
            row_id = params.get("row_id") or params.get("rowId") or params.get("id")
            if not row_id:
                return {"success": False, "data": None, "message": "restore_row action requires 'row_id' param."}
            res = generic_restore(table, row_id)
            return {"success": True, "data": res, "message": res.get("message")}

        elif action == "count_rows":
            records, truncated, total = generic_get_all(table, limit=None)
            return {"success": True, "data": {"count": total}, "message": f"Counted {total} rows in {table}."}

        return {"success": False, "data": None, "message": f"Unhandled action '{action}'."}

    except Exception as exc:
        return {"success": False, "data": None, "message": str(exc)}
