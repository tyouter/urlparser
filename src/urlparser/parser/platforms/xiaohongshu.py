"""
小红书 (Xiaohongshu) 解析器
"""

from typing import Dict
from playwright.async_api import Page
import asyncio
import urllib.parse

from ..base import ArticleParser
from ..models import ParserConfig
from ..mixins.content_quality import ContentQualityMixin
from ..mixins.content_clean import ContentCleanMixin


class XiaohongshuParser(ArticleParser):
    platform = "xiaohongshu"
    platform_domains = ["xiaohongshu.com", "xhslink.com"]

    selectors = {
        'title': '.title, .note-content-title, h1',
        'content': '.note-text, .desc, .content',
        'author': '.user-name, .author-name, .username',
        'likes': '.like-count, .count',
        'date': '.publish-time, time',
    }

    def __init__(self, config: ParserConfig = None):
        super().__init__(config)
        self.config.scroll_enabled = True
        self.config.dismiss_popups = True

    async def _fetch_with_page(self, page: Page, url: str):
        if 'redirectPath' in url:
            actual_url = await self._handle_redirect(page, url)
        else:
            actual_url = url

        return await super()._fetch_with_page(page, actual_url)

    async def _handle_redirect(self, page: Page, url: str) -> str:
        try:
            await page.goto(
                'https://www.xiaohongshu.com',
                timeout=60000,
                wait_until='domcontentloaded'
            )
            await asyncio.sleep(3)

            redirect_path = url.split('redirectPath=')[1].split('&')[0]
            actual_url = urllib.parse.unquote(redirect_path)

            if actual_url.startswith('http'):
                return actual_url
            else:
                return f'https://www.xiaohongshu.com{actual_url}'

        except Exception:
            return url

    async def pre_process(self, page: Page):
        await ContentQualityMixin.dismiss_popups(page)
        await asyncio.sleep(1)

    async def extract_content(self, page: Page) -> Dict:
        result = {}

        try:
            title = await page.evaluate('''() => {
                const selectors = ['.title', '.note-content-title', 'h1'];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent.trim()) return el.textContent.trim();
                }
                const ogTitle = document.querySelector('meta[property="og:title"]');
                return ogTitle ? ogTitle.getAttribute('content') : '';
            }''')
            result['title'] = title or ''
        except Exception:
            result['title'] = ''

        try:
            content = await page.evaluate('''() => {
                const selectors = ['.note-text', '.desc', '.content', '[class*="note"]'];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText.trim()) return el.innerText;
                }
                const mainContent = document.querySelector('#detail-desc, .note-content');
                return mainContent ? mainContent.innerText : document.body.innerText;
            }''')
            result['content'] = content or ''
            result['raw_text'] = content or ''
        except Exception:
            result['content'] = ''
            result['raw_text'] = ''

        try:
            author = await page.evaluate('''() => {
                const selectors = ['.user-name', '.author-name', '.username', '.name'];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent.trim()) return el.textContent.trim();
                }
                return '';
            }''')
            result['author'] = author or ''
        except Exception:
            result['author'] = ''

        try:
            likes = await page.evaluate('''() => {
                const el = document.querySelector('.like-count, .count, [class*="like"]');
                return el ? el.textContent.trim() : '';
            }''')
            result['likes'] = likes or ''
        except Exception:
            result['likes'] = ''

        result['metadata'] = {'platform': 'xiaohongshu'}

        return result

    def post_process(self, content: Dict):
        raw_text = content.get('raw_text', '')
        if raw_text:
            content['raw_text'] = ContentCleanMixin.clean_text(raw_text)

        result = super().post_process(content)

        text = content.get('content', '') or content.get('raw_text', '')
        result.metadata['is_access_restricted'] = ContentQualityMixin.is_access_restricted(text, 'xiaohongshu')

        return result