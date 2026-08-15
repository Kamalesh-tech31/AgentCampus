"""
text_service.py — Plain structured text output for Scribe.

Handles all three input cases:
  - CASE 1: Vault records only
  - CASE 2: Pulse/Analytics metrics only
  - CASE 3: Both records and metrics

If the Groq API is available, an LLM acts as a Text Output Formatter to
generate a well-structured, natural-language response.
Otherwise, falls back to a deterministic rule-based text generation.
"""

from typing import Any, Optional
import json
import logging
from app.services.output.heading_map import humanize

logger = logging.getLogger(__name__)

# Fields to skip entirely in the auto-generated data table
_SKIP_FIELDS = {"id"}


def _safe_str(value: Any) -> str:
    """Convert any value to a readable string, handling None gracefully."""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _format_records_table(records: list[dict]) -> str:
    """Render a list of dicts as a fixed-width text table."""
    if not records:
        return "  (No records available)"

    # Collect columns, skip internal IDs
    all_keys = []
    for key in records[0].keys():
        if key not in _SKIP_FIELDS:
            all_keys.append(key)

    headers = [humanize(k) for k in all_keys]

    # Compute column widths
    col_widths = [len(h) for h in headers]
    rows_data: list[list[str]] = []
    for rec in records:
        row = [_safe_str(rec.get(k)) for k in all_keys]
        rows_data.append(row)
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    # Build header row
    sep = "  "
    header_line = sep.join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    divider = sep.join("-" * w for w in col_widths)

    lines = [header_line, divider]
    for row in rows_data:
        lines.append(sep.join(cell.ljust(col_widths[i]) for i, cell in enumerate(row)))

    return "\n".join(lines)


def _format_metrics(metrics: dict) -> str:
    """Render OrchestrationMetrics dict as a readable summary block."""
    lines: list[str] = []

    scalar_fields = [
        ("totalRecords", "total_records"),
        ("averageCgpa", "average_cgpa"),
        ("highestCgpa", "highest_cgpa"),
        ("lowestCgpa", "lowest_cgpa"),
        ("avgAttendance", "avg_attendance"),
        ("probationCount", "probation_count"),
    ]

    for camel, snake in scalar_fields:
        value = metrics.get(camel) or metrics.get(snake)
        if value is not None:
            label = humanize(camel)
            val_str = f"{value:.2f}" if isinstance(value, float) else str(value)
            lines.append(f"  {label:<28} {val_str}")

    # Department breakdown
    breakdown = metrics.get("departmentBreakdown") or metrics.get("department_breakdown")
    if breakdown:
        lines.append("")
        lines.append("  DEPARTMENT BREAKDOWN:")
        lines.append("  " + "-" * 48)
        for dept, data in breakdown.items():
            if isinstance(data, dict):
                count = data.get("count", "?")
                avg = data.get("avgCgpa") or data.get("avg_cgpa", "?")
                avg_str = f"{avg:.2f}" if isinstance(avg, float) else str(avg)
                lines.append(f"    {dept:<24}  Students: {count:<4}  Avg CGPA: {avg_str}")

    return "\n".join(lines)


