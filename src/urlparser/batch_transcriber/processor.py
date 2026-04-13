"""
批量转录处理器

批量处理音视频文件转录，支持进度展示和时间预估
"""

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

from ..transcriber.base import TranscriptionResult
from ..transcriber import FunASRTranscriber, WhisperTranscriber
from ..utils import file_size_str, format_duration, format_duration_detailed
from .scanner import MediaFileInfo, ScanResult, MediaScanner
from .segment import SegmentHandler, SegmentationConfig, get_recommended_config
from .writer import TranscriptionWriter, WriterConfig


@dataclass
class BatchTranscribeConfig:
    """批量转录配置"""
    engine: str = "auto"           # funasr/whisper/auto
    model_size: str = "large"      # 模型大小
    device: str = "auto"           # 设备
    language: str = "zh"           # 语言
    recursive: bool = True         # 递归扫描
    skip_existing: bool = True     # 跳过已有转录
    segment_threshold_min: float = 30.0  # 分段时长阈值（分钟）
    max_file_size_mb: float = 500.0      # 最大文件大小阈值（MB）
    show_progress: bool = True     # 显示进度
    confirm_before_start: bool = True    # 开始前确认
    output_dir: Optional[str] = None     # 输出目录（None 表示保存到源文件同目录）

    def get_segment_threshold_seconds(self) -> float:
        """获取分段阈值（秒）"""
        return self.segment_threshold_min * 60

    def get_max_file_size_bytes(self) -> int:
        """获取最大文件大小（字节）"""
        return int(self.max_file_size_mb * 1024 * 1024)


@dataclass
class FileResult:
    """单文件处理结果"""
    file_info: MediaFileInfo
    transcription: TranscriptionResult
    md_path: Optional[Path] = None
    process_time: float = 0.0
    segmented: bool = False
    segment_count: int = 0
    success: bool = False
    error: Optional[str] = None

    @property
    def speed_factor(self) -> float:
        """处理速度因子（处理时间 / 文件时长）"""
        if self.file_info.duration_seconds <= 0:
            return 0.0
        return self.process_time / self.file_info.duration_seconds

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'filename': self.file_info.filename,
            'duration': self.file_info.duration_str,
            'process_time': f"{self.process_time:.1f}s",
            'speed_factor': f"{self.speed_factor:.2f}",
            'segmented': self.segmented,
            'segment_count': self.segment_count,
            'success': self.success,
            'md_path': str(self.md_path) if self.md_path else None,
            'error': self.error,
        }


@dataclass
class BatchResult:
    """批量处理结果"""
    total_files: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    total_duration: float = 0.0      # 总时长
    processed_duration: float = 0.0  # 已处理时长
    total_time: float = 0.0          # 总处理时间
    files: List[FileResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def avg_speed_factor(self) -> float:
        """平均速度因子"""
        successful_files = [f for f in self.files if f.success and f.speed_factor > 0]
        if not successful_files:
            return 0.0
        return sum(f.speed_factor for f in successful_files) / len(successful_files)

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_files == 0:
            return 0.0
        return self.success_count / self.total_files

    @property
    def total_time_str(self) -> str:
        """总时间字符串"""
        return format_duration(self.total_time)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_files': self.total_files,
            'success_count': self.success_count,
            'failed_count': self.failed_count,
            'skipped_count': self.skipped_count,
            'success_rate': f"{self.success_rate:.1%}",
            'total_duration': format_duration_detailed(self.total_duration),
            'processed_duration': format_duration_detailed(self.processed_duration),
            'total_time': self.total_time_str,
            'avg_speed_factor': f"{self.avg_speed_factor:.2f}",
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
        }


