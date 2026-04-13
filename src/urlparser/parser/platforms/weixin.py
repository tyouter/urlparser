"""
微信公众号 (Weixin) 解析器
"""

from typing import Dict
from playwright.async_api import Page

from ..base import ArticleParser
from ..models import ParserConfig
from ..mixins.content_clean import ContentCleanMixin


class WeixinParser(ArticleParser):
    platform = "weixin"
    platform_domains = ["weixin.qq.com", "mp.weixin.qq.com"]

    selectors = {
        'title': '#activity-name, .rich_media_title',
        'content': '#js_content, .rich_media_content',
        'author': '#js_name, .rich_media_meta_nickname',
        'date': '#publish_time, .rich_media_meta_date',
        'account': '#js_profile_qrcode .profile_nickname',
    }

    def __init__(self, config: ParserConfig = None):
        super().__init__(config)
        self.config.scroll_enabled = True

    async def extract_content(self, page: Page) -> Dict:
        result = {}

        try:
            title = await page.evaluate('''() => {
                const el = document.querySelector('#activity-name') ||
                           document.querySelector('.rich_media_title');
                return el ? el.textContent.trim() : '';
            }''')
            result['title'] = title or ''
        except Exception:
            result['title'] = ''

        try:
            content = await page.evaluate('''() => {
                const el = document.querySelector('#js_content') ||
                           document.querySelector('.rich_media_content');
                if (el) {
                    const images = el.querySelectorAll('img');
                    images.forEach(img => {
                        const alt = img.getAttribute('alt') || '';
                        img.replaceWith(`[图片: ${alt}]`);
                    });
                    return el.innerText;
                }
                return document.body.innerText;
            }''')
            result['content'] = content or ''
            result['raw_text'] = content or ''
        except Exception:
            result['content'] = ''
            result['raw_text'] = ''

        try:
            author = await page.evaluate('''() => {
                const el = document.querySelector('#js_name') ||
                           document.querySelector('.rich_media_meta_nickname');
                return el ? el.textContent.trim() : '';
            }''')
            result['author'] = author or ''
        except Exception:
            result['author'] = ''

        try:
            date = await page.evaluate('''() => {
                const el = document.querySelector('#publish_time') ||
                           document.querySelector('.rich_media_meta_date');
                return el ? (el.getAttribute('content') || el.textContent.trim()) : '';
            }''')
            result['publish_date'] = date or ''
        except Exception:
            result['publish_date'] = ''

        try:
            account = await page.evaluate('''() => {
                const el = document.querySelector('#js_profile_qrcode .profile_nickname');
                return el ? el.textContent.trim() : '';
            }''')
            result['account_name'] = account or ''
        except Exception:
            result['account_name'] = ''

        result['metadata'] = {
            'platform': 'weixin',
            'account': result.get('account_name', ''),
        }

        return result

    def post_process(self, content: Dict):
        raw_text = content.get('raw_text', '')
        if raw_text:
            content['raw_text'] = ContentCleanMixin.clean_text(raw_text)

        result = super().post_process(content)

        text = content.get('content', '') or content.get('raw_text', '')
        result.metadata['is_deleted'] = any(indicator in text for indicator in [
            '该内容已被发布者删除',
            '该公众号已被封禁',
            '此内容因违规无法查看'
        ])

        return result