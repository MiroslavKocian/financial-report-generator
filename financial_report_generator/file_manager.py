"""Disk storage for uploaded Excel files with filename sanitization."""

import os
import shutil
import tempfile

from fastapi import UploadFile

UPLOAD_DIR: str = "uploads"


def setup_upload_dir() -> str:
    """Create the upload directory if missing, then return its path."""
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    return UPLOAD_DIR


def sanitize_filename(filename: str | None) -> str:
    """
    Keep only the final path segment and reject empty/unsafe names.

    os.path.basename blocks classic path-traversal uploads.
    """
    if not filename or not filename.strip():
        raise ValueError("Uploaded file must have a filename.")

    normalized: str = filename.strip().replace("\\", "/")
    safe_name: str = os.path.basename(normalized)

    if not safe_name or safe_name in {".", ".."}:
        raise ValueError("Uploaded file must have a filename.")

    return safe_name


def save_temporary_upload(upload_file: UploadFile) -> str:
    """
    Write upload bytes to a temporary file inside UPLOAD_DIR.

    The final filename is applied only after the database update succeeds.
    """
    setup_upload_dir()
    file_descriptor: int
    temp_path: str
    file_descriptor, temp_path = tempfile.mkstemp(
        suffix=".part",
        dir=UPLOAD_DIR,
    )
    try:
        with os.fdopen(file_descriptor, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
    except OSError as exc:
        delete_uploaded_file(temp_path)
        raise OSError(f"Failed to save upload to {temp_path}: {exc}") from exc
    return temp_path


def publish_upload(temp_path: str, safe_name: str) -> str:
    """Move the temp file to its final name and remove older uploads."""
    final_path: str = os.path.join(UPLOAD_DIR, safe_name)
    try:
        os.replace(temp_path, final_path)
    except OSError as exc:
        raise OSError(f"Failed to publish upload to {final_path}: {exc}") from exc
    clear_upload_dir(keep_path=final_path)
    return final_path


def delete_uploaded_file(file_path: str) -> None:
    """Best-effort cleanup when a subsequent pipeline step fails."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass


def clear_upload_dir(*, keep_path: str | None = None) -> None:
    """Remove every file in UPLOAD_DIR except an optional keep_path."""
    if not os.path.exists(UPLOAD_DIR):
        return

    keep_abs: str | None = os.path.abspath(keep_path) if keep_path else None
    for name in os.listdir(UPLOAD_DIR):
        path: str = os.path.join(UPLOAD_DIR, name)
        if not os.path.isfile(path):
            continue
        if keep_abs is not None and os.path.abspath(path) == keep_abs:
            continue
        try:
            os.remove(path)
        except OSError as exc:
            raise OSError(f"Failed to remove previous upload {path}: {exc}") from exc
