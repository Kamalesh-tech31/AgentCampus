"""
Centralized SQL queries for database schema and information_schema discovery.
"""

INFORMATION_SCHEMA_COLUMNS_SQL = (
    "SELECT column_name, data_type "
    "FROM information_schema.columns "
    "WHERE table_schema = 'public' AND table_name = :table_name;"
)

INFORMATION_SCHEMA_TABLES_SQL = (
    "SELECT table_name "
    "FROM information_schema.tables "
    "WHERE table_schema = 'public';"
)
