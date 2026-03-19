import shutil  # Import shutil to help with high-level file operations like copying
import os  # Import os to handle file paths
from fastapi import FastAPI, Request, UploadFile, File  # Import FastAPI components
from fastapi.responses import HTMLResponse  # Import HTMLResponse to serve web pages
from fastapi.templating import Jinja2Templates  # Import Jinja2 for HTML templates
from file_manager import setup_upload_dir  # Import our helper function to get the upload folder

# Create the main FastAPI application instance
app = FastAPI()

# Set up the templates directory for loading HTML files
templates = Jinja2Templates(directory="templates")


# Define the route for the home page (GET request to root "/")
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Render the index.html template and return it to the browser
    return templates.TemplateResponse("index.html", {"request": request})


# Define the route to handle file uploads (POST request to "/uploadfile/")
@app.post("/uploadfile/")
async def create_upload_file(file: UploadFile = File(...)):
    # Ensure the upload directory exists and get its path
    upload_dir = setup_upload_dir()
    # Create the full file path by joining the folder path and the filename
    file_location = os.path.join(upload_dir, file.filename)
    
    # Open the specific file path in write-binary mode
    with open(file_location, "wb") as buffer:
        # Efficiently copy the uploaded file stream to the local file on disk
        shutil.copyfileobj(file.file, buffer)
        
    # Return a JSON confirmation to the client with the filename and status
    return {"filename": file.filename, "status": "File uploaded successfully"}