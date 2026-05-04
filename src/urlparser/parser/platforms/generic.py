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
            html_content = await page.evaluate('''() => {
                const contentSelectors = [
                    'article', '.content', '.post-content', 'main',
                    '.article-body', '#content', '[role="main"]', '.post',
                    '.RichContent-inner', '.Post-RichText'
                ];
                for (const sel of contentSelectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        return el.innerHTML;
                    }
                }
                return '';
            }''')
            result['raw_html'] = html_content or ''
        except Exception:
            result['raw_html'] = ''

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

    def _extract_images_from_html(self, html: str) -> str:
        """从 HTML 中提取图片并转换为 Markdown 格式"""
        if not html:
            return ''
            
        import re
        
        # 匹配 img 标签，提取 src 和 alt
        img_pattern = re.compile(
            r'<img[^>]+src\s*=\s*["\']([^"\']+)["\'][^>]*alt\s*=\s*["\']([^"\']+)["\'][^>]*>|'
            r'<img[^>]+alt\s*=\s*["\']([^"\']+)["\'][^>]*src\s*=\s*["\']([^"\']+)["\'][^>]*>|'
            r'<img[^>]+src\s*=\s*["\']([^"\']+)["\'][^>]*>',
            re.IGNORECASE
        )
        
        images = []
        for match in img_pattern.finditer(html):
            # 处理三种情况
            if match.group(1):
                src = match.group(1)
                alt = match.group(2) or ''
            elif match.group(3):
                alt = match.group(3)
                src = match.group(4)
            else:
                src = match.group(5)
                alt = ''
            
            # 跳过数据 URL
            if src.startswith('data:'):
                continue
                
            images.append(f'![{alt}]({src})')
        
        return '\n'.join(images)

    def post_process(self, content: Dict):
        raw_text = content.get('raw_text', '')
        if raw_text:
            content['raw_text'] = ContentCleanMixin.remove_duplicate_lines(
                ContentCleanMixin.clean_text(raw_text)
            )

        # 提取图片
        html_content = content.get('raw_html', '')
        if html_content:
            images_md = self._extract_images_from_html(html_content)
            if images_md:
                # 将图片添加到内容末尾
                current_content = content.get('content', '')
                content['content'] = current_content + '\n\n' + images_md

        return super().post_process(content)