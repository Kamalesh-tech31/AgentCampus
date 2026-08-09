from typing import Any, Literal

from pydantic import BaseModel, Field


TaskStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
]


class AgentTask(BaseModel):
    task_id: str
    agent: str
    objective: str
    input_data: dict[str, Any] = Field(
        default_factory=dict
    )
    expected_output: str
    status: TaskStatus = "pending"


class AgentResult(BaseModel):
    task_id: str
    agent: str
    status: TaskStatus
    result: dict[str, Any] = Field(
        default_factory=dict
    )
    error: str | None = None