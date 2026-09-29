"""FastAPI entrypoint: upload Excel, store rows, serve reports."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from financial_report_generator.analysis import (
    grouped_sales,
    summarize_sales,
    validate_sales_dataframe,
)
from financial_report_generator.database import (
    init_db,
    load_sales_dataframe,
    replace_sales_dataset,
)
from financial_report_generator.excel_loader import load_excel_dataframe
from financial_report_generator.export import build_report_workbook
from financial_report_generator.file_manager import (
    delete_uploaded_file,
    publish_upload,
    sanitize_filename,
    save_temporary_upload,
)
from financial_report_generator.schemas import (
    GroupedReportResponse,
    SummaryResponse,
    UploadResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_SERVER_ERROR = "Report could not be built. Check the server log."


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create SQLite schema once when the process starts."""
    init_db()
    logger.info("Application startup complete. Database initialized.")
    yield


app: FastAPI = FastAPI(
    title="Financial Report Generator",
    description="Upload Excel sales data and read grouped financial reports.",
    version="1.0.0",
    lifespan=lifespan,
)

_templates_dir: str = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "templates",
)
templates: Jinja2Templates = Jinja2Templates(directory=_templates_dir)


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


def _report_http_error(exc: Exception) -> HTTPException:
    """Map report failures to HTTP 400 or 500."""
    if isinstance(exc, ValueError):
        logger.warning("Report request failed: %s", exc)
        return HTTPException(status_code=400, detail=str(exc))
    logger.exception("Report request failed: %s", exc)
    return HTTPException(status_code=500, detail=_SERVER_ERROR)


@app.get("/summary", response_model=SummaryResponse)
def read_summary() -> SummaryResponse:
    """Return Decimal totals for the stored sales file."""
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


@app.get("/report/grouped", response_model=GroupedReportResponse)
def read_grouped_report(group_by: str | None = None) -> GroupedReportResponse:
    """Return per-group totals. Default column is region, then product."""
    try:
        report = grouped_sales(load_sales_dataframe(), group_by or None)
    except (ValueError, RuntimeError) as exc:
        raise _report_http_error(exc) from exc
    return GroupedReportResponse(**report)


@app.get("/report/export.xlsx")
def download_report(group_by: str | None = None) -> Response:
    """Download summary and grouped totals as an Excel workbook."""
    try:
        frame = load_sales_dataframe()
        payload: bytes = build_report_workbook(
            summarize_sales(frame),
            grouped_sales(frame, group_by or None),
        )
    except (ValueError, RuntimeError) as exc:
        raise _report_http_error(exc) from exc
    return Response(
        content=payload,
        media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": 'attachment; filename="financial-report.xlsx"'},
    )
