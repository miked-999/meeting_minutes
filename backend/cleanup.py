import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
from sqlalchemy.orm import Session

from backend.config import UPLOAD_DIR, CONVERTED_DIR, EXPORT_DIR, RETENTION_DAYS
from backend.database import SessionLocal
from backend.models import TranscriptionJob, AuditLog

logger = logging.getLogger(__name__)

def cleanup_expired_jobs(max_age_days: int = RETENTION_DAYS, db_session: Optional[Session] = None) -> Dict[str, Any]:
    """
    Purges completed/failed transcription jobs and orphaned files older than max_age_days.
    Returns a summary dictionary of removed items and freed disk space.
    """
    own_session = False
    if db_session is None:
        db_session = SessionLocal()
        own_session = True

    cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
    jobs_removed = 0
    files_removed = 0
    freed_bytes = 0

    try:
        logger.info(f"Starting disk cleanup for files and jobs older than {max_age_days} days (Cutoff: {cutoff_date.isoformat()})...")

        # 1. Purge expired completed or failed jobs from DB and disk
        expired_jobs = db_session.query(TranscriptionJob).filter(
            TranscriptionJob.created_at < cutoff_date,
            TranscriptionJob.status.in_(["COMPLETED", "FAILED"])
        ).all()

        for job in expired_jobs:
            # Delete upload file
            if job.stored_filename:
                upload_file = UPLOAD_DIR / job.stored_filename
                if upload_file.exists():
                    try:
                        freed_bytes += upload_file.stat().st_size
                        upload_file.unlink()
                        files_removed += 1
                    except Exception as err:
                        logger.warning(f"Failed to delete upload file {upload_file}: {err}")

            # Delete converted WAV file
            if job.converted_filename:
                conv_file = CONVERTED_DIR / job.converted_filename
                if conv_file.exists():
                    try:
                        freed_bytes += conv_file.stat().st_size
                        conv_file.unlink()
                        files_removed += 1
                    except Exception as err:
                        logger.warning(f"Failed to delete converted file {conv_file}: {err}")

            # Delete export files (.docx, .pdf, .txt, .srt)
            for ext in [".docx", ".pdf", ".txt", ".srt"]:
                exp_file = EXPORT_DIR / f"{job.id}{ext}"
                if exp_file.exists():
                    try:
                        freed_bytes += exp_file.stat().st_size
                        exp_file.unlink()
                        files_removed += 1
                    except Exception as err:
                        logger.warning(f"Failed to delete export file {exp_file}: {err}")

            # Delete job from DB
            db_session.delete(job)
            jobs_removed += 1

        # Purge audit logs older than retention days
        db_session.query(AuditLog).filter(AuditLog.timestamp < cutoff_date).delete()

        db_session.commit()

        # 2. Clean orphaned files in storage directories older than max_age_days
        for storage_dir in [UPLOAD_DIR, CONVERTED_DIR, EXPORT_DIR]:
            if not storage_dir.exists():
                continue
            for file_path in storage_dir.glob("*"):
                if file_path.name == ".gitkeep" or file_path.is_dir():
                    continue
                try:
                    mtime = datetime.utcfromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_date:
                        freed_bytes += file_path.stat().st_size
                        file_path.unlink()
                        files_removed += 1
                        logger.info(f"Purged orphaned file: {file_path.name}")
                except Exception as err:
                    logger.warning(f"Failed to check/unlink file {file_path}: {err}")

        logger.info(
            f"Disk cleanup complete: {jobs_removed} jobs removed, {files_removed} files deleted, "
            f"{(freed_bytes / (1024*1024)):.2f} MB freed."
        )

        return {
            "status": "success",
            "max_age_days": max_age_days,
            "jobs_removed": jobs_removed,
            "files_removed": files_removed,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "freed_bytes": freed_bytes,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error during disk cleanup: {e}", exc_info=True)
        if db_session:
            db_session.rollback()
        return {
            "status": "error",
            "detail": str(e),
            "max_age_days": max_age_days
        }

    finally:
        if own_session and db_session:
            db_session.close()
