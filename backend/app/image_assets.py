"""Lưu ảnh đầu vào cùng metadata dùng cho kho ảnh và import từ nguồn ngoài."""
import hashlib
import time
import uuid
from pathlib import Path

from . import config, db
from .image_normalize import normalize_image


def _clean_label(value: str, fallback: str = "") -> str:
    # Path.name loại bỏ thư mục do browser/Drive gửi kèm; giới hạn để UI/DB gọn.
    return (Path(value or "").name.strip() or fallback)[:200]


def save_upload(data: bytes, original_name: str, *, collection: str = "",
                source: str = "upload", source_ref: str = "",
                source_url: str = "") -> tuple[dict, bool]:
    """Chuẩn hóa và lưu ảnh; trả (asset, created).

    Drive dùng source_ref=file id để import lại cùng folder không nhân bản file.
    """
    existing = db.get_image_asset_by_source(source, source_ref)
    if existing:
        path = config.UPLOADS_DIR / existing["file_id"]
        if path.is_file():
            return asset_to_api(existing, path), False

    normalized, out_ext = normalize_image(data)
    file_id = f"{uuid.uuid4().hex}.{out_ext}"
    path = config.UPLOADS_DIR / file_id
    path.write_bytes(normalized)

    display_name = _clean_label(original_name, f"image.{out_ext}")
    collection = _clean_label(collection)
    content_sha = hashlib.sha256(normalized).hexdigest()
    db.save_image_asset(
        file_id, display_name, collection, source, source_ref, source_url, content_sha)
    record = {
        "file_id": file_id,
        "display_name": display_name,
        "collection": collection,
        "source": source,
        "source_ref": source_ref,
        "source_url": source_url,
        "content_sha": content_sha,
        "created_at": "",
    }
    return asset_to_api(record, path), True


def find_source_asset(source: str, source_ref: str, collection: str = "") -> dict | None:
    record = db.get_image_asset_by_source(source, source_ref)
    if not record:
        return None
    path = config.UPLOADS_DIR / record["file_id"]
    if not path.is_file():
        db.delete_image_asset(record["file_id"])
        return None
    clean_collection = _clean_label(collection)
    if clean_collection and clean_collection != record.get("collection"):
        db.update_image_asset_collection(record["file_id"], clean_collection)
        record["collection"] = clean_collection
    return asset_to_api(record, path)


def asset_to_api(record: dict, path: Path) -> dict:
    st = path.stat()
    return {
        "name": path.name,
        "file_id": path.name,
        "display_name": record.get("display_name") or path.name,
        "collection": record.get("collection") or "",
        "source": record.get("source") or "upload",
        "source_url": record.get("source_url") or "",
        "url": f"/api/uploads/{path.name}",
        "size": st.st_size,
        "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
        "modified_ts": st.st_mtime,
    }


def list_uploads() -> list[dict]:
    records = {item["file_id"]: item for item in db.list_image_assets()}
    items = []
    if not config.UPLOADS_DIR.is_dir():
        return items
    for path in config.UPLOADS_DIR.iterdir():
        if not path.is_file() or path.suffix.lower().lstrip(".") not in {
                "png", "jpg", "jpeg", "webp", "gif", "bmp"}:
            continue
        record = records.get(path.name, {
            "display_name": path.name,
            "collection": "",
            "source": "legacy",
            "source_url": "",
        })
        items.append(asset_to_api(record, path))
    items.sort(key=lambda item: item["modified_ts"], reverse=True)
    for item in items:
        del item["modified_ts"]
    return items
