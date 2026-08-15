# LLM & API Usage Audit Report — AgentCampus

**Date of Audit:** 2026-08-15  
**Project:** AgentCampus Multi-Agent University Campus Management System  
**Audit Scope:** Full Backend (`backend/app/**`), Orchestration Flows, Agent Implementations, Services, Configuration, and Frontend (`frontend/src/**`).  
**Mode:** READ-ONLY Inspection (No code, configurations, or environment variables modified).

---

## 1. Executive Summary

An exhaustive audit of the AgentCampus codebase was conducted to trace all Large Language Model (LLM) and External API configurations, client initializations, invocation call sites, multi-agent orchestration flows, fallback mechanisms, token expenditures, and key isolation boundaries.

### Key Architectural Findings:
1. **Total LLM Call Sites in Codebase:** `9` distinct API call sites.
2. **Total Agents Utilizing LLMs:** `5` agents (Input [Vision OCR], Mother Agent [Workflow Planning], DB Agent [Vault SQL Planning], Pulse/Analytics Agent [Analysis Planning & Interpretation], Scribe/Output Agent [Report Planning & Text Generation]).
3. **API Key Separation:**
   - **Isolated Key:** `PULSE_GROQ_API_KEY` is strictly used by the Pulse/Analytics Agent (`planner_service.py`, `llm_interpreter.py`).
   - **Shared Key:** `GROQ_API_KEY` (along with fallback aliases `GROQ_API_KEY_1`, `GROQ_API_KEY_2`, `GROQ_API_KEY_3`, `GROQ_API_KEY_4`) is shared across Mother Agent, DB Agent (Vault), Scribe Agent, and Input Agent (Vision).
   - **Orphaned / Unused Variables:** `SCRIBE_GROQ_API_KEY` is documented in comments but is not read by executable code (Scribe defaults to `GroqService()`, reading `GROQ_API_KEY`).
4. **Deterministic Fallback Resilience:** Every agent in AgentCampus possesses 100% deterministic Python/rule-based fallbacks. If all Groq API keys are absent, exhausted, or rate-limited (HTTP 429), the entire multi-agent pipeline completes successfully without runtime crashes.

---

## 2. Environment Variables Found

The following environment variables relating to LLMs, models, and external databases were discovered across `.env`, `backend/app/`, and documentation:

| Environment Variable | Category | Defined in `.env` | Referenced in Source Code | Status |
|----------------------|----------|-------------------|---------------------------|--------|
| `GROQ_API_KEY` | Primary LLM Key | Yes | Yes (`groq_service.py`, `groq_client.py`, `main.py`) | **Active / Used** |
| `GROQ_API_KEY_1` | Fallback Key | Yes | Yes (`groq_client.py` via prefix scan) | **Active / Used** |
| `GROQ_API_KEY_2` | Fallback Key | Yes | Yes (`groq_client.py` via prefix scan) | **Active / Used** |
| `GROQ_API_KEY_3` | Fallback Key | Yes | Yes (`groq_client.py` via prefix scan) | **Active / Used** |
| `GROQ_API_KEY_4` | Fallback Key | Yes | Yes (`groq_client.py` via prefix scan) | **Active / Used** |
| `GROQ_MODEL` | LLM Model Name | Yes | Yes (`groq_service.py`, `groq_client.py`, `vault_planner.py`) | **Active / Used** (Default: `llama-3.3-70b-versatile`) |
| `PULSE_GROQ_API_KEY` | Dedicated LLM Key | Yes | Yes (`planner_service.py`, `llm_interpreter.py`) | **Active / Used** |
| `PULSE_GROQ_MODEL` | Dedicated Model Name | Yes | Yes (`planner_service.py`, `llm_interpreter.py`) | **Active / Used** (Default: `llama-3.3-70b-versatile`) |
| `SCRIBE_GROQ_API_KEY` | Dedicated LLM Key | No | No (Only in docstrings) | **Unused / Orphaned** |
| `SUPABASE_URL` | Database Connection | Yes | Yes (`client.py`, `schema_registry.py`) | **Active / Used** |
| `SUPABASE_KEY` | Database Auth Key | Yes | Yes (`client.py`, `schema_registry.py`) | **Active / Used** |

