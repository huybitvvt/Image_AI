"""Triển khai lớp DB qua Supabase Data API."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from . import config
from . import supabase_api as api


EXEC_RETENTION = 50


def enabled() -> bool:
    return api.enabled()


def init_db() -> None:
    try:
        api.select("model_configs", "id", limit=1)
    except api.SupabaseError as exc:
        raise RuntimeError(
            "Supabase chưa được khởi tạo. Chạy file supabase_setup.sql "
            "trong Supabase SQL Editor.") from exc
    _bootstrap_model_config()
    _migrate_json_workflows()


def _bootstrap_model_config() -> None:
    name = config.AI_CONFIG_NAME
    if not name:
        return
    provider = config.AI_CONFIG_PROVIDER
    if provider not in {"openai", "gemini", "codex", "fake"}:
        raise ValueError(
            "AI_CONFIG_PROVIDER phải là openai, gemini, codex hoặc fake.")
    if get_model_config(name):
        return
    api.insert("model_configs", {
        "name": name,
        "provider": provider,
        "api_key": "",
        "model": config.AI_CONFIG_MODEL,
        "base_url": config.AI_CONFIG_BASE_URL,
    })


def _migrate_json_workflows() -> None:
    for path in sorted(config.WORKFLOWS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = data.get("name") or path.stem
        if not workflow_exists(name):
            api.insert("workflows", {"name": name, "data": data})


def list_model_configs() -> list[dict]:
    return api.select(
        "model_configs", filters=None, order="created_at.asc,id.asc")


def get_model_config(name: str) -> dict | None:
    rows = api.select(
        "model_configs", filters={"name": f"eq.{name}"}, limit=1)
    return rows[0] if rows else None


def get_model_config_by_id(config_id: int) -> dict | None:
    rows = api.select(
        "model_configs", filters={"id": f"eq.{config_id}"}, limit=1)
    return rows[0] if rows else None


def save_model_config(name: str, provider: str, api_key: str, model: str,
                      base_url: str, config_id: int | None = None) -> int | None:
    values = {
        "name": name,
        "provider": provider,
        "model": model,
        "base_url": base_url,
    }
    if api_key:
        values["api_key"] = api_key
    if config_id is not None:
        rows = api.update(
            "model_configs", values, {"id": f"eq.{config_id}"})
        return config_id if rows else None
    values["api_key"] = api_key
    rows = api.insert("model_configs", values)
    return int(rows[0]["id"]) if rows else None


def delete_model_config(config_id: int) -> bool:
    return bool(api.delete(
        "model_configs", {"id": f"eq.{config_id}"}))


def list_workflows() -> list[dict]:
    return api.select(
        "workflows", "name,updated_at", order="updated_at.desc")


def get_workflow(name: str) -> dict | None:
    rows = api.select(
        "workflows", "data", filters={"name": f"eq.{name}"}, limit=1)
    if not rows:
        return None
    data = rows[0]["data"]
    return json.loads(data) if isinstance(data, str) else data


def save_workflow(name: str, data: dict) -> None:
    api.insert(
        "workflows",
        {
            "name": name,
            "data": data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="name",
    )


def delete_workflow(name: str) -> bool:
    return bool(api.delete("workflows", {"name": f"eq.{name}"}))


def workflow_exists(name: str) -> bool:
    return bool(api.select(
        "workflows", "name", filters={"name": f"eq.{name}"}, limit=1))


def save_image_asset(file_id: str, display_name: str, collection: str = "",
                     source: str = "upload", source_ref: str = "",
                     source_url: str = "", content_sha: str = "",
                     size_bytes: int = 0) -> None:
    api.insert(
        "image_assets",
        {
            "file_id": file_id,
            "display_name": display_name,
            "collection": collection,
            "source": source,
            "source_ref": source_ref,
            "source_url": source_url,
            "content_sha": content_sha,
            "size_bytes": size_bytes,
        },
        on_conflict="file_id",
    )


def list_image_assets() -> list[dict]:
    return api.select("image_assets", order="created_at.desc")


def get_image_asset_by_source(source: str, source_ref: str) -> dict | None:
    if not source_ref:
        return None
    rows = api.select(
        "image_assets",
        filters={"source": f"eq.{source}", "source_ref": f"eq.{source_ref}"},
        order="created_at.desc",
        limit=1,
    )
    return rows[0] if rows else None


def delete_image_asset(file_id: str) -> None:
    api.delete("image_assets", {"file_id": f"eq.{file_id}"})


def update_image_asset_collection(file_id: str, collection: str) -> None:
    api.update(
        "image_assets", {"collection": collection},
        {"file_id": f"eq.{file_id}"})


def save_output_asset(name: str, size_bytes: int) -> None:
    api.insert(
        "output_assets",
        {
            "name": name,
            "size_bytes": size_bytes,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="name",
    )


def list_output_assets() -> list[dict]:
    return api.select("output_assets", order="created_at.desc")


def delete_output_asset(name: str) -> None:
    api.delete("output_assets", {"name": f"eq.{name}"})


def create_execution(name: str, mode: str) -> int:
    rows = api.insert("workflow_executions", {
        "workflow_name": name,
        "mode": mode,
        "status": "running",
    })
    return int(rows[0]["id"])


def finish_execution(exec_id: int, status: str, error: str, detail: dict,
                     duration_ms: int | None) -> None:
    rows = api.update(
        "workflow_executions",
        {
            "status": status,
            "error": error,
            "detail": detail,
            "duration_ms": duration_ms,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
        {"id": f"eq.{exec_id}"},
    )
    if not rows:
        return
    workflow_name = rows[0]["workflow_name"]
    retained = api.select(
        "workflow_executions", "id",
        filters={"workflow_name": f"eq.{workflow_name}"},
        order="id.desc")
    stale = retained[EXEC_RETENTION:]
    if stale:
        ids = ",".join(str(row["id"]) for row in stale)
        api.delete("workflow_executions", {"id": f"in.({ids})"})


def list_executions(name: str, limit: int, offset: int) -> tuple[list[dict], int]:
    all_rows = api.select(
        "workflow_executions",
        "id,workflow_name,mode,status,error,started_at,finished_at,duration_ms",
        filters={"workflow_name": f"eq.{name}"},
        order="id.desc")
    return all_rows[offset:offset + limit], len(all_rows)


def get_execution(exec_id: int) -> dict | None:
    rows = api.select(
        "workflow_executions", filters={"id": f"eq.{exec_id}"}, limit=1)
    if not rows:
        return None
    record = rows[0]
    if isinstance(record.get("detail"), str):
        try:
            record["detail"] = json.loads(record["detail"])
        except json.JSONDecodeError:
            record["detail"] = {}
    return record


def delete_execution(exec_id: int) -> bool:
    return bool(api.delete(
        "workflow_executions", {"id": f"eq.{exec_id}"}))


def clear_executions(name: str) -> int:
    return len(api.delete(
        "workflow_executions", {"workflow_name": f"eq.{name}"}))
