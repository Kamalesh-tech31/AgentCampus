"""
chart_service.py — Optional matplotlib chart generation for Scribe.

Charts are produced as in-memory PNG bytes and can be embedded into:
  - PDF reports (via ReportLab ImageReader)
  - PowerPoint presentations (via python-pptx add_picture)
  - Excel files (via openpyxl add_image)

All functions return None if:
  - matplotlib is not installed
  - Insufficient data to produce a meaningful chart
"""

from typing import Optional
import io
import logging

logger = logging.getLogger(__name__)

_MATPLOTLIB_AVAILABLE = False
try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend — safe for server use
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    _MATPLOTLIB_AVAILABLE = True
except ImportError:
    logger.warning("[ChartService] matplotlib not installed — charts will be skipped.")


def _png_bytes(fig) -> bytes:
    """Render a matplotlib Figure to PNG bytes and close the figure."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def cgpa_distribution_chart(records: list[dict]) -> Optional[bytes]:
    """
    Horizontal bar chart showing each student's CGPA.

    Returns None if matplotlib is unavailable or fewer than 2 records.
    """
    if not _MATPLOTLIB_AVAILABLE or len(records) < 2:
        return None

    try:
        names = [r.get("name", r.get("rollNumber", f"Student {i}")) for i, r in enumerate(records)]
        cgpas = [float(r.get("cgpa", 0.0)) for r in records]

        # Limit to top 20 for readability
        if len(names) > 20:
            paired = sorted(zip(cgpas, names), reverse=True)[:20]
            cgpas, names = zip(*[(c, n) for c, n in paired])

        fig, ax = plt.subplots(figsize=(8, max(4, len(names) * 0.4)))
        colors = ["#e74c3c" if c < 6.5 else "#f39c12" if c < 7.5 else "#2ecc71" for c in cgpas]
        bars = ax.barh(range(len(names)), cgpas, color=colors, edgecolor="white", height=0.6)

        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=8)
        ax.set_xlabel("CGPA", fontsize=10)
        ax.set_title("Student CGPA Distribution", fontsize=12, fontweight="bold")
        ax.set_xlim(0, 10)
        ax.axvline(x=6.5, color="#e74c3c", linestyle="--", linewidth=0.8, alpha=0.6, label="At-Risk (<6.5)")
        ax.legend(fontsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Value labels
        for bar, val in zip(bars, cgpas):
            ax.text(
                bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}", va="center", fontsize=7
            )

        fig.tight_layout()
        return _png_bytes(fig)

    except Exception as exc:
        logger.error(f"[ChartService] cgpa_distribution_chart error: {exc}")
        return None


def attendance_chart(records: list[dict]) -> Optional[bytes]:
    """
    Bar chart of attendance percentage per student.

    Returns None if matplotlib is unavailable or fewer than 2 records.
    """
    if not _MATPLOTLIB_AVAILABLE or len(records) < 2:
        return None

    try:
        names = [r.get("name", f"S{i}") for i, r in enumerate(records)]
        attendances = [float(r.get("attendance", 0.0)) for r in records]

        # Limit to top 20
        if len(names) > 20:
            names = names[:20]
            attendances = attendances[:20]

        fig, ax = plt.subplots(figsize=(8, max(4, len(names) * 0.4)))
        colors = ["#e74c3c" if a < 75 else "#f39c12" if a < 85 else "#3498db" for a in attendances]
        bars = ax.barh(range(len(names)), attendances, color=colors, edgecolor="white", height=0.6)

        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=8)
        ax.set_xlabel("Attendance (%)", fontsize=10)
        ax.set_title("Student Attendance", fontsize=12, fontweight="bold")
        ax.set_xlim(0, 105)
        ax.axvline(x=75, color="#e74c3c", linestyle="--", linewidth=0.8, alpha=0.6, label="Min Required (75%)")
        ax.legend(fontsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        for bar, val in zip(bars, attendances):
            ax.text(
                bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{val:.0f}%", va="center", fontsize=7
            )

        fig.tight_layout()
        return _png_bytes(fig)

    except Exception as exc:
        logger.error(f"[ChartService] attendance_chart error: {exc}")
        return None


def department_breakdown_chart(dept_breakdown: dict) -> Optional[bytes]:
    """
    Grouped bar chart comparing student count and average CGPA by department.

    Returns None if matplotlib unavailable or fewer than 2 departments.
    """
    if not _MATPLOTLIB_AVAILABLE or not dept_breakdown or len(dept_breakdown) < 2:
        return None

    try:
        depts = list(dept_breakdown.keys())
        counts = []
        avg_cgpas = []
        for d in depts:
            data = dept_breakdown[d]
            if isinstance(data, dict):
                counts.append(data.get("count", 0))
                avg_cgpas.append(data.get("avgCgpa") or data.get("avg_cgpa", 0.0))
            else:
                counts.append(0)
                avg_cgpas.append(0.0)

        x = range(len(depts))
        fig, ax1 = plt.subplots(figsize=(max(8, len(depts) * 1.5), 5))

        width = 0.4
        bars1 = ax1.bar([i - width / 2 for i in x], counts, width=width,
                        color="#3498db", label="Student Count", alpha=0.85)
        ax1.set_ylabel("Student Count", color="#3498db", fontsize=10)
        ax1.tick_params(axis="y", labelcolor="#3498db")

        ax2 = ax1.twinx()
        bars2 = ax2.bar([i + width / 2 for i in x], avg_cgpas, width=width,
                        color="#e67e22", label="Avg CGPA", alpha=0.85)
        ax2.set_ylabel("Average CGPA", color="#e67e22", fontsize=10)
        ax2.tick_params(axis="y", labelcolor="#e67e22")
        ax2.set_ylim(0, 10)

        ax1.set_xticks(list(x))
        ax1.set_xticklabels(depts, rotation=15, ha="right", fontsize=9)
        ax1.set_title("Department-wise Performance", fontsize=12, fontweight="bold")

        patches = [
            mpatches.Patch(color="#3498db", label="Student Count"),
            mpatches.Patch(color="#e67e22", label="Avg CGPA"),
        ]
        ax1.legend(handles=patches, loc="upper left", fontsize=9)
        ax1.spines["top"].set_visible(False)

        fig.tight_layout()
        return _png_bytes(fig)

    except Exception as exc:
        logger.error(f"[ChartService] department_breakdown_chart error: {exc}")
        return None


def ranking_bar_chart(top_records: list[dict], title: str = "Top Performers by Weighted Score") -> Optional[bytes]:
    """
    Render a horizontal bar chart of top performing students with weighted score values.
    Top 3 performers receive gold/silver/bronze accent colors.
    """
    if not _MATPLOTLIB_AVAILABLE or not top_records:
        return None

    try:
        # Reverse list so rank 1 is at the top of horizontal chart
        recs = list(reversed(top_records[:15]))
        names = [f"#{r.get('rank', i+1)} {r.get('name', r.get('rollNumber', 'Student'))}" for i, r in enumerate(recs)]
        scores = [float(r.get('_weighted_score', r.get('weighted_score', 0.0))) for r in recs]
        ranks = [r.get('rank', len(recs) - i) for i, r in enumerate(recs)]

        fig, ax = plt.subplots(figsize=(8.5, max(4.0, len(names) * 0.42)))

        # Color ranking bars: Gold for Rank 1, Silver for Rank 2, Bronze for Rank 3, Deep Blue for others
        colors = []
        for rk in ranks:
            if rk == 1:
                colors.append("#D4AF37")  # Gold
            elif rk == 2:
                colors.append("#A8A8A8")  # Silver
            elif rk == 3:
                colors.append("#CD7F32")  # Bronze
            else:
                colors.append("#2E75B6")  # Mid Blue

        bars = ax.barh(range(len(names)), scores, color=colors, edgecolor="white", height=0.62)

        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=8.5, fontweight="bold")
        ax.set_xlabel("Weighted Score (Out of 100)", fontsize=9.5, fontweight="bold")
        ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
        ax.set_xlim(0, 105)
        ax.grid(axis="x", linestyle="--", alpha=0.3, color="#BFBFBF")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        for bar, val in zip(bars, scores):
            ax.text(
                bar.get_width() + 0.8, bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}", va="center", fontsize=8, fontweight="bold", color="#1F4E79"
            )

        fig.tight_layout()
        return _png_bytes(fig)

    except Exception as exc:
        logger.error(f"[ChartService] ranking_bar_chart error: {exc}")
        return None


def scatter_plot_chart(
    points: list[dict],
    x_label: str = "X",
    y_label: str = "Y",
    title: str = "Correlation Scatter Plot",
    correlation: Optional[float] = None,
    r_squared: Optional[float] = None,
    regression: Optional[dict] = None,
) -> Optional[bytes]:
    """
    Render a high-resolution scatter plot with optional linear regression trend line.
    """
    if not _MATPLOTLIB_AVAILABLE or not points or len(points) < 2:
        return None

    try:
        x_vals = [float(p.get("x", 0.0)) for p in points if p.get("x") is not None and p.get("y") is not None]
        y_vals = [float(p.get("y", 0.0)) for p in points if p.get("x") is not None and p.get("y") is not None]

        if len(x_vals) < 2:
            return None

        fig, ax = plt.subplots(figsize=(8.5, 4.8))

        # Scatter points
        ax.scatter(x_vals, y_vals, color="#2e75b6", alpha=0.75, edgecolors="#1b4f72", s=45, label="Student Observations")

        # Trend line if regression data provided
        if regression and "slope" in regression and "intercept" in regression:
            slope = float(regression["slope"])
            intercept = float(regression["intercept"])
            min_x, max_x = min(x_vals), max(x_vals)
            line_x = [min_x, max_x]
            line_y = [(slope * min_x) + intercept, (slope * max_x) + intercept]
            ax.plot(line_x, line_y, color="#c00000", linewidth=2.0, linestyle="--", label=f"Linear Fit: y = {slope:.2f}x + {intercept:.2f}")

        ax.set_xlabel(x_label, fontsize=10, fontweight="bold", labelpad=8)
        ax.set_ylabel(y_label, fontsize=10, fontweight="bold", labelpad=8)
        ax.set_title(title, fontsize=12, fontweight="bold", pad=12)

        # Callout text box with statistical summary
        stat_text = []
        if correlation is not None:
            stat_text.append(f"r = {correlation:.4f}")
        if r_squared is not None:
            stat_text.append(f"R² = {r_squared:.4f}")
        stat_text.append(f"N = {len(x_vals)}")

        if stat_text:
            bbox_props = dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#d5dbdb", alpha=0.9)
            ax.text(
                0.03, 0.95, "\n".join(stat_text),
                transform=ax.transAxes, fontsize=9, va="top", bbox=bbox_props
            )

        ax.grid(True, linestyle=":", alpha=0.6, color="#bdc3c7")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.legend(loc="lower right", fontsize=8)

        fig.tight_layout()
        return _png_bytes(fig)
    except Exception as exc:
        logger.error(f"[ChartService] scatter_plot_chart error: {exc}")
        return None


def render_dynamic_chart(chart_info: dict) -> Optional[bytes]:
    """
    Render any chart from the Pulse dynamic chart_data format.
    Supports scatter plots, ranking bar charts, risk factor bars, severity pies, and comparison bar charts.
    """
    if not _MATPLOTLIB_AVAILABLE or not chart_info:
        return None

    try:
        chart_type = chart_info.get("type")
        title = chart_info.get("title", "Chart")

        # 1. Scatter plot handler
        if chart_type == "scatter":
            return scatter_plot_chart(
                points=chart_info.get("points", []),
                x_label=chart_info.get("x_label", "X"),
                y_label=chart_info.get("y_label", "Y"),
                title=title,
                correlation=chart_info.get("correlation"),
                r_squared=chart_info.get("r_squared"),
                regression=chart_info.get("regression"),
            )

        labels = chart_info.get("labels", [])
        values = chart_info.get("values", [])

        if not labels or not values or len(labels) != len(values):
            return None

        # Clean None values
        cleaned_pairs = [(l, float(v)) for l, v in zip(labels, values) if v is not None]
        if not cleaned_pairs:
            return None
        labels, values = zip(*cleaned_pairs)
        labels = list(labels)
        values = list(values)

        if "weighted" in title.lower() or "rank" in title.lower():
            records_dummy = [{"name": l, "_weighted_score": v, "rank": i + 1} for i, (l, v) in enumerate(zip(labels, values))]
            return ranking_bar_chart(records_dummy, title=title)

        fig, ax = plt.subplots(figsize=(8, 4.2))

        if chart_type == "pie":
            # Map specific colors if severity labels
            sev_color_map = {
                "Critical": "#C00000",
                "High": "#E74C3C",
                "Moderate": "#E67E22",
                "Low": "#F1C40F",
                "Safe": "#27AE60",
                "At Risk": "#C00000",
            }
            pie_colors = [sev_color_map.get(str(l), "#2e75b6") for l in labels]
            ax.pie(
                values,
                labels=labels,
                autopct="%1.1f%%",
                startangle=140,
                colors=pie_colors,
                textprops={'fontsize': 8.5, 'fontweight': 'bold'},
                wedgeprops={'edgecolor': 'white', 'linewidth': 1.2},
            )
            ax.axis("equal")
        else:
            # Bar chart
            if "risk factor" in title.lower() or "prevalence" in title.lower():
                # Horizontal bar chart for risk factors
                fig, ax = plt.subplots(figsize=(8.5, max(3.5, len(labels) * 0.6)))
                bar_colors = ["#C00000", "#E74C3C", "#E67E22", "#8E44AD", "#D35400"][:len(labels)]
                bars = ax.barh(range(len(labels)), values, color=bar_colors, edgecolor="white", height=0.55)
                ax.set_yticks(range(len(labels)))
                ax.set_yticklabels(labels, fontsize=8.5, fontweight="bold")
                ax.set_xlabel("Number of Affected Students", fontsize=9, fontweight="bold")
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                for bar, val in zip(bars, values):
                    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2, f"{int(val)}", va="center", fontsize=8, fontweight="bold")
            else:
                bar_colors = ["#2e75b6"] * len(labels)
                if "risk" in title.lower() or "at-risk" in title.lower():
                    bar_colors = ["#C00000" if "risk" in str(l).lower() or "at risk" in str(l).lower() else "#2e75b6" for l in labels]
                bars = ax.bar(labels, values, color=bar_colors, edgecolor="white", width=0.5)
                ax.set_ylabel(chart_info.get("y_label", "Value"), fontsize=9, fontweight="bold")
                ax.set_xlabel(chart_info.get("x_label", "Category"), fontsize=9, fontweight="bold")
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                plt.xticks(rotation=15, ha="right", fontsize=8)
                for bar, val in zip(bars, values):
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2, f"{val:.1f}" if isinstance(val, float) else f"{val}", ha="center", va="bottom", fontsize=7.5)

        ax.set_title(title, fontsize=11, fontweight="bold", pad=15)
        fig.tight_layout()
        return _png_bytes(fig)
    except Exception as exc:
        logger.error(f"[ChartService] render_dynamic_chart error: {exc}")
        return None
