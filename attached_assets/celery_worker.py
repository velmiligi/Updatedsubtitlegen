import os
import celery
import tempfile
import requests
import json
import logging
import time
import datetime
import whisper_subtitler
from celery import Celery, signals, Task
from celery.utils.log import get_task_logger

# Configure logging
logger = get_task_logger(__name__)
logging.basicConfig(level=logging.INFO)

# Configure Celery
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
celery_app = Celery('whisper_subtitler', broker=redis_url, backend=redis_url)

# Define default Celery settings
celery_app.conf.update(
    worker_concurrency=2,  # Number of simultaneous workers
    task_acks_late=True,   # Only acknowledge task after it's been processed
    task_time_limit=3600,  # 1 hour time limit per task
    task_soft_time_limit=3300,  # 55 minutes soft time limit
    broker_connection_retry_on_startup=True,  # Retry connection on startup
)

# Custom task base class
class LoggingTask(Task):
    """Base task class with enhanced logging."""
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {task_id} failed: {exc}\nArgs: {args}\nKwargs: {kwargs}")
        super().on_failure(exc, task_id, args, kwargs, einfo)
    
    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Task {task_id} succeeded with result: {retval}")
        super().on_success(retval, task_id, args, kwargs)

@signals.worker_ready.connect
def at_start(sender, **k):
    """Log when Celery worker starts."""
    logger.info("Celery worker is ready for processing subtitle tasks")

def get_gofile_server():
    """Get the best server for uploading to Gofile."""
    try:
        response = requests.get('https://api.gofile.io/getServer')
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'ok':
                return data.get('data', {}).get('server')
    except Exception as e:
        logger.error(f"Error getting Gofile server: {str(e)}")
    return None

def upload_to_gofile(file_path, file_name=None):
    """Upload a file to Gofile and return the download link."""
    if not file_name:
        file_name = os.path.basename(file_path)
        
    server = get_gofile_server()
    if not server:
        raise Exception("Failed to get Gofile server")
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_name, f)}
            response = requests.post(f'https://{server}.gofile.io/uploadFile', files=files)
            
            if response.status_code != 200:
                raise Exception(f"Gofile upload failed with status {response.status_code}")
                
            data = response.json()
            if data.get('status') != 'ok':
                raise Exception(f"Gofile upload error: {data.get('status')}")
                
            file_id = data.get('data', {}).get('fileId')
            download_page = data.get('data', {}).get('downloadPage')
            
            return {
                'file_id': file_id,
                'download_page': download_page,
                'direct_link': f"https://{server}.gofile.io/download/{file_id}/{file_name}"
            }
    except Exception as e:
        logger.error(f"Error uploading to Gofile: {str(e)}")
        raise

def download_from_gofile(file_id, output_path):
    """Download a file from Gofile using the file ID."""
    server = get_gofile_server()
    if not server:
        raise Exception("Failed to get Gofile server")
    
    # Get file details
    try:
        response = requests.get(f"https://api.gofile.io/getContent?contentId={file_id}")
        
        if response.status_code != 200:
            raise Exception(f"Gofile API error: {response.status_code}")
            
        data = response.json()
        if data.get('status') != 'ok':
            raise Exception(f"Gofile content error: {data.get('status')}")
            
        # Get download link and file details
        contents = data.get('data', {}).get('contents', {})
        if not contents:
            raise Exception("No file found in Gofile response")
            
        # Get the first file (we only expect one)
        file_info = next(iter(contents.values()))
        
        download_link = file_info.get('link')
        if not download_link:
            raise Exception("Download link not found in Gofile response")
            
        # Download the file
        with requests.get(download_link, stream=True) as r:
            r.raise_for_status()
            with open(output_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
        return True
        
    except Exception as e:
        logger.error(f"Error downloading from Gofile: {str(e)}")
        raise

@celery_app.task(bind=True, base=LoggingTask)
def process_subtitle_task(self, gofile_id, language='auto', model='base', format_type='srt'):
    """
    Process subtitle generation as a background task.
    
    Args:
        gofile_id: The Gofile ID of the uploaded video/audio file
        language: The language code or 'auto' for auto-detection
        model: The Whisper model size to use ('tiny', 'base', 'small', 'medium', 'large')
        format_type: The output format ('srt', 'vtt', 'txt')
        
    Returns:
        dict: Results including task status and gofile links
    """
    # Create temporary working directories
    temp_dir = tempfile.mkdtemp(prefix='whisper_subtitler_')
    input_file_path = os.path.join(temp_dir, f"input_file.mp4")  # Default extension
    
    self.update_state(state='STARTED', meta={'status': 'Downloading input file'})
    
    try:
        # 1. Download the file from Gofile
        logger.info(f"Downloading file from Gofile: {gofile_id}")
        download_from_gofile(gofile_id, input_file_path)
        
        # 2. Process with Whisper
        self.update_state(state='PROCESSING', meta={'status': 'Generating subtitles'})
        logger.info(f"Processing file with Whisper: {input_file_path}")
        logger.info(f"Parameters: language={language}, model={model}, format={format_type}")
        
        subtitle_path = whisper_subtitler.process_file(
            input_file_path,
            language=language,
            model=model,
            format_type=format_type
        )
        
        # 3. Upload the result to Gofile
        self.update_state(state='UPLOADING', meta={'status': 'Uploading subtitle file'})
        subtitle_filename = os.path.basename(subtitle_path)
        
        logger.info(f"Uploading subtitle file to Gofile: {subtitle_path}")
        result = upload_to_gofile(subtitle_path, subtitle_filename)
        
        # 4. Return results
        return {
            'status': 'completed',
            'subtitle_file_path': subtitle_path,
            'subtitle_file_name': subtitle_filename,
            'subtitle_file_id': result['file_id'],
            'subtitle_download_link': result['download_page'],
            'message': 'Subtitles generated successfully'
        }
        
    except Exception as e:
        logger.error(f"Error in subtitle generation task: {str(e)}")
        # Clean up any temporary files regardless of error
        try:
            if os.path.exists(temp_dir):
                for file in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, file))
                os.rmdir(temp_dir)
        except Exception as cleanup_error:
            logger.error(f"Error cleaning temp files: {str(cleanup_error)}")
            
        raise Exception(f"Subtitle generation failed: {str(e)}")
        
    finally:
        # Clean up temporary files
        try:
            if os.path.exists(temp_dir):
                for file in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, file))
                os.rmdir(temp_dir)
        except Exception as cleanup_error:
            logger.error(f"Error cleaning temp files: {str(cleanup_error)}")