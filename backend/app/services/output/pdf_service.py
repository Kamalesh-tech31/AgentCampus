"""
pdf_service.py — PDF report generation for Scribe using ReportLab.

Features:
  - Dynamic sections — only renders sections where data is available
  - Sections: Title, Executive Summary, Key Statistics, Data Table,
               Pulse Insights, At-Risk Students
  - Multi-page table support via platypus KeepTogether / TableOfContents
  - Optional embedded charts (PNG bytes from chart_service)
  - Professional styling with colour palette matching the project theme

If the Groq API is available, an LLM acts as a Report Planner to
structure the report intelligently based on the user's request.
Otherwise, falls back to a deterministic rule-based report generation.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.services.output.heading_map import humanize

logger = logging.getLogger(__name__)

# ── ReportLab imports ──────────────────────────────────────────────────────────
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, Image, KeepTogether, PageBreak, ListFlowable, ListItem
    )
    from reportlab.platypus.flowables import Flowable
    _REPORTLAB_OK = True
except ImportError:
    _REPORTLAB_OK = False
    logger.error("[PDFService] reportlab not installed.")

# ── Colours ───────────────────────────────────────────────────────────────────
DARK_BLUE = "#1F4E79"
MID_BLUE = "#2E75B6"
ACCENT_ORANGE = "#C55A11"
LIGHT_GRAY = "#F2F2F2"
BORDER_GRAY = "#BFBFBF"
WHITE = "#FFFFFF"
RED_RISK = "#C00000"

_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "output_files"


def _ensure_output_dir() -> Path:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return _OUTPUT_DIR


def _safe_str(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _build_styles():
    """Return a dict of named ParagraphStyles."""
    base = getSampleStyleSheet()
    styles = {}

    styles["title"] = ParagraphStyle(
        "ReportTitle",
        fontSize=22,
        textColor=colors.HexColor(DARK_BLUE),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )
    styles["subtitle"] = ParagraphStyle(
        "Subtitle",
        fontSize=11,
        textColor=colors.HexColor(MID_BLUE),
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName="Helvetica",
    )
    styles["section_header"] = ParagraphStyle(
        "SectionHeader",
        fontSize=13,
        textColor=colors.HexColor(DARK_BLUE),
        spaceBefore=14,
        spaceAfter=6,
        fontName="Helvetica-Bold",
        borderPad=(0, 0, 2, 0),
        keepWithNext=True,
    )
    styles["body"] = ParagraphStyle(
        "Body",
        fontSize=10,
        textColor=colors.black,
        spaceAfter=4,
        fontName="Helvetica",
        leading=14,
    )
    styles["bullet"] = ParagraphStyle(
        "Bullet",
        fontSize=10,
        textColor=colors.black,
        spaceAfter=3,
        leftIndent=12,
        fontName="Helvetica",
        bulletIndent=4,
        bulletText="•",
    )
    styles["kv_label"] = ParagraphStyle(
        "KVLabel",
        fontSize=10,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        alignment=TA_LEFT,
    )
    styles["kv_value"] = ParagraphStyle(
        "KVValue",
        fontSize=10,
        textColor=colors.black,
        fontName="Helvetica",
        alignment=TA_LEFT,
    )
    return styles


def _kv_table(rows: list[tuple[str, str]], styles: dict) -> Table:
    """Build a two-column key-value table for stats display."""
    data = [[
        Paragraph(label, styles["kv_label"]),
        Paragraph(value, styles["kv_value"]),
    ] for label, value in rows]

    tbl = Table(data, colWidths=[7 * cm, 9 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(MID_BLUE)),
        ("BACKGROUND", (1, 0), (1, -1), colors.HexColor(LIGHT_GRAY)),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("ROWBACKGROUNDS", (1, 0), (1, -1), [colors.HexColor(LIGHT_GRAY), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_GRAY)),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [3]),
    ]))
    return tbl


def _records_table(records: list[dict], styles: dict, max_cols: int = 7) -> Table:
    """Build a data table from student records with dynamic columns."""
    if not records:
        return Paragraph("No data available.", styles["body"])

    all_keys = [k for k in records[0].keys() if k != "id"]
    # Priority order for informative columns when many columns exist
    priority_order = [
        "roll_number", "rollNumber", "name", "department", "cgpa",
        "attendance", "status", "backlogs", "semester", "email", "project_title", "projectTitle"
    ]
    if len(all_keys) > max_cols:
        keys = [k for k in priority_order if k in all_keys]
        for k in all_keys:
            if k not in keys and len(keys) < max_cols:
                keys.append(k)
        keys = keys[:max_cols]
    else:
        keys = all_keys

    headers = [humanize(k) for k in keys]

    th_style = ParagraphStyle(
        "TableHeader",
        parent=styles["body"],
        fontSize=7.5,
        leading=9,
        textColor=colors.white,
    )
    td_style = ParagraphStyle(
        "TableCell",
        parent=styles["body"],
        fontSize=7.5,
        leading=9,
    )

    data = [[Paragraph(f"<b>{h}</b>", th_style) for h in headers]]
    for rec in records:
        row = [Paragraph(_safe_str(rec.get(k)), td_style) for k in keys]
        data.append(row)

    col_count = len(keys)
    page_width = A4[0] - 3 * cm  # subtract margins
    col_w = page_width / col_count

    tbl = Table(data, colWidths=[col_w] * col_count, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(DARK_BLUE)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT_GRAY)]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(BORDER_GRAY)),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def _add_section_header(story: list, title: str, styles: dict, color=MID_BLUE):
    story.append(Paragraph(title, styles["section_header"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(color)))
    story.append(Spacer(1, 0.3 * cm))


def _generate_fallback(story: list, records: list[dict], metrics: Optional[dict], insight: Optional[str], styles: dict, pulse_data: Optional[dict] = None):
    """Deterministic fallback logic for PDF generation."""
    if pulse_data:
        # Dynamic fallback based on Pulse results
        if pulse_data.get("summary"):
            _add_section_header(story, "Executive Summary", styles)
            story.append(Paragraph(pulse_data["summary"], styles["body"]))
            story.append(Spacer(1, 0.5 * cm))

        if pulse_data.get("findings"):
            _add_section_header(story, "Key Findings", styles)
            for f in pulse_data["findings"]:
                story.append(Paragraph(f"• {f}", styles["bullet"]))
            story.append(Spacer(1, 0.5 * cm))

        if pulse_data.get("insights"):
            _add_section_header(story, "Analytics Insights", styles)
            for ins in pulse_data["insights"]:
                story.append(Paragraph(ins, styles["body"]))
            story.append(Spacer(1, 0.5 * cm))

        # Dynamic charts from Pulse
        if pulse_data.get("chart_data"):
            from app.services.output.chart_service import render_dynamic_chart
            for cname, cdata in pulse_data["chart_data"].items():
                try:
                    chart_bytes = render_dynamic_chart(cdata)
                    if chart_bytes:
                        _add_section_header(story, cdata.get("title", "Chart"), styles)
                        img = Image(io.BytesIO(chart_bytes), width=14 * cm, height=7 * cm)
                        story.append(img)
                        story.append(Spacer(1, 0.5 * cm))
                except Exception as exc:
                    logger.warning(f"[PDFService] Fallback chart {cname} failed: {exc}")

        # Dynamic tables from Pulse
        if pulse_data.get("tables"):
            for tname, trows in pulse_data["tables"].items():
                if trows:
                    _add_section_header(story, f"{humanize(tname)} ({len(trows)} records)", styles)
                    story.append(_records_table(trows, styles))
                    story.append(Spacer(1, 0.5 * cm))
        return

    # ── Legacy Executive Summary (when no Pulse data is present) ──────────────
    if records or metrics:
        _add_section_header(story, "Executive Summary", styles)
        summary_parts = []
        if records:
            summary_parts.append(f"This report covers <b>{len(records)}</b> student record(s).")
        if metrics:
            avg = metrics.get("averageCgpa") or metrics.get("average_cgpa")
            if avg is not None:
                summary_parts.append(f"The overall average CGPA is <b>{avg:.2f}</b>.")
            prob = metrics.get("probationCount") or metrics.get("probation_count")
            if prob:
                summary_parts.append(f"<b>{prob}</b> student(s) are currently on academic probation.")

        for part in summary_parts:
            story.append(Paragraph(part, styles["body"]))
        story.append(Spacer(1, 0.5 * cm))

    # ── Key Statistics ────────────────────────────────────────────────────────
    if metrics:
        _add_section_header(story, "Key Statistics", styles)
        kv_rows = []
        stat_map = [
            ("totalRecords", "total_records", "Total Students"),
            ("averageCgpa", "average_cgpa", "Average CGPA"),
            ("highestCgpa", "highest_cgpa", "Highest CGPA"),
            ("lowestCgpa", "lowest_cgpa", "Lowest CGPA"),
            ("avgAttendance", "avg_attendance", "Average Attendance (%)"),
            ("probationCount", "probation_count", "Students on Probation"),
        ]
        for camel, snake, label in stat_map:
            value = metrics.get(camel) or metrics.get(snake)
            if value is not None:
                val_str = f"{value:.2f}" if isinstance(value, float) else str(value)
                kv_rows.append((label, val_str))

        if kv_rows:
            story.append(_kv_table(kv_rows, styles))
            story.append(Spacer(1, 0.5 * cm))

        # Department breakdown
        breakdown = metrics.get("departmentBreakdown") or metrics.get("department_breakdown")
        if breakdown and isinstance(breakdown, dict):
            _add_section_header(story, "Department-wise Breakdown", styles)
            dept_data = [
                [
                    Paragraph("<b>Department</b>", styles["body"]),
                    Paragraph("<b>Student Count</b>", styles["body"]),
                    Paragraph("<b>Avg CGPA</b>", styles["body"]),
                ]
            ]
            for dept, data in breakdown.items():
                if isinstance(data, dict):
                    cnt = data.get("count", 0)
                    avg = data.get("avgCgpa") or data.get("avg_cgpa", 0.0)
                    dept_data.append([
                        Paragraph(dept, styles["body"]),
                        Paragraph(str(cnt), styles["body"]),
                        Paragraph(f"{float(avg):.2f}" if avg else "—", styles["body"]),
                    ])

            dept_tbl = Table(dept_data, colWidths=[8 * cm, 5 * cm, 5 * cm], repeatRows=1)
            dept_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(DARK_BLUE)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT_GRAY)]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(BORDER_GRAY)),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(dept_tbl)
            story.append(Spacer(1, 0.5 * cm))

    # ── Pulse Insight ─────────────────────────────────────────────────────────
    if insight:
        _add_section_header(story, "Analytics Insight", styles)
        story.append(Paragraph(insight, styles["body"]))
        story.append(Spacer(1, 0.5 * cm))

    # ── CGPA Distribution Chart ───────────────────────────────────────────────
    if records:
        try:
            from app.services.output.chart_service import cgpa_distribution_chart
            chart_bytes = cgpa_distribution_chart(records)
            if chart_bytes:
                _add_section_header(story, "CGPA Distribution", styles)
                img = Image(io.BytesIO(chart_bytes), width=14 * cm, height=8 * cm)
                story.append(img)
                story.append(Spacer(1, 0.5 * cm))
        except Exception as exc:
            logger.warning(f"[PDFService] Could not embed CGPA chart: {exc}")

    # ── Department Breakdown Chart ────────────────────────────────────────────
    if metrics:
        breakdown = metrics.get("departmentBreakdown") or metrics.get("department_breakdown")
        if breakdown:
            try:
                from app.services.output.chart_service import department_breakdown_chart
                chart_bytes = department_breakdown_chart(breakdown)
                if chart_bytes:
                    _add_section_header(story, "Department Performance Chart", styles)
                    img = Image(io.BytesIO(chart_bytes), width=14 * cm, height=7 * cm)
                    story.append(img)
                    story.append(Spacer(1, 0.5 * cm))
            except Exception as exc:
                logger.warning(f"[PDFService] Could not embed dept chart: {exc}")

    # ── Student Data Table ────────────────────────────────────────────────────
    if records:
        story.append(PageBreak())
        _add_section_header(story, f"Student Data ({len(records)} records)", styles)
        story.append(_records_table(records, styles))
        story.append(Spacer(1, 0.5 * cm))

    # ── At-Risk Students ─────────────────────────────────────────────────────
    if records:
        at_risk = [
            r for r in records
            if (r.get("status") == "Probation" or float(r.get("cgpa", 10.0)) < 6.5)
        ]
        if at_risk:
            _add_section_header(story, f"At-Risk Students ({len(at_risk)})", styles, color=RED_RISK)

            for r in at_risk:
                name = r.get("name", r.get("rollNumber", "Unknown"))
                cgpa = r.get("cgpa", "?")
                dept = r.get("department", "?")
                status = r.get("status", "?")
                cgpa_str = f"{float(cgpa):.2f}" if isinstance(cgpa, (int, float)) else str(cgpa)
                story.append(Paragraph(
                    f"• <b>{name}</b> — {dept} | CGPA: {cgpa_str} | Status: {status}",
                    styles["body"]
                ))
            story.append(Spacer(1, 0.5 * cm))

    # ── No Data Fallback ─────────────────────────────────────────────────────
    if not records and not metrics:
        story.append(Paragraph("No data available for the requested query.", styles["body"]))


def _execute_plan(story: list, plan: Any, records: list[dict], metrics: Optional[dict], styles: dict, pulse_data: Optional[dict] = None):
    """Executes the dynamically generated PDF plan."""
    if plan.executive_summary:
        _add_section_header(story, "Executive Summary", styles)
        story.append(Paragraph(plan.executive_summary, styles["body"]))
        story.append(Spacer(1, 0.5 * cm))

    for section in plan.sections:
        _add_section_header(story, section.title, styles)

        # Render text content if provided
        if section.content and section.type != "table" and section.type != "chart":
            story.append(Paragraph(section.content, styles["body"]))
            story.append(Spacer(1, 0.3 * cm))

        # Handle specific section types
        if section.type == "table":
            tbl_name = section.content
            target_data = None
            if pulse_data and pulse_data.get("tables") and tbl_name in pulse_data["tables"]:
                target_data = pulse_data["tables"][tbl_name]
            elif records:
                target_data = records

            if target_data:
                story.append(_records_table(target_data, styles))
            else:
                story.append(Paragraph("No data available for table.", styles["body"]))
            story.append(Spacer(1, 0.5 * cm))

        elif section.type == "chart" or section.recommended_chart:
            chart_bytes = None
            chart_key = section.recommended_chart or section.content

            # Attempt dynamic chart from Pulse
            if pulse_data and pulse_data.get("chart_data") and chart_key in pulse_data["chart_data"]:
                try:
                    from app.services.output.chart_service import render_dynamic_chart
                    chart_bytes = render_dynamic_chart(pulse_data["chart_data"][chart_key])
                except Exception as exc:
                    logger.warning(f"[PDFService] Dynamic chart rendering failed: {exc}")

            # Fallbacks to standard legacy charts
            if not chart_bytes and chart_key == "cgpa_distribution" and records:
                try:
                    from app.services.output.chart_service import cgpa_distribution_chart
                    chart_bytes = cgpa_distribution_chart(records)
                except Exception:
                    pass
            elif not chart_bytes and chart_key == "department_performance" and metrics:
                breakdown = metrics.get("departmentBreakdown") or metrics.get("department_breakdown")
                if breakdown:
                    try:
                        from app.services.output.chart_service import department_breakdown_chart
                        chart_bytes = department_breakdown_chart(breakdown)
                    except Exception:
                        pass

            if chart_bytes:
                img = Image(io.BytesIO(chart_bytes), width=14 * cm, height=8 * cm)
                story.append(img)
                story.append(Spacer(1, 0.5 * cm))
            else:
                story.append(Paragraph("Chart data unavailable.", styles["body"]))

        elif section.type == "statistics" and metrics:
            kv_rows = []
            stat_map = [
                ("totalRecords", "total_records", "Total Students"),
                ("averageCgpa", "average_cgpa", "Average CGPA"),
                ("highestCgpa", "highest_cgpa", "Highest CGPA"),
                ("lowestCgpa", "lowest_cgpa", "Lowest CGPA"),
                ("avgAttendance", "avg_attendance", "Average Attendance (%)"),
                ("probationCount", "probation_count", "Students on Probation"),
            ]
            for camel, snake, label in stat_map:
                value = metrics.get(camel) or metrics.get(snake)
                if value is not None:
                    val_str = f"{value:.2f}" if isinstance(value, float) else str(value)
                    kv_rows.append((label, val_str))

            if kv_rows:
                story.append(_kv_table(kv_rows, styles))
                story.append(Spacer(1, 0.5 * cm))


def generate_pdf(
    records: list[dict],
    metrics: Optional[dict],
    insight: Optional[str],
    user_query: str = "",
    file_stem: str = "student_report",
    pulse_data: Optional[dict] = None,
) -> dict:
    """
    Generate a PDF report and return file metadata.
    Attempts to plan dynamically with Groq LLM, falls back to deterministic if unavailable.
    """
    if not _REPORTLAB_OK:
        raise RuntimeError("reportlab is required for PDF generation but is not installed.")

    styles = _build_styles()
    story: list = []

    # ── Attempt LLM Planning ───────────────────────────────────────────────────
    from app.services.groq_service import GroqService
    groq_svc = GroqService()

    # Build data summary for the LLM
    summary_parts = []
    summary_parts.append(f"Records Available: {len(records)}")
    if records:
        at_risk = len([r for r in records if float(r.get("cgpa", 10.0)) < 6.5])
        summary_parts.append(f"At-Risk Students (Legacy Threshold): {at_risk}")
    if metrics:
        avg = metrics.get("averageCgpa") or metrics.get("average_cgpa")
        if avg:
            summary_parts.append(f"Average CGPA: {avg:.2f}")
        breakdown = metrics.get("departmentBreakdown") or metrics.get("department_breakdown")
        if breakdown:
            summary_parts.append(f"Departments: {', '.join(breakdown.keys())}")

    if pulse_data:
        summary_parts.append("\nPULSE ANALYTICS RESULTS:")
        summary_parts.append(f"Summary: {pulse_data.get('summary')}")
        if pulse_data.get("findings"):
            summary_parts.append("Findings:")
            for f in pulse_data["findings"]:
                summary_parts.append(f"  - {f}")
        if pulse_data.get("insights"):
            summary_parts.append("Insights:")
            for ins in pulse_data["insights"]:
                summary_parts.append(f"  - {ins}")
        if pulse_data.get("tables"):
            summary_parts.append(f"Available Tables: {', '.join(pulse_data['tables'].keys())}")
        if pulse_data.get("chart_data"):
            summary_parts.append(f"Available Charts: {', '.join(pulse_data['chart_data'].keys())}")

    data_summary = "\n".join(summary_parts)

    plan = groq_svc.generate_pdf_plan(user_query, data_summary)

    # ── Title Page ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph("AgentCampus", styles["subtitle"]))

    # Dynamically select title based on request or plan
    title_text = "Student Analysis Report"
    if plan and plan.report_title:
        title_text = plan.report_title
    elif pulse_data and pulse_data.get("analysis_type"):
        title_text = f"{pulse_data['analysis_type'].replace('_', ' ').title()} Report"
    elif "at risk" in user_query.lower():
        title_text = "Academic Risk Assessment"

    story.append(Paragraph(title_text, styles["title"]))
    if plan and plan.report_type:
        story.append(Paragraph(plan.report_type, styles["subtitle"]))

    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor(DARK_BLUE)))
    story.append(Spacer(1, 0.4 * cm))

    generated_at = datetime.now().strftime("%d %B %Y, %I:%M %p")
    story.append(Paragraph(f"Generated: {generated_at}", styles["subtitle"]))
    if user_query:
        story.append(Paragraph(f'Query: <i>"{user_query}"</i>', styles["subtitle"]))
    story.append(Spacer(1, 1.0 * cm))

    if plan:
        logger.info("[PDFService] Executing Groq LLM Report Plan.")
        try:
            _execute_plan(story, plan, records, metrics, styles, pulse_data=pulse_data)
        except Exception as exc:
            logger.error(f"[PDFService] Error executing PDF plan: {exc}. Falling back to deterministic.")
            plan = None

    if not plan:
        logger.info("[PDFService] Using deterministic fallback generation.")
        _generate_fallback(story, records, metrics, insight, styles, pulse_data=pulse_data)

    # ── Footer note ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.0 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(BORDER_GRAY)))
    story.append(Paragraph(
        "This report was automatically generated by AgentCampus Scribe Agent.",
        ParagraphStyle("Footer", fontSize=8, textColor=colors.gray, alignment=TA_CENTER),
    ))

    # ── Build PDF ─────────────────────────────────────────────────────────────
    out_dir = _ensure_output_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{file_stem}_{timestamp}.pdf"
    file_path = str(out_dir / file_name)

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=title_text,
        author="AgentCampus Scribe",
    )

    def add_page_number(canvas, doc):
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.drawRightString(20 * cm, 1 * cm, text)

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    logger.info(f"[PDFService] Saved PDF report: {file_path}")

    return {
        "file_path": file_path,
        "file_name": file_name,
    }
