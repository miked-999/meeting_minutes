# User Guide & Manual: Meeting Transcribe

Welcome to **Meeting Transcribe**, your secure local speech-to-text meeting transcription application!

---

## 🛠️ Step-by-Step Operations Guide

### 1. Starting the Application
In your terminal, run:
```bash
./venv/bin/python run_server.py
```
Open your web browser to **`http://localhost:8000`**.

---

### 2. Uploading a Recording & Setting Options

1. **Select File**: Drag and drop your audio or video file (`.mp3`, `.wav`, `.m4a`, `.mp4`, `.mov`, `.mkv`) into the upload drop zone.
2. **Select Whisper Model**:
   - **Small (Recommended)**: Best balance of high accuracy and processing speed.
   - **Tiny**: Fastest execution for quick drafts.
   - **Medium**: Highest recognition precision for difficult audio.
3. **Toggle Speaker Diarization (Identify Speakers)**:
   - By default, Speaker Diarization is **OFF**.
   - Toggle **ON** the **`Speaker Diarization (Identify Individual Speakers)`** switch if you want the neural engine to separate and label different speakers (`Speaker 1`, `Speaker 2`, `Speaker 3`).
4. Click **Start Local Transcription**.

---

### 3. Monitoring Real-Time Live Preview Stream

- As your recording processes, the **Active Processing Monitor** shows live progress percentage.
- The **Live Transcript Stream** box displays text sentence-by-sentence as speech is decoded.
- When diarization is enabled, colored speaker badges (`Speaker 1`, `Speaker 2`, etc.) appear as soon as voice clustering completes!

---

### 4. Exporting & Downloading Transcripts

- Under **Export Formats**, click **DOCX (Word)**, **PDF**, **TXT**, or **SRT**.
- **Include Timestamps Toggle**: Turn ON the **"Include Timestamps"** toggle switch if you want `[00:01 - 00:05]` timestamp prefixes included in your downloaded files.
- **Color-Coded Speakers**: Downloaded Word and PDF documents highlight speaker names in distinct colors matching the web interface.

---

### 5. History & Downloads Management

- Click the **History & Downloads** tab to view all past transcriptions.
- **Rename Title (<i class="fa-solid fa-pen-to-square"></i>)**: Click the pencil edit icon next to any title to rename it inline. Press Enter or click the green checkmark to save.
- **Delete Record (<i class="fa-solid fa-trash-can"></i>)**: Click the trash icon. The button transforms into `<i class="fa-solid fa-triangle-exclamation"></i> Confirm Delete?`. Click again to confirm permanent deletion.

---

### 6. Stopping the Application

When finished, run:
```bash
./stop.sh
```
or:
```bash
./venv/bin/python stop_server.py
```
This safely stops all background processes and frees port 8000.
