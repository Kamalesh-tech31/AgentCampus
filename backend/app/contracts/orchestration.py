from typing import Literal, Optional, List, Dict, Any
from app.contracts.common import CamelModel
from app.contracts.students import StudentRecord
from app.contracts.agents import AgentType, AgentStatus, ActivityLog, AgentState

DynamicPlanRequestType = Literal["read", "analytics", "write", "complex"]


class PlanStep(CamelModel):
    id: str
    step_number: int
    agent: AgentType
    action: str
    description: str
    status: AgentStatus
    live_message: Optional[str] = None
    details: Optional[str] = None


class DynamicPlan(CamelModel):
    task_id: str
    title: str
    intent: str
    request_type: DynamicPlanRequestType
    steps: List[PlanStep]


class DepartmentMetric(CamelModel):
    count: int
    avg_cgpa: float


class OrchestrationMetrics(CamelModel):
    total_records: Optional[int] = None
    average_cgpa: Optional[float] = None
    highest_cgpa: Optional[float] = None
    lowest_cgpa: Optional[float] = None
    avg_attendance: Optional[float] = None
    probation_count: Optional[int] = None
    department_breakdown: Optional[Dict[str, DepartmentMetric]] = None


UserMode = Literal["modify", "explore", "analyze"]


class OrchestrationResult(CamelModel):
    summary: str
    query_executed: Optional[str] = None
    mutation_executed: Optional[str] = None
    affected_count: Optional[int] = None
    data: Optional[List[StudentRecord]] = None
    metrics: Optional[OrchestrationMetrics] = None
    csv_data: Optional[str] = None
    raw_plan: Optional[DynamicPlan] = None
    structured_intent: Optional[Any] = None
    # Scribe output metadata — additive, backward-compatible
    output_format: Optional[str] = None   # "text" | "excel" | "pdf" | "pptx"
    output_file: Optional[str] = None     # absolute file path when format is file-based
    # 3-Mode & confirmation extensions
    mode: Optional[str] = None            # "modify" | "explore" | "analyze"
    requires_confirmation: Optional[bool] = False
    confirmation_details: Optional[Dict[str, Any]] = None
    execution: Optional[Dict[str, Any]] = None
    # Error & rate-limit handling fields
    success: Optional[bool] = True
    error_type: Optional[str] = None      # "RATE_LIMITED" | "VALIDATION_ERROR" | "DATABASE_ERROR" | "INTERNAL_SERVER_ERROR"
    retry_after: Optional[str] = None



OrchestrationEventType = Literal[
    "TASK_CREATED",
    "AGENT_STARTED",
    "AGENT_WORKING",
    "AGENT_COMPLETED",
    "AGENT_FAILED",
    "PLAN_UPDATED",
    "RESULT_READY",
]


class OrchestrationEvent(CamelModel):
    type: OrchestrationEventType
    task_id: str
    timestamp: float
    agent_id: Optional[AgentType] = None
    message: Optional[str] = None
    plan: Optional[DynamicPlan] = None
    agent_state: Optional[Dict[str, Any]] = None
    log: Optional[ActivityLog] = None
    result: Optional[OrchestrationResult] = None
    structured_intent: Optional[Any] = None


class Turn(CamelModel):
    id: str
    timestamp: str
    prompt: str
    status: AgentStatus
    agents: Dict[str, AgentState]
    plan: Optional[DynamicPlan] = None
    result: Optional[OrchestrationResult] = None
    structured_intent: Optional[Any] = None
    duration_ms: Optional[float] = None


class ChatThread(CamelModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    turns: List[Turn]


class HistoryItem(CamelModel):
    id: str
    timestamp: str
    prompt: str
    plan_title: str
    status: AgentStatus
    result_summary: Optional[str] = None
    structured_intent: Optional[Any] = None


class OrchestrationRequest(CamelModel):
    prompt: Optional[str] = None
    user_query: Optional[str] = None
    mode: Optional[str] = None          # "modify" | "explore" | "analyze"
    confirmed: Optional[bool] = False   # Confirmation flag for destructive mutations

    def get_query(self) -> str:
        return self.user_query or self.prompt or ""

