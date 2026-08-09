from typing import List, Dict, Any
from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult
from app.services.student_service import student_service
from app.contracts.students import StudentRecord


class DBAgent(BaseAgent):
    name = "db"

    def execute(self, task: AgentTask) -> AgentResult:
        # Extract structured intent from input data (from InputAgent result or direct task input)
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