import json
import pytest
from pathlib import Path
from types import SimpleNamespace
from backend.exporter import generate_docx, generate_pdf, generate_txt, generate_srt, format_timestamp, group_segments_by_speaker

def test_format_timestamp():
    assert format_timestamp(45) == "00:45"
    assert format_timestamp(125) == "02:05"
    assert format_timestamp(3665) == "01:01:05"

def test_group_segments_by_speaker():
    segments = [
        {"id": 1, "start": 0.0, "end": 5.0, "speaker": "Speaker 1", "text": "Hello world."},
        {"id": 2, "start": 5.5, "end": 10.0, "speaker": "Speaker 1", "text": "How are you?"},
        {"id": 3, "start": 10.5, "end": 15.0, "speaker": "Speaker 2", "text": "I am fine."}
    ]
    turns = group_segments_by_speaker(segments, is_diarized=True)
    assert len(turns) == 2
    assert turns[0]["speaker"] == "Speaker 1"
    assert turns[0]["start"] == 0.0
    assert turns[0]["end"] == 10.0
    assert turns[0]["text"] == "Hello world. How are you?"
    
    assert turns[1]["speaker"] == "Speaker 2"
    assert turns[1]["start"] == 10.5
    assert turns[1]["end"] == 15.0
    assert turns[1]["text"] == "I am fine."

def test_generate_txt_nodiar(tmp_path):
    job = SimpleNamespace(
        id="test-job-1",
        original_filename="sample_meeting.mp3",
        duration_seconds=60.0,
        model_size="small",
        enable_diarization=False,
        transcript_json=json.dumps([
            {"id": 1, "start": 0.0, "end": 5.0, "text": "Welcome to the team sync."},
            {"id": 2, "start": 5.5, "end": 12.0, "text": "Let us review today's updates."}
        ]),
        full_text="Welcome to the team sync.\nLet us review today's updates."
    )
    
    txt_file = tmp_path / "test_out.txt"
    generate_txt(job, txt_file, include_timestamps=True)
    
    assert txt_file.exists()
    content = txt_file.read_text(encoding="utf-8")
    assert "MEETING TRANSCRIPT - sample_meeting.mp3" in content
    assert "[00:00 - 00:05] Welcome to the team sync." in content
    assert "Speaker 1:" not in content  # Must NOT include Speaker 1 when diarization is False

def test_generate_txt_with_diarization_grouped(tmp_path):
    job = SimpleNamespace(
        id="test-job-2",
        original_filename="panel_discussion.wav",
        duration_seconds=120.0,
        model_size="medium",
        enable_diarization=True,
        transcript_json=json.dumps([
            {"id": 1, "start": 0.0, "end": 5.0, "speaker": "Speaker 1", "text": "Good morning everyone."},
            {"id": 2, "start": 5.5, "end": 10.0, "speaker": "Speaker 1", "text": "Welcome to the annual panel discussion."},
            {"id": 3, "start": 10.5, "end": 15.0, "speaker": "Speaker 2", "text": "Good morning Alice."}
        ]),
        full_text="Speaker 1: Good morning everyone.\nSpeaker 2: Good morning Alice."
    )
    
    txt_file = tmp_path / "test_diar_out.txt"
    generate_txt(job, txt_file, include_timestamps=True)
    
    assert txt_file.exists()
    content = txt_file.read_text(encoding="utf-8")
    assert "Speaker 1: [00:00 - 00:10] Good morning everyone. Welcome to the annual panel discussion." in content
    assert "Speaker 2: [00:10 - 00:15] Good morning Alice." in content
    assert content.count("Speaker 1:") == 1

def test_generate_docx_and_pdf(tmp_path):
    job = SimpleNamespace(
        id="test-job-3",
        original_filename="board_meeting.m4a",
        duration_seconds=90.0,
        model_size="small",
        enable_diarization=True,
        transcript_json=json.dumps([
            {"id": 1, "start": 1.0, "end": 4.0, "speaker": "Speaker 1", "text": "Agenda point one."},
            {"id": 2, "start": 4.1, "end": 6.0, "speaker": "Speaker 1", "text": "Let us vote on it."},
            {"id": 3, "start": 6.5, "end": 8.0, "speaker": "Speaker 2", "text": "Agreed."}
        ]),
        full_text="Speaker 1: Agenda point one.\nSpeaker 2: Agreed."
    )
    
    docx_file = tmp_path / "test_out.docx"
    pdf_file = tmp_path / "test_out.pdf"
    srt_file = tmp_path / "test_out.srt"
    
    generate_docx(job, docx_file, include_timestamps=True)
    generate_pdf(job, pdf_file, include_timestamps=True)
    generate_srt(job, srt_file)
    
    assert docx_file.exists() and docx_file.stat().st_size > 0
    assert pdf_file.exists() and pdf_file.stat().st_size > 0
    assert srt_file.exists() and srt_file.stat().st_size > 0
