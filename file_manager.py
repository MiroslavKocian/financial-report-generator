import os  # Import the operating system module to interact with the file system
import shutil  # Import shutil to handle file copying operations
from fastapi import UploadFile  # Import UploadFile for type hinting

# Define the constant name for our upload directory
UPLOAD_DIR = "uploads"

def setup_upload_dir() -> str:
    """Ensures the upload directory exists."""
    # Check if the directory path specifically does NOT exist yet
    if not os.path.exists(UPLOAD_DIR):
        # Create the directory using the makedirs function
        os.makedirs(UPLOAD_DIR)
    # Return the directory name so the caller knows where files go
    return UPLOAD_DIR

def save_uploaded_file(upload_file: UploadFile) -> str:
    """Saves an incoming FastAPI UploadFile to the uploads directory."""
    # Ensure the destination directory exists
    setup_upload_dir()
    
    # Construct the full destination file path
    file_path = os.path.join(UPLOAD_DIR, upload_file.filename)
    
    # Write the binary stream directly to disk
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
        
    # Return the target path
    return file_path