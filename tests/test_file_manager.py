"""Tests for file_manager disk helpers."""

import os
import shutil
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import mock_open, patch

import pytest

from file_manager import UPLOAD_DIR, save_uploaded_file, setup_upload_dir


@pytest.fixture(autouse=True)
def clean_upload_dir():
    """Reset the upload directory before and after each test."""
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
        filename="sample.xlsx",
        file=BytesIO(file_content),
    )

    saved_path: str = save_uploaded_file(fake_file)

    assert os.path.exists(saved_path)
    assert saved_path == os.path.join(UPLOAD_DIR, "sample.xlsx")


def test_save_uploaded_file_requires_filename() -> None:
    fake_file: SimpleNamespace = SimpleNamespace(
        filename="",
        file=BytesIO(b"data"),
    )

    with pytest.raises(ValueError, match="filename"):
        save_uploaded_file(fake_file)


def test_save_uploaded_file_wraps_oserror() -> None:
    fake_file: SimpleNamespace = SimpleNamespace(
        filename="broken.xlsx",
        file=BytesIO(b"data"),
    )

    with patch(
        "builtins.open",
        mock_open(),
    ) as mocked_open:
        mocked_open.side_effect = OSError("disk full")
        with pytest.raises(OSError, match="Failed to save upload"):
            save_uploaded_file(fake_file)
