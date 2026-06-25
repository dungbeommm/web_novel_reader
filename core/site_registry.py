"""Registry — tự động tìm adapter phù hợp dựa trên domain URL."""

from urllib.parse import urlparse
from typing import Optional

from core.base_adapter import BaseSiteAdapter

# Import tất cả adapter
from sites.metruyenchuvn import MetruyenchuvnAdapter
from sites.wikicv import WikicvAdapter

# Danh sách adapter đã đăng ký
_ADAPTERS: list[BaseSiteAdapter] = [
    MetruyenchuvnAdapter(),
    WikicvAdapter(),
]


def get_adapter_for_url(url: str) -> Optional[BaseSiteAdapter]:
    """Tìm adapter phù hợp cho URL."""
    domain = urlparse(url).netloc.lower()
    for adapter in _ADAPTERS:
        if adapter.can_handle(domain):
            return adapter
    return None


def register_adapter(adapter: BaseSiteAdapter):
    """Đăng ký adapter mới runtime."""
    _ADAPTERS.append(adapter)


def list_supported_sites() -> list[str]:
    """Danh sách domain hỗ trợ."""
    domains = []
    for a in _ADAPTERS:
        domains.extend(a.SUPPORTED_DOMAINS)
    return domains
