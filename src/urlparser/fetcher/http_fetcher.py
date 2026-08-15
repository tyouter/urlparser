"""
HTTP 快路径读取器（v4 任务 C）

不渲染、不启动浏览器：curl_cffi（TLS 伪装，可选）→ httpx 下载 HTML，
由 core 的 trafilatura/BeautifulSoup 通道转 Markdown。
用于 --strategy http 与 mode=metadata 的非视频快路径（毫秒级）。
"""

import asyncio
import re
from typing import Tuple

from .base import BaseFetcher, FetchResult, FetchConfig, FetchStrategy

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _http_get(url: str, timeout_sec: float) -> Tuple[int, str, str]:
    """下载 HTML。优先 curl_cffi（TLS 指纹伪装），降级 httpx。

    Returns:
        (status_code, html, final_url)
    """
    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(
            url, impersonate="chrome", timeout=timeout_sec, headers=_HEADERS,
        )
        return resp.status_code, resp.text, str(resp.url)
    except Exception:
        pass

    import httpx
    resp = httpx.get(
        url, timeout=timeout_sec, headers=_HEADERS, follow_redirects=True,
    )
    return resp.status_code, resp.text, str(resp.url)


class HttpFetcher(BaseFetcher):
    """HTTP 快路径读取器

    特性:
    - 无浏览器依赖，毫秒级获取静态页
    - curl_cffi 可用时自动 TLS 伪装（chrome 指纹）
    - 提取 <title>；正文转换交给 core 的 trafilatura/BS4 通道
    """

    strategy = FetchStrategy.HTTP

    async def fetch(self, url: str, **kwargs) -> FetchResult:
        timeout_ms = kwargs.get('timeout', self.config.timeout)
        loop = asyncio.get_event_loop()

        try:
            status, html, final_url = await loop.run_in_executor(
                None, lambda: _http_get(url, timeout_ms / 1000.0),
            )
        except Exception as e:
            return FetchResult(
                url=url, strategy=self.strategy, success=False, error=str(e),
            )

        title = ""
        m = _TITLE_RE.search(html or "")
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()

        return FetchResult(
            url=url,
            html=html,
            text=title or "",
            title=title or "",
            status_code=status,
            strategy=self.strategy,
            success=status < 400 and bool(html),
            metadata={"final_url": final_url, "fetcher": "http_fast"},
        )
