"""Tests for file_manager disk helpers."""

import os
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import mock_open, patch

import pytest

from file_manager import (
    UPLOAD_DIR,
    clear_upload_dir,
    delete_uploaded_file,
    publish_upload,
    sanitize_filename,
    save_temporary_upload,
    setup_upload_dir,
)


def test_create_upload_dir(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    fresh_dir = tmp_path / "new_uploads"
    monkeypatch.setattr("file_manager.UPLOAD_DIR", str(fresh_dir))
    assert not fresh_dir.exists()

    result: str = setup_upload_dir()

    assert result == str(fresh_dir)
    assert fresh_dir.is_dir()


def test_sanitize_filename_strips_path_traversal() -> None:
    assert sanitize_filename("../../secret.xlsx") == "secret.xlsx"
    assert sanitize_filename(r"..\..\secret.xlsx") == "secret.xlsx"


def test_sanitize_filename_rejects_empty() -> None:
    with pytest.raises(ValueError, match="filename"):
        sanitize_filename("")
    with pytest.raises(ValueError, match="filename"):
        sanitize_filename(None)


def test_save_temporary_upload_writes_bytes() -> None:
    file_content: bytes = b"sample excel content"
    fake_file: SimpleNamespace = SimpleNamespace(
        filename="sample.xlsx",
        file=BytesIO(file_content),
    )

    temp_path: str = save_temporary_upload(fake_file)

    assert os.path.exists(temp_path)
    assert temp_path.endswith(".part")
    with open(temp_path, "rb") as handle:
        assert handle.read() == file_content


def test_publish_upload_moves_temp_file_and_clears_old_files() -> None:
    setup_upload_dir()
    temp_path = os.path.join(UPLOAD_DIR, "incoming.part")
    old_path = os.path.join(UPLOAD_DIR, "old.xlsx")
    with open(temp_path, "wb") as handle:
        handle.write(b"new")
    with open(old_path, "wb") as handle:
        handle.write(b"old")

    final_path = publish_upload(temp_path, "sales.xlsx")

    assert os.path.basename(final_path) == "sales.xlsx"
    assert not os.path.exists(temp_path)
    assert not os.path.exists(old_path)
    with open(final_path, "rb") as handle:
        assert handle.read() == b"new"


def test_save_temporary_upload_wraps_oserror() -> None:
    fake_file: SimpleNamespace = SimpleNamespace(
        filename="broken.xlsx",
        file=BytesIO(b"data"),
    )

    with patch("os.fdopen", side_effect=OSError("disk full")):
        with pytest.raises(OSError, match="Failed to save upload"):
            save_temporary_upload(fake_file)


def test_sanitize_filename_rejects_dot_segments() -> None:
    with pytest.raises(ValueError, match="filename"):
        sanitize_filename("..")
    with pytest.raises(ValueError, match="filename"):
        sanitize_filename(".")


def test_delete_uploaded_file_swallows_oserror() -> None:
    with patch("os.path.exists", return_value=True):
        with patch("os.remove", side_effect=OSError("locked")):
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


def test_clear_upload_dir_noop_when_upload_dir_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    missing = tmp_path / "absent_uploads"
    monkeypatch.setattr("file_manager.UPLOAD_DIR", str(missing))
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


def test_publish_upload_wraps_replace_error() -> None:
    setup_upload_dir()
    temp_path = os.path.join(UPLOAD_DIR, "incoming.part")
    with open(temp_path, "wb") as handle:
        handle.write(b"new")
    with patch("os.replace", side_effect=OSError("locked")):
        with pytest.raises(OSError, match="Failed to publish upload"):
            publish_upload(temp_path, "sales.xlsx")


def test_clear_upload_dir_raises_on_remove_failure() -> None:
    setup_upload_dir()
    path: str = os.path.join(UPLOAD_DIR, "locked.xlsx")
    with open(path, "wb") as handle:
        handle.write(b"data")

    with patch("os.remove", side_effect=OSError("locked")):
        with pytest.raises(OSError, match="Failed to remove"):
            clear_upload_dir()
