"""HTTP client với anti-block: xoay User-Agent, delay, retry, vượt Cloudflare."""

import asyncio
import random
import logging
from typing import Optional

from curl_cffi.requests import AsyncSession
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import config

logger = logging.getLogger(__name__)
ua = UserAgent()


class HttpClient:
    """Client HTTP bất đồng bộ với các biện pháp chống chặn."""

    def __init__(
        self,
        min_delay: float = config.MIN_DELAY,
        max_delay: float = config.MAX_DELAY,
        max_retries: int = config.MAX_RETRIES,
        proxy: Optional[str] = config.PROXY,
    ):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.proxy = proxy
        self._session: Optional[AsyncSession] = None
        self._lock = asyncio.Lock()

    async def _get_session(self) -> AsyncSession:
        if self._session is None:
            self._session = AsyncSession(
                impersonate="chrome",
                timeout=config.REQUEST_TIMEOUT,
                proxies={"https": self.proxy, "http": self.proxy} if self.proxy else None,
            )
        return self._session

    def _random_headers(self) -> dict:
        return {
            "User-Agent": ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _delay(self):
        """Delay ngẫu nhiên giữa các request."""
        wait = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(wait)

    async def fetch(self, url: str) -> str:
        """Tải 1 URL, trả về HTML. Tự retry khi lỗi."""
        async with self._lock:
            await self._delay()

        return await self._fetch_with_retry(url)

    @retry(
        stop=stop_after_attempt(config.MAX_RETRIES),
        wait=wait_exponential(multiplier=config.RETRY_BACKOFF, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception)),
        reraise=True,
    )
    async def _fetch_with_retry(self, url: str) -> str:
        session = await self._get_session()
        headers = self._random_headers()
        try:
            resp = await session.get(url, headers=headers)
            if resp.status_code in (403, 429, 503):
                logger.warning(f"Lỗi {resp.status_code} khi tải {url}, đang thử lại...")
                raise ConnectionError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.error(f"Lỗi khi tải {url}: {e}")
            raise

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
