from typing import Literal, Optional, List, Any
from pydantic import Field
from app.contracts.common import CamelModel

AgentStatus = Literal["waiting", "running", "complete", "failed"]

AgentType = Literal["input", "mother", "db", "analytics", "output"]

ActivityLogLevel = Literal["info", "working", "success", "warn", "error"]


class AgentInfo(CamelModel):
    id: AgentType
    name: str
    role: str
    badge: str
    model: str
    color: str


class ActivityLog(CamelModel):
    id: str
    timestamp: str
    agent_id: AgentType
    level: ActivityLogLevel
    message: str
    details: Optional[Any] = None


class AgentState(CamelModel):
    id: AgentType
    name: str
    role: str
    badge: str
    model: str
    status: AgentStatus
    status_message: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    logs: List[ActivityLog] = Field(default_factory=list)
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None
