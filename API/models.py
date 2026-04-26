from typing import Optional

from pydantic import BaseModel


class QueryRequest(BaseModel):
    """Request body for the POST /query RAG endpoint."""
    query: str
    job_id: Optional[str] = None
    invoice_file: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Response body for GET /jobs/{job_id}."""
    job_id: str
    status: str
    updated_at: str
    invoice_path: Optional[str] = None
    created_at: Optional[str] = None
    error: Optional[str] = None


class UploadResponse(BaseModel):
    """Response body for POST /upload."""
    job_id: str
    status: str


class AuditSummaryResponse(BaseModel):
    """Response body for GET /jobs/{job_id}/report (JSON summary)."""
    job_id: str
    validation_passed: Optional[bool]
    validation_findings: list
    errors: list
    detected_language: Optional[str]
    extraction_confidence: Optional[float]
    chunk_count: Optional[int]
