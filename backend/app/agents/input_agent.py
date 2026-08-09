from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult


class InputAgent(BaseAgent):

    name = "input"

    def execute(self, task: AgentTask) -> AgentResult:

        query = task.input_data.get(
            "user_query",
            ""
        )

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status="completed",
            result={
                "intent": "student_query",
                "sql": (
                    "SELECT * FROM students "
                    "ORDER BY cgpa DESC LIMIT 100;"
                ),
                "original_query": query,
            },
        )