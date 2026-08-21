from typing import List, Dict, Any
import logging
from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult
from app.services.student_service import student_service
from app.contracts.students import StudentRecord
from app.agents.vault_planner import vault_llm_plan
from app.agents.vault_executor import execute_plan
from app.db.sql import build_legacy_students_sql


def _format_sql_from_plan(plan: Dict[str, Any]) -> str:
    """Constructs a readable SQL string representation from a structured plan."""
    table = plan.get("table", "students")
    action = plan.get("action", "filter_rows")
    params = plan.get("params", {})

    if action in ("filter_rows", "get_all_rows"):
        fields = params.get("fields")
        fields_str = ", ".join(fields) if (isinstance(fields, list) and fields) else "*"

        filters = params.get("filters", [])
        if not filters and "field" in params:
            filters = [{"field": params["field"], "op": params.get("op", "eq"), "value": params.get("value")}]

        where_clauses = []
        for f in filters:
            field = f.get("field")
            op = str(f.get("op") or f.get("operator") or "eq").lower()
            op_str = "=" if op in ("eq", "==") else (">=" if op in ("gte", ">=") else ("<=" if op in ("lte", "<=") else (">" if op in ("gt", ">") else ("<" if op in ("lt", "<") else ("!=" if op in ("neq", "!=", "<>") else op)))))
            val = f.get("value")
            val_str = f"'{val}'" if isinstance(val, str) else str(val)
            if field and val is not None:
                where_clauses.append(f"{field} {op_str} {val_str}")

        where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        sort = params.get("sort")
        sort_field = params.get("sort_field")
        order_dir = "DESC"
        if isinstance(sort, dict):
            sort_field = sort.get("field", sort_field)
            order_dir = "DESC" if str(sort.get("direction") or sort.get("order") or "desc").lower() in ("desc", "descending") else "ASC"
        elif isinstance(sort, str):
            parts = sort.strip().split()
            if len(parts) >= 2:
                sort_field = parts[0]
                order_dir = "DESC" if parts[1].lower() in ("desc", "descending") else "ASC"
            elif parts and parts[0].lower() in ("asc", "desc"):
                order_dir = "DESC" if parts[0].lower() in ("desc", "descending") else "ASC"
            elif parts:
                sort_field = parts[0]
        elif sort_field:
            order_dir = "DESC" if str(params.get("order", "desc")).lower() in ("desc", "descending") else "ASC"

        sort_str = ""
        if sort_field:
            sec_col = "roll_number" if table == "students" else "id"
            if str(sort_field).lower() not in (sec_col, "rollnumber", "id"):
                sort_str = f" ORDER BY {sort_field} {order_dir}, {sec_col} ASC"
            else:
                sort_str = f" ORDER BY {sort_field} {order_dir}"

        limit = params.get("limit")
        limit_str = f" LIMIT {limit}" if limit is not None and str(limit).strip().lower() not in ("none", "null", "") else ""
        return f"SELECT {fields_str} FROM {table}{where_str}{sort_str}{limit_str};"

    elif action == "insert_row":
        data = params.get("data", {})
        if data:
            cols = list(data.keys())
            val_strs = [f"'{v}'" if isinstance(v, str) else str(v) for v in data.values()]
            return f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(val_strs)});"
        return f"INSERT INTO {table} DEFAULT VALUES;"

    elif action == "update_row":
        row_id = params.get("row_id")
        data = params.get("data", {})
        set_clauses = []
        for k, v in data.items():
            val_str = f"'{v}'" if isinstance(v, str) else str(v)
            set_clauses.append(f"{k} = {val_str}")
        set_str = ", ".join(set_clauses) if set_clauses else "status = status"
        id_col = "roll_number" if (isinstance(row_id, str) and row_id.startswith("21")) else "id"
        where_clause = f" WHERE {id_col} = '{row_id}'" if row_id else ""
        return f"UPDATE {table} SET {set_str}{where_clause};"

    elif action == "bulk_update":
        field = params.get("field", "status")
        op = params.get("operation", "set")
        val = params.get("value")
        val_str = f"'{val}'" if isinstance(val, str) else str(val)

        if op == "add":
            set_expr = f"{field} = {field} + {val_str}"
        elif op == "subtract":
            set_expr = f"{field} = {field} - {val_str}"
        elif op == "multiply":
            set_expr = f"{field} = {field} * {val_str}"
        else:
            set_expr = f"{field} = {val_str}"

        filters = params.get("filters", [])
        where_clauses = []
        for f in filters:
            f_col = f.get("field")
            f_op = f.get("op", "eq")
            op_str = "=" if f_op == "eq" else (">=" if f_op == "gte" else ("<=" if f_op == "lte" else (">" if f_op == "gt" else ("<" if f_op == "lt" else ("!=" if f_op in ("neq", "<>") else f_op)))))
            f_val = f.get("value")
            f_val_str = f"'{f_val}'" if isinstance(f_val, str) else str(f_val)
            if f_col and f_val is not None:
                where_clauses.append(f"{f_col} {op_str} {f_val_str}")
        where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        return f"UPDATE {table} SET {set_expr}{where_str};"

    elif action == "delete_row":
        row_id = params.get("row_id")
        filters = params.get("filters", [])
        if row_id:
            id_col = "roll_number" if (isinstance(row_id, str) and row_id.startswith("21")) else "id"
            return f"DELETE FROM {table} WHERE {id_col} = '{row_id}';"
        elif filters:
            where_clauses = []
            for f in filters:
                f_col = f.get("field")
                f_op = f.get("op", "eq")
                op_str = "=" if f_op == "eq" else (">=" if f_op == "gte" else ("<=" if f_op == "lte" else (">" if f_op == "gt" else ("<" if f_op == "lt" else ("!=" if f_op in ("neq", "<>") else f_op)))))
                f_val = f.get("value")
                f_val_str = f"'{f_val}'" if isinstance(f_val, str) else str(f_val)
                if f_col and f_val is not None:
                    where_clauses.append(f"{f_col} {op_str} {f_val_str}")
            where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            return f"DELETE FROM {table}{where_str};"
        return f"DELETE FROM {table};"

    elif action == "create_table":
        cols = params.get("columns", {})
        col_defs = [f"{col} {ctype.upper()}" for col, ctype in cols.items()]
        return f"CREATE TABLE {table} ({', '.join(col_defs)});"

    elif action == "add_column":
        col_name = params.get("column_name", "new_col")
        col_type = str(params.get("column_type", "TEXT")).upper()
        return f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type};"

    elif action == "drop_column":
        col_name = params.get("column_name", "col")
        return f"ALTER TABLE {table} DROP COLUMN {col_name};"

    elif action == "count_rows":
        return f"SELECT COUNT(*) FROM {table};"

    elif action == "join_query":
        p_tbl = params.get("primary_table", table)
        j_tbl = params.get("join_table", "courses")
        j_on = params.get("join_on", {})
        p_f = j_on.get("primary_field", "department")
        j_f = j_on.get("join_field", "department")
        return f"SELECT * FROM {p_tbl} JOIN {j_tbl} ON {p_tbl}.{p_f} = {j_tbl}.{j_f};"

    return f"SELECT * FROM {table};"


