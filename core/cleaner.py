"""Làm sạch nội dung chương: xóa quảng cáo, watermark, script, nút điều hướng."""

import re
from bs4 import BeautifulSoup, Comment


# Các selector cần loại bỏ
REMOVE_SELECTORS = [
    "script", "style", "iframe", "noscript",
    ".ads", ".advertisement", ".ad-container", "[class*='quang-cao']",
    ".comment", ".comments", "#comments", ".fb-comments",
    ".navigation", ".chapter-nav", ".nav-chapter", ".btn-nav",
    ".breadcrumb", ".social-share", ".share",
    "footer", "header", "nav",
    ".watermark", "[class*='watermark']",
    ".report", ".bookmark", ".rating",
    "[class*='footer']", "[class*='header']", "[class*='menu']",
    "[class*='sidebar']", ".sidebar",
    ".notice", ".alert", ".warning",
]

# Pattern nội dung watermark/quảng cáo trong text
SPAM_PATTERNS = [
    r"truyện được lấy từ.*?\.com",
    r"nguồn:?\s*https?://\S+",
    r"đọc truyện.*?tại.*?\.com",
    r"chương trước|chương sau|chương tiếp",
    r"← trước|sau →",
    r"www\.\S+\.com",
    r"^\s*quảng cáo\s*$",
]


_VIET_LETTER = re.compile(
    r"(?<=[a-zA-ZÀ-ỹĐđ])\.(?=[a-zA-ZÀ-ỹĐđ])"
)


def remove_hidden_dots(text: str) -> str:
    """Xóa dấu chấm giấu giữa các chữ cái trong từ.

    Nhiều nguồn chèn dấu chấm để qua mặt bộ lọc (vd: "chế.t" → "chết").
    Chỉ xóa dấu chấm nằm giữa hai chữ cái (kể cả có dấu tiếng Việt),
    không ảnh hưởng dấu chấm cuối câu hay số thập phân.
    """
    return _VIET_LETTER.sub("", text)


def clean_chapter_content(html: str, content_selector: str = None) -> str:
    """Làm sạch HTML chương, trả về text thuần."""
    soup = BeautifulSoup(html, "lxml")

    # Xóa comment HTML
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Xóa các element không cần
    for sel in REMOVE_SELECTORS:
        for el in soup.select(sel):
            el.decompose()

    # Lấy phần nội dung chính nếu có selector
    if content_selector:
        content_el = soup.select_one(content_selector)
        if content_el:
            soup = content_el

    text = soup.get_text(separator="\n")

    # Xóa các dòng spam/watermark
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            cleaned.append("")
            continue
        is_spam = any(re.search(p, line, re.IGNORECASE) for p in SPAM_PATTERNS)
        if not is_spam:
            cleaned.append(line)

    text = "\n".join(cleaned)

    # Xóa dấu chấm giấu trong từ (vd: "chế.t" → "chết", "đi.ên" → "điên")
    text = remove_hidden_dots(text)

    # Gộp nhiều dòng trống liên tiếp thành 1
    result = re.sub(r"\n{3,}", "\n\n", text)
    return result.strip()


def extract_chapter_title(html: str, title_selector: str = None) -> str:
    """Trích xuất tên chương từ HTML."""
    soup = BeautifulSoup(html, "lxml")
    if title_selector:
        el = soup.select_one(title_selector)
        if el:
            return el.get_text(strip=True)
    # Fallback: tìm h1, h2
    for tag in ["h1", "h2"]:
        el = soup.find(tag)
        if el:
            return el.get_text(strip=True)
    return "Untitled"
