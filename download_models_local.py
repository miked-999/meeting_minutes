#!/usr/bin/env python3
import os
import sys
import shutil
from pathlib import Path

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
# pyrefly: ignore [missing-import]
from faster_whisper import WhisperModel
from backend.config import MODELS_DIR

def download_model(model_size: str):
    print(f"Downloading Whisper model '{model_size}' to {MODELS_DIR}...")
    WhisperModel(model_size, device="cpu", compute_type="int8", download_root=str(MODELS_DIR))
    print(f"Successfully cached model '{model_size}'!")

def dereference_and_flatten_ecapa(target_dir: Path):
    """
    Ensures all model files in target_dir are standalone physical files
    without relying on symlinks or nested HuggingFace subfolders (snapshots/blobs).
    """
    target_dir = Path(target_dir)
    if not target_dir.exists():
        return

    print(f"Dereferencing symlinks and flattening physical model files in {target_dir}...")
    
    # Collect all items in target_dir recursively
    all_items = list(target_dir.rglob("*"))
    for item in all_items:
        if item.is_file() or item.is_symlink():
            real_path = item.resolve()
            dest_path = target_dir / item.name
            
            # If item is nested in a subfolder or is a symlink, replace with real file copy
            if item != dest_path or item.is_symlink():
                tmp_path = target_dir / f"{item.name}.tmp"
                shutil.copyfile(real_path, tmp_path)
                try:
                    if item.is_symlink() or item.is_file():
                        os.remove(item)
                except Exception:
                    pass
                if tmp_path.exists():
                    os.rename(tmp_path, dest_path)

    # Clean up empty/leftover subdirectories (blobs, refs, snapshots)
    for child in list(target_dir.iterdir()):
        if child.is_dir():
            try:
                shutil.rmtree(child)
            except Exception:
                pass

def download_ecapa():
    save_dir = MODELS_DIR / "spkrec-ecapa-voxceleb"
    print(f"Downloading SpeechBrain ECAPA-TDNN speaker recognition model to {save_dir}...")
    try:
        try:
            from speechbrain.inference.speaker import EncoderClassifier
        except (ImportError, AttributeError, ModuleNotFoundError):
            from speechbrain.pretrained import EncoderClassifier

        EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=str(save_dir),
            run_opts={"device": "cpu"}
        )
        
        # Convert all downloaded symlinks / HF cache files to local physical copies
        dereference_and_flatten_ecapa(save_dir)
        print("Successfully cached standalone physical SpeechBrain ECAPA-TDNN model!")
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