class BatchTranscriber:
    """批量转录处理器"""

    def __init__(self, config: Optional[BatchTranscribeConfig] = None):
        self.config = config or BatchTranscribeConfig()
        self.scanner = MediaScanner()
        self.writer = TranscriptionWriter(
            output_dir=Path(self.config.output_dir) if self.config.output_dir else None
        )
        self.transcriber = None
        self.segment_handler = None

        # 进度回调
        self.progress_callback: Optional[Callable] = None

    def _init_transcriber(self):
        """初始化转录器"""
        if self.transcriber is not None:
            return

        engine = self.config.engine
        if engine == "auto":
            engine = "funasr" if self.config.language == "zh" else "whisper"

        if engine == "funasr":
            self.transcriber = FunASRTranscriber(
                model_size=self.config.model_size,
                device=self.config.device
            )
        else:
            self.transcriber = WhisperTranscriber(
                model_size=self.config.model_size,
                device=self.config.device
            )

    def _init_segment_handler(self):
        """初始化分段处理器"""
        if self.segment_handler is not None:
            return

        segment_config = SegmentationConfig(
            max_segment_duration=self.config.get_segment_threshold_seconds(),
            max_segment_size_mb=self.config.max_file_size_mb
        )
        self.segment_handler = SegmentHandler(segment_config)

    def scan_and_preview(self, directory: str) -> tuple:
        """
        扫描目录并生成预览

        Args:
            directory: 目录路径

        Returns:
            (ScanResult, 预览文本)
        """
        scan_result = self.scanner.scan_directory(
            directory,
            recursive=self.config.recursive
        )

        from .scanner import generate_preview_text
        preview_text = generate_preview_text(scan_result)

        return scan_result, preview_text

    def filter_files_to_process(
        self,
        scan_result: ScanResult
    ) -> List[MediaFileInfo]:
        """
        过滤待处理文件

        Args:
            scan_result: 扫描结果

        Returns:
            待处理文件列表
        """
        files = self.scanner.filter_pending(
            scan_result.files,
            skip_existing=self.config.skip_existing
        )

        # 如果指定了 output_dir，需要检查 output_dir 中是否已有 MD 文件
        if self.config.output_dir and self.config.skip_existing:
            output_dir = Path(self.config.output_dir)
            pending_files = []
            for f in files:
                expected_md = output_dir / (f.path.stem + '.md')
                if not expected_md.exists():
                    pending_files.append(f)
            return pending_files

        return files

    def transcribe_single(
        self,
        file_info: MediaFileInfo,
        progress_callback: Optional[Callable] = None
    ) -> FileResult:
        """
        转录单个文件

        Args:
            file_info: 文件信息
            progress_callback: 进度回调

        Returns:
            FileResult 处理结果
        """
        self._init_transcriber()
        self._init_segment_handler()

        start_time = time.time()
        result = FileResult(file_info=file_info)

        try:
            # 判断是否需要分段
            size_mb = file_info.size_bytes / (1024 * 1024)
            duration = file_info.duration_seconds

            if self.segment_handler.should_segment(duration, size_mb):
                # 分段处理
                result.segmented = True
                segments = self.segment_handler.calculate_segments(duration)
                result.segment_count = len(segments)

                # 转录各分段
                transcription_results = self.segment_handler.transcribe_segments(
                    str(file_info.path),
                    segments,
                    self.transcriber,
                    self.config.language,
                    progress_callback
                )

                # 合并结果
                result.transcription = self.segment_handler.merge_results(
                    transcription_results,
                    segments
                )

            else:
                # 直接转录
                if file_info.is_video:
                    result.transcription = self.transcriber.transcribe_from_local_video(
                        str(file_info.path),
                        self.config.language,
                        extract_audio_only=True
                    )
                else:
                    result.transcription = self.transcriber.transcribe(
                        str(file_info.path),
                        self.config.language
                    )

            # 写入 MD 文件
            if result.transcription.success:
                result.md_path = self.writer.write(
                    file_info.path,
                    result.transcription
                )
                result.success = True
            else:
                result.error = result.transcription.error or "转录失败"

        except Exception as e:
            result.error = str(e)
            result.transcription = TranscriptionResult(
                success=False,
                error=str(e),
                engine=self.transcriber.engine_name if self.transcriber else "unknown"
            )

        result.process_time = time.time() - start_time
        return result

    def transcribe_all(
        self,
        files: List[MediaFileInfo],
        progress_callback: Optional[Callable] = None
    ) -> BatchResult:
        """
        批量转录所有文件

        Args:
            files: 文件列表
            progress_callback: 进度回调 (current, total, file_result, batch_result)

        Returns:
            BatchResult 批量处理结果
        """
        batch_result = BatchResult(
            total_files=len(files),
            start_time=datetime.now()
        )

        # 计算总时长
        batch_result.total_duration = sum(f.duration_seconds for f in files)

        for i, file_info in enumerate(files):
            # 处理单个文件
            file_result = self.transcribe_single(file_info)

            # 更新批量结果
            batch_result.files.append(file_result)
            batch_result.processed_duration += file_info.duration_seconds

            if file_result.success:
                batch_result.success_count += 1
            else:
                batch_result.failed_count += 1

            # 进度回调
            if progress_callback:
                progress_callback(i + 1, len(files), file_result, batch_result)

        batch_result.end_time = datetime.now()
        batch_result.total_time = (
            batch_result.end_time - batch_result.start_time
        ).total_seconds()

        return batch_result

    def estimate_remaining_time(
        self,
        batch_result: BatchResult,
        remaining_count: int
    ) -> float:
        """
        预估剩余时间

        Args:
            batch_result: 当前批量结果
            remaining_count: 剩余文件数

        Returns:
            预估剩余时间（秒）
        """
        if remaining_count == 0:
            return 0.0

        # 计算剩余时长
        processed_files = batch_result.files
        if not processed_files:
            return 0.0

        # 使用平均速度因子估算
        avg_factor = batch_result.avg_speed_factor
        if avg_factor <= 0:
            avg_factor = 0.5  # 默认因子

        # 剩余时长 = 平均速度因子 × 剩余文件的平均时长 × 剩余数量
        avg_duration = batch_result.total_duration / batch_result.total_files
        remaining_duration = avg_duration * remaining_count
        estimated_time = remaining_duration * avg_factor

        return estimated_time


