"""
SQL package containing centralized SQL query strings and builders.
"""
from app.db.sql.schema_queries import INFORMATION_SCHEMA_COLUMNS_SQL, INFORMATION_SCHEMA_TABLES_SQL
from app.db.sql.legacy_queries import build_legacy_students_sql

__all__ = [
    "INFORMATION_SCHEMA_COLUMNS_SQL",
    "INFORMATION_SCHEMA_TABLES_SQL",
    "build_legacy_students_sql",
]
