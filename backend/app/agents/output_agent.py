from typing import List, Dict, Any, Optional
from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult
from app.contracts import OrchestrationResult, StudentRecord, OrchestrationMetrics


class OutputAgent(BaseAgent):
    name = "output"

    def execute(self, task: AgentTask) -> AgentResult:
        db_result = task.input_data.get("db", {})
        analytics_result = task.input_data.get("analytics", {})

        records_raw = db_result.get("records", [])
        sql_executed = db_result.get("sql", "")
        affected_count = db_result.get("count", len(records_raw))

        # Parse StudentRecord models
        validated_students: List[StudentRecord] = [
            StudentRecord.model_validate(r) for r in records_raw
        ]

        # Parse OrchestrationMetrics if present from AnalyticsAgent
        raw_metrics = analytics_result.get("metrics")
        validated_metrics: Optional[OrchestrationMetrics] = (
            OrchestrationMetrics.model_validate(raw_metrics) if raw_metrics else None
        )

        # Build CSV data payload
        csv_lines = [
            "id,rollNumber,name,department,cgpa,semester,attendance,email,status,backlogs,projectTitle"
        ]
        for s in validated_students:
            csv_lines.append(
                f'"{s.id}","{s.roll_number}","{s.name}","{s.department}",{s.cgpa},{s.semester},{s.attendance},"{s.email}","{s.status}",{s.backlogs},"{s.project_title or ""}"'
            )
        csv_data = "\n".join(csv_lines)

        # Build human-readable summary
        dept_str = (
            f" in {validated_students[0].department}"
            if validated_students and all(s.department == validated_students[0].department for s in validated_students)
            else ""
        )
        metrics_str = (
            f" Average CGPA is {validated_metrics.average_cgpa:.2f}."
            if validated_metrics and validated_metrics.average_cgpa is not None
            else ""
        )
        summary = (
            f"Retrieved {len(validated_students)} student records{dept_str}.{metrics_str}"
        )

        # Construct and validate OrchestrationResult Pydantic model
        result_contract = OrchestrationResult(
            summary=summary,
            query_executed=sql_executed,
            affected_count=affected_count,
            data=validated_students,
            metrics=validated_metrics,
            csv_data=csv_data,
        )

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status="completed",
            result={
                "summary": summary,
                "result": result_contract.model_dump(by_alias=True),
            },
        )