import os
import logging
from typing import Optional, List
from dotenv import load_dotenv
from pydantic import BaseModel
from app.contracts.orchestration import DynamicPlanRequestType

# Ensure .env is loaded if GroqService is initialized independently
load_dotenv()

logger = logging.getLogger(__name__)

VALID_AGENTS = {"input", "db", "analytics", "output"}


class GroqStep(BaseModel):
    agent: str
    action: str
    description: str


class GroqPlanPayload(BaseModel):
    title: str
    intent: str
    request_type: DynamicPlanRequestType
    steps: List[GroqStep]


class GroqService:
    """Service abstraction for LLM planning via Groq API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.client = None

        if self.api_key:
            try:
                import groq

                self.client = groq.Groq(api_key=self.api_key)
                logger.info(f"[Groq] API configured (model={self.model})")
            except Exception as exc:
                logger.error(f"[Groq] Failed to initialize Groq client: {exc}")
        else:
            logger.info("[Groq] API key not found in environment; returning None for fallback.")

    def generate_plan(self, prompt: str) -> Optional[GroqPlanPayload]:
        """
        Sends planning prompt to Groq LLM and returns validated GroqPlanPayload.
        Returns None if Groq is unconfigured, disabled, or returns invalid plan.
        """
        if not self.client:
            logger.info("[Groq] API unavailable or unconfigured; returning None for fallback.")
            return None

        logger.info(f"[Groq] Generating workflow plan for prompt: '{prompt[:40]}...'")

        system_prompt = (
            "You are the planning intelligence for AgentCampus, a multi-agent university campus management system.\n"
            "Your job is to analyze the user's natural language request and output a structured JSON execution plan.\n\n"
            "You do NOT execute tools or query databases directly. You only produce a structured workflow plan.\n\n"
            "Available specialized agents:\n"
            "- input: Parse natural language intent into structured parameters. (Step 1)\n"
            "- db: Query campus database using structured parameters. (Step 2)\n"
            "- analytics: Compute statistical metrics (average, min, max, breakdown). Include ONLY when analytical computation is required.\n"
            "- output: Format the final response summary and dataset. (Final Step)\n\n"
            "Do NOT include 'mother' in steps. Only include valid agents: ['input', 'db', 'analytics', 'output'].\n\n"
            "Rules:\n"
            "1. Read query (e.g. 'Show top 10 CS students'): request_type='read', steps: input -> db -> output (NO analytics).\n"
            "2. Analytics query (e.g. 'Calculate average CGPA'): request_type='analytics', steps: input -> db -> analytics -> output.\n"
            "3. Write query (e.g. 'Update student'): request_type='write', steps: input -> db -> output.\n\n"
            "Return ONLY a valid JSON object matching schema:\n"
            "{\n"
            '  "title": "Short title",\n'
            '  "intent": "Intent description",\n'
            '  "request_type": "read" | "analytics" | "write" | "complex",\n'
            '  "steps": [\n'
            '    {\n'
            '      "agent": "input" | "db" | "analytics" | "output",\n'
            '      "action": "Short action name",\n'
            '      "description": "Step description"\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            raw_content = response.choices[0].message.content
            if not raw_content:
                logger.warning("[Groq] Empty response received from Groq LLM.")
                return None

            payload = GroqPlanPayload.model_validate_json(raw_content)

            # Validate agent names
            for step in payload.steps:
                if step.agent not in VALID_AGENTS:
                    logger.warning(f"[Groq] Plan contains invalid agent '{step.agent}'. Rejecting plan.")
                    return None

            # Validate analytics step routing consistency
            has_analytics_step = any(s.agent == "analytics" for s in payload.steps)
            if payload.request_type == "read" and has_analytics_step:
                logger.warning("[Groq] Plan specifies request_type='read' but included analytics step. Rejecting plan.")
                return None

            if payload.request_type == "analytics" and not has_analytics_step:
                logger.warning("[Groq] Plan specifies request_type='analytics' but missing analytics step. Rejecting plan.")
                return None

            logger.info(f"[Groq] Plan generated and validated (request_type='{payload.request_type}', steps={len(payload.steps)})")
            return payload

        except Exception as exc:
            logger.error(f"[Groq] API error or validation failure: {exc}")
            return None
