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


class GroqService:
    """Service abstraction for LLM planning via Groq API with automatic key fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def generate_plan(self, prompt: str) -> Optional[GroqPlanPayload]:
        """
        Sends planning prompt to Groq LLM and returns validated GroqPlanPayload.
        Automatically retries with GROQ_API_KEY_2 if rate limit occurs.
        """
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
