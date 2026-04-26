"""
AI Invoice Auditor — FastAPI application.

"""
from __future__ import annotations
import json
import sys
import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

import swagger_ui_bundle

from state import JobState
from workflow.workflow import workflow
from services.retriever_service import RetrieverService
from log_utils.logger import get_logger
from API.models import QueryRequest, UploadResponse

logger = get_logger(__name__)

# Project root directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directories anchored to project root so they resolve correctly regardless
# of where uvicorn is launched from.
UPLOAD_DIR = _PROJECT_ROOT / "uploads"
RUNS_DIR   = _PROJECT_ROOT / "runs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

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


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _save_upload(upload: UploadFile, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("wb") as f:
        shutil.copyfileobj(upload.file, f)


def _set_status(job_id: str, status: str, extra: Optional[dict] = None) -> None:
    payload = {
        "job_id":     job_id,
        "status":     status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    _write_json(RUNS_DIR / job_id / "status.json", payload)


def _run_langgraph_job(job_id: str, invoice_path: Path, metadata_path: Optional[Path]) -> None:
    try:
        logger.info("[app] Starting job %s — invoice=%s", job_id, invoice_path)
        _set_status(job_id, "processing", {"invoice_path": str(invoice_path)})

        state = JobState(
            job_id=job_id,
            invoice_path=str(invoice_path),
            metadata_path=str(metadata_path) if metadata_path else None,
        )

        result = workflow(state)

        job_dir = RUNS_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Save full Markdown audit report
        report_md = result.get("report") or ""
        (job_dir / "report.md").write_text(report_md, encoding="utf-8")

        # Save lightweight JSON summary
        summary = {
            "job_id":                job_id,
            "validation_passed":     result.get("validation_passed"),
            "validation_findings":   result.get("validation_findings", []),
            "errors":                result.get("error", []),
            "detected_language":     result.get("detected_language"),
            "extraction_confidence": result.get("extraction_confidence"),
            "chunk_count":           result.get("chunk_count"),
        }
        _write_json(job_dir / "report.json", summary)

        _set_status(job_id, "completed")
        logger.info(
            "[app] Job %s completed — validation_passed=%s",
            job_id, result.get("validation_passed"),
        )

    except Exception as e:
        logger.error("[app] Job %s failed: %s", job_id, e, exc_info=True)
        (RUNS_DIR / job_id).mkdir(parents=True, exist_ok=True)
        (RUNS_DIR / job_id / "error.txt").write_text(str(e), encoding="utf-8")
        _set_status(job_id, "failed", {"error": str(e)})


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
    Accept an invoice PDF (and optional metadata JSON/XML), save to disk,
    and kick off the full LangGraph audit pipeline as a background task.

    Returns `job_id` immediately; poll `GET /jobs/{job_id}` for status.
    """
    job_id = _new_job_id()

    job_upload_dir = UPLOAD_DIR / job_id
    invoice_path   = job_upload_dir / invoice_file.filename
    _save_upload(invoice_file, invoice_path)

    metadata_path: Optional[Path] = None
    if metadata_file is not None:
        metadata_path = job_upload_dir / metadata_file.filename
        _save_upload(metadata_file, metadata_path)

    _set_status(job_id, "queued", {"created_at": datetime.now(timezone.utc).isoformat()})
    background_tasks.add_task(_run_langgraph_job, job_id, invoice_path, metadata_path)

    logger.info("[app] Queued job %s for invoice '%s'", job_id, invoice_file.filename)
    return UploadResponse(job_id=job_id, status="queued")


@app.get(
    "/jobs/{job_id}",
    summary="Get job status",
)
async def job_status(job_id: str):
    """Returns the current status of an audit job (queued / processing / completed / failed)."""
    p = RUNS_DIR / job_id / "status.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="job not found")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get(
    "/jobs/{job_id}/report",
    summary="Get JSON audit summary",
)
async def job_report(job_id: str):
    """
    Returns the structured JSON audit summary once the job is completed.
    Includes `validation_passed`, findings list, errors, and metadata.
    """
    p = RUNS_DIR / job_id / "report.json"
    if not p.exists():
        raise HTTPException(
            status_code=404,
            detail="report not ready — job may still be processing",
        )
    return json.loads(p.read_text(encoding="utf-8"))


@app.get(
    "/jobs/{job_id}/report/markdown",
    response_class=PlainTextResponse,
    summary="Get Markdown audit report",
)
async def job_report_markdown(job_id: str):
    """Returns the full LLM-generated Markdown audit report for human review."""
    p = RUNS_DIR / job_id / "report.md"
    if not p.exists():
        raise HTTPException(
            status_code=404,
            detail="report not ready — job may still be processing",
        )
    return p.read_text(encoding="utf-8")


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


