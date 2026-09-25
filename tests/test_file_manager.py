"""Tests for file_manager disk helpers."""

import os
import shutil
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import mock_open, patch

import pytest

from file_manager import (
    UPLOAD_DIR,
    clear_upload_dir,
    delete_uploaded_file,
    sanitize_filename,
    save_uploaded_file,
    setup_upload_dir,
)


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


def test_sanitize_filename_strips_path_traversal() -> None:
    assert sanitize_filename("../../secret.xlsx") == "secret.xlsx"
    assert sanitize_filename(r"..\..\secret.xlsx") == "secret.xlsx"


def test_sanitize_filename_rejects_empty() -> None:
    with pytest.raises(ValueError, match="filename"):
        sanitize_filename("")
    with pytest.raises(ValueError, match="filename"):
        sanitize_filename(None)


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


def test_save_uploaded_file_overwrites_same_name() -> None:
    first: SimpleNamespace = SimpleNamespace(
        filename="dup.xlsx",
        file=BytesIO(b"one"),
    )
    second: SimpleNamespace = SimpleNamespace(
        filename="dup.xlsx",
        file=BytesIO(b"two"),
    )
    path: str = save_uploaded_file(first)
    save_uploaded_file(second)

    with open(path, "rb") as handle:
        assert handle.read() == b"two"


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


def test_sanitize_filename_rejects_dot_segments() -> None:
    with pytest.raises(ValueError, match="filename"):
        sanitize_filename("..")
    with pytest.raises(ValueError, match="filename"):
        sanitize_filename(".")


def test_delete_uploaded_file_swallows_oserror() -> None:
    with patch("os.path.exists", return_value=True):
        with patch("os.remove", side_effect=OSError("locked")):
            # Must not raise — cleanup is best-effort.
            delete_uploaded_file("uploads/locked.xlsx")


def test_clear_upload_dir_keeps_specified_file() -> None:
    setup_upload_dir()
    old_path: str = os.path.join(UPLOAD_DIR, "old.xlsx")
    keep_path: str = os.path.join(UPLOAD_DIR, "new.xlsx")
    with open(old_path, "wb") as handle:
        handle.write(b"old")
    with open(keep_path, "wb") as handle:
        handle.write(b"new")

    clear_upload_dir(keep_path=keep_path)

    assert not os.path.exists(old_path)
    assert os.path.exists(keep_path)


def test_clear_upload_dir_noop_when_missing() -> None:
    # No uploads/ directory yet — must not raise.
    clear_upload_dir()


def test_clear_upload_dir_removes_all_when_keep_omitted() -> None:
    setup_upload_dir()
    path: str = os.path.join(UPLOAD_DIR, "only.xlsx")
    with open(path, "wb") as handle:
        handle.write(b"data")

    clear_upload_dir()

    assert not os.path.exists(path)


def test_clear_upload_dir_skips_directories() -> None:
    setup_upload_dir()
    subdir: str = os.path.join(UPLOAD_DIR, "subdir")
    os.makedirs(subdir)
    file_path: str = os.path.join(UPLOAD_DIR, "keep.xlsx")
    with open(file_path, "wb") as handle:
        handle.write(b"data")

    clear_upload_dir(keep_path=file_path)

    assert os.path.isdir(subdir)
    assert os.path.exists(file_path)


def test_clear_upload_dir_raises_on_remove_failure() -> None:
    setup_upload_dir()
    path: str = os.path.join(UPLOAD_DIR, "locked.xlsx")
    with open(path, "wb") as handle:
        handle.write(b"data")

    with patch("os.remove", side_effect=OSError("locked")):
        with pytest.raises(OSError, match="Failed to remove"):
            clear_upload_dir()
