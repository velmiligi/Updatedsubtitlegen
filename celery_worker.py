import os
import tempfile
import time
import logging
import uuid
import datetime
import requests
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure
import config

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Celery instance directly with config values
celery_app = Celery('whisper_subtitler',
                   broker=config.Config.CELERY_BROKER_URL,
                   backend=config.Config.CELERY_RESULT_BACKEND)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# These imports need to be after celery_app creation to avoid circular imports
from models import SubtitleTask
from whisper_subtitler import process_file
from gofile_api import upload_to_gofile

# We'll use a function to get the app and db when needed
def get_app_context():
    from app import app, db
    return app, db

@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    """Update task status when task starts."""
    app, db = get_app_context()
    with app.app_context():
        # Find the task in DB by task ID
        db_task = SubtitleTask.query.filter_by(task_id=kwargs.get('args', [''])[0]).first()
        if db_task:
            db_task.celery_status = 'STARTED'
            db_task.progress = 'Task started'
            db.session.commit()

@task_postrun.connect
def task_postrun_handler(task_id, task, retval, state, *args, **kwargs):
    """Update task status when task completes."""
    app, db = get_app_context()
    with app.app_context():
        # Find the task in DB by task ID
        db_task = SubtitleTask.query.filter_by(task_id=kwargs.get('args', [''])[0]).first()
        if db_task and state == 'SUCCESS':
            db_task.status = 'completed'
            db_task.celery_status = 'SUCCESS'
            db_task.progress = 'Task completed successfully'
            db_task.completed_at = datetime.datetime.utcnow()
            db.session.commit()

@task_failure.connect
def task_failure_handler(task_id, exception, args, kwargs, traceback, einfo, *args_, **kwargs_):
    """Update task status when task fails."""
    app, db = get_app_context()
    with app.app_context():
        # Find the task in DB by task ID
        db_task = SubtitleTask.query.filter_by(task_id=args[0]).first()
        if db_task:
            db_task.status = 'failed'
            db_task.celery_status = 'FAILURE'
            db_task.message = str(exception)
            db_task.progress = f'Task failed: {str(exception)}'
            db.session.commit()

@celery_app.task(bind=True, name='generate_subtitles')
def generate_subtitles(self, task_id):
    """Celery task to generate subtitles from an audio/video file."""
    try:
        app, db = get_app_context()
        with app.app_context():
            # Get task from database
            task = SubtitleTask.query.filter_by(task_id=task_id).first()
            
            if not task:
                raise ValueError(f"Task with ID {task_id} not found")
            
            # Download file from Gofile
            self.update_state(state='PROCESSING', meta={'progress': 'Downloading file...'})
            task.celery_status = 'PROCESSING'
            task.progress = 'Downloading file...'
            db.session.commit()
            
            # Create a temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(task.original_filename)[1])
            os.close(temp_fd)
            
            try:
                # Download the file
                response = requests.get(task.input_gofile_link, stream=True)
                response.raise_for_status()
                
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192): 
                        if chunk:
                            f.write(chunk)
                
                # Process the file with Whisper
                self.update_state(state='PROCESSING', meta={'progress': 'Generating subtitles...'})
                task.celery_status = 'PROCESSING'
                task.progress = 'Generating subtitles...'
                db.session.commit()
                
                subtitle_path = process_file(
                    temp_path, 
                    language=task.language, 
                    model=task.model, 
                    format_type=task.format_type,
                    output_language=task.output_language
                )
                
                # Upload subtitles to Gofile
                self.update_state(state='UPLOADING', meta={'progress': 'Uploading subtitle file...'})
                task.celery_status = 'UPLOADING'
                task.progress = 'Uploading subtitle file...'
                db.session.commit()
                
                subtitle_filename = f"{os.path.splitext(task.original_filename)[0]}.{task.format_type}"
                
                upload_result = upload_to_gofile(subtitle_path, subtitle_filename)
                
                # Update task with result information
                task.subtitle_gofile_id = upload_result['fileId']
                task.subtitle_gofile_link = upload_result['downloadPage']
                task.subtitle_filename = subtitle_filename
                task.status = 'completed'
                task.completed_at = datetime.datetime.utcnow()
                task.progress = 'Subtitles generated successfully'
                
                db.session.commit()
                
                # Clean up temporary subtitle file
                if os.path.exists(subtitle_path):
                    os.remove(subtitle_path)
                
                return {
                    'status': 'success',
                    'task_id': task_id,
                    'subtitle_gofile_link': task.subtitle_gofile_link
                }
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
    except Exception as e:
        logger.error(f"Error generating subtitles: {str(e)}")
        app, db = get_app_context()
        with app.app_context():
            task = SubtitleTask.query.filter_by(task_id=task_id).first()
            if task:
                task.status = 'failed'
                task.message = str(e)
                task.progress = f"Error: {str(e)}"
                db.session.commit()
        
        raise
