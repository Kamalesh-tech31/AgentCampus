import os
import logging
from typing import Optional, List
from dotenv import load_dotenv
from pydantic import BaseModel
from app.contracts.orchestration import DynamicPlanRequestType
from app.services.groq_client import call_groq_completion

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


# ── Scribe Report Planning Schemas ──────────────────────────────────────────

class ReportSection(BaseModel):
    title: str
    type: str  # "summary" | "statistics" | "table" | "chart" | "insights" | "recommendations"
    content: Optional[str] = None
    data_priority: Optional[str] = None
    recommended_chart: Optional[str] = None


class ReportPlan(BaseModel):
    report_title: str
    report_type: str
    executive_summary: Optional[str] = None
    sections: List[ReportSection]


class SlidePlan(BaseModel):
    slide_title: str
    slide_type: str  # "title" | "kpi_dashboard" | "chart" | "table" | "insights" | "recommendation" | "conclusion"
    key_points: List[str]
    insights: Optional[str] = None
    recommended_chart: Optional[str] = None
    priority: int = 1


class PresentationPlan(BaseModel):
    presentation_title: str
    presentation_subtitle: Optional[str] = None
    presentation_style: str = "executive"
    slides: List[SlidePlan]


class GroqService:
    """Service abstraction for LLM planning via Groq API with automatic key fallback."""

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
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
            except Exception:
                self.client = None

    def generate_plan(self, prompt: str) -> Optional[GroqPlanPayload]:
        """
        Sends planning prompt to Groq LLM and returns validated GroqPlanPayload.
        Automatically retries with GROQ_API_KEY_2 if rate limit occurs.
        """
        if not self.api_key and not self.client:
            logger.info("[Groq] No API key configured; returning None for deterministic fallback.")
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
            if self.client:
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
            else:
                raw_content = call_groq_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    model=self.model,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )

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
            "You are an expert Presentation Designer for AgentCampus.\n"
            "Your job is to analyze the user's request and the available data summary to create a structured PowerPoint presentation plan.\n\n"
            "You do NOT write python code. You only produce a structured JSON plan.\n\n"
            "STRICT RULES:\n"
            "1. NO FIXED OR GENERIC SLIDES. Never automatically generate generic slides like 'Executive Summary', 'Introduction', 'Overview', 'CGPA Distribution', 'Department Performance', generic conclusions, or generic recommendations unless they are directly relevant to the user request.\n"
            "2. DYNAMIC CONTENT: The presentation title, slide titles, slide types, key points, charts, insights, and recommendations must be completely custom-tailored to the user query and the available data.\n"
            "3. If the user asks about risk/probation, focus the entire presentation structure around risk analysis, at-risk students, root causes, and risk-related interventions. Do not include unrelated department/academic statistics.\n"
            "4. For slides of type 'table': if the data summary lists specific tables (e.g. 'at_risk_students'), focus the slide on that specific data.\n"
            "5. For slides of type 'chart': if the data summary lists specific charts (e.g. 'risk_pie', 'group_bar'), specify it in 'recommended_chart'. Otherwise, use 'cgpa_distribution', 'department_performance', or null.\n"
            "6. Make 3 to 6 slides maximum, depending on the complexity of the request.\n\n"
            "Available Slide Types:\n"
            "- title: Presentation title slide.\n"
            "- kpi_dashboard: High-level numerical summary cards/metrics.\n"
            "- chart: A visual chart representation.\n"
            "- table: A structured data table.\n"
            "- insights: Analytical insights and breakdown.\n"
            "- recommendation: Actionable next steps.\n"
            "- conclusion: Summary and closing thoughts.\n\n"
            "Return a valid JSON matching this schema:\n"
            "{\n"
            '  "presentation_title": "Custom title fitting user request",\n'
            '  "presentation_subtitle": "Custom subtitle",\n'
            '  "presentation_style": "executive | analytical | modern",\n'
            '  "slides": [\n'
            '    {\n'
            '      "slide_title": "...",\n'
            '      "slide_type": "title | kpi_dashboard | chart | table | insights | recommendation | conclusion",\n'
            '      "key_points": ["...", "..."],\n'
            '      "insights": "Optional string or null",\n'
            '      "recommended_chart": "Chart key or null",\n'
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
            "STRICT RULES:\n"
            "1. NO FIXED OR GENERIC SECTIONS. Never automatically generate generic sections like 'Executive Summary', 'Introduction', 'Key Statistics', 'CGPA Distribution', 'Department Performance', generic conclusions, or generic recommendations unless they are directly relevant to the user request.\n"
            "2. DYNAMIC CONTENT: The title, sections, charts, tables, insights, recommendations, and layout must be completely custom-tailored to the user query and the available data.\n"
            "3. If the user asks about risk/probation, focus the entire report structure around risk analysis, at-risk students, and risk-related recommendations. Do not include unrelated department/academic statistics.\n"
            "4. For sections of type 'table': if the data summary lists specific tables (e.g. 'at_risk_students'), set the 'content' field to that specific table name. If not, set it to 'all_records' or null.\n"
            "5. For sections of type 'chart': if the data summary lists specific charts (e.g. 'risk_pie', 'group_bar'), specify it in 'recommended_chart'. Otherwise, use 'cgpa_distribution', 'department_performance', or null.\n\n"
            "Available Section Types:\n"
            "- summary: A text block summarizing context.\n"
            "- statistics: Key metrics and KPI list.\n"
            "- chart: A visual chart.\n"
            "- table: A detailed data table.\n"
            "- insights: Analytical insights.\n"
            "- recommendations: Actionable advice.\n\n"
            "Return a valid JSON matching this schema:\n"
            "{\n"
            '  "report_title": "Custom title fitting user request",\n'
            '  "report_type": "Custom report type description",\n'
            '  "executive_summary": "Tailored executive summary or null",\n'
            '  "sections": [\n'
            '    {\n'
            '      "title": "Descriptive section title",\n'
            '      "type": "summary | statistics | table | chart | insights | recommendations",\n'
            '      "content": "Specific table/chart name or text content or null",\n'
            '      "data_priority": "e.g., high, medium, low",\n'
            '      "recommended_chart": "Chart key or null"\n'
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

    def extract_data_from_image(self, image_path: str, query: Optional[str] = None) -> Optional[dict]:
        """
        Sends an image to Groq's Vision LLM to extract either a natural language query
        or structured student records.

        Uses two strategies:
        1. Parse JSON from the response (after stripping think block).
        2. If JSON is missing/truncated, parse matched records from the <think> block
           directly — the model reliably outputs match lines even when it runs out of
           tokens before producing JSON.
        """
        if not self.client:
            logger.info("[Groq] API unavailable or unconfigured for image extraction.")
            return None

        import base64
        import mimetypes
        import re
        import json as _json

        logger.info(f"[Groq] Extracting data from image: {image_path} (filter query: {query})")

        try:
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")

            mime_type, _ = mimetypes.guess_type(image_path)
            mime_type = mime_type or "image/jpeg"

            if query and query.strip():
                filter_instruction = (
                    f"FILTER: Only return records matching '{query.strip()}'. Skip all other rows."
                )
            else:
                filter_instruction = "Return at most 10 records."

            vision_prompt = (
                f"/no_think\n"
                f"Extract student data from this image as JSON.\n"
                f"{filter_instruction}\n\n"
                f"Output ONLY this JSON (omit null fields):\n"
                f'{{"type":"table","records":[{{"name":"...","department":"Computer Science|Electronics|Mechanical|Civil|Data Science|AI & ML","cgpa":0.0,"roll_number":"..."}}]}}\n'
                f"Dept abbreviations: CSE=Computer Science, AIML=AI & ML, MECH=Mechanical, CIVIL=Civil.\n"
                f"No markdown. No explanation. JSON only."
            )

            response = self.client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=[
                    {
                        "role": "system",
                        "content": "Output ONLY valid JSON. No thinking. No explanation.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": vision_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{base64_image}"},
                            },
                        ],
                    },
                ],
                max_tokens=3500,
                temperature=0.0,
            )

            raw_content = response.choices[0].message.content
            if not raw_content:
                logger.warning("[Groq Vision] Empty response from vision model.")
                return None

            # ── Strategy 1: Parse JSON from outside the <think> block ──────────────────
            clean = re.sub(r"<think>[\s\S]*?</think>", "", raw_content).strip()
            md_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean, re.IGNORECASE)
            if md_match:
                clean = md_match.group(1).strip()
            else:
                j_match = re.search(r"(\{[\s\S]*\})", clean)
                if j_match:
                    clean = j_match.group(1).strip()

            if clean:
                try:
                    data = _json.loads(clean)
                    n = len(data.get("records") or [])
                    logger.info(f"[Groq Vision] JSON parsed OK — type={data.get('type')} records={n}")
                    return data
                except _json.JSONDecodeError:
                    logger.warning("[Groq Vision] JSON parse failed; trying think-block fallback.")

            # ── Strategy 2: Parse matched records from <think> block ─────────────────
            # The model always writes "Row N: ID XXXX, Name ..., Dept CSE, CGPA X.XX. (Match"
            # for every row that satisfies the filter, even when it runs out of tokens
            # before producing the JSON output section.
            think_match = re.search(r"<think>([\s\S]*?)(?:</think>|$)", raw_content)
            if think_match:
                think_content = think_match.group(1)

                DEPT_MAP = {
                    "CSE": "Computer Science",
                    "AIML": "AI & ML",
                    "AI&ML": "AI & ML",
                    "MECH": "Mechanical",
                    "CIVIL": "Civil",
                    "ECE": "Electronics",
                    "EC": "Electronics",
                    "DS": "Data Science",
                }

                # Match lines like: "Row 5: ID 5005, Name Student 05, Dept CSE, CGPA 9.18. (Match"
                row_iter = re.finditer(
                    r"Row\s+\d+:\s+ID\s+(\S+),\s+Name\s+(.+?),\s+Dept\s+(\S+),\s+CGPA\s+([\d.]+).*?\(Match",
                    think_content,
                )
                records = []
                for m in row_iter:
                    roll, name, dept, cgpa = (
                        m.group(1).strip(),
                        m.group(2).strip(),
                        m.group(3).strip().upper(),
                        m.group(4).strip(),
                    )
                    try:
                        cgpa_f = round(float(cgpa), 2)
                        if not (0.0 <= cgpa_f <= 10.0):
                            continue
                    except ValueError:
                        continue
                    records.append({
                        "name": name,
                        "department": DEPT_MAP.get(dept, dept),
                        "cgpa": cgpa_f,
                        "roll_number": roll,
                    })

                # Deduplicate by roll_number, sort by cgpa desc
                seen: set = set()
                unique = []
                for r in records:
                    if r["roll_number"] not in seen:
                        seen.add(r["roll_number"])
                        unique.append(r)
                unique.sort(key=lambda x: x["cgpa"], reverse=True)

                # Honour "top N" limit from the query string
                limit_m = re.search(r"\btop\s+(\d+)\b", query or "", re.IGNORECASE)
                if limit_m:
                    unique = unique[: int(limit_m.group(1))]

                if unique:
                    logger.info(
                        f"[Groq Vision] Extracted {len(unique)} records from think block."
                    )
                    return {"type": "table", "records": unique}

            logger.warning("[Groq Vision] Could not extract any data from response.")
            return None

        except Exception as exc:
            logger.error(f"[Groq Vision] Error extracting data from image: {exc}")
            return None
