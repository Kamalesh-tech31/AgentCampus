from typing import List, Dict, Any
import logging
from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult
from app.services.student_service import student_service
from app.contracts.students import StudentRecord
from app.agents.vault_planner import vault_llm_plan
from app.agents.vault_executor import execute_plan


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

        # Main Vault DB Agent flow (Supabase live DB via vault_llm_plan and execute_plan)
        plan = vault_llm_plan(task.input_data)
        exec_res = execute_plan(plan)

        if exec_res.get("success"):
            data = exec_res.get("data")
            records = data if isinstance(data, list) else ([data] if data else [])
            sql_repr = _format_sql_from_plan(plan)

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
                },
            )

        # Fallback to legacy dispatch if dynamic execution was not successful
        return self._legacy_dispatch(task, structured_intent)

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

        where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        order_dir = "DESC" if sort_desc else "ASC"
        sql = f"SELECT * FROM students{where_str} ORDER BY {sort_field} {order_dir} LIMIT {limit_val};"

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
        """Legacy hardcoded query dispatch kept for reference and fallback."""
        dept_filter = structured_intent.get("department")
        min_cgpa = structured_intent.get("min_cgpa")
        limit = structured_intent.get("limit", 100)

        where_clauses = []
        if dept_filter:
            where_clauses.append(f"department = '{dept_filter}'")
        if min_cgpa is not None:
            where_clauses.append(f"cgpa >= {min_cgpa}")

        where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"SELECT * FROM students{where_str} ORDER BY cgpa DESC LIMIT {limit};"

        all_students = student_service.get_students()
        filtered: List[StudentRecord] = []

        for student in all_students:
            if dept_filter and student.department != dept_filter:
                continue
            if min_cgpa is not None and student.cgpa < min_cgpa:
                continue
            filtered.append(student)

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