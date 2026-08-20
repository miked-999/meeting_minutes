import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_get_auth_status():
    response = client.get("/api/auth-status")
    assert response.status_code == 200
    data = response.json()
    assert "keycloak_enabled" in data
    assert "user" in data

def test_list_jobs():
    response = client.get("/api/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_audit_logs():
    response = client.get("/api/audit-logs")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "logs" in data
    assert "total_jobs" in data["summary"]

def test_invalid_file_upload():
    # Submit unsupported file extension
    files = {"file": ("test_executable.exe", b"invalid executable content", "application/octet-stream")}
    data = {"model_size": "small", "language": "en", "enable_diarization": "false"}
    
    response = client.post("/api/transcribe", files=files, data=data)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]

def test_job_not_found():
    response = client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"

def test_rename_invalid_job():
    response = client.patch(
        "/api/jobs/00000000-0000-0000-0000-000000000000/rename",
        json={"title": "New Title"}
    )
    assert response.status_code == 404

def test_delete_invalid_job():
    response = client.delete("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
