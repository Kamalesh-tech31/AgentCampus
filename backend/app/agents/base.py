from abc import ABC, abstractmethod

from app.mother.types import AgentTask, AgentResult


class BaseAgent(ABC):

    name: str

    @abstractmethod
    def execute(self, task: AgentTask) -> AgentResult:
        pass