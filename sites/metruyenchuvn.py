"""Adapter cho metruyenchuvn.com"""

import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from core.base_adapter import BaseSiteAdapter, ChapterData, StoryMeta
from core.cleaner import clean_chapter_content


class MetruyenchuvnAdapter(BaseSiteAdapter):
    """
    Adapter cho https://metruyenchuvn.com
    Cấu trúc trang:
    - Nội dung chương: #chapter-c hoặc .chapter-c hoặc .truyen
    - Link chương sau: a#next_chap hoặc a.next
    - Tên truyện: h1.truyen-title hoặc .story-title
    """

    SUPPORTED_DOMAINS = ["metruyenchuvn.com", "metruyenchu.com"]

    async def get_chapter(self, html: str, url: str) -> ChapterData:
        soup = BeautifulSoup(html, "lxml")

        # Tên chương
        title = ""
        title_el = soup.select_one("h2.heading, .chapter-title, a.chapter-title")
        if title_el:
            title = title_el.get_text(strip=True)

        # Nội dung
        content_el = soup.select_one("#chapter-c, .chapter-c, #chapterbody, .chapter-content, .truyen")
        content = ""
        if content_el:
            content = clean_chapter_content(str(content_el))
        else:
            content = clean_chapter_content(html)

        # Link chương sau
        next_url = None
        next_el = soup.select_one("a#next_chap, a.next, a[title*='Chương sau'], a[title*='chương sau']")
        if not next_el:
            for a in soup.find_all("a"):
                text = a.get_text(strip=True).lower()
                if "chương sau" in text or "chương tiếp" in text or "next" in text:
                    next_el = a
                    break
        if next_el and next_el.get("href"):
            href = next_el["href"]
            if href and href != "#" and "javascript:" not in href:
                next_url = urljoin(url, href)

        # Tên truyện
        story_title = ""
        st_el = soup.select_one("h1.truyen-title, .story-title, a.truyen-title")
        if st_el:
            story_title = st_el.get_text(strip=True)

        return ChapterData(
            title=title or "Chương không rõ",
            content=content,
            chapter_url=url,
            next_url=next_url,
            story_title=story_title,
        )

    async def get_story_meta(self, html: str, url: str) -> StoryMeta:
        soup = BeautifulSoup(html, "lxml")

        title = ""
        st_el = soup.select_one("h1.truyen-title, .story-title, a.truyen-title")
        if st_el:
            title = st_el.get_text(strip=True)

        author = ""
        auth_el = soup.select_one("a[href*='tac-gia'], .author, span[itemprop='author']")
        if auth_el:
            author = auth_el.get_text(strip=True)

        return StoryMeta(title=title, author=author)

    def get_toc_url(self, chapter_url: str) -> str | None:
        parsed = urlparse(chapter_url)
        # metruyenchuvn.com/truyen-name/chuong-1 → metruyenchuvn.com/truyen-name
        parts = parsed.path.rstrip("/").rsplit("/", 1)
        if len(parts) >= 2 and re.match(r"chuong-\d+", parts[-1]):
            return f"{parsed.scheme}://{parsed.netloc}{parts[0]}"
        return None

    async def get_chapter_list(self, html: str, url: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        chapters = []
        for a in soup.select("ul.list-chapter a[href], .list-chapter a[href]"):
            href = a.get("href", "")
            if not href or href == "#":
                continue
            title = a.get_text(strip=True)
            chapters.append({"title": title, "url": urljoin(url, href)})
        return chapters
