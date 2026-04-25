"""
ffmpeg / ffprobe 路径查找

统一查找 ffmpeg 和 ffprobe 可执行文件，避免各模块重复实现。
查找顺序：PATH → imageio-ffmpeg → 常见安装路径 → fallback
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

_cached_ffmpeg: Optional[str] = None
_cached_ffprobe: Optional[str] = None


def find_ffmpeg() -> str:
    """查找 ffmpeg 可执行文件路径。

    查找顺序:
    1. 系统 PATH
    2. imageio-ffmpeg 捆绑的 ffmpeg
    3. 常见安装路径（Windows/Linux/macOS）
    4. fallback "ffmpeg"
    """
    global _cached_ffmpeg
    if _cached_ffmpeg is not None:
        return _cached_ffmpeg

    # 1. Try system PATH
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'], capture_output=True, timeout=5
        )
        if result.returncode == 0:
            _cached_ffmpeg = 'ffmpeg'
            return _cached_ffmpeg
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 2. Try imageio-ffmpeg bundled binary
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.isfile(path):
            _cached_ffmpeg = path
            return _cached_ffmpeg
    except (ImportError, Exception):
        pass

    # 3. Common install paths
    common_paths = []
    if os.name == 'nt':
        common_paths.append(r'C:\ffmpeg\bin\ffmpeg.exe')
    else:
        common_paths.extend([
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/snap/bin/ffmpeg',
        ])

    for p in common_paths:
        if os.path.isfile(p):
            _cached_ffmpeg = p
            return _cached_ffmpeg

    _cached_ffmpeg = 'ffmpeg'
    return _cached_ffmpeg


def find_ffprobe() -> str:
    """查找 ffprobe 可执行文件路径。

    查找顺序:
    1. 系统 PATH
    2. ffmpeg 同目录下查找
    3. 常见安装路径（Windows/Linux/macOS）
    4. fallback "ffprobe"
    """
    global _cached_ffprobe
    if _cached_ffprobe is not None:
        return _cached_ffprobe

    # 1. Try system PATH
    try:
        result = subprocess.run(
            ['ffprobe', '-version'], capture_output=True, timeout=5
        )
        if result.returncode == 0:
            _cached_ffprobe = 'ffprobe'
            return _cached_ffprobe
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 2. Check alongside ffmpeg
    ffmpeg_path = find_ffmpeg()
    if os.path.isabs(ffmpeg_path):
        ext = os.path.splitext(os.path.basename(ffmpeg_path))[1]
        candidate = os.path.join(os.path.dirname(ffmpeg_path), 'ffprobe' + ext)
        if os.path.isfile(candidate):
            _cached_ffprobe = candidate
            return _cached_ffprobe

    # 3. Common install paths
    common_paths = []
    if os.name == 'nt':
        common_paths.append(r'C:\ffmpeg\bin\ffprobe.exe')
    else:
        common_paths.extend([
            '/usr/bin/ffprobe',
            '/usr/local/bin/ffprobe',
            '/snap/bin/ffprobe',
        ])

    for p in common_paths:
        if os.path.isfile(p):
            _cached_ffprobe = p
            return _cached_ffprobe

    _cached_ffprobe = 'ffprobe'
    return _cached_ffprobe
