"""
output_agent.py — Scribe / Output Agent

Responsibility:
  Receives already-prepared results from Vault (DBAgent) and/or Pulse
  (AnalyticsAgent) and converts them into the format requested by the user.

  DOES NOT:
    - Query or mutate the database
    - Control or invoke other agents
    - Perform document extraction
    - Change workflow routing

Supported output formats:
  - text   : Plain structured text response (default)
  - excel  : .xlsx spreadsheet (openpyxl)
  - pdf    : .pdf report (ReportLab)
  - pptx   : .pptx presentation (python-pptx)

Format detection:
  Keyword-based detection from the original user_query string.
  Falls back to "text" for unrecognised or missing format hints.

Backward compatibility:
  result["summary"]  — still present (MotherAgent reads this)
  result["result"]   — OrchestrationResult model_dump (existing tests read this)
  result["output_format"] — NEW additive field
  result["output_file"]   — NEW additive field (None for text)
"""

import logging
from typing import Any, Optional

from app.agents.base import BaseAgent
from app.mother.types import AgentTask, AgentResult
from app.contracts import OrchestrationResult, OrchestrationMetrics

logger = logging.getLogger(__name__)

# ── Format keyword map ─────────────────────────────────────────────────────────
_FORMAT_KEYWORDS: dict[str, list[str]] = {
    "excel": ["excel", "xlsx", "spreadsheet", "csv", "table format", "download"],
    "pdf": ["pdf", "report", "document", "printable", "generate report"],
    "pptx": ["ppt", "pptx", "powerpoint", "presentation", "slides", "slide deck"],
}


def _detect_format(query: str) -> str:
    """
    Detect requested output format from natural-language query string.

    Returns one of: "text", "excel", "pdf", "pptx".
    Falls back to "text" if no format keyword is found.
    """
    q = query.lower()
    # Check text first to prevent matching "report" to pdf when it says "text report"
    text_kws = ["plain text", "written answer", "text report", "write an answer", "directly as text", "in text", "as text"]
    if any(kw in q for kw in text_kws):
        return "text"
    for fmt, keywords in _FORMAT_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return fmt
    return "text"


def _extract_records(input_data: dict) -> list[dict]:
    """Safely extract raw records from DBAgent result."""
    db_result = input_data.get("db", {})
    return db_result.get("records", []) if isinstance(db_result, dict) else []


def _extract_sql(input_data: dict) -> Optional[str]:
    """Safely extract executed SQL from DBAgent result."""
    db_result = input_data.get("db", {})
    return db_result.get("sql") if isinstance(db_result, dict) else None


def _extract_metrics(input_data: dict) -> Optional[dict]:
    """Safely extract OrchestrationMetrics dict from AnalyticsAgent result."""
    analytics_result = input_data.get("analytics", {})
    if not isinstance(analytics_result, dict):
        return None
    raw_metrics = analytics_result.get("metrics")
    return raw_metrics if isinstance(raw_metrics, dict) else None


def _extract_insight(input_data: dict) -> Optional[str]:
    """Safely extract insight string from AnalyticsAgent result."""
    analytics_result = input_data.get("analytics", {})
    if not isinstance(analytics_result, dict):
        return None
    return analytics_result.get("insight")


def _extract_pulse_data(input_data: dict) -> Optional[dict]:
    """Safely extract the full Pulse analytics dict if available."""
    analytics_result = input_data.get("analytics")
    if isinstance(analytics_result, dict) and ("summary" in analytics_result or "findings" in analytics_result):
        return analytics_result
    return None


def _build_summary(
    records: list[dict],
    metrics: Optional[dict],
    output_format: str,
    file_info: Optional[dict] = None,
) -> str:
    """Build the human-readable summary string stored in result['summary']."""
    parts = []

    if records:
        parts.append(f"Retrieved {len(records)} student record(s).")

    if metrics:
        avg = metrics.get("averageCgpa") or metrics.get("average_cgpa")
        if avg is not None:
            parts.append(f"Average CGPA is {avg:.2f}.")

    if not parts:
        parts.append("No data available for the requested query.")

    if output_format != "text" and file_info:
        parts.append(f"Report generated as {output_format.upper()}: {file_info.get('file_name', '')}")

    return " ".join(parts)


