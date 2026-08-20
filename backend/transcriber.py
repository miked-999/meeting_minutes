import json
import logging
from pathlib import Path
from backend.config import MODELS_DIR, DEVICE, COMPUTE_TYPE

logger = logging.getLogger(__name__)

# Global model cache to avoid reloading heavy model weights unnecessarily
_MODEL_CACHE = {}

def get_whisper_model(model_size: str = "tiny"):
    """Loads and caches the faster-whisper model instance locally."""
    global _MODEL_CACHE
    
    if model_size in _MODEL_CACHE:
        return _MODEL_CACHE[model_size]
    
    from faster_whisper import WhisperModel

    # Determine optimal device and compute type
    device = DEVICE
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    
    compute_type = COMPUTE_TYPE
    if device == "cpu" and compute_type == "default":
        compute_type = "int8"  # Faster execution on CPU
    elif device == "cuda" and compute_type == "default":
        compute_type = "float16"

    logger.info(f"Loading faster-whisper model '{model_size}' on device={device}, compute_type={compute_type}...")
    
    model = WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
        download_root=str(MODELS_DIR)
    )
    
    _MODEL_CACHE[model_size] = model
    return model

def run_transcription(
    wav_path: Path,
    model_size: str = "tiny",
    language: str = "en",
    enable_diarization: bool = False,
    total_duration: float = 0.0,
    progress_callback = None
):
    """
    Executes local Whisper transcription on the WAV file.
    Returns (segments_list, full_text_str, detected_language).
    """
    model = get_whisper_model(model_size)
    
    kwargs = {"vad_filter": True}
    if language and language.lower() not in ["auto", "none", ""]:
        kwargs["language"] = language.lower()

    logger.info(f"Starting transcription for {wav_path} (duration: {total_duration}s, diarization: {enable_diarization})...")
    segments_raw, info = model.transcribe(str(wav_path), **kwargs)

    detected_lang = info.language
    logger.info(f"Detected language: {detected_lang} (probability: {round(info.language_probability, 2)})")

    segments = []
    full_text_parts = []
    for seg in segments_raw:
        seg_dict = {
            "id": seg.id,
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip()
        }
        segments.append(seg_dict)

        if progress_callback and total_duration > 0:
            current_progress = min(88.0, (seg.end / total_duration) * 100.0)
            progress_callback(current_progress, segments)

    # Perform Speaker Diarization ONLY if requested by user
    if enable_diarization and segments:
        try:
            from backend.diarizer import perform_diarization
            segments = perform_diarization(wav_path, segments)
        except Exception as e:
            logger.warning(f"Diarization error: {e}")

    for seg in segments:
        spk = seg.get("speaker", None)
        if spk:
            full_text_parts.append(f"{spk}: {seg['text']}")
        else:
            full_text_parts.append(seg['text'])

    full_text = "\n".join(full_text_parts)
    return segments, full_text, detected_lang
