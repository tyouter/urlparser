"""
读取器工厂

根据配置自动选择合适的读取策略
"""

from typing import Optional
from urllib.parse import urlparse

from .base import BaseFetcher, FetchResult, FetchConfig, FetchStrategy
from .playwright_fetcher import PlaywrightFetcher
from .cookie_fetcher import CookieFetcher
from .user_chrome_fetcher import UserChromeFetcher
from .browser_use_fetcher import BrowserUseFetcher
from .bb_browser_fetcher import BbBrowserFetcher


class FetcherFactory:
    """
    读取器工厂

    根据配置自动选择合适的读取策略

    使用方式:
        # 自动选择
        fetcher = FetcherFactory.create(config)
        result = await fetcher.fetch(url)

        # 指定策略
        fetcher = FetcherFactory.create(config, strategy=FetchStrategy.COOKIE)
        result = await fetcher.fetch(url, cookies_file="cookies.json")
    """

    _registry = {
        FetchStrategy.DIRECT: PlaywrightFetcher,
        FetchStrategy.COOKIE: CookieFetcher,
        FetchStrategy.USER_CHROME: UserChromeFetcher,
        FetchStrategy.BROWSER_USE: BrowserUseFetcher,
        FetchStrategy.BB_BROWSER: BbBrowserFetcher,
    }

    @classmethod
    def create(
        cls,
        config: Optional[FetchConfig] = None,
        strategy: Optional[FetchStrategy] = None,
    ) -> BaseFetcher:
        """
        创建读取器实例

        Args:
            config: 读取配置
            strategy: 指定策略（可选，不指定则根据配置自动选择）

        Returns:
            BaseFetcher 实例
        """
        config = config or FetchConfig()

        if strategy:
            fetcher_cls = cls._registry.get(strategy)
            if not fetcher_cls:
                raise ValueError(f"Unknown strategy: {strategy}")
            return fetcher_cls(config)

        if config.cookies_file:
            return CookieFetcher(config)

        if config.user_data_dir:
            return UserChromeFetcher(config)

        return PlaywrightFetcher(config)

    _COOKIE_PRIORITY_PLATFORMS = {'zhihu', 'xiaohongshu', 'weixin'}

    @classmethod
    def auto_select(cls, url: str, config: Optional[FetchConfig] = None) -> BaseFetcher:
        config = config or FetchConfig()

        platform = cls._detect_platform(url)

        if platform in cls._COOKIE_PRIORITY_PLATFORMS:
            if config.cookies_file:
                return CookieFetcher(config)
            cookies_file = cls._try_auto_cookies(url)
            if cookies_file:
                config = FetchConfig(
                    timeout=config.timeout,
                    headless=config.headless,
                    compatibility_mode=config.compatibility_mode,
                    scroll_enabled=config.scroll_enabled,
                    max_scrolls=config.max_scrolls,
                    scroll_delay=config.scroll_delay,
                    load_full_content=config.load_full_content,
                    dismiss_popups=config.dismiss_popups,
                    cookies_file=cookies_file,
                )
                return CookieFetcher(config)

        bb_fetcher = BbBrowserFetcher(config)
        if bb_fetcher._check_bb_browser():
            return bb_fetcher

        if config.cookies_file:
            return CookieFetcher(config)

        cookies_file = cls._try_auto_cookies(url)
        if cookies_file:
            config = FetchConfig(
                timeout=config.timeout,
                headless=config.headless,
                compatibility_mode=config.compatibility_mode,
                scroll_enabled=config.scroll_enabled,
                max_scrolls=config.max_scrolls,
                scroll_delay=config.scroll_delay,
                load_full_content=config.load_full_content,
                dismiss_popups=config.dismiss_popups,
                cookies_file=cookies_file,
            )
            return CookieFetcher(config)

        if config.user_data_dir:
            return UserChromeFetcher(config)

        return PlaywrightFetcher(config)

    @classmethod
    def _detect_platform(cls, url: str) -> str:
        try:
            from ..utils import detect_platform
            return detect_platform(url)
        except Exception:
            return ''

    @classmethod
    def _try_auto_cookies(cls, url: str) -> Optional[str]:
        try:
            from ..cookies_manager import CookieManager
            from ..utils import detect_platform
            platform = detect_platform(url)
            mgr = CookieManager()
            cookies_path = mgr.get_cookies_path(platform)
            if not mgr._is_valid(cookies_path):
                mgr._refresh_from_browser(platform)
            if cookies_path.exists():
                return str(cookies_path)
        except Exception:
            pass
        return None