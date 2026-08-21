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

    # ── 1. Special Handling for Weighted Ranking ──────────────────────────────
    if pulse_data and (pulse_data.get("analysis_type") == "weighted_ranking" or "ranking" in pulse_data):
        formula = pulse_data.get("formula", "Weighted Score = ((CGPA / 10) × 100 × 0.80) + (Attendance × 0.20)")
        top_recs = pulse_data.get("ranking") or (pulse_data.get("tables", {}).get("top_performers", []))
        top_n = pulse_data.get("top_n", len(top_recs))
        total_recs = pulse_data.get("records_analyzed", len(records))

        sections.append("=" * 60)
        sections.append("ACADEMIC PERFORMANCE & WEIGHTED RANKING REPORT".center(60))
        sections.append("=" * 60)
        sections.append("")
        sections.append(f"Analysis Pool: {total_recs} students analyzed")
        sections.append(f"Scoring Model: 80% Academic Performance, 20% Attendance")
        sections.append(f"Formula: {formula}\n")

        sections.append(f"TOP {len(top_recs)} CONFIRMED PERFORMERS:")
        sections.append("-" * 60)
        for i, r in enumerate(top_recs):
            rk = r.get("rank", i + 1)
            name = r.get("name", r.get("rollNumber", "Unknown"))
            roll = r.get("rollNumber", "")
            dept = r.get("department", "")
            cgpa = r.get("cgpa", 0.0)
            att = r.get("attendance", 0.0)
            acad_pts = r.get("academic_contribution", round(float(cgpa) * 8.0, 2))
            att_pts = r.get("attendance_contribution", round(float(att) * 0.20, 2))
            w_score = r.get("_weighted_score", r.get("weighted_score", 0.0))

            roll_str = f" ({roll})" if roll else ""
            sections.append(
                f"  {rk:>2}. {name}{roll_str:<14} | {dept:<18} | CGPA: {cgpa:.2f} ({acad_pts:.2f} pts) | Att: {att:.0f}% ({att_pts:.2f} pts) | Score: {w_score:.2f}"
            )
        sections.append("")

        # Tie details
        ties = pulse_data.get("ties", [])
        if ties:
            sections.append("TIE INFORMATION & RESOLUTION:")
            sections.append("-" * 60)
            sections.append(f"  • {pulse_data.get('tie_breaking_rule', 'Ties resolved deterministically.')}")
            for t in ties[:3]:
                sections.append(f"  • Score {t['weighted_score']:.2f} collision between {t['count']} students: {', '.join(t['students'][:3])}")
            sections.append("")

        # Key Insight
        if insight:
            sections.append("ANALYSIS INSIGHT & OBSERVATIONS:")
            sections.append("-" * 60)
            sections.append(f"  {insight}\n")

        sections.append("=" * 60)
        return "\n".join(sections)

    # ── 2. Special Handling for Academic Risk Analysis ────────────────────────
    if pulse_data and (pulse_data.get("analysis_type") == "risk_analysis" or "at_risk" in pulse_data or "at_risk_students" in pulse_data.get("tables", {})):
        at_risk_recs = pulse_data.get("at_risk") or pulse_data.get("tables", {}).get("at_risk_students", [])
        total_recs = pulse_data.get("total_records", pulse_data.get("records_analyzed", len(records)))
        at_risk_count = pulse_data.get("at_risk_count", len(at_risk_recs))
        safe_count = pulse_data.get("safe_count", total_recs - at_risk_count)
        at_risk_pct = pulse_data.get("at_risk_percentage", round((at_risk_count / max(1, total_recs)) * 100.0, 1))

        sections.append("=" * 65)
        sections.append("ACADEMIC RISK ASSESSMENT & EARLY INTERVENTION REPORT".center(65))
        sections.append("=" * 65)
        sections.append("")
        sections.append(f"Cohort Scope: {total_recs} students analyzed")
        sections.append(f"At-Risk Identified: {at_risk_count} ({at_risk_pct}% of cohort) | Safe: {safe_count}")

        # Dominant Pattern
        dom_pat = pulse_data.get("dominant_risk_pattern")
        if dom_pat:
            sections.append(f"\nDOMINANT VULNERABILITY PATTERN:\n  • {dom_pat}\n")

        # Severity Breakdown
        sev_dist = pulse_data.get("severity_distribution", {})
        if sev_dist:
            sections.append("SEVERITY CLASSIFICATION BREAKDOWN:")
            sections.append("-" * 65)
            sev_str = " | ".join([f"{k}: {v}" for k, v in sev_dist.items()])
            sections.append(f"  {sev_str}\n")

        # Risk Factors
        factors = pulse_data.get("factor_frequencies", {})
        if factors:
            sections.append("RISK INDICATOR PREVALENCE:")
            sections.append("-" * 65)
            for fac, cnt in factors.items():
                sections.append(f"  • {fac:<32}: {cnt:>3} students")
            sections.append("")

        # Top Priority Students Roster
        sections.append(f"HIGHEST PRIORITY AT-RISK STUDENTS (Top {min(10, len(at_risk_recs))} of {at_risk_count}):")
        sections.append("-" * 65)
        for i, s in enumerate(at_risk_recs[:10]):
            rk = s.get("risk_rank", i + 1)
            name = s.get("name", "Student")
            roll = s.get("rollNumber", "")
            dept = s.get("department", "")
            cgpa = s.get("cgpa", 0.0)
            att = s.get("attendance", 0.0)
            sev = s.get("risk_severity", "Moderate")
            reasons = s.get("risk_reasons_str") or ", ".join([f["label"] for f in s.get("risk_flags", [])]) or "At-risk"

            roll_str = f" ({roll})" if roll else ""
            sections.append(f"  {rk:>2}. [{sev.upper():<8}] {name}{roll_str} | {dept}")
            sections.append(f"      Metrics: CGPA {cgpa:.2f} | Att {att:.0f}% | Status: {s.get('status', 'Active')} | Backlogs: {s.get('backlogs', 0)}")
            sections.append(f"      Reasons: {reasons}")
        sections.append("")

        if len(at_risk_recs) > 10:
            sections.append(f"  [ℹ] Showing top 10 priority cases above. All {at_risk_count} at-risk records are available in the generated PDF report and data viewer.\n")

        # Recommendations
        recs = pulse_data.get("data_driven_recommendations", [])
        if recs:
            sections.append("DATA-DRIVEN ACTION RECOMMENDATIONS:")
            sections.append("-" * 65)
            for r in recs:
                sections.append(f"  • {r}")
            sections.append("")

        sections.append("=" * 65)
        return "\n".join(sections)

    # ── 3. Special Handling for Correlation Analysis ──────────────────────────
    if pulse_data and (pulse_data.get("analysis_type") == "correlation_analysis" or "correlation" in pulse_data):
        f1 = pulse_data.get("field1_label") or pulse_data.get("field1") or "Attendance"
        f2 = pulse_data.get("field2_label") or pulse_data.get("field2") or "CGPA"
        r_val = pulse_data.get("correlation", 0.0)
        r_sq = pulse_data.get("r_squared", round(r_val ** 2, 4))
        strength = pulse_data.get("strength", "")
        direction = pulse_data.get("direction", "")
        reg = pulse_data.get("regression", {})
        interp = pulse_data.get("interpretation")

        sections.append("=" * 65)
        sections.append(f"BIVARIATE CORRELATION REPORT: {f1.upper()} vs {f2.upper()}".center(65))
        sections.append("=" * 65)
        sections.append("")
        sections.append(f"Observation Count (N): {pulse_data.get('records_analyzed', len(records))} paired observations")
        sections.append(f"Pearson Correlation (r): {r_val} ({strength.upper()} {direction.upper()} association)")
        sections.append(f"Coefficient of Determination (R²): {r_sq} ({r_sq * 100:.1f}% explained variance)\n")

        if reg.get("formula"):
            sections.append("LINEAR REGRESSION MODEL:")
            sections.append("-" * 65)
            sections.append(f"  Fitted Equation: {reg['formula']}")
            sections.append(f"  Slope (m): {reg.get('slope')} | Intercept (b): {reg.get('intercept')}\n")

        # Descriptive stats
        f1_stats = pulse_data.get("field1_stats", {})
        f2_stats = pulse_data.get("field2_stats", {})
        if f1_stats and f2_stats:
            sections.append("DESCRIPTIVE DIMENSION STATISTICS:")
            sections.append("-" * 65)
            sections.append(f"  • {f1:<16}: Mean={f1_stats.get('mean')}, StdDev={f1_stats.get('std_dev')}, Range=[{f1_stats.get('min')} - {f1_stats.get('max')}]")
            sections.append(f"  • {f2:<16}: Mean={f2_stats.get('mean')}, StdDev={f2_stats.get('std_dev')}, Range=[{f2_stats.get('min')} - {f2_stats.get('max')}]\n")

        if interp:
            sections.append("ANALYTICAL INTERPRETATION & LIMITATIONS:")
            sections.append("-" * 65)
            sections.append(f"  {interp}\n")

        sections.append("=" * 65)
        return "\n".join(sections)

    # ── 4. Standard Reports ───────────────────────────────────────────────────
    user_q_lower = (user_query or "").lower()
    wants_risk = any(k in user_q_lower for k in ("risk", "at-risk", "at risk", "probation", "failing", "intervention"))

    if pulse_data and pulse_data.get("analysis_type"):
        title = f"{pulse_data['analysis_type'].replace('_', ' ').upper()} REPORT"
    elif wants_risk:
        title = "ACADEMIC RISK ASSESSMENT REPORT"
    elif metrics:
        title = "STUDENT ANALYSIS REPORT"
    elif any(k in user_q_lower for k in ("top ", "top-", "highest", "lowest", "rank", "best")):
        title = f"{user_query.strip().upper()}" if len(user_query.strip()) <= 50 else "STUDENT RANKING RESULTS"
    else:
        title = "STUDENT RECORDS"

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
                sections.append(_format_records_table(trows[:25]))
                sections.append("")
    else:
        # Fallback to legacy metrics (only if metrics were calculated)
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
            rec_header = f"STUDENT RECORD (1 result):" if len(records) == 1 else f"STUDENT RECORDS ({len(records)} total):"
            sections.append(rec_header)
            sections.append("-" * 40)
            sections.append(_format_records_table(records))
            sections.append("")

        # ── At-Risk Students Fallback (strictly request-scoped) ───────────────
        if records and wants_risk:
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
    from app.services.groq_service import GroqService
    import os
    groq_svc = GroqService(
        api_key=os.getenv("SCRIBE_GROQ_API_KEY"),
        model=os.getenv("SCRIBE_GROQ_MODEL", "llama-3.3-70b-versatile"),
    )

    # Build data summary for the LLM (always compact and verified)
    summary_data = {}
    if pulse_data and (pulse_data.get("analysis_type") == "weighted_ranking" or "ranking" in pulse_data):
        summary_data["analysis_type"] = "weighted_ranking"
        summary_data["formula"] = pulse_data.get("formula")
        summary_data["weights"] = pulse_data.get("weights")
        summary_data["top_ranking_verified"] = pulse_data.get("ranking", [])[:12]
        summary_data["total_records"] = pulse_data.get("records_analyzed", len(records))
        summary_data["statistics"] = pulse_data.get("statistics")
        summary_data["ties"] = pulse_data.get("ties", [])[:3]
        summary_data["tie_breaking_rule"] = pulse_data.get("tie_breaking_rule")
        if insight:
            summary_data["insight"] = insight
    else:
        if records:
            summary_data["records_sample"] = records[:12]
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

    data_summary = json.dumps(summary_data, indent=2, default=str)

    llm_text = groq_svc.generate_text_report(user_query, data_summary)

    if llm_text:
        logger.info("[TextService] Using Groq LLM generated text report.")
        return llm_text

    # ── Fallback ──────────────────────────────────────────────────────────────
    logger.info("[TextService] Using deterministic fallback generation.")
    return _generate_fallback_text(records, metrics, insight, user_query, pulse_data=pulse_data)
