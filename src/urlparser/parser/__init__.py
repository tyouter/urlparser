"""
内容解析层

提供平台自动识别和内容提取能力
"""

from .base import BaseParser, VideoParser, ArticleParser
from .models import ParseResult, ParserConfig, PlatformType, ContentType, VideoInfo, ArticleInfo
from .factory import ParserFactory, ParserRegistry
from .platforms import (
    ZhihuParser,
    XiaohongshuParser,
    BilibiliParser,
    YoutubeParser,
    WeixinParser,
    GithubParser,
    GenericParser,
)

__all__ = [
    'BaseParser',
    'VideoParser',
    'ArticleParser',
    'ParseResult',
    'ParserConfig',
    'PlatformType',
    'ContentType',
    'VideoInfo',
    'ArticleInfo',
    'ParserFactory',
    'ParserRegistry',
    'ZhihuParser',
    'XiaohongshuParser',
    'BilibiliParser',
    'YoutubeParser',
    'WeixinParser',
    'GithubParser',
    'GenericParser',
]