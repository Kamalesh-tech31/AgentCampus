from typing import List
import logging
from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult
from app.services.student_service import student_service
from app.contracts.students import StudentRecord

logger = logging.getLogger(__name__)


class DBAgent(BaseAgent):
    name = "db"

    def execute(self, task: AgentTask) -> AgentResult:
        # Extract structured intent from InputAgent result or direct task input
        input_result = task.input_data.get("input", {})
        structured_intent = input_result.get("structured_intent") or task.input_data.get(
            "structured_intent", {}
        )

        dept_filter = structured_intent.get("department")
        status_filter = structured_intent.get("status_filter")
        limit_val: int = structured_intent.get("limit") or 100

        # ── Data source: file-parsed records take priority over main DB ──
        parsed_records: list = structured_intent.get("parsed_records") or []
        if parsed_records:
            logger.info(
                "DBAgent using %d file-parsed records from InputAgent", len(parsed_records)
            )
            # Convert raw dicts to StudentRecord objects for uniform filtering
            source_students: List[StudentRecord] = []
            for idx, rec in enumerate(parsed_records):
                try:
                    # Auto-fill required fields that may be missing from file data
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

        else:
            # Fall back to the main in-memory database
            source_students = student_service.get_students()


        # Unified filters list from InputAgent (may include cgpa, attendance, etc.)
        unified_filters: list = structured_intent.get("filters") or []

        # Backward compat: if no unified filters but legacy min_cgpa present, derive one
        min_cgpa = structured_intent.get("min_cgpa")
        if not unified_filters and min_cgpa is not None:
            unified_filters = [{"field": "cgpa", "operator": ">=", "value": min_cgpa}]

        # Sort spec: {"field": "cgpa", "direction": "desc"}
        sort_spec = structured_intent.get("sort")
        sort_field = "cgpa"
        sort_desc = True
        if sort_spec:
            sort_field = sort_spec.get("field", "cgpa")
            sort_desc = sort_spec.get("direction", "desc") == "desc"

        # ── Build SQL representation (for traceability — not executed directly) ──
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
        sql = (
            f"SELECT * FROM students{where_str} "
            f"ORDER BY {sort_field} {order_dir} LIMIT {limit_val};"
        )

        # ── Query the source (file-parsed records OR database) ──
        filtered: List[StudentRecord] = []

        for student in source_students:
            if dept_filter and student.department != dept_filter:
                continue
            if status_filter and student.status != status_filter:
                continue
            if not _apply_filters(student, unified_filters):
                continue
            filtered.append(student)


        # Sort
        try:
            filtered.sort(
                key=lambda s: getattr(s, sort_field, 0) or 0,
                reverse=sort_desc,
            )
        except Exception:
            filtered.sort(key=lambda s: s.cgpa, reverse=True)

        final_records = filtered[:limit_val]

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


def _apply_filters(student: StudentRecord, filters: list) -> bool:
    """Apply unified filter conditions. Returns True if student passes ALL filters."""
    for f in filters:
        if "validation_error" in f:
            continue  # skip invalid conditions — they were already logged by InputAgent
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