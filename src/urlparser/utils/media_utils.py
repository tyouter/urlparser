"""
音视频文件工具

提供音视频文件判断、元数据获取等功能
"""

import subprocess
import os
from pathlib import Path
from typing import Optional, Tuple

from .ffmpeg_utils import find_ffmpeg, find_ffprobe


# 音频文件扩展名
AUDIO_EXTENSIONS = {
    '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.opus',
    '.ape', '.aiff', '.au', '.mid', '.midi', '.ra', '.rm', '.amr'
}

# 视频文件扩展名
VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
    '.ts', '.mts', '.m2ts', '.vob', '.ogv', '.3gp', '.3g2', '.f4v',
    '.asf', '.dv', '.gif', '.rmvb'
}

# 所有音视频扩展名
MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


def is_audio_file(path: str) -> bool:
    """判断是否为音频文件"""
    ext = Path(path).suffix.lower()
    return ext in AUDIO_EXTENSIONS


def is_video_file(path: str) -> bool:
    """判断是否为视频文件"""
    ext = Path(path).suffix.lower()
    return ext in VIDEO_EXTENSIONS


def is_media_file(path: str) -> bool:
    """判断是否为音视频文件"""
    ext = Path(path).suffix.lower()
    return ext in MEDIA_EXTENSIONS


def get_media_duration(path: str) -> float:
    """
    使用 ffprobe 获取音视频时长（秒）

    Args:
        path: 音视频文件路径

    Returns:
        时长（秒），获取失败返回 0.0
    """
    if not Path(path).exists():
        return 0.0

    try:
        ffprobe_cmd = find_ffprobe()

        cmd = [
            ffprobe_cmd,
            '-v', 'quiet',
            '-show_entries', 'format=duration',
            '-of', 'csv=p=0',
            path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())

        # 备用方案：使用 stream duration
        cmd = [
            ffprobe_cmd,
            '-v', 'quiet',
            '-show_entries', 'stream=duration',
            '-of', 'csv=p=0',
            '-select_streams', 'a:0',  # 选择第一个音频流
            path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and result.stdout.strip():
            duration_str = result.stdout.strip().split('\n')[0]
            if duration_str and duration_str != 'N/A':
                return float(duration_str)

        return 0.0

    except subprocess.TimeoutExpired:
        return 0.0
    except Exception:
        return 0.0


def get_media_info(path: str) -> Tuple[float, int, Optional[str]]:
    """
    获取音视频文件基本信息

    Args:
        path: 音视频文件路径

    Returns:
        (时长秒, 文件大小字节, 文件类型描述)
    """
    p = Path(path)
    if not p.exists():
        return (0.0, 0, None)

    size_bytes = p.stat().st_size
    duration = get_media_duration(path)
    file_type = "audio" if is_audio_file(path) else "video" if is_video_file(path) else None

    return (duration, size_bytes, file_type)


def format_duration(seconds: float) -> str:
    """
    格式化时长为可读字符串

    Args:
        seconds: 时长（秒）

    Returns:
        格式化字符串，如 "1:23:45" 或 "12:34"
    """
    if seconds <= 0:
        return "00:00"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def format_duration_detailed(seconds: float) -> str:
    """
    格式化时长为详细描述

    Args:
        seconds: 时长（秒）

    Returns:
        格式化字符串，如 "1小时23分45秒" 或 "12分34秒"
    """
    if seconds <= 0:
        return "未知"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0:
        parts.append(f"{minutes}分")
    if secs > 0 or not parts:
        parts.append(f"{secs}秒")

    return ''.join(parts)


def extract_audio_segment(video_path: str, start: float, end: float,
                          output_path: str) -> bool:
    """
    从视频中提取音频片段

    Args:
        video_path: 视频文件路径
        start: 开始时间（秒）
        end: 结束时间（秒）
        output_path: 输出音频文件路径

    Returns:
        是否成功
    """
    try:
        ffmpeg_cmd = find_ffmpeg()

        cmd = [
            ffmpeg_cmd,
            '-i', video_path,
            '-ss', str(start),
            '-to', str(end),
            '-vn',
            '-acodec', 'libmp3lame',
            '-ab', '192k',
            '-y',
            output_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        return result.returncode == 0 and Path(output_path).exists()

    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def check_ffmpeg_available() -> bool:
    """检查 ffmpeg/ffprobe 是否可用"""
    try:
        ffmpeg_cmd = find_ffmpeg()
        ffprobe_cmd = find_ffprobe()

        # 检查 ffmpeg
        result = subprocess.run(
            [ffmpeg_cmd, '-version'],
            capture_output=True,
            timeout=5
        )
        if result.returncode != 0:
            return False

        # 检查 ffprobe
        result = subprocess.run(
            [ffprobe_cmd, '-version'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0

    except Exception:
        return False