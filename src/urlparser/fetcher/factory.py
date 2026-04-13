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

    @classmethod
    def auto_select(cls, url: str, config: Optional[FetchConfig] = None) -> BaseFetcher:
        """
        根据 URL 和配置自动选择最佳策略

        Args:
            url: 目标 URL
            config: 读取配置

        Returns:
            BaseFetcher 实例
        """
        config = config or FetchConfig()

        if config.cookies_file:
            return CookieFetcher(config)

        if config.user_data_dir:
            return UserChromeFetcher(config)

        domain = urlparse(url).netloc.lower()

        strong_anti_scraping = ['zhihu.com', 'xiaohongshu.com']
        if any(s in domain for s in strong_anti_scraping):
            if config.cookies_file:
                return CookieFetcher(config)

        return PlaywrightFetcher(config)