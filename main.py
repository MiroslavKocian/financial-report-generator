from contextlib import asynccontextmanager  # Import context manager for lifespan events
import shutil  # Import shutil to help with high-level file operations like copying
import os  # Import os to handle file paths
from typing import Dict, Any, Optional  # Import type hints
from fastapi import FastAPI, Request, UploadFile, File  # Import FastAPI components
from fastapi.responses import HTMLResponse  # Import HTMLResponse to serve web pages
from fastapi.templating import Jinja2Templates  # Import Jinja2 for HTML templates
from file_manager import (
    setup_upload_dir,  # Helper function to get upload folder
)
import pandas as pd  # Import pandas to read Excel files
from database import (
    init_db, 
    save_upload_metadata, 
    insert_generic_row, 
    get_db_connection  # <--- Make sure this is included!
)

# Define lifespan context manager (replaces the deprecated startup event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the database
    init_db()
    print("--- Application startup complete. Database initialized. ---")
    yield
    # Shutdown logic (if needed) goes here

# Create the main FastAPI application instance with the lifespan handler
app: FastAPI = FastAPI(lifespan=lifespan)

# Set up templates directory with absolute path to avoid "TemplateNotFound" errors
templates: Jinja2Templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)

# Define the route for the home page (GET request to root "/")
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request) -> HTMLResponse:
    # Render the index.html template and return it to the browser
    return templates.TemplateResponse(request, "index.html")


# Define the route to handle file uploads (POST request to "/uploadfile/")
@app.post("/uploadfile/")
async def create_upload_file(file: UploadFile = File(...)) -> dict:
    """
    Handles file upload from the browser, saves file to disk, 
    records metadata, reads Excel rows via pandas, and stores 
    raw data into SQLite using manual raw SQL.
    """
    import pandas as pd
    from fastapi import HTTPException

    # Ensure the upload directory exists and get its path
    upload_dir: str = setup_upload_dir()
    file_location: str = os.path.join(upload_dir, file.filename)
    
    # Save physical file to disk
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Save metadata to uploads table via raw SQL
    file_id: int = save_upload_metadata(file.filename)
    
    # Attempt to read the uploaded Excel file using pandas
    try:
        df: pd.DataFrame = pd.read_excel(file_location, engine="openpyxl")
    except Exception as e:
        # Fail fast and raise HTTP 400 if file is not a valid Excel file
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid Excel file format: {str(e)}"
        )
    
    # Normalize column names for safe SQL usage
    df.columns = [
        str(col).strip().lower().replace(" ", "_") 
        for col in df.columns
    ]
    
    # Dynamically create a table for this upload using raw SQL
    conn = get_db_connection()
    with conn:
        col_defs: str = ", ".join([f"{col} TEXT" for col in df.columns])
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS dynamic_sales_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_id INTEGER,
                {col_defs},
                FOREIGN KEY (upload_id) REFERENCES uploads (id)
            )
        """)
    conn.close()
    
    # Insert each row from the Excel file into SQLite
    inserted_rows_count: int = 0
    for _, row in df.iterrows():
        row_dict: dict = row.to_dict()
        row_dict["upload_id"] = file_id
        
        # Insert using our raw SQL generic inserter
        insert_generic_row("dynamic_sales_data", row_dict)
        inserted_rows_count += 1

    return {
        "filename": file.filename, 
        "file_id": file_id, 
        "rows_stored": inserted_rows_count,
        "status": "File uploaded and raw data stored via raw SQL"
    }

if __name__ == "__main__":
    import uvicorn
    # Run the server directly when this script is executed
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)