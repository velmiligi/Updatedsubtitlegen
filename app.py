import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize SQLAlchemy
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    
    # Configure the app
    app.config.from_object('config.Config')
    app.secret_key = os.environ.get("SESSION_SECRET", "whisper-subtitler-secret-key")
    
    # Initialize extensions
    db.init_app(app)
    
    # Create database tables
    with app.app_context():
        from models import SubtitleTask  # Import here to avoid circular imports
        db.create_all()
    
    # Register blueprints - moved after db initialization to avoid circular imports
    from routes import main_bp
    from api_routes import api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app

# Create the application instance
app = create_app()
@app.route('/')
def home():
    return "Hello, world!"

# Code to ensure it listens on the right port
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
