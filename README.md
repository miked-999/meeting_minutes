# Meeting Transcribe - Local Air-Gapped Speech-to-Text & Diarization

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![SpeechBrain: Apache 2.0](https://img.shields.io/badge/SpeechBrain-Apache_2.0-green.svg)](https://github.com/speechbrain/speechbrain)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9+-brightgreen.svg)](https://python.org)

**Meeting Transcribe** is a secure, local, air-gapped Speech-to-Text (STT) web application designed for processing meeting recordings, panel discussions, interviews, and confidential voice calls with **zero internet reliance, zero cloud data transfer, and zero third-party API costs**.

---

## ✨ Features

- **🔒 100% Offline Air-Gapped Operation**: Runs completely locally using cached OpenAI Whisper models and SpeechBrain neural weights.
- **🗣️ Deep Neural Speaker Diarization (EXPERIMENTAL)**: Powered by SpeechBrain ECAPA-TDNN 192-D deep neural voice embeddings and Cosine Distance Clustering to differentiate multi-speaker conversations (`Speaker 1`, `Speaker 2`, `Speaker 3`, up to 20 speakers).
- **⏱️ Real-Time Live Transcript Preview**: Renders text line-by-line in real time as speech is recognized.
- **📄 Multi-Format Exports**: Download formatted Word (`.docx`), PDF (`.pdf`), Plain Text (`.txt`), and Subtitles (`.srt`). Includes an optional **"Include Timestamps"** toggle switch.
- **🎨 UI-Matched Speaker Color Coding**: Downloaded Word and PDF documents feature theme-matched colored speaker tags.
- **🧹 Automatic Media Cleanup**: Uploaded raw media files and converted WAV audio streams are auto-deleted upon completion to save disk space and enforce privacy compliance.
- **✏️ Inline Title Renaming & History Management**: Edit transcript titles directly on the History page and manage past jobs with 2-step inline confirmation.
- **📊 Usage Audit Logging System**: Structured JSON logs (`logs/app_usage.log`) and SQLite `AuditLog` database table record telemetry, processing durations, and system metrics.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.9+
- FFmpeg (`brew install ffmpeg`)

### 2. Run the Application
```bash
./venv/bin/python run_server.py
```
Open your browser to: **`http://localhost:8000`**

### 3. Stop the Application
```bash
./stop.sh  # or ./venv/bin/python stop_server.py
```

---

## 🧹 Data Retention & Disk Cleanup

The app automatically executes disk cleanup on server startup and supports standalone CLI / API triggers:
- **Default Retention**: Purges files and jobs older than **7 days** (configurable via environment variable `RETENTION_DAYS=7`).
- **Standalone CLI Script**:
  ```bash
  ./venv/bin/python cleanup.py --days 7
  ```
- **Admin API Endpoint**: `DELETE /api/admin/cleanup?days=7`

---

## 🧪 Running Automated Tests

Run the full pytest suite:
```bash
./venv/bin/pytest -v
```

---

## 📚 Documentation Suite

- [README_WIN.md](file:///Users/michael/meeting_minutes/README_WIN.md): Complete Windows Server 2016/2019/2022 & Windows 10/11 production deployment manual (NSSM Windows Service + IIS Reverse Proxy).
- [ARCHITECTURE.md](file:///Users/michael/meeting_minutes/ARCHITECTURE.md): System architecture, REST API specification, database schema, and SpeechBrain ECAPA-TDNN neural design.
- [USER_GUIDE.md](file:///Users/michael/meeting_minutes/USER_GUIDE.md): Complete end-user manual and feature walkthrough.
