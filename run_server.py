#!/usr/bin/env python3
import sys
import uvicorn
from pathlib import Path

# Ensure root workspace directory is in python path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if __name__ == "__main__":
    print("Starting AirGap Meeting Transcription Web Server on http://localhost:8000 ...")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
