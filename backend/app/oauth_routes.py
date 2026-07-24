"""REST endpoint cho đăng nhập OpenAI qua Codex OAuth.

Local mở browser và bắt callback cổng 1455. Server headless dùng device code:
frontend mở trang OpenAI, hiển thị mã một lần và poll tới khi đăng nhập xong.
"""
import os
import secrets
import threading
import time
import webbrowser

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from . import config
from .codex_login_server import wait_for_callback
from .providers import openai_codex_oauth as oauth
from .providers.base import ProviderError

router = APIRouter(prefix="/api/oauth/openai", tags=["oauth"])

_DEVICE_SESSION_TTL = 15 * 60
_device_sessions: dict[str, dict] = {}
_device_sessions_lock = threading.Lock()


@router.get("/status")
def oauth_status():
    """Đã đăng nhập chưa (không trả token thô)."""
    return oauth.status()


@router.post("/start")
def oauth_start():
    """Bắt đầu OAuth phù hợp với môi trường desktop hoặc hosted."""
    mode = config.CODEX_OAUTH_MODE
    use_device = mode == "device" or (
        mode == "auto" and bool(os.getenv("RENDER")))
    if use_device:
        try:
            device = oauth.request_device_code()
        except ProviderError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        session_id = secrets.token_urlsafe(32)
        now = time.monotonic()
        with _device_sessions_lock:
            _cleanup_device_sessions(now)
            _device_sessions[session_id] = {
                **device,
                "created_at": now,
                "next_poll_at": now,
                "polling": False,
            }
        return {
            "flow": "device_code",
            "session_id": session_id,
            "verification_url": device["verification_url"],
            "user_code": device["user_code"],
            "interval": device["interval"],
            "expires_in": _DEVICE_SESSION_TTL,
        }

    return _browser_oauth_start()


def _browser_oauth_start():
    """Mở browser local → bắt callback → đổi token → lưu.

    Endpoint đồng bộ, FastAPI chạy trong thread pool nên chặn tới khi xong
    (≤180s) không ảnh hưởng event loop. Trả trạng thái login sau khi hoàn tất.
    """
    verifier, challenge = oauth.generate_pkce()
    state = secrets.token_urlsafe(24)
    url = oauth.build_authorize_url(challenge, state)

    if not webbrowser.open(url):
        # Không mở được trình duyệt (vd headless) → trả URL ngay, đừng chờ timeout.
        return JSONResponse(
            {"error": "Không tự mở được trình duyệt. Mở link này để đăng nhập rồi thử lại.",
             "authorize_url": url},
            status_code=400)
    try:
        code = wait_for_callback(state, timeout=180)
        token_resp = oauth.exchange_code(code, verifier)
        oauth.store_login(token_resp)
    except ProviderError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    return oauth.status()


@router.get("/device/{session_id}")
def oauth_device_status(session_id: str):
    """Poll một phiên device code; chỉ trả trạng thái, không trả token."""
    now = time.monotonic()
    with _device_sessions_lock:
        _cleanup_device_sessions(now)
        session = _device_sessions.get(session_id)
        if not session:
            return JSONResponse(
                {"error": "Mã đăng nhập đã hết hạn hoặc không tồn tại."},
                status_code=404)
        if session["polling"] or now < session["next_poll_at"]:
            return {"state": "pending"}
        session["polling"] = True
        session["next_poll_at"] = now + session["interval"]
        device_auth_id = session["device_auth_id"]
        user_code = session["user_code"]

    try:
        token_resp = oauth.poll_device_code(device_auth_id, user_code)
        if token_resp is None:
            return {"state": "pending"}
        oauth.store_login(token_resp)
    except ProviderError as exc:
        with _device_sessions_lock:
            _device_sessions.pop(session_id, None)
        return JSONResponse({"error": str(exc)}, status_code=400)
    finally:
        with _device_sessions_lock:
            current = _device_sessions.get(session_id)
            if current:
                current["polling"] = False

    with _device_sessions_lock:
        _device_sessions.pop(session_id, None)
    return {"state": "complete", **oauth.status()}


def _cleanup_device_sessions(now: float) -> None:
    expired = [
        session_id
        for session_id, session in _device_sessions.items()
        if now - session["created_at"] >= _DEVICE_SESSION_TTL
    ]
    for session_id in expired:
        _device_sessions.pop(session_id, None)
