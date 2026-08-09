from typing import Any

from pydantic import BaseModel, Field

from .types import AgentTask


class WorkflowState(BaseModel):
    workflow_id: str
    user_query: str

    current_task: AgentTask | None = None

    task_history: list[AgentTask] = Field(
        default_factory=list
    )

    results: dict[str, Any] = Field(
        default_factory=dict
    )

    status: str = "planning"