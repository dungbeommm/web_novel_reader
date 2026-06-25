"""Adapter cho wikicv.net"""

import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from core.base_adapter import BaseSiteAdapter, ChapterData, StoryMeta
from core.cleaner import clean_chapter_content


class WikicvAdapter(BaseSiteAdapter):
    """
    Adapter cho https://wikicv.net
    Cấu trúc trang:
    - Nội dung chương: .content-body-wrapper hoặc .entry-content
    - Link chương sau: a.next hoặc a[rel='next']
    - Tên truyện: .story-name hoặc breadcrumb
    """

    SUPPORTED_DOMAINS = ["wikicv.net", "wikicv.com"]

    async def get_chapter(self, html: str, url: str) -> ChapterData:
        soup = BeautifulSoup(html, "lxml")

        # Tên chương
        title = ""
        title_el = soup.select_one(
            "h1.entry-title, h2.entry-title, .chapter-title, "
            "h1.name-chapter, .heading-chapter"
        )
        if title_el:
            title = title_el.get_text(strip=True)

        # Nội dung
        content_el = soup.select_one(
            ".content-body-wrapper, .entry-content, .text-content, #content, "
            ".chapter-content, .reading-content, .content-chapter"
        )
        content = ""
        if content_el:
            content = clean_chapter_content(str(content_el))
        else:
            content = clean_chapter_content(html)

        # Link chương sau
        next_url = None
        next_el = soup.select_one(
            "a.next, a[rel='next'], a.next-chap, a.btn-next"
        )
        if not next_el:
            for a in soup.find_all("a"):
                text = a.get_text(strip=True).lower()
                href = (a.get("href") or "").lower()
                if ("chương sau" in text or "chương tiếp" in text or
                    "next" in text or "chuong-tiep" in href):
                    next_el = a
                    break
        if next_el and next_el.get("href"):
            href = next_el["href"]
            if href and href != "#" and "javascript:" not in href:
                next_url = urljoin(url, href)

        # Tên truyện
        story_title = ""
        st_el = soup.select_one(
            ".story-name, .truyen-title, a.story-name, "
            "h1.story-title"
        )
        if not st_el:
            bc = soup.select_one(".breadcrumb, nav[aria-label='breadcrumb']")
            if bc:
                links = bc.find_all("a")
                if len(links) >= 2:
                    story_title = links[-1].get_text(strip=True)
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
        st_el = soup.select_one(".story-name, .truyen-title, h1.story-title")
        if st_el:
            title = st_el.get_text(strip=True)

        author = ""
        auth_el = soup.select_one("a[href*='tac-gia'], .author, .story-author")
        if auth_el:
            author = auth_el.get_text(strip=True)

        return StoryMeta(title=title, author=author)

    def get_toc_url(self, chapter_url: str) -> str | None:
        parsed = urlparse(chapter_url)
        # wikicv.net/truyen/ten-truyen/chuong-1 → wikicv.net/truyen/ten-truyen
        parts = parsed.path.rstrip("/").rsplit("/", 1)
        if len(parts) >= 2 and re.match(r"chuong-\d+", parts[-1]):
            return f"{parsed.scheme}://{parsed.netloc}{parts[0]}"
        return None

    async def get_chapter_list(self, html: str, url: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        chapters = []
        for a in soup.select("ul.list-chapter a[href], .list-chapter a[href], .chapter-list a[href]"):
            href = a.get("href", "")
            if not href or href == "#":
                continue
            title = a.get_text(strip=True)
            chapters.append({"title": title, "url": urljoin(url, href)})
        return chapters
