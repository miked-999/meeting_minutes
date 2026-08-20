import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from backend.config import BASE_DIR

# Ensure logs directory exists
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

USAGE_LOG_PATH = LOGS_DIR / "app_usage.log"

# Set up dedicated audit logger
audit_logger = logging.getLogger("audit_logger")
audit_logger.setLevel(logging.INFO)

if not audit_logger.handlers:
    file_handler = logging.FileHandler(str(USAGE_LOG_PATH), encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(file_handler)

def log_audit_event(
    event_type: str,
    job_id: Optional[str] = None,
    filename: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    db_session = None
):
    """
    Logs structured audit telemetry event to logs/app_usage.log and SQLite AuditLog table.
    """
    event_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
        "job_id": job_id or "N/A",
        "filename": filename or "N/A",
        "details": details or {}
    }

    # 1. Write structured JSON line to logs/app_usage.log
    audit_logger.info(json.dumps(event_data))

    # 2. Store in SQLite database if db_session provided
    if db_session is not None:
        try:
            from backend.models import AuditLog
            log_entry = AuditLog(
                event_type=event_type,
                job_id=job_id,
                filename=filename,
                details_json=json.dumps(details or {})
            )
            db_session.add(log_entry)
            db_session.commit()
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to record DB audit log: {e}")

    return event_data
