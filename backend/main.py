import uuid
import shutil
import logging
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.config import BASE_DIR, UPLOAD_DIR, EXPORT_DIR, ENABLE_KEYCLOAK
from backend.database import engine, get_db, Base
from backend.models import TranscriptionJob
from backend.worker import queue_transcription_job
from backend.auth import get_current_user

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Air-Gapped Meeting Transcription API",
    description="Local speech-to-text transcription engine with Word/PDF exports and Keycloak auth support.",
    version="1.0.0"
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

@app.post("/api/transcribe")
async def create_transcription_job(
    file: UploadFile = File(...),
    model_size: str = Form("small"),
    language: Optional[str] = Form("en"),
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
        language=language if language and language.lower() != "auto" else None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Submit to background queue worker
    queue_transcription_job(job.id)

    return JSONResponse(status_code=201, content=job.to_dict())

@app.get("/api/jobs")
def list_jobs(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """List all transcription jobs ordered by creation time descending."""
    jobs = db.query(TranscriptionJob).order_by(TranscriptionJob.created_at.desc()).all()
    return [j.to_dict() for j in jobs]

@app.get("/api/jobs/{job_id}")
def get_job_detail(job_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Get status and transcript details for a specific job."""
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()

@app.get("/api/jobs/{job_id}/download/{fmt}")
def download_export(job_id: str, fmt: str, db: Session = Depends(get_db)):
    """Download transcript in docx, pdf, txt, or srt format."""
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job or job.status != "COMPLETED":
        raise HTTPException(status_code=404, detail="Completed job not found")

    fmt = fmt.lower()
    filename_map = {
        "docx": f"transcript_{job.id}.docx",
        "pdf": f"transcript_{job.id}.pdf",
        "txt": f"transcript_{job.id}.txt",
        "srt": f"transcript_{job.id}.srt",
    }

    if fmt not in filename_map:
        raise HTTPException(status_code=400, detail="Invalid format. Use docx, pdf, txt, or srt.")

    file_path = EXPORT_DIR / filename_map[fmt]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Export file {fmt} not generated yet.")

    download_name = f"{Path(job.original_filename).stem}_transcript.{fmt}"
    return FileResponse(path=file_path, filename=download_name, media_type="application/octet-stream")

@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Delete a transcription job and its stored files."""
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Cleanup files
    try:
        (UPLOAD_DIR / job.stored_filename).unlink(missing_ok=True)
        if job.converted_filename:
            (BASE_DIR / "converted" / job.converted_filename).unlink(missing_ok=True)
        for fmt in ["docx", "pdf", "txt", "srt"]:
            (EXPORT_DIR / f"transcript_{job.id}.{fmt}").unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Error removing files for job {job_id}: {e}")

    db.delete(job)
    db.commit()
    return {"message": "Job deleted successfully"}

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
