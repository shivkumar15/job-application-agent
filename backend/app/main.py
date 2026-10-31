import os
from io import BytesIO
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.integrations.internshala import (
    InternshalaJobCreate,
    InternshalaJobStore,
    build_store,
)
from app.resume_parser import analyze_resume

APP_ENV = os.getenv("APP_ENV", "development")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "5"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

app = FastAPI(
    title="Job Application Agent API",
    version="0.2.0",
    description=(
        "Phase 1: resume intelligence. Phase 2: compliant Internshala "
        "manual listing capture. No automated Internshala website access."
    ),
)

origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

job_store: InternshalaJobStore = build_store()


@app.get("/health", tags=["System"])
def health():
    return {
        "status": "healthy",
        "service": "job-application-agent-api",
        "phase": 2,
        "environment": APP_ENV,
    }


@app.post("/api/v1/resumes/analyze", tags=["Resume"])
async def analyze_resume_endpoint(file: UploadFile = File(...)):
    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Please upload a PDF resume.")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Resume exceeds the {MAX_UPLOAD_MB} MB upload limit.",
        )
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF.")

    try:
        profile = analyze_resume(BytesIO(content))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Could not read this PDF. It may be scanned or password-protected.",
        ) from exc

    return {
        "filename": file.filename,
        "profile": profile,
        "note": "Review extracted fields before using them. The API does not store the uploaded resume.",
    }


@app.get("/api/v1/integrations/internshala/status", tags=["Internshala"])
def internshala_status():
    return {
        "platform": "Internshala",
        "integration_mode": "manual_capture",
        "automated_site_access": False,
        "storage": job_store.storage_mode,
        "message": (
            "Capture listings that you select through Internshala's normal website. "
            "Automated scraping and website interaction are not implemented."
        ),
    }


@app.post("/api/v1/integrations/internshala/jobs", status_code=201, tags=["Internshala"])
def create_internshala_job(payload: InternshalaJobCreate):
    try:
        return job_store.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=409,
            detail="This listing has already been captured.",
        ) from exc


@app.get("/api/v1/integrations/internshala/jobs", tags=["Internshala"])
def list_internshala_jobs(
    paid_only: bool = Query(default=False),
    work_mode: Optional[str] = Query(default=None, pattern="^(remote|onsite|hybrid|unknown)$"),
):
    return {
        "count": len(job_store.list_jobs(paid_only=paid_only, work_mode=work_mode)),
        "jobs": job_store.list_jobs(paid_only=paid_only, work_mode=work_mode),
    }


@app.get("/api/v1/integrations/internshala/jobs/{dedupe_key}", tags=["Internshala"])
def get_internshala_job(dedupe_key: str):
    job = job_store.get(dedupe_key)
    if job is None:
        raise HTTPException(status_code=404, detail="Captured listing not found.")
    return job
