"""Cấu hình tập trung cho toàn bộ tool."""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Tải truyện ---
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
MAX_WORKERS = 5          # Số worker tải đồng thời (3-8)
MIN_DELAY = 1.5          # Delay tối thiểu giữa các request (giây)
MAX_DELAY = 4.0          # Delay tối đa
MAX_RETRIES = 3          # Số lần thử lại khi lỗi
RETRY_BACKOFF = 2        # Hệ số backoff (exponential)
REQUEST_TIMEOUT = 30     # Timeout mỗi request (giây)

# --- Proxy (tùy chọn) ---
PROXY = None             # Ví dụ: "http://user:pass@proxy:8080"

# --- TTS API keys (tùy chọn) ---
GOOGLE_TTS_API_KEY = os.getenv("GOOGLE_TTS_API_KEY", "")
AZURE_TTS_KEY = os.getenv("AZURE_TTS_KEY", "")
AZURE_TTS_REGION = os.getenv("AZURE_TTS_REGION", "southeastasia")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# --- Server ---
HOST = "0.0.0.0"
PORT = 8000
