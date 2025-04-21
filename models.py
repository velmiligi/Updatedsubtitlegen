import datetime
from app import db

class SubtitleTask(db.Model):
    """Model to store subtitle generation task information."""
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(255), unique=True, nullable=False)
    session_id = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='pending')
    
    # Input file information
    original_filename = db.Column(db.String(255), nullable=False)
    input_gofile_id = db.Column(db.String(255), nullable=False)
    input_gofile_link = db.Column(db.String(512), nullable=False)
    
    # Processing parameters
    language = db.Column(db.String(10), nullable=False, default='auto')
    output_language = db.Column(db.String(10), nullable=True, default='same')
    model = db.Column(db.String(20), nullable=False, default='base')
    format_type = db.Column(db.String(10), nullable=False, default='srt')
    
    # Celery task status
    celery_status = db.Column(db.String(50), nullable=True)
    progress = db.Column(db.String(255), nullable=True)
    
    # Result information
    subtitle_gofile_id = db.Column(db.String(255), nullable=True)
    subtitle_gofile_link = db.Column(db.String(512), nullable=True)
    subtitle_filename = db.Column(db.String(255), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Error handling
    message = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f"<SubtitleTask {self.task_id} ({self.status})>"
    
    def to_dict(self):
        """Convert the model to a dictionary."""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'status': self.status,
            'celery_status': self.celery_status,
            'progress': self.progress,
            'original_filename': self.original_filename,
            'input_gofile_link': self.input_gofile_link,
            'language': self.language,
            'output_language': self.output_language,
            'model': self.model,
            'format_type': self.format_type,
            'subtitle_gofile_link': self.subtitle_gofile_link,
            'subtitle_filename': self.subtitle_filename,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'completed_at': self.completed_at.strftime('%Y-%m-%d %H:%M:%S') if self.completed_at else None,
            'message': self.message
        }
