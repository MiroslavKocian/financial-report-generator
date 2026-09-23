from io import BytesIO
import os
import shutil
from types import SimpleNamespace

import pytest

from file_manager import UPLOAD_DIR, save_uploaded_file, setup_upload_dir


@pytest.fixture(autouse=True)
def clean_upload_dir():
    """Fixture to reset the upload directory before and after each test."""
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
    yield
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)


def test_create_upload_dir() -> None:
    assert not os.path.exists(UPLOAD_DIR)

    result: str = setup_upload_dir()

    assert result == UPLOAD_DIR
    assert os.path.exists(UPLOAD_DIR)


def test_save_uploaded_file() -> None:
    file_content: bytes = b"sample excel content"
    fake_file: SimpleNamespace = SimpleNamespace(
        filename="sample.xlsx", file=BytesIO(file_content)
    )

    saved_path: str = save_uploaded_file(fake_file)

    assert os.path.exists(saved_path)
    assert saved_path == os.path.join(UPLOAD_DIR, "sample.xlsx")
