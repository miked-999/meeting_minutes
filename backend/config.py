import os
from pathlib import Path

# Disable Hugging Face symlink warnings/errors on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

BASE_DIR = Path(__file__).resolve().parent.parent

# Storage Directories
UPLOAD_DIR = BASE_DIR / "uploads"
CONVERTED_DIR = BASE_DIR / "converted"
EXPORT_DIR = BASE_DIR / "exports"
MODELS_DIR = BASE_DIR / "models_cache"
DATABASE_URL = f"sqlite:///{BASE_DIR}/meeting_minutes.db"

# Create directories if they don't exist
for folder in [UPLOAD_DIR, CONVERTED_DIR, EXPORT_DIR, MODELS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# Application Settings
DEFAULT_WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")  # Options: tiny, small, medium
DEVICE = os.getenv("WHISPER_DEVICE", "auto")  # Options: auto, cpu, cuda
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "default")  # float16, int8, float32, default

# Data Retention & Disk Cleanup Settings (Default: 7 Days)
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))
APP_VERSION = "1.0.0"

# Authentication Settings (Keycloak)
ENABLE_KEYCLOAK = os.getenv("ENABLE_KEYCLOAK", "false").lower() == "true"
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080/realms/master")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "meeting-minutes-app")
