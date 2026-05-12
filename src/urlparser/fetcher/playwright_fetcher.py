"""
Playwright 直接读取器

使用 Playwright 直接访问 URL，获取页面内容
"""

import asyncio
from typing import Optional, Tuple
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .base import BaseFetcher, FetchResult, FetchConfig, FetchStrategy


_BILIBILI_VIDEO_SELECTORS = {
    'title': '.video-title, h1[data-title], .tit',
    'author': '.up-name, .username',
    'stats': '.video-info-detail, .video-data',
    'desc': '.basic-desc-info, .desc-info-text, .video-desc',
    'main_content': '.video-container-center, .bpx-player-container, .video-info-m',
}

_WEIXIN_REMOVE_SELECTORS = [
    '#js_pc_qr_code', '#js_share_guide', '#js_sponsor_ad_area',
    '#js_tags_preview_area', '#js_tags_area', '.reward_area',
    '.reward_area_box', '.read_more_area', '.rich_media_tool_area',
    '#js_reader_bottom_area', '#js_cmt_area', '#js_comment_area',
    '.comment_area', '#js_pc_toast', '#js_image_view',
    '.profile_card_wrap', '.rich_media_area_extra',
    '#js_tags_container', '.article-bottom-area', '.share_area',
    '.tips_global', '.weui-dialog', '.weui-mask', '.weui-toast',
    '#js_bottom_banner', '.bottom_banner_area', '#js_ad_area',
    '.rich_media_ad_switch', '.js_ad_container', '.js_ad_inner',
    '#js_tags_list', '.rich_media_tool', '#js_article_edit_area',
    '.original_area', '.copyright_area', '#js_author_name',
    '.profile_arrow_wrap', '.js_wx_tap_highlight',
    '#js_content_bottom_area', '.rich_media_content_primary_bottom',
    '#js_vote_area', '.vote_area', '.js_img_popup_area',
    '#js_img_popup', '.img_popup_area', '#js_pc_close_btn',
    '.pc_close_btn', '#js_next_article_area', '.next_article_area',
    '#js_chinese_suggest', '.chinese_suggest',
    '.js_appmsg_analysis', '.appmsg_analysis',
    '#js_content_bottom_toolbar', '.rich_media_tool_area_new',
    '#js_like_old_area', '#js_like_area', '.like_area',
    '#js_wx_tap_reader', '.wx_tap_reader', '#js_media_banner',
    '.media_banner', '#js_sponsor_tips', '.sponsor_tips',
    '#js_pay_bottom', '.pay_bottom_area', '#js_pay_area',
    '.pay_area', '#js_inclue_area', '.inclue_area',
    '#js_operate_area', '.operate_area', '#js_author_card',
    '.author_card', '#js_profile_qrcode', '.profile_qrcode',
    '#js_recom_article_area', '.recom_article_area',
    '#js_recom_article_list', '.recom_article_list',
    '#js_bottom_business_area', '.bottom_business_area',
    '#js_report_area', '.report_area', '#js_pc_qr_code_show',
    '.pc_qr_code_show', '#js_subscribe_area', '.subscribe_area',
    '#js_subscribe_btn', '.subscribe_btn',
    '#js_article_follow_btn', '.article_follow_btn',
    '#js_readmore3', '.read_more_btn', '#js_reader_qrcode',
    '.reader_qrcode', '#js_font_area', '.font_area',
    '#js_content_bottom', '.content_bottom_area',
    '#js_album_area', '.album_area', '#js_album_list',
    '.album_list', '#js_source_area', '.source_area',
    '#js_content_header', '.content_header_area',
    '#js_mini_program_bottom', '.mini_program_bottom',
    '#js_redpacketcover', '.redpacketcover',
    '#js_appmsg_copyright', '.appmsg_copyright_area',
    '#js_view_source', '.view_source', '.qr_code_pc',
    '#js_share_friend', '#js_share_moments',
    '#js_share_favorite', '#js_share_weibo', '#js_share_copy',
    '.share_btn', '.js_share_btn', '#js_share_btn_area',
    '.share_btn_area', '#js_more_read_area', '.more_read_area',
    '#js_tags_recommend', '.tags_recommend',
    '#js_comment_tip', '.comment_tip', '#js_write_comment',
    '.write_comment', '#js_selected_comment', '.selected_comment',
    '#js_comment_list', '.comment_list', '#js_cmt_list', '.cmt_list',
    '#js_cmt_header', '.cmt_header', '#js_cmt_switch', '.cmt_switch',
    '#js_cmt_search', '.cmt_search', '#js_cmt_more', '.cmt_more',
    '#js_cmt_no_comment', '.cmt_no_comment', '#js_cmt_loading',
    '.cmt_loading', '#js_cmt_error', '.cmt_error',
    '#js_cmt_single', '.cmt_single', '#js_cmt_reply', '.cmt_reply',
    '#js_cmt_like', '.cmt_like', '#js_cmt_report', '.cmt_report',
    '#js_cmt_delete', '.cmt_delete', '#js_cmt_avatar', '.cmt_avatar',
    '#js_cmt_nickname', '.cmt_nickname', '#js_cmt_text', '.cmt_text',
    '#js_cmt_time', '.cmt_time', '#js_cmt_location', '.cmt_location',
    '#js_novel_card', '.novel-card', '.wx_tap_card',
    '#wx_stream_article_slide_tip', '.wx_stream_article_slide_tip',
    '#wx_expand_article_placeholder', '.wx_expand_article_button_wrap',
    '#js_cmt_container', '.rich_media_extra', '.rich_media_extra_discuss',
    '#js_minipro_dialog', '.outer_dialog',
    '#content_bottom_area', '.wx_bottom_modal_wrp', '.font-pannel-modal',
    '#js_temp_bottom_area', '.rich_media_tool_area',
    '#js_tags_preview_toast', '.article-tag__error-tips',
    '.dialog-pay',
]


