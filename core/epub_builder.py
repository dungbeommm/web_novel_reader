"""Tạo file EPUB từ các chương truyện."""

from ebooklib import epub
from typing import List, Tuple


def create_epub(
    story_title: str,
    author: str,
    chapters: List[Tuple[str, str]],
    output_path: str,
    cover_url: str = "",
    description: str = "",
) -> str:
    """
    Tạo file EPUB.
    chapters: list các tuple (chapter_title, chapter_content)
    """
    book = epub.EpubBook()

    book.set_identifier(f"story-tool-{story_title}")
    book.set_title(story_title)
    book.set_language("vi")
    book.add_author(author or "Không rõ")

    if description:
        book.add_metadata("DC", "description", description)

    # CSS cho nội dung
    style = epub.EpubItem(
        uid="style",
        file_name="style/default.css",
        media_type="text/css",
        content=b"""
body { font-family: serif; line-height: 1.8; padding: 1em; }
h1 { font-size: 1.4em; margin-bottom: 1em; text-align: center; }
p { text-indent: 2em; margin: 0.5em 0; }
""",
    )
    book.add_item(style)

    epub_chapters = []
    spine = ["nav"]

    for i, (title, content) in enumerate(chapters):
        ch = epub.EpubHtml(
            title=title,
            file_name=f"chapter_{i+1:04d}.xhtml",
            lang="vi",
        )
        # Chuyển text thành HTML đơn giản
        paragraphs = content.split("\n\n")
        html_content = f"<h1>{title}</h1>\n"
        for p in paragraphs:
            p = p.strip()
            if p:
                html_content += f"<p>{p}</p>\n"

        ch.content = html_content.encode("utf-8")
        ch.add_item(style)
        book.add_item(ch)
        epub_chapters.append(ch)
        spine.append(ch)

    # Mục lục
    book.toc = epub_chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_path, book, {})
    return output_path
