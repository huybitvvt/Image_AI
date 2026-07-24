import json

from app import config, remote_db
from app import supabase_api as api


def test_remote_init_bootstraps_model_and_workflow(tmp_path, monkeypatch):
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "demo.json").write_text(
        json.dumps({"name": "demo", "nodes": [], "edges": []}),
        encoding="utf-8")
    monkeypatch.setattr(config, "WORKFLOWS_DIR", workflows)
    monkeypatch.setattr(config, "AI_CONFIG_NAME", "gpt")
    monkeypatch.setattr(config, "AI_CONFIG_PROVIDER", "openai")
    monkeypatch.setattr(config, "AI_CONFIG_MODEL", "gpt-image-1")
    monkeypatch.setattr(config, "AI_CONFIG_BASE_URL", "")

    inserted = []

    def select(table, columns="*", **kwargs):
        assert table in {"model_configs", "workflows"}
        return []

    def insert(table, row, **kwargs):
        inserted.append((table, row))
        return [{"id": 1, **row}]

    monkeypatch.setattr(api, "select", select)
    monkeypatch.setattr(api, "insert", insert)

    remote_db.init_db()

    assert inserted[0][0] == "model_configs"
    assert inserted[0][1]["name"] == "gpt"
    assert inserted[1][0] == "workflows"
    assert inserted[1][1]["data"]["name"] == "demo"


def test_remote_image_upsert_includes_size(monkeypatch):
    captured = {}

    def insert(table, row, **kwargs):
        captured.update({"table": table, "row": row, **kwargs})
        return [row]

    monkeypatch.setattr(api, "insert", insert)
    remote_db.save_image_asset(
        "a.png", "A", "Sàn", "upload", "", "", "sha", 123)

    assert captured["table"] == "image_assets"
    assert captured["row"]["size_bytes"] == 123
    assert captured["on_conflict"] == "file_id"
