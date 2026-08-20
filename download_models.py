#!/usr/bin/env python3
import sys
from pathlib import Path
from faster_whisper import WhisperModel
from backend.config import MODELS_DIR

def download_model(model_size: str):
    print(f"Downloading Whisper model '{model_size}' to {MODELS_DIR}...")
    WhisperModel(model_size, device="cpu", compute_type="int8", download_root=str(MODELS_DIR))
    print(f"Successfully cached model '{model_size}'!")

if __name__ == "__main__":
    models_to_download = sys.argv[1:] if len(sys.argv) > 1 else ["tiny", "base", "small"]
    for m in models_to_download:
        download_model(m)
