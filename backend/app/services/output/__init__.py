"""
Output services package for the Scribe / Output Agent.

Provides format-specific generation services:
  - text_service  : Plain structured text
  - excel_service : .xlsx via openpyxl / pandas
  - pdf_service   : .pdf via ReportLab
  - ppt_service   : .pptx via python-pptx
  - chart_service : Optional matplotlib charts (embedded in PDF/PPT)
  - heading_map   : Human-readable field-name mappings
"""
