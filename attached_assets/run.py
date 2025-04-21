#!/usr/bin/env python3
"""
Launcher script for WhisperSubtitler using Gunicorn with optimized multi-user settings.
This script ensures the app is started with the proper settings for concurrent users.
"""
import os
import sys
import subprocess
import argparse

def main():
    """Run the WhisperSubtitler application with optimized Gunicorn settings."""
    parser = argparse.ArgumentParser(description="Run WhisperSubtitler application")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker processes")
    parser.add_argument("--threads", type=int, default=2, help="Number of threads per worker")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--timeout", type=int, default=120, help="Worker timeout in seconds")
    args = parser.parse_args()
    
    # Construct the Gunicorn command with optimized settings
    cmd = [
        "gunicorn",
        f"--bind={args.host}:{args.port}",
        f"--workers={args.workers}",
        f"--threads={args.threads}",
        "--worker-class=sync",
        "--worker-connections=1000",
        f"--timeout={args.timeout}",
        "--keep-alive=5",
        "--reuse-port",
        "--reload",
        "main:app"
    ]
    
    print(f"Starting WhisperSubtitler with {args.workers} workers and {args.threads} threads per worker")
    print(f"Listening on {args.host}:{args.port}")
    
    try:
        # Execute Gunicorn with the optimized settings
        process = subprocess.run(cmd)
        return process.returncode
    except KeyboardInterrupt:
        print("\nShutting down WhisperSubtitler...")
        return 0
    except Exception as e:
        print(f"Error starting WhisperSubtitler: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())