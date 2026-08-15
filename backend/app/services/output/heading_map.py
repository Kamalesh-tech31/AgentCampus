"""
heading_map.py — Human-readable field-name mappings for Scribe output.

Covers both snake_case and camelCase variants (records can come in either
form depending on the serialization path through Vault/Pulse agents).

For unknown fields, `humanize()` generates a readable heading automatically
using title-casing without requiring an LLM.
"""

FIELD_HEADINGS: dict[str, str] = {
    # Student record fields — snake_case
    "id": "Student ID",
    "roll_number": "Roll Number",
    "name": "Student Name",
    "department": "Department",
    "cgpa": "CGPA",
    "semester": "Semester",
    "attendance": "Attendance (%)",
    "email": "Email",
    "status": "Status",
    "backlogs": "Backlogs",
    "project_title": "Project Title",
    # Student record fields — camelCase (DB agent serialises by alias)
    "rollNumber": "Roll Number",
    "projectTitle": "Project Title",
    # Analytics / metrics fields — snake_case
    "total_records": "Total Records",
    "average_cgpa": "Average CGPA",
    "highest_cgpa": "Highest CGPA",
    "lowest_cgpa": "Lowest CGPA",
    "avg_attendance": "Avg Attendance (%)",
    "probation_count": "Students on Probation",
    "department_breakdown": "Department Breakdown",
    # Analytics / metrics fields — camelCase
    "totalRecords": "Total Records",
    "averageCgpa": "Average CGPA",
    "highestCgpa": "Highest CGPA",
    "lowestCgpa": "Lowest CGPA",
    "avgAttendance": "Avg Attendance (%)",
    "probationCount": "Students on Probation",
    "departmentBreakdown": "Department Breakdown",
    # Department metric sub-fields
    "count": "Student Count",
    "avg_cgpa": "Avg CGPA",
    "avgCgpa": "Avg CGPA",
}


def humanize(field: str) -> str:
    """
    Return a human-readable heading for a field name.

    Priority:
    1. Exact match in FIELD_HEADINGS dict.
    2. Title-case conversion of snake_case / camelCase / kebab-case string.
    """
    if field in FIELD_HEADINGS:
        return FIELD_HEADINGS[field]

    # Convert camelCase → words
    import re
    spaced = re.sub(r"([A-Z])", r" \1", field)
    # Replace underscores / hyphens
    spaced = spaced.replace("_", " ").replace("-", " ")
    return spaced.strip().title()
