"""CLI — dùng cho GitHub Actions hoặc chạy tay trong terminal."""

import argparse
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.downloader import StoryDownloader


async def main():
    parser = argparse.ArgumentParser(description="Tải truyện chữ tiếng Việt")
    parser.add_argument("--url", required=True, help="Link chương đầu tiên")
    parser.add_argument("--start", type=int, default=1, help="Bắt đầu từ chương số")
    parser.add_argument("--max", type=int, default=0, help="Số chương tối đa (0=hết truyện)")
    parser.add_argument("--workers", type=int, default=5, help="Số worker")
    parser.add_argument("--min-delay", type=float, default=1.5, help="Delay tối thiểu (giây)")
    parser.add_argument("--max-delay", type=float, default=4.0, help="Delay tối đa (giây)")
    args = parser.parse_args()

    async def show_progress(data):
        status = data.get("status", "")
        ch = data.get("current_chapter", "")
        total = data.get("total_downloaded", 0)
        print(f"\r[{status}] Đã tải: {total} — {ch}", end="", flush=True)

    downloader = StoryDownloader(
        start_url=args.url,
        start_chapter=args.start,
        max_chapters=args.max,
        workers=args.workers,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        on_progress=show_progress,
    )

    result = await downloader.download()
    print(f"\n\nHoàn tất! Đã tải {result.total_downloaded} chương.")
    print(f"Truyện: {result.story_title}")
    print(f"Thư mục: {downloader.get_story_dir()}")

    if result.errors:
        print(f"\nLỗi ({len(result.errors)}):")
        for e in result.errors:
            print(f"  - {e}")


if __name__ == "__main__":
    asyncio.run(main())
