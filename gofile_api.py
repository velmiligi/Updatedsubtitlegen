import os
import logging
import requests
import json
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Gofile API URLs and credentials
GOFILE_API_URL = 'https://api.gofile.io'
GOFILE_API_TOKEN = os.environ.get('GOFILE_API_TOKEN')

def get_gofile_server():
    """Get the best Gofile server for uploads."""
    max_retries = 3
    retry_count = 0
    
    # Add token to headers if available
    headers = {}
    if GOFILE_API_TOKEN:
        headers['Authorization'] = f'Bearer {GOFILE_API_TOKEN}'
        logger.info("Using Gofile API token for authentication")
    
    while retry_count < max_retries:
        try:
            response = requests.get(f"{GOFILE_API_URL}/getServer", headers=headers)
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

def add_to_account(file_id):
    """Add a file to user's Gofile account using the API token."""
    if not GOFILE_API_TOKEN:
        logger.warning("No Gofile API token provided, skipping add_to_account")
        return False
        
    try:
        headers = {'Authorization': f'Bearer {GOFILE_API_TOKEN}'}
        response = requests.put(
            f"{GOFILE_API_URL}/contents/{file_id}",
            headers=headers,
            json={"accountToken": GOFILE_API_TOKEN}
        )
        response.raise_for_status()
        
        data = response.json()
        if data.get('status') == 'ok':
            logger.info(f"Added file {file_id} to Gofile account")
            return True
        else:
            logger.warning(f"Failed to add file to account: {data.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.warning(f"Error adding file to account: {str(e)}")
        return False

def download_from_gofile(file_id, output_path):
    """Download a file from Gofile using the file ID."""
    if not file_id:
        raise ValueError("No file ID provided")
        
    max_retries = 3
    retry_count = 0
    
    # Prepare headers with API token if available
    headers = {}
    if GOFILE_API_TOKEN:
        headers['Authorization'] = f'Bearer {GOFILE_API_TOKEN}'
    
    while retry_count < max_retries:
        try:
            # Get file info
            response = requests.get(
                f"{GOFILE_API_URL}/contents/{file_id}",
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            if data['status'] != 'ok':
                raise ValueError(f"Gofile API error: {data.get('message', 'Unknown error')}")
                
            download_url = data['data']['contents']['file']['directLink']
            
            # Download the file
            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
            logger.info(f"File downloaded successfully to {output_path}")
            return True
            
        except Exception as e:
            retry_count += 1
            wait_time = retry_count * 2
            logger.warning(f"Error downloading from Gofile (attempt {retry_count}/{max_retries}): {str(e)}")
            
            if retry_count < max_retries:
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"Failed to download file from Gofile after {max_retries} attempts: {str(e)}")
    
    return False

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
    
    # Prepare headers with API token if available
    headers = {}
    if GOFILE_API_TOKEN:
        headers['Authorization'] = f'Bearer {GOFILE_API_TOKEN}'
    
    while retry_count < max_retries:
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f)}
                data = {}
                
                # Add token to form data as well (Gofile supports both methods)
                if GOFILE_API_TOKEN:
                    data['token'] = GOFILE_API_TOKEN
                
                response = requests.post(
                    f"https://{server}.gofile.io/uploadFile", 
                    files=files,
                    data=data,
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                if data['status'] == 'ok':
                    logger.info(f"File uploaded successfully to Gofile: {filename}")
                    result = {
                        'fileId': data['data']['fileId'],
                        'fileName': data['data']['fileName'],
                        'downloadPage': data['data']['downloadPage']
                    }
                    
                    # If we have a token, add the file to account
                    if GOFILE_API_TOKEN and 'fileId' in data['data']:
                        try:
                            add_to_account(data['data']['fileId'])
                        except Exception as e:
                            logger.warning(f"Failed to add file to account: {e}")
                    
                    return result
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
