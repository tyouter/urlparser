"""
bb-browser 读取器

通过 bb-browser (CDP) 控制用户已登录的 Chrome 浏览器，
复用登录态获取页面内容、结构化数据和音频流。

依赖: npm install -g bb-browser
"""

import asyncio
import json
import os
import re
import shutil
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse, parse_qs, unquote

from .base import BaseFetcher, FetchResult, FetchConfig, FetchStrategy


_PLATFORM_ADAPTERS = {
    'bilibili.com': 'bilibili/video',
    'www.bilibili.com': 'bilibili/video',
    'zhihu.com': 'zhihu/question',
    'www.zhihu.com': 'zhihu/question',
    'zhuanlan.zhihu.com': 'zhihu/question',
    'xiaohongshu.com': 'xiaohongshu/note',
    'www.xiaohongshu.com': 'xiaohongshu/note',
    'mp.weixin.qq.com': 'weixin/article',
    'sspai.com': 'sspai/article',
    'www.sspai.com': 'sspai/article',
}

_CONTENT_SELECTORS = {
    'zhihu.com': '.AnswerItem .RichContent-inner, .Post-RichTextContainer, .RichText',
    'www.zhihu.com': '.AnswerItem .RichContent-inner, .Post-RichTextContainer, .RichText',
    'zhuanlan.zhihu.com': '.Post-RichTextContainer, .RichText',
    'mp.weixin.qq.com': '#js_content, .rich_media_content',
    'xiaohongshu.com': '.note-text, .desc',
    'www.xiaohongshu.com': '.note-text, .desc',
    'sspai.com': '.article-content, .content',
    'www.sspai.com': '.article-content, .content',
    'ifeng.com': '[class*="artical"], [class*="article"], [class*="content"]',
    'auto.ifeng.com': '[class*="artical"], [class*="article"], [class*="content"]',
    'www.ifeng.com': '[class*="artical"], [class*="article"], [class*="content"]',
}

_TITLE_SELECTORS = {
    'mp.weixin.qq.com': '#activity-name, .rich_media_title',
    'zhuanlan.zhihu.com': '.Post-Title, .Post-RichTextContainer h1',
    'sspai.com': '.article-title, h1',
    'www.sspai.com': '.article-title, h1',
}

_HIGH_SECURITY_DOMAINS = [
    'zhihu.com',
    'xiaohongshu.com',
    'mp.weixin.qq.com',
]


