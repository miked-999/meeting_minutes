import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Text, DateTime, Boolean
from backend.database import Base

class TranscriptionJob(Base):
    __tablename__ = "transcription_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    converted_filename = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=False)
    duration_seconds = Column(Float, nullable=True, default=0.0)
    
    # Status tracking
    status = Column(String(50), nullable=False, default="QUEUED")  # QUEUED, CONVERTING, TRANSCRIBING, COMPLETED, FAILED
    progress = Column(Float, nullable=False, default=0.0)  # 0.0 to 100.0
    current_stage = Column(String(255), nullable=False, default="Queued")
    
    # Transcription settings & output
    model_size = Column(String(50), nullable=False, default="small")
    language = Column(String(20), nullable=True, default="en")
    enable_diarization = Column(Boolean, nullable=False, default=False)
    transcript_json = Column(Text, nullable=True)  # JSON string of segments [{start, end, text, speaker}]
    full_text = Column(Text, nullable=True)
    
    # Generated document export paths
    docx_path = Column(String(500), nullable=True)
    pdf_path = Column(String(500), nullable=True)
    
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        import json
        segments = []
        if self.transcript_json:
            try:
                segments = json.loads(self.transcript_json)
            except Exception:
                segments = []

        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "duration_seconds": round(self.duration_seconds or 0, 1),
            "status": self.status,
            "progress": round(self.progress, 1),
            "current_stage": self.current_stage,
            "model_size": self.model_size,
            "language": self.language or "Auto",
            "enable_diarization": self.enable_diarization,
            "full_text": self.full_text or "",
            "segments": segments,
            "has_docx": bool(self.docx_path),
            "has_pdf": bool(self.pdf_path),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
