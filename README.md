# Story Tool — Tải & Nghe Truyện Chữ Tiếng Việt

Tool tải truyện và nghe truyện (đọc bằng giọng nói) từ các website truyện chữ tiếng Việt, có giao diện web đầy đủ.

## Tính năng

- **Nghe truyện**: Text-to-Speech với nhiều chế độ giọng đọc, tự động chuyển chương
- **2 chế độ TTS**: Giọng trình duyệt (miễn phí) và Edge TTS Neural (server)
- **Cloud TTS**: Hỗ trợ Google Cloud, Azure, OpenAI TTS (tùy chọn, cần API key)
- **Tải truyện**: Tải song song hoặc tuần tự, xuất `.txt` và `.epub`
- **Chống chặn**: Delay ngẫu nhiên, xoay User-Agent, vượt Cloudflare, retry tự động
- **Resume**: Tiếp tục tải từ chỗ bị gián đoạn
- **Plugin**: Dễ dàng thêm site mới

## Site hỗ trợ

| Site | Domain |
|------|--------|
| Mê Truyện Chữ | metruyenchuvn.com |
| WikiCV | wikicv.net |

## Cài đặt

```bash
# Clone project
git clone https://github.com/your-username/story-tool.git
cd story-tool

# Tạo môi trường ảo (khuyến nghị)
python -m venv .venv

# Kích hoạt (Windows)
.venv\Scripts\activate

# Kích hoạt (Linux/Mac)
source .venv/bin/activate

# Cài thư viện
pip install -r requirements.txt
```

## Chạy

### Web UI (local)

```bash
python run.py
```

Mở trình duyệt tại `http://localhost:8000`

### CLI (command line)

```bash
# Tải 50 chương từ chương 1
python cli.py --url "https://metruyenchuvn.com/truyen/ten-truyen/chuong-1" --max 50

# Tải hết truyện
python cli.py --url "https://metruyenchuvn.com/truyen/ten-truyen/chuong-1"

# Tùy chỉnh delay và worker
python cli.py --url "..." --min-delay 2 --max-delay 5 --workers 3
```

## Sử dụng Web UI

### Tab Nghe Truyện

1. Dán link chương truyện vào ô input
2. Nhấn **Tải chương**
3. Chọn chế độ TTS:
   - **Giọng trình duyệt**: Miễn phí, dùng Web Speech API (Google/Microsoft tùy trình duyệt)
   - **Edge TTS Server**: Giọng Neural chất lượng cao (cần server chạy)
4. Chọn giọng đọc tiếng Việt từ danh sách (nhóm theo provider)
5. Điều chỉnh: tốc độ, cao độ (pitch), âm lượng
6. Nhấn **Play** để bắt đầu nghe
7. Dùng thanh kéo để tua đến đoạn muốn nghe
8. Bật **Tự động chuyển chương** để nghe liên tục

### Tab Tải Truyện

1. Dán link chương bắt đầu
2. Chọn số chương dừng (0 = tải hết)
3. Nhấn **Bắt đầu tải**
4. Khi xong, tải ZIP hoặc EPUB

Tool sẽ tự động dùng tải song song nếu có thể lấy danh sách chương từ mục lục, nếu không sẽ tải tuần tự theo liên kết chương.

## Giọng đọc (TTS)

### Giọng trình duyệt (miễn phí, mặc định)

Dùng Web Speech API có sẵn trong trình duyệt:
- **Chrome**: Giọng Google tiếng Việt
- **Edge/Windows**: Giọng Microsoft tiếng Việt

### Edge TTS Server (miễn phí, Neural)

Giọng Neural chất lượng cao từ Microsoft Edge TTS:
- `vi-VN-HoaiMyNeural` — Nữ (mặc định)
- `vi-VN-NamMinhNeural` — Nam

Cần cài `edge-tts`: `pip install edge-tts`

### Cloud TTS (tùy chọn, trả phí)

Đặt biến môi trường để kích hoạt:

```bash
# Google Cloud TTS
set GOOGLE_TTS_API_KEY=your-key

# Azure Cognitive Services TTS
set AZURE_TTS_KEY=your-key
set AZURE_TTS_REGION=southeastasia

# OpenAI TTS
set OPENAI_API_KEY=your-key
```

Trạng thái cấu hình các provider hiển thị trong phần Cài đặt TTS trên Web UI.

## Deploy GitHub Pages (phần nghe truyện)

1. Push code lên GitHub
2. Vào Settings → Pages → Source: **GitHub Actions**
3. Workflow `Deploy GitHub Pages` sẽ tự chạy khi push thư mục `docs/`
4. Truy cập: `https://your-username.github.io/story-tool/`

**Lưu ý**: Phiên bản GitHub Pages cần chạy server local (`python run.py`) để lấy nội dung chương (do CORS).

