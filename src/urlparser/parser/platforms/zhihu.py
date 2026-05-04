"""
知乎 (Zhihu) 解析器
"""

from typing import Dict
from playwright.async_api import Page
import asyncio

from ..base import ArticleParser
from ..models import ParserConfig
from ..mixins.content_quality import ContentQualityMixin
from ..mixins.content_clean import ContentCleanMixin


class ZhihuParser(ArticleParser):
    platform = "zhihu"
    platform_domains = ["zhihu.com"]

    selectors = {
        'title': 'h1.Post-Title, .QuestionHeader-title, [data-za-detail-view-path-module="Title"]',
        'content': '.Post-RichText, .RichContent-inner, .css-1yuhvjn',
        'author': '.AuthorInfo-name, .UserLink-link, .Name',
        'votes': '.VoteButton--up, .css-1c8urzw',
        'date': 'time, .ContentItem-time',
        'topic': '.TopicLink, .rich-topic-wrapper',
    }

    def __init__(self, config: ParserConfig = None):
        super().__init__(config)
        self.config.scroll_enabled = True
        self.config.load_full_content = True
        self.config.dismiss_popups = True

    async def pre_process(self, page: Page):
        await ContentQualityMixin.dismiss_popups(page)
        await asyncio.sleep(1)
        await ContentQualityMixin.load_full_content(page)
        await asyncio.sleep(0.5)

    async def extract_content(self, page: Page) -> Dict:
        result = {}

        try:
            title = await page.evaluate('''() => {
                const selectors = [
                    'h1.Post-Title',
                    '.QuestionHeader-title',
                    '[data-za-detail-view-path-module="Title"]',
                    'h1'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent.trim()) return el.textContent.trim();
                }
                return '';
            }''')
            result['title'] = title or ''
        except Exception:
            result['title'] = ''

        try:
            content = await page.evaluate('''() => {
                const selectors = [
                    '.Post-RichText',
                    '.RichContent-inner',
                    '.css-1yuhvjn',
                    '.RichText',
                    '.RichContent',
                    'article',
                    '.ContentItem-richText',
                    '[itemprop="text"]',
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText.trim().length > 100) return el.innerText;
                }
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) return el.innerText;
                }
                return document.body.innerText;
            }''')
            result['content'] = content or ''
            result['raw_text'] = content or ''
        except Exception:
            result['content'] = ''
            result['raw_text'] = ''

        try:
            html_content = await page.evaluate('''() => {
                const selectors = [
                    '.Post-RichText',
                    '.RichContent-inner',
                    '.css-1yuhvjn',
                    '.RichText',
                    '.RichContent',
                    'article',
                    '.ContentItem-richText',
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) return el.innerHTML;
                }
                return '';
            }''')
            result['raw_html'] = html_content or ''
        except Exception:
            result['raw_html'] = ''

        try:
            author = await page.evaluate('''() => {
                const selectors = [
                    '.AuthorInfo-name',
                    '.UserLink-link',
                    '.Name',
                    '[itemprop="name"]'
                ];
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
            votes = await page.evaluate('''() => {
                const el = document.querySelector('.VoteButton--up, .css-1c8urvw');
                if (el) {
                    const count = el.querySelector('[class*="count"]');
                    return count ? count.textContent.trim() : el.getAttribute('aria-label') || '';
                }
                return '';
            }''')
            result['votes'] = votes or ''
        except Exception:
            result['votes'] = ''

        try:
            date = await page.evaluate('''() => {
                const el = document.querySelector('time, .ContentItem-time');
                return el ? (el.getAttribute('datetime') || el.textContent.trim()) : '';
            }''')
            result['publish_date'] = date or ''
        except Exception:
            result['publish_date'] = ''

        result['metadata'] = {
            'platform': 'zhihu',
            'has_copyright_footer': '北京智者天下科技有限公司' in (result.get('content') or '')
        }

        return result

    def _extract_images_from_html(self, html: str) -> str:
        """从 HTML 中提取图片并转换为 Markdown 格式"""
        if not html:
            return ''
            
        import re
        
        img_pattern = re.compile(
            r'<img[^>]+src\s*=\s*["\']([^"\']+)["\'][^>]*alt\s*=\s*["\']([^"\']+)["\'][^>]*>|'
            r'<img[^>]+alt\s*=\s*["\']([^"\']+)["\'][^>]*src\s*=\s*["\']([^"\']+)["\'][^>]*>|'
            r'<img[^>]+src\s*=\s*["\']([^"\']+)["\'][^>]*>',
            re.IGNORECASE
        )
        
        images = []
        for match in img_pattern.finditer(html):
            if match.group(1):
                src = match.group(1)
                alt = match.group(2) or ''
            elif match.group(3):
                alt = match.group(3)
                src = match.group(4)
            else:
                src = match.group(5)
                alt = ''
            
            if src.startswith('data:'):
                continue
                
            images.append(f'![{alt}]({src})')
        
        return '\n'.join(images)

    def post_process(self, content: Dict):
        raw_text = content.get('raw_text', '')
        if raw_text:
            content['raw_text'] = ContentCleanMixin.clean_text(raw_text)

        html_content = content.get('raw_html', '')
        if html_content:
            images_md = self._extract_images_from_html(html_content)
            if images_md:
                current_content = content.get('content', '')
                content['content'] = current_content + '\n\n' + images_md

        result = super().post_process(content)
        result.metadata['is_complete'] = self._check_completeness(content)

        return result

    @staticmethod
    def _check_completeness(content: Dict) -> bool:
        text = content.get('content', '') or content.get('raw_text', '')
        if len(text) > 500:
            return '北京智者天下科技有限公司' in text
        return True