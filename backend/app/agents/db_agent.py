from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult


class DBAgent(BaseAgent):

    name = "db"

    def execute(self, task: AgentTask) -> AgentResult:

        sql = task.input_data.get(
            "sql",
            ""
        )

        records = [
            {
                "student_id": 1,
                "name": "Student A",
                "cgpa": 9.92,
            },
            {
                "student_id": 2,
                "name": "Student B",
                "cgpa": 9.81,
            },
            {
                "student_id": 3,
                "name": "Student C",
                "cgpa": 9.74,
            },
        ]

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status="completed",
            result={
                "sql": sql,
                "records": records,
                "count": len(records),
            },
        )