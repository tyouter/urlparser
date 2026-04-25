"""
抽象基类 - 定义解析器的统一接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
import asyncio
import json

from .models import ParseResult, ParserConfig, PlatformType
from .mixins.scrolling import ScrollingMixin
from .mixins.anti_scraping import AntiScrapingMixin
from .mixins.content_clean import ContentCleanMixin


class BaseParser(ABC):
    """
    URL 内容解析器抽象基类

    子类需要实现:
    - platform: 平台标识符
    - platform_domains: 支持的域名列表
    - selectors: CSS 选择器配置
    - extract_content(): 内容提取逻辑
    - pre_process(): 页面预处理（可选）
    - post_process(): 结果后处理（可选）
    """

    platform: str = "default"
    platform_domains: List[str] = []
    selectors: Dict[str, str] = {}

    def __init__(self, config: Optional[ParserConfig] = None):
        self.config = config or ParserConfig()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._playwright = None
        self._cookies_cache = None

    @classmethod
    def can_handle(cls, url: str) -> bool:
        domain = urlparse(url).netloc.lower()
        return any(d in domain for d in cls.platform_domains)

    async def fetch(self, url: str) -> ParseResult:
        try:
            await self._ensure_browser()
            page = await self.browser.new_page()

            try:
                result = await self._fetch_with_page(page, url)
                return result
            finally:
                await page.close()

        except Exception as e:
            return ParseResult(
                url=url,
                platform=self.platform,
                fetch_success=False,
                error=str(e)
            )

    async def _fetch_with_page(self, page: Page, url: str) -> ParseResult:
        timeout = 60000 if self.platform in ['zhihu', 'xiaohongshu'] else self.config.timeout

        await page.goto(url, timeout=timeout, wait_until='domcontentloaded')
        await asyncio.sleep(2)

        await self.pre_process(page)

        if self.config.scroll_enabled:
            await ScrollingMixin.scroll_to_load_all(
                page,
                max_scrolls=self.config.max_scrolls,
                scroll_delay=self.config.scroll_delay
            )

        content = await self.extract_content(page)
        content['url'] = url
        content['platform'] = self.platform
        content['fetch_success'] = True

        result = self.post_process(content)
        return result

    async def pre_process(self, page: Page):
        if self.config.close_login_popup:
            await AntiScrapingMixin.close_login_popup(page)

        if self.config.expand_full_text:
            await AntiScrapingMixin.expand_full_text(page)

    @abstractmethod
    async def extract_content(self, page: Page) -> Dict:
        pass

    def post_process(self, content: Dict) -> ParseResult:
        raw_text = content.get('raw_text', '') or content.get('content', '')

        if raw_text and len(raw_text) > 100:
            cleaned = ContentCleanMixin.clean_text(raw_text)
            content['raw_text'] = cleaned

        return ParseResult(
            url=content.get('url', ''),
            platform=content.get('platform', self.platform),
            title=content.get('title', ''),
            content=content.get('content', ''),
            raw_text=content.get('raw_text', ''),
            author=content.get('author', ''),
            publish_date=content.get('publish_date', ''),
            video_specific=content.get('video_specific', {}),
            article_specific=content.get('article_specific', {}),
            metadata=content.get('metadata', {}),
            fetch_success=content.get('fetch_success', False),
            error=content.get('error')
        )

    async def _ensure_browser(self):
        if self.browser is not None:
            return

        self._playwright = await async_playwright().start()

        launch_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

        use_headless = self.config.headless and self.platform not in ['zhihu', 'xiaohongshu']

        self.browser = await self._playwright.chromium.launch(
            headless=use_headless,
            args=launch_args
        )

        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            # Defaults are China-oriented; override FetchConfig for other regions
            locale='zh-CN',
            timezone_id='Asia/Shanghai'
        )

        if self.config.stealth_mode:
            await self._add_stealth_scripts()

        cookies = self._load_cookies()
        if cookies:
            await self.context.add_cookies(cookies)

    async def _add_stealth_scripts(self):
        if not self.context:
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
        window.chrome = { runtime: {} };
        """

        try:
            await self.context.add_init_script(stealth_js)
        except Exception:
            pass

    def _load_cookies(self) -> List[Dict]:
        if self._cookies_cache is not None:
            return self._cookies_cache

        if not self.config.cookies_file:
            return []

        from pathlib import Path
        cookie_path = Path(self.config.cookies_file)
        if not cookie_path.exists():
            return []

        try:
            with open(cookie_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            if content.startswith('['):
                cookies = json.loads(content)
                self._cookies_cache = cookies
                return cookies

            cookies = []
            for line in content.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 7:
                    domain, flag, path, secure, expiry, name, value = parts[:7]
                    cookies.append({
                        'name': name,
                        'value': value,
                        'domain': domain,
                        'path': path,
                        'secure': secure.lower() == 'true',
                        'expires': int(expiry) if expiry.isdigit() else None
                    })

            self._cookies_cache = cookies
            return cookies

        except Exception:
            return []

    async def close(self):
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
            self.context = None

        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
            self.browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class VideoParser(BaseParser):
    """视频平台解析器基类"""

    async def fetch(self, url: str) -> ParseResult:
        try:
            from ..transcriber.video_info import extract_video_info, is_video_url

            if not is_video_url(url):
                return await super().fetch(url)

            # 在线模式：直接调用 LLM API，跳过 yt-dlp + 浏览器
            if self.config.parse_mode == "online":
                return await self._fetch_online(url)

            # 本地模式：yt-dlp 提取
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(None, lambda: extract_video_info(url))

            if content.get('fetch_success'):
                return ParseResult(
                    url=url,
                    platform=self.platform,
                    title=content.get('title', ''),
                    content=content.get('description', ''),
                    author=content.get('author', ''),
                    publish_date=content.get('publish_date_formatted', ''),
                    video_specific={
                        'duration': content.get('duration', ''),
                        'views': content.get('views', ''),
                        'likes': content.get('likes', ''),
                        'coins': content.get('coins', ''),
                        'favorites': content.get('favorites', ''),
                        'tags': content.get('tags', ''),
                        'subtitles': content.get('subtitles', []),
                    },
                    metadata=content,
                    fetch_success=True
                )

            return await super().fetch(url)

        except Exception as e:
            return ParseResult(
                url=url,
                platform=self.platform,
                fetch_success=False,
                error=str(e)
            )

    async def _fetch_online(self, url: str) -> ParseResult:
        """在线模式：通过 LLM API 获取视频信息"""
        from ..transcriber.online_video_fetch import fetch_video_online

        content = await fetch_video_online(url)

        if content.get('fetch_success'):
            return ParseResult(
                url=url,
                platform=self.platform,
                title=content.get('title', ''),
                content=content.get('description', ''),
                author=content.get('author', ''),
                publish_date=content.get('publish_date_formatted', ''),
                video_specific={
                    'duration': content.get('duration', ''),
                    'views': content.get('views', ''),
                    'likes': content.get('likes', ''),
                    'coins': content.get('coins', ''),
                    'favorites': content.get('favorites', ''),
                    'tags': content.get('tags', ''),
                    'subtitles': content.get('subtitles', []),
                },
                metadata=content,
                fetch_success=True
            )

        return ParseResult(
            url=url,
            platform=self.platform,
            fetch_success=False,
            error=content.get('error', 'Online parse failed')
        )


class ArticleParser(BaseParser):
    """文章平台解析器基类"""

    def post_process(self, content: Dict) -> ParseResult:
        result = super().post_process(content)
        result.article_specific = {
            'votes': content.get('votes', ''),
            'comments': content.get('comments', ''),
        }
        return result