import io
import wave
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def extract_wav_clip(wav_path: Path, start_sec: float, end_sec: float) -> bytes:
    """
    Extracts audio frames from a WAV file between start_sec and end_sec.
    Returns binary WAV file content as bytes.
    """
    if not wav_path.exists():
        raise FileNotFoundError(f"WAV file not found at {wav_path}")

    with wave.open(str(wav_path), 'rb') as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()

        start_frame = max(0, int(start_sec * framerate))
        end_frame = min(n_frames, int(end_sec * framerate))

        # Ensure clip is at least 0.5 seconds if possible
        min_frames = int(0.5 * framerate)
        if end_frame - start_frame < min_frames:
            end_frame = min(n_frames, start_frame + min_frames)

        num_frames_to_read = max(1, end_frame - start_frame)

        wf.setpos(start_frame)
        frames = wf.readframes(num_frames_to_read)

        out_buf = io.BytesIO()
        with wave.open(out_buf, 'wb') as out_wf:
            out_wf.setnchannels(n_channels)
            out_wf.setsampwidth(sampwidth)
            out_wf.setframerate(framerate)
            out_wf.writeframes(frames)

        return out_buf.getvalue()