def _build_orchestration_result(
    records: list[dict],
    metrics_dict: Optional[dict],
    sql: Optional[str],
    summary: str,
    output_format: str,
    output_file: Optional[str],
    affected_count: Optional[int] = None,
    sql_metadata: Optional[dict] = None,
) -> OrchestrationResult:
    """
    Build and validate the OrchestrationResult contract model.
    Preserves all existing fields for backward compatibility and attaches SQL inspection metadata.
    """
    from app.contracts.students import StudentRecord

    validated_metrics: Optional[OrchestrationMetrics] = None
    if metrics_dict:
        try:
            validated_metrics = OrchestrationMetrics.model_validate(metrics_dict)
        except Exception as exc:
            logger.warning(f"[Scribe] Could not validate metrics: {exc}")

    parsed_records = []
    if isinstance(records, list) and records:
        for r in records:
            if isinstance(r, dict):
                try:
                    parsed_records.append(StudentRecord.model_validate(r))
                except Exception:
                    # Fall back to creating a StudentRecord with best effort
                    try:
                        parsed_records.append(StudentRecord(**r))
                    except Exception:
                        pass

    # Extract metadata attributes
    sql_meta = sql_metadata or {}
    req_lim = sql_meta.get("requested_limit")
    rows_ret = sql_meta.get("rows_returned", len(records))
    op = sql_meta.get("operation", "SELECT" if sql and "SELECT" in sql.upper() else None)
    tbl = sql_meta.get("table", "students")

    return OrchestrationResult(
        summary=summary,
        query_executed=sql,
        mutation_executed=sql if sql and any(kw in sql.upper() for kw in ("UPDATE", "INSERT", "DELETE", "ALTER", "CREATE")) else None,
        affected_count=affected_count if affected_count is not None else len(records),
        data=parsed_records if parsed_records else None,
        metrics=validated_metrics,
        csv_data=None,
        output_format=output_format,
        output_file=output_file,
        sql=sql,
        requested_limit=req_lim,
        rows_returned=rows_ret,
        operation=op,
        table=tbl,
        sql_metadata=sql_meta if sql_meta else None,
        success=True,
    )


