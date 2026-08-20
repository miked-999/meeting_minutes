import logging
import wave
import torch
import numpy as np
from pathlib import Path
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score

from backend.config import MODELS_DIR

logger = logging.getLogger(__name__)

_SPEAKER_CLASSIFIER = None

def get_speaker_classifier():
    """Loads and caches SpeechBrain's ECAPA-TDNN deep speaker recognition model."""
    global _SPEAKER_CLASSIFIER
    if _SPEAKER_CLASSIFIER is not None:
        return _SPEAKER_CLASSIFIER

    try:
        from speechbrain.inference.speaker import EncoderClassifier

        save_dir = str(MODELS_DIR / "spkrec-ecapa-voxceleb")
        logger.info(f"Loading SpeechBrain ECAPA-TDNN speaker embedding model from {save_dir}...")
        
        _SPEAKER_CLASSIFIER = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=save_dir,
            run_opts={"device": "cuda" if torch.cuda.is_available() else "cpu"}
        )
        return _SPEAKER_CLASSIFIER
    except Exception as e:
        logger.warning(f"Failed to load SpeechBrain ECAPA-TDNN model: {e}")
        return None

def extract_deep_speaker_embedding(classifier, audio_tensor: torch.Tensor) -> np.ndarray:
    """
    Extracts a 192-dimensional deep voice embedding vector for an audio segment.
    """
    with torch.no_grad():
        # Ensure audio length is at least 0.4 seconds (6400 samples at 16kHz) by padding
        if audio_tensor.shape[1] < 6400:
            pad_amount = 6400 - audio_tensor.shape[1]
            audio_tensor = torch.nn.functional.pad(audio_tensor, (0, pad_amount))

        embeddings = classifier.encode_batch(audio_tensor)
        # Squeeze batch dimension to get 1D numpy array
        emb_np = embeddings.squeeze().cpu().numpy()
        # L2 normalize embedding vector
        norm = np.linalg.norm(emb_np)
        if norm > 0:
            emb_np = emb_np / norm
        return emb_np

def perform_diarization(wav_path: Path, segments: list) -> list:
    """
    Performs deep speaker diarization using SpeechBrain ECAPA-TDNN embeddings & Cosine Distance Clustering.
    Attaches 'speaker' field (e.g. 'Speaker 1', 'Speaker 2', 'Speaker 3') to each segment.
    """
    if not segments:
        return segments

    if len(segments) == 1:
        segments[0]["speaker"] = "Speaker 1"
        return segments

    classifier = get_speaker_classifier()
    if classifier is None:
        logger.warning("ECAPA-TDNN classifier unavailable. Falling back to single speaker.")
        for seg in segments:
            seg["speaker"] = "Speaker 1"
        return segments

    try:
        # Load WAV file into float tensor
        with wave.open(str(wav_path), 'rb') as wf:
            sample_rate = wf.getframerate()
            num_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            raw_bytes = wf.readframes(wf.getnframes())

        if sample_width == 2:
            audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            audio = np.frombuffer(raw_bytes, dtype=np.int8).astype(np.float32) / 128.0

        if num_channels > 1:
            audio = audio[::num_channels]

        embeddings = []
        valid_indices = []

        for idx, seg in enumerate(segments):
            start_sec = seg.get("start", 0.0)
            end_sec = seg.get("end", 0.0)
            
            start_sample = int(start_sec * sample_rate)
            end_sample = int(end_sec * sample_rate)
            
            chunk = audio[start_sample:end_sample]
            if len(chunk) > 800:  # > 50ms of audio
                chunk_tensor = torch.tensor(chunk, dtype=torch.float32).unsqueeze(0)
                emb = extract_deep_speaker_embedding(classifier, chunk_tensor)
                embeddings.append(emb)
                valid_indices.append(idx)

        if not embeddings:
            for seg in segments:
                seg["speaker"] = "Speaker 1"
            return segments

        embeddings = np.array(embeddings)
        n_samples = len(embeddings)

        if n_samples < 2:
            for seg in segments:
                seg["speaker"] = "Speaker 1"
            return segments

        max_speakers = min(20, n_samples)
        best_k = 1
        best_score = -1.0
        best_labels = np.zeros(n_samples, dtype=int)

        # 1. Test Adaptive Cosine Distance Thresholds
        thresholds_to_test = [0.20, 0.25, 0.28, 0.32, 0.36, 0.40]
        for thresh in thresholds_to_test:
            clustering = AgglomerativeClustering(
                n_clusters=None,
                distance_threshold=thresh,
                metric='cosine',
                linkage='average'
            )
            labels = clustering.fit_predict(embeddings)
            k = len(set(labels))
            if 2 <= k <= max_speakers:
                score = silhouette_score(embeddings, labels, metric='cosine')
                logger.info(f"Tested distance_threshold={thresh} -> identified {k} clusters (silhouette score: {round(score, 3)})")
                if score > best_score:
                    best_score = score
                    best_k = k
                    best_labels = labels

        # 2. Test Fixed k Values in Range [2, max_speakers]
        for k in range(2, max_speakers + 1):
            clustering = AgglomerativeClustering(n_clusters=k, metric='cosine', linkage='average')
            labels = clustering.fit_predict(embeddings)
            if len(set(labels)) > 1:
                score = silhouette_score(embeddings, labels, metric='cosine')
                if score > best_score:
                    best_score = score
                    best_k = k
                    best_labels = labels

        logger.info(f"Final Deep Diarization Choice: {best_k} speaker(s) across {n_samples} segments (best silhouette score: {round(best_score, 3)})")

        if best_k == 1:
            for seg in segments:
                seg["speaker"] = "Speaker 1"
        else:
            # Map numeric cluster labels to Speaker 1, Speaker 2, Speaker 3 in order of first appearance
            speaker_map = {}
            next_speaker_num = 1
            
            for idx_in_valid, orig_idx in enumerate(valid_indices):
                lbl = best_labels[idx_in_valid]
                if lbl not in speaker_map:
                    speaker_map[lbl] = f"Speaker {next_speaker_num}"
                    next_speaker_num += 1
                segments[orig_idx]["speaker"] = speaker_map[lbl]

            # Assign default to any unmapped segment
            for seg in segments:
                if "speaker" not in seg:
                    seg["speaker"] = "Speaker 1"

    except Exception as e:
        logger.error(f"Deep Diarization failed: {e}. Falling back to default Speaker 1.")
        for seg in segments:
            seg["speaker"] = "Speaker 1"

    return segments
