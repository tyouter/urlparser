"""
Bilibili (B站) 解析器
"""

from typing import Dict
from playwright.async_api import Page

from ..base import VideoParser
from ..models import ParserConfig


class BilibiliParser(VideoParser):
    platform = "bilibili"
    platform_domains = ["bilibili.com", "b23.tv"]

    selectors = {
        'title': 'h1.video-title, .video-title-href, [data-title]',
        'description': '.desc-info-text, .basic-desc-info, .video-desc .text',
        'tags': '.tag-link, .tag-item, .bili-tag',
        'author': '.up-name, .up-info-name, .username',
        'views': '.view-text, .video-data-item',
        'duration': '.duration',
        'content': '.desc-info-text, .basic-desc-info, .video-desc',
        'danmaku': '.dm, [class*="danmaku"]',
    }

    def __init__(self, config: ParserConfig = None):
        super().__init__(config)

    async def extract_content(self, page: Page) -> Dict:
        result = {}

        try:
            title = await page.evaluate('''() => {
                const el = document.querySelector('h1.video-title') ||
                           document.querySelector('.video-title-href') ||
                           document.querySelector('[data-title]');
                return el ? el.textContent.trim() : '';
            }''')
            result['title'] = title or ''
        except Exception:
            result['title'] = ''

        try:
            description = await page.evaluate('''() => {
                const descEl = document.querySelector('.desc-info-text') ||
                               document.querySelector('.basic-desc-info') ||
                               document.querySelector('.video-desc .text');
                if (descEl) {
                    let text = descEl.textContent.trim();
                    const expandBtn = document.querySelector('.desc-btn, [class*="expand"]');
                    if (expandBtn) expandBtn.click();
                    const fullDesc = document.querySelector('.desc-info-text') ||
                                     document.querySelector('.basic-desc-info');
                    if (fullDesc) text = fullDesc.textContent.trim();
                    return text;
                }
                return '';
            }''')
            import html
            result['description'] = html.unescape(description or '')
            result['content'] = html.unescape(description or '')
        except Exception:
            result['description'] = ''
            result['content'] = ''

        try:
            author = await page.evaluate('''() => {
                const el = document.querySelector('.up-name') ||
                           document.querySelector('.up-info-name') ||
                           document.querySelector('.username');
                return el ? el.textContent.trim() : '';
            }''')
            result['author'] = author or ''
        except Exception:
            result['author'] = ''

        try:
            views = await page.evaluate('''() => {
                const el = document.querySelector('.view-text') ||
                           document.querySelector('.video-data-item');
                return el ? el.textContent.trim() : '';
            }''')
            result['views'] = views or ''
        except Exception:
            result['views'] = ''

        try:
            tags = await page.evaluate('''() => {
                const tagEls = document.querySelectorAll('.tag-link, .tag-item, .bili-tag');
                return Array.from(tagEls).map(el => el.textContent.trim()).filter(t => t).join('\\n');
            }''')
            result['tags'] = tags or ''
        except Exception:
            result['tags'] = ''

        try:
            video_info = await page.evaluate('''() => {
                const info = {};
                const durationEl = document.querySelector('.duration, [class*="duration"]');
                if (durationEl) info.duration = durationEl.textContent.trim();
                const likeEl = document.querySelector('.video-like-info, [class*="like"]');
                if (likeEl) info.likes = likeEl.textContent.trim();
                const coinEl = document.querySelector('.video-coin-info, [class*="coin"]');
                if (coinEl) info.coins = coinEl.textContent.trim();
                const favEl = document.querySelector('.video-fav-info, [class*="fav"]');
                if (favEl) info.favorites = favEl.textContent.trim();
                const categoryEl = document.querySelector('[class*="tag-channel"], .channel-name');
                if (categoryEl) info.category = categoryEl.textContent.trim();
                return info;
            }''')
            result.update(video_info)
        except Exception:
            pass

        result['raw_text'] = f"{result.get('title', '')}\n\n{result.get('description', '')}"
        result['metadata'] = {'platform': 'bilibili'}
        result['video_specific'] = {
            'duration': result.get('duration', ''),
            'views': result.get('views', ''),
            'likes': result.get('likes', ''),
            'coins': result.get('coins', ''),
            'favorites': result.get('favorites', ''),
            'tags': result.get('tags', ''),
            'category': result.get('category', ''),
        }

        return result