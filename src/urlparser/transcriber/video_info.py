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
                    sub_ext = sub.get('ext', '')

                    if sub_url:
                        sub_entries = self._download_and_parse_subtitle(sub_url, sub_ext)

                        if sub_entries:
                            subtitles.append({
                                'language': lang,
                                'type': sub_type,
                                'entries': sub_entries,
                                'text': ' '.join(e.get('text', '') for e in sub_entries),
                            })
            except Exception:
                pass

        return subtitles

    def _download_and_parse_subtitle(self, url: str, ext: str) -> List[Dict]:
        import httpx

        try:
            resp = httpx.get(url, timeout=15, follow_redirects=True)
            resp.raise_for_status()
            content = resp.text
        except Exception:
            return []

        if ext in ('json3', 'json') or url.endswith('.json3') or url.endswith('.json'):
            return self._parse_json3_subtitle(content)
        elif ext in ('srv1', 'srv2', 'srv3') or '.srv' in url:
            return self._parse_xml_subtitle(content)
        elif ext in ('vtt', 'srt') or url.endswith('.vtt') or url.endswith('.srt'):
            return self._parse_vtt_subtitle(content)
        else:
            entries = self._parse_json3_subtitle(content)
            if entries:
                return entries
            entries = self._parse_vtt_subtitle(content)
            if entries:
                return entries
            return self._parse_xml_subtitle(content)

    def _parse_json3_subtitle(self, content: str) -> List[Dict]:
        try:
            data = json.loads(content)
            events = data.get('events', [])
            entries = []
            for event in events:
                if not event.get('segs'):
                    continue
                text = ''.join(seg.get('utf8', '') for seg in event['segs']).strip()
                if not text:
                    continue
                start_ms = event.get('tStartMs', 0)
                duration_ms = event.get('dDurationMs', 0)
                entries.append({
                    'start': start_ms / 1000.0,
                    'end': (start_ms + duration_ms) / 1000.0,
                    'text': text,
                })
            return entries
        except Exception:
            return []

    def _parse_vtt_subtitle(self, content: str) -> List[Dict]:
        entries = []
        try:
            time_pattern = re.compile(
                r'(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[.,](\d{3})'
            )
            lines = content.split('\n')
            i = 0
            while i < len(lines):
                match = time_pattern.search(lines[i])
                if match:
                    g = match.groups()
                    start = int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000.0
                    end = int(g[4]) * 3600 + int(g[5]) * 60 + int(g[6]) + int(g[7]) / 1000.0
                    text_lines = []
                    i += 1
                    while i < len(lines) and lines[i].strip() and not time_pattern.search(lines[i]):
                        line = lines[i].strip()
                        if not line.startswith('WEBVTT') and not line.startswith('Kind:') and not line.startswith('Language:'):
                            text_lines.append(line)
                        i += 1
                    text = ' '.join(text_lines).strip()
                    if text:
                        entries.append({'start': start, 'end': end, 'text': text})
                else:
                    i += 1
        except Exception:
            pass
        return entries

    def _parse_xml_subtitle(self, content: str) -> List[Dict]:
        import xml.etree.ElementTree as ET

        entries = []
        try:
            root = ET.fromstring(content)
            for elem in root.iter():
                start = elem.get('t')
                duration = elem.get('d')
                text = elem.text
                if start and text and text.strip():
                    start_s = float(start) / 1000.0
                    dur_s = float(duration) / 1000.0 if duration else 0
                    entries.append({
                        'start': start_s,
                        'end': start_s + dur_s,
                        'text': text.strip(),
                    })
        except Exception:
            pass
        return entries

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