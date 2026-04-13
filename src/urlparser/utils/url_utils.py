"""
URL 处理工具

URL 规范化、哈希、平台检测
"""

import re
import hashlib
from urllib.parse import urlparse
from typing import Optional


class URLNormalizer:
    """URL 规范化器，去除跟踪参数"""

    TRACKING_PARAMS = (
        r'[?&](buvid|timestamp|unique_k|up_id|mid|is_story_h5|plat_id|'
        r'spmid|share_session_id|fsource|from_spmid|bvid|utm_|'
        r'ref_|share_|from_|spm_|vd_source)[^&]*'
    )

    def normalize(self, url: str) -> str:
        url = re.sub(self.TRACKING_PARAMS, '', url)
        url = url.split('#')[0]
        url = url.rstrip('?')
        return url.strip()


_normalizer = URLNormalizer()


def normalize_url(url: str) -> str:
    return _normalizer.normalize(url)


def hash_url(url: str) -> str:
    normalized = normalize_url(url)
    return hashlib.md5(normalized.encode()).hexdigest()


def detect_platform(url: str) -> str:
    domain = urlparse(url).netloc.lower()

    platform_map = {
        'zhihu.com': 'zhihu',
        'bilibili.com': 'bilibili',
        'b23.tv': 'bilibili',
        'youtube.com': 'youtube',
        'youtu.be': 'youtube',
        'weixin.qq.com': 'weixin',
        'mp.weixin.qq.com': 'weixin',
        'xiaohongshu.com': 'xiaohongshu',
        'xhslink.com': 'xiaohongshu',
        'github.com': 'github',
        'dribbble.com': 'dribbble',
        'douyin.com': 'douyin',
        'vimeo.com': 'vimeo',
        'dailymotion.com': 'dailymotion',
        'twitch.tv': 'twitch',
    }

    for platform_domain, platform_name in platform_map.items():
        if platform_domain in domain:
            return platform_name

    return 'generic'


def is_video_url(url: str) -> bool:
    platform = detect_platform(url)
    return platform in ('bilibili', 'youtube', 'douyin', 'vimeo', 'dailymotion', 'twitch')