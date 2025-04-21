import os
import uuid
import logging
import json
import requests
from flask import Blueprint, request, jsonify, session
from app import db
from models import SubtitleTask
from gofile_api import get_gofile_server
# Import the celery task after all other imports to avoid circular imports
from celery_worker import generate_subtitles
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Blueprint
api_bp = Blueprint('api', __name__)

@api_bp.route('/gofile/server', methods=['GET'])
def get_server():
    """Get the best Gofile server for uploads."""
    try:
        server = get_gofile_server()
        return jsonify({
            'status': 'success',
            'server': server
        })
    except Exception as e:
        logger.error(f"Error getting Gofile server: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/task', methods=['POST'])
def create_task():
    """Create a new subtitle generation task."""
    try:
        # Ensure we have a session_id
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        # Get task data from request
        data = request.json
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['gofile_id', 'gofile_link', 'filename', 'language', 'model', 'format']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        
        # Get output language (optional field)
        output_language = data.get('output_language', 'same')
        
        # Create a new task
        task = SubtitleTask(
            task_id=task_id,
            session_id=session['session_id'],
            status='pending',
            original_filename=data['filename'],
            input_gofile_id=data['gofile_id'],
            input_gofile_link=data['gofile_link'],
            language=data['language'],
            output_language=output_language,
            model=data['model'],
            format_type=data['format'],
            created_at=datetime.utcnow()
        )
        
        db.session.add(task)
        db.session.commit()
        
        # Store the task ID in the session
        session['last_task_id'] = task_id
        
        # Start the subtitle generation task
        generate_subtitles.delay(task_id)
        
        return jsonify({
            'status': 'success',
            'message': 'Task created successfully',
            'task_id': task_id
        })
        
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id):
    """Get the status of a specific task."""
    try:
        task = SubtitleTask.query.filter_by(task_id=task_id).first()
        
        if not task:
            return jsonify({
                'status': 'error',
                'message': 'Task not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'task': task.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error getting task: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/my-tasks', methods=['GET'])
def get_my_tasks():
    """Get all tasks for the current session."""
    try:
        if 'session_id' not in session:
            return jsonify({
                'status': 'success',
                'tasks': []
            })
        
        tasks = SubtitleTask.query.filter_by(session_id=session['session_id']).order_by(SubtitleTask.created_at.desc()).all()
        
        return jsonify({
            'status': 'success',
            'tasks': [task.to_dict() for task in tasks]
        })
        
    except Exception as e:
        logger.error(f"Error getting tasks: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
