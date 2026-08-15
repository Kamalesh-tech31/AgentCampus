from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Query, Body, HTTPException
from app.contracts.common import CamelModel
from app.db.schema_registry import get_database_preview, get_live_schema, resolve_column_name

router = APIRouter(prefix="/database", tags=["database"])


class ValidateColumnRequest(CamelModel):
    table: str = "students"
    column: str


class ColumnValidationResponse(CamelModel):
    table: str
    column: str
    valid: bool
    resolved_column: Optional[str] = None
    suggestion: Optional[str] = None


class TableColumnInfo(CamelModel):
    name: str
    type: str


class DatabaseTablePreview(CamelModel):
    name: str
    columns: List[TableColumnInfo]
    sample_records: List[Dict[str, Any]]
    row_count: int


class DatabasePreviewResponse(CamelModel):
    tables: List[DatabaseTablePreview]


@router.get("/preview", response_model=DatabasePreviewResponse)
def database_preview(sample_size: int = Query(5, ge=1, le=50)):
    """
    Live database preview across all available tables:
    - Tables list
    - Column names and data types
    - Real sample records
    - Total row count
    Always fetches fresh live database state.
    """
    raw_preview = get_database_preview(sample_size=sample_size)
    return DatabasePreviewResponse.model_validate(raw_preview)


@router.get("/tables", response_model=List[str])
def list_tables():
    """Returns a list of all tables discovered in the live database schema."""
    schema = get_live_schema(force_refresh=False)
    return list(schema.keys())


@router.post("/validate-column", response_model=ColumnValidationResponse)
def validate_column(req: ValidateColumnRequest):
    """
    Validates a candidate column name against schema with fuzzy suggestions.
    Prevents LLMs or user prompts from hallucinating non-existent database columns.
    """
    res = resolve_column_name(req.table, req.column)
    return ColumnValidationResponse(
        table=req.table,
        column=req.column,
        valid=res.get("valid", False),
        resolved_column=res.get("column"),
        suggestion=res.get("suggestion"),
    )
