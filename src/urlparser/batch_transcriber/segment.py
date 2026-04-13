"""
大文件分段处理

处理超大音视频文件的分段转录策略
"""

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from ..transcriber.base import TranscriptionResult
from ..utils.media_utils import (
    get_media_duration, extract_audio_segment, format_duration
)


@dataclass
class SegmentInfo:
    """分段信息"""
    start: float
    end: float
    index: int

    @property
    def duration(self) -> float:
        """分段时长"""
        return self.end - self.start

    @property
    def duration_str(self) -> str:
        """时长字符串"""
        return format_duration(self.duration)

    @property
    def range_str(self) -> str:
        """时间范围字符串"""
        return f"{format_duration(self.start)} - {format_duration(self.end)}"


@dataclass
class SegmentationConfig:
    """分段配置"""
    max_segment_duration: float = 1800.0  # 30分钟
    max_segment_size_mb: float = 500.0    # 500MB
    overlap_seconds: float = 2.0          # 重叠时间（秒）
    gpu_memory_factor: float = 1.0        # GPU显存调整因子


class SegmentHandler:
    """分段处理器"""

    def __init__(self, config: Optional[SegmentationConfig] = None):
        self.config = config or SegmentationConfig()

    def should_segment(self, duration: float, size_mb: float) -> bool:
        """
        判断是否需要分段

        Args:
            duration: 文件时长（秒）
            size_mb: 文件大小（MB）

        Returns:
            是否需要分段
        """
        # 大文件强制分段（内存保护）
        if size_mb > self.config.max_segment_size_mb:
            return True

        # 长文件建议分段
        if duration > self.config.max_segment_duration:
            return True

        return False

    def calculate_segments(self, duration: float) -> List[SegmentInfo]:
        """
        计算分段方案

        Args:
            duration: 文件总时长（秒）

        Returns:
            分段信息列表
        """
        if duration <= self.config.max_segment_duration:
            return [SegmentInfo(start=0, end=duration, index=0)]

        # 计算分段数
        segment_duration = self.config.max_segment_duration
        num_segments = int(duration / segment_duration) + 1

        # 调整分段时长以均匀分布
        adjusted_duration = duration / num_segments

        segments = []
        for i in range(num_segments):
            start = i * adjusted_duration
            end = min((i + 1) * adjusted_duration + self.config.overlap_seconds, duration)

            if start >= duration:
                break

            segments.append(SegmentInfo(start=start, end=end, index=i))

        return segments

    def transcribe_segment(
        self,
        file_path: str,
        segment: SegmentInfo,
        transcriber,
        language: str = "zh",
        temp_dir: Optional[str] = None
    ) -> TranscriptionResult:
        """
        转录单个分段

        Args:
            file_path: 音视频文件路径
            segment: 分段信息
            transcriber: 转录器实例
            language: 语言
            temp_dir: 临时目录

        Returns:
            转录结果
        """
        temp_audio = None

        try:
            # 创建临时目录
            if temp_dir is None:
                temp_dir = tempfile.mkdtemp(prefix='segment_')

            # 提取音频片段
            temp_audio = os.path.join(
                temp_dir,
                f"segment_{segment.index}.mp3"
            )

            success = extract_audio_segment(
                file_path,
                segment.start,
                segment.end,
                temp_audio
            )

            if not success:
                # 如果提取失败，尝试直接转录原文件
                # 但限制时长可能会有问题，这里记录警告
                return TranscriptionResult(
                    success=False,
                    error=f"无法提取音频片段 {segment.range_str}",
                    engine=transcriber.engine_name
                )

            # 转录片段
            result = transcriber.transcribe(temp_audio, language)

            return result

        except Exception as e:
            return TranscriptionResult(
                success=False,
                error=str(e),
                engine=transcriber.engine_name if hasattr(transcriber, 'engine_name') else "unknown"
            )

        finally:
            # 清理临时文件
            if temp_audio and os.path.exists(temp_audio):
                try:
                    os.unlink(temp_audio)
                except Exception:
                    pass

    def transcribe_segments(
        self,
        file_path: str,
        segments: List[SegmentInfo],
        transcriber,
        language: str = "zh",
        progress_callback=None
    ) -> List[TranscriptionResult]:
        """
        批量转录多个分段

        Args:
            file_path: 音视频文件路径
            segments: 分段列表
            transcriber: 转录器实例
            language: 语言
            progress_callback: 进度回调函数 (segment_index, total_segments)

        Returns:
            转录结果列表
        """
        temp_dir = tempfile.mkdtemp(prefix='segments_')
        results = []

        try:
            total = len(segments)

            for i, segment in enumerate(segments):
                result = self.transcribe_segment(
                    file_path,
                    segment,
                    transcriber,
                    language,
                    temp_dir
                )
                results.append(result)

                if progress_callback:
                    progress_callback(i + 1, total)

            return results

        finally:
            # 清理临时目录
            if temp_dir and os.path.exists(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

    def merge_results(
        self,
        results: List[TranscriptionResult],
        segments: List[SegmentInfo]
    ) -> TranscriptionResult:
        """
        合并多个分段转录结果

        Args:
            results: 各分段转录结果
            segments: 分段信息

        Returns:
            合并后的转录结果
        """
        if not results:
            return TranscriptionResult(
                success=False,
                error="无转录结果",
                engine="merged"
            )

        # 检查是否全部失败
        failed_count = sum(1 for r in results if not r.success)
        if failed_count == len(results):
            return TranscriptionResult(
                success=False,
                error="所有分段转录失败",
                engine="merged"
            )

        # 合并文本
        merged_text = ""
        merged_segments = []
        total_duration = 0.0

        for i, (result, segment) in enumerate(zip(results, segments)):
            if result.success and result.text:
                merged_text += result.text

                # 调整时间戳偏移
                for seg in result.segments:
                    adjusted_seg = {
                        'start': seg.get('start', 0) + segment.start,
                        'end': seg.get('end', 0) + segment.start,
                        'text': seg.get('text', ''),
                    }
                    merged_segments.append(adjusted_seg)

            total_duration += segment.duration

        # 去除重叠部分的重复文本
        merged_text = self._remove_overlap_text(merged_text)

        return TranscriptionResult(
            success=True,
            text=merged_text,
            segments=merged_segments,
            language=results[0].language if results else "",
            duration=total_duration,
            engine=f"merged({len(results)} segments)"
        )

    def _remove_overlap_text(self, text: str) -> str:
        """
        去除重叠部分的重复文本

        Args:
            text: 合并后的文本

        Returns:
        cleaned 文本
        """
        # 简单处理：去除完全重复的句子
        # 重叠部分可能导致相似的文本出现两次
        sentences = text.replace('\n', ' ').split('。')
        seen = set()
        cleaned = []

        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and sentence not in seen:
                seen.add(sentence)
                cleaned.append(sentence)

        return '。'.join(cleaned) + '。' if cleaned else ""


def estimate_gpu_segment_size(gpu_memory_gb: float) -> float:
    """
    根据 GPU 显存估算推荐的分段大小（秒）

    Args:
        gpu_memory_gb: GPU 显存大小（GB）

    Returns:
        推荐的分段时长（秒）
    """
    # 基于经验值：
    # - 4GB 显存: 约 15-20 分钟
    # - 8GB 显存: 约 30-40 分钟
    # - 16GB+ 显存: 可以处理更长时间

    if gpu_memory_gb < 4:
        return 900.0  # 15分钟
    elif gpu_memory_gb < 8:
        return 1800.0  # 30分钟
    elif gpu_memory_gb < 16:
        return 3600.0  # 60分钟
    else:
        return 7200.0  # 120分钟


def get_recommended_config(
    file_size_mb: float,
    file_duration: float,
    gpu_memory_gb: Optional[float] = None
) -> SegmentationConfig:
    """
    根据文件和硬件条件获取推荐的分段配置

    Args:
        file_size_mb: 文件大小（MB）
        file_duration: 文件时长（秒）
        gpu_memory_gb: GPU 显存大小（GB）

    Returns:
        推荐的分段配置
    """
    config = SegmentationConfig()

    # 根据文件大小调整
    if file_size_mb > 1000:  # > 1GB
        config.max_segment_duration = 900.0  # 15分钟
        config.max_segment_size_mb = 300.0
    elif file_size_mb > 500:  # > 500MB
        config.max_segment_duration = 1200.0  # 20分钟

    # 根据 GPU 显存调整
    if gpu_memory_gb:
        recommended_duration = estimate_gpu_segment_size(gpu_memory_gb)
        config.max_segment_duration = min(
            config.max_segment_duration,
            recommended_duration
        )

    return config