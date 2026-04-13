"""
YouTube 解析器
"""

from typing import Dict
from playwright.async_api import Page

from ..base import VideoParser
from ..models import ParserConfig


class YoutubeParser(VideoParser):
    platform = "youtube"
    platform_domains = ["youtube.com", "youtu.be"]

    selectors = {
        'title': 'h1.ytd-video-primary-info-renderer, #title h1',
        'description': '#description, ytd-text-inline-expander',
        'author': '#channel-name, ytd-channel-name',
        'views': '#count, .view-count',
        'content': '#description',
    }

    def __init__(self, config: ParserConfig = None):
        super().__init__(config)

    async def extract_content(self, page: Page) -> Dict:
        result = {}

        try:
            title = await page.evaluate('''() => {
                const el = document.querySelector('h1.ytd-video-primary-info-renderer') ||
                           document.querySelector('#title h1');
                return el ? el.textContent.trim() : '';
            }''')
            result['title'] = title or ''
        except Exception:
            result['title'] = ''

        try:
            description = await page.evaluate('''() => {
                const el = document.querySelector('#description') ||
                           document.querySelector('ytd-text-inline-expander');
                if (el) {
                    const expandBtn = document.querySelector('#expand, tp-yt-paper-button#expand');
                    if (expandBtn) expandBtn.click();
                    return el.innerText || el.textContent;
                }
                return '';
            }''')
            result['description'] = description or ''
            result['content'] = description or ''
        except Exception:
            result['description'] = ''
            result['content'] = ''

        try:
            author = await page.evaluate('''() => {
                const el = document.querySelector('#channel-name') ||
                           document.querySelector('ytd-channel-name');
                return el ? el.textContent.trim() : '';
            }''')
            result['author'] = author or ''
        except Exception:
            result['author'] = ''

        try:
            views = await page.evaluate('''() => {
                const el = document.querySelector('#count') ||
                           document.querySelector('.view-count');
                return el ? el.textContent.trim() : '';
            }''')
            result['views'] = views or ''
        except Exception:
            result['views'] = ''

        try:
            video_info = await page.evaluate('''() => {
                const info = {};
                const metaTags = document.querySelectorAll('meta');
                for (const tag of metaTags) {
                    const name = tag.getAttribute('name') || tag.getAttribute('property');
                    const content = tag.getAttribute('content');
                    if (name && content) info[name] = content;
                }
                return info;
            }''')
            result.update(video_info)
        except Exception:
            pass

        result['raw_text'] = f"{result.get('title', '')}\n\n{result.get('description', '')}"
        result['metadata'] = {'platform': 'youtube'}
        result['video_specific'] = {
            'duration': result.get('duration', ''),
            'views': result.get('views', ''),
            'likes': '',
            'tags': result.get('keywords', ''),
        }

        return result