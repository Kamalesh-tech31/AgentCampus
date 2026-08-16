"""
Centralized SQL query string builders for legacy dispatch fallback in DBAgent.
"""
from typing import List, Optional


def build_legacy_students_sql(where_clauses: List[str], sort_field: str = "cgpa", order_dir: str = "DESC", limit: Optional[int] = 100) -> str:
    """
    Constructs the formatted SQL representation string for legacy student query dispatch in DBAgent.
    Completely omits the LIMIT clause if limit is None.
    """
    where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    sort_str = f" ORDER BY {sort_field} {order_dir}" if sort_field else ""
    limit_str = f" LIMIT {limit}" if limit is not None and str(limit).strip().lower() not in ("none", "null", "") else ""
    return f"SELECT * FROM students{where_str}{sort_str}{limit_str};"