class OutputAgent(BaseAgent):
    """
    Scribe / Output Agent — transforms prepared results into requested format.

    Coordinate of output pipeline:

        SCRIBE
           |
      Detected Format
           |
      ┌────┼────┬────┐
     TEXT EXCEL PDF PPT
    """

    name = "output"

    def execute(self, task: AgentTask) -> AgentResult:
        """
        Execute the output transformation.

        Reads input_data accumulated from prior agents:
          input_data["db"]        → Vault records
          input_data["analytics"] → Pulse metrics + insight
          input_data["user_query"] → Original user query (for format detection)

        Returns an AgentResult whose result dict contains:
          "summary"       — plain text summary (required by MotherAgent)
          "result"        — OrchestrationResult model dump (required by existing tests)
          "output_format" — format string
          "output_file"   — file path (for file formats) or None
          "text_content"  — formatted text (for text format)
        """
        try:
            return self._execute_safe(task)
        except Exception as exc:
            logger.exception(f"[Scribe] Unhandled error in OutputAgent.execute: {exc}")
            return AgentResult(
                task_id=task.task_id,
                agent=self.name,
                status="failed",
                error=f"Scribe agent encountered an unexpected error: {str(exc)}",
            )

    def _execute_safe(self, task: AgentTask) -> AgentResult:
        input_data: dict[str, Any] = task.input_data

        # ── Extract data from upstream agents ──────────────────────────────────
        records = _extract_records(input_data)
        sql = _extract_sql(input_data)
        metrics_dict = _extract_metrics(input_data)
        insight = _extract_insight(input_data)
        pulse_data = _extract_pulse_data(input_data)
        user_query = str(input_data.get("user_query", ""))

        # ── Detect requested output format ────────────────────────────────────
        output_format = _detect_format(user_query)
        logger.info(f"[Scribe] Requested format: {output_format}")
        logger.info(f"[Scribe] Records received: {len(records)}")
        logger.info(f"[Scribe] Analytics received: {'yes' if metrics_dict else 'no'}")

        # ── Route to the appropriate output service ───────────────────────────
        output_file: Optional[str] = None
        text_content: Optional[str] = None
        file_info: Optional[dict] = None
        format_error: Optional[str] = None

        if output_format == "text":
            logger.info(f"[Scribe] Generating file: (None, text output)")
            text_content = self._generate_text(records, metrics_dict, insight, user_query, pulse_data)
            logger.info(f"[Scribe] File generated successfully: (Text content returned)")

        elif output_format == "excel":
            try:
                logger.info(f"[Scribe] Generating file: .xlsx")
                from app.services.output.excel_service import generate_excel
                # Keep backward compatibility, pass pulse_data as kwarg
                file_info = generate_excel(records, metrics_dict, insight, pulse_data=pulse_data)
                output_file = file_info.get("file_path")
                logger.info(f"[Scribe] File generated successfully: {output_file}")
            except Exception as exc:
                format_error = f"Excel generation failed: {str(exc)}"
                logger.error(f"[Scribe] {format_error}")
                # Graceful degradation — fall back to text
                output_format = "text"
                text_content = self._generate_text(records, metrics_dict, insight, user_query, pulse_data)
                text_content += f"\n\n[Note: {format_error}]"

        elif output_format == "pdf":
            try:
                logger.info(f"[Scribe] Generating file: .pdf")
                from app.services.output.pdf_service import generate_pdf
                file_info = generate_pdf(records, metrics_dict, insight, user_query, pulse_data=pulse_data)
                output_file = file_info.get("file_path")
                logger.info(f"[Scribe] File generated successfully: {output_file}")
            except Exception as exc:
                format_error = f"PDF generation failed: {str(exc)}"
                logger.error(f"[Scribe] {format_error}")
                output_format = "text"
                text_content = self._generate_text(records, metrics_dict, insight, user_query, pulse_data)
                text_content += f"\n\n[Note: {format_error}]"

        elif output_format == "pptx":
            try:
                logger.info(f"[Scribe] Generating file: .pptx")
                from app.services.output.ppt_service import generate_ppt
                file_info = generate_ppt(records, metrics_dict, insight, user_query, pulse_data=pulse_data)
                output_file = file_info.get("file_path")
                logger.info(f"[Scribe] File generated successfully: {output_file}")
            except Exception as exc:
                format_error = f"PPT generation failed: {str(exc)}"
                logger.error(f"[Scribe] {format_error}")
                output_format = "text"
                text_content = self._generate_text(records, metrics_dict, insight, user_query, pulse_data)
                text_content += f"\n\n[Note: {format_error}]"

        else:
            # Unsupported / unknown format — fall back to text
            logger.warning(f"[Scribe] Unsupported output format '{output_format}'; falling back to text.")
            output_format = "text"
            text_content = self._generate_text(records, metrics_dict, insight, user_query)

        # ── Build summary & affected_count ────────────────────────────────────
        db_res = input_data.get("db", {})
        affected_count = (
            db_res.get("rows_updated")
            if isinstance(db_res, dict) and db_res.get("rows_updated") is not None
            else (db_res.get("count") if isinstance(db_res, dict) else len(records))
        )
        if isinstance(db_res, dict) and db_res.get("message") and any(w in db_res.get("message", "").lower() for w in ("updated", "deleted", "inserted", "bulk update")):
            summary = db_res["message"]
        elif text_content:
            summary = text_content
            if output_format != "text" and file_info:
                summary += f"\n\n[Report generated as {output_format.upper()}: {file_info.get('file_name', '')}]"
        else:
            summary = _build_summary(records, metrics_dict, output_format, file_info)

        # ── Build OrchestrationResult (backward-compatible contract) ──────────
        result_contract = _build_orchestration_result(
            records=records,
            metrics_dict=metrics_dict,
            sql=sql,
            summary=summary,
            output_format=output_format,
            output_file=output_file,
            affected_count=affected_count,
            sql_metadata=db_res if isinstance(db_res, dict) else {},
        )

        # ── Assemble AgentResult ──────────────────────────────────────────────
        result_payload: dict[str, Any] = {
            "summary": summary,
            "result": result_contract.model_dump(by_alias=True),
            "output_format": output_format,
            "output_file": output_file,
        }

        if text_content is not None:
            result_payload["text_content"] = text_content

        if file_info is not None:
            result_payload["file_info"] = file_info

        if format_error is not None:
            result_payload["format_error"] = format_error

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status="completed",
            result=result_payload,
        )

    @staticmethod
    def _generate_text(
        records: list[dict],
        metrics_dict: Optional[dict],
        insight: Optional[str],
        user_query: str,
        pulse_data: Optional[dict] = None,
    ) -> str:
        """Generate structured text output, with safe fallback."""
        try:
            from app.services.output.text_service import generate_text
            return generate_text(records, metrics_dict, insight, user_query, pulse_data=pulse_data)
        except Exception as exc:
            logger.error(f"[Scribe] TextService error: {exc}")
            # Ultra-minimal fallback
            lines = [f"Records: {len(records)}"]
            if metrics_dict:
                avg = metrics_dict.get("averageCgpa") or metrics_dict.get("average_cgpa")
                if avg:
                    lines.append(f"Average CGPA: {avg:.2f}")
            if insight:
                lines.append(f"Insight: {insight}")
            return "\n".join(lines) or "No data available."