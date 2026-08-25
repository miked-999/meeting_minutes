from unittest.mock import patch
from download_models import download_model, download_ecapa

def test_download_model():
    with patch("download_models.WhisperModel") as mock_whisper:
        download_model("tiny")
        mock_whisper.assert_called_once()

def test_download_ecapa():
    with patch("speechbrain.inference.speaker.EncoderClassifier.from_hparams") as mock_encoder:
        download_ecapa()
        mock_encoder.assert_called_once()
