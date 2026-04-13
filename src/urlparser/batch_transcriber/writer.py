"""
转录结果写入器

生成 Markdown 格式的转录文件
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from ..transcriber.base import TranscriptionResult
from ..utils import format_duration, format_duration_detailed, is_video_file


@dataclass
class WriterConfig:
    """写入器配置"""
    include_metadata: bool = True
    include_timestamps: bool = True
    include_segments: bool = True
    max_segments_display: int = 100  # 显示的最大分段数
    add_source_link: bool = True


class TranscriptionWriter:
    """转录结果写入器"""

    def __init__(self, config: Optional[WriterConfig] = None, output_dir: Optional[Path] = None):
        self.config = config or WriterConfig()
        self.output_dir = output_dir  # 指定的输出目录

    def write(
        self,
        media_path: Path,
        result: TranscriptionResult,
        metadata: Optional[Dict[str, Any]] = None,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        写入转录结果到 MD 文件

        Args:
            media_path: 原始音视频文件路径
            result: 转录结果
            metadata: 额外元数据
            output_path: 指定的输出路径（可选）

        Returns:
            生成的 MD 文件路径
        """
        # 确定输出路径
        if output_path:
            md_path = output_path
        elif self.output_dir:
            # 使用指定的输出目录
            md_path = self.output_dir / (media_path.stem + '.md')
        else:
            # 默认保存到媒体文件同目录
            md_path = media_path.with_suffix('.md')

        content = self._generate_content(media_path, result, metadata)

        md_path.write_text(content, encoding='utf-8')
        return md_path

    def _generate_content(
        self,
        media_path: Path,
        result: TranscriptionResult,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成 Markdown 内容

        Args:
            media_path: 原始文件路径
            result: 转录结果
            metadata: 额外元数据

        Returns:
            Markdown 内容
        """
        lines = []

        # 标题
        title = self._generate_title(media_path, metadata)
        lines.append(f"# {title}")
        lines.append("")

        # 元数据
        if self.config.include_metadata:
            lines.append(self._generate_metadata_section(media_path, result, metadata))
            lines.append("")

        # 转录状态
        if not result.success:
            lines.append("## 转录状态")
            lines.append("")
            lines.append(f"**状态**: 失败")
            lines.append(f"**错误**: {result.error or '未知错误'}")
            lines.append("")
            return "\n".join(lines)

        # 转录正文
        lines.append("## 转录正文")
        lines.append("")
        if result.text:
            lines.append(result.text)
        else:
            lines.append("（无转录内容）")
        lines.append("")

        # 时间戳分段
        if self.config.include_segments and result.segments:
            lines.append(self._generate_segments_section(result))
            lines.append("")

        # 尾部信息
        lines.append("---")
        lines.append("")
        lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append(f"*转录引擎: {result.engine}*")

        return "\n".join(lines)

    def _generate_title(
        self,
        media_path: Path,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """生成标题"""
        if metadata and metadata.get('title'):
            return metadata['title']

        # 从文件名生成标题
        filename = media_path.stem
        # 去除常见前缀和后缀
        title = filename.replace('_', ' ').replace('-', ' ')
        return f"{title} 转录"

    def _generate_metadata_section(
        self,
        media_path: Path,
        result: TranscriptionResult,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """生成元数据部分"""
        lines = []
        lines.append("## 文件信息")
        lines.append("")

        # 文件基本信息
        is_video = is_video_file(str(media_path))
        type_str = "视频" if is_video else "音频"
        lines.append(f"- **类型**: {type_str}")
        lines.append(f"- **文件名**: {media_path.name}")

        # 文件大小
        try:
            size_bytes = media_path.stat().st_size
            from ..utils import file_size_str
            lines.append(f"- **大小**: {file_size_str(size_bytes)}")
        except Exception:
            pass

        # 时长
        if result.duration > 0:
            lines.append(f"- **时长**: {format_duration_detailed(result.duration)}")

        # 语言
        if result.language:
            lines.append(f"- **语言**: {result.language}")

        # 额外元数据
        if metadata:
            if metadata.get('author'):
                lines.append(f"- **作者**: {metadata['author']}")
            if metadata.get('publish_date'):
                lines.append(f"- **发布日期**: {metadata['publish_date']}")
            if metadata.get('source_url'):
                lines.append(f"- **来源**: {metadata['source_url']}")

        # 源文件链接
        if self.config.add_source_link:
            lines.append("")
            lines.append(f"**源文件**: `{media_path.name}`")

        return "\n".join(lines)

    def _generate_segments_section(self, result: TranscriptionResult) -> str:
        """生成时间戳分段部分"""
        lines = []
        lines.append(f"## 时间戳分段 ({len(result.segments)} 段)")
        lines.append("")

        # 限制显示数量
        segments = result.segments[:self.config.max_segments_display]

        for i, seg in enumerate(segments, 1):
            start = seg.get('start', 0)
            end = seg.get('end', 0)
            text = seg.get('text', '').strip()

            if text:
                time_str = self._format_segment_time(start, end)
                lines.append(f"**[{time_str}]** {text}")
                lines.append("")

        if len(result.segments) > self.config.max_segments_display:
            hidden_count = len(result.segments) - self.config.max_segments_display
            lines.append(f"*... 还有 {hidden_count} 个分段未显示*")
            lines.append("")

        return "\n".join(lines)

    def _format_segment_time(self, start: float, end: float) -> str:
        """格式化分段时间"""
        def format_time(seconds: float) -> str:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)

            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{secs:02d}"
            else:
                return f"{minutes:02d}:{secs:02d}"

        return f"{format_time(start)} - {format_time(end)}"

    def update_existing(
        self,
        md_path: Path,
        result: TranscriptionResult,
        preserve_original: bool = True
    ) -> bool:
        """
        更新现有 MD 文件

        Args:
            md_path: MD 文件路径
            result: 新的转录结果
            preserve_original: 是否保留原有内容

        Returns:
            是否成功更新
        """
        if not md_path.exists():
            return False

        try:
            original_content = md_path.read_text(encoding='utf-8')

            if preserve_original:
                # 在原有内容后追加新的转录结果
                new_section = "\n\n---\n\n## 更新的转录结果\n\n"
                new_section += f"*更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"

                if result.success and result.text:
                    new_section += result.text
                else:
                    new_section += f"转录失败: {result.error or '未知错误'}"

                md_path.write_text(original_content + new_section, encoding='utf-8')
            else:
                # 完全替换
                media_path = md_path.with_suffix('')
                # 尝试找到原始媒体文件
                for ext in ['.mp3', '.mp4', '.wav', '.mkv', '.avi', '.m4a', '.flac']:
                    potential_media = md_path.with_suffix(ext)
                    if potential_media.exists():
                        media_path = potential_media
                        break

                content = self._generate_content(media_path, result)
                md_path.write_text(content, encoding='utf-8')

            return True

        except Exception:
            return False


def generate_simple_md(
    media_path: Path,
    result: TranscriptionResult,
    include_timestamps: bool = True
) -> str:
    """
    生成简单格式的 MD 内容

    Args:
        media_path: 媒体文件路径
        result: 转录结果
        include_timestamps: 是否包含时间戳

    Returns:
        MD 内容
    """
    lines = []

    # 标题
    lines.append(f"# {media_path.stem}")
    lines.append("")
    lines.append(f"文件: `{media_path.name}`")
    lines.append(f"引擎: {result.engine}")
    lines.append(f"时长: {format_duration(result.duration)}")
    lines.append("")

    if not result.success:
        lines.append(f"转录失败: {result.error}")
        return "\n".join(lines)

    # 正文
    lines.append("## 转录内容")
    lines.append("")
    lines.append(result.text)
    lines.append("")

    # 时间戳
    if include_timestamps and result.segments:
        lines.append("## 时间戳")
        lines.append("")
        for seg in result.segments[:50]:
            start = seg.get('start', 0)
            text = seg.get('text', '').strip()
            if text:
                minutes = int(start // 60)
                seconds = int(start % 60)
                lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")

    return "\n".join(lines)