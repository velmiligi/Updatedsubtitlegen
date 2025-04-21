import os

class Config:
    """Base configuration."""
    # Flask config
    SECRET_KEY = os.environ.get('SESSION_SECRET', 'whisper-subtitler-secret-key')
    
    # SQLAlchemy config
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///subtitles.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Celery config
    CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # Whisper config
    WHISPER_MODELS = ['tiny', 'base', 'small', 'medium', 'large']
    DEFAULT_WHISPER_MODEL = 'base'
    
    # Gofile config
    GOFILE_API_URL = 'https://api.gofile.io'
    
    # File upload config
    MAX_CONTENT_LENGTH = 512 * 1024 * 1024  # 512 MB
    ALLOWED_EXTENSIONS = {'mp3', 'mp4', 'wav', 'avi', 'mov', 'mkv', 'flac', 'ogg', 'm4a'}
    
    # Session config
    SESSION_TYPE = 'filesystem'
    
    # CORS
    CORS_HEADERS = 'Content-Type'
