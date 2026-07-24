"""Supabase Data API + Storage REST client dùng riêng ở backend."""
from __future__ import annotations

from urllib.parse import quote

import httpx

from . import config


class SupabaseError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


_client: httpx.Client | None = None
_client_identity: tuple[str, str] | None = None


def enabled() -> bool:
    if bool(config.SUPABASE_URL) != bool(config.SUPABASE_SECRET_KEY):
        raise SupabaseError(
            "Phải cấu hình đủ SUPABASE_URL và SUPABASE_SECRET_KEY.")
    if config.SUPABASE_URL and not config.SUPABASE_BUCKET:
        raise SupabaseError("SUPABASE_BUCKET không được để trống.")
    return bool(config.SUPABASE_URL and config.SUPABASE_SECRET_KEY)


def _get_client() -> httpx.Client:
    global _client, _client_identity
    if not enabled():
        raise SupabaseError(
            "Thiếu SUPABASE_URL hoặc SUPABASE_SECRET_KEY.")
    identity = (config.SUPABASE_URL, config.SUPABASE_SECRET_KEY)
    if _client is None or _client_identity != identity:
        if _client is not None:
            _client.close()
        headers = {"apikey": config.SUPABASE_SECRET_KEY}
        # Legacy service_role là JWT và cần Bearer. Secret key sb_secret_* mới
        # chỉ gửi qua apikey theo hướng dẫn hiện tại của Supabase.
        if not config.SUPABASE_SECRET_KEY.startswith("sb_secret_"):
            headers["Authorization"] = (
                f"Bearer {config.SUPABASE_SECRET_KEY}")
        _client = httpx.Client(
            base_url=config.SUPABASE_URL.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(120.0, connect=20.0),
        )
        _client_identity = identity
    return _client


def _request(method: str, path: str, **kwargs) -> httpx.Response:
    try:
        response = _get_client().request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        raise SupabaseError(f"Không kết nối được Supabase: {exc}") from exc
    if response.is_error:
        try:
            body = response.json()
            detail = body.get("message") or body.get("error") or str(body)
        except (ValueError, AttributeError):
            detail = response.text[:300]
        raise SupabaseError(
            f"Supabase trả lỗi {response.status_code}: {detail}",
            response.status_code)
    return response


def select(table: str, columns: str = "*", *, filters: dict[str, str] | None = None,
           order: str = "", limit: int | None = None,
           offset: int | None = None) -> list[dict]:
    params: dict[str, str | int] = {"select": columns}
    params.update(filters or {})
    if order:
        params["order"] = order
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return _request("GET", f"/rest/v1/{table}", params=params).json()


def insert(table: str, row: dict, *, on_conflict: str = "") -> list[dict]:
    headers = {"Prefer": "return=representation"}
    params = None
    if on_conflict:
        headers["Prefer"] = "resolution=merge-duplicates,return=representation"
        params = {"on_conflict": on_conflict}
    response = _request(
        "POST", f"/rest/v1/{table}", json=row, headers=headers, params=params)
    return response.json()


def update(table: str, values: dict, filters: dict[str, str]) -> list[dict]:
    response = _request(
        "PATCH", f"/rest/v1/{table}", json=values, params=filters,
        headers={"Prefer": "return=representation"})
    return response.json()


def delete(table: str, filters: dict[str, str]) -> list[dict]:
    response = _request(
        "DELETE", f"/rest/v1/{table}", params=filters,
        headers={"Prefer": "return=representation"})
    return response.json()


def upload_object(object_path: str, data: bytes, content_type: str) -> None:
    bucket_path = quote(
        f"{config.SUPABASE_BUCKET}/{object_path}", safe="/")
    _request(
        "POST", f"/storage/v1/object/{bucket_path}", content=data,
        headers={
            "Content-Type": content_type,
            "Cache-Control": "3600",
            "x-upsert": "false",
        })


def download_object(object_path: str) -> bytes:
    bucket_path = quote(
        f"{config.SUPABASE_BUCKET}/{object_path}", safe="/")
    return _request(
        "GET", f"/storage/v1/object/authenticated/{bucket_path}").content


def delete_object(object_path: str) -> None:
    bucket = quote(config.SUPABASE_BUCKET, safe="")
    _request(
        "DELETE", f"/storage/v1/object/{bucket}",
        json={"prefixes": [object_path]})
