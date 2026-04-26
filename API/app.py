"""
AI Invoice Auditor — FastAPI application.
"""
from __future__ import annotations
import json
import sys
import uuid
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.responses import PlainTextResponse

import swagger_ui_bundle

from state import JobState
from workflow.workflow import workflow
from services.retriever_service import RetrieverService
from services.s3_service import put_json, put_text, upload_file, get_json, get_text, key_exists
from log_utils.logger import get_logger
from API.models import QueryRequest, UploadResponse

logger = get_logger(__name__)

# Local temp dir for uploads before pushing to S3
_TMP_DIR = Path(tempfile.gettempdir()) / "invoice_auditor"
_TMP_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

app = FastAPI(
    title="AI Invoice Auditor",
    description="Invoice extraction, translation, validation and RAG query API.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

_retriever: Optional[RetrieverService] = None


def _get_retriever() -> RetrieverService:
    global _retriever
    if _retriever is None:
        _retriever = RetrieverService()
    return _retriever


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _new_job_id() -> str:
    return str(uuid.uuid4())


def _set_status(job_id: str, status: str, extra: Optional[dict] = None) -> None:
    payload = {
        "job_id":     job_id,
        "status":     status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    put_json(f"runs/{job_id}/status.json", payload)


def _save_upload_to_tmp(upload: UploadFile, job_id: str) -> Path:
    """Save uploaded file to a local temp path, return the path."""
    filename = Path(upload.filename).name  # strip any path components — security fix
    tmp_path = _TMP_DIR / job_id / filename
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return tmp_path


def _run_langgraph_job(
    job_id: str,
    invoice_local: Path,
    metadata_local: Optional[Path],
    invoice_s3_key: str,
) -> None:
    try:
        logger.info("[app] Starting job %s — invoice=%s", job_id, invoice_local)
        _set_status(job_id, "processing", {"invoice_s3_key": invoice_s3_key})

        state = JobState(
            job_id=job_id,
            invoice_path=str(invoice_local),
            metadata_path=str(metadata_local) if metadata_local else None,
        )

        result = workflow(state)

        # Save Markdown report to S3
        report_md = result.get("report") or ""
        put_text(f"runs/{job_id}/report.md", report_md)

        # Save JSON summary to S3
        summary = {
            "job_id":                job_id,
            "validation_passed":     result.get("validation_passed"),
            "validation_findings":   result.get("validation_findings", []),
            "errors":                result.get("error", []),
            "detected_language":     result.get("detected_language"),
            "extraction_confidence": result.get("extraction_confidence"),
            "chunk_count":           result.get("chunk_count"),
        }
        put_json(f"runs/{job_id}/report.json", summary)

        _set_status(job_id, "completed")
        logger.info("[app] Job %s completed — validation_passed=%s", job_id, result.get("validation_passed"))

    except Exception as e:
        logger.error("[app] Job %s failed: %s", job_id, e, exc_info=True)
        put_text(f"runs/{job_id}/error.txt", str(e))
        _set_status(job_id, "failed", {"error": str(e)})

    finally:
        # Clean up local temp files
        tmp_job_dir = _TMP_DIR / job_id
        if tmp_job_dir.exists():
            shutil.rmtree(tmp_job_dir, ignore_errors=True)


@app.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload invoice and trigger audit pipeline",
)
async def upload(
    background_tasks: BackgroundTasks,
    invoice_file: UploadFile = File(...),
    metadata_file: Optional[UploadFile] = File(None),
):
    """
    Accept an invoice PDF (and optional metadata JSON/XML), upload to S3,
    and kick off the full LangGraph audit pipeline as a background task.

    Returns `job_id` immediately; poll `GET /jobs/{job_id}` for status.
    """
    # Validate file extension
    suffix = Path(invoice_file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{suffix}'. Allowed: {ALLOWED_EXTENSIONS}")

    job_id = _new_job_id()
    filename = Path(invoice_file.filename).name  # strip path components

    # Save to temp local path (needed by pdfplumber/tesseract which require local files)
    invoice_local = _save_upload_to_tmp(invoice_file, job_id)

    # Upload to S3
    invoice_s3_key = f"uploads/{job_id}/{filename}"
    upload_file(str(invoice_local), invoice_s3_key)

    metadata_local: Optional[Path] = None
    if metadata_file is not None:
        metadata_local = _save_upload_to_tmp(metadata_file, job_id)
        upload_file(str(metadata_local), f"uploads/{job_id}/{Path(metadata_file.filename).name}")

    _set_status(job_id, "queued", {"created_at": datetime.now(timezone.utc).isoformat()})
    background_tasks.add_task(_run_langgraph_job, job_id, invoice_local, metadata_local, invoice_s3_key)

    logger.info("[app] Queued job %s for invoice '%s'", job_id, filename)
    return UploadResponse(job_id=job_id, status="queued")


@app.get(
    "/jobs/{job_id}",
    summary="Get job status",
)
async def job_status(job_id: str):
    """Returns the current status of an audit job (queued / processing / completed / failed)."""
    data = get_json(f"runs/{job_id}/status.json")
    if not data:
        raise HTTPException(status_code=404, detail="job not found")
    return data


@app.get(
    "/jobs/{job_id}/report",
    summary="Get JSON audit summary",
)
async def job_report(job_id: str):
    """
    Returns the structured JSON audit summary once the job is completed.
    Includes `validation_passed`, findings list, errors, and metadata.
    """
    data = get_json(f"runs/{job_id}/report.json")
    if not data:
        raise HTTPException(status_code=404, detail="report not ready — job may still be processing")
    return data


@app.get(
    "/jobs/{job_id}/report/markdown",
    response_class=PlainTextResponse,
    summary="Get Markdown audit report",
)
async def job_report_markdown(job_id: str):
    """Returns the full LLM-generated Markdown audit report for human review."""
    text = get_text(f"runs/{job_id}/report.md")
    if not text:
        raise HTTPException(status_code=404, detail="report not ready — job may still be processing")
    return text


@app.post(
    "/query",
    summary="RAG query against ingested invoice data",
)
async def query_invoice(body: QueryRequest):
    """
    Ask a natural-language question about one or more ingested invoices.
    Optionally scope the search to a specific `job_id` or `invoice_file`.

    Example request body:
    ```json
    { "query": "What is the grand total?", "job_id": "abc-123" }
    ```
    """
    svc = _get_retriever()
    return svc.answer(body.query, job_id=body.job_id, invoice_file=body.invoice_file)
