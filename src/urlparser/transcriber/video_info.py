"""
视频信息提取器

使用 yt-dlp 提取视频元数据
"""

import re
import json
import hashlib
from typing import Dict, Optional, List
from urllib.parse import urlparse
from pathlib import Path


class VideoInfoExtractor:
    def __init__(self):
        self.supported_platforms = []

    def extract(self, url: str) -> Dict:
        raise NotImplementedError

    def _detect_platform(self, url: str) -> Optional[str]:
        return None


class YtdlpExtractor(VideoInfoExtractor):
    """使用 yt-dlp 提取视频信息"""

    def __init__(self):
        super().__init__()
        self.supported_platforms = [
            'youtube.com', 'youtu.be',
            'bilibili.com', 'b23.tv',
            'douyin.com',
            'kuaishou.com',
            'vimeo.com',
            'dailymotion.com',
            'twitch.tv',
        ]

    def extract(self, url: str, include_comments: bool = False) -> Dict:
        import yt_dlp

        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writesubtitleslangs': ['zh', 'en', 'zh-Hans', 'zh-Hant'],
            'listsubtitles': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }

        if include_comments:
            ydl_opts['getcomments'] = True

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                result = {
                    'url': url,
                    'platform': self._detect_platform(url),
                    'fetch_success': True,
                }

                result['title'] = info.get('title', '')
                result['description'] = info.get('description', '')

                result['author'] = info.get('uploader') or info.get('channel', '')
                result['author_id'] = info.get('uploader_id') or info.get('channel_id', '')

                result['publish_date'] = info.get('upload_date', '')
                if result['publish_date']:
                    try:
                        from datetime import datetime
                        date_obj = datetime.strptime(result['publish_date'], '%Y%m%d')
                        result['publish_date_formatted'] = date_obj.strftime('%Y-%m-%d')
                    except Exception:
                        pass

                duration = info.get('duration')
                if duration:
                    minutes = int(duration // 60)
                    seconds = int(duration % 60)
                    result['duration'] = f"{minutes}:{seconds:02d}"
                    result['duration_seconds'] = duration
                else:
                    result['duration'] = ''
                    result['duration_seconds'] = 0

                result['views'] = self._format_number(info.get('view_count'))
                result['likes'] = self._format_number(info.get('like_count'))
                result['coins'] = self._format_number(info.get('coin_count'))
                result['favorites'] = self._format_number(info.get('favorites'))
                result['shares'] = self._format_number(info.get('repost_count'))

                tags = info.get('tags', [])
                if tags:
                    if isinstance(tags, str):
                        result['tags'] = tags
                    else:
                        result['tags'] = ', '.join([str(t) for t in tags])
                else:
                    result['tags'] = ''

                categories = info.get('categories', [])
                result['category'] = categories[0] if categories else ''

                result['thumbnail'] = info.get('thumbnail', '')
                result['subtitles'] = self._extract_subtitles(info)

                if include_comments:
                    result['comments_summary'] = self._extract_comments_summary(info)
                else:
                    result['comments_summary'] = None

                result['raw_text'] = self._build_raw_text(result)

                result['content_hash'] = hashlib.md5(
                    (result.get('title', '') + result.get('description', '')).encode()
                ).hexdigest()[:12]

                return result

        except Exception as e:
            return {
                'url': url,
                'platform': self._detect_platform(url),
                'fetch_success': False,
                'error': str(e),
                'title': '',
                'description': '',
                'raw_text': ''
            }

    def _detect_platform(self, url: str) -> str:
        domain = urlparse(url).netloc.lower()

        platform_map = {
            'youtube.com': 'youtube',
            'youtu.be': 'youtube',
            'bilibili.com': 'bilibili',
            'b23.tv': 'bilibili',
            'douyin.com': 'douyin',
            'kuaishou.com': 'kuaishou',
            'vimeo.com': 'vimeo',
            'dailymotion.com': 'dailymotion',
            'twitch.tv': 'twitch',
        }

        for platform_domain, platform_name in platform_map.items():
            if platform_domain in domain:
                return platform_name

        return 'unknown'

    def _extract_subtitles(self, info: Dict) -> List[Dict]:
        subtitles = []

        available_subtitles = info.get('subtitles', {})
        automatic_subtitles = info.get('automatic_captions', {})

        all_subtitles = {}
        for lang, sub_data in available_subtitles.items():
            all_subtitles[lang] = (sub_data, 'manual')
        for lang, sub_data in automatic_subtitles.items():
            if lang not in all_subtitles:
                all_subtitles[lang] = (sub_data, 'automatic')

        for lang, (sub_data, sub_type) in all_subtitles.items():
            try:
                if isinstance(sub_data, list) and len(sub_data) > 0:
                    sub = sub_data[0]
                    sub_url = sub.get('url')

                    if sub_url:
                        sub_entries = []

                        subtitles.append({
                            'language': lang,
                            'type': sub_type,
                            'entries': sub_entries
                        })
            except Exception:
                pass

        return subtitles

    def _extract_comments_summary(self, info: Dict) -> Optional[Dict]:
        comments = info.get('comments', [])

        if not comments or len(comments) == 0:
            return None

        return {
            'total': len(comments),
            'top_comment': comments[0]['text'] if comments else '',
            'avg_likes': sum(c.get('like_count', 0) for c in comments) / len(comments) if comments else 0
        }

    def _build_raw_text(self, result: Dict) -> str:
        parts = []

        if result.get('title'):
            parts.append(result['title'])

        if result.get('description'):
            parts.append(result['description'])

        if result.get('tags'):
            parts.append(f"Tags: {result['tags']}")

        return '\n\n'.join(parts)

    def _format_number(self, num: Optional[int]) -> str:
        if num is None:
            return ''

        if num >= 100000000:
            return f'{num/100000000:.1f}M'
        elif num >= 10000:
            return f'{num/10000:.1f}万'
        elif num >= 1000:
            return f'{num/1000:.1f}K'
        else:
            return str(num)


_ytdlp_extractor: Optional[YtdlpExtractor] = None


def get_video_extractor() -> YtdlpExtractor:
    global _ytdlp_extractor
    if _ytdlp_extractor is None:
        _ytdlp_extractor = YtdlpExtractor()
    return _ytdlp_extractor


def extract_video_info(url: str, include_comments: bool = False) -> Dict:
    extractor = get_video_extractor()
    return extractor.extract(url, include_comments=include_comments)


def is_video_url(url: str) -> bool:
    extractor = get_video_extractor()
    return any(platform in urlparse(url).netloc.lower()
               for platform in extractor.supported_platforms)