import os
import logging
import requests
import json
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Gofile API URLs
GOFILE_API_URL = 'https://api.gofile.io'

def get_gofile_server():
    """Get the best Gofile server for uploads."""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = requests.get(f"{GOFILE_API_URL}/getServer")
            response.raise_for_status()
            
            data = response.json()
            if data['status'] == 'ok':
                return data['data']['server']
            else:
                error_msg = f"Gofile API error: {data.get('message', 'Unknown error')}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
        except (requests.RequestException, ValueError) as e:
            retry_count += 1
            wait_time = retry_count * 2  # Exponential backoff
            logger.warning(f"Error getting Gofile server (attempt {retry_count}/{max_retries}): {str(e)}")
            
            if retry_count < max_retries:
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"Failed to get Gofile server after {max_retries} attempts: {str(e)}")
    
    # This should not be reached due to the raise in the loop
    raise RuntimeError("Failed to get Gofile server")

def upload_to_gofile(file_path, filename=None):
    """Upload a file to Gofile and return the download link."""
    if not os.path.exists(file_path):
        raise ValueError(f"File not found: {file_path}")
    
    if not filename:
        filename = os.path.basename(file_path)
    
    # Get the best server
    server = get_gofile_server()
    logger.info(f"Using Gofile server: {server}")
    
    # Upload the file
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f)}
                response = requests.post(f"https://{server}.gofile.io/uploadFile", files=files)
                response.raise_for_status()
                
                data = response.json()
                if data['status'] == 'ok':
                    logger.info(f"File uploaded successfully to Gofile: {filename}")
                    return {
                        'fileId': data['data']['fileId'],
                        'fileName': data['data']['fileName'],
                        'downloadPage': data['data']['downloadPage']
                    }
                else:
                    error_msg = f"Gofile upload error: {data.get('message', 'Unknown error')}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                    
        except (requests.RequestException, ValueError) as e:
            retry_count += 1
            wait_time = retry_count * 2  # Exponential backoff
            logger.warning(f"Error uploading to Gofile (attempt {retry_count}/{max_retries}): {str(e)}")
            
            if retry_count < max_retries:
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"Failed to upload file to Gofile after {max_retries} attempts: {str(e)}")
    
    # This should not be reached due to the raise in the loop
    raise RuntimeError("Failed to upload file to Gofile")
