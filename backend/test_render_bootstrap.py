from app import config, db


def test_init_db_bootstraps_model_config_from_env(tmp_path, monkeypatch):
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data.db")
    monkeypatch.setattr(config, "WORKFLOWS_DIR", workflows)
    monkeypatch.setattr(config, "AI_CONFIG_NAME", "gpt")
    monkeypatch.setattr(config, "AI_CONFIG_PROVIDER", "openai")
    monkeypatch.setattr(config, "AI_CONFIG_MODEL", "gpt-image-1")
    monkeypatch.setattr(config, "AI_CONFIG_BASE_URL", "")

    db.init_db()

    model = db.get_model_config("gpt")
    assert model is not None
    assert model["provider"] == "openai"
    assert model["model"] == "gpt-image-1"
    assert model["api_key"] == ""


def test_init_db_rejects_invalid_bootstrap_provider(tmp_path, monkeypatch):
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data.db")
    monkeypatch.setattr(config, "WORKFLOWS_DIR", workflows)
    monkeypatch.setattr(config, "AI_CONFIG_NAME", "bad")
    monkeypatch.setattr(config, "AI_CONFIG_PROVIDER", "unknown")

    try:
        db.init_db()
    except ValueError as exc:
        assert "AI_CONFIG_PROVIDER" in str(exc)
    else:
        raise AssertionError("Provider bootstrap không hợp lệ phải bị từ chối.")