*(Note: Secret values were not logged or printed in compliance with security guidelines).*

---

## 3. API-Key Usage Map

```
GROQ_API_KEY (+ GROQ_API_KEY_1..4)
 ├── backend/app/services/groq_service.py (GroqService)
 │    ├── MotherAgent (Workflow Plan Synthesis)
 │    ├── InputAgent (Vision OCR on Image Files: .png, .jpg, .jpeg)
 │    └── Scribe / Output Agent (Text Generation, PDF Plan, PPT Plan)
 ├── backend/app/services/groq_client.py (call_groq_completion)
 │    └── DB Agent / Vault Planner (Dynamic SQL & Mutation Plan)
 └── backend/app/main.py (Startup Health Diagnostic)

PULSE_GROQ_API_KEY
 ├── backend/app/services/pulse/planner_service.py (get_analysis_plan)
 └── backend/app/services/pulse/llm_interpreter.py (interpret_results, llm_reasoning_analysis)

SUPABASE_URL & SUPABASE_KEY
 ├── backend/app/db/client.py (Supabase Client for CRUD & RPC)
 └── backend/app/db/schema_registry.py (Dynamic Schema Inspection)
```

---

## 4. Agent → API Key → Model Mapping

| Agent | Sub-Component | API Key Variable | Model Identifier | Separation Status |
|---|---|---|---|---|
| **Input Agent** | Text / Excel / PDF | None (Deterministic) | N/A | Deterministic (0 LLM Calls) |
| **Input Agent** | Image OCR Parser | `GROQ_API_KEY` | `qwen/qwen3.6-27b` | Shared with Mother/DB/Scribe |
| **Mother Agent** | Dynamic Plan Synthesizer | `GROQ_API_KEY` | `GROQ_MODEL` (`llama-3.3-70b-versatile`) | Shared with DB/Scribe/Input |
| **DB Agent** | Vault Query Planner | `GROQ_API_KEY` (+ `_1`..`_4`) | `GROQ_MODEL` (`llama-3.3-70b-versatile` + fallbacks) | Shared pool |
| **Pulse Agent** | Analysis Planner | `PULSE_GROQ_API_KEY` | `PULSE_GROQ_MODEL` (`llama-3.3-70b-versatile`) | **Dedicated / Isolated** |
| **Pulse Agent** | Result Interpreter | `PULSE_GROQ_API_KEY` | `PULSE_GROQ_MODEL` (`llama-3.3-70b-versatile`) | **Dedicated / Isolated** |
| **Scribe Agent** | Text Formatter | `GROQ_API_KEY` | `GROQ_MODEL` (`llama-3.3-70b-versatile`) | Shared with Mother/DB/Input |
| **Scribe Agent** | PDF Planner | `GROQ_API_KEY` | `GROQ_MODEL` (`llama-3.3-70b-versatile`) | Shared with Mother/DB/Input |
| **Scribe Agent** | PPT Planner | `GROQ_API_KEY` | `GROQ_MODEL` (`llama-3.3-70b-versatile`) | Shared with Mother/DB/Input |
| **Scribe Agent** | Excel Generator | None (Deterministic) | N/A | Deterministic (0 LLM Calls) |

---

## 5. LLM Client Creation Locations

| # | File | Line | Class / Function | Client Type | Lifecycle | Key Used |
|---|---|---|---|---|---|---|
| 1 | `backend/app/services/groq_service.py` | 76 | `GroqService.__init__` | `groq.Groq(api_key=...)` | Per-instance | `GROQ_API_KEY` |
| 2 | `backend/app/services/groq_client.py` | 57 | `call_groq_completion` | `groq.Groq(api_key=...)` | Created per request & per fallback iteration | `GROQ_API_KEY*` |
| 3 | `backend/app/services/pulse/planner_service.py` | 105 | `get_analysis_plan` | `groq.Groq(api_key=...)` | Created per execution | `PULSE_GROQ_API_KEY` |
| 4 | `backend/app/services/pulse/llm_interpreter.py` | 121 | `interpret_results` | `groq.Groq(api_key=...)` | Created per execution | `PULSE_GROQ_API_KEY` |
| 5 | `backend/app/services/pulse/llm_interpreter.py` | 188 | `llm_reasoning_analysis`| `groq.Groq(api_key=...)` | Created per execution | `PULSE_GROQ_API_KEY` |

