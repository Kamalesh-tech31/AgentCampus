from typing import List, Dict, Any
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


class DBAgent(BaseAgent):
    name = "db"

    def execute(self, task: AgentTask) -> AgentResult:
        """
        Executes database query task by generating a plan via vault_llm_plan and executing it via execute_plan.
        Falls back to _legacy_dispatch if planning/execution encounters an unhandled error or unconfigured LLM.
        """
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
        return self._legacy_dispatch(task)

    def _legacy_dispatch(self, task: AgentTask) -> AgentResult:
        """Legacy hardcoded query dispatch kept for reference and fallback."""
        input_result = task.input_data.get("input", {})
        structured_intent = input_result.get("structured_intent") or task.input_data.get(
            "structured_intent", {}
        )

        dept_filter = structured_intent.get("department")
        min_cgpa = structured_intent.get("min_cgpa")
        limit = structured_intent.get("limit", 100)

        # Build SQL query representation
        where_clauses = []
        if dept_filter:
            where_clauses.append(f"department = '{dept_filter}'")
        if min_cgpa is not None:
            where_clauses.append(f"cgpa >= {min_cgpa}")

        where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"SELECT * FROM students{where_str} ORDER BY cgpa DESC LIMIT {limit};"

        # Query StudentService database
        all_students = student_service.get_students()
        filtered: List[StudentRecord] = []

        for student in all_students:
            if dept_filter and student.department != dept_filter:
                continue
            if min_cgpa is not None and student.cgpa < min_cgpa:
                continue
            filtered.append(student)

        # Sort and limit
        filtered.sort(key=lambda s: s.cgpa, reverse=True)
        final_records = filtered[:limit]

        # Validate each record through StudentRecord contract
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