def format_batch_result_summary(batch_result: BatchResult) -> str:
    """
    格式化批量结果摘要

    Args:
        batch_result: 批量处理结果

    Returns:
        摘要文本
    """
    lines = []
    lines.append("=" * 60)
    lines.append("批量转录完成")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"总文件数: {batch_result.total_files}")
    lines.append(f"成功: {batch_result.success_count}")
    lines.append(f"失败: {batch_result.failed_count}")
    lines.append(f"跳过: {batch_result.skipped_count}")
    lines.append(f"成功率: {batch_result.success_rate:.1%}")
    lines.append("")
    lines.append(f"总时长: {format_duration_detailed(batch_result.total_duration)}")
    lines.append(f"处理时间: {batch_result.total_time_str}")
    lines.append(f"平均速度: {batch_result.avg_speed_factor:.2f}x")
    lines.append("")
    lines.append("=" * 60)

    if batch_result.files:
        lines.append("")
        lines.append("详细结果:")
        lines.append("-" * 60)

        for file_result in batch_result.files:
            status = "[OK]" if file_result.success else "[FAIL]"
            segmented = "(分段)" if file_result.segmented else ""
            lines.append(
                f"{status} {file_result.file_info.filename} {segmented}"
            )
            lines.append(
                f"  时长: {file_result.file_info.duration_str} | "
                f"耗时: {file_result.process_time:.1f}s"
            )
            if not file_result.success:
                lines.append(f"  错误: {file_result.error}")

    return "\n".join(lines)


def create_progress_bar_description(
    current: int,
    total: int,
    filename: str,
    batch_result: BatchResult
) -> str:
    """
    创建进度条描述文本

    Args:
        current: 当前处理数
        total: 总数
        filename: 当前文件名
        batch_result: 批量结果

    Returns:
        进度描述文本
    """
    remaining = total - current
    avg_factor = batch_result.avg_speed_factor if batch_result.avg_speed_factor > 0 else 0.5

    # 预估剩余时间
    if batch_result.processed_duration > 0 and batch_result.total_duration > 0:
        remaining_duration = batch_result.total_duration - batch_result.processed_duration
        estimated_remaining = remaining_duration * avg_factor
        eta_str = format_duration(estimated_remaining)
    else:
        eta_str = "未知"

    return f"[{current}/{total}] {filename[:30]} (ETA: {eta_str})"