---

## 6. Every LLM API Call Site

| Site # | File | Line | Invoking Method | Agent | Target Model | Purpose | Call Frequency & Conditions |
|---|---|---|---|---|---|---|---|
| **1** | `app/services/groq_service.py` | 122 | `generate_plan` | **Mother** | `llama-3.3-70b-versatile` | Natural language query → multi-agent workflow step plan | 1x per workflow planning stage. |
| **2** | `app/services/groq_client.py` | 67 | `call_groq_completion` | **DB (Vault)** | `llama-3.3-70b-versatile` *(fallbacks: `llama-3.1-8b`, `mixtral-8x7b`)* | Structured intent + dynamic live schema → database execution JSON plan | 1x per DB Agent task execution. Loops over fallback keys/models on 429 errors. |
| **3** | `app/services/groq_service.py` | 406 | `extract_data_from_image` | **Input** | `qwen/qwen3.6-27b` | Vision OCR on uploaded image files (`.png`, `.jpg`) | 1x only when an image file path is passed to InputAgent. |
| **4** | `app/services/pulse/planner_service.py` | 122 | `get_analysis_plan` | **Pulse** | `llama-3.3-70b-versatile` | User analytical query + dataset profile → tool execution plan | 1x per AnalyticsAgent task execution when `PULSE_GROQ_API_KEY` is present. |
| **5** | `app/services/pulse/llm_interpreter.py` | 129 | `interpret_results` | **Pulse** | `llama-3.3-70b-versatile` | Tool execution numerical results → human insight string | 1x per AnalyticsAgent execution after tool calculation phase. |
| **6** | `app/services/pulse/llm_interpreter.py` | 189 | `llm_reasoning_analysis`| **Pulse** | `llama-3.3-70b-versatile` | Direct qualitative reasoning on sample records | 1x alternative to #5 when strategy is `llm_reasoning`. |
| **7** | `app/services/groq_service.py` | 339 | `generate_text_report` | **Scribe** | `llama-3.3-70b-versatile` | Formats final data and pulse insights into structured natural text | 1x per OutputAgent execution when format is `text`. |
| **8** | `app/services/groq_service.py` | 290 | `generate_pdf_plan` | **Scribe** | `llama-3.3-70b-versatile` | Generates dynamic section plan for PDF document generation | 1x per OutputAgent execution when format is `pdf`. |
| **9** | `app/services/groq_service.py` | 221 | `generate_ppt_plan` | **Scribe** | `llama-3.3-70b-versatile` | Generates dynamic slide plan for PowerPoint presentation | 1x per OutputAgent execution when format is `pptx`. |

---

## 7. Complete User Request Flow Architecture

```
User Prompt (Frontend)
   │
   ▼
POST /api/orchestrate
   │
   ├── [MotherAgent.create_workflow]
   │     └── synthesize_plan() ──────────────► [LLM CALL #1: GroqService.generate_plan]
   │
   ▼
[Execution Pipeline / CrewAdapter]
   │
   ├── Step 1: InputAgent.execute()
   │     ├── If Text/Excel/PDF: Deterministic Regex/Tokens (0 LLM Calls)
   │     └── If Image File: ──────────────────► [LLM CALL (Vision): extract_data_from_image]
   │
   ├── Step 2: DBAgent.execute()
   │     └── vault_llm_plan() ────────────────► [LLM CALL #2: call_groq_completion]
   │           │
   │           ▼
   │     execute_plan() ──────────────────────► PostgreSQL / Supabase Query (0 LLM Calls)
   │
   ├── Step 3: AnalyticsAgent.execute() (If Analytics / Analyze Mode)
   │     ├── dataset_profiler() ──────────────► Deterministic Profile (0 LLM Calls)
   │     ├── planner_service.py ──────────────► [LLM CALL #3: get_analysis_plan]
   │     ├── analytics_tools.py ──────────────► Python Calculations: avg, min, max, rank (0 LLM Calls)
   │     └── llm_interpreter.py ──────────────► [LLM CALL #4: interpret_results]
   │
   ├── Step 4: OutputAgent.execute()
   │     ├── If Format == "text": ────────────► [LLM CALL #5: generate_text_report]
   │     ├── If Format == "pdf": ─────────────► [LLM CALL #5: generate_pdf_plan]
   │     ├── If Format == "pptx": ────────────► [LLM CALL #5: generate_ppt_plan]
   │     └── If Format == "excel": ───────────► Deterministic OpenPyXL (0 LLM Calls)
   │
   ▼
Response JSON (Result Contract) ─────────────► Frontend UI
```

