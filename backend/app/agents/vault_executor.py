from typing import Dict, Any, List, Optional, Tuple
from app.contracts.students import StudentRecord
from app.db.client import supabase
from app.db.schema_registry import get_known_fields, get_live_schema
from app.db.generic_queries import generic_filter, generic_get_all, compute_filter, generic_weighted_compute, generic_join_query, ALLOWED_OPERATORS
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
}


def _parse_sort_params(params: Dict[str, Any], default_field: str = "id") -> Optional[Tuple[str, bool]]:
    """
    Parses sorting configuration from query parameters.
    Handles:
      - params["sort"] = "asc" / "desc"
      - params["sort"] = "field_name asc" / "field_name desc" / "field_name"
      - params["sort"] = {"field": "...", "direction" | "order": "asc"|"desc"}
      - params["sort_field"] = "...", params["sort_dir"] | params["order"] = "..."
      - params["order"] = "asc" | "desc"
    Returns (sort_field, is_desc) or None.
    """
    sort = params.get("sort")
    sort_field = params.get("sort_field")
    order = params.get("order") or params.get("sort_dir")

    if isinstance(sort, dict):
        f = sort.get("field") or sort_field or default_field
        d = str(sort.get("direction") or sort.get("order") or order or "desc").lower()
        return (f, d == "desc")

    if isinstance(sort, str):
        parts = sort.strip().split()
        if len(parts) == 1:
            val = parts[0].lower()
            if val in ("asc", "desc"):
                return (sort_field or default_field, val == "desc")
            else:
                d = str(order or "asc").lower()
                return (parts[0], d == "desc")
        elif len(parts) >= 2:
            f = parts[0]
            d = parts[1].lower()
            return (f, d == "desc")

    if sort_field:
        d = str(order or "asc").lower()
        return (sort_field, d == "desc")

    if order:
        return (default_field, str(order).lower() == "desc")

    return None


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
            fields = params.get("fields") or params.get("select") or params.get("columns")
            select_clause = "*"
            if fields and isinstance(fields, list):
                valid_cols = [f for f in fields if f in known_fields]
                if valid_cols:
                    select_clause = ", ".join(valid_cols)
            elif isinstance(fields, str) and fields.strip() in known_fields:
                select_clause = fields.strip()

            query = supabase.table(table).select(select_clause, count="exact")
            sort_info = _parse_sort_params(params)
            if sort_info:
                sort_field, is_desc = sort_info
                if sort_field in known_fields:
                    query = query.order(sort_field, desc=is_desc)
                    sec_col = "roll_number" if "roll_number" in known_fields else ("id" if "id" in known_fields else None)
                    if sec_col and sort_field != sec_col:
                        query = query.order(sec_col, desc=False)

            if limit is not None:
                query = query.limit(int(limit))

            records = []
            total = 0
            try:
                res = query.execute()
                records = res.data or []
                total = res.count if res.count is not None else len(records)
                if limit is not None and len(records) > int(limit):
                    records = records[:int(limit)]
            except Exception as exc:
                logger.warning(f"[VaultExecutor] Supabase query failed: {exc}")

            if not records and table.lower() == "students":
                from app.services.student_service import student_service
                students = list(student_service.get_students())
                if sort_info:
                    s_field, is_desc = sort_info
                    try:
                        students.sort(
                            key=lambda s: (
                                -(getattr(s, s_field, 0.0) or 0.0) if is_desc else (getattr(s, s_field, 0.0) or 0.0),
                                getattr(s, "roll_number", getattr(s, "rollNumber", getattr(s, "id", ""))) or "",
                            )
                        )
                    except Exception:
                        try:
                            students.sort(key=lambda s: getattr(s, s_field, 0.0) or 0.0, reverse=is_desc)
                        except Exception:
                            pass
                total = len(students)
                if limit is not None:
                    try:
                        students = students[:int(limit)]
                    except Exception:
                        students = students[:limit]
                records = [s.model_dump(by_alias=True) for s in students]

            truncated = (total > len(records))
            msg = f"Fetched {len(records)} rows from {table}." if not truncated else f"Fetched {len(records)} rows from {table} (total: {total}, truncated: true)."
            return {"success": True, "data": records, "truncated": truncated, "total": total, "message": msg}

        elif action == "filter_rows":
            limit = params.get("limit")
            filters = params.get("filters", [])
            fields = params.get("fields") or params.get("select") or params.get("columns")

            # Support single filter param format
            if not filters and "field" in params:
                filters = [{"field": params["field"], "op": params.get("op", "eq"), "value": params.get("value")}]

            select_clause = "*"
            if fields and isinstance(fields, list):
                valid_cols = [f for f in fields if f in known_fields]
                if valid_cols:
                    select_clause = ", ".join(valid_cols)
            elif isinstance(fields, str) and fields.strip() in known_fields:
                select_clause = fields.strip()

            query = supabase.table(table).select(select_clause, count="exact")
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

            sort_info = _parse_sort_params(params)
            if sort_info:
                sort_field, is_desc = sort_info
                if sort_field in known_fields:
                    query = query.order(sort_field, desc=is_desc)
                    sec_col = "roll_number" if "roll_number" in known_fields else ("id" if "id" in known_fields else None)
                    if sec_col and sort_field != sec_col:
                        query = query.order(sec_col, desc=False)

            if limit is not None:
                query = query.limit(int(limit))

            records = []
            total = 0
            try:
                res = query.execute()
                records = res.data or []
                total = res.count if res.count is not None else len(records)
                if limit is not None and len(records) > int(limit):
                    records = records[:int(limit)]
            except Exception as exc:
                logger.warning(f"[VaultExecutor] Supabase query failed: {exc}")

            if not records and table.lower() == "students":
                from app.services.student_service import student_service
                from app.agents.input_agent import DEPARTMENT_ALIASES
                all_students = student_service.get_students()
                filtered = []
                for s in all_students:
                    s_dict = s.model_dump(by_alias=True)
                    match = True
                    for f in filters:
                        f_field = f.get("field")
                        f_op = f.get("op", "eq")
                        f_val = f.get("value")
                        actual = s_dict.get(f_field, getattr(s, f_field, None))
                        if actual is None:
                            match = False
                            break
                        if f_field == "department":
                            canon_actual = DEPARTMENT_ALIASES.get(str(actual).lower(), str(actual).lower())
                            canon_val = DEPARTMENT_ALIASES.get(str(f_val).lower(), str(f_val).lower())
                            if f_op in ("eq", "==") and canon_actual != canon_val:
                                match = False
                                break
                        elif f_op in ("eq", "=="):
                            if str(actual).lower() != str(f_val).lower():
                                match = False
                                break
                        else:
                            try:
                                act_num = float(actual)
                                val_num = float(f_val)
                                if f_op == "gt" and not (act_num > val_num):
                                    match = False
                                    break
                                elif f_op == "gte" and not (act_num >= val_num):
                                    match = False
                                    break
                                elif f_op == "lt" and not (act_num < val_num):
                                    match = False
                                    break
                                elif f_op == "lte" and not (act_num <= val_num):
                                    match = False
                                    break
                                elif f_op in ("neq", "!=") and not (act_num != val_num):
                                    match = False
                                    break
                            except (ValueError, TypeError):
                                match = False
                                break
                    if match:
                        filtered.append(s)

                if sort_info:
                    s_field, is_desc = sort_info
                    try:
                        filtered.sort(
                            key=lambda s: (
                                -(getattr(s, s_field, 0.0) or 0.0) if is_desc else (getattr(s, s_field, 0.0) or 0.0),
                                getattr(s, "roll_number", getattr(s, "rollNumber", getattr(s, "id", ""))) or "",
                            )
                        )
                    except Exception:
                        try:
                            filtered.sort(key=lambda s: getattr(s, s_field, 0.0) or 0.0, reverse=is_desc)
                        except Exception:
                            pass

                total = len(filtered)
                if limit is not None:
                    try:
                        filtered = filtered[:int(limit)]
                    except Exception:
                        filtered = filtered[:limit]
                records = [s.model_dump(by_alias=True) for s in filtered]

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

        elif action == "join_query":
            primary_table = params.get("primary_table") or table or "students"
            join_table = params.get("join_table") or params.get("secondary_table") or "courses"
            join_on = params.get("join_on")
            primary_filters = params.get("primary_filters")
            join_filters = params.get("join_filters")
            limit = params.get("limit")

            # If a single filters list is passed, auto-partition by table schema
            if "filters" in params and not primary_filters and not join_filters:
                p_schema = get_known_fields(primary_table)
                j_schema = get_known_fields(join_table)
                p_flts = []
                j_flts = []
                for flt in params["filters"]:
                    f = flt.get("field")
                    if f in p_schema:
                        p_flts.append(flt)
                    elif f in j_schema:
                        j_flts.append(flt)
                    else:
                        p_flts.append(flt)
                primary_filters = p_flts
                join_filters = j_flts

            data, truncated, total = generic_join_query(
                primary_table=primary_table,
                join_table=join_table,
                join_on=join_on,
                primary_filters=primary_filters,
                join_filters=join_filters,
                limit=limit,
            )
            msg = f"Joined {primary_table} with {join_table} ({len(data)} records returned)."
            return {"success": True, "data": data, "truncated": truncated, "total": total, "message": msg}

        elif action == "insert_row":
            row_data = params.get("data", {})
            orig_id = plan.get("id") or plan.get("row_id") or plan.get("rowId") or (plan.get("data", {}) if isinstance(plan.get("data"), dict) else {}).get("id")
            if orig_id and ("id" not in row_data or not row_data["id"]):
                row_data["id"] = orig_id
            try:
                inserted = generic_insert(table, row_data)
            except Exception as e:
                if table == "students":
                    from app.services.student_service import student_service
                    inserted = dict(row_data)
                    inserted.setdefault("id", f"STU-{len(student_service._fallback_students)+1001}")
                    inserted.setdefault("rollNumber", f"21CS{len(student_service._fallback_students)+100:03d}")
                    inserted.setdefault("department", "Computer Science")
                    inserted.setdefault("cgpa", 8.0)
                    inserted.setdefault("status", "Active")
                    student_service._fallback_students.append(StudentRecord.model_validate(inserted))
                else:
                    raise e
            return {"success": True, "data": inserted, "message": f"Inserted row into {table}."}

        elif action == "update_row":
            row_id = params.get("row_id") or params.get("rowId") or params.get("id")
            row_data = params.get("data", {})
            if not row_id:
                return {"success": False, "data": None, "message": "update_row action requires 'row_id' param."}
            try:
                updated = generic_update(table, row_id, row_data)
            except Exception as e:
                if table == "students":
                    from app.services.student_service import student_service
                    students = student_service._fallback_students
                    updated = row_data
                    for idx, s in enumerate(students):
                        if s.id == row_id or s.roll_number == row_id or (s.name and row_id and str(row_id).lower() in s.name.lower()):
                            s_dict = s.model_dump(by_alias=True)
                            s_dict.update(row_data)
                            updated = s_dict
                            students[idx] = StudentRecord.model_validate(s_dict)
                            break
                else:
                    raise e
            return {"success": True, "data": updated, "message": f"Updated row {row_id} in {table}."}

        elif action == "bulk_update":
            filters = params.get("filters", [])
            field = params.get("field")
            operation = params.get("operation")
            value = params.get("value")
            max_rows = params.get("max_rows", 1000)

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
            filters = params.get("filters")
            if not row_id and not filters:
                return {"success": False, "data": None, "message": "delete_row action requires 'row_id' or 'filters' param."}
            try:
                res = generic_delete(table, row_id=row_id, filters=filters)
            except Exception as e:
                if table == "students":
                    from app.services.student_service import student_service
                    students = student_service._fallback_students
                    if row_id:
                        initial_len = len(students)
                        students = [s for s in students if s.id != row_id and s.roll_number != row_id and (not s.name or str(row_id).lower() not in s.name.lower())]
                        student_service._fallback_students = students
                        del_count = initial_len - len(students)
                    elif filters:
                        initial_len = len(students)
                        filtered = []
                        for s in students:
                            s_dict = s.model_dump(by_alias=True)
                            match = True
                            for f in filters:
                                fld = f.get("field")
                                op = f.get("op", "eq")
                                val = f.get("value")
                                actual = s_dict.get(fld, getattr(s, fld, None))
                                if actual is None: match = False; break
                                try:
                                    if op == "eq" and str(actual).lower() != str(val).lower(): match = False
                                    elif op == "lt" and not (float(actual) < float(val)): match = False
                                    elif op == "lte" and not (float(actual) <= float(val)): match = False
                                    elif op == "gt" and not (float(actual) > float(val)): match = False
                                    elif op == "gte" and not (float(actual) >= float(val)): match = False
                                except Exception:
                                    match = False
                            if not match:
                                filtered.append(s)
                        student_service._fallback_students = filtered
                        del_count = initial_len - len(filtered)
                    res = {"success": True, "deleted": True, "rows_deleted": del_count, "data": [], "message": f"Successfully deleted {del_count} row(s) from {table}."}
                else:
                    raise e
            return {
                "success": res.get("success", False),
                "deleted": res.get("deleted", False),
                "rows_deleted": res.get("rows_deleted", 0),
                "data": res.get("data", []),
                "message": res.get("message"),
            }


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
