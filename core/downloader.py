"""Engine tải truyện — quản lý việc tải nhiều chương, lưu file, resume."""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional
from slugify import slugify

from core.http_client import HttpClient
from core.base_adapter import ChapterData
from core.epub_builder import create_epub
from core.site_registry import get_adapter_for_url
import config

logger = logging.getLogger(__name__)


@dataclass
class DownloadProgress:
    """Trạng thái tải truyện."""
    story_title: str = ""
    total_downloaded: int = 0
    current_chapter: str = ""
    current_url: str = ""
    status: str = "idle"       # idle, downloading, paused, done, error
    errors: list = field(default_factory=list)
    chapter_list: list = field(default_factory=list)


class StoryDownloader:
    """Tải truyện theo chuỗi chương, lưu file, hỗ trợ resume."""

    def __init__(
        self,
        start_url: str,
        start_chapter: int = 1,
        max_chapters: int = 0,
        workers: int = config.MAX_WORKERS,
        min_delay: float = config.MIN_DELAY,
        max_delay: float = config.MAX_DELAY,
        on_progress: Optional[Callable] = None,
    ):
        self.start_url = start_url
        self.start_chapter = start_chapter
        self.max_chapters = max_chapters
        self.workers = workers
        self.client = HttpClient(min_delay=min_delay, max_delay=max_delay)
        self.on_progress = on_progress
        self.progress = DownloadProgress()
        self._stop_event = asyncio.Event()
        self._story_dir = ""

    def stop(self):
        self._stop_event.set()

    def _safe_filename(self, name: str) -> str:
        """Tạo tên file an toàn từ tên chương."""
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        name = name.strip()[:200]
        return name or "untitled"

    def _get_story_dir(self, title: str) -> str:
        folder = slugify(title, allow_unicode=True) or "truyen"
        path = os.path.join(config.DOWNLOAD_DIR, folder)
        os.makedirs(path, exist_ok=True)
        return path

    def _get_progress_file(self, story_dir: str) -> str:
        return os.path.join(story_dir, ".progress.json")

    def _load_progress(self, story_dir: str) -> dict:
        """Load trạng thái đã tải (để resume)."""
        pf = self._get_progress_file(story_dir)
        if os.path.exists(pf):
            with open(pf, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"downloaded_urls": [], "last_url": "", "chapters": []}

    def _save_progress(self, story_dir: str, data: dict):
        pf = self._get_progress_file(story_dir)
        with open(pf, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def _emit(self):
        if self.on_progress:
            await self.on_progress(asdict(self.progress))

    async def download(self) -> DownloadProgress:
        """Bắt đầu tải truyện từ start_url."""
        self.progress.status = "downloading"
        await self._emit()

        adapter = get_adapter_for_url(self.start_url)
        if not adapter:
            self.progress.status = "error"
            self.progress.errors.append(f"Không hỗ trợ site: {self.start_url}")
            await self._emit()
            return self.progress

        current_url = self.start_url
        chapters_data = []

        # Lấy HTML đầu tiên để biết tên truyện
        try:
            first_html = await self.client.fetch(current_url)
            meta = await adapter.get_story_meta(first_html, current_url)
            self.progress.story_title = meta.title or "Truyen"
            self._story_dir = self._get_story_dir(self.progress.story_title)
        except Exception as e:
            self.progress.status = "error"
            self.progress.errors.append(f"Không thể truy cập {current_url}: {e}")
            await self._emit()
            return self.progress

        # Load progress cũ (resume)
        saved = self._load_progress(self._story_dir)
        downloaded_urls = set(saved.get("downloaded_urls", []))

        # Try parallel download via chapter list
        chapter_list = await self._try_get_chapter_list(adapter, current_url, first_html)
        if chapter_list:
            chapters_data = await self._download_parallel(
                adapter, chapter_list, downloaded_urls, meta,
            )
        else:
            chapters_data = await self._download_sequential(
                adapter, current_url, first_html, downloaded_urls, meta,
            )

        # Tạo EPUB
        if chapters_data:
            try:
                epub_path = os.path.join(self._story_dir, f"{slugify(self.progress.story_title, allow_unicode=True)}.epub")
                create_epub(
                    story_title=self.progress.story_title,
                    author=meta.author if meta else "",
                    chapters=chapters_data,
                    output_path=epub_path,
                )
                logger.info(f"Đã tạo EPUB: {epub_path}")
            except Exception as e:
                logger.error(f"Lỗi tạo EPUB: {e}")
                self.progress.errors.append(f"Lỗi tạo EPUB: {e}")

        self.progress.status = "done" if not self.progress.errors else "done_with_errors"
        await self._emit()
        await self.client.close()
        return self.progress

    async def _try_get_chapter_list(
        self, adapter, chapter_url: str, chapter_html: str,
    ) -> list[dict]:
        toc_url = adapter.get_toc_url(chapter_url)
        if not toc_url:
            return []
        try:
            toc_html = await self.client.fetch(toc_url)
            chapters = await adapter.get_chapter_list(toc_html, toc_url)
            if chapters:
                logger.info(f"Lấy được {len(chapters)} chương từ mục lục: {toc_url}")
            return chapters
        except Exception as e:
            logger.warning(f"Không lấy được mục lục ({toc_url}): {e}")
            return []

    async def _download_parallel(
        self,
        adapter,
        chapter_list: list[dict],
        downloaded_urls: set[str],
        meta,
    ) -> list[tuple[str, str]]:
        # Apply start_chapter offset and max_chapters limit
        start_idx = max(0, self.start_chapter - 1)
        chapter_list = chapter_list[start_idx:]
        if self.max_chapters > 0:
            chapter_list = chapter_list[: self.max_chapters]

        semaphore = asyncio.Semaphore(self.workers)
        results: list[Optional[tuple[int, str, str]]] = [None] * len(chapter_list)
        lock = asyncio.Lock()

        async def fetch_one(idx: int, ch_info: dict):
            if self._stop_event.is_set():
                return
            ch_url = ch_info["url"]
            chapter_num = start_idx + idx + 1

            if ch_url in downloaded_urls:
                logger.info(f"Bỏ qua (đã tải): {ch_url}")
                return

            async with semaphore:
                if self._stop_event.is_set():
                    return
                try:
                    html = await self.client.fetch(ch_url)
                    chapter = await adapter.get_chapter(html, ch_url)

                    safe_name = self._safe_filename(chapter.title)
                    txt_path = os.path.join(self._story_dir, f"{safe_name}.txt")
                    with open(txt_path, "w", encoding="utf-8") as f:
                        f.write(chapter.content)

                    results[idx] = (chapter_num, chapter.title, chapter.content)

                    async with lock:
                        downloaded_urls.add(ch_url)
                        self.progress.total_downloaded += 1
                        self.progress.current_chapter = chapter.title
                        self.progress.current_url = ch_url
                        self.progress.chapter_list.append({
                            "num": chapter_num,
                            "title": chapter.title,
                            "file": f"{safe_name}.txt",
                        })
                        self._save_progress(self._story_dir, {
                            "downloaded_urls": list(downloaded_urls),
                            "last_url": ch_url,
                            "chapters": self.progress.chapter_list,
                        })
                        await self._emit()

                except Exception as e:
                    err = f"Lỗi chương {chapter_num} ({ch_url}): {e}"
                    logger.error(err)
                    async with lock:
                        self.progress.errors.append(err)
                    await self._emit()

        tasks = [fetch_one(i, ch) for i, ch in enumerate(chapter_list)]
        await asyncio.gather(*tasks)

        # Return in order for EPUB
        chapters_data = []
        for r in results:
            if r is not None:
                chapters_data.append((r[1], r[2]))
        return chapters_data

    async def _download_sequential(
        self,
        adapter,
        current_url: str,
        first_html: str,
        downloaded_urls: set[str],
        meta,
    ) -> list[tuple[str, str]]:
        chapter_num = self.start_chapter
        chapters_data = []

        while current_url and not self._stop_event.is_set():
            if self.max_chapters > 0 and chapter_num > self.max_chapters:
                break

            if current_url in downloaded_urls:
                logger.info(f"Bỏ qua (đã tải): {current_url}")
                try:
                    html = await self.client.fetch(current_url)
                    ch = await adapter.get_chapter(html, current_url)
                    current_url = ch.next_url
                    chapter_num += 1
                    continue
                except Exception:
                    break

            self.progress.current_url = current_url
            self.progress.current_chapter = f"Chương {chapter_num}"
            await self._emit()

            try:
                html = first_html if chapter_num == self.start_chapter else await self.client.fetch(current_url)
                first_html = None

                chapter = await adapter.get_chapter(html, current_url)
                self.progress.current_chapter = chapter.title

                safe_name = self._safe_filename(chapter.title)
                txt_path = os.path.join(self._story_dir, f"{safe_name}.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(chapter.content)

                chapters_data.append((chapter.title, chapter.content))
                downloaded_urls.add(current_url)

                self.progress.total_downloaded += 1
                self.progress.chapter_list.append({
                    "num": chapter_num,
                    "title": chapter.title,
                    "file": f"{safe_name}.txt",
                })
                await self._emit()

                self._save_progress(self._story_dir, {
                    "downloaded_urls": list(downloaded_urls),
                    "last_url": current_url,
                    "chapters": self.progress.chapter_list,
                })

                current_url = chapter.next_url
                chapter_num += 1

            except Exception as e:
                err = f"Lỗi chương {chapter_num} ({current_url}): {e}"
                logger.error(err)
                self.progress.errors.append(err)
                await self._emit()
                # Chapters are discovered via next_url linked-list — no way to skip ahead on parse failure.
                break

        return chapters_data

    def get_story_dir(self) -> str:
        return self._story_dir
