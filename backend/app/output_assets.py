"""Lưu và đọc ảnh thành phẩm ở Supabase Storage hoặc filesystem local."""
from datetime import datetime
from pathlib import Path

from . import config, db, supabase_api


_IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "gif", "bmp"}


def _safe_name(name: str) -> bool:
    return bool(name and Path(name).name == name)


def _content_type(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }.get(suffix, "image/png")


def save_output(name: str, data: bytes) -> str:
    if not _safe_name(name):
        raise ValueError("Tên file đầu ra không hợp lệ.")
    if supabase_api.enabled():
        supabase_api.upload_object(
            f"outputs/{name}", data, _content_type(name))
        try:
            db.save_output_asset(name, len(data))
        except Exception:
            supabase_api.delete_object(f"outputs/{name}")
            raise
    else:
        (config.OUTPUTS_DIR / name).write_bytes(data)
        db.save_output_asset(name, len(data))
    _trim_outputs()
    return f"/api/outputs/{name}"


def list_outputs() -> list[dict]:
    if supabase_api.enabled():
        return [
            {
                "name": row["name"],
                "url": f"/api/outputs/{row['name']}",
                "size": int(row.get("size_bytes") or 0),
                "modified": _display_modified(row.get("created_at") or ""),
            }
            for row in db.list_output_assets()
        ]
    items = []
    for path in config.OUTPUTS_DIR.iterdir():
        if (not path.is_file()
                or path.suffix.lower().lstrip(".") not in _IMAGE_EXTS):
            continue
        stat = path.stat()
        items.append({
            "name": path.name,
            "url": f"/api/outputs/{path.name}",
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                "%Y-%m-%d %H:%M"),
            "_mtime": stat.st_mtime,
        })
    items.sort(key=lambda item: item["_mtime"], reverse=True)
    for item in items:
        del item["_mtime"]
    return items


def _display_modified(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M")
    except ValueError:
        return value[:16].replace("T", " ")


def _trim_outputs() -> None:
    rows = db.list_output_assets()
    for row in rows[config.OUTPUT_RETENTION:]:
        name = row["name"]
        if supabase_api.enabled():
            try:
                supabase_api.delete_object(f"outputs/{name}")
            except supabase_api.SupabaseError:
                continue
        else:
            (config.OUTPUTS_DIR / name).unlink(missing_ok=True)
        db.delete_output_asset(name)


def get_output_bytes(name: str) -> bytes | None:
    if not _safe_name(name):
        return None
    if supabase_api.enabled():
        try:
            return supabase_api.download_object(f"outputs/{name}")
        except supabase_api.SupabaseError as exc:
            if exc.status_code == 404:
                return None
            raise
    path = (config.OUTPUTS_DIR / name).resolve()
    if not path.is_relative_to(config.OUTPUTS_DIR) or not path.is_file():
        return None
    return path.read_bytes()


def delete_output(name: str) -> bool:
    if not _safe_name(name):
        return False
    if supabase_api.enabled():
        exists = any(
            item["name"] == name for item in db.list_output_assets())
        try:
            supabase_api.delete_object(f"outputs/{name}")
        except supabase_api.SupabaseError as exc:
            if exc.status_code != 404:
                raise
        db.delete_output_asset(name)
        return exists
    path = (config.OUTPUTS_DIR / name).resolve()
    if not path.is_relative_to(config.OUTPUTS_DIR) or not path.is_file():
        return False
    path.unlink()
    db.delete_output_asset(name)
    return True


def media_type(name: str) -> str:
    return _content_type(name)
