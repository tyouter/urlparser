"""
Parser 内部数据模型

注意: ParseResult 和 ContentType 在此模块中是 parser 子系统内部使用的简化版本。
规范定义在 urlparser.models 中，通过 create_result_from_parser() 转换。
长期计划：将 parser 层迁移到直接使用 urlparser.models.ParseResult。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from ..models import PlatformType, ContentType

# Alias for cross-reference
from ..models import ParseResult as CanonicalParseResult


@dataclass
class ParserConfig:
    use_user_chrome: bool = False
    user_data_dir: Optional[str] = None
    cookies_file: Optional[str] = None
    timeout: int = 30000
    headless: bool = True
    scroll_enabled: bool = True
    max_scrolls: int = 40
    scroll_delay: float = 2.0
    load_full_content: bool = True
    dismiss_popups: bool = True
    compatibility_mode: bool = True
    parse_mode: str = "local"  # "local" | "online"

    def to_dict(self) -> Dict:
        return {
            'use_user_chrome': self.use_user_chrome,
            'user_data_dir': self.user_data_dir,
            'cookies_file': self.cookies_file,
            'timeout': self.timeout,
            'headless': self.headless,
            'scroll_enabled': self.scroll_enabled,
            'max_scrolls': self.max_scrolls,
            'scroll_delay': self.scroll_delay,
            'load_full_content': self.load_full_content,
            'dismiss_popups': self.dismiss_popups,
            'compatibility_mode': self.compatibility_mode,
            'parse_mode': self.parse_mode,
        }


@dataclass
class ParseResult:
    url: str = ""
    platform: str = ""
    title: str = ""
    content: str = ""
    raw_text: str = ""
    author: str = ""
    publish_date: str = ""

    video_specific: Dict[str, Any] = field(default_factory=dict)
    article_specific: Dict[str, Any] = field(default_factory=dict)

    metadata: Dict[str, Any] = field(default_factory=dict)
    source_path: Optional[str] = None
    fetch_success: bool = False
    error: Optional[str] = None
    has_transcription: bool = False

    @property
    def is_video(self) -> bool:
        return self.platform in ['bilibili', 'youtube']

    @property
    def is_article(self) -> bool:
        return self.platform in ['zhihu', 'weixin']

    @property
    def content_type(self) -> ContentType:
        if self.is_video:
            return ContentType.VIDEO
        elif self.is_article:
            return ContentType.ARTICLE
        else:
            return ContentType.WEBPAGE

    @property
    def content_length(self) -> int:
        return len(self.content) + len(self.raw_text)

    def to_dict(self) -> Dict:
        return {
            'url': self.url,
            'platform': self.platform,
            'title': self.title,
            'content': self.content,
            'raw_text': self.raw_text,
            'author': self.author,
            'publish_date': self.publish_date,
            'video_specific': self.video_specific,
            'article_specific': self.article_specific,
            'metadata': self.metadata,
            'source_path': self.source_path,
            'fetch_success': self.fetch_success,
            'error': self.error
        }


@dataclass
class VideoInfo:
    duration: str = ""
    views: str = ""
    likes: str = ""
    coins: str = ""
    favorites: str = ""
    tags: str = ""
    description: str = ""
    subtitles: List[Dict] = field(default_factory=list)
    transcription: str = ""
    transcription_method: str = ""


@dataclass
class ArticleInfo:
    votes: str = ""
    comments: str = ""
    category: str = ""
    reading_count: str = ""