# Meeting Transcribe - Windows Server & Windows 10/11 Installation Guide

This document provides complete, step-by-step instructions for installing, configuring, pre-caching AI models, and running **Meeting Transcribe** in a production environment on **Windows Server 2016/2019/2022** or **Windows 10/11 (64-bit)**.

---

## 📋 System Requirements

- **Operating System**: Windows Server 2016/2019/2022 or Windows 10/11 (64-bit)
- **CPU**: 4–8 CPU Cores (x86_64) recommended
- **RAM**: Minimum 8 GB (16 GB recommended)
- **Disk Space**: 10 GB free space (for cached Whisper models & storage)
- **Python**: Python 3.9+ for Windows (64-bit)
- **Media Codec Engine**: FFmpeg for Windows

---

## 🛠️ Step 1: Install System Prerequisites

### 1.1 Install Python 3.9+ (64-bit)
1. Download the latest Python 64-bit installer from [python.org/downloads/windows](https://www.python.org/downloads/windows/).
2. Run the installer and **IMPORTANTLY** check the box:  
   ☑ **"Add Python 3.x to PATH"**
3. Complete the installation wizard.
4. Open PowerShell or Command Prompt and verify:
   ```powershell
   python --version
   ```

### 1.2 Install FFmpeg for Windows
1. Download a static 64-bit release build of FFmpeg from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) or [ffmpeg.org](https://ffmpeg.org/download.html).
2. Extract the ZIP file and copy `ffmpeg.exe` and `ffprobe.exe` into a folder on your system (e.g. `C:\ffmpeg\bin` or directly into `C:\meeting_minutes\bin`).
3. Add the folder containing `ffmpeg.exe` to your System Environment `PATH`:
   - Press `Win + R`, type `sysdm.cpl`, and hit Enter.
   - Go to **Advanced** ➔ **Environment Variables**.
   - Under **System variables**, select `Path` ➔ Edit ➔ Add `C:\ffmpeg\bin`.
4. Open a fresh PowerShell window and verify FFmpeg is accessible:
   ```powershell
   ffmpeg -version
   ```

---

## 📥 Step 2: Code Setup & Virtual Environment

1. Extract or clone the **Meeting Transcribe** codebase into your desired application folder (e.g., `C:\meeting_minutes`).
2. Open PowerShell as Administrator and navigate to the project directory:
   ```powershell
   cd C:\meeting_minutes
   ```
3. Create a Python Virtual Environment:
   ```powershell
   python -m venv venv
   ```
4. Activate the virtual environment:
   - **PowerShell**:
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
     *(Note: If PowerShell blocks script execution, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` once).*
   - **Command Prompt (cmd.exe)**:
     ```cmd
     venv\Scripts\activate.bat
     ```
5. Upgrade `pip` and install all required Python libraries:
   ```powershell
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 🧠 Step 3: Download & Pre-Cache AI Models (Air-Gap Preparation)

Before putting the application into an air-gapped or production environment, pre-cache the OpenAI Whisper models and SpeechBrain speaker recognition models locally:

```powershell
.\venv\Scripts\python.exe download_models.py
```

- **Output**: Models will be downloaded into `C:\meeting_minutes\models_cache`.
- Once downloaded, the application runs **100% offline with zero internet access required**.

---

## 🧪 Step 4: Verification & Manual Testing

1. Start the application web server manually:
   ```powershell
   .\venv\Scripts\python.exe run_server.py
   ```
2. Open your web browser and navigate to:  
   👉 **`http://localhost:8000`**
3. Test uploading a short `.mp4`, `.mp3`, or `.wav` file, toggling **Speaker Diarisation**, and downloading Word (`.docx`) and PDF reports.
4. Run the automated test suite to ensure system integrity:
   ```powershell
   .\venv\Scripts\pytest.exe -v
   ```
5. To stop the manual server:
   ```powershell
   .\venv\Scripts\python.exe stop_server.py
   ```

---

## 🏭 Step 5: Production Deployment on Windows Server

For a production deployment, run Python as an **automatic background Windows Service** (using NSSM) and optional **IIS Reverse Proxy**.

### Option A: Register as a Background Windows Service (NSSM - Recommended)

[NSSM (Non-Sucking Service Manager)](https://nssm.cc/) allows your Python app to run seamlessly in the background, automatically start on Windows Server reboots, and auto-restart if it crashes.

1. Download **NSSM 2.24+** from [nssm.cc/download](https://nssm.cc/download) and copy `nssm.exe` (64-bit) to `C:\Windows\System32` (or `C:\meeting_minutes\bin`).
2. Open PowerShell as Administrator and run:
   ```powershell
   nssm install MeetingTranscribe "C:\meeting_minutes\venv\Scripts\python.exe" "C:\meeting_minutes\run_server.py"
   nssm set MeetingTranscribe AppDirectory "C:\meeting_minutes"
   nssm set MeetingTranscribe DisplayName "AirGap Meeting Transcription Engine"
   nssm set MeetingTranscribe Description "Local Speech-to-Text and Diarization Web Service"
   nssm set MeetingTranscribe Start SERVICE_AUTO_START
   ```
3. Start the service:
   ```powershell
   nssm start MeetingTranscribe
   ```
4. Verify service status:
   ```powershell
   nssm status MeetingTranscribe
   ```
   *(The app is now running in the background on port 8000 and will automatically boot with Windows Server!)*

---

### Option B: IIS Reverse Proxy Integration (HTTPS & Corporate Domain Binding)

**Option B** is how you make **Meeting Transcribe** accessible to everyone in your organisation over a secure, user-friendly corporate URL (such as `https://transcribe.company.local`) instead of requiring users to type `http://192.168.1.50:8000`.

#### 🔍 Traffic Flow Diagram:
```text
[ User Browser ] ──► (HTTPS Port 443) ──► [ IIS Web Server (Option B) ]
                                                   │
                                     (Internal Proxy Pass to 127.0.0.1:8000)
                                                   │
                                                   ▼
                                     [ Python Windows Service (Option A) ]
```

- **Option A (Background Service)** runs your Python app in the background on internal port `8000`.
- **Option B (IIS Web Server)** sits on public HTTPS port `443`. It handles the SSL security certificate, decrypts incoming traffic, and passes requests to port `8000` in milliseconds.

---

#### 📦 Required Software Modules (All Free from Microsoft):

1. **IIS (Internet Information Services)**: Built into Windows Server (enabled via *Server Manager ➔ Add Roles and Features ➔ Web Server IIS*).
2. **URL Rewrite Module 2.1**: Free Microsoft IIS extension that inspects incoming URLs and rewrites them internally.
3. **Application Request Routing (ARR 3.0)**: Free Microsoft IIS extension that allows IIS to proxy HTTP traffic to internal backend ports.
4. **Corporate SSL Certificate**: Your company's standard SSL certificate (e.g. `.pfx` or Active Directory CA certificate) to enable HTTPS.

---

#### ⚙️ Step-by-Step Configuration Guide:

1. **Install IIS & Microsoft Modules**:
   - Download and install [URL Rewrite 2.1](https://www.iis.net/downloads/microsoft/url-rewrite) and [ARR 3.0](https://www.iis.net/downloads/microsoft/application-request-routing).
2. **Enable Proxying in IIS Manager**:
   - Open **IIS Manager** (`inetmgr`).
   - Click your Server's root node in the left pane.
   - Double-click **Application Request Routing Cache**.
   - In the right-hand Actions menu, click **Server Proxy Settings**.
   - Check the box **"Enable proxy"** and click **Apply**.
3. **Add Website & Bind SSL Certificate**:
   - In IIS Manager, right-click **Sites** ➔ **Add Website**.
   - **Site name**: `MeetingTranscribe`
   - **Physical path**: `C:\meeting_minutes\frontend` (or any folder).
   - **Binding**: Select `https`, Port `443`, Host name: `transcribe.company.local`.
   - **SSL Certificate**: Select your corporate certificate from the dropdown list.
4. **Create `web.config` Reverse Proxy Rule**:
   - Place a file named `web.config` inside `C:\meeting_minutes\frontend\web.config` containing:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <system.webServer>
        <rewrite>
            <rules>
                <rule name="ReverseProxyToFastAPI" stopProcessing="true">
                    <match url="(.*)" />
                    <action type="REWRITE" url="http://127.0.0.1:8000/{R:1}" />
                </rule>
            </rules>
        </rewrite>
    </system.webServer>
</configuration>
```

#### 💡 Why Option A + Option B Combined is Gold Standard for Windows:
- **Option A (NSSM Service)** gives you 24/7 background execution, auto-boot on server restart, and automatic crash recovery.
- **Option B (IIS Reverse Proxy)** gives your users trusted HTTPS security, corporate domain names, and integration with your network firewall.
6. Bind your corporate SSL certificate to the IIS website on port 443.

---

## 🧹 Step 6: Automated Disk Cleanup & Data Retention

The application automatically purges files older than **7 days** on server startup.

### Standalone CLI Execution:
To manually clean files older than X days:
```powershell
.\venv\Scripts\python.exe cleanup.py --days 7
```

### Windows Task Scheduler (Optional Daily Maintenance):
1. Open **Windows Task Scheduler** (`taskschd.msc`).
2. Click **Create Task** ➔ Name: `MeetingTranscribeCleanup`.
3. Set Security Options to **"Run whether user is logged on or not"**.
4. **Triggers**: Daily at 3:00 AM.
5. **Actions**: Start a program:
   - Program: `C:\meeting_minutes\venv\Scripts\python.exe`
   - Arguments: `C:\meeting_minutes\cleanup.py --days 7`
   - Start in: `C:\meeting_minutes`

---

## 🔍 Troubleshooting & Logs

- **Application Logs**:
  - Console / Service Logs: `C:\meeting_minutes\logs\app_usage.log`
  - Database Audit Logs: Queryable via API `GET /api/audit-logs`
- **Port 8000 Already in Use**:
  ```powershell
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force
  ```
- **FFmpeg Not Found**:
  Verify `ffmpeg.exe` is in `PATH` or place `ffmpeg.exe` directly inside `C:\meeting_minutes\bin\`.
