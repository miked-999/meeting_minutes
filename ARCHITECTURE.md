# Architecture & System Design Specification

## Overview

**Meeting Transcribe** is built on an asynchronous, decoupled architecture separating REST API request handling, background task execution, deep neural audio processing, document export generation, and structured audit logging.

```
[ Frontend (HTML/JS/CSS) ]
           │
           │ (HTTP REST API)
           ▼
[ FastAPI Application Server (main.py) ] ◄───► [ SQLite Database (meeting_minutes.db) ]
           │
           │ (Sequential Worker Thread)
           ▼
[ Worker Pipeline (worker.py) ]
     │               │                 │
     ▼               ▼                 ▼
[ FFmpeg ]   [ faster-whisper ]   [ SpeechBrain ECAPA-TDNN ]
(Converter)     (Speech-to-Text)    (Speaker Diarization)
     │               │                 │
     └───────────────┴─────────────────┘
                     │
                     ▼
       [ Document Exporter (exporter.py) ]
       (DOCX, PDF, TXT, SRT Exports)
                     │
                     ▼
       [ Audit Logger (audit_logger.py) ]
       (logs/app_usage.log & AuditLog DB)
```

---

## Technical Stack & Libraries

| Component | Library / Framework | License | Role |
| :--- | :--- | :--- | :--- |
| **Web Server** | FastAPI & Uvicorn | MIT | Asynchronous REST API server & static UI router |
| **Database** | SQLite & SQLAlchemy | MIT / BSD | Local transactional database for jobs & audit logs |
| **Media Extraction** | FFmpeg via Subprocess | LGPL v2.1+ | Converts MP4, MOV, MP3, M4A to 16kHz mono WAV |
| **STT Engine** | CTranslate2 / `faster-whisper` | MIT | High-speed local speech recognition engine |
| **Diarization Engine** | SpeechBrain ECAPA-TDNN | Apache 2.0 | 192-D deep neural voice embedding classifier |
| **Document Exports** | `python-docx` & ReportLab | MIT / BSD | Word (.docx) and PDF document layout engines |
| **Audit Logging** | Python `logging` & JSON lines | Standard | Structured JSON usage audit & telemetry logger |

---

## Data Flow & Processing Stages

1. **Job Creation & Upload (`POST /api/transcribe`)**:
   - The user selects a media file, model size (`small`, `tiny`, `medium`), and toggles Speaker Diarization (`true`/`false`).
   - The API creates a database row with status `QUEUED` and records a `JOB_CREATED` audit event.

2. **FFmpeg Audio Conversion (`Stage 1`)**:
   - Background worker extracts audio into a 16kHz 16-bit mono WAV file (`converted/{job_id}.wav`).

3. **Whisper Speech Recognition (`Stage 2`)**:
   - `faster-whisper` processes audio in 30-second sliding windows.
   - Intermediate text segments are committed to SQLite line-by-line so the UI live preview stream updates in real-time.

4. **SpeechBrain ECAPA-TDNN Neural Diarization (`Optional Stage 2.5`)**:
   - If `enable_diarization == True`, SpeechBrain extracts a 192-dimensional acoustic vector for every speech segment.
   - **Cosine Distance Agglomerative Clustering** evaluates candidate speaker counts ($k=2..20$) and assigns `Speaker 1`, `Speaker 2`, `Speaker 3` labels based on acoustic timbre.

5. **Document Export & Auto-Deletion (`Stage 3 & Cleanup`)**:
   - Exporter builds `.docx`, `.pdf`, `.txt`, and `.srt` files.
   - Upon completion, the uploaded raw media file and converted WAV file are **automatically deleted** from disk to save storage and ensure data privacy.

---

## Database Schema (SQLite)

### `transcription_jobs`
- `id` (VARCHAR(36), PK): UUID identifier.
- `original_filename` (VARCHAR(255)): Display title.
- `stored_filename` (VARCHAR(255)): Temp upload filename.
- `converted_filename` (VARCHAR(255)): Temp WAV filename.
- `file_size` (INTEGER): Size in bytes.
- `duration_seconds` (FLOAT): Audio duration.
- `status` (VARCHAR(50)): `QUEUED`, `CONVERTING`, `TRANSCRIBING`, `COMPLETED`, `FAILED`.
- `progress` (FLOAT): 0.0 to 100.0.
- `model_size` (VARCHAR(50)): `small`, `tiny`, `medium`.
- `enable_diarization` (BOOLEAN): Diarization toggle state.
- `transcript_json` (TEXT): JSON array of segments `[{start, end, text, speaker}]`.
- `full_text` (TEXT): Complete transcript text.
- `created_at` / `completed_at` (DATETIME): Processing timestamps.

### `audit_logs`
- `id` (INTEGER, PK): Autoincrement ID.
- `event_type` (VARCHAR(50)): Event name (`JOB_CREATED`, `JOB_COMPLETED`, `JOB_FAILED`, `DOCUMENT_DOWNLOADED`, `JOB_RENAMED`, `JOB_DELETED`).
- `job_id` (VARCHAR(36)): Associated job UUID.
- `filename` (VARCHAR(255)): Associated filename.
- `details_json` (TEXT): JSON telemetry details.
- `timestamp` (DATETIME): Event timestamp.

---

## REST API Endpoint Specification

- `GET /api/auth-status`: Returns Keycloak OIDC status.
- `POST /api/transcribe`: Upload file & create transcription job.
- `GET /api/jobs`: List all past transcription jobs.
- `GET /api/jobs/{id}`: Get job status & live segment data.
- `PATCH /api/jobs/{id}/rename`: Rename transcript title (`{"title": "..."}`).
- `GET /api/jobs/{id}/download/{fmt}?timestamps=true|false`: Download DOCX, PDF, TXT, or SRT.
- `DELETE /api/jobs/{id}`: Delete job record and exports.
- `GET /api/audit-logs`: Get system usage metrics & audit log history.
