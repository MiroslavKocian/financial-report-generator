import io
import os
import shutil

from fastapi.testclient import TestClient
import pandas as pd
import pytest

from database import DB_NAME, init_db
from file_manager import UPLOAD_DIR
from main import app

client: TestClient = TestClient(app)


@pytest.fixture(autouse=True)
def clean_environment():
    """Fixture to clean database and upload folder for each test."""
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    init_db()
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
    yield
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)


def test_read_root_endpoint() -> None:
    """Test standard GET / route to cover HTML template response."""
    response = client.get("/")
    assert response.status_code == 200


def test_upload_file_endpoint() -> None:
    df_test: pd.DataFrame = pd.DataFrame(
        {"Region": ["North", "South"], "Amount": [100.50, 250.75]}
    )
    excel_buffer: io.BytesIO = io.BytesIO()
    df_test.to_excel(excel_buffer, index=False, engine="openpyxl")
    excel_bytes: bytes = excel_buffer.getvalue()

    filename: str = "test_report.xlsx"

    response = client.post(
        "/uploadfile/",
        files={
            "file": (
                filename,
                excel_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200

    json_response: dict = response.json()
    assert json_response["filename"] == filename
    assert json_response["status"] == "File uploaded and raw data stored via raw SQL"
    assert isinstance(json_response["file_id"], int)
    assert json_response["rows_stored"] == 2
    assert os.path.exists(os.path.join(UPLOAD_DIR, filename))


def test_upload_invalid_file_format() -> None:
    """Test uploading a non-Excel file to cover the Exception block."""
    bad_bytes: bytes = b"This is just a plain text file, not Excel!"
    response = client.post(
        "/uploadfile/",
        files={"file": ("invalid.txt", bad_bytes, "text/plain")},
    )
    assert response.status_code == 400
    assert "Invalid Excel file format" in response.json()["detail"]
