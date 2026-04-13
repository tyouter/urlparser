"""
文件扫描器

扫描目录中的音视频文件，收集文件信息
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..utils import is_audio_file, is_video_file, get_media_duration, file_size_str


@dataclass
class MediaFileInfo:
    """音视频文件信息"""
    path: Path
    size_bytes: int
    duration_seconds: float
    is_video: bool
    existing_md: Optional[Path] = None
    error: Optional[str] = None

    @property
    def size_str(self) -> str:
        """文件大小字符串"""
        return file_size_str(self.size_bytes)

    @property
    def duration_str(self) -> str:
        """时长字符串"""
        from ..utils.media_utils import format_duration
        return format_duration(self.duration_seconds)

    @property
    def filename(self) -> str:
        """文件名"""
        return self.path.name

    @property
    def extension(self) -> str:
        """扩展名"""
        return self.path.suffix.lower()

    @property
    def has_existing_md(self) -> bool:
        """是否已有转录文件"""
        return self.existing_md is not None and self.existing_md.exists()

    @property
    def md_path(self) -> Path:
        """预期的 MD 文件路径"""
        return self.path.with_suffix('.md')

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'path': str(self.path),
            'filename': self.filename,
            'size_bytes': self.size_bytes,
            'size_str': self.size_str,
            'duration_seconds': self.duration_seconds,
            'duration_str': self.duration_str,
            'is_video': self.is_video,
            'extension': self.extension,
            'existing_md': str(self.existing_md) if self.existing_md else None,
            'has_existing_md': self.has_existing_md,
            'error': self.error,
        }


@dataclass
class ScanResult:
    """扫描结果"""
    files: List[MediaFileInfo] = field(default_factory=list)
    total_count: int = 0
    audio_count: int = 0
    video_count: int = 0
    total_size_bytes: int = 0
    total_duration_seconds: float = 0.0
    existing_md_count: int = 0
    error_count: int = 0

    @property
    def total_size_str(self) -> str:
        """总大小字符串"""
        return file_size_str(self.total_size_bytes)

    @property
    def total_duration_str(self) -> str:
        """总时长字符串"""
        from ..utils.media_utils import format_duration_detailed
        return format_duration_detailed(self.total_duration_seconds)

    @property
    def pending_count(self) -> int:
        """待处理数量"""
        return self.total_count - self.existing_md_count

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_count': self.total_count,
            'audio_count': self.audio_count,
            'video_count': self.video_count,
            'total_size_bytes': self.total_size_bytes,
            'total_size_str': self.total_size_str,
            'total_duration_seconds': self.total_duration_seconds,
            'total_duration_str': self.total_duration_str,
            'existing_md_count': self.existing_md_count,
            'pending_count': self.pending_count,
            'error_count': self.error_count,
        }


class MediaScanner:
    """音视频文件扫描器"""

    def __init__(self, timeout_per_file: float = 30.0):
        """
        Args:
            timeout_per_file: 每个文件获取元数据的超时时间（秒）
        """
        self.timeout_per_file = timeout_per_file

    def scan_directory(self, directory: str, recursive: bool = True) -> ScanResult:
        """
        扫描目录中的音视频文件

        Args:
            directory: 目录路径
            recursive: 是否递归扫描子目录

        Returns:
            ScanResult 扫描结果
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            return ScanResult(error_count=1)

        if not dir_path.is_dir():
            return ScanResult(error_count=1)

        # 收集所有文件
        if recursive:
            all_files = list(dir_path.rglob('*'))
        else:
            all_files = list(dir_path.glob('*'))

        # 过滤音视频文件
        media_files = []
        for f in all_files:
            if f.is_file() and (is_audio_file(str(f)) or is_video_file(str(f))):
                media_files.append(f)

        # 分析每个文件
        file_infos = []
        result = ScanResult()

        for media_path in media_files:
            info = self._analyze_file(media_path)
            file_infos.append(info)

            result.total_count += 1
            result.total_size_bytes += info.size_bytes
            result.total_duration_seconds += info.duration_seconds

            if info.is_video:
                result.video_count += 1
            else:
                result.audio_count += 1

            if info.has_existing_md:
                result.existing_md_count += 1

            if info.error:
                result.error_count += 1

        result.files = file_infos
        return result

    def _analyze_file(self, path: Path) -> MediaFileInfo:
        """分析单个文件"""
        is_video = is_video_file(str(path))
        size_bytes = path.stat().st_size if path.exists() else 0

        # 检查已有转录文件
        md_path = path.with_suffix('.md')
        existing_md = md_path if md_path.exists() else None

        # 获取时长
        duration = get_media_duration(str(path))
        error = None

        if duration <= 0:
            # 如果无法获取时长，尝试估算
            # 对于大文件，这可能意味着 ffprobe 失败
            if size_bytes > 100 * 1024 * 1024:  # > 100MB
                error = "无法获取时长（文件较大，可能需要检查 ffmpeg）"

        return MediaFileInfo(
            path=path,
            size_bytes=size_bytes,
            duration_seconds=duration,
            is_video=is_video,
            existing_md=existing_md,
            error=error,
        )

    def filter_pending(self, files: List[MediaFileInfo],
                       skip_existing: bool = True) -> List[MediaFileInfo]:
        """
        过滤待处理文件

        Args:
            files: 文件列表
            skip_existing: 是否跳过已有转录的文件

        Returns:
            待处理的文件列表
        """
        if not skip_existing:
            return files

        return [f for f in files if not f.has_existing_md]

    def filter_by_duration(self, files: List[MediaFileInfo],
                           min_duration: float = 0.0,
                           max_duration: float = float('inf')) -> List[MediaFileInfo]:
        """
        按时长过滤文件

        Args:
            files: 文件列表
            min_duration: 最小时长（秒）
            max_duration: 最大时长（秒）

        Returns:
            过滤后的文件列表
        """
        return [
            f for f in files
            if min_duration <= f.duration_seconds <= max_duration
        ]

    def filter_by_size(self, files: List[MediaFileInfo],
                       min_size: int = 0,
                       max_size: int = float('inf')) -> List[MediaFileInfo]:
        """
        按文件大小过滤

        Args:
            files: 文件列表
            min_size: 最小大小（字节）
            max_size: 最大大小（字节）

        Returns:
            过滤后的文件列表
        """
        return [
            f for f in files
            if min_size <= f.size_bytes <= max_size
        ]

    def get_large_files(self, files: List[MediaFileInfo],
                        size_threshold_mb: float = 500.0,
                        duration_threshold_min: float = 30.0) -> List[MediaFileInfo]:
        """
        获取需要分段处理的大文件

        Args:
            files: 文件列表
            size_threshold_mb: 大小阈值（MB）
            duration_threshold_min: 时长阈值（分钟）

        Returns:
            大文件列表
        """
        size_threshold = size_threshold_mb * 1024 * 1024
        duration_threshold = duration_threshold_min * 60

        return [
            f for f in files
            if f.size_bytes > size_threshold or f.duration_seconds > duration_threshold
        ]


