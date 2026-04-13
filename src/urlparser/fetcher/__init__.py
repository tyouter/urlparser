"""
URL 读取层

提供原子化的 URL 内容获取能力:
- PlaywrightFetcher: Playwright 直接读取
- CookieFetcher: Cookie 认证读取
- UserChromeFetcher: 用户浏览器读取
- BrowserUseFetcher: AI 反爬读取
"""

from .base import BaseFetcher, FetchResult, FetchConfig, FetchStrategy
from .playwright_fetcher import PlaywrightFetcher
from .cookie_fetcher import CookieFetcher
from .user_chrome_fetcher import UserChromeFetcher
from .browser_use_fetcher import BrowserUseFetcher
from .factory import FetcherFactory

__all__ = [
    'BaseFetcher',
    'FetchResult',
    'FetchConfig',
    'FetchStrategy',
    'PlaywrightFetcher',
    'CookieFetcher',
    'UserChromeFetcher',
    'BrowserUseFetcher',
    'FetcherFactory',
]