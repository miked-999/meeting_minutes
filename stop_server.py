#!/usr/bin/env python3
"""
Stop Script for Meeting Transcribe Web Application.
Kills all running uvicorn / run_server.py processes and frees port 8000.
"""
import os
import signal
import subprocess

def stop_server():
    print("Stopping Meeting Transcribe Web Server...")
    
    # 1. Kill via pkill on run_server.py and uvicorn
    try:
        subprocess.run(["pkill", "-9", "-f", "run_server.py"], stderr=subprocess.DEVNULL)
        subprocess.run(["pkill", "-9", "-f", "uvicorn"], stderr=subprocess.DEVNULL)
    except Exception:
        pass

    # 2. Kill any process listening on port 8000
    try:
        lsof_out = subprocess.check_output(["lsof", "-t", "-i", ":8000"]).decode().strip()
        if lsof_out:
            for pid_str in lsof_out.split():
                try:
                    pid = int(pid_str)
                    os.kill(pid, signal.SIGKILL)
                    print(f"Killed process {pid} listening on port 8000")
                except Exception:
                    pass
    except Exception:
        pass

    print("✅ App server stopped successfully! Port 8000 is clear.")

if __name__ == "__main__":
    stop_server()