---

## 8. LLM Calls Per Request Type

| Category | Typical Query | Agents Executed | Expected LLM Calls | Call Breakdown |
|---|---|---|---|---|
| **A. Simple Database Retrieval** | *"Show the CSE students"* | Input, Mother, DB, Scribe | **3** | • #1 Mother Plan<br>• #2 DB Vault Plan<br>• #3 Scribe Text Formatter |
| **B. Complex Academic Analysis** | *"Find academically at-risk students and explain why"* | Input, Mother, DB, Pulse, Scribe | **5** | • #1 Mother Plan<br>• #2 DB Vault Plan<br>• #3 Pulse Analysis Plan<br>• #4 Pulse Insight Interpretation<br>• #5 Scribe Text Formatter |
| **C. Weighted Composite Ranking** | *"Rank top 10 students using 80% marks and 20% attendance"* | Input, Mother, DB, Pulse, Scribe | **5** | • #1 Mother Plan<br>• #2 DB Vault Plan<br>• #3 Pulse Analysis Plan<br>• #4 Pulse Insight Interpretation<br>• #5 Scribe Text Formatter |
| **D. Text Report Request** | *"Provide an analytical summary as text"* | Input, Mother, DB, Pulse, Scribe | **5** | • #1 Mother Plan<br>• #2 DB Vault Plan<br>• #3 Pulse Analysis Plan<br>• #4 Pulse Insight Interpretation<br>• #5 Scribe Text Formatter |
| **E. PDF Report Request** | *"Generate a PDF report on at-risk students"* | Input, Mother, DB, Pulse, Scribe | **5** | • #1 Mother Plan<br>• #2 DB Vault Plan<br>• #3 Pulse Analysis Plan<br>• #4 Pulse Insight Interpretation<br>• #5 Scribe PDF Planner |
| **F. PowerPoint Slide Deck** | *"Create a presentation on student metrics in PPT"* | Input, Mother, DB, Pulse, Scribe | **5** | • #1 Mother Plan<br>• #2 DB Vault Plan<br>• #3 Pulse Analysis Plan<br>• #4 Pulse Insight Interpretation<br>• #5 Scribe PPT Planner |
| **G. Excel Spreadsheet (Read)** | *"Export all students to Excel"* | Input, Mother, DB, Scribe | **2** | • #1 Mother Plan<br>• #2 DB Vault Plan<br>*(Excel generation is 100% deterministic)* |
| **H. Excel Spreadsheet (Analytics)** | *"Export department metrics to Excel"* | Input, Mother, DB, Pulse, Scribe | **4** | • #1 Mother Plan<br>• #2 DB Vault Plan<br>• #3 Pulse Analysis Plan<br>• #4 Pulse Insight Interpretation<br>*(Excel generation is deterministic)* |
| **I. Database Modification** | *"Change Rahul's CGPA to 9.2"* | Input, Mother, DB, Scribe | **3** | • #1 Mother Plan<br>• #2 DB Vault Plan<br>• #3 Scribe Text Formatter |
| **J. Image OCR Query** | Uploaded `image.png` + *"Show top students"* | Input, Mother, DB, Scribe | **4** | • #1 Input Vision OCR<br>• #2 Mother Plan<br>• #3 DB Vault Plan<br>• #4 Scribe Text Formatter |

