"""
小红书 (Xiaohongshu) 解析器

主方案: xhshow API 签名 + 直接 HTTP 请求（快速、稳定）
降级方案: Playwright 浏览器渲染（获取 xsec_token 或直接提取 SSR 数据）
"""

import json
import re
import urllib.parse
from typing import Dict, Optional
from playwright.async_api import Page
import asyncio

from ..base import ArticleParser
from ..models import ParserConfig
from ..mixins.content_quality import ContentQualityMixin
from ..mixins.content_clean import ContentCleanMixin
from ...cookies_manager import CookieManager


_XHS_API_BASE = "https://edith.xiaohongshu.com"
_FEED_URI = "/api/sns/web/v1/feed"
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"


def _extract_note_id(url: str) -> Optional[str]:
    patterns = [
        r'/explore/([a-f0-9]{24})',
        r'/discovery/item/([a-f0-9]{24})',
        r'/note/([a-f0-9]{24})',
        r'/search_result/.*?note_id=([a-f0-9]{24})',
        r'xhslink\.com/(\w+)',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def _extract_xsec_token(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    tokens = params.get('xsec_token', [])
    return tokens[0] if tokens else ''


def _extract_xsec_source(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    sources = params.get('xsec_source', [])
    return sources[0] if sources else 'pc_share'


class XiaohongshuParser(ArticleParser):
    platform = "xiaohongshu"
    platform_domains = ["xiaohongshu.com", "xhslink.com"]

    selectors = {
        'title': '.title, .note-content-title, h1',
        'content': '.note-text, .desc, .content',
        'author': '.user-name, .author-name, .username',
    }

    def __init__(self, config: ParserConfig = None):
        super().__init__(config)
        self.config.scroll_enabled = True
        self.config.dismiss_popups = True
        self._cookie_manager = CookieManager()
        self._xhshow = None

    def _get_xhshow(self):
        if self._xhshow is None:
            try:
                from xhshow import Xhshow
                self._xhshow = Xhshow()
            except ImportError:
                return None
        return self._xhshow

    def _get_cookies_dict(self) -> Dict[str, str]:
        cookies = self._cookie_manager.get_cookies("xiaohongshu")
        if not cookies:
            return {}
        return {c['name']: c['value'] for c in cookies}

    async def fetch(self, url: str):
        from ..models import ParseResult

        note_id = _extract_note_id(url)
        if not note_id:
            return await self._fallback_playwright(url)

        xsec_token = _extract_xsec_token(url)
        xsec_source = _extract_xsec_source(url)

        api_result = await self._try_api_parse(note_id, xsec_token, xsec_source, url)
        if api_result and api_result.fetch_success:
            return api_result

        if not xsec_token:
            token = await self._get_xsec_token_via_homefeed(note_id)
            if token:
                api_result = await self._try_api_parse(note_id, token, 'pc_share', url)
                if api_result and api_result.fetch_success:
                    return api_result

        return ParseResult(
            url=url,
            platform=self.platform,
            fetch_success=False,
            error="笔记需要 xsec_token 才能访问，请提供完整的小红书分享链接（包含 xsec_token 参数）",
            metadata={"platform": "xiaohongshu", "note_id": note_id, "parse_method": "none"},
        )

    async def _try_api_parse(self, note_id: str, xsec_token: str, xsec_source: str, original_url: str):
        from ..models import ParseResult

        xhshow = self._get_xhshow()
        if xhshow is None:
            return None

        cookies_dict = self._get_cookies_dict()
        if not cookies_dict.get('a1') or not cookies_dict.get('web_session'):
            return None

        try:
            import requests as req
        except ImportError:
            return None

        payload = {
            "source_note_id": note_id,
            "image_scenes": ["CRD_WM_WEBP"],
            "xsec_source": xsec_source,
            "xsec_token": xsec_token,
        }

        try:
            headers = xhshow.sign_headers_post(
                uri=_FEED_URI,
                cookies=cookies_dict,
                payload=payload,
            )
        except Exception:
            return None

        headers.update({
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
            "Origin": "https://www.xiaohongshu.com",
            "Referer": "https://www.xiaohongshu.com/",
        })

        try:
            body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
            resp = req.post(
                f"{_XHS_API_BASE}{_FEED_URI}",
                headers=headers,
                cookies=cookies_dict,
                data=body.encode(),
                timeout=15,
            )
            data = resp.json()
        except Exception:
            return None

        if not data.get("success"):
            return None

        code = data.get("code")
        if code == 300031:
            return None

        items = data.get("data", {}).get("items", [])
        if not items:
            return None

        note_card = items[0].get("note_card", {})
        if not note_card:
            return None

        title = note_card.get("title", "") or ""
        desc = note_card.get("desc", "") or ""
        author = note_card.get("user", {}).get("nickname", "") or ""
        note_type = note_card.get("type", "")

        content_parts = []
        if title:
            content_parts.append(title)
        if desc:
            content_parts.append(desc)
        content = "\n\n".join(content_parts)

        if len(content) < 10:
            return None

        content = ContentCleanMixin.clean_text(content)

        return ParseResult(
            url=original_url,
            platform=self.platform,
            title=title,
            content=content,
            raw_text=content,
            author=author,
            fetch_success=True,
            metadata={
                "platform": "xiaohongshu",
                "note_type": note_type,
                "note_id": note_id,
                "parse_method": "xhshow_api",
            },
        )

    async def _get_xsec_token_via_homefeed(self, note_id: str) -> Optional[str]:
        xhshow = self._get_xhshow()
        if xhshow is None:
            return None

        cookies_dict = self._get_cookies_dict()
        if not cookies_dict.get('a1') or not cookies_dict.get('web_session'):
            return None

        try:
            import requests as req
        except ImportError:
            return None

        for page_num in range(3):
            try:
                payload = {
                    "cursor_score": "",
                    "num": 20,
                    "refresh_type": 1 if page_num == 0 else 2,
                    "note_index": page_num * 20,
                    "unread_begin_note_id": "",
                    "ends": [],
                }
                headers = xhshow.sign_headers_post(
                    uri="/api/sns/web/v1/homefeed",
                    cookies=cookies_dict,
                    payload=payload,
                )
                headers.update({
                    "Content-Type": "application/json",
                    "User-Agent": _USER_AGENT,
                    "Origin": "https://www.xiaohongshu.com",
                    "Referer": "https://www.xiaohongshu.com/",
                })
                body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
                resp = req.post(
                    "https://edith.xiaohongshu.com/api/sns/web/v1/homefeed",
                    headers=headers,
                    cookies=cookies_dict,
                    data=body.encode(),
                    timeout=15,
                )
                data = resp.json()
                items = data.get("data", {}).get("items", [])

                for item in items:
                    if item.get("id") == note_id:
                        return item.get("xsec_token", "")

            except Exception:
                continue

        return None

    async def _fallback_playwright(self, url: str):
        await self._ensure_browser()
        page = await self.browser.new_page()
        try:
            result = await self._fetch_with_page(page, url)
            if result.fetch_success and result.metadata is not None:
                result.metadata['parse_method'] = 'playwright'
            return result
        finally:
            await page.close()

    async def _ensure_browser(self):
        if not self.config.cookies_file:
            cookies = self._cookie_manager.get_cookies("xiaohongshu")
            if cookies:
                cookies_path = self._cookie_manager.get_cookies_path("xiaohongshu")
                self.config.cookies_file = str(cookies_path)
        await super()._ensure_browser()

    async def _fetch_with_page(self, page: Page, url: str):
        if 'redirectPath' in url:
            actual_url = await self._handle_redirect(page, url)
        else:
            actual_url = url

        if 'discovery/item' in actual_url:
            actual_url = actual_url.replace('discovery/item', 'explore')

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
        await asyncio.sleep(2)

        try:
            is_login_page = await page.evaluate('''() => {
                const loginBtn = document.querySelector('.login-btn, [class*="login"]');
                const pageText = document.body.innerText || '';
                return pageText.includes('手机号登录') || pageText.includes('扫码登录');
            }''')

            if is_login_page:
                close_selectors = [
                    '.close-circle', '.close-btn', '[class*="close"]',
                    '.login-container .close', '.overlay .close',
                    'button[aria-label="Close"]', '.modal-close',
                ]
                for sel in close_selectors:
                    try:
                        btn = await page.query_selector(sel)
                        if btn and await btn.is_visible():
                            await btn.click()
                            await asyncio.sleep(2)
                            break
                    except Exception:
                        continue

                try:
                    await page.keyboard.press('Escape')
                    await asyncio.sleep(1)
                except Exception:
                    pass

                await asyncio.sleep(3)
        except Exception:
            pass

    async def extract_content(self, page: Page) -> Dict:
        result = {}

        ssr_data = await self._extract_from_initial_state(page)

        if ssr_data:
            result.update(ssr_data)
        else:
            result.update(await self._extract_from_dom(page))

        result['metadata'] = {'platform': 'xiaohongshu'}
        return result

    async def _extract_from_initial_state(self, page: Page) -> Dict:
        try:
            data = await page.evaluate('''() => {
                if (typeof window.__INITIAL_STATE__ === 'undefined') return null;
                const state = window.__INITIAL_STATE__;
                const noteMap = state && state.note && state.note.noteDetailMap;
                if (!noteMap) return null;
                const keys = Object.keys(noteMap);
                if (keys.length === 0) return null;
                const note = noteMap[keys[0]].note;
                if (!note) return null;
                return {
                    title: note.title || '',
                    desc: note.desc || '',
                    nickname: (note.user && note.user.nickname) || '',
                };
            }''')

            if not data:
                return {}

            title = data.get('title', '') or ''
            desc = data.get('desc', '') or ''
            author = data.get('nickname', '') or ''

            content_parts = []
            if title:
                content_parts.append(title)
            if desc:
                content_parts.append(desc)

            content = '\n\n'.join(content_parts)

            if len(content) < 10:
                return {}

            return {
                'title': title,
                'content': content,
                'raw_text': content,
                'author': author,
            }
        except Exception:
            return {}

    async def _extract_from_dom(self, page: Page) -> Dict:
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
                return mainContent ? mainContent.innerText : '';
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

        return result

    def post_process(self, content: Dict):
        raw_text = content.get('raw_text', '')
        if raw_text:
            content['raw_text'] = ContentCleanMixin.clean_text(raw_text)

        result = super().post_process(content)

        text = content.get('content', '') or content.get('raw_text', '')
        result.metadata['is_access_restricted'] = ContentQualityMixin.is_access_restricted(text, 'xiaohongshu')

        return result