class BbBrowserFetcher(BaseFetcher):
    """
    bb-browser 读取器

    通过 CDP 控制用户已登录的 Chrome 浏览器，
    复用登录态获取页面内容和结构化数据。

    特性:
    - 复用用户浏览器登录态
    - 获取结构化 JSON 数据（比 HTML 解析更精准）
    - 自动匹配平台 adapter
    - Bilibili 音频流下载（带登录态的媒体获取）
    - 带登录态的 HTTP 请求 (bb-browser fetch)
    - CDP eval fallback (open + eval 获取页面内容)

    依赖:
    - npm install -g bb-browser
    - bb-browser daemon 需运行
    - ffmpeg (音频转换)
    """

    strategy = FetchStrategy.BB_BROWSER

    def __init__(self, config: Optional[FetchConfig] = None):
        super().__init__(config)
        self._bb_available: Optional[bool] = None

    def _check_bb_browser(self) -> bool:
        if self._bb_available is not None:
            return self._bb_available
        self._bb_available = shutil.which('bb-browser') is not None
        return self._bb_available

    def _is_daemon_error(self, err: str) -> bool:
        return 'Chrome not connected' in err or 'CDP' in err or 'Daemon HTTP 503' in err

    async def _try_restart_daemon(self) -> bool:
        try:
            out, err, code = await self._run_exec(['bb-browser', 'daemon', 'shutdown'])
            await asyncio.sleep(1)
            out, err, code = await self._run_exec(['bb-browser', 'tab', 'list'])
            return code == 0
        except Exception:
            return False

    async def _run_exec(self, cmd: List[str]) -> Tuple[str, str, int]:
        """Run bb-browser command. On Windows, use shell=True for .cmd wrappers."""
        import sys
        if sys.platform == 'win32':
            quoted = ' '.join(f'"{c}"' if ' ' in c or '&' in c or '?' in c else c for c in cmd)
            proc = await asyncio.create_subprocess_shell(
                quoted,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        stdout, stderr = await proc.communicate()
        out = stdout.decode('utf-8', errors='replace').strip()
        err = stderr.decode('utf-8', errors='replace').strip()
        return out, err, proc.returncode or 0

    async def _run_bb_browser(self, adapter: str, args: List[str]) -> Dict[str, Any]:
        cmd = ['bb-browser', 'site', adapter] + args + ['--json']
        out, err, code = await self._run_exec(cmd)

        if code != 0:
            raise RuntimeError(f"bb-browser exited {code}: {err}")

        if not out:
            raise RuntimeError("bb-browser returned empty output")

        return json.loads(out)

    async def bb_fetch(self, url: str) -> Dict[str, Any]:
        """
        使用 bb-browser fetch 发送带登录态的 HTTP 请求

        Args:
            url: 请求 URL

        Returns:
            JSON 响应数据
        """
        cmd = ['bb-browser', 'fetch', url, '--json']
        out, err, code = await self._run_exec(cmd)

        if code != 0:
            raise RuntimeError(f"bb-browser fetch failed ({code}): {err}")

        if not out:
            raise RuntimeError("bb-browser fetch returned empty output")

        return json.loads(out)

    async def bb_eval(self, js_expr: str) -> Any:
        """
        使用 bb-browser eval 在当前页面执行 JavaScript

        Args:
            js_expr: JavaScript 表达式

        Returns:
            执行结果
        """
        cmd = ['bb-browser', 'eval', js_expr, '--json']
        out, err, code = await self._run_exec(cmd)

        if code != 0:
            raise RuntimeError(f"bb-browser eval failed ({code}): {err}")

        if not out:
            raise RuntimeError("bb-browser eval returned empty output")

        data = json.loads(out)
        if data.get('success'):
            return data.get('data', {}).get('result')
        raise RuntimeError(f"bb-browser eval error: {data.get('error', 'unknown')}")

    async def bb_open_and_read(self, url: str) -> Tuple[str, str, str]:
        """
        打开 URL 并读取页面标题、正文内容和 HTML

        Args:
            url: 目标 URL

        Returns:
            (title, content, html) 元组
        """
        cmd = ['bb-browser', 'open', url]
        out, err, code = await self._run_exec(cmd)

        if code != 0:
            raise RuntimeError(f"bb-browser open failed ({code}): {err}")

        await asyncio.sleep(2)

        domain = urlparse(url).netloc.lower()

        title = ''
        title_selector = _TITLE_SELECTORS.get(domain)
        if title_selector:
            try:
                js = f"document.querySelector('{title_selector}')?.innerText"
                result = await self.bb_eval(js)
                title = str(result) if isinstance(result, str) else ''
            except Exception:
                pass
        if not title:
            try:
                result = await self.bb_eval("document.title")
                title = str(result) if isinstance(result, str) else ''
            except Exception:
                pass

        selector = _CONTENT_SELECTORS.get(domain, 'body')

        if 'mp.weixin.qq.com' in domain:
            content, html = await self._read_weixin_content(selector)
        else:
            content = ''
            try:
                js = f"document.querySelector('{selector}').innerText"
                result = await self.bb_eval(js)
                content = str(result) if isinstance(result, str) else ''
            except Exception:
                try:
                    result = await self.bb_eval("document.body.innerText")
                    content = str(result) if isinstance(result, str) else ''
                except Exception:
                    pass

            html = ''
            try:
                js = f"document.querySelector('{selector}')?.innerHTML"
                result = await self.bb_eval(js)
                html = str(result) if isinstance(result, str) else ''
            except Exception:
                try:
                    result = await self.bb_eval("document.body.innerHTML")
                    html = str(result) if isinstance(result, str) else ''
                except Exception:
                    pass

        return title, content, html

    async def _read_weixin_content(self, selector: str) -> Tuple[str, str]:
        _weixin_remove = [
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
        ]

        remove_js = json.dumps(_weixin_remove)

        content = ''
        try:
            js = f'''(() => {{
                const removeSelectors = {remove_js};
                const contentEl = document.querySelector('{selector}');
                if (!contentEl) return document.body.innerText;
                const clone = contentEl.cloneNode(true);
                for (const sel of removeSelectors) {{
                    const els = clone.querySelectorAll(sel);
                    els.forEach(el => el.remove());
                }}
                clone.querySelectorAll('script, style, svg, iframe, noscript').forEach(el => el.remove());
                const images = clone.querySelectorAll('img');
                images.forEach(img => {{
                    const src = img.getAttribute('data-src') || img.getAttribute('src') || '';
                    const alt = img.getAttribute('alt') || '';
                    if (src && !src.startsWith('data:')) {{
                        const span = document.createElement('span');
                        span.setAttribute('data-img-src', src);
                        span.textContent = `[图片: ${{alt || src.split('/').pop().split('?')[0].split('#')[0]}}]`;
                        img.replaceWith(span);
                    }} else {{
                        img.remove();
                    }}
                }});
                return clone.innerText;
            }})()'''
            result = await self.bb_eval(js)
            content = str(result) if isinstance(result, str) else ''
        except Exception:
            try:
                result = await self.bb_eval(f"document.querySelector('{selector}')?.innerText")
                content = str(result) if isinstance(result, str) else ''
            except Exception:
                pass

        html = ''
        try:
            js = f'''(() => {{
                const removeSelectors = {remove_js};
                const contentEl = document.querySelector('{selector}');
                if (!contentEl) return document.body ? document.body.innerHTML : '';
                const clone = contentEl.cloneNode(true);
                for (const sel of removeSelectors) {{
                    const els = clone.querySelectorAll(sel);
                    els.forEach(el => el.remove());
                }}
                clone.querySelectorAll('script, style, svg, iframe, noscript').forEach(el => el.remove());
                return clone.innerHTML;
            }})()'''
            result = await self.bb_eval(js)
            html = str(result) if isinstance(result, str) else ''
        except Exception:
            pass

        if not html:
            try:
                result = await self.bb_eval("document.body ? document.body.innerHTML : ''")
                html = str(result) if isinstance(result, str) else ''
            except Exception:
                pass

        return content, html

    async def get_bilibili_audio_url(self, bvid: str, cid: int) -> Optional[str]:
        api_url = (
            f"https://api.bilibili.com/x/player/playurl"
            f"?bvid={bvid}&cid={cid}&qn=0&fnval=16"
        )

        try:
            data = await self.bb_fetch(api_url)

            if data.get('code') != 0:
                return None

            dash = data.get('data', {}).get('dash', {})
            audio_list = dash.get('audio', [])

            if not audio_list:
                return None

            best_audio = max(audio_list, key=lambda a: a.get('bandwidth', 0))
            audio_url = best_audio.get('baseUrl') or best_audio.get('base_url')

            if not audio_url and best_audio.get('backup_url'):
                audio_url = best_audio['backup_url'][0]

            return audio_url

        except Exception:
            return None

    async def download_bilibili_audio(
        self,
        bvid: str,
        cid: int,
        output_path: str,
    ) -> bool:
        audio_url = await self.get_bilibili_audio_url(bvid, cid)
        if not audio_url:
            return False

        try:
            import subprocess

            headers = (
                "Referer: https://www.bilibili.com\r\n"
                "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )

            cmd = [
                "ffmpeg", "-y",
                "-headers", headers,
                "-i", audio_url,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                output_path,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=600,
            )

            return os.path.exists(output_path) and os.path.getsize(output_path) > 0

        except Exception:
            return False

    @staticmethod
    def _extract_adapter_and_args(url: str) -> Optional[Tuple[str, List[str]]]:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path

        adapter = _PLATFORM_ADAPTERS.get(domain)
        if not adapter:
            for d, a in _PLATFORM_ADAPTERS.items():
                if domain.endswith(d) or d in domain:
                    adapter = a
                    break
        if not adapter:
            return None

        args: List[str] = []

        if 'bilibili.com' in domain:
            match = re.search(r'/video/(BV[\w]+)', path)
            if match:
                args = [match.group(1)]
            else:
                qs = parse_qs(parsed.query)
                for key in ['bvid', 'aid']:
                    if key in qs:
                        args = [qs[key][0]]
                        break

        elif 'zhihu.com' in domain:
            if 'zhuanlan.zhihu.com' in domain:
                match = re.search(r'/p/(\d+)', path)
                if match:
                    args = [match.group(1)]
            else:
                match = re.search(r'/question/(\d+)', path)
                if match:
                    args = [match.group(1)]
                else:
                    match = re.search(r'/answer/(\d+)', path)
                    if match:
                        args = [match.group(1)]

        elif 'xiaohongshu.com' in domain:
            decoded = unquote(url)
            match = re.search(r'/explore/([a-f0-9]+)', decoded)
            if not match:
                match = re.search(r'/discovery/item/([a-f0-9]+)', decoded)
            if match:
                args = [match.group(1)]

        elif 'mp.weixin.qq.com' in domain:
            args = [url]

        elif 'sspai.com' in domain:
            match = re.search(r'/post/(\d+)', path)
            if match:
                args = [match.group(1)]

        if not args:
            return None

        return adapter, args

    @staticmethod
    def _requires_enhanced_access(url: str) -> bool:
        domain = urlparse(url).netloc.lower()
        return any(s in domain for s in _HIGH_SECURITY_DOMAINS)

    @staticmethod
    def _parse_bb_result(bb_data: Dict[str, Any], url: str) -> FetchResult:
        success = bb_data.get('success', False)
        data = bb_data.get('data', {})
        error = bb_data.get('error', '')

        if not success:
            return FetchResult(
                url=url,
                strategy=FetchStrategy.BB_BROWSER,
                success=False,
                error=error or 'bb-browser returned success=false',
            )

        title = ''
        text = ''
        html = ''
        metadata: Dict[str, Any] = {'bb_browser': True}

        if 'bvid' in data:
            title = data.get('title', '')
            desc = data.get('description', '')
            author = data.get('author', '')
            duration = data.get('duration_text', '')
            stat = data.get('stat', {})
            parts = []
            if title:
                parts.append(f"# {title}")
            if author:
                parts.append(f"作者: {author}")
            if duration:
                parts.append(f"时长: {duration}")
            if stat:
                view = stat.get('view', 0)
                like = stat.get('like', 0)
                coin = stat.get('coin', 0)
                parts.append(f"播放: {view} | 点赞: {like} | 投币: {coin}")
            if desc:
                parts.append(f"\n## 简介\n{desc}")
            text = '\n'.join(parts)
            metadata.update({
                'platform': 'bilibili',
                'bvid': data.get('bvid'),
                'aid': data.get('aid'),
                'duration': data.get('duration'),
                'author': author,
                'stat': stat,
                'pages': data.get('pages', []),
                'url': data.get('url', url),
            })

        elif 'question' in data or 'answers' in data:
            q = data.get('question', data)
            title = q.get('title', '')
            parts = []
            if title:
                parts.append(f"# {title}")
            answers = data.get('answers', [])
            if isinstance(answers, list):
                for i, ans in enumerate(answers[:5], 1):
                    a_author = ans.get('author', {}).get('name', '') if isinstance(ans.get('author'), dict) else ''
                    a_content = ans.get('excerpt', ans.get('content', ''))
                    parts.append(f"\n## 回答 {i}" + (f" - {a_author}" if a_author else ''))
                    parts.append(a_content)
            text = '\n'.join(parts)
            metadata.update({
                'platform': 'zhihu',
                'question_id': q.get('id'),
                'answer_count': q.get('answer_count', len(answers)),
            })

        elif 'note_card' in data or 'title' in data:
            title = data.get('title', data.get('note_card', {}).get('title', ''))
            desc = data.get('desc', data.get('note_card', {}).get('desc', ''))
            parts = []
            if title:
                parts.append(f"# {title}")
            if desc:
                parts.append(f"\n{desc}")
            text = '\n'.join(parts)
            metadata.update({
                'platform': 'xiaohongshu',
                'note_id': data.get('note_id', data.get('id', '')),
            })

        else:
            title = data.get('title', '')
            content = data.get('content', data.get('text', data.get('description', '')))
            if not content:
                content = json.dumps(data, ensure_ascii=False, indent=2)
            html = ''
            # If content looks like HTML, preserve it for further markdown/image processing
            if isinstance(content, str) and re.search(r'<\w+[^>]*>', content):
                html = content
                # Also extract plain text for the text field
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(content, 'lxml')
                    plain = soup.get_text(separator='\n')
                    text = f"# {title}\n\n{plain}" if title else plain
                except Exception:
                    text = f"# {title}\n\n{content}" if title else content
            else:
                text = f"# {title}\n\n{content}" if title else content
            metadata['raw_data'] = data

        return FetchResult(
            url=url,
            text=text,
            title=title,
            html=html,
            status_code=200,
            strategy=FetchStrategy.BB_BROWSER,
            success=True,
            metadata=metadata,
        )

    async def fetch(self, url: str, **kwargs) -> FetchResult:
        if not self._check_bb_browser():
            return FetchResult(
                url=url,
                strategy=FetchStrategy.BB_BROWSER,
                success=False,
                error='bb-browser not installed. Run: npm install -g bb-browser',
            )

        adapter_args = self._extract_adapter_and_args(url)
        if not adapter_args:
            return await self._fetch_via_open_and_read(url)

        adapter, args = adapter_args

        try:
            bb_data = await self._run_bb_browser(adapter, args)
            result = self._parse_bb_result(bb_data, url)
            if result.success and result.text and len(result.text) > 50:
                return result
        except Exception as e:
            err_str = str(e)
            if self._is_daemon_error(err_str):
                restarted = await self._try_restart_daemon()
                if restarted:
                    try:
                        bb_data = await self._run_bb_browser(adapter, args)
                        result = self._parse_bb_result(bb_data, url)
                        if result.success and result.text and len(result.text) > 50:
                            return result
                    except Exception:
                        pass

        return await self._fetch_via_open_and_read(url)

    async def _fetch_via_open_and_read(self, url: str) -> FetchResult:
        """
        Fallback: 通过 bb-browser open + eval 获取页面内容

        适用于:
        - adapter 不存在的平台 (如微信公众号)
        - adapter 失败的情况 (如知乎回答页)
        """
        try:
            title, content, html = await self.bb_open_and_read(url)

            if not content or not content.strip():
                return FetchResult(
                    url=url,
                    strategy=FetchStrategy.BB_BROWSER,
                    success=False,
                    error='bb-browser open+eval returned empty content',
                )

            domain = urlparse(url).netloc.lower()
            platform = 'unknown'
            if 'bilibili.com' in domain:
                platform = 'bilibili'
            elif 'zhihu.com' in domain:
                platform = 'zhihu'
            elif 'xiaohongshu.com' in domain:
                platform = 'xiaohongshu'
            elif 'mp.weixin.qq.com' in domain:
                platform = 'weixin'
            elif 'sspai.com' in domain:
                platform = 'sspai'

            text_parts = []
            if title:
                text_parts.append(f"# {title}")
            text_parts.append(f"\n{content}")
            text = '\n'.join(text_parts)

            return FetchResult(
                url=url,
                text=text,
                title=title,
                html=html,
                status_code=200,
                strategy=FetchStrategy.BB_BROWSER,
                success=True,
                metadata={
                    'bb_browser': True,
                    'bb_method': 'open_and_read',
                    'platform': platform,
                },
            )
        except Exception as e:
            err_str = str(e)
            if self._is_daemon_error(err_str):
                restarted = await self._try_restart_daemon()
                if restarted:
                    try:
                        title, content, html = await self.bb_open_and_read(url)
                        if content and content.strip():
                            domain = urlparse(url).netloc.lower()
                            platform = 'unknown'
                            if 'bilibili.com' in domain:
                                platform = 'bilibili'
                            elif 'zhihu.com' in domain:
                                platform = 'zhihu'
                            elif 'xiaohongshu.com' in domain:
                                platform = 'xiaohongshu'
                            elif 'mp.weixin.qq.com' in domain:
                                platform = 'weixin'
                            elif 'sspai.com' in domain:
                                platform = 'sspai'
                            text_parts = []
                            if title:
                                text_parts.append(f"# {title}")
                            text_parts.append(f"\n{content}")
                            text = '\n'.join(text_parts)
                            return FetchResult(
                                url=url,
                                text=text,
                                title=title,
                                html=html,
                                status_code=200,
                                strategy=FetchStrategy.BB_BROWSER,
                                success=True,
                                metadata={
                                    'bb_browser': True,
                                    'bb_method': 'open_and_read',
                                    'platform': platform,
                                },
                            )
                    except Exception:
                        pass
            return FetchResult(
                url=url,
                strategy=FetchStrategy.BB_BROWSER,
                success=False,
                error=f'bb-browser open+eval failed: {e}',
            )

    async def close(self):
        pass
