import uuid
import shutil
import logging
from pathlib import Path
from typing import Optional, List

from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.config import BASE_DIR, UPLOAD_DIR, EXPORT_DIR, ENABLE_KEYCLOAK, APP_VERSION
from backend.database import engine, get_db, Base
from backend.models import TranscriptionJob
from backend.worker import queue_transcription_job
from backend.auth import get_current_user

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from backend.worker import recover_pending_queue
        recover_pending_queue()
    except Exception as e:
        logger.warning(f"Startup queue recovery failed: {e}")

    try:
        from backend.cleanup import cleanup_expired_jobs
        cleanup_expired_jobs()
    except Exception as e:
        logger.warning(f"Startup disk cleanup failed: {e}")
    yield

app = FastAPI(
    title="Air-Gapped Meeting Transcription API",
    description="Local speech-to-text transcription engine with Word/PDF exports and Keycloak auth support.",
    version=APP_VERSION,
    lifespan=lifespan
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes

@app.get("/api/auth-status")
def auth_status(current_user: dict = Depends(get_current_user)):
    return {
        "keycloak_enabled": ENABLE_KEYCLOAK,
        "user": current_user
    }

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header, Request

def extract_session_id(request: Request, x_session_id: Optional[str] = None) -> Optional[str]:
    if x_session_id and isinstance(x_session_id, str):
        return x_session_id.strip()
    header_val = request.headers.get("x-session-id")
    if header_val:
        return header_val.strip()
    return request.cookies.get("session_id") or request.query_params.get("session_id")

@app.post("/api/transcribe")
async def create_transcription_job(
    request: Request,
    file: UploadFile = File(...),
    model_size: str = Form("small"),
    language: Optional[str] = Form("en"),
    enable_diarization: str = Form("false"),
    x_session_id: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Upload audio/video file and trigger background transcription."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    file_ext = Path(file.filename).suffix.lower()
    allowed_exts = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"}
    if file_ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{file_ext}'. Allowed formats: {', '.join(sorted(allowed_exts))}"
        )

    job_id = str(uuid.uuid4())
    stored_filename = f"{job_id}{file_ext}"
    dest_path = UPLOAD_DIR / stored_filename

    # Save uploaded file
    file_size = 0
    with dest_path.open("wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)
            file_size += len(chunk)

    is_diarized = str(enable_diarization).lower().strip() in ["true", "1", "on", "yes"]
    session_id = extract_session_id(request, x_session_id)

    # Create job in database
    job = TranscriptionJob(
        id=job_id,
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_size=file_size,
        status="QUEUED",
        progress=0.0,
        current_stage="Queued for processing",
        model_size=model_size,
        language=language if language and language.lower() != "auto" else "en",
        enable_diarization=is_diarized,
        session_id=session_id
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Log audit event
    try:
        from backend.audit_logger import log_audit_event
        log_audit_event(
            event_type="JOB_CREATED",
            job_id=job.id,
            filename=job.original_filename,
            details={
                "file_size": file_size,
                "model_size": model_size,
                "enable_diarization": is_diarized,
                "session_id": session_id
            },
            db_session=db
        )
    except Exception as audit_err:
        logger.warning(f"Audit log failed: {audit_err}")

    # Submit to background queue worker
    queue_transcription_job(job.id)

    return JSONResponse(status_code=201, content=job.to_dict(db_session=db))

@app.get("/api/jobs")
def list_jobs(
    request: Request,
    x_session_id: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List transcription jobs filtered by session_id if provided."""
    session_id = extract_session_id(request, x_session_id)
    query = db.query(TranscriptionJob)
    if session_id:
        query = query.filter(TranscriptionJob.session_id == session_id)
    jobs = query.order_by(TranscriptionJob.created_at.desc()).all()
    return [j.to_dict(db_session=db) for j in jobs]

class RenameJobRequest(BaseModel):
    title: str

@app.patch("/api/jobs/{job_id}/rename")
def rename_job(
    job_id: str,
    req: RenameJobRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Rename original title for a transcription job."""
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    new_title = req.title.strip()
    if not new_title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    
    old_title = job.original_filename
    job.original_filename = new_title
    db.commit()
    db.refresh(job)

    try:
        from backend.audit_logger import log_audit_event
        log_audit_event(
            event_type="JOB_RENAMED",
            job_id=job.id,
            filename=new_title,
            details={"old_title": old_title, "new_title": new_title},
            db_session=db
        )
    except Exception:
        pass

    return job.to_dict(db_session=db)

@app.get("/api/jobs/{job_id}")
def get_job_detail(job_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Get status and transcript details for a specific job."""
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict(db_session=db)

@app.get("/api/jobs/{job_id}/download/{fmt}")
def download_export(job_id: str, fmt: str, timestamps: bool = False, db: Session = Depends(get_db)):
    """Download transcript in docx, pdf, txt, or srt format with optional timestamps."""
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job or job.status != "COMPLETED":
        raise HTTPException(status_code=404, detail="Completed job not found")

    fmt = fmt.lower()
    ts_suffix = "_ts" if timestamps else ""
    filename_map = {
        "docx": f"transcript_{job.id}{ts_suffix}.docx",
        "pdf": f"transcript_{job.id}{ts_suffix}.pdf",
        "txt": f"transcript_{job.id}{ts_suffix}.txt",
        "srt": f"transcript_{job.id}.srt",
    }

    if fmt not in filename_map:
        raise HTTPException(status_code=400, detail="Invalid format. Use docx, pdf, txt, or srt.")

    file_path = EXPORT_DIR / filename_map[fmt]

    # Generate on-demand if specified format with/without timestamps doesn't exist
    if not file_path.exists():
        from backend.exporter import generate_docx, generate_pdf, generate_txt, generate_srt
        if fmt == "docx":
            generate_docx(job, file_path, include_timestamps=timestamps)
        elif fmt == "pdf":
            generate_pdf(job, file_path, include_timestamps=timestamps)
        elif fmt == "txt":
            generate_txt(job, file_path, include_timestamps=timestamps)
        elif fmt == "srt":
            generate_srt(job, file_path)

    media_types = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
        "txt": "text/plain",
        "srt": "text/plain"
    }

    export_name = f"{Path(job.original_filename).stem}_transcript.{fmt}"

    try:
        from backend.audit_logger import log_audit_event
        log_audit_event(
            event_type="DOCUMENT_DOWNLOADED",
            job_id=job.id,
            filename=job.original_filename,
            details={"format": fmt, "timestamps": timestamps},
            db_session=db
        )
    except Exception:
        pass

    return FileResponse(
        path=file_path,
        media_type=media_types[fmt],
        filename=export_name
    )

@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str, request: Request, db: Session = Depends(get_db)):
    """Cancels an in-progress or queued transcription job."""
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    session_id = extract_session_id(request)
    if job.session_id and (not session_id or job.session_id != session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to cancel transcriptions created in another session."
        )

    if job.status in ["COMPLETED", "FAILED", "CANCELLED"]:
        return {"message": f"Job is already in state '{job.status}'", "job_id": job.id, "status": job.status}

    from backend.worker import cancel_job_id
    cancel_job_id(job.id)

    job.status = "CANCELLED"
    job.current_stage = "Cancelled by user"
    db.commit()

    try:
        from backend.audit_logger import log_audit_event
        log_audit_event(
            event_type="JOB_CANCELLED",
            job_id=job.id,
            filename=job.original_filename,
            details={"stage": "User requested cancellation"},
            db_session=db
        )
    except Exception:
        pass

    return {"message": "Job cancellation requested", "job_id": job.id, "status": "CANCELLED"}

@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Deletes a transcription job and all associated export files."""
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job_title = job.original_filename

    # Delete export files
    for fmt_suffix in ["", "_ts"]:
        for ext in ["docx", "pdf", "txt"]:
            export_file = EXPORT_DIR / f"transcript_{job.id}{fmt_suffix}.{ext}"
            if export_file.exists():
                try:
                    export_file.unlink()
                except Exception:
                    pass

    srt_file = EXPORT_DIR / f"transcript_{job.id}.srt"
    if srt_file.exists():
        try:
            srt_file.unlink()
        except Exception:
            pass
            
    # Cleanup source files
    try:
        (UPLOAD_DIR / job.stored_filename).unlink(missing_ok=True)
        if job.converted_filename:
            (BASE_DIR / "converted" / job.converted_filename).unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Error removing source files for job {job_id}: {e}")

    db.delete(job)
    db.commit()

    try:
        from backend.audit_logger import log_audit_event
        log_audit_event(
            event_type="JOB_DELETED",
            job_id=job_id,
            filename=job_title,
            db_session=db
        )
    except Exception:
        pass

    return {"message": "Job deleted successfully"}

@app.get("/api/audit-logs")
def get_audit_logs(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Retrieves usage audit log entries and system metrics."""
    from backend.models import AuditLog
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(200).all()
    
    total_jobs = db.query(TranscriptionJob).count()
    completed_jobs = db.query(TranscriptionJob).filter(TranscriptionJob.status == "COMPLETED").count()
    failed_jobs = db.query(TranscriptionJob).filter(TranscriptionJob.status == "FAILED").count()

    return {
        "summary": {
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs
        },
        "logs": [l.to_dict() for l in logs]
    }

@app.delete("/api/admin/cleanup")
def trigger_cleanup(
    days: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Trigger manual data retention cleanup for files and jobs older than specified days."""
    from backend.cleanup import cleanup_expired_jobs
    from backend.config import RETENTION_DAYS
    max_days = days if days is not None and days >= 0 else RETENTION_DAYS
    res = cleanup_expired_jobs(max_age_days=max_days, db_session=db)
    return res

# Serve static frontend UI
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

@app.get("/")
def serve_index():
    index_file = BASE_DIR / "frontend" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Air-Gapped Meeting Transcription API running. Frontend loading..."}
