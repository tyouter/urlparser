"""
urlparser - 通用 URL 资源解析器

一个输入，自动识别平台、提取内容、可选转录音频。

核心接口:
    from urlparser import parse

    result = await parse("https://www.bilibili.com/video/BVxxx")
    print(result.title, result.content, result.transcription)

支持平台:
    - 知乎 (zhihu.com)       文章/问答/想法
    - B站  (bilibili.com)    视频 + 音频转录
    - 微信 (weixin.qq.com)   公众号文章
    - 小红书 (xiaohongshu)   笔记/图文
    - YouTube (youtube.com)  视频 + 字幕
    - GitHub (github.com)    仓库/README
    - 通用网页               自动提取主要内容

模块结构:
    urlparser/
    ├── core.py          统一入口 (UrlParser, parse, parse_batch)
    ├── config.py        配置 (ParseConfig, BatchTranscribeConfig)
    ├── models.py        数据模型 (ParseResult, PlatformType, ContentType)
    ├── cli.py           CLI 接口
    ├── fetcher/         URL 读取层 (Playwright, Cookie, UserChrome, BrowserUse)
    ├── parser/          内容解析层 (平台解析器 + 工厂 + Mixins)
    ├── transcriber/     音视频转录层 (FunASR, Whisper, yt-dlp)
    ├── batch_transcriber/ 批量转录层 (BatchTranscriber, MediaScanner, SegmentHandler)
    ├── storage/         存储层 (缓存, 文件存储, 源文档, 状态管理)
    └── utils/           工具集 (URL处理, 文本清洗, 文件操作, 音视频工具)

使用方式:

    # 最简用法 - 一行代码
    result = await parse("https://www.zhihu.com/question/xxx")

    # 带配置
    result = await parse(url, enable_transcribe=True, cookies_file="cookies.json")

    # 批量解析
    results = await parse_batch(["url1", "url2", "url3"])

    # 同步包装（在已有事件循环中使用）
    import asyncio
    result = asyncio.run(parse("https://..."))

    # CLI
    python -m urlparser parse https://www.zhihu.com/question/xxx
    python -m urlparser parse-batch urls.txt --transcribe
    python -m urlparser cache stats
    python -m urlparser status validate
"""

# =============================================================================
# Logging setup - prevent "No handler found" warnings in library mode
# =============================================================================
import logging

logging.getLogger('urlparser').addHandler(logging.NullHandler())

# =============================================================================
# CRITICAL: Set cache directories BEFORE any imports to prevent re-downloading
# =============================================================================
import os
from pathlib import Path

_env_initialized = False

def _ensure_env():
    """Set cache directories lazily, only once."""
    global _env_initialized
    if _env_initialized:
        return
    _env_initialized = True

    # ModelScope cache for FunASR models
    _modelscope_cache = Path.home() / '.cache' / 'modelscope'
    _modelscope_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MODELSCOPE_CACHE', str(_modelscope_cache))

    # HuggingFace cache for Whisper models
    _hf_cache = Path.home() / '.cache' / 'huggingface'
    _hf_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('HF_HOME', str(_hf_cache))
    os.environ.setdefault('HUGGINGFACE_HUB_CACHE', str(_hf_cache / 'hub'))

    # OpenMP workaround for Windows
    os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')

_ensure_env()
# =============================================================================
# End of cache setup - now imports can proceed
# =============================================================================

from .core import parse, parse_batch, parse_sync, UrlParser
from .config import ParseConfig, BrowserConfig, ScrollConfig, TranscribeConfig, ComprehensionConfig, ImageDownloadConfig, RetryConfig
from .models import (
    ParseResult, PlatformType, ContentType,
    VideoMetadata, TranscriptionResult, ArticleMetadata,
    ComprehensionResult, VisualFrameResult, RetryAttempt,
)
from .utils import (
    URLNormalizer, normalize_url, hash_url, detect_platform, is_video_url,
    clean_text, remove_duplicate_lines, extract_main_content,
    ensure_dir, safe_filename, read_json, write_json, read_text, write_text,
    is_audio_file, is_video_file, is_media_file, get_media_duration,
    format_duration, format_duration_detailed, file_size_str, list_files,
)

# 图片下载模块
try:
    from .image_downloader import ImageDownloader
except ImportError:
    pass

# Optional imports - these may fail if optional dependencies are not installed
try:
    from .fetcher import (
        BaseFetcher, FetchResult, FetchConfig, FetchStrategy,
        PlaywrightFetcher, CookieFetcher, UserChromeFetcher, BrowserUseFetcher,
        ScraplingFetcher,
        FetcherFactory,
    )
