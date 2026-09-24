"""Disk storage for uploaded Excel files."""

import os
import shutil

from fastapi import UploadFile

UPLOAD_DIR: str = "uploads"


def setup_upload_dir() -> str:
    """Create the upload directory if missing, then return its path."""
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    return UPLOAD_DIR


def save_uploaded_file(upload_file: UploadFile) -> str:
    """
    Save an UploadFile to UPLOAD_DIR.

    Raises:
        ValueError: If the upload has no filename.
        OSError: If the file cannot be written to disk.
    """
    if not upload_file.filename:
        raise ValueError("Uploaded file must have a filename.")

    setup_upload_dir()
    file_path: str = os.path.join(UPLOAD_DIR, upload_file.filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
    except OSError as exc:
        raise OSError(f"Failed to save upload to {file_path}: {exc}") from exc

    return file_path
