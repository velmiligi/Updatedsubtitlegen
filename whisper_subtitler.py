import os
import tempfile
import logging
import whisper
import subprocess
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Check if ffmpeg is available
def is_ffmpeg_available():
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("ffmpeg not found in PATH. Some functionality may be limited.")
        return False

# Global variable to track ffmpeg availability
FFMPEG_AVAILABLE = is_ffmpeg_available()

def extract_audio(video_path):
    """Extract audio from video file using ffmpeg."""
    if not FFMPEG_AVAILABLE:
        raise RuntimeError("ffmpeg is required for audio extraction but not found on the system.")
    
    # Create temporary file for audio
    audio_path = tempfile.mktemp(suffix='.wav')
    
    try:
        # Run ffmpeg to extract audio
        cmd = ['ffmpeg', '-i', video_path, '-q:a', '0', '-map', 'a', audio_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if result.returncode != 0:
            error_message = result.stderr.decode('utf-8', errors='replace')
            raise RuntimeError(f"Failed to extract audio: {error_message}")
        
        return audio_path
    except Exception as e:
        # Clean up temporary file if extraction fails
        if os.path.exists(audio_path):
            os.remove(audio_path)
        logger.error(f"Error extracting audio: {str(e)}")
        raise

def transcribe_audio(audio_path, language='auto', model_name='base'):
    """Transcribe audio using Whisper model."""
    try:
        # Load Whisper model
        logger.info(f"Loading Whisper model: {model_name}")
        model = whisper.load_model(model_name)
        
        # Transcribe
        logger.info("Starting transcription...")
        transcription_options = {}
        
        # Only set language if not auto
        if language != 'auto':
            transcription_options['language'] = language
        
        result = model.transcribe(audio_path, **transcription_options)
        
        return result
    except Exception as e:
        logger.error(f"Error in transcription: {str(e)}")
        raise

def format_subtitles(transcription, format_type='srt'):
    """Format transcription results to the specified subtitle format."""
    segments = transcription['segments']
    
    # Create temporary file for the subtitles
    subtitle_path = tempfile.mktemp(suffix=f'.{format_type}')
    
    try:
        with open(subtitle_path, 'w', encoding='utf-8') as f:
            if format_type == 'srt':
                for i, segment in enumerate(segments, 1):
                    # Format time (start and end in seconds to SRT format)
                    start_time = format_timestamp(segment['start'])
                    end_time = format_timestamp(segment['end'])
                    text = segment['text'].strip()
                    
                    # Write SRT entry
                    f.write(f"{i}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{text}\n\n")
            
            elif format_type == 'vtt':
                f.write("WEBVTT\n\n")
                for i, segment in enumerate(segments, 1):
                    start_time = format_timestamp(segment['start'], vtt=True)
                    end_time = format_timestamp(segment['end'], vtt=True)
                    text = segment['text'].strip()
                    
                    # Write VTT entry
                    f.write(f"{i}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{text}\n\n")
            
            elif format_type == 'txt':
                for segment in segments:
                    f.write(f"{segment['text'].strip()}\n")
        
        return subtitle_path
    except Exception as e:
        # Clean up temporary file if formatting fails
        if os.path.exists(subtitle_path):
            os.remove(subtitle_path)
        logger.error(f"Error formatting subtitles: {str(e)}")
        raise

def format_timestamp(seconds, vtt=False):
    """Convert seconds to timestamp format HH:MM:SS,mmm or HH:MM:SS.mmm for VTT."""
    hours = int(seconds / 3600)
    minutes = int((seconds % 3600) / 60)
    seconds = seconds % 60
    
    if vtt:
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace('.', '.')
    else:
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace('.', ',')

def process_file(file_path, language='auto', model='base', format_type='srt'):
    """Process a media file to generate subtitles."""
    logger.info(f"Processing file: {file_path}")
    logger.info(f"Parameters: language={language}, model={model}, format={format_type}")
    
    temp_files = []
    
    try:
        # Determine if we need to extract audio (for video files)
        file_ext = Path(file_path).suffix.lower()
        is_video = file_ext not in ['.mp3', '.wav', '.flac', '.ogg', '.m4a']
        
        audio_path = file_path
        if is_video and FFMPEG_AVAILABLE:
            logger.info("Extracting audio from video...")
            audio_path = extract_audio(file_path)
            temp_files.append(audio_path)
        
        # Transcribe the audio
        logger.info("Transcribing audio...")
        transcription = transcribe_audio(audio_path, language, model)
        
        # Format subtitles
        logger.info(f"Formatting subtitles as {format_type}...")
        subtitle_path = format_subtitles(transcription, format_type)
        
        return subtitle_path
    
    except Exception as e:
        # Clean up any temporary files
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        
        logger.error(f"Error in processing file: {str(e)}")
        raise
