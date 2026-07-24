import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Khi đóng gói PyInstaller (sys.frozen): __file__ nằm trong thư mục giải nén tạm
# (sys._MEIPASS, read-only) → KHÔNG dùng làm nơi ghi dữ liệu. Đặt ROOT_DIR cạnh
# file .exe để DB/cache/ảnh sống lâu dài; SPA lấy từ data bundle (_MEIPASS).
if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys.executable).resolve().parent  # ghi được, cạnh .exe
    SPA_DIR = Path(sys._MEIPASS) / "frontend_dist"  # frontend build nhúng kèm
else:
    ROOT_DIR = Path(__file__).resolve().parents[2]
    SPA_DIR = ROOT_DIR / "frontend" / "dist"

load_dotenv(ROOT_DIR / ".env")

# Cho phép host gắn persistent disk cho toàn bộ dữ liệu runtime trong khi
# frontend và workflow mẫu vẫn được đọc từ image ứng dụng.
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR)).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

OUTPUTS_DIR = DATA_DIR / "outputs"
UPLOADS_DIR = DATA_DIR / "uploads"
WORKFLOWS_DIR = ROOT_DIR / "workflows"
# Cache output node trên đĩa (sống qua --reload): nodes/ manifest, blobs/ ảnh dedupe.
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "data.db"

for d in (OUTPUTS_DIR, UPLOADS_DIR, WORKFLOWS_DIR, CACHE_DIR / "nodes", CACHE_DIR / "blobs"):
    d.mkdir(parents=True, exist_ok=True)

# Ngưỡng tổng dung lượng blobs cache; vượt → tự xóa blob cũ nhất (LRU theo mtime).
CACHE_MAX_BYTES = int(os.getenv("CACHE_MAX_BYTES", str(500 * 1024 * 1024)))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Tạo sẵn một cấu hình model khi khởi động server mới. API key vẫn đọc từ
# biến môi trường của provider và không bị ghi vào SQLite.
AI_CONFIG_NAME = os.getenv("AI_CONFIG_NAME", "").strip()
AI_CONFIG_PROVIDER = os.getenv("AI_CONFIG_PROVIDER", "").strip()
AI_CONFIG_MODEL = os.getenv("AI_CONFIG_MODEL", "").strip()
AI_CONFIG_BASE_URL = os.getenv("AI_CONFIG_BASE_URL", "").strip()

# File token OAuth ChatGPT của Codex CLI (dùng chung — tránh đăng nhập lại nếu
# user đã chạy `codex login`). Override qua CODEX_AUTH_FILE nếu cần.
CODEX_AUTH_FILE = Path(os.getenv("CODEX_AUTH_FILE", Path.home() / ".codex" / "auth.json"))

# CODEX_DEBUG=1 → ghi log request/response (SSE) của provider codex vào
# logs/codex/ để soi lỗi khi tạo ảnh treo hoặc thất bại.
CODEX_DEBUG = os.getenv("CODEX_DEBUG", "").lower() in ("1", "true", "yes")
LOGS_DIR = DATA_DIR / "logs"
