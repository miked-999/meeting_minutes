import time
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import TranscriptionJob
from backend.worker import _executor, recover_pending_queue

client = TestClient(app)

def test_executor_max_workers_is_one():
    """Verify single-worker thread pool executor configuration."""
    assert _executor._max_workers == 1

def test_queue_position_calculation():
    """Verify 1-based queue position ordering for queued jobs."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        job1 = TranscriptionJob(
            id="test-queue-job-1",
            original_filename="first_upload.mp3",
            stored_filename="temp1.mp3",
            file_size=1000,
            status="QUEUED",
            created_at=now - timedelta(seconds=10)
        )
        job2 = TranscriptionJob(
            id="test-queue-job-2",
            original_filename="second_upload.mp3",
            stored_filename="temp2.mp3",
            file_size=1000,
            status="QUEUED",
            created_at=now
        )
        db.add(job1)
        db.add(job2)
        db.commit()

        dict1 = job1.to_dict(db_session=db)
        dict2 = job2.to_dict(db_session=db)

        assert dict1["queue_position"] == 1
        assert "Position 1" in dict1["current_stage"]

        assert dict2["queue_position"] == 2
        assert "Position 2" in dict2["current_stage"]

    finally:
        db.query(TranscriptionJob).filter(TranscriptionJob.id.in_(["test-queue-job-1", "test-queue-job-2"])).delete()
        db.commit()
        db.close()

def test_startup_queue_recovery():
    """Verify recover_pending_queue re-queues interrupted or pending jobs."""
    db = SessionLocal()
    try:
        interrupted_job = TranscriptionJob(
            id="test-interrupted-job",
            original_filename="interrupted.mp3",
            stored_filename="temp_interrupted.mp3",
            file_size=5000,
            status="CONVERTING",
            created_at=datetime.utcnow()
        )
        db.add(interrupted_job)
        db.commit()

        # Execute recovery
        recover_pending_queue()

        db.refresh(interrupted_job)
        assert interrupted_job.status == "QUEUED"
        assert interrupted_job.current_stage == "Queued for processing"

    finally:
        db.query(TranscriptionJob).filter(TranscriptionJob.id == "test-interrupted-job").delete()
        db.commit()
        db.close()
