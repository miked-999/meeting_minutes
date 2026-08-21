import os
import time
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import TranscriptionJob
from backend.config import UPLOAD_DIR, CONVERTED_DIR, EXPORT_DIR
from backend.cleanup import cleanup_expired_jobs

client = TestClient(app)

def test_cleanup_expired_jobs_functionality():
    """Verify that jobs and files older than retention days are purged while recent jobs remain."""
    db = SessionLocal()
    try:
        # Create an old job (8 days old)
        old_created_at = datetime.utcnow() - timedelta(days=8)
        old_job = TranscriptionJob(
            id="old_test_job_123",
            original_filename="old_meeting.mp4",
            stored_filename="old_test_job_123.mp4",
            converted_filename="old_test_job_123.wav",
            file_size=1024,
            status="COMPLETED",
            created_at=old_created_at
        )
        db.add(old_job)

        # Create a recent job (1 day old)
        recent_job = TranscriptionJob(
            id="recent_test_job_456",
            original_filename="recent_meeting.mp4",
            stored_filename="recent_test_job_456.mp4",
            converted_filename="recent_test_job_456.wav",
            file_size=2048,
            status="COMPLETED",
            created_at=datetime.utcnow() - timedelta(days=1)
        )
        db.add(recent_job)
        db.commit()

        # Create dummy physical files for the old job
        old_upload = UPLOAD_DIR / "old_test_job_123.mp4"
        old_conv = CONVERTED_DIR / "old_test_job_123.wav"
        old_export = EXPORT_DIR / "old_test_job_123.docx"

        for f in [old_upload, old_conv, old_export]:
            f.write_text("dummy old data")

        # Run cleanup for max_age_days = 7
        result = cleanup_expired_jobs(max_age_days=7, db_session=db)

        assert result["status"] == "success"
        assert result["jobs_removed"] >= 1

        # Verify old job and files were deleted
        assert not old_upload.exists()
        assert not old_conv.exists()
        assert not old_export.exists()
        assert db.query(TranscriptionJob).filter_by(id="old_test_job_123").first() is None

        # Verify recent job remains intact
        assert db.query(TranscriptionJob).filter_by(id="recent_test_job_456").first() is not None

    finally:
        # Cleanup test records
        db.query(TranscriptionJob).filter(TranscriptionJob.id.in_(["old_test_job_123", "recent_test_job_456"])).delete()
        db.commit()
        db.close()

def test_admin_cleanup_api_endpoint():
    """Verify DELETE /api/admin/cleanup API endpoint."""
    res = client.delete("/api/admin/cleanup?days=30")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "jobs_removed" in data
    assert "freed_mb" in data
