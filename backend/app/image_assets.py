"""Lưu ảnh đầu vào cùng metadata dùng cho kho ảnh và import từ nguồn ngoài."""
import hashlib
import time
import uuid
from datetime import datetime
from pathlib import Path

from . import config, db, supabase_api
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
        if supabase_api.enabled():
            return asset_to_api(existing), False
        path = config.UPLOADS_DIR / existing["file_id"]
        if path.is_file():
            return asset_to_api(existing, path), False

    normalized, out_ext = normalize_image(data)
    file_id = f"{uuid.uuid4().hex}.{out_ext}"
    path = None
    if supabase_api.enabled():
        content_type = "image/png" if out_ext == "png" else "image/jpeg"
        supabase_api.upload_object(
            f"uploads/{file_id}", normalized, content_type)
    else:
        path = config.UPLOADS_DIR / file_id
        path.write_bytes(normalized)

    display_name = _clean_label(original_name, f"image.{out_ext}")
    collection = _clean_label(collection)
    content_sha = hashlib.sha256(normalized).hexdigest()
    try:
        db.save_image_asset(
            file_id, display_name, collection, source, source_ref, source_url,
            content_sha, len(normalized))
    except Exception:
        if supabase_api.enabled():
            supabase_api.delete_object(f"uploads/{file_id}")
        elif path:
            path.unlink(missing_ok=True)
        raise
    record = {
        "file_id": file_id,
        "display_name": display_name,
        "collection": collection,
        "source": source,
        "source_ref": source_ref,
        "source_url": source_url,
        "content_sha": content_sha,
        "size_bytes": len(normalized),
        "created_at": "",
    }
    return asset_to_api(record, path), True


def find_source_asset(source: str, source_ref: str, collection: str = "") -> dict | None:
    record = db.get_image_asset_by_source(source, source_ref)
    if not record:
        return None
    if supabase_api.enabled():
        clean_collection = _clean_label(collection)
        if clean_collection and clean_collection != record.get("collection"):
            db.update_image_asset_collection(record["file_id"], clean_collection)
            record["collection"] = clean_collection
        return asset_to_api(record)
    path = config.UPLOADS_DIR / record["file_id"]
    if not path.is_file():
        db.delete_image_asset(record["file_id"])
        return None
    clean_collection = _clean_label(collection)
    if clean_collection and clean_collection != record.get("collection"):
        db.update_image_asset_collection(record["file_id"], clean_collection)
        record["collection"] = clean_collection
    return asset_to_api(record, path)


def _display_modified(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M")
    except ValueError:
        return value[:16].replace("T", " ")


def asset_to_api(record: dict, path: Path | None = None) -> dict:
    file_id = path.name if path else record["file_id"]
    if path:
        stat = path.stat()
        size = stat.st_size
        modified = time.strftime(
            "%Y-%m-%d %H:%M", time.localtime(stat.st_mtime))
    else:
        size = int(record.get("size_bytes") or 0)
        modified = _display_modified(record.get("created_at") or "")
    return {
        "name": file_id,
        "file_id": file_id,
        "display_name": record.get("display_name") or file_id,
        "collection": record.get("collection") or "",
        "source": record.get("source") or "upload",
        "source_url": record.get("source_url") or "",
        "url": f"/api/uploads/{file_id}",
        "size": size,
        "modified": modified,
    }


def list_uploads() -> list[dict]:
    if supabase_api.enabled():
        return [asset_to_api(record) for record in db.list_image_assets()]
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
        item = asset_to_api(record, path)
        item["_mtime"] = path.stat().st_mtime
        items.append(item)
    items.sort(key=lambda item: item["_mtime"], reverse=True)
    for item in items:
        del item["_mtime"]
    return items


def get_upload_bytes(file_id: str) -> bytes | None:
    if not file_id or Path(file_id).name != file_id:
        return None
    if supabase_api.enabled():
        try:
            return supabase_api.download_object(f"uploads/{file_id}")
        except supabase_api.SupabaseError as exc:
            if exc.status_code == 404:
                return None
            raise
    path = (config.UPLOADS_DIR / file_id).resolve()
    if not path.is_relative_to(config.UPLOADS_DIR) or not path.is_file():
        return None
    return path.read_bytes()


def delete_upload(file_id: str) -> bool:
    if not file_id or Path(file_id).name != file_id:
        return False
    if supabase_api.enabled():
        try:
            supabase_api.delete_object(f"uploads/{file_id}")
        except supabase_api.SupabaseError as exc:
            if exc.status_code != 404:
                raise
        exists = any(
            item["file_id"] == file_id for item in db.list_image_assets())
        db.delete_image_asset(file_id)
        return exists
    path = (config.UPLOADS_DIR / file_id).resolve()
    if not path.is_relative_to(config.UPLOADS_DIR) or not path.is_file():
        return False
    path.unlink()
    db.delete_image_asset(file_id)
    return True
