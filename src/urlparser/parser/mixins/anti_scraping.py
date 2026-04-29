"""
内容质量检测 Mixin

提供页面质量验证、登录弹窗关闭、全文展开等能力。
"""

import asyncio
import urllib.parse
from typing import Dict, List, Any, Optional, Tuple
from playwright.async_api import Page


class AntiScrapingMixin:

    # ---- 页面质量检测模式 ----
    BLOCKED_PATTERNS: Dict[str, List[Dict[str, Any]]] = {
        "zhihu": [
            {"type": "text_contains", "pattern": "没有知识存在的荒原"},
            {"type": "text_contains", "pattern": "你似乎来到了没有知识存在的荒原"},
            {"type": "login_wall", "login_keyword": "登录/注册", "min_count": 3, "max_text": 200},
        ],
        "xiaohongshu": [
            {"type": "title_exact", "title": "小红书 - 你的生活兴趣社区"},
            {"type": "login_and_empty", "login_keyword": "登录"},
        ],
        "weixin": [
            {"type": "login_and_empty", "login_keyword": "登录"},
        ],
    }

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

    @staticmethod
    def detect_blocked(platform: str, title: str, text: str) -> Optional[str]:
        """检测页面是否需要登录。返回 reason 字符串或 None。"""
        patterns = AntiScrapingMixin.BLOCKED_PATTERNS.get(platform, [])
        for pat in patterns:
            ptype = pat["type"]
            if ptype == "text_contains":
                if pat["pattern"] in text:
                    return f"blocked: text contains '{pat['pattern']}'"
            elif ptype == "title_exact":
                if title == pat["title"]:
                    return f"blocked: title is '{pat['title']}'"
            elif ptype == "login_wall":
                count = text.count(pat["login_keyword"])
                if count >= pat["min_count"] and len(text) < pat["max_text"]:
                    return f"blocked: login wall ({count}x '{pat['login_keyword']}', {len(text)} chars)"
            elif ptype == "login_and_empty":
                has_login = pat["login_keyword"] in text
                has_content = len(text.strip()) > 100
                if has_login and not has_content:
                    return "blocked: login prompt without real content"
        return None

    @staticmethod
    def validate_quality(title: str, text: str, min_length: int = 100) -> Tuple[bool, str]:
        """验证内容质量。返回 (passed, reason)。"""
        if not text or len(text.strip()) < min_length:
            return False, f"content too short ({len(text.strip()) if text else 0} chars, need {min_length})"
        if not title or len(title.strip()) < 2:
            return False, "title is empty or too short"
        return True, "ok"