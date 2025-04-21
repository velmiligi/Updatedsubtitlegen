#!/bin/bash

# Start Redis server in the background
echo "Starting Redis server..."
redis-server --daemonize yes

# Start Celery worker in the background
echo "Starting Celery worker..."
celery -A celery_worker.celery_app worker --loglevel=info &

# Start the Flask application with Gunicorn
echo "Starting Whisper Subtitler application..."
gunicorn --bind 0.0.0.0:5000 --worker-class=gthread --workers=2 --threads=4 --reload main:app