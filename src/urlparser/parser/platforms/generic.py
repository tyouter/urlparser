"""
通用网页解析器
"""

from typing import Dict
from playwright.async_api import Page

from ..base import BaseParser
from ..models import ParserConfig
from ..mixins.content_clean import ContentCleanMixin


class GenericParser(BaseParser):
    platform = "default"
    platform_domains = []

    selectors = {
        'title': 'h1, title',
        'content': 'article, .content, .post-content, main, .article-body, #content',
        'description': 'meta[name="description"]',
        'author': '[rel="author"], .author, [itemprop="author"]',
    }

    def __init__(self, config: ParserConfig = None):
        super().__init__(config)
        self.config.scroll_enabled = True

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return True

    async def extract_content(self, page: Page) -> Dict:
        result = {}

        try:
            title = await page.evaluate('''() => {
                const selectors = ['h1', '.title', 'title'];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent.trim()) {
                        const text = el.textContent.trim();
                        if (text.length < 200) return text;
                    }
                }
                const ogTitle = document.querySelector('meta[property="og:title"]');
                if (ogTitle) return ogTitle.getAttribute('content');
                return document.title || '';
            }''')
            result['title'] = title or ''
        except Exception:
            result['title'] = ''

        try:
            content = await page.evaluate('''() => {
                const contentSelectors = [
                    'article', '.content', '.post-content', 'main',
                    '.article-body', '#content', '[role="main"]', '.post'
                ];
                let bestContent = '';
                let bestLength = 0;
                for (const sel of contentSelectors) {
                    const els = document.querySelectorAll(sel);
                    for (const el of els) {
                        const text = el.innerText;
                        if (text.length > bestLength && text.length > 100) {
                            bestLength = text.length;
                            bestContent = text;
                        }
                    }
                }
                if (bestContent) return bestContent;
                const bodyText = document.body.innerText;
                const scripts = document.querySelectorAll('script, style, nav, footer, header');
                let cleanBody = bodyText;
                scripts.forEach(s => cleanBody = cleanBody.replace(s.innerText, ''));
                return cleanBody.substring(0, 50000);
            }''')
            result['content'] = content or ''
            result['raw_text'] = content or ''
        except Exception:
            result['content'] = ''
            result['raw_text'] = ''

        try:
            description = await page.evaluate('''() => {
                const el = document.querySelector('meta[name="description"]');
                return el ? el.getAttribute('content') : '';
            }''')
            result['description'] = description or ''
        except Exception:
            result['description'] = ''

        try:
            author = await page.evaluate('''() => {
                const selectors = ['[rel="author"]', '.author', '[itemprop="author"]'];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent.trim()) return el.textContent.trim();
                }
                return '';
            }''')
            result['author'] = author or ''
        except Exception:
            result['author'] = ''

        result['metadata'] = {'platform': 'generic'}

        return result

    def post_process(self, content: Dict):
        raw_text = content.get('raw_text', '')
        if raw_text:
            content['raw_text'] = ContentCleanMixin.remove_duplicate_lines(
                ContentCleanMixin.clean_text(raw_text)
            )

        return super().post_process(content)