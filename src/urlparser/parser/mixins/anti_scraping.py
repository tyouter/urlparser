"""
反爬虫处理 Mixin
"""

import asyncio
import urllib.parse
from playwright.async_api import Page


class AntiScrapingMixin:

    LOGIN_POPUP_SELECTORS = [
        '.Modal-closeButton',
        '[class*="close"]',
        'button[aria-label="关闭"]',
        '.css-1u4r8cb',
        '.login-container .close',
        '#login-container .close',
        'svg[class*="close"]',
    ]

    EXPAND_SELECTORS = [
        'button[class*="ExpandButton"]',
        'button:has-text("阅读全文")',
        'span:has-text("阅读全文")',
        '[class*="expand"]:has-text("全文")',
        '.read-more',
        '[class*="show-all"]',
        '[class*="expand-content"]',
    ]

    EXPAND_TEXTS = ['阅读全文', '展开', '查看全部', 'Show more', 'Read more']

    @staticmethod
    async def close_login_popup(page: Page):
        for selector in AntiScrapingMixin.LOGIN_POPUP_SELECTORS:
            try:
                close_btn = await page.query_selector(selector)
                if close_btn and await close_btn.is_visible():
                    await close_btn.click()
                    await asyncio.sleep(0.5)
                    break
            except Exception:
                continue

        try:
            await page.evaluate('document.body.click()')
            await asyncio.sleep(0.3)
            await page.keyboard.press('Escape')
            await asyncio.sleep(0.3)
        except Exception:
            pass

    @staticmethod
    async def expand_full_text(page: Page):
        for selector in AntiScrapingMixin.EXPAND_SELECTORS:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(0.5)
            except Exception:
                continue

        for text in AntiScrapingMixin.EXPAND_TEXTS:
            try:
                btn = page.get_by_text(text, exact=True)
                if await btn.count() > 0:
                    first = btn.first
                    if await first.is_visible():
                        await first.click()
                        await asyncio.sleep(0.5)
                        break
            except Exception:
                continue

    @staticmethod
    async def handle_xiaohongshu_redirect(page: Page, url: str) -> str:
        if 'redirectPath' not in url:
            return url

        await page.goto(
            'https://www.xiaohongshu.com',
            timeout=60000,
            wait_until='domcontentloaded'
        )
        await asyncio.sleep(3)

        actual_url = 'https://www.xiaohongshu.com' + urllib.parse.unquote(
            url.split('redirectPath=')[1].split('&')[0]
        )

        return actual_url

    @staticmethod
    def is_login_blocked(content: str, platform: str) -> bool:
        if platform == 'zhihu':
            return any(indicator in content for indicator in [
                '安全验证 - 知乎', '登录知乎'
            ])

        if platform == 'xiaohongshu':
            return any(indicator in content for indicator in [
                '登录后推荐', '扫码登录', '手机号登录',
                '《用户协议》', '《隐私政策》'
            ])

        return False

    @staticmethod
    def is_content_complete(content: str, platform: str) -> bool:
        if platform == 'zhihu' and len(content) > 500:
            return '北京智者天下科技有限公司' in content

        return True