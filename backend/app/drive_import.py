"""Nhập ảnh từ file/folder Google Drive public vào kho ảnh nội bộ."""
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import gdown

from .image_assets import find_source_asset, save_upload
from .image_normalize import MAX_UPLOAD_BYTES

MAX_DRIVE_FILES = 50
ALLOWED_HOSTS = {"drive.google.com", "docs.google.com"}


def _parse_drive_url(url: str) -> tuple[str, str]:
    parsed = urlparse((url or "").strip())
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("Chỉ chấp nhận link https://drive.google.com công khai.")
    parts = [part for part in parsed.path.split("/") if part]
    if "folders" in parts:
        index = parts.index("folders")
        if index + 1 < len(parts):
            return "folder", parts[index + 1]
    if "d" in parts:
        index = parts.index("d")
        if index + 1 < len(parts):
            return "file", parts[index + 1]
    file_id = parse_qs(parsed.query).get("id", [""])[0]
    if file_id:
        return "file", file_id
    raise ValueError("Không nhận ra ID file/folder trong link Google Drive.")


def _download_file(file_id: str, output: Path) -> None:
    result = gdown.download(
        id=file_id, output=str(output), quiet=True, use_cookies=False)
    if not result or not output.is_file():
        raise ValueError("Google Drive từ chối tải file. Kiểm tra quyền 'Bất kỳ ai có link'.")
    if output.stat().st_size > MAX_UPLOAD_BYTES:
        raise ValueError(f"File vượt quá {MAX_UPLOAD_BYTES // (1024 * 1024)}MB.")


def import_public_drive(url: str, collection: str = "") -> dict:
    kind, drive_id = _parse_drive_url(url)
    candidates: list[tuple[str, str]]
    if kind == "folder":
        try:
            found = gdown.download_folder(
                id=drive_id,
                quiet=True,
                use_cookies=False,
                remaining_ok=True,
                skip_download=True,
            )
        except Exception as exc:
            raise ValueError(
                "Không đọc được folder Drive. Hãy bật quyền 'Bất kỳ ai có link'.") from exc
        if not found:
            raise ValueError(
                "Folder Drive không tồn tại, chưa public hoặc link đã sai.")
        if len(found) > MAX_DRIVE_FILES:
            raise ValueError(
                f"Folder có {len(found)} file; giới hạn mỗi lần nhập là {MAX_DRIVE_FILES}.")
        candidates = [(item.id, Path(item.path).name) for item in found]
    else:
        candidates = [(drive_id, f"drive-{drive_id}")]

    items = []
    errors = []
    imported = 0
    skipped = 0
    with tempfile.TemporaryDirectory(prefix="image-workflow-drive-") as temp:
        temp_dir = Path(temp)
        for index, (file_id, display_name) in enumerate(candidates):
            target = temp_dir / f"{index:03d}.download"
            existing = find_source_asset("google-drive", file_id, collection)
            if existing:
                items.append(existing)
                skipped += 1
                continue

            try:
                _download_file(file_id, target)
                asset, created = save_upload(
                    target.read_bytes(), display_name,
                    collection=collection,
                    source="google-drive",
                    source_ref=file_id,
                    source_url=url,
                )
                items.append(asset)
                imported += int(created)
                skipped += int(not created)
            except (OSError, ValueError) as exc:
                errors.append({"name": display_name, "error": str(exc)})

    if not items:
        detail = errors[0]["error"] if errors else "Không tìm thấy ảnh hợp lệ."
        raise ValueError(f"Không nhập được ảnh nào. {detail}")
    return {
        "kind": kind,
        "folder_id": drive_id if kind == "folder" else "",
        "items": items,
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
    }