---

## 9. Fallback & Retry Behavior

### 1. Multi-Key & Multi-Model Vault Failover (`groq_client.py`)
- **Key Discovery:** Dynamically detects all variables prefixed with `GROQ_API_KEY` (`GROQ_API_KEY`, `GROQ_API_KEY_1`, `GROQ_API_KEY_2`, `GROQ_API_KEY_3`, `GROQ_API_KEY_4`).
- **Model Fallback Chain:**
  1. `GROQ_MODEL` (Default: `llama-3.3-70b-versatile`)
  2. `llama-3.1-8b-instant`
  3. `mixtral-8x7b-32768`
- **Rate-Limit Failover Logic:** If an API key encounters an HTTP 429 rate limit or quota exhaustion, it immediately cycles through the remaining keys for that model before cascading to the next model tier.
- **Fail-Safe:** If all keys and models are exhausted, it raises `RuntimeError`, triggering `_deterministic_fallback_plan()`.

### 2. Pulse Agent Fallback (`analytics_agent.py`, `planner_service.py`, `llm_interpreter.py`)
- If `PULSE_GROQ_API_KEY` is not set or the API returns an error:
  - `get_analysis_plan()` returns `None` -> switches to `_build_deterministic_plan()`.
  - Python calculations run natively via `analytics_tools.py`.
  - `interpret_results()` switches to `_deterministic_summary()`.
- Legacy `OrchestrationMetrics` are always computed via standard Python math.

### 3. Scribe Agent Fallback (`text_service.py`, `pdf_service.py`, `ppt_service.py`)
- If `GroqService` text generation or plan synthesis fails:
  - Text format uses `_generate_fallback_text()` with formatted ASCII tables.
  - PDF format generates standard structured ReportLab layout.
  - PPT format builds structured PowerPoint slides using preset layouts.

---

## 10. Token Usage Risks & Analysis

1. **Live Schema Injection in Vault Planner (`vault_planner.py:365`):**
   - Injects the entire schema dictionary (`json.dumps(live_schema)`) into every DB prompt.
   - *Token Cost:* ~500 to 1,200 tokens per call.
2. **Context Window Protection (Good Practice Implemented):**
   - `llm_interpreter.py` slices records to `records[:20]` (max 20 records).
   - `text_service.py` slices records to `records[:15]` (max 15 records).
   - `planner_service.py` receives only column summaries, not raw records.
3. **Vision Base64 Encodings:**
   - Full image base64 is transmitted to `qwen/qwen3.6-27b`, consuming ~1,000–3,500 tokens per image.
4. **Duplicate Payload Transmission:**
   - Pulse generates an LLM insight string; then Scribe passes both the raw sample data AND the Pulse insight to another LLM to format text.

---

## 11. Duplicate / Potential Unnecessary LLM Calls

1. **Mother Agent Plan Synthesis on Simple Queries:**
   - `MotherAgent.classify_intent()` already deterministically categorizes requests (`read`, `write`, `analytics`). Calling Groq to generate a static 3-step plan (`input -> db -> output`) for basic queries adds an unnecessary ~500ms–1.5s latency and consumes API quota.
2. **Double Interpretation (Pulse Interpreter + Scribe Text Formatter):**
   - For analytical requests, Pulse Agent calls an LLM to interpret calculation results into insights.
   - Scribe Agent then calls an LLM a second time to format that insight and data into markdown text. A deterministic template can format Pulse's output directly.
3. **DB Agent Vault Planning for Simple Reads:**
   - Standard queries matching explicit regex patterns (e.g., `"Show CSE students"`) could resolve directly to deterministic plans without invoking Groq completion.

---

## 12. API-Key Separation Analysis

- **Current State:**
  - **Shared Keys:** `GROQ_API_KEY` is shared across Mother, DB Agent, Scribe, and Input (Vision). A quota exhaustion on Scribe or DB planning impacts Mother Agent orchestration.
  - **Isolated Keys:** `PULSE_GROQ_API_KEY` is completely isolated for Pulse Analytics.
  - **Configured vs Used:** `SCRIBE_GROQ_API_KEY` is not wired in code.
