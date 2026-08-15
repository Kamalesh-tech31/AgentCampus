from typing import Any, List, Dict, Optional
from pydantic import BaseModel, Field
from app.mother.types import AgentTask, AgentResult
from app.contracts import (
    DynamicPlan,
    OrchestrationEvent,
    OrchestrationResult,
    DynamicPlanRequestType,
    AgentState,
)


class WorkflowState(BaseModel):
    workflow_id: str
    user_query: str
    mode: Optional[str] = None  # "modify" | "explore" | "analyze"
    confirmed: bool = False     # Confirmation flag for destructive mutations
    request_type: DynamicPlanRequestType = "read"
    status: str = "planning"

    current_task: Optional[AgentTask] = None
    task_history: List[AgentTask] = Field(default_factory=list)
    results: Dict[str, Any] = Field(default_factory=dict)
    events: List[OrchestrationEvent] = Field(default_factory=list)
    plan: Optional[DynamicPlan] = None
    final_result: Optional[OrchestrationResult] = None