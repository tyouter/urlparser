"""
Cookie 认证读取器

使用 Cookie 文件提供已认证的页面访问
"""

import json
from typing import Optional, List, Dict
from pathlib import Path
from playwright.async_api import BrowserContext

from .base import BaseFetcher, FetchResult, FetchConfig, FetchStrategy
from .playwright_fetcher import PlaywrightFetcher


class CookieFetcher(PlaywrightFetcher):
    """
    Cookie 认证读取器

    继承 PlaywrightFetcher，增加 Cookie 加载能力

    特性:
    - 支持多种 Cookie 格式 (JSON/NetScape)
    - 自动匹配域名
    - Cookie 缓存避免重复加载
    """

    strategy = FetchStrategy.COOKIE

    def __init__(self, config: Optional[FetchConfig] = None):
        super().__init__(config)
        self._cookies_cache: Dict[str, List[Dict]] = {}

    async def _load_cookies(self, cookies_file: str) -> List[Dict]:
        if cookies_file in self._cookies_cache:
            return self._cookies_cache[cookies_file]

        cookies_path = Path(cookies_file)
        if not cookies_path.exists():
            raise FileNotFoundError(f"Cookie file not found: {cookies_file}")

        with open(cookies_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        if content.startswith('['):
            cookies = json.loads(content)
        elif content.startswith('#') or '\t' in content:
            cookies = self._parse_netscape_cookies(content)
        else:
            cookies = json.loads(content)

        playwright_cookies = []
        for cookie in cookies:
            pc = {
                'name': cookie.get('name', ''),
                'value': cookie.get('value', ''),
                'domain': cookie.get('domain', ''),
                'path': cookie.get('path', '/'),
            }
            if cookie.get('secure'):
                pc['secure'] = True
            if cookie.get('httpOnly'):
                pc['httpOnly'] = True
            if cookie.get('sameSite'):
                pc['sameSite'] = cookie['sameSite']
            if cookie.get('expires') and cookie['expires'] > 0:
                pc['expires'] = cookie['expires']
            playwright_cookies.append(pc)

        self._cookies_cache[cookies_file] = playwright_cookies
        return playwright_cookies

    def _parse_netscape_cookies(self, content: str) -> List[Dict]:
        cookies = []
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) >= 7:
                cookies.append({
                    'domain': parts[0],
                    'path': parts[2],
                    'secure': parts[3].lower() == 'true',
                    'expires': int(parts[4]) if parts[4].isdigit() else 0,
                    'name': parts[5],
                    'value': parts[6],
                })
        return cookies

    async def _ensure_browser(self):
        await super()._ensure_browser()
        if self.config.cookies_file and self._context:
            try:
                cookies = await self._load_cookies(self.config.cookies_file)
                if cookies:
                    await self._context.add_cookies(cookies)
            except Exception:
                pass

    async def fetch(self, url: str, **kwargs) -> FetchResult:
        cookies_file = kwargs.get('cookies_file', self.config.cookies_file)
        if cookies_file and self._context:
            try:
                cookies = await self._load_cookies(cookies_file)
                if cookies:
                    await self._context.add_cookies(cookies)
            except Exception:
                pass

        return await super().fetch(url, **kwargs)