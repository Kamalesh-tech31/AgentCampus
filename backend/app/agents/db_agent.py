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
        filters = params.get("filters", [])
        if not filters and "field" in params:
            filters = [{"field": params["field"], "op": params.get("op", "eq"), "value": params.get("value")}]

        where_clauses = []
        for f in filters:
            field = f.get("field")
            op = f.get("op", "eq")
            op_str = "=" if op == "eq" else (">=" if op == "gte" else ("<=" if op == "lte" else op))
            val = f.get("value")
            val_str = f"'{val}'" if isinstance(val, str) else str(val)
            if field and val is not None:
                where_clauses.append(f"{field} {op_str} {val_str}")

        where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        limit = params.get("limit")
        limit_str = f" LIMIT {limit}" if limit else ""
        return f"SELECT * FROM {table}{where_str}{limit_str};"

    elif action == "insert_row":
        data = params.get("data", {})
        return f"INSERT INTO {table} ({', '.join(data.keys())}) VALUES ({', '.join([repr(v) for v in data.values()])});"
    elif action == "update_row":
        row_id = params.get("row_id")
        data = params.get("data", {})
        set_str = ", ".join([f"{k} = {repr(v)}" for k, v in data.items()])
        return f"UPDATE {table} SET {set_str} WHERE id = '{row_id}';"
    elif action == "delete_row":
        row_id = params.get("row_id")
        return f"DELETE FROM {table} WHERE id = '{row_id}';"

    return f"-- Action: {action} on table: {table}"


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

        # Legacy backward compatibility check: if no "table" key AND contains legacy structured intent fields
        is_legacy = "table" not in structured_intent and "table" not in task.input_data and any(
            k in structured_intent for k in ("department", "min_cgpa", "status_filter")
        )
        if is_legacy:
            return self._legacy_dispatch(task, structured_intent)

        # Main Vault DB Agent flow (Supabase live DB via vault_llm_plan and execute_plan)
        plan = vault_llm_plan(task.input_data)
        action = plan.get("action", "")
        table = plan.get("table", "students")
        params = plan.get("params", {})
        confirmed = bool(task.input_data.get("confirmed"))

        # Dangerous / destructive operations safety confirmation check
        is_destructive = (
            action == "drop_column"
            or (action == "delete_row" and (not params.get("row_id") or "filters" in params))
            or (action == "bulk_update" and params.get("filters"))
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
            data = exec_res.get("data")
            records = data if isinstance(data, list) else ([data] if data else [])
            sql_repr = _format_sql_from_plan(plan)

            # Invalidate schema cache so preview is never stale
            from app.db.schema_registry import invalidate_schema_cache
            invalidate_schema_cache()

            # Ensure in-memory fallback is also synced for live refresh
            if action in ("update_row", "insert_row", "delete_row", "bulk_update") and table == "students":
                self._sync_in_memory_mutation(action, plan, params)

            return AgentResult(
                task_id=task.task_id,
                agent=self.name,
                status="completed",
                result={
                    "sql": sql_repr,
                    "records": records,
                    "count": len(records),
                    "plan": plan,
                    "message": exec_res.get("message"),
                    "requires_confirmation": False,
                },
            )

        # Fallback to legacy dispatch if dynamic execution was not successful
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