logger = logging.getLogger(__name__)


class DBAgent(BaseAgent):
    name = "db"

    def execute(self, task: AgentTask) -> AgentResult:
        # Check for file-parsed records from InputAgent first
        input_result = task.input_data.get("input", {})
        structured_intent = input_result.get("structured_intent") or task.input_data.get("structured_intent", {})
        parsed_records: list = structured_intent.get("parsed_records") or []

        if parsed_records:
            return self._execute_file_parsed_flow(task, structured_intent, parsed_records)

        # Main Vault DB Agent flow (Supabase live DB via vault_llm_plan and execute_plan)
        query_str = (
            task.input_data.get("user_query")
            or task.input_data.get("query")
            or task.input_data.get("prompt")
            or (input_result.get("raw_query") if isinstance(input_result, dict) else "")
            or ""
        )

        # Legacy backward compatibility check: only if no query text was provided and non-null legacy structured intent fields are present
        is_legacy = not query_str.strip() and "table" not in structured_intent and "table" not in task.input_data and any(
            structured_intent.get(k) is not None for k in ("department", "min_cgpa", "status_filter")
        )
        if is_legacy:
            return self._legacy_dispatch(task, structured_intent)

        plan = vault_llm_plan(task.input_data)
        action = plan.get("action", "")
        table = plan.get("table", "students")
        params = plan.get("params", {})
        confirmed = bool(task.input_data.get("confirmed"))

        # Dangerous / destructive operations safety confirmation check
        is_destructive = (
            action == "drop_column"
            or (action == "delete_row" and (not params.get("row_id") or "filters" in params))
            or (action == "bulk_update" and (params.get("filters") or not params.get("filters")))
        )

        if is_destructive and not confirmed:
            from app.db.generic_mutations import estimate_affected_rows
            affected_count = estimate_affected_rows(table, action, params)
            filters = params.get("filters", [])
            cond_parts = [f"{f.get('field')} {f.get('op')} {f.get('value')}" for f in filters]
            condition_str = " AND ".join(cond_parts) if cond_parts else "ALL RECORDS"
            op_name = action.replace("_row", "")

            sql_repr = _format_sql_from_plan(plan)
            return AgentResult(
                task_id=task.task_id,
                agent=self.name,
                status="completed",
                result={
                    "requires_confirmation": True,
                    "operation": op_name,
                    "target_table": table,
                    "condition": condition_str,
                    "affected_records": affected_count,
                    "message": f"This operation will modify/delete {affected_count} record(s) in '{table}'.",
                    "warning": "Destructive operation requires explicit confirmation.",
                    "sql": sql_repr,
                    "records": [],
                    "count": 0,
                    "plan": plan,
                },
            )

        exec_res = execute_plan(plan)

        if exec_res.get("success"):
            sql_repr = _format_sql_from_plan(plan)

            is_mutation_action = action in (
                "update_row",
                "insert_row",
                "delete_row",
                "bulk_update",
                "create_table",
                "add_column",
                "drop_column",
                "restore_row",
                "revert_row",
            )

            if is_mutation_action:
                # Invalidate schema cache so preview is never stale
                from app.db.schema_registry import invalidate_schema_cache
                invalidate_schema_cache()

                # Ensure in-memory fallback is also synced for live refresh
                if action in ("update_row", "insert_row", "delete_row", "bulk_update") and table == "students":
                    self._sync_in_memory_mutation(action, plan, params)

                # Query the database again to fetch the updated records so preview reflects actual state
                from app.db.generic_queries import generic_get_all
                fresh_records, _, total_count = generic_get_all(table, limit=100)

                # Extract actual rows_updated from exec_res if available
                res_data = exec_res.get("data", {})
                rows_updated = None
                if isinstance(res_data, dict):
                    rows_updated = res_data.get("rows_updated")
                elif action in ("update_row", "insert_row"):
                    rows_updated = 1
                elif action == "delete_row":
                    rows_updated = exec_res.get("rows_deleted", 1)

                if rows_updated is None and action == "bulk_update":
                    rows_updated = total_count

                return AgentResult(
                    task_id=task.task_id,
                    agent=self.name,
                    status="completed",
                    result={
                        "sql": sql_repr,
                        "records": fresh_records,
                        "count": total_count,
                        "rows_updated": rows_updated,
                        "plan": plan,
                        "message": exec_res.get("message"),
                        "requires_confirmation": False,
                        "mutation_status": "success",
                    },
                )

            # Read action (filter_rows, get_all_rows, compute_filter, weighted_compute, join_query, count_rows):
            # Strictly return the scoped records from query execution (do not fetch 100 rows).
            queried_records = exec_res.get("data")
            if not isinstance(queried_records, list):
                queried_records = []

            return AgentResult(
                task_id=task.task_id,
                agent=self.name,
                status="completed",
                result={
                    "sql": sql_repr,
                    "records": queried_records,
                    "count": len(queried_records),
                    "requested_limit": params.get("limit"),
                    "rows_returned": len(queried_records),
                    "operation": "SELECT",
                    "table": table,
                    "rows_updated": None,
                    "plan": plan,
                    "message": exec_res.get("message"),
                    "requires_confirmation": False,
                    "mutation_status": None,
                },
            )

        # If execution was not successful, return error with exact SQL and do NOT fall back to legacy SELECT
        sql_repr = _format_sql_from_plan(plan)
        err_msg = exec_res.get("message", f"Failed executing {action} on {table}")
        if action in ("insert_row", "update_row", "delete_row", "bulk_update", "create_table", "add_column", "drop_column", "error"):
            return AgentResult(
                task_id=task.task_id,
                agent=self.name,
                status="failed",
                error=err_msg,
                result={
                    "sql": sql_repr,
                    "records": [],
                    "count": 0,
                    "rows_updated": 0,
                    "plan": plan,
                    "message": err_msg,
                    "requires_confirmation": False,
                    "mutation_status": "failed",
                },
            )

        # Fallback to legacy dispatch only for read queries with no structured action
        return self._legacy_dispatch(task, structured_intent)

    def _sync_in_memory_mutation(self, action: str, plan: dict, params: dict) -> None:
        try:
            from app.services.student_service import student_service
            students = student_service._fallback_students
            if action == "update_row":
                row_id = params.get("row_id") or params.get("rowId") or params.get("id")
                data = params.get("data", {})
                for idx, s in enumerate(students):
                    if (s.id == row_id or s.roll_number == row_id or 
                        (s.name and row_id and row_id.lower() in s.name.lower())):
                        s_dict = s.model_dump(by_alias=True)
                        s_dict.update(data)
                        students[idx] = StudentRecord.model_validate(s_dict)
                        break
            elif action == "insert_row":
                data = params.get("data", {})
                if data:
                    data.setdefault("id", f"STU-{len(students)+1001}")
                    data.setdefault("rollNumber", f"21CS{len(students)+100:03d}")
                    data.setdefault("department", "Computer Science")
                    data.setdefault("cgpa", 8.0)
                    data.setdefault("status", "Active")
                    students.append(StudentRecord.model_validate(data))
            elif action == "delete_row":
                row_id = params.get("row_id")
                filters = params.get("filters", [])
                if row_id:
                    student_service._fallback_students = [
                        s for s in students if s.id != row_id and s.roll_number != row_id and (not s.name or row_id.lower() not in s.name.lower())
                    ]
                elif filters:
                    filtered = []
                    for s in students:
                        s_dict = s.model_dump(by_alias=True)
                        match = True
                        for f in filters:
                            fld = f.get("field")
                            op = f.get("op", "eq")
                            val = f.get("value")
                            actual = s_dict.get(fld, getattr(s, fld, None))
                            if actual is None:
                                match = False
                                break
                            try:
                                if op == "eq" and str(actual).lower() != str(val).lower():
                                    match = False
                                elif op == "lt" and not (float(actual) < float(val)):
                                    match = False
                                elif op == "lte" and not (float(actual) <= float(val)):
                                    match = False
                                elif op == "gt" and not (float(actual) > float(val)):
                                    match = False
                                elif op == "gte" and not (float(actual) >= float(val)):
                                    match = False
                            except Exception:
                                match = False
                        if not match:
                            filtered.append(s)
                    student_service._fallback_students = filtered
            elif action == "bulk_update":
                field = params.get("field")
                operation = params.get("operation")
                value = params.get("value")
                filters = params.get("filters", [])
                for idx, s in enumerate(students):
                    s_dict = s.model_dump(by_alias=True)
                    match = True
                    for f in filters:
                        fld = f.get("field")
                        op = f.get("op", "eq")
                        val = f.get("value")
                        actual = s_dict.get(fld, getattr(s, fld, None))
                        if actual is None:
                            match = False
                            break
                        if op == "eq" and str(actual).lower() != str(val).lower():
                            match = False
                            break
                    if match and field:
                        curr = float(s_dict.get(field, getattr(s, field, 0.0)))
                        val_num = float(value)
                        if operation == "subtract":
                            new_val = curr - val_num
                        elif operation == "add":
                            new_val = curr + val_num
                        elif operation == "set":
                            new_val = val_num
                        elif operation == "multiply":
                            new_val = curr * val_num
                        else:
                            new_val = curr
                        s_dict[field] = round(new_val, 2)
                        snake_field = "".join(["_" + c.lower() if c.isupper() else c for c in field]).lstrip("_")
                        s_dict[snake_field] = round(new_val, 2)
                        students[idx] = StudentRecord.model_validate(s_dict)
        except Exception as exc:
            logger.debug(f"[DBAgent] _sync_in_memory_mutation ignored: {exc}")


    def _execute_file_parsed_flow(self, task: AgentTask, structured_intent: dict, parsed_records: list) -> AgentResult:
        """File-parsed records filtering flow from InputAgent."""
        logger.info("DBAgent using %d file-parsed records from InputAgent", len(parsed_records))
        dept_filter = structured_intent.get("department")
        status_filter = structured_intent.get("status_filter")
        limit_val: int = structured_intent.get("limit") or 100

        source_students: List[StudentRecord] = []
        for idx, rec in enumerate(parsed_records):
            try:
                rec.setdefault("roll_number", rec.get("id", f"FILE-{idx+1:04d}"))
                rec.setdefault("id", rec.get("roll_number", f"FILE-{idx+1:04d}"))
                rec.setdefault("name", "Unknown")
                rec.setdefault("department", "Computer Science")
                rec.setdefault("cgpa", 0.0)
                rec.setdefault("semester", 1)
                rec.setdefault("attendance", 0.0)
                rec.setdefault("email", f"{rec.get('name', 'unknown').lower().replace(' ', '.')}@campus.edu")
                rec.setdefault("status", "Active")
                rec.setdefault("backlogs", 0)
                source_students.append(StudentRecord.model_validate(rec))
            except Exception as e:
                logger.warning("Skipping invalid parsed record: %s — %s", rec, e)

        unified_filters: list = structured_intent.get("filters") or []
        min_cgpa = structured_intent.get("min_cgpa")
        if not unified_filters and min_cgpa is not None:
            unified_filters = [{"field": "cgpa", "operator": ">=", "value": min_cgpa}]

        sort_spec = structured_intent.get("sort")
        sort_field = "cgpa"
        sort_desc = True
        if sort_spec:
            sort_field = sort_spec.get("field", "cgpa")
            sort_desc = sort_spec.get("direction", "desc") == "desc"

        where_clauses = []
        if dept_filter:
            where_clauses.append(f"department = '{dept_filter}'")
        for f in unified_filters:
            if "validation_error" not in f:
                where_clauses.append(f"{f['field']} {f['operator']} {f['value']}")
        if status_filter:
            where_clauses.append(f"status = '{status_filter}'")

        order_dir = "DESC" if sort_desc else "ASC"
        sql = build_legacy_students_sql(where_clauses, sort_field=sort_field, order_dir=order_dir, limit=limit_val)

        filtered: List[StudentRecord] = []
        for student in source_students:
            if dept_filter and student.department != dept_filter:
                continue
            if status_filter and student.status != status_filter:
                continue
            if not _apply_filters(student, unified_filters):
                continue
            filtered.append(student)

        try:
            filtered.sort(key=lambda s: getattr(s, sort_field, 0) or 0, reverse=sort_desc)
        except Exception:
            filtered.sort(key=lambda s: s.cgpa, reverse=True)

        final_records = filtered[:limit_val]
        validated_records = [
            StudentRecord.model_validate(s.model_dump()).model_dump(by_alias=True)
            for s in final_records
        ]

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status="completed",
            result={
                "sql": sql,
                "records": validated_records,
                "count": len(validated_records),
            },
        )

    def _legacy_dispatch(self, task: AgentTask, structured_intent: dict) -> AgentResult:
        """Legacy query dispatch supporting structured_intent filters."""
        dept_filter = structured_intent.get("department")
        status_filter = structured_intent.get("status_filter")
        min_cgpa = structured_intent.get("min_cgpa")
        limit = structured_intent.get("limit", 100)

        unified_filters: list = structured_intent.get("filters") or []
        if not unified_filters and min_cgpa is not None:
            unified_filters = [{"field": "cgpa", "operator": ">=", "value": min_cgpa}]

        where_clauses = []
        if dept_filter:
            where_clauses.append(f"department = '{dept_filter}'")
        for f in unified_filters:
            if "validation_error" not in f:
                where_clauses.append(f"{f['field']} {f['operator']} {f['value']}")
        if status_filter:
            where_clauses.append(f"status = '{status_filter}'")

        sql = build_legacy_students_sql(where_clauses, sort_field="cgpa", order_dir="DESC", limit=limit)

        all_students = student_service.get_students()
        filtered: List[StudentRecord] = []

        for student in all_students:
            if dept_filter and student.department != dept_filter:
                continue
            if status_filter and student.status != status_filter:
                continue
            if min_cgpa is not None and student.cgpa < min_cgpa:
                continue
            if not _apply_filters(student, unified_filters):
                continue
            filtered.append(student)

        sort_spec = structured_intent.get("sort")
        sort_field = "cgpa"
        sort_desc = True
        if sort_spec:
            sort_field = sort_spec.get("field", "cgpa")
            sort_desc = sort_spec.get("direction", "desc") == "desc"

        try:
            filtered.sort(key=lambda s: getattr(s, sort_field, 0) or 0, reverse=sort_desc)
        except Exception:
            filtered.sort(key=lambda s: s.cgpa, reverse=True)

        final_records = filtered[:limit]

        validated_records = [
            StudentRecord.model_validate(s.model_dump()).model_dump(by_alias=True)
            for s in final_records
        ]

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status="completed",
            result={
                "sql": sql,
                "records": validated_records,
                "count": len(validated_records),
            },
        )


def _apply_filters(student: StudentRecord, filters: list) -> bool:
    """Apply unified filter conditions. Returns True if student passes ALL filters."""
    for f in filters:
        if "validation_error" in f:
            continue
        field = f.get("field")
        op = f.get("operator")
        value = f.get("value")

        if field is None or op is None or value is None:
            continue

        student_val = getattr(student, field, None)
        if student_val is None:
            return False

        try:
            sv = float(student_val)
            v = float(value)
            if op == ">":
                if not (sv > v):
                    return False
            elif op == ">=":
                if not (sv >= v):
                    return False
            elif op == "<":
                if not (sv < v):
                    return False
            elif op == "<=":
                if not (sv <= v):
                    return False
            elif op == "=":
                if not (sv == v):
                    return False
        except (TypeError, ValueError):
            return False

    return True