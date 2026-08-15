"""
统一配置

整合解析器配置 + 转录配置 + 浏览器配置 + 批量转录配置
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List
from pathlib import Path


@dataclass
class ImageDownloadConfig:
    """图片下载配置"""
    enabled: bool = False
    mode: str = "local"  # "local" | "base64"
    image_dir: Optional[str] = None  # 图片保存目录
    image_prefix: str = "images/"  # Markdown 中图片路径的前缀
    max_size: int = 10  # 最大图片大小(MB)
    timeout: int = 30  # 下载超时(秒)
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@dataclass
class BrowserConfig:
    """浏览器配置"""
    use_user_chrome: bool = False
    user_data_dir: Optional[str] = None
    cookies_file: Optional[str] = None
    headless: bool = True
    timeout: int = 30000
    compatibility_mode: bool = True
    cookie_max_age_hours: int = 168        # cookie 有效期（小时），超过视为过期
    cookie_auto_refresh: bool = True       # 过期时是否自动从持久 profile 刷新


@dataclass
class ScrollConfig:
    """滚动配置"""
    enabled: bool = True
    max_scrolls: int = 40
    scroll_delay: float = 2.0


@dataclass
class TranscribeConfig:
    """音频转录配置"""
    enabled: bool = False
    model_size: str = "large"
    device: str = "auto"
    language: str = "zh"


@dataclass
class ComprehensionConfig:
    """视频理解配置"""
    enabled: bool = False
    mode: str = "audio_video"       # "audio_only" | "video_only" | "audio_video"
    engine: str = "auto"            # "auto" | "openvino" | "llamacpp"
    max_frames: int = 50
    scdet_threshold: int = 10
    language: str = "zh"
    temp_dir: Optional[str] = None


@dataclass
class RetryConfig:
    """多策略回退重试配置"""
    enabled: bool = True
    max_attempts: int = 4           # 最多重试次数
    timeout_per_attempt: int = 30   # 每次重试超时(秒)
    total_timeout: int = 120        # 所有重试总超时(秒)
    min_quality_length: int = 100   # 最低内容长度


@dataclass
class ParseConfig:
    """
    统一解析配置

    使用方式:
        config = ParseConfig(
            enable_transcribe=True,
            cookies_file="cookies/zhihu_cookies.json",
        )

        result = await parse(url, config=config)
    """

    browser: BrowserConfig = field(default_factory=BrowserConfig)
    scroll: ScrollConfig = field(default_factory=ScrollConfig)
    transcribe: TranscribeConfig = field(default_factory=TranscribeConfig)
    comprehension: ComprehensionConfig = field(default_factory=ComprehensionConfig)
    on_progress: Optional[Callable] = None  # Callable[[ProgressEvent], None]
    image_download: ImageDownloadConfig = field(default_factory=ImageDownloadConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)

    load_full_content: bool = True
    dismiss_popups: bool = True
    parse_mode: str = "local"  # "local" | "online"

    @classmethod
    def simple(cls, **kwargs):
        """快速创建简单配置"""
        return cls(**kwargs)

    @classmethod
    def with_transcribe(cls, **kwargs) -> 'ParseConfig':
        """启用转录的配置"""
        transcribe = TranscribeConfig(enabled=True)
        return cls(transcribe=transcribe, **kwargs)

    @classmethod
    def with_cookies(cls, cookies_file: str, **kwargs):
        """使用 Cookie 的配置"""
        browser = BrowserConfig(cookies_file=cookies_file)
        return cls(browser=browser, **kwargs)

    @classmethod
    def with_online_parse(cls, **kwargs):
        """使用在线 LLM 解析的配置"""
        return cls(parse_mode="online", **kwargs)

    @classmethod
    def with_comprehension(cls, mode: str = "audio_video", engine: str = "auto", **kwargs):
        """启用视频理解"""
        comprehension = ComprehensionConfig(enabled=True, mode=mode, engine=engine)
        return cls(comprehension=comprehension, **kwargs)

    @classmethod
    def with_image_download(cls, mode: str = "local", image_dir: Optional[str] = None, **kwargs):
        """启用图片下载"""
        image_download = ImageDownloadConfig(enabled=True, mode=mode, image_dir=image_dir)
        return cls(image_download=image_download, **kwargs)

    @classmethod
    def full_feature(cls, **kwargs):
        """全功能配置（滚动+展开+弹窗关闭+转录）"""
        return cls(
            browser=BrowserConfig(
                headless=False,
                compatibility_mode=True,
            ),
            scroll=ScrollConfig(enabled=True, max_scrolls=40),
            load_full_content=True,
            dismiss_popups=True,
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
            load_full_content=self.load_full_content,
            dismiss_popups=self.dismiss_popups,
            compatibility_mode=self.browser.compatibility_mode,
            parse_mode=self.parse_mode,
        )

    def to_fetch_config(self):
        """转换为 fetcher 模块的 FetchConfig"""
        from .fetcher.base import FetchConfig

        return FetchConfig(
            timeout=self.browser.timeout,
            headless=self.browser.headless,
            compatibility_mode=self.browser.compatibility_mode,
            scroll_enabled=self.scroll.enabled,
            max_scrolls=self.scroll.max_scrolls,
            scroll_delay=self.scroll.scroll_delay,
            load_full_content=self.load_full_content,
            dismiss_popups=self.dismiss_popups,
            cookies_file=self.browser.cookies_file,
            user_data_dir=self.browser.user_data_dir,
        )


# 批量转录配置（从 batch_transcriber 模块导入）
# 用户可以直接从 config 模块访问
from .batch_transcriber.processor import BatchTranscribeConfig


@dataclass
class ParseOptions:
    """单次解析的运行时选项（v4：快路径/预算/策略控制，修复 C1/C2/C3）

    mode: "full"=正文+转录+理解 | "content"=正文 | "metadata"=仅元数据（不渲染不转录）
    strategy: None=auto 降级链 | "http"|"cffi"|"playwright"|"bb"|"cookie"|"user_chrome"|"browser_use"
    budget_ms: 总时间预算（毫秒），0=不限；超时返回 E_BUDGET_EXCEEDED
    """

    mode: str = "full"
    strategy: Optional[str] = None
    budget_ms: int = 0


def apply_fields(data: Dict[str, Any], fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """输出字段裁剪（v4 --fields）：始终保留 schema_version 与 url"""
    if not fields:
        return data
    keep = set(fields) | {"schema_version", "url"}
    return {k: v for k, v in data.items() if k in keep}


def load_user_config(path: Optional[str] = None) -> Dict[str, Any]:
    """读取 ~/.urlparser/config.toml（tomllib，Python 3.11+）；失败返回 {}"""
    import os as _os

    p = Path(path) if path else Path(_os.path.expanduser("~/.urlparser/config.toml"))
    if not p.exists():
        return {}
    try:
        import tomllib
        with open(p, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def get_profile(data: Dict[str, Any], name: Optional[str]) -> Dict[str, Any]:
    """从配置取 profile（[profiles.<name>]）"""
    if not name or not data:
        return {}
    return dict((data.get("profiles") or {}).get(name) or {})

__all__ = [
    'BrowserConfig',
    'ScrollConfig',
    'TranscribeConfig',
    'ComprehensionConfig',
    'ImageDownloadConfig',
    'RetryConfig',
    'ParseConfig',
    'BatchTranscribeConfig',
    'ParseOptions',
    'apply_fields',
    'load_user_config',
    'get_profile',
]