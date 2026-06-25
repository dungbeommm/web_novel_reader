"""Base adapter — mỗi site kế thừa class này."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChapterData:
    """Dữ liệu 1 chương truyện."""
    title: str                        # Tên chương
    content: str                      # Nội dung đã clean
    chapter_url: str                  # URL chương hiện tại
    next_url: Optional[str] = None    # URL chương kế (None = hết truyện)
    story_title: str = ""             # Tên truyện (lấy từ trang)


@dataclass
class StoryMeta:
    """Thông tin truyện."""
    title: str = ""
    author: str = ""
    cover_url: str = ""
    description: str = ""


class BaseSiteAdapter(ABC):
    """Adapter cho 1 website truyện. Mỗi site chỉ cần implement 3 method."""

    # Domain(s) mà adapter này xử lý — dùng để tự nhận diện
    SUPPORTED_DOMAINS: list[str] = []

    @abstractmethod
    async def get_chapter(self, html: str, url: str) -> ChapterData:
        """Parse HTML 1 trang chương → ChapterData."""
        ...

    @abstractmethod
    async def get_story_meta(self, html: str, url: str) -> StoryMeta:
        """Lấy metadata truyện (tên, tác giả...) từ trang chương."""
        ...

    def can_handle(self, domain: str) -> bool:
        """Kiểm tra adapter có hỗ trợ domain này không."""
        return any(d in domain for d in self.SUPPORTED_DOMAINS)

    async def get_chapter_list(self, html: str, url: str) -> list[dict]:
        """Lấy danh sách chương từ trang mục lục.

        Returns list of {"title": str, "url": str}.
        Default: empty list (adapter chưa hỗ trợ → fallback sang linked-list).
        """
        return []

    def get_toc_url(self, chapter_url: str) -> str | None:
        """Suy ra URL trang mục lục từ URL chương.

        Returns None nếu không xác định được.
        """
        return None
