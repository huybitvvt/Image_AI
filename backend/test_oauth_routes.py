from app import config
from app import oauth_routes as routes


def _start_device_session(monkeypatch):
    monkeypatch.setattr(config, "CODEX_OAUTH_MODE", "device")
    monkeypatch.setattr(
        routes.oauth,
        "request_device_code",
        lambda: {
            "device_auth_id": "dev-secret",
            "user_code": "ABCD-EFGH",
            "interval": 1,
            "verification_url": "https://auth.openai.com/codex/device",
        },
    )
    routes._device_sessions.clear()
    return routes.oauth_start()


def test_device_start_does_not_expose_device_auth_id(monkeypatch):
    result = _start_device_session(monkeypatch)

    assert result["flow"] == "device_code"
    assert result["user_code"] == "ABCD-EFGH"
    assert "device_auth_id" not in result
    assert result["session_id"] in routes._device_sessions


def test_device_poll_pending_then_persists_login(monkeypatch):
    started = _start_device_session(monkeypatch)
    session_id = started["session_id"]
    monkeypatch.setattr(
        routes.oauth, "poll_device_code", lambda *_args: None)

    assert routes.oauth_device_status(session_id) == {"state": "pending"}

    routes._device_sessions[session_id]["next_poll_at"] = 0
    monkeypatch.setattr(
        routes.oauth,
        "poll_device_code",
        lambda *_args: {"access_token": "access"},
    )
    persisted = {}
    monkeypatch.setattr(
        routes.oauth, "store_login", lambda token: persisted.update(token))
    monkeypatch.setattr(
        routes.oauth,
        "status",
        lambda: {"logged_in": True, "account_id": "account", "expired": False},
    )

    result = routes.oauth_device_status(session_id)

    assert result["state"] == "complete"
    assert result["logged_in"] is True
    assert persisted == {"access_token": "access"}
    assert session_id not in routes._device_sessions
