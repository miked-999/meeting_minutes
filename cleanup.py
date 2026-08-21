#!/usr/bin/env python3
"""
Standalone Data Retention & Disk Cleanup Script.
Usage:
    python cleanup.py [--days 7]
"""
import sys
import argparse
import logging
from backend.config import RETENTION_DAYS
from backend.cleanup import cleanup_expired_jobs

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    parser = argparse.ArgumentParser(description="Clean up expired meeting transcription jobs and files.")
    parser.add_argument("--days", type=int, default=RETENTION_DAYS, help=f"Retention window in days (default: {RETENTION_DAYS})")
    args = parser.parse_args()

    result = cleanup_expired_jobs(max_age_days=args.days)
    if result.get("status") == "success":
        print(f"✅ Cleanup successful: {result['jobs_removed']} jobs removed, {result['files_removed']} files deleted ({result['freed_mb']} MB freed).")
        sys.exit(0)
    else:
        print(f"❌ Cleanup failed: {result.get('detail')}")
        sys.exit(1)

if __name__ == "__main__":
    main()
