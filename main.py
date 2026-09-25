"""FastAPI entrypoint: upload Excel, store rows in SQLite, return summary."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from analysis import summarize_sales, validate_sales_dataframe
from database import init_db, load_sales_dataframe, replace_sales_dataset
from excel_loader import load_excel_dataframe
from file_manager import (
    delete_uploaded_file,
    publish_upload,
    sanitize_filename,
    save_temporary_upload,
)
from schemas import SummaryResponse, UploadResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create SQLite schema once when the process starts."""
    init_db()
    logger.info("Application startup complete. Database initialized.")
    yield


app: FastAPI = FastAPI(
    title="Financial Report Generator",
    description="Upload Excel sales data and read a JSON summary report.",
    version="1.0.0",
    lifespan=lifespan,
)

templates: Jinja2Templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request) -> HTMLResponse:
    """Serve the Excel upload form."""
    return templates.TemplateResponse(request, "index.html")


@app.post("/uploadfile/", response_model=UploadResponse)
def create_upload_file(file: UploadFile = File(...)) -> UploadResponse:
    """
    Accept an Excel upload and store raw rows in SQLite.

    Parse and validate before replacing data so a bad file never
    overwrites the previous dataset or its file on disk.
    """
    temp_path: str | None = None
    try:
        safe_name: str = sanitize_filename(file.filename)
        temp_path = save_temporary_upload(file)
        dataframe = load_excel_dataframe(temp_path)
        validate_sales_dataframe(dataframe)

        stored = replace_sales_dataset(safe_name, dataframe)
        publish_upload(temp_path, safe_name)
        temp_path = None
    except ValueError as exc:
        logger.warning("Upload rejected: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RuntimeError, OSError) as exc:
        logger.exception("Upload failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Upload could not be stored. Check the server log.",
        ) from exc
    finally:
        if temp_path is not None:
            delete_uploaded_file(temp_path)

    return UploadResponse(
        filename=safe_name,
        file_id=stored.upload_id,
        rows_stored=stored.rows_stored,
        status="File uploaded and raw data stored via raw SQL",
    )


@app.get("/summary", response_model=SummaryResponse)
def read_summary() -> SummaryResponse:
    """Return the pandas summary of the single stored sales file."""
    try:
        summary = summarize_sales(load_sales_dataframe())
    except ValueError as exc:
        logger.warning("Summary request failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Summary request failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Summary could not be loaded. Check the server log.",
        ) from exc
    return SummaryResponse(**summary)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
