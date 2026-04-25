"""
用户浏览器读取器

使用用户已登录的 Chrome 浏览器状态
"""

from typing import Optional
from pathlib import Path

from .base import BaseFetcher, FetchResult, FetchConfig, FetchStrategy
from .playwright_fetcher import PlaywrightFetcher


class UserChromeFetcher(PlaywrightFetcher):
    """
    用户浏览器读取器

    使用用户已登录的 Chrome 浏览器状态，绕过登录验证

    特性:
    - 复用用户 Chrome 登录状态
    - 无需手动导出 Cookie
    - 适合强反爬站点
    """

    strategy = FetchStrategy.USER_CHROME

    def __init__(self, config: Optional[FetchConfig] = None):
        super().__init__(config)
        self._user_data_dir = config.user_data_dir if config else None

    async def _ensure_browser(self):
        if self._browser is not None:
            return

        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        user_data_dir = self._user_data_dir
        if not user_data_dir:
            default_paths = [
                Path.home() / 'AppData' / 'Local' / 'Google' / 'Chrome' / 'User Data',
                Path.home() / 'Library' / 'Application Support' / 'Google' / 'Chrome',
                Path.home() / '.config' / 'google-chrome',
            ]
            for p in default_paths:
                if p.exists():
                    user_data_dir = str(p)
                    break

        if user_data_dir:
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=self.config.headless,
                channel='chrome',
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                ],
                viewport=self.config.viewport,
                locale=self.config.locale,
                timezone_id=self.config.timezone_id,
            )
            self._browser = self._context.browser if hasattr(self._context, 'browser') else None
        else:
            await super()._ensure_browser()