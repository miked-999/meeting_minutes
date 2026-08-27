import io
import wave
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend.audio_slicer import extract_wav_clip
from backend.config import CONVERTED_DIR
from backend.database import get_db, Base, engine
from backend.models import TranscriptionJob
from sqlalchemy.orm import sessionmaker

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c

def test_extract_wav_clip(tmp_path):
    wav_file = tmp_path / "sample_16k.wav"
    
    # Create a 16kHz mono WAV file with 3 seconds of dummy audio frames
    framerate = 16000
    n_samples = framerate * 3
    dummy_data = b'\x00\x00' * n_samples

    with wave.open(str(wav_file), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(dummy_data)

    # Slice 1 second clip (from 1.0s to 2.0s)
    clip_bytes = extract_wav_clip(wav_file, 1.0, 2.0)
    assert len(clip_bytes) > 44  # Valid WAV header + PCM frames

    with wave.open(io.BytesIO(clip_bytes), 'rb') as clip_wf:
        assert clip_wf.getframerate() == 16000
        assert clip_wf.getnchannels() == 1
        # Approx 1 second of frames (16000 frames)
        assert abs(clip_wf.getnframes() - 16000) < 100

def test_rename_speakers_endpoint(client):
    db = TestingSessionLocal()
    job = TranscriptionJob(
        id="test-label-job-1",
        original_filename="interview.mp3",
        stored_filename="test-label-job-1.mp3",
        file_size=1024,
        status="COMPLETED",
        enable_diarization=True,
        session_id="test_sess_123",
        transcript_json=json.dumps([
            {"id": 1, "start": 0.0, "end": 5.0, "speaker": "Speaker 1", "text": "Hello."},
            {"id": 2, "start": 5.5, "end": 10.0, "speaker": "Speaker 2", "text": "Hi there."}
        ]),
        full_text="Speaker 1: Hello.\nSpeaker 2: Hi there."
    )
    db.add(job)
    db.commit()
    db.close()

    res = client.post(
        f"/api/jobs/test-label-job-1/rename-speakers",
        headers={"X-Session-ID": "test_sess_123"},
        json={"speaker_map": {"Speaker 1": "Alice", "Speaker 2": "Bob"}}
    )
    assert res.status_code == 200
    data = res.json()
    assert "Alice" in data["full_text"]
    assert "Bob" in data["full_text"]
    assert "Speaker 1" not in data["full_text"]

def test_audio_clip_endpoint(client, tmp_path):
    job_id = "test-clip-job-2"
    conv_wav = CONVERTED_DIR / f"{job_id}.wav"
    
    # Create test WAV in CONVERTED_DIR
    framerate = 16000
    dummy_data = b'\x00\x00' * (framerate * 4)
    with wave.open(str(conv_wav), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(dummy_data)

    db = TestingSessionLocal()
    job = TranscriptionJob(
        id=job_id,
        original_filename="podcast.wav",
        stored_filename=f"{job_id}.wav",
        converted_filename=f"{job_id}.wav",
        file_size=1024,
        status="COMPLETED",
        enable_diarization=True,
        session_id="sess_clip_999",
        transcript_json=json.dumps([
            {"id": 1, "start": 0.5, "end": 2.0, "speaker": "Speaker 1", "text": "Segment 1."},
            {"id": 2, "start": 2.2, "end": 3.5, "speaker": "Speaker 1", "text": "Segment 2."}
        ])
    )
    db.add(job)
    db.commit()
    db.close()

    try:
        res = client.get(
            f"/api/jobs/{job_id}/speakers/Speaker%201/audio-clip?clip_index=0",
            headers={"X-Session-ID": "sess_clip_999"}
        )
        assert res.status_code == 200
        assert res.headers["content-type"] == "audio/wav"
        assert len(res.content) > 44

        # Test clip_index=1 cycling to segment 2
        res2 = client.get(
            f"/api/jobs/{job_id}/speakers/Speaker%201/audio-clip?clip_index=1",
            headers={"X-Session-ID": "sess_clip_999"}
        )
        assert res2.status_code == 200
        assert len(res2.content) > 44
    finally:
        if conv_wav.exists():
            conv_wav.unlink()
