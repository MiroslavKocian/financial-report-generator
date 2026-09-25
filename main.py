"""FastAPI entrypoint: routes wire file, Excel, SQLite, and summary.

Pipeline for steps 1-2 (upload + store raw data):
1) Persist the binary to disk under a sanitized name (same name
   overwrites the file on disk).
2) Parse Excel with pandas (openpyxl); on failure keep prior data.
3) Replace previous dataset (other files + DB), then store the new one.
If a later step fails, delete the saved file so uploads/ stays clean.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from analysis import summarize_sales
from database import (
    clear_stored_upload_data,
    get_db_connection,
    init_db,
    load_sales_dataframe,
    save_upload_metadata,
    store_dataframe_rows,
)
from excel_loader import load_excel_dataframe
from file_manager import (
    clear_upload_dir,
    delete_uploaded_file,
    save_uploaded_file,
)

logger = logging.getLogger(__name__)


def _delete_upload_metadata(upload_id: int) -> None:
    """Remove an uploads row if a later step fails after INSERT."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create SQLite schema once when the process starts."""
    init_db()
    print("--- Application startup complete. Database initialized. ---")
    yield


app: FastAPI = FastAPI(lifespan=lifespan)

# Absolute template path avoids TemplateNotFound when cwd differs.
templates: Jinja2Templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request) -> HTMLResponse:
    """Serve the Excel upload form (step 1 UI)."""
    return templates.TemplateResponse(request, "index.html")


@app.post("/uploadfile/")
def create_upload_file(file: UploadFile = File(...)) -> dict:  # noqa: B008
    """
    Accept an Excel upload and store raw rows in SQLite (steps 1-2).

    Only one dataset is active: a valid new file replaces prior disk
    files and DB rows, including when the filename is unchanged.
    """
    file_location: str | None = None
    file_id: int | None = None
    try:
        # Step A: write bytes to disk (sanitized name; may overwrite).
        file_location = save_uploaded_file(file)

        # Step B: parse before clearing so a bad file keeps prior data.
        dataframe = load_excel_dataframe(file_location)

        # Step C: one active dataset — drop previous files and DB rows.
        clear_upload_dir(keep_path=file_location)
        clear_stored_upload_data()

        # Step D: metadata first to obtain upload_id as a foreign key.
        filename: str = os.path.basename(file_location)
        file_id = save_upload_metadata(filename)
        rows_stored: int = store_dataframe_rows(file_id, dataframe)
    except ValueError as exc:
        if file_id is not None:
            _delete_upload_metadata(file_id)
        if file_location is not None:
            delete_uploaded_file(file_location)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RuntimeError, OSError) as exc:
        if file_id is not None:
            _delete_upload_metadata(file_id)
        if file_location is not None:
            delete_uploaded_file(file_location)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "filename": filename,
        "file_id": file_id,
        "rows_stored": rows_stored,
        "status": "File uploaded and raw data stored via raw SQL",
    }


@app.get("/summary")
def read_summary() -> dict:
    """Return the pandas summary of the single stored sales file."""
    try:
        return summarize_sales(load_sales_dataframe())
    except ValueError as exc:
        logger.error("Summary request failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("Summary request failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    # reload=True is for local learning/debug; disable in production.
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
