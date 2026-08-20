import json
import logging
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.config import UPLOAD_DIR, CONVERTED_DIR, EXPORT_DIR
from backend.database import SessionLocal
from backend.models import TranscriptionJob
from backend.converter import convert_to_wav
from backend.transcriber import run_transcription
from backend.exporter import generate_docx, generate_pdf, generate_txt, generate_srt

logger = logging.getLogger(__name__)

# Single background worker thread to process jobs sequentially and avoid hardware overloading
_executor = ThreadPoolExecutor(max_workers=1)

def process_job(job_id: str):
    """Executes the full media conversion, transcription, and export pipeline for a job."""
    db = SessionLocal()
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job:
        db.close()
        return

    try:
        logger.info(f"Processing job {job.id} for file '{job.original_filename}'")
        
        # Stage 1: Conversion
        job.status = "CONVERTING"
        job.progress = 5.0
        job.current_stage = "Converting audio stream via FFmpeg"
        db.commit()

        input_path = UPLOAD_DIR / job.stored_filename
        wav_filename = f"{job.id}.wav"
        output_wav_path = CONVERTED_DIR / wav_filename

        duration = convert_to_wav(input_path, output_wav_path)
        job.converted_filename = wav_filename
        job.duration_seconds = duration
        job.progress = 15.0
        job.current_stage = "Audio extraction complete. Preparing STT Model"
        db.commit()

        # Stage 2: Transcription
        job.status = "TRANSCRIBING"
        job.progress = 20.0
        job.current_stage = f"Transcribing with Whisper ({job.model_size})"
        db.commit()

        def update_progress(proc_percent: float, current_segments: list = None):
            # Scale transcription progress from 20% to 88%
            scaled_progress = 20.0 + (proc_percent * 0.68)
            job.progress = min(88.0, round(scaled_progress, 1))
            if current_segments:
                job.transcript_json = json.dumps(current_segments)
            db.commit()

        segments, full_text, detected_lang = run_transcription(
            wav_path=output_wav_path,
            model_size=job.model_size,
            language=job.language,
            enable_diarization=job.enable_diarization,
            total_duration=duration,
            progress_callback=update_progress
        )

        job.transcript_json = json.dumps(segments)
        job.full_text = full_text
        job.language = detected_lang
        job.progress = 92.0
        job.current_stage = "Generating DOCX & PDF exports"
        db.commit()

        # Stage 3: Export Generation
        docx_filename = f"transcript_{job.id}.docx"
        pdf_filename = f"transcript_{job.id}.pdf"
        txt_filename = f"transcript_{job.id}.txt"
        srt_filename = f"transcript_{job.id}.srt"

        generate_docx(job, EXPORT_DIR / docx_filename)
        generate_pdf(job, EXPORT_DIR / pdf_filename)
        generate_txt(job, EXPORT_DIR / txt_filename)
        generate_srt(job, EXPORT_DIR / srt_filename)

        job.docx_path = docx_filename
        job.pdf_path = pdf_filename

        # Final Completion
        job.status = "COMPLETED"
        job.progress = 100.0
        job.current_stage = "Transcription completed successfully"
        job.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Job {job.id} completed successfully!")

        try:
            from backend.audit_logger import log_audit_event
            spk_set = set()
            for s in segments:
                if s.get("speaker"):
                    spk_set.add(s["speaker"])

            log_audit_event(
                event_type="JOB_COMPLETED",
                job_id=job.id,
                filename=job.original_filename,
                details={
                    "duration_seconds": duration,
                    "model_size": job.model_size,
                    "enable_diarization": job.enable_diarization,
                    "segment_count": len(segments),
                    "speaker_count": len(spk_set) if spk_set else (1 if job.enable_diarization else 0)
                },
                db_session=db
            )
        except Exception as audit_err:
            logger.warning(f"Audit log failed in worker: {audit_err}")

    except Exception as e:
        err_msg = f"{str(e)}\n{traceback.format_exc()}"
        logger.error(f"Error processing job {job_id}: {err_msg}")
        job.status = "FAILED"
        job.current_stage = "Failed during processing"
        job.error_message = str(e)
        db.commit()

        try:
            from backend.audit_logger import log_audit_event
            log_audit_event(
                event_type="JOB_FAILED",
                job_id=job.id,
                filename=job.original_filename if 'job' in locals() and job else "Unknown",
                details={"error": str(e)},
                db_session=db
            )
        except Exception:
            pass
    finally:
        # Auto-delete uploaded raw media file and converted WAV to free disk space & preserve privacy
        try:
            if job.stored_filename:
                stored_file_path = UPLOAD_DIR / job.stored_filename
                if stored_file_path.exists():
                    stored_file_path.unlink()
                    logger.info(f"Auto-deleted uploaded media file {stored_file_path}")
        except Exception as cleanup_err:
            logger.warning(f"Error auto-deleting stored media: {cleanup_err}")

        try:
            if job.converted_filename:
                conv_file_path = CONVERTED_DIR / job.converted_filename
                if conv_file_path.exists():
                    conv_file_path.unlink()
                    logger.info(f"Auto-deleted converted WAV file {conv_file_path}")
        except Exception as cleanup_err:
            logger.warning(f"Error auto-deleting converted WAV: {cleanup_err}")

        db.close()

def queue_transcription_job(job_id: str):
    """Submits a job ID to the background executor thread."""
    _executor.submit(process_job, job_id)

def recover_pending_queue():
    """Resumes processing for any pending or interrupted jobs upon application startup."""
    db = SessionLocal()
    try:
        pending_jobs = db.query(TranscriptionJob).filter(
            TranscriptionJob.status.in_(["QUEUED", "CONVERTING", "TRANSCRIBING"])
        ).order_by(TranscriptionJob.created_at.asc()).all()

        if pending_jobs:
            logger.info(f"Startup Queue Recovery: Found {len(pending_jobs)} pending/interrupted job(s). Re-queuing...")
            for j in pending_jobs:
                if j.status != "QUEUED":
                    j.status = "QUEUED"
                    j.current_stage = "Queued for processing"
                    db.commit()
                queue_transcription_job(j.id)
    except Exception as e:
        logger.warning(f"Error during queue recovery: {e}")
    finally:
        db.close()
