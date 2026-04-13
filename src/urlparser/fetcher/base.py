"""
URL 读取器抽象基类

定义统一的 URL 内容获取接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class FetchStrategy(Enum):
    """读取策略"""
    DIRECT = "direct"
    COOKIE = "cookie"
    USER_CHROME = "user_chrome"
    BROWSER_USE = "browser_use"


@dataclass
class FetchResult:
    """URL 读取结果"""
    url: str = ""
    html: str = ""
    text: str = ""
    title: str = ""
    status_code: int = 0
    strategy: FetchStrategy = FetchStrategy.DIRECT
    success: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    page: Any = None

    @property
    def has_content(self) -> bool:
        return bool(self.text and len(self.text) > 10)

    @property
    def has_html(self) -> bool:
        return bool(self.html)

    def to_dict(self) -> Dict:
        return {
            'url': self.url,
            'title': self.title,
            'text_length': len(self.text) if self.text else 0,
            'html_length': len(self.html) if self.html else 0,
            'strategy': self.strategy.value,
            'success': self.success,
            'error': self.error,
            'metadata': self.metadata,
        }


@dataclass
class FetchConfig:
    """读取配置"""
    timeout: int = 30000
    headless: bool = True
    stealth_mode: bool = True
    scroll_enabled: bool = True
    max_scrolls: int = 20
    scroll_delay: float = 1.5
    expand_full_text: bool = True
    close_login_popup: bool = True
    cookies_file: Optional[str] = None
    user_data_dir: Optional[str] = None
    locale: str = 'zh-CN'
    timezone_id: str = 'Asia/Shanghai'
    viewport: Dict[str, int] = field(default_factory=lambda: {'width': 1920, 'height': 1080})


class BaseFetcher(ABC):
    """
    URL 读取器抽象基类

    所有读取策略必须继承此类并实现 fetch() 方法
    """

    strategy: FetchStrategy = FetchStrategy.DIRECT

    def __init__(self, config: Optional[FetchConfig] = None):
        self.config = config or FetchConfig()
        self._browser = None
        self._context = None
        self._playwright = None

    @abstractmethod
    async def fetch(self, url: str, **kwargs) -> FetchResult:
        """
        读取 URL 内容

        Args:
            url: 目标 URL
            **kwargs: 额外参数

        Returns:
            FetchResult 读取结果
        """
        pass

    async def close(self):
        """释放资源"""
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

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