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

    def extract_data_from_image(self, image_path: str) -> Optional[dict]:
        """
        Sends an image to Groq's Vision LLM to extract either a natural language query
        or structured student records.
        """
        if not self.client:
            logger.info("[Groq] API unavailable or unconfigured for image extraction.")
            return None

        import base64
        import mimetypes

        logger.info(f"[Groq] Extracting data from image: {image_path}")

        try:
            # 1. Base64 encode the image
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")

            mime_type, _ = mimetypes.guess_type(image_path)
            mime_type = mime_type or "image/jpeg"

            # 2. Call Groq vision API
            vision_prompt = (
                "Analyze this image. It contains either a natural language query (text) about students, "
                "or a table/list of student records.\n\n"
                "Extract the content and return ONLY a JSON object matching this schema:\n"
                "{\n"
                '  "type": "table" | "query",\n'
                '  "query": "the extracted text query if type is query, else null",\n'
                '  "records": [\n'
                "    {\n"
                '      "name": "Student Full Name",\n'
                '      "department": "Computer Science" | "Electronics" | "Mechanical" | "Civil" | "Data Science" | "AI & ML",\n'
                '      "cgpa": float (between 0.0 and 10.0),\n'
                '      "attendance": float (between 0.0 and 100.0),\n'
                '      "status": "Active" | "Probation" | "Graduated",\n'
                '      "roll_number": "Roll number string if present, else empty/null",\n'
                '      "semester": int (between 1 and 8 if present, else null),\n'
                '      "email": "Email string if present, else null",\n'
                '      "backlogs": int (>=0 if present, else null),\n'
                '      "project_title": "Project title string if present, else null"\n'
                "    }\n"
                "  ]\n"
                "}\n\n"
                "Return raw valid JSON only. Do not wrap in markdown code blocks."
            )

            response = self.client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": vision_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            raw_content = response.choices[0].message.content
            if not raw_content:
                logger.warning("[Groq Vision] Empty response from vision model.")
                return None

            import json
            data = json.loads(raw_content)
            logger.info(f"[Groq Vision] Successfully parsed image of type: {data.get('type')}")
            return data

        except Exception as exc:
            logger.error(f"[Groq Vision] Error extracting data from image: {exc}")
            return None

