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
        self._pending_storage_state: Optional[dict] = None

    def _load_storage_state(self, path: str) -> Optional[dict]:
        """Try to load a Playwright storageState JSON file.

        Returns dict with 'cookies' and 'origins' keys if the file is a valid
        storageState; returns None if the file does not exist or is not in
        storageState format (so the caller should fall back to add_cookies).
        """
        cookies_path = Path(path)
        if not cookies_path.exists():
            return None
        try:
            with open(cookies_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and 'origins' in data:
                return data
        except Exception:
            pass
        return None

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
            data = json.loads(content)
            if isinstance(data, dict) and 'cookies' in data:
                # storageState format: extract cookies list from dict
                cookies = data['cookies']
            else:
                cookies = data

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
        # If the cookie file is a Playwright storageState (contains origins),
        # use it to seed the browser context directly (preserves indexedDB /
        # localStorage, which some platforms like xiaohongshu need).
        cookies_file = self.config.cookies_file
        if cookies_file:
            storage_state = self._load_storage_state(cookies_file)
            # Also check for a sibling _storage.json (created by login_via_qr.py)
            # e.g. xiaohongshu_cookies.json → xiaohongshu_storage.json
            if storage_state is None:
                cp = Path(cookies_file)
                sibling_storage = cp.with_name(cp.stem.replace('_cookies', '_storage') + '.json')
                storage_state = self._load_storage_state(str(sibling_storage))
            if storage_state is not None:
                self._pending_storage_state = storage_state
                await super()._ensure_browser()
                return

        # Fallback: plain cookie list
        await super()._ensure_browser()
        if cookies_file and self._context:
            try:
                cookies = await self._load_cookies(cookies_file)
                if cookies:
                    await self._context.add_cookies(cookies)
            except Exception:
                pass

    async def fetch(self, url: str, **kwargs) -> FetchResult:
        cookies_file = kwargs.get('cookies_file', self.config.cookies_file)
        # Only add cookies via add_cookies() if we didn't already seed the
        # context with a full storageState in _ensure_browser().
        if cookies_file and self._context and self._pending_storage_state is None:
            try:
                cookies = await self._load_cookies(cookies_file)
                if cookies:
                    await self._context.add_cookies(cookies)
            except Exception:
                pass

        return await super().fetch(url, **kwargs)