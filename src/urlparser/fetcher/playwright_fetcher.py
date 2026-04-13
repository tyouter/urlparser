"""
Playwright 直接读取器

使用 Playwright 直接访问 URL，获取页面内容
"""

import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .base import BaseFetcher, FetchResult, FetchConfig, FetchStrategy


class PlaywrightFetcher(BaseFetcher):
    """
    Playwright 直接读取器

    特性:
    - Stealth 模式避免检测
    - 智能滚动加载懒加载内容
    - 自动关闭登录弹窗
    - 自动展开全文
    """

    strategy = FetchStrategy.DIRECT

    def __init__(self, config: Optional[FetchConfig] = None):
        super().__init__(config)

    async def _ensure_browser(self):
        if self._browser is not None:
            return

        self._playwright = await async_playwright().start()

        launch_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

        self._browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
            args=launch_args
        )

        self._context = await self._browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport=self.config.viewport,
            locale=self.config.locale,
            timezone_id=self.config.timezone_id
        )

        if self.config.stealth_mode:
            await self._add_stealth_scripts()

    async def _add_stealth_scripts(self):
        if not self._context:
            return

        stealth_js = """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                { name: 'Native Client', filename: 'internal-nacl-plugin' }
            ]
        });
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
        window.chrome = { runtime: {} };
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        """

        try:
            await self._context.add_init_script(stealth_js)
        except Exception:
            pass

    async def _close_login_popup(self, page: Page):
        close_selectors = [
            '.Modal-closeButton',
            '[class*="close"]',
            'button[aria-label="关闭"]',
            '.css-1u4r8cb',
            '.login-container .close',
            '#login-container .close',
            'svg[class*="close"]',
        ]

        for selector in close_selectors:
            try:
                close_btn = await page.query_selector(selector)
                if close_btn and await close_btn.is_visible():
                    await close_btn.click()
                    await asyncio.sleep(0.5)
                    break
            except Exception:
                continue

        try:
            await page.evaluate('document.body.click()')
            await asyncio.sleep(0.3)
            await page.keyboard.press('Escape')
            await asyncio.sleep(0.3)
        except Exception:
            pass

    async def _expand_full_text(self, page: Page):
        expand_selectors = [
            'button[class*="ExpandButton"]',
            'button:has-text("阅读全文")',
            'span:has-text("阅读全文")',
            '[class*="expand"]:has-text("全文")',
            '.read-more',
            '[class*="show-all"]',
            '[class*="expand-content"]',
        ]

        for selector in expand_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(0.5)
            except Exception:
                continue

        for text in ['阅读全文', '展开', '查看全部', 'Show more']:
            try:
                btn = page.get_by_text(text, exact=True)
                if await btn.count() > 0:
                    first = btn.first
                    if await first.is_visible():
                        await first.click()
                        await asyncio.sleep(0.5)
                        break
            except Exception:
                continue

    async def _scroll_to_load_all(self, page: Page):
        last_height = await page.evaluate('document.body.scrollHeight')
        no_change_count = 0
        max_no_change = 5

        for i in range(self.config.max_scrolls):
            current_height = await page.evaluate('document.body.scrollHeight')

            if current_height == last_height:
                no_change_count += 1
                if no_change_count >= max_no_change:
                    break

            try:
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(self.config.scroll_delay)

                await page.wait_for_load_state('networkidle', timeout=8000)

                new_height = await page.evaluate('document.body.scrollHeight')

                if new_height > current_height:
                    no_change_count = 0
                    last_height = new_height
                elif new_height == current_height:
                    no_change_count += 1

            except Exception:
                break

        await page.evaluate('window.scrollTo(0, 0)')

    async def fetch(self, url: str, **kwargs) -> FetchResult:
        try:
            await self._ensure_browser()
            page = await self._context.new_page()

            try:
                timeout = kwargs.get('timeout', self.config.timeout)
                await page.goto(url, timeout=timeout, wait_until='domcontentloaded')
                await asyncio.sleep(2)

                if self.config.close_login_popup:
                    await self._close_login_popup(page)

                if self.config.expand_full_text:
                    await self._expand_full_text(page)

                if self.config.scroll_enabled:
                    await self._scroll_to_load_all(page)

                title = await page.title()
                text = await page.evaluate('document.body.innerText')
                html = await page.content()

                return FetchResult(
                    url=url,
                    html=html,
                    text=text or '',
                    title=title or '',
                    status_code=200,
                    strategy=self.strategy,
                    success=True,
                    metadata={'final_url': page.url}
                )

            finally:
                await page.close()

        except Exception as e:
            return FetchResult(
                url=url,
                strategy=self.strategy,
                success=False,
                error=str(e)
            )