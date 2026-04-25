"""
GitHub 解析器
"""

from typing import Dict
from playwright.async_api import Page

from ..base import BaseParser
from ..models import ParserConfig


class GithubParser(BaseParser):
    platform = "github"
    platform_domains = ["github.com"]

    selectors = {
        'title': 'h1, .repository-name',
        'description': '.repository-description, p.f4',
        'stars': '.star-count, span.Counter',
        'content': '.repository-content, article.markdown-body, .readme',
        'language': '.language-color, [itemprop="programmingLanguage"]',
    }

    def __init__(self, config: ParserConfig = None):
        super().__init__(config)
        self.config.scroll_enabled = False

    async def extract_content(self, page: Page) -> Dict:
        result = {}

        try:
            title = await page.evaluate('''() => {
                const el = document.querySelector('h1 strong, h1 .js-repo-pjax-container') ||
                           document.querySelector('h1');
                if (el) return el.textContent.trim();
                const ogTitle = document.querySelector('meta[property="og:title"]');
                return ogTitle ? ogTitle.getAttribute('content').replace('GitHub - ', '') : '';
            }''')
            result['title'] = title or ''
        except Exception:
            result['title'] = ''

        try:
            description = await page.evaluate('''() => {
                const el = document.querySelector('.repository-description, p.f4');
                if (el) return el.textContent.trim();
                const aboutEl = document.querySelector('[itemprop="about"] p');
                return aboutEl ? aboutEl.textContent.trim() : '';
            }''')
            result['description'] = description or ''
            result['content'] = description or ''
        except Exception:
            result['description'] = ''
            result['content'] = ''

        try:
            stars = await page.evaluate('''() => {
                const el = document.querySelector('#repo-stars-counter-star a, #stargazers span.Counter');
                return el ? el.textContent.trim().replace(',', '') : '';
            }''')
            result['stars'] = stars or ''
        except Exception:
            result['stars'] = ''

        try:
            language = await page.evaluate('''() => {
                const el = document.querySelector('[itemprop="programmingLanguage"]');
                return el ? el.textContent.trim() : '';
            }''')
            result['language'] = language or ''
        except Exception:
            result['language'] = ''

        try:
            readme = await page.evaluate('''() => {
                const el = document.querySelector('.readme article, .Box-body .markdown-body') ||
                           document.querySelector('article.markdown-body') ||
                           document.querySelector('.markdown-body');
                if (el) return el.innerText;
                return '';
            }''')
            result['raw_text'] = readme or ''
            if readme and len(readme) > len(result.get('content', '')):
                result['content'] = readme
        except Exception:
            result['raw_text'] = ''

        try:
            author = await page.evaluate('''() => {
                const el = document.querySelector('a[rel="author"], .author');
                return el ? el.textContent.trim().replace('/', '') : '';
            }''')
            result['author'] = author or ''
        except Exception:
            result['author'] = ''

        result['metadata'] = {
            'platform': 'github',
            'stars': result.get('stars', ''),
            'language': result.get('language', ''),
        }

        return result