def generate_preview_text(scan_result: ScanResult) -> str:
    """
    生成扫描预览文本

    Args:
        scan_result: 扫描结果

    Returns:
        预览文本
    """
    lines = []
    lines.append("=" * 60)
    lines.append("音视频文件扫描结果")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"总文件数: {scan_result.total_count}")
    lines.append(f"  - 音频文件: {scan_result.audio_count}")
    lines.append(f"  - 视频文件: {scan_result.video_count}")
    lines.append("")
    lines.append(f"总大小: {scan_result.total_size_str}")
    lines.append(f"总时长: {scan_result.total_duration_str}")
    lines.append("")
    lines.append(f"已有转录文件: {scan_result.existing_md_count}")
    lines.append(f"待处理文件: {scan_result.pending_count}")
    lines.append(f"元数据获取失败: {scan_result.error_count}")
    lines.append("")
    lines.append("=" * 60)

    if scan_result.files:
        lines.append("")
        lines.append("文件列表:")
        lines.append("-" * 60)

        for i, info in enumerate(scan_result.files[:20], 1):
            status = "[已转录]" if info.has_existing_md else "[待处理]"
            type_str = "视频" if info.is_video else "音频"
            lines.append(
                f"{i}. {status} [{type_str}] {info.filename}"
            )
            lines.append(
                f"   大小: {info.size_str} | 时长: {info.duration_str}"
            )

        if len(scan_result.files) > 20:
            lines.append("")
            lines.append(
                f"... 还有 {len(scan_result.files) - 20} 个文件未显示"
            )

    return "\n".join(lines)