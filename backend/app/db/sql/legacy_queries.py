"""
Centralized SQL query string builders for legacy dispatch fallback in DBAgent.
"""
from typing import List, Optional


def build_legacy_students_sql(where_clauses: List[str], sort_field: str = "cgpa", order_dir: str = "DESC", limit: int = 100) -> str:
    """
    Constructs the formatted SQL representation string for legacy student query dispatch in DBAgent.
    """
    where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    return f"SELECT * FROM students{where_str} ORDER BY {sort_field} {order_dir} LIMIT {limit};"
