#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chạy server Web UI."""

import sys
import os

# Force UTF-8 encoding
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
import config

if __name__ == "__main__":
    print("=" * 50)
    print("🎙️ Story Tool - Nghe & Tải Truyện")
    print("=" * 50)
    print(f"Mở trình duyệt: http://127.0.0.1:{config.PORT}")
    print("Nhấn Ctrl+C để dừng")
    print("=" * 50)
    uvicorn.run(
        "webui.app:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
    )
