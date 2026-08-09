import uuid

from .types import AgentTask


class TaskManager:

    def create_task(
        self,
        agent: str,
        objective: str,
        input_data: dict,
        expected_output: str,
    ) -> AgentTask:

        task = AgentTask(
            task_id=f"TASK-{uuid.uuid4().hex[:6].upper()}",
            agent=agent,
            objective=objective,
            input_data=input_data,
            expected_output=expected_output,
        )

        return task