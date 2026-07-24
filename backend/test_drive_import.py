"""Test import Google Drive public bằng mock mạng; không chạm Drive thật."""
import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image


def _png(color: str) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (16, 12), color).save(out, "PNG")
    return out.getvalue()


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    from app import config, db

    uploads = tmp_path / "uploads"
    workflows = tmp_path / "workflows"
    uploads.mkdir()
    workflows.mkdir()
    monkeypatch.setattr(config, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(config, "WORKFLOWS_DIR", workflows)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data.db")
    db.init_db()
    return uploads


def test_parse_drive_urls():
    from app.drive_import import _parse_drive_url

    assert _parse_drive_url(
        "https://drive.google.com/drive/folders/folder123") == ("folder", "folder123")
    assert _parse_drive_url(
        "https://drive.google.com/file/d/file123/view") == ("file", "file123")
    assert _parse_drive_url(
        "https://drive.google.com/uc?id=query123") == ("file", "query123")
    with pytest.raises(ValueError):
        _parse_drive_url("https://example.com/file/d/nope")


def test_import_folder_and_skip_existing(isolated_store, monkeypatch):
    from app import drive_import

    rows = [
        SimpleNamespace(id="drive-a", path="A.png"),
        SimpleNamespace(id="drive-b", path="B.png"),
    ]
    monkeypatch.setattr(
        drive_import.gdown, "download_folder",
        lambda **kwargs: rows)

    calls = []

    def fake_download(*, id, output, **kwargs):
        calls.append(id)
        Path(output).write_bytes(_png("red" if id == "drive-a" else "blue"))
        return output

    monkeypatch.setattr(drive_import.gdown, "download", fake_download)
    url = "https://drive.google.com/drive/folders/public-folder"

    first = drive_import.import_public_drive(url, "Sàn gỗ")
    assert first["imported"] == 2
    assert first["skipped"] == 0
    assert [item["display_name"] for item in first["items"]] == ["A.png", "B.png"]
    assert all(item["collection"] == "Sàn gỗ" for item in first["items"])

    second = drive_import.import_public_drive(url, "Sàn mới")
    assert second["imported"] == 0
    assert second["skipped"] == 2
    assert all(item["collection"] == "Sàn mới" for item in second["items"])
    assert calls == ["drive-a", "drive-b"]
    assert len(list(isolated_store.iterdir())) == 2
