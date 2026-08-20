import logging
import wave
import struct
import numpy as np
from pathlib import Path
from scipy.fft import rfft
from scipy.signal import get_window
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

def extract_audio_segment_features(audio_data: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    """
    Extracts acoustic voice embedding features (MFCC-like filterbanks, spectral centroid,
    energy, and pitch statistics) for an audio segment.
    """
    if len(audio_data) < sample_rate * 0.2:
        # Padded fallback for very short audio clips
        return np.zeros(26)

    # Frame parameters: 25ms frame, 10ms hop
    frame_len = int(sample_rate * 0.025)
    hop_len = int(sample_rate * 0.010)
    window = get_window('hamming', frame_len)

    num_frames = (len(audio_data) - frame_len) // hop_len + 1
    if num_frames < 1:
        return np.zeros(26)

    # Filterbank energies across 20 mel-scale frequency bands
    n_filters = 20
    low_freq_mel = 0
    high_freq_mel = 2595 * np.log10(1 + (sample_rate / 2) / 700)
    mel_pts = np.linspace(low_freq_mel, high_freq_mel, n_filters + 2)
    hz_pts = 700 * (10**(mel_pts / 2595) - 1)
    bin_pts = np.floor((frame_len + 1) * hz_pts / sample_rate).astype(int)

    nfft = frame_len
    fbanks = np.zeros((n_filters, int(np.floor(nfft / 2 + 1))))
    for m in range(1, n_filters + 1):
        f_m_minus = bin_pts[m - 1]
        f_m = bin_pts[m]
        f_m_plus = bin_pts[m + 1]

        for k in range(f_m_minus, f_m):
            fbanks[m - 1, k] = (k - bin_pts[m - 1]) / (f_m - bin_pts[m - 1])
        for k in range(f_m, f_m_plus):
            fbanks[m - 1, k] = (bin_pts[m + 1] - k) / (bin_pts[m + 1] - f_m)

    frame_features = []
    for i in range(num_frames):
        start_idx = i * hop_len
        end_idx = start_idx + frame_len
        frame = audio_data[start_idx:end_idx] * window
        
        # Power spectrum
        mag_spec = np.abs(rfft(frame, n=nfft))
        pow_spec = (1.0 / nfft) * (mag_spec ** 2)
        
        # Filterbank log energy
        filter_energies = np.dot(fbanks, pow_spec)
        filter_energies = np.where(filter_energies == 0, np.finfo(float).eps, filter_energies)
        log_filter_energies = np.log(filter_energies)

        # Spectral centroid & energy
        freqs = np.linspace(0, sample_rate / 2, len(mag_spec))
        spec_sum = np.sum(pow_spec) + 1e-10
        centroid = np.sum(freqs * pow_spec) / spec_sum
        energy = np.sum(frame ** 2)

        feat_vector = np.concatenate([log_filter_energies, [centroid, energy]])
        frame_features.append(feat_vector)

    frame_features = np.array(frame_features)
    
    # Compute mean and standard deviation over frames to capture voice character
    mean_feat = np.mean(frame_features, axis=0)
    std_feat = np.std(frame_features, axis=0)
    
    return np.concatenate([mean_feat, std_feat])

def perform_diarization(wav_path: Path, segments: list) -> list:
    """
    Performs speaker diarization by clustering acoustic voice embeddings of segments.
    Appends 'speaker' field (e.g. 'Speaker 1', 'Speaker 2') to each segment.
    """
    if not segments:
        return segments

    if len(segments) == 1:
        segments[0]["speaker"] = "Speaker 1"
        return segments

    try:
        # Load WAV file
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
            if len(chunk) > 0:
                emb = extract_audio_segment_features(chunk, sample_rate)
                embeddings.append(emb)
                valid_indices.append(idx)
            else:
                embeddings.append(np.zeros(44))
                valid_indices.append(idx)

        embeddings = np.array(embeddings)

        if len(embeddings) < 2:
            for seg in segments:
                seg["speaker"] = "Speaker 1"
            return segments

        # Standardize feature vectors
        scaler = StandardScaler()
        norm_embeddings = scaler.fit_transform(embeddings)

        # Automatically determine optimal speaker count (from 1 to min(5, n_segments))
        max_speakers = min(5, len(segments))
        best_k = 1
        best_score = -1.0

        if len(segments) >= 3 and max_speakers >= 2:
            for k in range(2, max_speakers + 1):
                clustering = AgglomerativeClustering(n_clusters=k, metric='euclidean', linkage='ward')
                labels = clustering.fit_predict(norm_embeddings)
                if len(set(labels)) > 1:
                    score = silhouette_score(norm_embeddings, labels)
                    if score > best_score:
                        best_score = score
                        best_k = k

        # If silhouette score is low, default to 2 speakers if distinct clusters exist, else 1
        if best_k > 1 and best_score < 0.1:
            best_k = 2 if len(segments) >= 4 else 1

        logger.info(f"Diarization identified {best_k} speaker(s) (silhouette score: {round(best_score, 3)})")

        if best_k == 1:
            for seg in segments:
                seg["speaker"] = "Speaker 1"
        else:
            clustering = AgglomerativeClustering(n_clusters=best_k, metric='euclidean', linkage='ward')
            cluster_labels = clustering.fit_predict(norm_embeddings)
            
            # Map numeric clusters to Speaker 1, Speaker 2 ordered by first appearance
            speaker_map = {}
            next_speaker_num = 1
            
            for idx, label in enumerate(cluster_labels):
                if label not in speaker_map:
                    speaker_map[label] = f"Speaker {next_speaker_num}"
                    next_speaker_num += 1
                segments[idx]["speaker"] = speaker_map[label]

    except Exception as e:
        logger.error(f"Diarization failed gracefully: {e}. Falling back to default Speaker 1.")
        for seg in segments:
            seg["speaker"] = "Speaker 1"

    return segments
