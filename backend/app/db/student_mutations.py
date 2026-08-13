from typing import Dict, List, Any
from app.db.client import supabase
from app.db.generic_mutations import (
    generic_insert,
    generic_update,
    generic_delete,
    generic_bulk_insert,
)


def insert_student(data: Dict[str, Any]) -> Dict[str, Any]:
    """Delegates to generic_insert for students table."""
    return generic_insert("students", data)


def update_student(student_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Delegates to generic_update for students table."""
    return generic_update("students", student_id, data)


def delete_student(student_id: str) -> bool:
    """Delegates to generic_delete for students table."""
    return generic_delete("students", student_id)


def delete_all_students() -> None:
    """Delete all rows from the students table."""
    supabase.table("students").delete().neq("id", "").execute()


def bulk_insert_students(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Delegates to generic_bulk_insert for students table."""
    return generic_bulk_insert("students", records)