class PlaywrightFetcher(BaseFetcher):
    """
    Playwright 直接读取器

    特性:
    - 兼容模式提升浏览器适配性
    - 智能滚动加载懒加载内容
    - 自动处理页面弹窗
    - 自动加载完整内容
    """

    strategy = FetchStrategy.DIRECT

    def __init__(self, config: Optional[FetchConfig] = None):
        super().__init__(config)

    async def _ensure_browser(self):
        if self._browser is not None:
            return

        self._playwright = await async_playwright().start()

        launch_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

        self._browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
            args=launch_args
        )

        self._context = await self._browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport=self.config.viewport,
            locale=self.config.locale,
            timezone_id=self.config.timezone_id
        )

        if self.config.compatibility_mode:
            await self._add_compatibility_scripts()

    async def _add_compatibility_scripts(self):
        if not self._context:
            return

        compatibility_js = """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                { name: 'Native Client', filename: 'internal-nacl-plugin' }
            ]
        });
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
        window.chrome = { runtime: {} };
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        """

        try:
            await self._context.add_init_script(compatibility_js)
        except Exception:
            pass

    async def _dismiss_popups(self, page: Page):
        close_selectors = [
            '.Modal-closeButton',
            '[class*="close"]',
            'button[aria-label="关闭"]',
            '.css-1u4r8cb',
            '.login-container .close',
            '#login-container .close',
            'svg[class*="close"]',
        ]

        for selector in close_selectors:
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

    async def _load_full_content(self, page: Page):
        expand_selectors = [
            'button[class*="ExpandButton"]',
            'button:has-text("阅读全文")',
            'span:has-text("阅读全文")',
            '[class*="expand"]:has-text("全文")',
            '.read-more',
            '[class*="show-all"]',
            '[class*="expand-content"]',
        ]

        for selector in expand_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(0.5)
            except Exception:
                continue

        for text in ['阅读全文', '展开', '查看全部', 'Show more', 'Read more']:
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

    async def _scroll_to_load_all(self, page: Page):
        last_height = await page.evaluate('document.body.scrollHeight')
        no_change_count = 0
        max_no_change = 5

        for i in range(self.config.max_scrolls):
            current_height = await page.evaluate('document.body.scrollHeight')

            if current_height == last_height:
                no_change_count += 1
                if no_change_count >= max_no_change:
                    break

            try:
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(self.config.scroll_delay)

                await page.wait_for_load_state('networkidle', timeout=8000)

                new_height = await page.evaluate('document.body.scrollHeight')

                if new_height > current_height:
                    no_change_count = 0
                    last_height = new_height
                elif new_height == current_height:
                    no_change_count += 1

            except Exception:
                break

        await page.evaluate('window.scrollTo(0, 0)')

    async def _extract_weixin_content(self, page: Page) -> Tuple[str, str, str]:
        """提取微信公众号文章的核心内容，排除底部UI噪声"""
        remove_js = str(_WEIXIN_REMOVE_SELECTORS)

        title = ''
        try:
            title = await page.evaluate('''() => {
                const el = document.querySelector('#activity-name') ||
                           document.querySelector('.rich_media_title');
                return el ? el.textContent.trim() : '';
            }''')
        except Exception:
            title = await page.title()

        text = ''
        try:
            text = await page.evaluate('''%s
            () => {
                const contentEl = document.querySelector('#js_content') ||
                                  document.querySelector('.rich_media_content') ||
                                  document.querySelector('.rich_media_area_primary') ||
                                  document.querySelector('#img-content');
                if (!contentEl) return document.body ? document.body.innerText : '';

                const clone = contentEl.cloneNode(true);

                for (const sel of removeSelectors) {
                    const els = clone.querySelectorAll(sel);
                    els.forEach(el => el.remove());
                }

                clone.querySelectorAll('script, style, svg, iframe, noscript').forEach(el => el.remove());

                const images = clone.querySelectorAll('img');
                images.forEach(img => {
                    const src = img.getAttribute('data-src') || img.getAttribute('src') || '';
                    const alt = img.getAttribute('alt') || '';
                    if (src && !src.startsWith('data:')) {
                        const span = document.createElement('span');
                        span.setAttribute('data-img-src', src);
                        span.textContent = `[图片: ${alt || src.split('/').pop().split('?')[0].split('#')[0]}]`;
                        img.replaceWith(span);
                    } else {
                        img.remove();
                    }
                });

                return clone.innerText;
            }''' % ('const removeSelectors = ' + remove_js + ';'))
        except Exception:
            text = await page.evaluate('document.body.innerText')

        html = ''
        try:
            html = await page.evaluate('''%s
            () => {
                const contentEl = document.querySelector('#js_content') ||
                                  document.querySelector('.rich_media_content') ||
                                  document.querySelector('.rich_media_area_primary') ||
                                  document.querySelector('#img-content');
                if (!contentEl) return document.body ? document.body.innerHTML : '';

                const clone = contentEl.cloneNode(true);

                for (const sel of removeSelectors) {
                    const els = clone.querySelectorAll(sel);
                    els.forEach(el => el.remove());
                }

                clone.querySelectorAll('script, style, svg, iframe, noscript').forEach(el => el.remove());

                return clone.innerHTML;
            }''' % ('const removeSelectors = ' + remove_js + ';'))
        except Exception:
            html = await page.content()

        if not html:
            html = await page.content()

        return title, text, html

    async def _extract_bilibili_video_content(self, page: Page) -> Tuple[str, str]:
        """提取B站视频页面的核心内容"""
        parts = []
        title = ''

        for selector in _BILIBILI_VIDEO_SELECTORS['title'].split(', '):
            try:
                el = await page.query_selector(selector)
                if el:
                    title = (await el.inner_text()).strip()
                    if title:
                        parts.append(f"# {title}")
                        break
            except Exception:
                continue

        for selector in _BILIBILI_VIDEO_SELECTORS['author'].split(', '):
            try:
                el = await page.query_selector(selector)
                if el:
                    author = (await el.inner_text()).strip()
                    if author:
                        parts.append(f"作者: {author}")
                        break
            except Exception:
                continue

        for selector in _BILIBILI_VIDEO_SELECTORS['stats'].split(', '):
            try:
                el = await page.query_selector(selector)
                if el:
                    stats = (await el.inner_text()).strip()
                    if stats:
                        parts.append(stats)
                        break
            except Exception:
                continue

        for selector in _BILIBILI_VIDEO_SELECTORS['desc'].split(', '):
            try:
                el = await page.query_selector(selector)
                if el:
                    desc = (await el.inner_text()).strip()
                    if desc:
                        parts.append(f"\n## 简介\n{desc}")
                        break
            except Exception:
                continue

        text = '\n'.join(parts)
        return title, text

    async def fetch(self, url: str, **kwargs) -> FetchResult:
        try:
            await self._ensure_browser()
            page = await self._context.new_page()

            try:
                timeout = kwargs.get('timeout', self.config.timeout)
                await page.goto(url, timeout=timeout, wait_until='domcontentloaded')
                await asyncio.sleep(2)

                if self.config.dismiss_popups:
                    await self._dismiss_popups(page)

                if self.config.load_full_content:
                    await self._load_full_content(page)

                if self.config.scroll_enabled:
                    await self._scroll_to_load_all(page)

                html = await page.content()
                
                domain = urlparse(url).netloc.lower()
                is_bilibili_video = 'bilibili.com' in domain and '/video/' in url
                is_weixin = 'mp.weixin.qq.com' in domain or 'weixin.qq.com' in domain
                
                if is_bilibili_video:
                    title, text = await self._extract_bilibili_video_content(page)
                    if not title:
                        title = await page.title()
                elif is_weixin:
                    title, text, html = await self._extract_weixin_content(page)
                else:
                    title = await page.title()
                    text = await page.evaluate('document.body.innerText')

                return FetchResult(
                    url=url,
                    html=html,
                    text=text or '',
                    title=title or '',
                    status_code=200,
                    strategy=self.strategy,
                    success=True,
                    metadata={'final_url': page.url}
                )

            finally:
                await page.close()

        except Exception as e:
            return FetchResult(
                url=url,
                strategy=self.strategy,
                success=False,
                error=str(e)
            )