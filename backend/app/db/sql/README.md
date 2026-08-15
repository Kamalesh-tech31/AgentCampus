# Centralized SQL Directory (`app/db/sql`)

This directory contains all raw SQL queries, schema reflection query templates, and legacy SQL query builders used across AgentCampus.

## File Overview

### Standalone `.sql` Files (For Manual Copy & Supabase SQL Editor Use)
These plain SQL files can be opened directly in VS Code or copy-pasted into the Supabase SQL Editor:
- **`setup_db.sql`**: Consolidated idempotent setup script creating all 4 production tables (`students`, `courses`, `enrollments`, `history`), the `exec_sql` RPC function, and audit triggers.
- **`get_table_columns.sql`**: Discovers column names and data types for a table from `information_schema.columns`.
- **`get_all_tables.sql`**: Lists all tables in the `public` schema from `information_schema.tables`.
- **`select_legacy_students.sql`**: Template for legacy student filtering, sorting, and limit selection.

### Python Modules (Application Code Imports)
These Python modules are the authoritative source imported and executed by application agents:
- **`schema_queries.py`**: Exports `INFORMATION_SCHEMA_COLUMNS_SQL` and `INFORMATION_SCHEMA_TABLES_SQL` string constants.
- **`legacy_queries.py`**: Exports the `build_legacy_students_sql()` formatted query builder function.
- **`__init__.py`**: Package exports for `app.db.sql`.

## Guidelines for Adding New Queries

1. Create a matching standalone `.sql` file in this directory with clear comments for manual execution.
2. Define the Python constant or builder in `schema_queries.py` or `legacy_queries.py`.
3. Export the query symbol in `app/db/sql/__init__.py`.