- **Architectural Assessment:**
  - Isolating Pulse on `PULSE_GROQ_API_KEY` is effective.
  - Connecting Scribe to `SCRIBE_GROQ_API_KEY` (if provisioned in `.env`) would decouple document rendering from Mother Agent workflow orchestration.

---

## 13. Summary Tables

### Table A: User Request Execution Profile

| Request Category | Agents Involved | Max LLM Calls | Primary Model | Active API Key |
|---|---|---|---|---|
| **Simple DB Retrieval** | Input, Mother, DB, Scribe | **3** | `llama-3.3-70b-versatile` | `GROQ_API_KEY` (+ `_1`..`_4`) |
| **Complex Analysis** | Input, Mother, DB, Pulse, Scribe | **5** | `llama-3.3-70b-versatile` | `GROQ_API_KEY` & `PULSE_GROQ_API_KEY` |
| **Weighted Ranking** | Input, Mother, DB, Pulse, Scribe | **5** | `llama-3.3-70b-versatile` | `GROQ_API_KEY` & `PULSE_GROQ_API_KEY` |
| **Text Report** | Input, Mother, DB, Pulse, Scribe | **5** | `llama-3.3-70b-versatile` | `GROQ_API_KEY` & `PULSE_GROQ_API_KEY` |
| **PDF Document** | Input, Mother, DB, Pulse, Scribe | **5** | `llama-3.3-70b-versatile` | `GROQ_API_KEY` & `PULSE_GROQ_API_KEY` |
| **PowerPoint Deck** | Input, Mother, DB, Pulse, Scribe | **5** | `llama-3.3-70b-versatile` | `GROQ_API_KEY` & `PULSE_GROQ_API_KEY` |
| **Excel Export (Read)** | Input, Mother, DB, Scribe | **2** | `llama-3.3-70b-versatile` | `GROQ_API_KEY` (+ `_1`..`_4`) |
| **Excel Export (Analytics)**| Input, Mother, DB, Pulse, Scribe | **4** | `llama-3.3-70b-versatile` | `GROQ_API_KEY` & `PULSE_GROQ_API_KEY` |
| **DB Modification** | Input, Mother, DB, Scribe | **3** | `llama-3.3-70b-versatile` | `GROQ_API_KEY` (+ `_1`..`_4`) |
| **Image OCR + Read** | Input, Mother, DB, Scribe | **4** | `qwen/qwen3.6-27b` & `llama-3.3-70b` | `GROQ_API_KEY` (+ `_1`..`_4`) |

### Table B: Agent LLM Call Sites & Configuration

| Agent Name | LLM Call Sites | API Key Variable | Default Model | Fallback Mechanism |
|---|---|---|---|---|
| **Input Agent** | 1 (Image Vision) | `GROQ_API_KEY` | `qwen/qwen3.6-27b` | Skips OCR / returns None |
| **Mother Agent** | 1 (Plan Synthesis) | `GROQ_API_KEY` | `llama-3.3-70b-versatile` | Deterministic 3-step / 4-step workflow plan |
| **DB Agent (Vault)** | 1 (SQL Plan) | `GROQ_API_KEY` (+ `_1`..`_4`) | `llama-3.3-70b-versatile` | Multi-key/model failover -> Deterministic SQL plan |
| **Pulse Agent** | 3 (Plan, Interpret, Reason) | `PULSE_GROQ_API_KEY` | `llama-3.3-70b-versatile` | Deterministic tool plan + Python calculations + basic summary |
| **Scribe Agent** | 3 (Text, PDF, PPT) | `GROQ_API_KEY` | `llama-3.3-70b-versatile` | Deterministic text tables, ReportLab PDF, python-pptx |

---

## 14. Confirmation of No Code Changes

- **Zero files modified during this audit.**
- **No environment files or credentials altered.**
- **No API keys created or deleted.**
- **Strictly read-only inspection performed.**
