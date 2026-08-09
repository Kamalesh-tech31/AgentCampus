from typing import Dict, Any, List
from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult
from app.contracts import OrchestrationMetrics, DepartmentMetric


class AnalyticsAgent(BaseAgent):
    name = "analytics"

    def execute(self, task: AgentTask) -> AgentResult:
        # Strictly consume records from DBAgent output
        db_result = task.input_data.get("db", {})
        records: List[Dict[str, Any]] = db_result.get("records") or task.input_data.get(
            "records", []
        )

        if not records:
            empty_metrics = OrchestrationMetrics(
                total_records=0,
                average_cgpa=0.0,
                highest_cgpa=0.0,
                lowest_cgpa=0.0,
                avg_attendance=0.0,
                probation_count=0,
                department_breakdown={},
            )
            return AgentResult(
                task_id=task.task_id,
                agent=self.name,
                status="completed",
                result={
                    "metrics": empty_metrics.model_dump(by_alias=True),
                    "insight": "No records available for statistical calculation.",
                },
            )

        total_records = len(records)
        cgpa_list = [r.get("cgpa", 0.0) for r in records]
        attendance_list = [r.get("attendance", 0.0) for r in records]
        probation_count = sum(1 for r in records if r.get("status") == "Probation")

        avg_cgpa = round(sum(cgpa_list) / total_records, 2)
        highest_cgpa = round(max(cgpa_list), 2)
        lowest_cgpa = round(min(cgpa_list), 2)
        avg_attendance = round(sum(attendance_list) / total_records, 2)

        # Department breakdown
        dept_counts: Dict[str, List[float]] = {}
        for r in records:
            d = r.get("department", "Unknown")
            cg = r.get("cgpa", 0.0)
            dept_counts.setdefault(d, []).append(cg)

        dept_breakdown: Dict[str, DepartmentMetric] = {}
        for dept, c_list in dept_counts.items():
            dept_breakdown[dept] = DepartmentMetric(
                count=len(c_list),
                avg_cgpa=round(sum(c_list) / len(c_list), 2),
            )

        metrics = OrchestrationMetrics(
            total_records=total_records,
            average_cgpa=avg_cgpa,
            highest_cgpa=highest_cgpa,
            lowest_cgpa=lowest_cgpa,
            avg_attendance=avg_attendance,
            probation_count=probation_count,
            department_breakdown=dept_breakdown,
        )

        insight = (
            f"Analyzed {total_records} records. Average CGPA is {avg_cgpa} with highest CGPA of {highest_cgpa}."
        )

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status="completed",
            result={
                "metrics": metrics.model_dump(by_alias=True),
                "insight": insight,
            },
        )