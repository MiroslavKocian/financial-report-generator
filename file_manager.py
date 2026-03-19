import os  # Import the operating system module to interact with the file system

# Define the constant name for our upload directory
UPLOAD_DIR = "uploads"

def setup_upload_dir():
    """Ensures the upload directory exists."""
    # Check if the directory path specifically does NOT exist yet
    if not os.path.exists(UPLOAD_DIR):
        # Create the directory using the makedirs function
        os.makedirs(UPLOAD_DIR)
    # Return the directory name so the caller knows where files go
    return UPLOAD_DIR