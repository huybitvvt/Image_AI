import io

from PIL import Image

from app import db, image_assets, output_assets, supabase_api


def _png() -> bytes:
    data = io.BytesIO()
    Image.new("RGB", (20, 12), "green").save(data, "PNG")
    return data.getvalue()


def test_upload_and_read_use_supabase_storage(monkeypatch):
    objects = {}
    rows = []

    monkeypatch.setattr(supabase_api, "enabled", lambda: True)
    monkeypatch.setattr(
        supabase_api, "upload_object",
        lambda path, data, content_type: objects.__setitem__(path, data))
    monkeypatch.setattr(
        supabase_api, "download_object", lambda path: objects[path])
    monkeypatch.setattr(
        supabase_api, "delete_object", lambda path: objects.pop(path, None))
    monkeypatch.setattr(db, "get_image_asset_by_source", lambda *args: None)

    def save_asset(file_id, display_name, collection, source, source_ref,
                   source_url, content_sha, size_bytes):
        rows.append({
            "file_id": file_id,
            "display_name": display_name,
            "collection": collection,
            "source": source,
            "source_ref": source_ref,
            "source_url": source_url,
            "content_sha": content_sha,
            "size_bytes": size_bytes,
            "created_at": "2026-07-24T10:00:00+00:00",
        })

    monkeypatch.setattr(db, "save_image_asset", save_asset)
    monkeypatch.setattr(db, "list_image_assets", lambda: list(rows))
    monkeypatch.setattr(
        db, "delete_image_asset",
        lambda file_id: rows.__setitem__(
            slice(None), [row for row in rows if row["file_id"] != file_id]))

    asset, created = image_assets.save_upload(
        _png(), "san.png", collection="Sàn gỗ")

    assert created is True
    assert asset["collection"] == "Sàn gỗ"
    assert f"uploads/{asset['file_id']}" in objects
    assert image_assets.get_upload_bytes(asset["file_id"]) == (
        objects[f"uploads/{asset['file_id']}"])
    assert image_assets.list_uploads()[0]["display_name"] == "san.png"
    assert image_assets.delete_upload(asset["file_id"]) is True
    assert not objects


def test_output_uses_supabase_storage(monkeypatch):
    objects = {}
    rows = []

    monkeypatch.setattr(supabase_api, "enabled", lambda: True)
    monkeypatch.setattr(
        supabase_api, "upload_object",
        lambda path, data, content_type: objects.__setitem__(path, data))
    monkeypatch.setattr(
        supabase_api, "download_object", lambda path: objects[path])
    monkeypatch.setattr(
        supabase_api, "delete_object", lambda path: objects.pop(path, None))
    monkeypatch.setattr(
        db, "save_output_asset",
        lambda name, size: rows.append({
            "name": name,
            "size_bytes": size,
            "created_at": "2026-07-24T10:00:00+00:00",
        }))
    monkeypatch.setattr(db, "list_output_assets", lambda: list(rows))
    monkeypatch.setattr(
        db, "delete_output_asset",
        lambda name: rows.__setitem__(
            slice(None), [row for row in rows if row["name"] != name]))

    path = output_assets.save_output("result.png", b"image")

    assert path == "/api/outputs/result.png"
    assert output_assets.get_output_bytes("result.png") == b"image"
    assert output_assets.list_outputs()[0]["size"] == 5
    assert output_assets.delete_output("result.png") is True
    assert not objects
