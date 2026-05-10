"""
Scrapling/curl-cffi TLS fingerprint fetcher for anti-bot sites.

Uses curl_cffi (the same TLS engine scrapling wraps) to bypass Cloudflare
and similar protections. Falls back silently if curl_cffi is not installed.

Design note: scrapling's StealthyFetcher uses sync Playwright internally,
which conflicts with urlparser's asyncio architecture. Using curl_cffi
directly avoids this while providing the same TLS fingerprint randomization.
"""

from typing import Optional

from .base import BaseFetcher, FetchResult, FetchConfig, FetchStrategy


class ScraplingFetcher(BaseFetcher):
    """
    curl_cffi-based fetcher with TLS fingerprint spoofing.

    Targets generic/unknown platform URLs where standard Playwright may be
    blocked by Cloudflare. Uses curl_cffi's impersonate feature to mimic
    Chrome's TLS fingerprint.

    Graceful degradation:
        - curl_cffi not installed → fetch() returns failure
        - curl_cffi fetch fails → same fallthrough behavior
    """

    strategy = FetchStrategy.SCRAPLING

    def __init__(self, config: Optional[FetchConfig] = None):
        super().__init__(config)

    @property
    def _available(self) -> bool:
        try:
            from curl_cffi import requests  # noqa: F401
            return True
        except Exception:
            return False

    async def fetch(self, url: str, **kwargs) -> FetchResult:
        if not self._available:
            return FetchResult(
                url=url, strategy=self.strategy,
                success=False, error="curl_cffi not installed",
            )

        try:
            from curl_cffi import requests
            import asyncio

            timeout = kwargs.get('timeout', self.config.timeout) / 1000  # ms -> s

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    url,
                    impersonate="chrome",
                    timeout=timeout,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                    },
                )
            )

            return FetchResult(
                url=url,
                html=response.text,
                text=response.text,
                title="",
                status_code=response.status_code,
                strategy=self.strategy,
                success=response.status_code < 400,
                metadata={"fetcher": "curl_cffi", "status": response.status_code},
            )

        except Exception as e:
            return FetchResult(
                url=url,
                strategy=self.strategy,
                success=False,
                error=f"curl_cffi fetch failed: {str(e)[:200]}",
            )

    async def close(self):
        pass