def _generate_fallback_text(
    records: list[dict],
    metrics: Optional[dict],
    insight: Optional[str],
    user_query: str = "",
    pulse_data: Optional[dict] = None,
) -> str:
    """Deterministic fallback logic for text generation."""
    sections: list[str] = []

    # ── Dynamic Title based on request ────────────────────────────────────────
    title = "STUDENT ANALYSIS REPORT"
    if pulse_data and pulse_data.get("analysis_type"):
        title = f"{pulse_data['analysis_type'].replace('_', ' ').upper()} REPORT"
    elif "at risk" in user_query.lower() or "attention" in user_query.lower():
        title = "ACADEMIC RISK ASSESSMENT REPORT"

    sections.append("=" * 60)
    sections.append(title.center(60))
    sections.append("=" * 60)

    if user_query:
        sections.append(f"\nQuery: {user_query}\n")

    # ── Pulse Data summary ────────────────────────────────────────────────────
    if pulse_data:
        if pulse_data.get("summary"):
            sections.append("SUMMARY:")
            sections.append("-" * 40)
            sections.append(f"  {pulse_data['summary']}\n")

        if pulse_data.get("findings"):
            sections.append("FINDINGS:")
            sections.append("-" * 40)
            for f in pulse_data["findings"]:
                sections.append(f"  • {f}")
            sections.append("")

        if pulse_data.get("insights"):
            sections.append("INSIGHTS:")
            sections.append("-" * 40)
            for ins in pulse_data["insights"]:
                sections.append(f"  • {ins}")
            sections.append("")

        if pulse_data.get("tables"):
            for tname, trows in pulse_data["tables"].items():
                sections.append(f"TABLE: {humanize(tname).upper()} ({len(trows)} rows):")
                sections.append("-" * 40)
                sections.append(_format_records_table(trows))
                sections.append("")
    else:
        # Fallback to legacy metrics
        if metrics:
            sections.append("KEY STATISTICS:")
            sections.append("-" * 40)
            sections.append(_format_metrics(metrics))
            sections.append("")

        if insight:
            sections.append("ANALYSIS INSIGHT:")
            sections.append("-" * 40)
            sections.append(f"  {insight}")
            sections.append("")

        if records:
            sections.append(f"STUDENT RECORDS  ({len(records)} total):")
            sections.append("-" * 40)
            sections.append(_format_records_table(records))
            sections.append("")

        # ── At-Risk Students Fallback ─────────────────────────────────────────
        if records:
            at_risk = [
                r for r in records
                if (r.get("status") == "Probation" or float(r.get("cgpa", 10.0)) < 6.5)
            ]
            if at_risk:
                sections.append(f"AT-RISK STUDENTS  ({len(at_risk)} identified):")
                sections.append("-" * 40)
                for r in at_risk:
                    name = r.get("name", r.get("rollNumber", "Unknown"))
                    cgpa = r.get("cgpa", "?")
                    dept = r.get("department", "?")
                    status = r.get("status", "?")
                    cgpa_str = f"{float(cgpa):.2f}" if isinstance(cgpa, (int, float)) else str(cgpa)
                    sections.append(f"  • {name}  |  {dept}  |  CGPA: {cgpa_str}  |  Status: {status}")
                sections.append("")

    # ── No Data Fallback ─────────────────────────────────────────────────────
    if not records and not metrics and not pulse_data:
        sections.append("No data available for the requested query.")

    sections.append("=" * 60)
    return "\n".join(sections)


def generate_text(
    records: list[dict],
    metrics: Optional[dict],
    insight: Optional[str],
    user_query: str = "",
    pulse_data: Optional[dict] = None,
) -> str:
    """
    Generate structured plain-text output.
    Attempts to use Groq LLM for natural formatting, falls back to deterministic if unavailable.

    Args:
        records:    List of student record dicts from Vault agent.
        metrics:    OrchestrationMetrics dict from Pulse agent (or None).
        insight:    Natural-language insight string from Pulse agent (or None).
        user_query: Original user query for context header.
        pulse_data: Pulse analytics result dictionary (or None).

    Returns:
        A multi-line string ready for display.
    """
    # ── Attempt LLM Generation ───────────────────────────────────────────────────
    from app.services.groq_service import GroqService
    groq_svc = GroqService()

    # Build data summary for the LLM
    summary_data = {}
    if records:
        # Pass a sample of records to avoid blowing up the context window
        summary_data["records_sample"] = records[:15]
        summary_data["total_records"] = len(records)
    if metrics:
        summary_data["metrics"] = metrics
    if insight:
        summary_data["insight"] = insight
    if pulse_data:
        summary_data["pulse_data"] = {
            "summary": pulse_data.get("summary"),
            "findings": pulse_data.get("findings"),
            "insights": pulse_data.get("insights"),
            "table_names": list(pulse_data.get("tables", {}).keys()),
            "chart_keys": list(pulse_data.get("chart_data", {}).keys()),
        }

    data_summary = json.dumps(summary_data, indent=2)

    llm_text = groq_svc.generate_text_report(user_query, data_summary)

    if llm_text:
        logger.info("[TextService] Using Groq LLM generated text report.")
        return llm_text

    # ── Fallback ──────────────────────────────────────────────────────────────
    logger.info("[TextService] Using deterministic fallback generation.")
    return _generate_fallback_text(records, metrics, insight, user_query, pulse_data=pulse_data)
