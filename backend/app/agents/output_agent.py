from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult


class OutputAgent(BaseAgent):

    name = "output"

    def execute(self, task: AgentTask) -> AgentResult:

        database = task.input_data.get(
            "database",
            {}
        )

        analysis = task.input_data.get(
            "analysis",
            {}
        )

        count = database.get(
            "count",
            0
        )

        average = analysis.get(
            "average_cgpa",
            0
        )

        response = (
            f"Retrieved {count} students. "
            f"The average CGPA is {average}."
        )

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status="completed",
            result={
                "response": response,
                "format": "text",
            },
        )