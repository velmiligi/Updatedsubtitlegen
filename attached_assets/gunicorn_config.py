"""
Gunicorn configuration file for optimized multi-user support.
This configuration enables multiple worker processes and threads
for better handling of concurrent users and transcription tasks.
"""
import multiprocessing

# Worker processes - recommended to be 2-4 x number of CPU cores
# For Replit, we'll set to 4 workers as a good balance
workers = 4  

# Threads per worker
threads = 2

# Worker class
worker_class = 'sync'  # 'sync' is most compatible, alternatives are 'eventlet', 'gevent'

# Connection parameters
worker_connections = 1000  # Max concurrent connections per worker
timeout = 120  # Increase timeout for long-running transcription tasks
keepalive = 5  # How long to wait for requests on a Keep-Alive connection

# Server socket
bind = '0.0.0.0:5000'
backlog = 2048  # Maximum number of pending connections

# Server mechanics
daemon = False
reload = True  # Auto-reload on code changes
reuse_port = True

# Logging
loglevel = 'info'
accesslog = '-'  # Log to stdout
errorlog = '-'  # Log to stderr

# Process naming
proc_name = 'whisper_subtitler'

# Server hooks
def on_starting(server):
    """Log when server starts."""
    server.log.info("Starting WhisperSubtitler with multiple worker support")

def on_exit(server):
    """Log when server exits."""
    server.log.info("Shutting down WhisperSubtitler")