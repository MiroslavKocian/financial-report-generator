"""Shared pytest fixtures for isolated database and upload paths."""

import pytest

from database import init_db


@pytest.fixture(autouse=True)
def isolated_storage(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Run each test in its own cwd with a fresh SQLite file and uploads/."""
    database_file = tmp_path / "sales_data.db"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("database.DB_NAME", str(database_file))
    monkeypatch.setattr("file_manager.UPLOAD_DIR", str(upload_dir))

    init_db()
    yield
