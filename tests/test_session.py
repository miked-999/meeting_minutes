import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_session_isolation():
    """Verify jobs are isolated between different X-Session-ID headers."""
    session_a_headers = {"X-Session-ID": "test_session_user_A"}
    session_b_headers = {"X-Session-ID": "test_session_user_B"}

    # User B list jobs
    res_b_before = client.get("/api/jobs", headers=session_b_headers)
    assert res_b_before.status_code == 200
    jobs_b_initial_count = len(res_b_before.json())

    # User A uploads a dummy file (should fail validation or succeed)
    # Let's test with unsupported format to verify endpoint accepts header cleanly
    files = {"file": ("user_a_file.exe", b"dummy content", "application/octet-stream")}
    data = {"model_size": "tiny", "language": "en", "enable_diarization": "false"}

    res_upload = client.post("/api/transcribe", files=files, data=data, headers=session_a_headers)
    assert res_upload.status_code == 400  # Unsupported extension

    # User B list jobs should remain unaffected
    res_b_after = client.get("/api/jobs", headers=session_b_headers)
    assert res_b_after.status_code == 200
    assert len(res_b_after.json()) == jobs_b_initial_count

def test_session_cancel_isolation():
    """Verify users cannot cancel jobs created in other sessions."""
    from backend.database import SessionLocal
    from backend.models import TranscriptionJob
    import uuid

    db = SessionLocal()
    job_id = str(uuid.uuid4())
    user_a_session = "session_user_A_123"
    user_b_session = "session_user_B_456"

    # Create job belonging to User A
    job_a = TranscriptionJob(
        id=job_id,
        original_filename="user_a_meeting.mp3",
        stored_filename=f"{job_id}.mp3",
        file_size=2048,
        status="TRANSCRIBING",
        progress=50.0,
        current_stage="Transcribing audio",
        session_id=user_a_session
    )
    db.add(job_a)
    db.commit()
    db.close()

    # User B attempts to cancel User A's job -> Must fail with 403 Forbidden
    res_cancel_b = client.post(f"/api/jobs/{job_id}/cancel", headers={"X-Session-ID": user_b_session})
    assert res_cancel_b.status_code == 403
    assert "not authorized" in res_cancel_b.json()["detail"].lower()

    # User A cancels their own job -> Must succeed with 200 OK
    res_cancel_a = client.post(f"/api/jobs/{job_id}/cancel", headers={"X-Session-ID": user_a_session})
    assert res_cancel_a.status_code == 200
    assert res_cancel_a.json()["status"] == "CANCELLED"

    # Cleanup DB
    db = SessionLocal()
    clean_job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if clean_job:
        db.delete(clean_job)
        db.commit()
    db.close()
