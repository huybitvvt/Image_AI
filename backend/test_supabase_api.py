import httpx

from app import config
from app import supabase_api as api


def _mock_client(monkeypatch, handler, key="sb_secret_test"):
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def factory(**kwargs):
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(api.httpx, "Client", factory)
    monkeypatch.setattr(config, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_SECRET_KEY", key)
    monkeypatch.setattr(config, "SUPABASE_BUCKET", "image-workflow")
    monkeypatch.setattr(api, "_client", None)
    monkeypatch.setattr(api, "_client_identity", None)


def test_new_secret_key_uses_apikey_only(monkeypatch):
    seen = {}

    def handler(request):
        seen["headers"] = request.headers
        return httpx.Response(200, json=[])

    _mock_client(monkeypatch, handler)
    assert api.select("workflows") == []
    assert seen["headers"]["apikey"] == "sb_secret_test"
    assert "authorization" not in seen["headers"]


def test_legacy_service_role_uses_bearer(monkeypatch):
    seen = {}

    def handler(request):
        seen["headers"] = request.headers
        return httpx.Response(200, json=[])

    _mock_client(monkeypatch, handler, key="legacy-jwt")
    api.select("workflows")
    assert seen["headers"]["authorization"] == "Bearer legacy-jwt"


def test_storage_upload_download_delete(monkeypatch):
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path, request.content))
        if request.method == "GET":
            return httpx.Response(200, content=b"image-data")
        return httpx.Response(200, json={"ok": True})

    _mock_client(monkeypatch, handler)
    api.upload_object("uploads/a b.png", b"abc", "image/png")
    assert api.download_object("uploads/a b.png") == b"image-data"
    api.delete_object("uploads/a b.png")

    assert requests[0][:2] == (
        "POST", "/storage/v1/object/image-workflow/uploads/a b.png")
    assert requests[1][:2] == (
        "GET",
        "/storage/v1/object/authenticated/image-workflow/uploads/a b.png")
    assert requests[2][:2] == (
        "DELETE", "/storage/v1/object/image-workflow")


def test_api_error_exposes_status_without_secret(monkeypatch):
    def handler(request):
        return httpx.Response(404, json={"message": "missing"})

    _mock_client(monkeypatch, handler)
    try:
        api.download_object("uploads/missing.png")
    except api.SupabaseError as exc:
        assert exc.status_code == 404
        assert "sb_secret" not in str(exc)
    else:
        raise AssertionError("Supabase 404 phải raise SupabaseError.")


def test_partial_config_is_rejected(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_SECRET_KEY", "")
    try:
        api.enabled()
    except api.SupabaseError as exc:
        assert "cấu hình đủ" in str(exc)
    else:
        raise AssertionError("Cấu hình Supabase thiếu key phải bị từ chối.")
