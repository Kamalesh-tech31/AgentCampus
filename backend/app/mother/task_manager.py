import uuid
from typing import Dict, Any
from app.mother.types import AgentTask, AgentResult, TaskStatus


class TaskManager:
    """Manages creation, tracking, and updating of AgentTasks within a workflow."""

    def create_task(
        self,
        agent: str,
        objective: str,
        input_data: Dict[str, Any],
        expected_output: str,
    ) -> AgentTask:
        task = AgentTask(
            task_id=f"TASK-{uuid.uuid4().hex[:6].upper()}",
            agent=agent,
            objective=objective,
            input_data=input_data,
            expected_output=expected_output,
            status="pending",
        )
        return task

    def update_task_status(
        self, task: AgentTask, status: TaskStatus
    ) -> AgentTask:
        task.status = status
        return task