## Chạy GitHub Actions (tải truyện)

1. Vào tab **Actions** trên GitHub
2. Chọn workflow **Tải truyện**
3. Nhấn **Run workflow**
4. Nhập: link chương, số chương bắt đầu/dừng, delay
5. Khi xong, tải artifact từ kết quả workflow

## Cấu hình

Chỉnh file `config.py`:

| Tham số | Mặc định | Mô tả |
|---------|----------|-------|
| `MAX_WORKERS` | 5 | Số worker tải song song |
| `MIN_DELAY` | 1.5 | Delay tối thiểu (giây) |
| `MAX_DELAY` | 4.0 | Delay tối đa (giây) |
| `MAX_RETRIES` | 3 | Số lần retry |
| `RETRY_BACKOFF` | 2 | Hệ số exponential backoff |
| `REQUEST_TIMEOUT` | 30 | Timeout mỗi request (giây) |
| `PROXY` | None | Proxy (ví dụ: `http://user:pass@proxy:8080`) |

## Thêm site mới

Tạo file mới trong `sites/`, ví dụ `sites/newsite.py`:

```python
from core.base_adapter import BaseSiteAdapter, ChapterData, StoryMeta
from core.cleaner import clean_chapter_content
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class NewSiteAdapter(BaseSiteAdapter):
    SUPPORTED_DOMAINS = ["newsite.com"]

    async def get_chapter(self, html, url):
        soup = BeautifulSoup(html, "lxml")
        title = soup.select_one("h1.chapter-title").get_text(strip=True)
        content = clean_chapter_content(str(soup.select_one(".chapter-content")))
        next_el = soup.select_one("a.next-chapter")
        next_url = urljoin(url, next_el["href"]) if next_el else None
        return ChapterData(title=title, content=content,
                          chapter_url=url, next_url=next_url)

    async def get_story_meta(self, html, url):
        soup = BeautifulSoup(html, "lxml")
        title = soup.select_one(".story-title").get_text(strip=True)
        return StoryMeta(title=title)

    # Tùy chọn: hỗ trợ tải song song
    def get_toc_url(self, chapter_url):
        # Suy ra URL mục lục từ URL chương
        return None

    async def get_chapter_list(self, html, url):
        # Parse trang mục lục → [{"title": str, "url": str}, ...]
        return []
```

Đăng ký trong `core/site_registry.py`:

```python
from sites.newsite import NewSiteAdapter

_ADAPTERS = [
    ...,
    NewSiteAdapter(),
]
```

## Cấu trúc project

```
story-tool/
├── config.py              # Cấu hình tập trung
├── run.py                 # Chạy Web UI server
├── cli.py                 # CLI tải truyện
├── requirements.txt       # Thư viện Python
├── core/                  # Logic lõi
│   ├── base_adapter.py    # Base class cho adapter
│   ├── cleaner.py         # Làm sạch nội dung
│   ├── cloud_tts.py       # Cloud TTS providers (Google/Azure/OpenAI)
│   ├── downloader.py      # Engine tải truyện (song song + tuần tự)
│   ├── epub_builder.py    # Tạo file EPUB
│   ├── http_client.py     # HTTP client (anti-block)
│   ├── local_tts.py       # Edge TTS + Cloud TTS manager
│   └── site_registry.py   # Registry adapter
├── sites/                 # Adapter từng site
│   ├── metruyenchuvn.py
│   └── wikicv.py
├── webui/                 # FastAPI + Frontend
│   ├── app.py             # API server
│   └── static/
│       └── index.html     # Web UI đầy đủ
├── docs/                  # GitHub Pages
│   └── index.html         # Bản tĩnh (nghe truyện)
├── downloads/             # Truyện đã tải
└── .github/workflows/
    ├── download.yml       # Action tải truyện
    └── pages.yml          # Deploy GitHub Pages
```

## Thư viện sử dụng

| Thư viện | Mục đích |
|----------|----------|
| `httpx` | HTTP client bất đồng bộ |
| `beautifulsoup4` + `lxml` | Parse HTML |
| `curl_cffi` | Vượt Cloudflare (giả lập trình duyệt) |
| `fake-useragent` | Xoay vòng User-Agent |
| `tenacity` | Retry tự động với exponential backoff |
| `fastapi` + `uvicorn` | Web server và API |
| `edge-tts` | Microsoft Neural TTS (miễn phí) |
| `ebooklib` | Tạo file EPUB |
| `python-slugify` | Tạo tên file/thư mục an toàn |
| `aiohttp` + `aiofiles` | Xử lý bất đồng bộ |
| `tqdm` | Progress bar (CLI) |

## Yêu cầu hệ thống

- Python 3.10+
- Trình duyệt hiện đại (Chrome, Edge, Firefox) cho Web UI
- Kết nối Internet

## License

MIT
