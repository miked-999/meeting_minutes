import pytest
from pathlib import Path
from backend.diarizer import perform_diarization

def test_perform_diarization_empty():
    assert perform_diarization(Path("non_existent.wav"), []) == []

def test_perform_diarization_single_segment():
    segments = [{"id": 1, "start": 0.0, "end": 2.0, "text": "Single speaker line."}]
    result = perform_diarization(Path("non_existent.wav"), segments)
    assert len(result) == 1
    assert result[0]["speaker"] == "Speaker 1"

def test_perform_diarization_missing_wav_fallback():
    segments = [
        {"id": 1, "start": 0.0, "end": 2.0, "text": "Line one."},
        {"id": 2, "start": 2.5, "end": 5.0, "text": "Line two."}
    ]
    # When file does not exist, perform_diarization should log warning & gracefully fall back to Speaker 1
    result = perform_diarization(Path("non_existent_file.wav"), segments)
    assert len(result) == 2
    assert result[0]["speaker"] == "Speaker 1"
    assert result[1]["speaker"] == "Speaker 1"
