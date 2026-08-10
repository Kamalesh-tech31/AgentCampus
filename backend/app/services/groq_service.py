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


class SlidePlan(BaseModel):
    slide_title: str
    slide_type: str  # e.g., "title", "kpi_dashboard", "chart", "table", "insights", "recommendation", "conclusion"
    key_points: List[str]
    insights: Optional[str] = None
    recommended_chart: Optional[str] = None  # e.g., "cgpa_distribution", "department_performance", None
    priority: int


class PresentationPlan(BaseModel):
    presentation_title: str
    presentation_subtitle: str
    presentation_style: str  # e.g., "executive", "academic", "professional", "modern", "minimal", "analytical"
    slides: List[SlidePlan]


class ReportSectionPlan(BaseModel):
    title: str
    type: str  # e.g., "summary", "statistics", "table", "chart", "insights", "recommendations"
    content: Optional[str] = None
    data_priority: Optional[str] = None
    recommended_chart: Optional[str] = None


class ReportPlan(BaseModel):
    report_title: str
    report_type: str
    executive_summary: Optional[str] = None
    sections: List[ReportSectionPlan]


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

    def generate_ppt_plan(self, prompt: str, data_summary: str) -> Optional[PresentationPlan]:
        """
        Sends presentation planning prompt to Groq LLM and returns validated PresentationPlan.
        Returns None if Groq is unconfigured, disabled, or returns invalid plan.
        """
        if not self.client:
            logger.info("[Groq] API unavailable or unconfigured; returning None for fallback.")
            return None

        logger.info(f"[Groq] Generating PPT plan for prompt: '{prompt[:40]}...'")

        system_prompt = (
            "You are an expert Presentation Planner for AgentCampus.\n"
            "Your job is to analyze the user's request and the available data summary to create a structured PowerPoint presentation plan.\n\n"
            "You do NOT write python code. You only produce a structured JSON plan.\n\n"
            "Available Slide Types:\n"
            "- title: The opening slide.\n"
            "- kpi_dashboard: For high-level statistics and metrics.\n"
            "- chart: For visual data representation.\n"
            "- table: For detailed lists of students or data.\n"
            "- insights: For analytical findings and textual summaries.\n"
            "- recommendation: For actionable advice.\n"
            "- conclusion: For the closing slide.\n\n"
            "Available Charts (use ONLY these exact strings for recommended_chart, or null):\n"
            "- cgpa_distribution\n"
            "- department_performance\n\n"
            "Rules:\n"
            "1. Create only relevant slides. Do not create empty slides.\n"
            "2. Keep key_points concise.\n"
            "3. Dynamically choose slide layouts based on content.\n"
            "4. NEVER invent data. Use ONLY the provided data summary.\n"
            "5. Return a valid JSON matching this schema:\n"
            "{\n"
            '  "presentation_title": "...",\n'
            '  "presentation_subtitle": "...",\n'
            '  "presentation_style": "executive",\n'
            '  "slides": [\n'
            '    {\n'
            '      "slide_title": "...",\n'
            '      "slide_type": "title",\n'
            '      "key_points": ["...", "..."],\n'
            '      "insights": "Optional string or null",\n'
            '      "recommended_chart": "cgpa_distribution",\n'
            '      "priority": 1\n'
            '    }\n'
            '  ]\n'
            "}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"User Request: {prompt}\n\nAvailable Data Summary:\n{data_summary}"},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )

            raw_content = response.choices[0].message.content
            if not raw_content:
                logger.warning("[Groq] Empty response received from Groq LLM for PPT plan.")
                return None

            payload = PresentationPlan.model_validate_json(raw_content)
            logger.info(f"[Groq] PPT Plan generated and validated (slides={len(payload.slides)})")
            return payload

        except Exception as exc:
            logger.error(f"[Groq] PPT planning API error or validation failure: {exc}")
            return None

    def generate_pdf_plan(self, prompt: str, data_summary: str) -> Optional[ReportPlan]:
        """
        Sends report planning prompt to Groq LLM and returns validated ReportPlan.
        Returns None if Groq is unconfigured, disabled, or returns invalid plan.
        """
        if not self.client:
            logger.info("[Groq] API unavailable or unconfigured; returning None for fallback.")
            return None

        logger.info(f"[Groq] Generating PDF plan for prompt: '{prompt[:40]}...'")

        system_prompt = (
            "You are an expert Report Planner for AgentCampus.\n"
            "Your job is to analyze the user's request and the available data summary to create a structured PDF report plan.\n\n"
            "You do NOT write python code. You only produce a structured JSON plan.\n\n"
            "Available Section Types:\n"
            "- summary: A text block summarizing context.\n"
            "- statistics: Key metrics and KPI list.\n"
            "- chart: A visual chart.\n"
            "- table: A detailed data table.\n"
            "- insights: Analytical insights.\n"
            "- recommendations: Actionable advice.\n\n"
            "Available Charts (use ONLY these exact strings for recommended_chart, or null):\n"
            "- cgpa_distribution\n"
            "- department_performance\n\n"
            "Rules:\n"
            "1. Create only relevant sections. Do not create empty sections if data is unavailable.\n"
            "2. Ensure the report flows logically.\n"
            "3. Return a valid JSON matching this schema:\n"
            "{\n"
            '  "report_title": "...",\n'
            '  "report_type": "...",\n'
            '  "executive_summary": "Optional short summary or null",\n'
            '  "sections": [\n'
            '    {\n'
            '      "title": "...",\n'
            '      "type": "summary | statistics | table | chart | insights | recommendations",\n'
            '      "content": "Optional string text or null",\n'
            '      "data_priority": "Optional instruction for the renderer or null",\n'
            '      "recommended_chart": "Optional chart type or null"\n'
            '    }\n'
            '  ]\n'
            "}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"User Request: {prompt}\n\nAvailable Data Summary:\n{data_summary}"},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )

            raw_content = response.choices[0].message.content
            if not raw_content:
                logger.warning("[Groq] Empty response received from Groq LLM for PDF plan.")
                return None

            payload = ReportPlan.model_validate_json(raw_content)
            logger.info(f"[Groq] PDF Plan generated and validated (sections={len(payload.sections)})")
            return payload

        except Exception as exc:
            logger.error(f"[Groq] PDF planning API error or validation failure: {exc}")
            return None

    def generate_text_report(self, prompt: str, data_summary: str) -> Optional[str]:
        """
        Sends text report generation prompt to Groq LLM and returns formatted text.
        Returns None if Groq is unconfigured, disabled, or encounters an error.
        """
        if not self.client:
            logger.info("[Groq] API unavailable or unconfigured; returning None for fallback.")
            return None

        logger.info(f"[Groq] Generating text report for prompt: '{prompt[:40]}...'")

        system_prompt = (
            "You are an expert Text Output Formatter for AgentCampus.\n"
            "Your job is to analyze the user's request and the available data summary to create a natural, well-organized text response.\n\n"
            "STRICT RULES:\n"
            "1. ONLY use information provided in the Available Data Summary.\n"
            "2. DO NOT hallucinate or invent student records, names, or statistics.\n"
            "3. If information is missing, clearly state that it is unavailable.\n"
            "4. Follow the user's requested style (e.g., detailed report, quick summary, ranked list).\n"
            "5. Keep the answer concise unless the user explicitly requests a detailed report.\n"
            "6. Output in clean Markdown format.\n"
            "7. Do NOT include JSON, and do NOT write Python code.\n"
            "8. Improve wording, structure, readability, and provide clear insights based ONLY on the data."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"User Request: {prompt}\n\nAvailable Data Summary:\n{data_summary}"},
                ],
                temperature=0.2,
            )

            raw_content = response.choices[0].message.content
            if not raw_content:
                logger.warning("[Groq] Empty response received from Groq LLM for text report.")
                return None

            logger.info("[Groq] Text report generated successfully.")
            return raw_content.strip()

        except Exception as exc:
            logger.error(f"[Groq] Text generation API error: {exc}")
            return None
