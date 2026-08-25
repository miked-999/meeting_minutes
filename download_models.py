#!/usr/bin/env python3
import sys
from pathlib import Path
# pyrefly: ignore [missing-import]
from faster_whisper import WhisperModel
from backend.config import MODELS_DIR

def download_model(model_size: str):
    print(f"Downloading Whisper model '{model_size}' to {MODELS_DIR}...")
    WhisperModel(model_size, device="cpu", compute_type="int8", download_root=str(MODELS_DIR))
    print(f"Successfully cached model '{model_size}'!")

def download_ecapa():
    save_dir = str(MODELS_DIR / "spkrec-ecapa-voxceleb")
    print(f"Downloading SpeechBrain ECAPA-TDNN speaker recognition model to {save_dir}...")
    try:
        from speechbrain.inference.speaker import EncoderClassifier
        EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=save_dir,
            run_opts={"device": "cpu"}
        )
        print("Successfully cached SpeechBrain ECAPA-TDNN model!")
    except Exception as e:
        print(f"Failed to download SpeechBrain ECAPA model: {e}")

if __name__ == "__main__":
    raw_args = sys.argv[1:]
    
    skip_ecapa = "--skip-ecapa" in raw_args
    ecapa_only = "--ecapa-only" in raw_args
    
    filtered_args = [a for a in raw_args if a not in ("--skip-ecapa", "--ecapa-only", "ecapa", "ecapa-tdnn")]
    
    if ecapa_only:
        download_ecapa()
    else:
        models_to_download = filtered_args if filtered_args else ["tiny", "base", "small"]
        for m in models_to_download:
            download_model(m)
        
        if not skip_ecapa:
            download_ecapa()

