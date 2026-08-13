from typing import List, Dict, Any, Optional
from app.db.client import supabase


def get_all_students() -> List[Dict[str, Any]]:
    """Query and return all rows from the students table as raw dicts."""
    response = supabase.table("students").select("*").execute()
    return response.data or []


def get_students_filtered(
    department: Optional[str] = None,
    min_cgpa: Optional[float] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Query students table with optional filters applied at the database level using Supabase query builder."""
    query = supabase.table("students").select("*")

    if department:
        query = query.eq("department", department)
    if min_cgpa is not None:
        query = query.gte("cgpa", min_cgpa)

    query = query.limit(limit)
    response = query.execute()
    return response.data or []
