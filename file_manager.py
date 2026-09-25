"""Disk storage for uploaded Excel files with filename sanitization."""

import os
import shutil

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

    os.path.basename strips directory components on Windows and Unix,
    which blocks classic path-traversal uploads.
    """
    if not filename or not filename.strip():
        raise ValueError("Uploaded file must have a filename.")

    # Normalize separators, then keep the last segment only.
    normalized: str = filename.strip().replace("\\", "/")
    safe_name: str = os.path.basename(normalized)

    if not safe_name or safe_name in {".", ".."}:
        raise ValueError("Uploaded file must have a filename.")

    return safe_name


def save_uploaded_file(upload_file: UploadFile) -> str:
    """
    Save an UploadFile into UPLOAD_DIR under a sanitized filename.

    Raises:
        ValueError: Missing/unsafe filename.
        OSError: Disk write failure.

    An existing file with the same sanitized name is replaced.
    """
    safe_name: str = sanitize_filename(upload_file.filename)
    setup_upload_dir()
    file_path: str = os.path.join(UPLOAD_DIR, safe_name)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
    except OSError as exc:
        raise OSError(f"Failed to save upload to {file_path}: {exc}") from exc

    return file_path


def delete_uploaded_file(file_path: str) -> None:
    """Best-effort cleanup when a subsequent pipeline step fails."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        # Cleanup must not hide the original failure reason.
        pass


def clear_upload_dir(*, keep_path: str | None = None) -> None:
    """
    Remove every file in UPLOAD_DIR except an optional keep_path.

    Used when a new valid Excel replaces the previous dataset so only
    one file remains on disk.
    """
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
