FROM python:3.10-slim

# Prevent Python from writing .pyc files & enable unbuffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODELS_CACHE_DIR=/app/models_cache \
    DATABASE_URL=sqlite:////app/data/meeting_minutes.db

# Install system dependencies including FFmpeg and libsndfile1 for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY download_models.py .
COPY run_server.py .
COPY cleanup.py .
COPY stop_server.py .

# Create persistent storage directories with proper permissions
RUN mkdir -p /app/models_cache /app/data /app/uploads /app/converted /app/exports /app/logs

EXPOSE 8000

# Default entrypoint runs FastAPI server
CMD ["python", "run_server.py"]
