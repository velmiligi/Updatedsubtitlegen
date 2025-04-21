import os
import uuid
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from werkzeug.utils import secure_filename
from app import db
from models import SubtitleTask

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Blueprint
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Render the index page with file upload form."""
    # Generate a session ID if one doesn't exist
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    return render_template('index.html')

@main_bp.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and redirect to processing."""
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('main.index'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('main.index'))
    
    # Get parameters from form
    language = request.form.get('language', 'auto')
    model = request.form.get('model', 'base')
    format_type = request.form.get('format', 'srt')
    
    # Send the task to the API endpoint which will handle Gofile upload
    # This is a redirect to keep the flow in the browser
    return redirect(url_for('main.processing_redirect', 
                           language=language, 
                           model=model, 
                           format=format_type))

@main_bp.route('/processing-redirect')
def processing_redirect():
    """Renders a page that will use JavaScript to properly process the file upload."""
    language = request.args.get('language', 'auto')
    model = request.args.get('model', 'base')
    format_type = request.args.get('format', 'srt')
    
    return render_template('processing_redirect.html', 
                          language=language,
                          model=model,
                          format=format_type)

@main_bp.route('/task/<task_id>')
def task_status(task_id):
    """Show the status of a specific task."""
    # Check if task exists
    task = SubtitleTask.query.filter_by(task_id=task_id).first()
    
    if not task:
        flash('Task not found', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('task_status.html', task_id=task_id)

@main_bp.route('/tasks')
def tasks_list():
    """Show a list of tasks for the current session."""
    # Ensure we have a session_id
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    return render_template('tasks_list.html')

@main_bp.route('/result')
def result():
    """Show the result of the most recent completed task."""
    if 'last_task_id' not in session:
        flash('No completed task found', 'warning')
        return redirect(url_for('main.index'))
    
    task_id = session['last_task_id']
    task = SubtitleTask.query.filter_by(task_id=task_id).first()
    
    if not task or task.status != 'completed':
        flash('Task not found or not completed', 'warning')
        return redirect(url_for('main.index'))
    
    # Get a preview of the subtitle content
    # This is a placeholder; in a real app, you'd retrieve the actual content
    preview_content = "1\n00:00:00,000 --> 00:00:05,000\nThis is a preview of the generated subtitles.\n\n2\n00:00:05,500 --> 00:00:10,000\nThe full content is available for download."
    
    return render_template('results.html', task=task, preview_content=preview_content)

@main_bp.route('/download')
def download_result():
    """Download the latest subtitle file."""
    if 'last_task_id' not in session:
        flash('No completed task found', 'warning')
        return redirect(url_for('main.index'))
    
    task_id = session['last_task_id']
    task = SubtitleTask.query.filter_by(task_id=task_id).first()
    
    if not task or task.status != 'completed' or not task.subtitle_gofile_link:
        flash('Subtitle file not available', 'warning')
        return redirect(url_for('main.index'))
    
    # Redirect to the Gofile download link
    return redirect(task.subtitle_gofile_link)
