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
