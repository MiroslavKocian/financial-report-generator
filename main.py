from contextlib import asynccontextmanager  # Import context manager for lifespan events
import shutil  # Import shutil to help with high-level file operations like copying
import os  # Import os to handle file paths
from fastapi import FastAPI, Request, UploadFile, File  # Import FastAPI components
from fastapi.responses import HTMLResponse  # Import HTMLResponse to serve web pages
from fastapi.templating import Jinja2Templates  # Import Jinja2 for HTML templates
from file_manager import (
    setup_upload_dir,  # Helper function to get upload folder
)
import pandas as pd  # Import pandas to read Excel files
from database import init_db, save_upload_metadata  # Import database functions

# Define lifespan context manager (replaces the deprecated startup event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the database
    init_db()
    print("--- Application startup complete. Database initialized. ---")
    yield
    # Shutdown logic (if needed) goes here

# Create the main FastAPI application instance with the lifespan handler
app = FastAPI(lifespan=lifespan)

# Set up templates directory with absolute path to avoid "TemplateNotFound" errors
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)

# Define the route for the home page (GET request to root "/")
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Render the index.html template and return it to the browser
    return templates.TemplateResponse(request, "index.html")


# Define the route to handle file uploads (POST request to "/uploadfile/")
@app.post("/uploadfile/")
async def create_upload_file(file: UploadFile = File(...)):
    """
    Handles file upload from the browser, saves file to disk, 
    records metadata, reads Excel rows via pandas, and stores 
    raw data into SQLite using manual raw SQL.
    """
    upload_dir = setup_upload_dir()
    file_location = os.path.join(upload_dir, file.filename)
    
    # Save the physical file to disk
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Save upload metadata to 'uploads' table via raw SQL
    file_id = save_upload_metadata(file.filename)
    
    # Read the uploaded Excel file using pandas
    df = pd.read_excel(file_location)
    
    # Normalize column names for safe SQL usage (lowercase, replace spaces)
    df.columns = [
        str(col).strip().lower().replace(" ", "_") 
        for col in df.columns
    ]
    
    # Dynamically create a table for this upload using raw SQL
    conn = get_db_connection()
    with conn:
        col_defs = ", ".join([f"{col} TEXT" for col in df.columns])
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS dynamic_sales_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_id INTEGER,
                {col_defs},
                FOREIGN KEY (upload_id) REFERENCES uploads (id)
            )
        """)
    conn.close()
    
    # Insert each row from the Excel file into SQLite using insert_generic_row
    inserted_rows_count = 0
    for _, row in df.iterrows():
        # Convert pandas row to dictionary and add upload_id foreign key
        row_dict = row.to_dict()
        row_dict["upload_id"] = file_id
        
        # Insert using our raw SQL generic inserter
        insert_generic_row("dynamic_sales_data", row_dict)
        inserted_rows_count += 1

    # Return success response to the browser
    return {
        "filename": file.filename, 
        "file_id": file_id, 
        "rows_stored": inserted_rows_count,
        "status": "File uploaded and raw data stored successfully via raw SQL"
    }

if __name__ == "__main__":
    import uvicorn
    # Run the server directly when this script is executed
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)