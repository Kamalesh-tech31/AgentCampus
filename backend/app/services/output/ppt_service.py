"""
ppt_service.py — PowerPoint (.pptx) generation for Scribe using python-pptx.

Dynamic slide structure — slides are only added when the corresponding
data actually exists. No empty placeholder slides are created.

If the Groq API is available, an LLM acts as a Presentation Planner to
structure the presentation intelligently based on the user's request.
Otherwise, falls back to a deterministic rule-based slide generation.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    _PPTX_OK = True
except ImportError:
    _PPTX_OK = False
    logger.error("[PPTService] python-pptx not installed.")

from app.services.output.heading_map import humanize

_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "output_files"

# ── Color palette ──────────────────────────────────────────────────────────────
_DARK_BLUE = RGBColor(0x1F, 0x4E, 0x79)
_MID_BLUE = RGBColor(0x2E, 0x75, 0xB6)
_ORANGE = RGBColor(0xC5, 0x5A, 0x11)
_LIGHT_GRAY = RGBColor(0xF2, 0xF2, 0xF2)
_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
_BLACK = RGBColor(0x00, 0x00, 0x00)
_RED = RGBColor(0xC0, 0x00, 0x00)


def _ensure_output_dir() -> Path:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return _OUTPUT_DIR


def _safe_str(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


# ── Slide builders ─────────────────────────────────────────────────────────────

def _add_title_slide(prs: "Presentation", user_query: str, title: str = "Student Performance Report", subtitle: str = "AgentCampus — Scribe Agent") -> None:
    """Slide 1: Title."""
    layout = prs.slide_layouts[0]  # Title Slide layout
    slide = prs.slides.add_slide(layout)

    # Title
    title_ph = slide.shapes.title
    title_ph.text = title
    tf = title_ph.text_frame.paragraphs[0]
    tf.font.size = Pt(36)
    tf.font.bold = True
    tf.font.color.rgb = _DARK_BLUE

    # Subtitle
    subtitle_ph = slide.placeholders[1]
    subtitle_tf = subtitle_ph.text_frame
    subtitle_tf.text = subtitle
    p2 = subtitle_tf.add_paragraph()
    p2.text = f"Generated: {datetime.now().strftime('%d %B %Y, %I:%M %p')}"
    if user_query:
        p3 = subtitle_tf.add_paragraph()
        p3.text = f'Query: "{user_query}"'
        p3.font.italic = True
        p3.font.size = Pt(12)


def _add_generic_text_slide(prs: "Presentation", title: str, points: list[str], insights: Optional[str] = None, color: RGBColor = _BLACK) -> None:
    """Generic slide for text points and insights."""
    layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(layout)
    slide.shapes.title.text = title
    _style_title(slide.shapes.title)

    tf = slide.placeholders[1].text_frame
    tf.clear()
    
    first = True
    for pt in points:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.text = pt
        p.font.size = Pt(18)
        p.font.color.rgb = color
        
    if insights:
        p = tf.add_paragraph() if not first else tf.paragraphs[0]
        p.text = insights
        p.font.size = Pt(16)
        p.font.italic = True
        p.font.color.rgb = _DARK_BLUE


def _add_summary_slide(prs: "Presentation", records: list[dict], metrics: Optional[dict]) -> None:
    """Fallback Slide 2: Executive Summary."""
    points: list[str] = []
    if records:
        points.append(f"Total students in this report: {len(records)}")
    if metrics:
        avg = metrics.get("averageCgpa") or metrics.get("average_cgpa")
        if avg is not None:
            points.append(f"Overall average CGPA: {avg:.2f}")
        prob = metrics.get("probationCount") or metrics.get("probation_count")
        if prob:
            points.append(f"Students on academic probation: {prob}")
        highest = metrics.get("highestCgpa") or metrics.get("highest_cgpa")
        if highest:
            points.append(f"Highest CGPA recorded: {highest:.2f}")
        avg_att = metrics.get("avgAttendance") or metrics.get("avg_attendance")
        if avg_att is not None:
            points.append(f"Average attendance: {avg_att:.1f}%")

    if records and not metrics:
        at_risk = [r for r in records if float(r.get("cgpa", 10.0)) < 6.5]
        if at_risk:
            points.append(f"Students identified as at-risk: {len(at_risk)}")

    _add_generic_text_slide(prs, "Executive Summary", points)


def _add_stats_slide(prs: "Presentation", metrics: dict) -> None:
    """Fallback Slide 3: Key Statistics."""
    stat_map = [
        ("totalRecords", "total_records", "Total Students"),
        ("averageCgpa", "average_cgpa", "Average CGPA"),
        ("highestCgpa", "highest_cgpa", "Highest CGPA"),
        ("lowestCgpa", "lowest_cgpa", "Lowest CGPA"),
        ("avgAttendance", "avg_attendance", "Average Attendance (%)"),
        ("probationCount", "probation_count", "On Probation"),
    ]
    points = []
    for camel, snake, label in stat_map:
        value = metrics.get(camel) or metrics.get(snake)
        if value is not None:
            val_str = f"{value:.2f}" if isinstance(value, float) else str(value)
            points.append(f"{label}:  {val_str}")
            
    _add_generic_text_slide(prs, "Key Statistics", points, color=_DARK_BLUE)


def _add_department_slide(prs: "Presentation", breakdown: dict) -> None:
    """Fallback Slide 4: Department Breakdown."""
    points = []
    for dept, data in breakdown.items():
        if isinstance(data, dict):
            cnt = data.get("count", 0)
            avg = data.get("avgCgpa") or data.get("avg_cgpa", 0.0)
            avg_str = f"{float(avg):.2f}" if avg else "—"
            points.append(f"{dept}:  {cnt} students  |  Avg CGPA: {avg_str}")
            
    _add_generic_text_slide(prs, "Department Breakdown", points)


def _add_insight_slide(prs: "Presentation", insight: str) -> None:
    """Fallback Slide 5: Analytics Insight."""
    _add_generic_text_slide(prs, "Analytics Insight", [], insights=insight)


def _add_data_table_slide(prs: "Presentation", records: list[dict], title: str = "Student Data") -> None:
    """Slide 6: Student Data (up to 15 rows for readability)."""
    MAX_ROWS = 15
    sample = records[:MAX_ROWS]

    layout = prs.slide_layouts[5]  # Blank layout (more space)
    slide = prs.slides.add_slide(layout)

    # Title text box
    txBox = slide.shapes.add_textbox(Inches(0.3), Inches(0.15), Inches(9), Inches(0.5))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    
    title_suffix = f" (showing {len(sample)} of {len(records)})" if len(records) > MAX_ROWS else ""
    p.text = title + title_suffix
    p.font.size = Pt(20)
    p.font.bold = True
    p.font.color.rgb = _DARK_BLUE

    if not sample:
        return

    keys = [k for k in sample[0].keys() if k != "id"]
    headers = [humanize(k) for k in keys]

    n_cols = len(keys)
    n_rows = len(sample) + 1  # +1 for header

    slide_width = prs.slide_width
    slide_height = prs.slide_height
    tbl_left = Inches(0.3)
    tbl_top = Inches(0.9)
    tbl_width = slide_width - Inches(0.6)
    tbl_height = slide_height - Inches(1.2)

    table = slide.shapes.add_table(
        n_rows, n_cols, tbl_left, tbl_top, tbl_width, tbl_height
    ).table

    col_width = tbl_width // n_cols
    for i in range(n_cols):
        table.columns[i].width = col_width

    # Header row
    for col_idx, header in enumerate(headers):
        cell = table.cell(0, col_idx)
        cell.text = header
        cell.text_frame.paragraphs[0].font.size = Pt(9)
        cell.text_frame.paragraphs[0].font.bold = True
        cell.text_frame.paragraphs[0].font.color.rgb = _WHITE
        cell.fill.solid()
        cell.fill.fore_color.rgb = _DARK_BLUE

    # Data rows
    for row_idx, rec in enumerate(sample, start=1):
        bg = _LIGHT_GRAY if row_idx % 2 == 0 else _WHITE
        for col_idx, key in enumerate(keys):
            cell = table.cell(row_idx, col_idx)
            cell.text = _safe_str(rec.get(key))
            cell.text_frame.paragraphs[0].font.size = Pt(8)
            cell.text_frame.paragraphs[0].font.color.rgb = _BLACK
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg


def _add_at_risk_slide(prs: "Presentation", at_risk: list[dict]) -> None:
    """Fallback Slide 7: At-Risk Students."""
    points = []
    for r in at_risk[:12]:  # Cap at 12 for slide readability
        name = r.get("name", r.get("rollNumber", "Unknown"))
        cgpa = r.get("cgpa", "?")
        dept = r.get("department", "?")
        status = r.get("status", "?")
        cgpa_str = f"{float(cgpa):.2f}" if isinstance(cgpa, (int, float)) else str(cgpa)
        points.append(f"{name}  —  {dept}  |  CGPA: {cgpa_str}  |  {status}")
        
    _add_generic_text_slide(prs, f"At-Risk Students ({len(at_risk)})", points, color=_RED)


def _add_chart_slide(prs: "Presentation", chart_bytes: bytes, title: str) -> None:
    """Add a slide with an embedded PNG chart image."""
    layout = prs.slide_layouts[5]  # Blank
    slide = prs.slides.add_slide(layout)

    txBox = slide.shapes.add_textbox(Inches(0.3), Inches(0.1), Inches(9), Inches(0.5))
    p = txBox.text_frame.paragraphs[0]
    p.text = title
    p.font.size = Pt(20)
    p.font.bold = True
    p.font.color.rgb = _DARK_BLUE

    pic_stream = io.BytesIO(chart_bytes)
    slide.shapes.add_picture(pic_stream, Inches(0.5), Inches(0.8), width=Inches(9))


def _style_title(shape, color: RGBColor = None) -> None:
    """Apply consistent title styling."""
    for para in shape.text_frame.paragraphs:
        for run in para.runs:
            run.font.bold = True
            run.font.size = Pt(28)
            run.font.color.rgb = color or _DARK_BLUE
    # Also set frame-level font
    shape.text_frame.paragraphs[0].font.bold = True
    shape.text_frame.paragraphs[0].font.color.rgb = color or _DARK_BLUE


def _generate_recommendations(records: list[dict], metrics: Optional[dict]) -> list[str]:
    """Heuristically generate recommendations from available data."""
    recs = []
    if metrics:
        avg = metrics.get("averageCgpa") or metrics.get("average_cgpa", 0.0)
        if avg and avg < 7.0:
            recs.append("Consider academic support programmes — average CGPA is below 7.0.")
        prob = metrics.get("probationCount") or metrics.get("probation_count", 0)
        if prob and prob > 0:
            recs.append(f"Arrange counselling sessions for the {prob} student(s) on probation.")
        avg_att = metrics.get("avgAttendance") or metrics.get("avg_attendance", 100.0)
        if avg_att and avg_att < 80:
            recs.append("Investigate attendance issues — average is below 80%.")

    if records:
        low_att = [r for r in records if float(r.get("attendance", 100)) < 75]
        if low_att:
            recs.append(f"{len(low_att)} student(s) have attendance below 75% — require intervention.")

    if not recs:
        recs.append("Overall performance is satisfactory. Continue monitoring trends.")

    return recs


def _add_multi_data_table_slides(prs: "Presentation", records: list[dict], title: str) -> int:
    """Add one or more table slides, splitting content in chunks of 15."""
    if not records:
        return 0
    chunk_size = 15
    chunks = [records[i:i + chunk_size] for i in range(0, len(records), chunk_size)]
    for idx, chunk in enumerate(chunks):
        suffix = f" (Part {idx + 1})" if len(chunks) > 1 else ""
        _add_data_table_slide(prs, chunk, title=title + suffix)
    return len(chunks)


def _add_split_text_slides(prs: "Presentation", title: str, points: list[str], insights: Optional[str] = None, color: RGBColor = _BLACK) -> int:
    """Add one or more text slides, splitting key points in chunks of 5."""
    if not points:
        _add_generic_text_slide(prs, title, [], insights, color)
        return 1

    chunk_size = 5
    chunks = [points[i:i + chunk_size] for i in range(0, len(points), chunk_size)]
    for idx, chunk in enumerate(chunks):
        suffix = f" (Part {idx + 1})" if len(chunks) > 1 else ""
        ins = insights if idx == len(chunks) - 1 else None
        _add_generic_text_slide(prs, title + suffix, chunk, ins, color)
    return len(chunks)


def _add_recommendations_slide(prs: "Presentation", recommendations: list[str]) -> None:
    """Fallback Slide: Recommendations."""
    _add_split_text_slides(prs, "Recommendations", [f"• {r}" for r in recommendations], color=_BLACK)


# ── LLM Plan Execution ─────────────────────────────────────────────────────────

def _execute_plan(prs: "Presentation", plan: Any, records: list[dict], metrics: Optional[dict], user_query: str, pulse_data: Optional[dict] = None) -> int:
    """Executes the dynamically generated PPT plan."""
    _add_title_slide(prs, user_query, title=plan.presentation_title, subtitle=plan.presentation_subtitle)
    slide_count = 1

    for slide_plan in sorted(plan.slides, key=lambda s: s.priority):
        if slide_plan.slide_type == "title":
            continue  # Already handled above

        elif slide_plan.slide_type == "table":
            tbl_name = slide_plan.slide_title.lower().replace(" ", "_")
            target_data = None
            if pulse_data and pulse_data.get("tables"):
                for k, v in pulse_data["tables"].items():
                    if k in tbl_name or tbl_name in k:
                        target_data = v
                        break
            if not target_data and records:
                target_data = records

            if target_data:
                slide_count += _add_multi_data_table_slides(prs, target_data, title=slide_plan.slide_title)
            else:
                slide_count += _add_split_text_slides(prs, slide_plan.slide_title, slide_plan.key_points, slide_plan.insights)

        elif slide_plan.slide_type == "chart" or slide_plan.recommended_chart:
            chart_bytes = None
            chart_key = slide_plan.recommended_chart or slide_plan.slide_title.lower().replace(" ", "_")

            # Attempt dynamic chart from Pulse
            if pulse_data and pulse_data.get("chart_data") and chart_key in pulse_data["chart_data"]:
                try:
                    from app.services.output.chart_service import render_dynamic_chart
                    chart_bytes = render_dynamic_chart(pulse_data["chart_data"][chart_key])
                except Exception as exc:
                    logger.warning(f"[PPTService] Dynamic chart failed: {exc}")

            # Legacy chart fallbacks
            if not chart_bytes and (slide_plan.recommended_chart == "cgpa_distribution" or "distribution" in chart_key) and records:
                try:
                    from app.services.output.chart_service import cgpa_distribution_chart
                    chart_bytes = cgpa_distribution_chart(records)
                except Exception:
                    pass
            elif not chart_bytes and (slide_plan.recommended_chart == "department_performance" or "department" in chart_key) and metrics:
                breakdown = metrics.get("departmentBreakdown") or metrics.get("department_breakdown")
                if breakdown:
                    try:
                        from app.services.output.chart_service import department_breakdown_chart
                        chart_bytes = department_breakdown_chart(breakdown)
                    except Exception:
                        pass

            if chart_bytes:
                _add_chart_slide(prs, chart_bytes, slide_plan.slide_title)
                slide_count += 1
            else:
                slide_count += _add_split_text_slides(prs, slide_plan.slide_title, slide_plan.key_points, slide_plan.insights)

        else:
            # Generic text slide for kpi_dashboard, insights, recommendation, conclusion
            color = _BLACK
            if slide_plan.slide_type == "recommendation":
                color = _ORANGE
            elif slide_plan.slide_type == "kpi_dashboard":
                color = _DARK_BLUE

            slide_count += _add_split_text_slides(prs, slide_plan.slide_title, slide_plan.key_points, slide_plan.insights, color=color)

    return slide_count


def _generate_fallback_ppt(
    prs: "Presentation",
    records: list[dict],
    metrics: Optional[dict],
    insight: Optional[str],
    user_query: str,
    pulse_data: Optional[dict] = None
) -> int:
    """Deterministic fallback ppt generation."""
    _add_title_slide(prs, user_query)
    slide_count = 1

    if pulse_data:
        # Dynamic fallback based on Pulse results
        if pulse_data.get("summary"):
            _add_generic_text_slide(prs, "Executive Summary", [pulse_data["summary"]])
            slide_count += 1

        if pulse_data.get("findings"):
            slide_count += _add_split_text_slides(prs, "Key Findings", pulse_data["findings"])

        if pulse_data.get("insights"):
            slide_count += _add_split_text_slides(prs, "Analytics Insights", pulse_data["insights"])

        # Render charts as slides
        if pulse_data.get("chart_data"):
            from app.services.output.chart_service import render_dynamic_chart
            for cname, cdata in pulse_data["chart_data"].items():
                try:
                    chart_bytes = render_dynamic_chart(cdata)
                    if chart_bytes:
                        _add_chart_slide(prs, chart_bytes, cdata.get("title", "Chart"))
                        slide_count += 1
                except Exception as exc:
                    logger.warning(f"[PPTService] Fallback chart failed: {exc}")

        # Render tables as slides
        if pulse_data.get("tables"):
            for tname, trows in pulse_data["tables"].items():
                if trows:
                    slide_count += _add_multi_data_table_slides(prs, trows, humanize(tname))
        return slide_count

    # Legacy fallback behavior when pulse_data is not present
    if records or metrics:
        _add_summary_slide(prs, records, metrics)
        slide_count += 1

    if metrics:
        _add_stats_slide(prs, metrics)
        slide_count += 1

        breakdown = metrics.get("departmentBreakdown") or metrics.get("department_breakdown")
        if breakdown and isinstance(breakdown, dict) and len(breakdown) > 0:
            _add_department_slide(prs, breakdown)
            slide_count += 1

    if insight:
        _add_insight_slide(prs, insight)
        slide_count += 1

    if records:
        try:
            from app.services.output.chart_service import cgpa_distribution_chart
            chart_bytes = cgpa_distribution_chart(records)
            if chart_bytes:
                _add_chart_slide(prs, chart_bytes, "CGPA Distribution")
                slide_count += 1
        except Exception as exc:
            logger.warning(f"[PPTService] Could not embed chart: {exc}")

    if metrics:
        breakdown = metrics.get("departmentBreakdown") or metrics.get("department_breakdown")
        if breakdown:
            try:
                from app.services.output.chart_service import department_breakdown_chart
                chart_bytes = department_breakdown_chart(breakdown)
                if chart_bytes:
                    _add_chart_slide(prs, chart_bytes, "Department Performance")
                    slide_count += 1
            except Exception as exc:
                logger.warning(f"[PPTService] Could not embed dept chart: {exc}")

    if records:
        slide_count += _add_multi_data_table_slides(prs, records, "Student Data")

        at_risk = [
            r for r in records
            if (r.get("status") == "Probation" or float(r.get("cgpa", 10.0)) < 6.5)
        ]
        if at_risk:
            _add_at_risk_slide(prs, at_risk)
            slide_count += 1

    recommendations = _generate_recommendations(records, metrics)
    _add_recommendations_slide(prs, recommendations)
    slide_count += 1

    return slide_count


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_ppt(
    records: list[dict],
    metrics: Optional[dict],
    insight: Optional[str],
    user_query: str = "",
    file_stem: str = "student_report",
    pulse_data: Optional[dict] = None,
) -> dict:
    """
    Generate a PowerPoint presentation and return file metadata.
    Attempts to plan dynamically with Groq LLM, falls back to deterministic if unavailable.
    """
    if not _PPTX_OK:
        raise RuntimeError("python-pptx is required for PPT generation but is not installed.")

    prs = Presentation()
    # Widescreen layout (13.33 x 7.5 inches)
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    slide_count = 0

    from app.services.groq_service import GroqService
    import os
    groq_svc = GroqService(
        api_key=os.getenv("SCRIBE_GROQ_API_KEY"),
        model=os.getenv("SCRIBE_GROQ_MODEL", "llama-3.3-70b-versatile"),
    )

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

    plan = groq_svc.generate_ppt_plan(user_query, data_summary)

    if plan:
        logger.info("[PPTService] Executing Groq LLM Presentation Plan.")
        try:
            slide_count = _execute_plan(prs, plan, records, metrics, user_query, pulse_data=pulse_data)
        except Exception as exc:
            logger.error(f"[PPTService] Error executing PPT plan: {exc}. Falling back to deterministic.")
            plan = None  # Force fallback

    # ── Fallback ──────────────────────────────────────────────────────────────
    if not plan:
        logger.info("[PPTService] Using deterministic fallback generation.")
        slide_count = _generate_fallback_ppt(prs, records, metrics, insight, user_query, pulse_data=pulse_data)

    # ── Save ──────────────────────────────────────────────────────────────────
    out_dir = _ensure_output_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{file_stem}_{timestamp}.pptx"
    file_path = str(out_dir / file_name)

    prs.save(file_path)
    logger.info(f"[PPTService] Saved PowerPoint: {file_path}")

    return {
        "file_path": file_path,
        "file_name": file_name,
        "slide_count": slide_count,
    }
