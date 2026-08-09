from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult


class AnalyticsAgent(BaseAgent):

    name = "analytics"

    def execute(self, task: AgentTask) -> AgentResult:

        records = task.input_data.get(
            "records",
            []
        )

        if records:
            average = sum(
                student["cgpa"]
                for student in records
            ) / len(records)

            highest = max(
                student["cgpa"]
                for student in records
            )
        else:
            average = 0
            highest = 0

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status="completed",
            result={
                "average_cgpa": round(
                    average,
                    2
                ),
                "highest_cgpa": highest,
                "insight": (
                    "Students show strong "
                    "academic performance."
                ),
            },
        )