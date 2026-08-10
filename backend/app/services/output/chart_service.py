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
