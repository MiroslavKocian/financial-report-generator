"""FastAPI entrypoint: routes wire file, Excel, and SQLite modules."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import init_db, save_upload_metadata, store_dataframe_rows
from excel_loader import load_excel_dataframe
from file_manager import save_uploaded_file


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize SQLite on startup."""
    init_db()
    print("--- Application startup complete. Database initialized. ---")
    yield


app: FastAPI = FastAPI(lifespan=lifespan)

templates: Jinja2Templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request) -> HTMLResponse:
    """Serve the Excel upload form."""
    return templates.TemplateResponse(request, "index.html")


@app.post("/uploadfile/")
def create_upload_file(file: UploadFile = File(...)) -> dict:  # noqa: B008
    """
    Accept an Excel upload, store the file and raw rows in SQLite.

    Does not run analysis yet — that is a later step.
    """
    try:
        file_location: str = save_uploaded_file(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename: str = file.filename or os.path.basename(file_location)

    try:
        file_id: int = save_upload_metadata(filename)
        dataframe = load_excel_dataframe(file_location)
        rows_stored: int = store_dataframe_rows(file_id, dataframe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RuntimeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "filename": filename,
        "file_id": file_id,
        "rows_stored": rows_stored,
        "status": "File uploaded and raw data stored via raw SQL",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
