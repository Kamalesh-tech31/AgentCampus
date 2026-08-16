from app.agents.base import BaseAgent
from app.agents.input_agent import InputAgent
from app.agents.db_agent import DBAgent
from app.agents.analytics_agent import AnalyticsAgent
from app.agents.output_agent import OutputAgent


class AgentRegistry:
    
    def __init__(self):

        self._agents: dict[str, BaseAgent] = {
            "input": InputAgent(),
            "db": DBAgent(),
            "analytics": AnalyticsAgent(),
            "output": OutputAgent(),
        }

    def get(self, agent_name: str) -> BaseAgent:

        agent = self._agents.get(agent_name)

        if agent is None:
            raise ValueError(
                f"Agent not registered: {agent_name}"
            )

        return agent

    def register(self, name: str, agent: BaseAgent) -> None:
        self._agents[name] = agent

    def list_agents(self) -> list[str]:
        return list(self._agents.keys())