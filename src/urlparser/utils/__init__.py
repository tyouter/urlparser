"""
工具集

提供 URL 处理、内容清洗、文件操作等通用工具
"""

from .url_utils import URLNormalizer, normalize_url, hash_url, detect_platform, is_video_url
from .text_utils import clean_text, remove_duplicate_lines, extract_main_content
from .file_utils import ensure_dir, safe_filename, read_json, write_json, read_text, write_text, file_size_str, list_files
from .media_utils import (
    is_audio_file, is_video_file, is_media_file,
    get_media_duration, get_media_info, format_duration, format_duration_detailed,
    extract_audio_segment, check_ffmpeg_available,
    AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, MEDIA_EXTENSIONS,
)

__all__ = [
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
    'file_size_str',
    'list_files',

    # Media utilities
    'is_audio_file',
    'is_video_file',
    'is_media_file',
    'get_media_duration',
    'get_media_info',
    'format_duration',
    'format_duration_detailed',
    'extract_audio_segment',
    'check_ffmpeg_available',
    'AUDIO_EXTENSIONS',
    'VIDEO_EXTENSIONS',
    'MEDIA_EXTENSIONS',
]