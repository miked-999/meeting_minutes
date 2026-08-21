import os
import subprocess
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Auto-resolve static FFmpeg/FFprobe binaries via static_ffmpeg package
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception as e:
    logger.warning(f"static_ffmpeg add_paths failed or skipped: {e}")

def probe_media_duration(file_path: Path) -> float:
    """Uses ffprobe to return total duration in seconds of a media file."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        if "format" in data and "duration" in data["format"]:
            return float(data["format"]["duration"])
        # Fallback check streams
        for stream in data.get("streams", []):
            if "duration" in stream:
                return float(stream["duration"])
    except Exception as e:
        logger.warning(f"ffprobe failed to extract duration for {file_path}: {e}")
    return 0.0

def convert_to_wav(input_path: Path, output_wav_path: Path) -> float:
    """
    Converts any video or audio file into a 16kHz 16-bit Mono WAV file for Whisper.
    Returns the media duration in seconds.
    """
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output file if exists
        "-i", str(input_path),
        "-vn",  # Disable video stream
        "-acodec", "pcm_s16le",  # 16-bit PCM
        "-ar", "16000",  # 16kHz sampling rate
        "-ac", "1",  # 1 channel (mono)
        str(output_wav_path)
    ]
    
    logger.info(f"Running ffmpeg conversion: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg conversion failed: {result.stderr}")
    
    duration = probe_media_duration(output_wav_path)
    if duration <= 0:
        duration = probe_media_duration(input_path)
    return duration
