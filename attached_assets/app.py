import os
import logging
import tempfile
import uuid
import threading
import time
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from werkzeug.utils import secure_filename
import whisper_subtitler
import requests
from celery.result import AsyncResult

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")

# SQLAlchemy Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///subtitles.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Redis and Celery Configuration
app.config['REDIS_URL'] = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
app.config['CELERY_BROKER_URL'] = app.config['REDIS_URL']
app.config['CELERY_RESULT_BACKEND'] = app.config['REDIS_URL']

# Configure upload settings
UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'whisper_subtitler_uploads')
RESULTS_FOLDER = os.path.join(tempfile.gettempdir(), 'whisper_subtitler_results')
ALLOWED_EXTENSIONS = {'mp3', 'mp4', 'wav', 'avi', 'mov', 'mkv', 'flac', 'ogg', 'm4a'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 512 * 1024 * 1024  # 512MB max upload size

# Create folders if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# Initialize database
from models import db, SubtitleTask
db.init_app(app)

# Connect to Celery worker
from celery_worker import celery_app, process_subtitle_task, get_gofile_server

# Create database tables if they don't exist
with app.app_context():
    db.create_all()

# File cleanup settings
FILE_RETENTION_HOURS = 24  # Keep files for 24 hours
cleanup_lock = threading.Lock()

# Start a background thread to periodically clean up old files
def cleanup_old_files():
    """Remove files older than FILE_RETENTION_HOURS."""
    while True:
        try:
            with cleanup_lock:
                logger.info("Running scheduled file cleanup")
                cutoff_time = datetime.now() - timedelta(hours=FILE_RETENTION_HOURS)
                
                # Clean upload folder
                for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if file_modified < cutoff_time:
                        try:
                            if os.path.isfile(filepath):
                                os.remove(filepath)
                                logger.info(f"Removed old upload file: {filepath}")
                        except Exception as e:
                            logger.error(f"Error removing file {filepath}: {str(e)}")
                
                # Clean results folder
                for filename in os.listdir(app.config['RESULTS_FOLDER']):
                    filepath = os.path.join(app.config['RESULTS_FOLDER'], filename)
                    file_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if file_modified < cutoff_time:
                        try:
                            if os.path.isfile(filepath):
                                os.remove(filepath)
                                logger.info(f"Removed old result file: {filepath}")
                        except Exception as e:
                            logger.error(f"Error removing file {filepath}: {str(e)}")
        except Exception as e:
            logger.error(f"Error in cleanup thread: {str(e)}")
        
        # Sleep for 1 hour before next cleanup
        time.sleep(3600)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        # Generate unique IDs for this session and files
        session_id = str(uuid.uuid4())
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{session_id}_{original_filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        file.save(filepath)
        logger.debug(f"File saved at {filepath}")
        
        # Get form parameters
        language = request.form.get('language', 'auto')
        model = request.form.get('model', 'base')
        format_type = request.form.get('format', 'srt')
        
        # Create a unique result filename
        result_filename = f"{session_id}_{original_filename.rsplit('.', 1)[0]}.{format_type}"
        result_path = os.path.join(app.config['RESULTS_FOLDER'], result_filename)
        
        try:
            # Process the file with WhisperSubtitler
            # The process_file function saves to a temporary location, 
            # so we'll move the result to our organized results folder
            temp_result_path = whisper_subtitler.process_file(
                filepath, 
                language=language,
                model=model,
                format_type=format_type
            )
            
            # Copy the result to our results folder with the session-specific name
            with open(temp_result_path, 'rb') as src_file, open(result_path, 'wb') as dest_file:
                dest_file.write(src_file.read())
            
            # Try to remove the temporary file
            try:
                if os.path.exists(temp_result_path):
                    os.remove(temp_result_path)
            except Exception as e:
                logger.warning(f"Could not remove temp file {temp_result_path}: {str(e)}")
            
            # Store result information in session for download
            session['result_path'] = result_path
            session['original_filename'] = original_filename.rsplit('.', 1)[0]
            session['format_type'] = format_type
            session['session_id'] = session_id
            
            flash('File processed successfully!', 'success')
            return redirect(url_for('results'))
            
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            flash(f"Error processing file: {str(e)}", 'danger')
            
            # Clean up the uploaded file if processing failed
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as cleanup_error:
                logger.warning(f"Could not remove upload file after error: {str(cleanup_error)}")
                
            return redirect(url_for('index'))
    else:
        flash(f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}', 'danger')
        return redirect(url_for('index'))

@app.route('/results')
def results():
    result_path = session.get('result_path')
    if not result_path or not os.path.exists(result_path):
        flash('No results found or results expired', 'warning')
        return redirect(url_for('index'))
    
    # Read the first few lines of the subtitle file to preview
    try:
        with open(result_path, 'r', encoding='utf-8') as f:
            preview_content = ''.join(f.readlines()[:20])  # First 20 lines
    except Exception as e:
        logger.error(f"Error reading subtitle file: {str(e)}")
        preview_content = "Error reading subtitle content"
    
    return render_template('results.html', 
                          preview_content=preview_content,
                          original_filename=session.get('original_filename', 'subtitle'),
                          format_type=session.get('format_type', 'srt'))

@app.route('/download')
def download_result():
    result_path = session.get('result_path')
    if not result_path or not os.path.exists(result_path):
        flash('Results not found or expired', 'danger')
        return redirect(url_for('index'))
    
    original_filename = session.get('original_filename', 'subtitle')
    format_type = session.get('format_type', 'srt')
    download_name = f"{original_filename}.{format_type}"
    
    return send_file(result_path, 
                     as_attachment=True,
                     download_name=download_name)

@app.route('/clear')
def clear_session():
    # Clear any temporary files associated with this user's session
    result_path = session.get('result_path')
    session_id = session.get('session_id')
    
    if result_path and os.path.exists(result_path):
        try:
            os.remove(result_path)
            logger.info(f"Removed result file: {result_path}")
        except Exception as e:
            logger.error(f"Error removing result file: {str(e)}")
    
    # Try to remove any uploaded files from this session
    if session_id:
        try:
            # Look for files with the session_id prefix in the upload folder
            for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                if filename.startswith(session_id):
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                        logger.info(f"Removed upload file: {filepath}")
        except Exception as e:
            logger.error(f"Error removing session files: {str(e)}")
    
    # Clear session data
    session.clear()
    flash('Session cleared successfully', 'info')
    return redirect(url_for('index'))

@app.errorhandler(413)
def request_entity_too_large(error):
    flash('File too large. Maximum size is 512MB.', 'danger')
    return redirect(url_for('index')), 413

@app.errorhandler(500)
def server_error(error):
    flash('Server error occurred. Please try again later.', 'danger')
    return redirect(url_for('index')), 500

# API Endpoints for Gofile and Celery task management
@app.route('/api/gofile/server', methods=['GET'])
def get_server():
    """Get the best Gofile server for uploading."""
    server = get_gofile_server()
    if server:
        return jsonify({'status': 'success', 'server': server})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to get Gofile server'}), 500

@app.route('/api/task', methods=['POST'])
def create_task():
    """Create a new subtitle generation task with Gofile ID."""
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data provided'}), 400
        
        # Required fields
        gofile_id = data.get('gofile_id')
        gofile_link = data.get('gofile_link')
        original_filename = data.get('filename')
        
        if not all([gofile_id, gofile_link, original_filename]):
            return jsonify({
                'status': 'error', 
                'message': 'Missing required fields (gofile_id, gofile_link, filename)'
            }), 400
        
        # Optional parameters with defaults
        language = data.get('language', 'auto')
        model = data.get('model', 'base')
        format_type = data.get('format', 'srt')
        
        # Generate a unique session ID if not in session
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        # Start Celery task
        task = process_subtitle_task.delay(
            gofile_id=gofile_id,
            language=language,
            model=model,
            format_type=format_type
        )
        
        # Store task information in database
        subtitle_task = SubtitleTask(
            task_id=task.id,
            session_id=session['session_id'],
            status='pending',
            original_filename=original_filename,
            input_gofile_id=gofile_id,
            input_gofile_link=gofile_link,
            language=language,
            model=model,
            format_type=format_type,
            message='Task initiated'
        )
        
        db.session.add(subtitle_task)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'task_id': task.id,
            'message': 'Task created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """Get the status of a subtitle generation task."""
    try:
        # Check database first
        task_record = SubtitleTask.query.filter_by(task_id=task_id).first()
        if not task_record:
            return jsonify({'status': 'error', 'message': 'Task not found'}), 404
        
        # Check Celery task status
        task_result = AsyncResult(task_id)
        current_status = task_result.status
        
        # Update database record if needed
        if current_status != task_record.status and current_status in ('SUCCESS', 'FAILURE'):
            if current_status == 'SUCCESS':
                result = task_result.get()
                task_record.status = 'completed'
                task_record.subtitle_gofile_id = result.get('subtitle_file_id')
                task_record.subtitle_gofile_link = result.get('subtitle_download_link')
                task_record.subtitle_filename = result.get('subtitle_file_name')
                task_record.message = result.get('message', 'Subtitles generated successfully')
                task_record.completed_at = datetime.utcnow()
            else:
                task_record.status = 'failed'
                task_record.message = str(task_result.result)
            
            db.session.commit()
        
        # Return task details
        task_info = task_record.to_dict()
        task_info['celery_status'] = current_status
        
        if current_status in ('STARTED', 'PROCESSING', 'UPLOADING') and task_result.info:
            task_info['progress'] = task_result.info.get('status', 'Processing')
        
        return jsonify({'status': 'success', 'task': task_info})
        
    except Exception as e:
        logger.error(f"Error getting task status: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/my-tasks', methods=['GET'])
def get_user_tasks():
    """Get all tasks for the current user session."""
    try:
        if 'session_id' not in session:
            return jsonify({'status': 'error', 'message': 'No active session'}), 400
            
        tasks = SubtitleTask.query.filter_by(session_id=session['session_id']).order_by(
            SubtitleTask.created_at.desc()
        ).all()
        
        return jsonify({
            'status': 'success',
            'tasks': [task.to_dict() for task in tasks]
        })
        
    except Exception as e:
        logger.error(f"Error getting user tasks: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Start the background cleanup thread when the application starts
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

# Routes for task management
@app.route('/task/<task_id>')
def task_status(task_id):
    """Display the status of a subtitle generation task."""
    task = SubtitleTask.query.filter_by(task_id=task_id).first()
    if not task:
        flash('Task not found', 'danger')
        return redirect(url_for('index'))
    
    # Check if task belongs to this session
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    # Allow viewing the task even if it's from a different session
    # This helps with sharing task results or accessing across different browsers
    
    return render_template('task_status.html', task_id=task_id)

@app.route('/tasks')
def tasks_list():
    """Display a list of all tasks for the current user session."""
    # Ensure we have a session ID
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    return render_template('tasks_list.html')

# Enable session cookie security for multi-user support
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
