import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/files", tags=["files"])

BASE_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output_files"


@router.get("/download/{file_name}")
def download_file(file_name: str):
    """
    Secure file download endpoint for generated Scribe artifacts (PDF, PPTX, XLSX).
    """
    # Prevent directory traversal
    clean_name = os.path.basename(file_name)
    file_path = BASE_OUTPUT_DIR / clean_name

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{clean_name}' not found.")

    media_type = "application/octet-stream"
    if clean_name.endswith(".pdf"):
        media_type = "application/pdf"
    elif clean_name.endswith(".xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif clean_name.endswith(".pptx"):
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    return FileResponse(
        path=file_path,
        filename=clean_name,
        media_type=media_type,
    )