except ImportError:
    pass

try:
    from .parser import (
        BaseParser, VideoParser, ArticleParser,
        ParseResult as ParserParseResult,
        ParserConfig, ParserFactory, ParserRegistry,
        ZhihuParser, XiaohongshuParser, BilibiliParser, YoutubeParser,
        WeixinParser, GithubParser, GenericParser,
    )
    from .parser.mixins.content_quality import ContentQualityMixin
except ImportError:
    pass

try:
    from .transcriber import (
        BaseTranscriber, TranscriptionResult as TranscriberResult,
        FunASRTranscriber, WhisperTranscriber,
        YtdlpExtractor, extract_video_info,
        OnlineVideoFetcher, fetch_video_online,
    )
except ImportError:
    pass

try:
    from .storage import (
        ResultCache, CacheEntry, ResultStorage,
        SourceDocumentManager, StateManager, ProcessStatus, ResourceState,
    )
except ImportError:
    pass

try:
    from .batch_transcriber import (
        BatchTranscriber, BatchTranscribeConfig, BatchResult, FileResult,
        MediaScanner, MediaFileInfo, ScanResult,
        SegmentHandler, SegmentationConfig,
        TranscriptionWriter, WriterConfig,
    )
except ImportError:
    pass

try:
    from .dependency_installer import (
        ensure_dependency, ensure_all_dependencies,
        ensure_transcribe_dependencies, ensure_core_dependencies,
        ensure_comprehension_dependencies, ensure_image_dependencies,
        is_package_installed, is_ffmpeg_installed,
    )
except ImportError:
    pass

__all__ = [
    'parse',
    'parse_batch',
    'parse_sync',
    'UrlParser',

    'ParseConfig',
    'BrowserConfig',
    'ScrollConfig',
    'TranscribeConfig',
    'BatchTranscribeConfig',
    'ComprehensionConfig',
    'ImageDownloadConfig',
    'RetryConfig',

    'ParseResult',
    'PlatformType',
    'ContentType',
    'VideoMetadata',
    'TranscriptionResult',
    'ArticleMetadata',
    'ComprehensionResult',
    'VisualFrameResult',
    'RetryAttempt',

    'ImageDownloader',

    'BaseFetcher',
    'FetchResult',
    'FetchConfig',
    'FetchStrategy',
    'PlaywrightFetcher',
    'CookieFetcher',
    'UserChromeFetcher',
    'ScraplingFetcher',
    'BrowserUseFetcher',
    'FetcherFactory',

    'BaseParser',
    'VideoParser',
    'ArticleParser',
    'ParserFactory',
    'ParserRegistry',
    'ZhihuParser',
    'XiaohongshuParser',
    'BilibiliParser',
    'YoutubeParser',
    'WeixinParser',
    'GithubParser',
    'GenericParser',
    'ContentQualityMixin',

    'BaseTranscriber',
    'FunASRTranscriber',
    'WhisperTranscriber',
    'YtdlpExtractor',
    'extract_video_info',
    'OnlineVideoFetcher',
    'fetch_video_online',

    'ResultCache',
    'CacheEntry',
    'ResultStorage',
    'SourceDocumentManager',
    'StateManager',
    'ProcessStatus',
    'ResourceState',

    # Batch transcriber
    'BatchTranscriber',
    'BatchResult',
    'FileResult',
    'MediaScanner',
    'MediaFileInfo',
    'ScanResult',
    'SegmentHandler',
    'SegmentationConfig',
    'TranscriptionWriter',
    'WriterConfig',

    'URLNormalizer',
    'normalize_url',
    'hash_url',
    'detect_platform',
    'is_video_url',
    'clean_text',
    'remove_duplicate_lines',
    'extract_main_content',
    'ensure_dir',
    'safe_filename',
    'read_json',
    'write_json',
    'read_text',
    'write_text',

    # Media utilities
    'is_audio_file',
    'is_video_file',
    'is_media_file',
    'get_media_duration',
    'format_duration',
    'format_duration_detailed',
    'file_size_str',
    'list_files',

    # Dependency installer
    'ensure_dependency',
    'ensure_all_dependencies',
    'ensure_transcribe_dependencies',
    'ensure_core_dependencies',
    'ensure_comprehension_dependencies',
    'ensure_image_dependencies',
    'is_package_installed',
    'is_ffmpeg_installed',
]
__version__ = '3.3.1'