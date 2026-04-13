"""
统一配置

整合解析器配置 + 转录配置 + 浏览器配置
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path


@dataclass
class BrowserConfig:
    """浏览器配置"""
    use_user_chrome: bool = False
    user_data_dir: Optional[str] = None
    cookies_file: Optional[str] = None
    headless: bool = True
    timeout: int = 30000
    stealth_mode: bool = True


@dataclass
class ScrollConfig:
    """滚动配置"""
    enabled: bool = True
    max_scrolls: int = 20
    scroll_delay: float = 1.5


@dataclass
class TranscribeConfig:
    """音频转录配置"""
    enabled: bool = False
    engine: str = "auto"
    model_size: str = "large"
    device: str = "auto"
    language: str = "zh"


@dataclass
class ParseConfig:
    """
    统一解析配置

    使用方式:
        config = ParseConfig(
            enable_transcribe=True,
            cookies_file="cookies/zhihu_cookies.json",
            transcribe_engine="funasr",
        )

        result = await parse(url, config=config)
    """

    browser: BrowserConfig = field(default_factory=BrowserConfig)
    scroll: ScrollConfig = field(default_factory=ScrollConfig)
    transcribe: TranscribeConfig = field(default_factory=TranscribeConfig)

    expand_full_text: bool = True
    close_login_popup: bool = True

    @classmethod
    def simple(cls, **kwargs):
        """快速创建简单配置"""
        return cls(**kwargs)

    @classmethod
    def with_transcribe(cls, engine: str = "auto", **kwargs):
        """启用转录的配置"""
        transcribe = TranscribeConfig(enabled=True, engine=engine)
        return cls(transcribe=transcribe, **kwargs)

    @classmethod
    def with_cookies(cls, cookies_file: str, **kwargs):
        """使用 Cookie 的配置"""
        browser = BrowserConfig(cookies_file=cookies_file)
        return cls(browser=browser, **kwargs)

    @classmethod
    def full_feature(cls, **kwargs):
        """全功能配置（滚动+展开+弹窗关闭+转录）"""
        return cls(
            browser=BrowserConfig(
                headless=False,
                stealth_mode=True,
            ),
            scroll=ScrollConfig(enabled=True, max_scrolls=20),
            expand_full_text=True,
            close_login_popup=True,
            **kwargs
        )

    def to_parser_config(self):
        """转换为 parsers 模块的 ParserConfig"""
        from .parser import ParserConfig

        return ParserConfig(
            use_user_chrome=self.browser.use_user_chrome,
            user_data_dir=self.browser.user_data_dir,
            cookies_file=self.browser.cookies_file,
            timeout=self.browser.timeout,
            headless=self.browser.headless,
            scroll_enabled=self.scroll.enabled,
            max_scrolls=self.scroll.max_scrolls,
            scroll_delay=self.scroll.scroll_delay,
            expand_full_text=self.expand_full_text,
            close_login_popup=self.close_login_popup,
            stealth_mode=self.browser.stealth_mode,
        )