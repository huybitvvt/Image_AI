import json

from app import main
from app.main import ModelConfigIn


def _body(response):
    return json.loads(response.body.decode("utf-8"))


def test_duplicate_model_name_returns_clear_error(monkeypatch):
    monkeypatch.setattr(
        main.db,
        "get_model_config",
        lambda _name: {"id": 1, "name": "gpt"},
    )

    response = main.save_model_config(ModelConfigIn(
        name="gpt", provider="codex", model="", api_key="", base_url=""))

    assert response.status_code == 400
    assert _body(response)["error"] == "Đã có cấu hình tên 'gpt'."


def test_system_model_name_is_rejected(monkeypatch):
    response = main.save_model_config(ModelConfigIn(
        name="__system__:test",
        provider="codex",
        model="",
        api_key="",
        base_url="",
    ))

    assert response.status_code == 400
    assert "dành riêng" in _body(response)["error"]
