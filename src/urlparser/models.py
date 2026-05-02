"""
统一数据模型

整合解析结果 + 转录结果 + 元数据
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


class PlatformType(Enum):
    """平台类型"""
    ZHIHU = "zhihu"
    BILIBILI = "bilibili"
    YOUTUBE = "youtube"
    WEIXIN = "weixin"
    XIAOHONGSHU = "xiaohongshu"
    GITHUB = "github"
    DRIBBBLE = "dribbble"
    GENERIC = "generic"
    UNKNOWN = "unknown"


class ContentType(Enum):
    """内容类型"""
    ARTICLE = "article"
    VIDEO = "video"
    WEBPAGE = "webpage"
    REPOSITORY = "repository"
    NOTE = "note"
    IDEA = "idea"
    UNKNOWN = "unknown"


@dataclass
class VideoMetadata:
    """视频元数据"""
    duration: str = ""
    views: str = ""
    likes: str = ""
    coins: str = ""
    favorites: str = ""
    tags: str = ""
    danmaku: str = ""
    subtitles: Optional[List[Dict]] = None

    def to_dict(self) -> Dict:
        return {
            'duration': self.duration,
            'views': self.views,
            'likes': self.likes,
            'coins': self.coins,
            'favorites': self.favorites,
            'tags': self.tags,
            'danmaku': self.danmaku,
            'subtitles': self.subtitles,
        }


@dataclass
class TranscriptionResult:
    """转录结果"""
    success: bool = False
    text: str = ""
    segments: List[Dict] = field(default_factory=list)
    language: str = ""
    duration: float = 0.0
    engine: str = ""
    error: Optional[str] = None

    @property
    def has_content(self) -> bool:
        return bool(self.text and len(self.text) > 10)

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'text': self.text,
            'segment_count': self.segment_count,
            'language': self.language,
            'duration': self.duration,
            'engine': self.engine,
            'error': self.error,
        }

    def to_markdown(self) -> str:
        """格式化为 Markdown"""
        if not self.success:
            return f"转录失败: {self.error or '未知错误'}"

        parts = [f"## 语音转录 ({self.engine})\n\n"]

        if self.text:
            parts.append(f"{self.text}\n")

        if self.segments:
            parts.append(f"\n### 时间戳分段 ({len(self.segments)} 段)\n\n")
            for i, seg in enumerate(self.segments[:50], 1):
                start = seg.get('start', 0)
                end = seg.get('end', 0)
                text = seg.get('text', '')
                h, m, s = int(start // 3600), int((start % 3600) // 60), int(start % 60)
                he, me, se = int(end // 3600), int((end % 3600) // 60), int(end % 60)
                parts.append(f"{i}. [{h:02d}:{m:02d}:{s:02d} - {he:02d}:{me:02d}:{se:02d}]\n{text}\n")

        return ''.join(parts)


@dataclass
class VisualFrameResult:
    """单帧 VLM 分析结果"""
    timestamp: float = 0.0          # 秒
    frame_path: str = ""            # 临时文件路径（已清理后为空）
    description: str = ""           # VLM 描述
    confidence: float = 1.0         # 置信度

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'description': self.description,
            'confidence': self.confidence,
        }


@dataclass
class ComprehensionResult:
    """视频理解结果"""
    success: bool = False
    mode: str = "audio_video"       # "audio_only" | "video_only" | "audio_video"
    visual_frames: List[VisualFrameResult] = field(default_factory=list)
    timeline_summary: str = ""
    merged_text: str = ""
    engine: str = ""
    frame_count: int = 0
    error: Optional[str] = None

    @property
    def has_content(self) -> bool:
        return bool(self.merged_text or self.timeline_summary)

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'mode': self.mode,
            'frame_count': self.frame_count,
            'engine': self.engine,
            'timeline_summary': self.timeline_summary,
            'merged_text': self.merged_text,
            'error': self.error,
        }

    def to_markdown(self) -> str:
        """格式化为 Markdown"""
        if not self.success:
            return f"视频理解失败: {self.error or '未知错误'}"

        parts = [f"## 视频理解 ({self.mode}, engine={self.engine})\n\n"]

        if self.merged_text:
            parts.append(f"{self.merged_text}\n\n")
        elif self.timeline_summary:
            parts.append(f"### 摘要\n\n{self.timeline_summary}\n\n")

        if self.visual_frames:
            parts.append(f"### 关键帧时间轴 ({self.frame_count} 帧)\n\n")
            for vf in self.visual_frames:
                h, m, s = int(vf.timestamp // 3600), int((vf.timestamp % 3600) // 60), int(vf.timestamp % 60)
                parts.append(f"- [{h:02d}:{m:02d}:{s:02d}] {vf.description}\n")

        return ''.join(parts)


@dataclass
class ArticleMetadata:
    """文章元数据"""
    votes: str = ""
    topic: str = ""
    likes: str = ""

    def to_dict(self) -> Dict:
        return {
            'votes': self.votes,
            'topic': self.topic,
            'likes': self.likes,
        }


@dataclass
class RetryAttempt:
    """单次重试记录"""
    strategy: str = ""
    success: bool = False
    access_restriction_reason: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'strategy': self.strategy,
            'success': self.success,
            'access_restriction_reason': self.access_restriction_reason,
            'error': self.error,
            'duration': self.duration,
        }


@dataclass
class ParseResult:
    """
    统一解析结果

    属性:
        url: 原始 URL
        platform: 检测到的平台
        title: 标题
        content: 正文内容（纯文本）
        raw_html: 原始 HTML（可选）
        author: 作者
        publish_date: 发布日期
        video_specific: 视频专用元数据
        article_specific: 文章专用元数据
        transcription: 语音转录结果（视频类）
        metadata: 其他元数据
        fetch_success: 是否成功
        error: 错误信息
        parse_time: 解析耗时（秒）
    """

    url: str = ""
    platform: str = ""
    platform_type: PlatformType = PlatformType.UNKNOWN
    content_type: ContentType = ContentType.UNKNOWN

    title: str = ""
    content: str = ""
    raw_text: str = ""
    author: str = ""
    publish_date: str = ""

    video_metadata: VideoMetadata = field(default_factory=VideoMetadata)
    article_metadata: ArticleMetadata = field(default_factory=ArticleMetadata)
    transcription: TranscriptionResult = field(default_factory=TranscriptionResult)
    comprehension: 'ComprehensionResult' = field(default_factory=ComprehensionResult)

    metadata: Dict[str, Any] = field(default_factory=dict)

    source_path: Optional[str] = None
    fetch_success: bool = False
    error: Optional[str] = None
    parse_time: float = 0.0

    retry_attempts: List[RetryAttempt] = field(default_factory=list)
    final_strategy: str = ""

    @property
    def is_video(self) -> bool:
        return self.content_type == ContentType.VIDEO

    @property
    def is_article(self) -> bool:
        return self.content_type in [ContentType.ARTICLE, ContentType.NOTE]

    @property
    def has_transcription(self) -> bool:
        return self.transcription is not None and self.transcription.success and bool(self.transcription.text and self.transcription.text.strip())

    @property
    def has_comprehension(self) -> bool:
        return self.comprehension is not None and self.comprehension.success

    @property
    def content_length(self) -> int:
        return len(self.content or '')

    @property
    def full_text(self) -> str:
        """获取完整文本（内容 + 转录 + 理解）"""
        parts = []
        if self.title:
            parts.append(f"# {self.title}\n")
        if self.content:
            parts.append(self.content)
        if self.has_transcription and self.transcription.text:
            parts.append(f"\n\n{self.transcription.to_markdown()}")
        if self.has_comprehension and self.comprehension.merged_text:
            parts.append(f"\n\n{self.comprehension.to_markdown()}")
        return '\n'.join(parts)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'url': self.url,
            'platform': self.platform,
            'platform_type': self.platform_type.value,
            'content_type': self.content_type.value,
            'title': self.title,
            'content_length': self.content_length,
            'author': self.author,
            'publish_date': self.publish_date,
            'is_video': self.is_video,
            'is_article': self.is_article,
            'has_transcription': self.has_transcription,
            'video_metadata': self.video_metadata.to_dict(),
            'transcription': self.transcription.to_dict(),
            'comprehension': self.comprehension.to_dict(),
            'metadata': self.metadata,
            'fetch_success': self.fetch_success,
            'error': self.error,
            'parse_time': self.parse_time,
            'final_strategy': self.final_strategy,
            'retry_attempts': [a.to_dict() for a in self.retry_attempts],
        }

    def to_markdown(self) -> str:
        """生成 Markdown 格式报告"""
        lines = []

        if self.title:
            lines.append(f"# {self.title}")
            lines.append("")

        lines.append(f"> **来源**: {self.url}")
        lines.append(f"> **平台**: {self.platform} | **类型**: {self.content_type.value}")
        if self.author:
            lines.append(f"> **作者**: {self.author}")
        if self.publish_date:
            lines.append(f"> **发布**: {self.publish_date}")
        if self.final_strategy:
            lines.append(f"> **解析策略**: {self.final_strategy}")
        if self.parse_time:
            lines.append(f"> **解析时间**: {self.parse_time}s")
        lines.append("")

        if self.is_video and self.video_metadata:
            vm = self.video_metadata
            lines.append("## 视频信息")
            if vm.duration:
                lines.append(f"- 时长: {vm.duration}")
            if vm.views:
                lines.append(f"- 播放: {vm.views}")
            if vm.likes:
                lines.append(f"- 点赞: {vm.likes}")
            if vm.coins:
                lines.append(f"- 投币: {vm.coins}")
            if vm.favorites:
                lines.append(f"- 收藏: {vm.favorites}")
            if vm.danmaku:
                lines.append(f"- 弹幕: {vm.danmaku}")
            if vm.tags:
                lines.append(f"- 标签: {vm.tags}")
            lines.append("")

        if self.content:
            lines.append("## 内容摘要")
            lines.append(self.content)
            lines.append("")

        if self.has_transcription:
            tr = self.transcription
            lines.append("## 语音转录")
            lines.append(f"> 引擎: {tr.engine} | 时长: {tr.duration:.1f}s | 语言: {tr.language}")
            lines.append("")
            if tr.text:
                lines.append(tr.text)
            has_valid_segments = tr.segments and any(
                seg.get('text', '').strip() for seg in tr.segments
            )
            if has_valid_segments:
                lines.append(f"\n### 时间戳分段 ({tr.segment_count} 段)\n")
                for i, seg in enumerate(tr.segments[:50], 1):
                    start = seg.get('start', 0)
                    end = seg.get('end', 0)
                    text = seg.get('text', '')
                    h, m, s = int(start // 3600), int((start % 3600) // 60), int(start % 60)
                    he, me, se = int(end // 3600), int((end % 3600) // 60), int(end % 60)
                    lines.append(f"{i}. [{h:02d}:{m:02d}:{s:02d} - {he:02d}:{me:02d}:{se:02d}] {text}")
            lines.append("")

        if self.has_comprehension:
            lines.append(self.comprehension.to_markdown())

        if self.retry_attempts:
            lines.append("## 重试记录")
            for i, attempt in enumerate(self.retry_attempts, 1):
                status = "成功" if attempt.success else "失败"
                line = f"{i}. **{attempt.strategy}** → {status}"
                if attempt.access_restriction_reason:
                    line += f" ({attempt.access_restriction_reason})"
                if attempt.error:
                    line += f" | 错误: {attempt.error}"
                line += f" ({attempt.duration:.1f}s)"
                lines.append(line)
            lines.append("")

        if self.error:
            lines.append("## 错误信息")
            lines.append(self.error)
            lines.append("")

        return '\n'.join(lines)


def create_result_from_parser(parser_result) -> ParseResult:
    """从 parsers 模块的 ParseResult 转换"""
    from .models import PlatformType as PT, ContentType as CT

    platform_map = {
        'zhihu': PT.ZHIHU, 'bilibili': PT.BILIBILI, 'youtube': PT.YOUTUBE,
        'weixin': PT.WEIXIN, 'xiaohongshu': PT.XIAOHONGSHU, 'github': PT.GITHUB,
        'default': PT.GENERIC, 'generic': PT.GENERIC,
    }

    content_type_map = {
        'article': CT.ARTICLE, 'articles': CT.ARTICLE,
        'video': CT.VIDEO, 'videos': CT.VIDEO,
        'webpage': CT.WEBPAGE, 'webpages': CT.WEBPAGE,
        'note': CT.NOTE, 'notes': CT.NOTE,
        'idea': CT.IDEA, 'ideas': CT.IDEA,
        'repository': CT.REPOSITORY,
    }

    pt = platform_map.get(getattr(parser_result, 'platform', ''), PT.UNKNOWN)
    ct = content_type_map.get(getattr(parser_result, 'content_type', '').value if hasattr(parser_result.content_type, 'value') else '', CT.UNKNOWN)

    result = ParseResult(
        url=getattr(parser_result, 'url', ''),
        platform=getattr(parser_result, 'platform', ''),
        platform_type=pt,
        content_type=ct,
        title=getattr(parser_result, 'title', '') or '',
        content=getattr(parser_result, 'content', '') or '',
        raw_text=getattr(parser_result, 'raw_text', '') or '',
        author=getattr(parser_result, 'author', '') or '',
        publish_date=getattr(parser_result, 'publish_date', '') or '',
        metadata=dict(getattr(parser_result, 'metadata', {}) or {}),
        fetch_success=getattr(parser_result, 'fetch_success', False),
        error=getattr(parser_result, 'error', None),
    )

    vs = getattr(parser_result, 'video_specific', {}) or {}
    if vs:
        result.video_metadata = VideoMetadata(
            duration=vs.get('duration', ''),
            views=vs.get('views', ''),
            likes=vs.get('likes', ''),
            coins=vs.get('coins', ''),
            favorites=vs.get('favorites', ''),
            tags=vs.get('tags', ''),
            subtitles=vs.get('subtitles'),
        )

        if vs.get('has_subtitles') and vs.get('subtitles'):
            subtitle_text = "\n".join(
                s.get('text', '') for s in vs['subtitles'] if s.get('text')
            )
            valid_segments = [s for s in vs['subtitles'] if s.get('entries')]
            duration = vs.get('duration_seconds', 0.0)
            if subtitle_text.strip() or valid_segments:
                result.transcription = TranscriptionResult(
                    success=True,
                    text=subtitle_text,
                    duration=float(duration) if duration else 0.0,
                    engine="subtitle",
                    segments=vs['subtitles'],
                )

        if vs.get('needs_transcription'):
            result.metadata['needs_transcription'] = True

    return result