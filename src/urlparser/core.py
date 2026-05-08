"""
核心解析器 - 统一入口

提供最简 API: parse(url) -> ParseResult

整合 fetcher / parser / transcriber / storage 四大子包
"""

import asyncio
import time
from copy import deepcopy
from typing import Optional, List, Dict, Any

from .config import ParseConfig
from .models import (
    ParseResult, PlatformType, ContentType,
    VideoMetadata, TranscriptionResult, RetryAttempt,
    create_result_from_parser,
)
from .parser import ParserFactory
from .parser.mixins.content_quality import ContentQualityMixin
from .transcriber import FunASRTranscriber, WhisperTranscriber
from .utils import detect_platform, is_video_url
from .comprehension import ComprehensionPipeline


class UrlParser:
    """
    通用 URL 解析器

    使用方式:
        parser = UrlParser()
        result = await parser.parse("https://www.bilibili.com/video/BVxxx")

        # 带配置
        parser = UrlParser(config=ParseConfig.with_transcribe())
        result = await parser.parse(url)

        # 批量解析
        results = await parser.parse_batch(["url1", "url2"])
    """

    def __init__(self, config: Optional[ParseConfig] = None):
        self.config = config or ParseConfig()
        self._fetcher = None
        self._transcriber = None
        self._cache = None
        try:
            from .storage import ResultCache
            self._cache = ResultCache()
        except Exception:
            pass

    async def parse(
        self,
        url: str,
        config: Optional[ParseConfig] = None,
        output_dir: Optional[str] = None,
        **kwargs
    ) -> ParseResult:
        """
        解析单个 URL（主入口）

        Args:
            url: 要解析的 URL
            config: 可选配置（覆盖默认）
            output_dir: 可选输出目录（用于保存图片）
            **kwargs: 快捷参数

        Returns:
            ParseResult 统一解析结果
        """
        cfg = config or self.config

        force_refresh = kwargs.pop('force_refresh', False)

        # Check cache before parsing
        if not force_refresh and self._cache:
            try:
                cached = await self._cache.get(url)
                if cached is not None:
                    return ParseResult(**cached) if isinstance(cached, dict) else cached
            except Exception:
                pass

        if kwargs.get('enable_transcribe'):
            cfg = deepcopy(cfg)
            cfg.transcribe.enabled = True

        if kwargs.get('cookies_file'):
            cfg = deepcopy(cfg)
            cfg.browser.cookies_file = kwargs['cookies_file']

        if kwargs.get('use_user_chrome'):
            cfg = deepcopy(cfg)
            cfg.browser.use_user_chrome = True

        start_time = time.time()

        try:
            if cfg.retry.enabled:
                result = await self._parse_with_retry(url, cfg)
            else:
                result = await self._do_parse(url, cfg)
            result.parse_time = round(time.time() - start_time, 2)

            # 下载图片（如果启用）
            if cfg.image_download.enabled:
                result = UrlParser._download_images_in_content(result, cfg, output_dir)

            # Write to cache on success
            if result.fetch_success and self._cache:
                try:
                    await self._cache.set(result.to_dict(), url=url)
                except Exception:
                    pass

            return result

        except Exception as e:
            return ParseResult(
                url=url,
                platform="unknown",
                fetch_success=False,
                error=str(e),
                parse_time=round(time.time() - start_time, 2),
            )

    async def _parse_with_retry(self, url: str, config: ParseConfig) -> ParseResult:
        """带多策略回退的解析流程"""
        platform = detect_platform(url)
        is_vid = is_video_url(url)
        content_type = ContentType.VIDEO if is_vid else ContentType.ARTICLE
        platform_type = self._detect_platform_type(platform)

        retry_attempts: List[RetryAttempt] = []
        start_total = time.time()

        await self._ensure_cookies(platform)

        # --- Attempt 1: auto_select fetcher -> fallback parser ---
        attempt_start = time.time()
        try:
            result = await self._do_parse(url, config)
            elapsed = round(time.time() - attempt_start, 2)

            strategy_name = getattr(result, 'final_strategy', None) or 'auto'

            if result.fetch_success:
                blocked = ContentQualityMixin.detect_access_restriction(
                    platform, result.title, result.content
                )
                quality_ok, q_reason = ContentQualityMixin.validate_quality(
                    result.title, result.content,
                    min_length=config.retry.min_quality_length,
                    platform=platform,
                )

                if not blocked and quality_ok:
                    result.final_strategy = strategy_name
                    result.retry_attempts = retry_attempts
                    return result

                if blocked:
                    retry_attempts.append(RetryAttempt(
                        strategy=strategy_name,
                        success=False,
                        access_restriction_reason=blocked,
                        duration=elapsed,
                    ))
                else:
                    retry_attempts.append(RetryAttempt(
                        strategy=strategy_name,
                        success=False,
                        error=q_reason,
                        duration=elapsed,
                    ))
            else:
                retry_attempts.append(RetryAttempt(
                    strategy="playwright",
                    success=False,
                    error=result.error or "fetch failed",
                    duration=elapsed,
                ))
        except Exception as e:
            elapsed = round(time.time() - attempt_start, 2)
            retry_attempts.append(RetryAttempt(
                strategy="playwright",
                success=False,
                error=str(e),
                duration=elapsed,
            ))
            result = ParseResult(
                url=url, platform=platform,
                platform_type=platform_type, content_type=content_type,
                fetch_success=False, error=str(e),
            )

        # --- Retry loop with fallback strategies ---
        strategies = [
            ("playwright_extended", self._strategy_playwright_extended),
            ("bb_browser", self._strategy_bb_browser),
            ("cookie_fetcher", self._strategy_cookie_fetcher),
            ("user_chrome", self._strategy_user_chrome),
        ]

        for strategy_name, strategy_fn in strategies:
            # Check total timeout
            if time.time() - start_total > config.retry.total_timeout:
                break
            if len(retry_attempts) > config.retry.max_attempts:
                break

            attempt_start = time.time()
            try:
                fetch_result = await asyncio.wait_for(
                    strategy_fn(url, config),
                    timeout=config.retry.timeout_per_attempt,
                )
                elapsed = round(time.time() - attempt_start, 2)

                if not fetch_result or not fetch_result.success:
                    retry_attempts.append(RetryAttempt(
                        strategy=strategy_name,
                        success=False,
                        error=fetch_result.error if fetch_result else "no result",
                        duration=elapsed,
                    ))
                    continue

                # Convert FetchResult to ParseResult
                candidate = self._fetch_result_to_parse_result(
                    fetch_result, url, platform, platform_type, content_type
                )

                # Check blocked + quality
                blocked = ContentQualityMixin.detect_access_restriction(
                    platform, candidate.title, candidate.content
                )
                quality_ok, q_reason = ContentQualityMixin.validate_quality(
                    candidate.title, candidate.content,
                    min_length=config.retry.min_quality_length,
                    platform=platform,
                )

                if not blocked and quality_ok:
                    candidate.final_strategy = strategy_name
                    candidate.retry_attempts = retry_attempts

                    # Run transcription/comprehension if video
                    if is_vid and config.transcribe.enabled and candidate.fetch_success and not candidate.has_transcription:
                        candidate.transcription = await self._transcribe_audio(url, config.transcribe, platform)
                    if is_vid and config.comprehension.enabled and candidate.fetch_success:
                        candidate.comprehension = await self._run_comprehension(
                            url, config.comprehension, candidate.transcription
                        )

                    retry_attempts.append(RetryAttempt(
                        strategy=strategy_name,
                        success=True,
                        duration=elapsed,
                    ))
                    candidate.retry_attempts = retry_attempts
                    return candidate
                else:
                    if blocked:
                        retry_attempts.append(RetryAttempt(
                            strategy=strategy_name,
                            success=False,
                            access_restriction_reason=blocked,
                            duration=elapsed,
                        ))
                    else:
                        retry_attempts.append(RetryAttempt(
                            strategy=strategy_name,
                            success=False,
                            error=q_reason,
                            duration=elapsed,
                        ))

            except asyncio.TimeoutError:
                elapsed = round(time.time() - attempt_start, 2)
                retry_attempts.append(RetryAttempt(
                    strategy=strategy_name,
                    success=False,
                    error="timeout",
                    duration=elapsed,
                ))
            except Exception as e:
                elapsed = round(time.time() - attempt_start, 2)
                retry_attempts.append(RetryAttempt(
                    strategy=strategy_name,
                    success=False,
                    error=str(e),
                    duration=elapsed,
                ))

        # All retries exhausted - return best result with attempts log
        result.retry_attempts = retry_attempts
        if not result.final_strategy:
            result.final_strategy = "exhausted"

        has_restriction = any(
            a.access_restriction_reason for a in retry_attempts
        )
        if has_restriction:
            login_ok = await self._try_interactive_login(platform)
            if login_ok:
                retry_with_cookies = await self._retry_with_saved_cookies(
                    url, platform, platform_type, content_type, config
                )
                if retry_with_cookies and retry_with_cookies.fetch_success:
                    retry_with_cookies.retry_attempts = retry_attempts + [
                        RetryAttempt(strategy="interactive_login+cookie", success=True, duration=0)
                    ]
                    return retry_with_cookies

            hint = self._build_login_hint(platform)
            if hint:
                result.error = (result.error or '') + '\n' + hint

        return result

    async def _strategy_playwright_extended(self, url: str, config: ParseConfig):
        """Extended Playwright with more scrolling and longer wait."""
        from .fetcher import PlaywrightFetcher, FetchConfig
        fc = FetchConfig(
            timeout=60000,
            headless=config.browser.headless,
            compatibility_mode=config.browser.compatibility_mode,
            scroll_enabled=config.scroll.enabled,
            max_scrolls=config.scroll.max_scrolls,
            scroll_delay=config.scroll.scroll_delay,
            load_full_content=config.load_full_content,
            dismiss_popups=config.dismiss_popups,
        )
        async with PlaywrightFetcher(fc) as fetcher:
            return await fetcher.fetch(url)

    async def _strategy_bb_browser(self, url: str, config: ParseConfig):
        """CDP-controlled user Chrome via bb-browser."""
        try:
            from .fetcher import BbBrowserFetcher
        except ImportError:
            return None
        async with BbBrowserFetcher() as fetcher:
            return await fetcher.fetch(url)

    async def _strategy_cookie_fetcher(self, url: str, config: ParseConfig):
        """Playwright with cookies (auto-extract from browser if needed)."""
        cookies_file = config.browser.cookies_file

        if not cookies_file:
            from .cookies_manager import CookieManager
            platform = detect_platform(url)
            mgr = CookieManager()
            cookies_path = mgr.get_cookies_path(platform)
            if not mgr._is_valid(cookies_path):
                mgr._refresh_from_browser(platform)
            if cookies_path.exists():
                cookies_file = str(cookies_path)

        if not cookies_file:
            return None

        try:
            from .fetcher import CookieFetcher, FetchConfig
        except ImportError:
            return None
        fc = FetchConfig(
            cookies_file=cookies_file,
            headless=config.browser.headless,
            compatibility_mode=config.browser.compatibility_mode,
            scroll_enabled=config.scroll.enabled,
            max_scrolls=config.scroll.max_scrolls,
            scroll_delay=config.scroll.scroll_delay,
            load_full_content=config.load_full_content,
            dismiss_popups=config.dismiss_popups,
        )
        async with CookieFetcher(fc) as fetcher:
            return await fetcher.fetch(url)

    async def _strategy_user_chrome(self, url: str, config: ParseConfig):
        """User Chrome profile."""
        try:
            from .fetcher import UserChromeFetcher, FetchConfig
        except ImportError:
            return None
        fc = FetchConfig(
            user_data_dir=config.browser.user_data_dir,
            headless=False,
            compatibility_mode=config.browser.compatibility_mode,
            scroll_enabled=config.scroll.enabled,
            max_scrolls=config.scroll.max_scrolls,
            scroll_delay=config.scroll.scroll_delay,
            load_full_content=config.load_full_content,
            dismiss_popups=config.dismiss_popups,
        )
        async with UserChromeFetcher(fc) as fetcher:
            return await fetcher.fetch(url)

    @staticmethod
    def _fetch_result_to_parse_result(
        fr, url: str, platform: str,
        platform_type: PlatformType, content_type: ContentType
    ) -> ParseResult:
        """Convert Fetcher's FetchResult to canonical ParseResult."""
        from .fetcher import FetchResult
        if not isinstance(fr, FetchResult):
            return ParseResult(
                url=url, platform=platform,
                platform_type=platform_type, content_type=content_type,
                fetch_success=False, error="invalid fetch result type",
            )

        result = ParseResult(
            url=url,
            platform=platform,
            platform_type=platform_type,
            content_type=content_type,
            title=fr.title or "",
            content=fr.text or "",
            raw_text=fr.text or "",
            raw_html=fr.html or "",
            metadata=dict(fr.metadata) if fr.metadata else {},
            fetch_success=fr.success,
            error=fr.error,
        )

        # Extract bilibili video metadata from bb-browser structured data
        meta = fr.metadata or {}
        if 'bvid' in meta:
            stat = meta.get('stat', {})
            result.video_metadata = VideoMetadata(
                duration=str(meta.get('duration', '')),
                views=str(stat.get('view', '')),
                likes=str(stat.get('like', '')),
                coins=str(stat.get('coin', '')),
                favorites=str(stat.get('favorite', '')),
                danmaku=str(stat.get('danmaku', '')),
            )
            result.author = meta.get('author', '')

        # Convert raw_html directly to markdown with images in correct positions
        if result.raw_html and content_type == ContentType.ARTICLE:
            content_from_html = UrlParser._html_to_markdown(result.raw_html, result.url)
            if content_from_html:
                # Use the HTML-converted content which has images in correct positions
                result.content = content_from_html

        return result

    @staticmethod
    def _download_images_in_content(
        result: 'ParseResult', 
        config: 'ParseConfig', 
        output_dir: Optional[str] = None
    ) -> 'ParseResult':
        """
        下载内容中的图片
        
        Args:
            result: 解析结果
            config: 解析配置
            output_dir: 输出目录（可选）
        
        Returns:
            更新后的解析结果
        """
        if not config.image_download.enabled or not result.content:
            return result
        
        try:
            from .image_downloader import ImageDownloader
            
            downloader = ImageDownloader(config.image_download)
            processed_content, downloaded_images = downloader.process_markdown(
                markdown=result.content,
                output_dir=output_dir,
                base_url=result.url
            )
            
            if processed_content:
                result.content = processed_content
                result.metadata['downloaded_images'] = downloaded_images
            
            downloader.cleanup()
            
        except Exception as e:
            # 图片下载失败不应影响整个解析流程
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"图片下载失败: {e}")
        
        return result

    async def _do_parse(self, url: str, config: ParseConfig) -> ParseResult:
        """执行实际解析：auto_select fetcher -> fallback parser -> transcribe"""
        platform = detect_platform(url)
        is_vid = is_video_url(url)

        content_type = ContentType.VIDEO if is_vid else ContentType.ARTICLE
        platform_type = self._detect_platform_type(platform)

        parser_first_platforms = {'xiaohongshu'}

        if platform not in parser_first_platforms:
            from .fetcher.factory import FetcherFactory
            from .fetcher.base import FetchResult

            fetch_config = config.to_fetch_config()
            fetcher = FetcherFactory.auto_select(url, fetch_config)

            if fetcher is not None:
                try:
                    fr = await fetcher.fetch(url)
                    if fr and fr.success and fr.has_content:
                        result = self._fetch_result_to_parse_result(
                            fr, url, platform, platform_type, content_type
                        )

                        blocked = ContentQualityMixin.detect_access_restriction(
                            platform, result.title, result.content
                        )
                        if not blocked:
                            if is_vid and config.transcribe.enabled and result.fetch_success and not result.has_transcription:
                                result.transcription = await self._transcribe_audio(url, config.transcribe, platform)
                            if is_vid and config.comprehension.enabled and result.fetch_success:
                                result.comprehension = await self._run_comprehension(
                                    url, config.comprehension, result.transcription
                                )
                            result.final_strategy = fetcher.strategy.value
                            return result
                except Exception:
                    pass
                finally:
                    try:
                        await fetcher.close()
                    except Exception:
                        pass

        parser_config = config.to_parser_config()
        parser = ParserFactory.create(url, config=parser_config)

        try:
            parse_result = await parser.fetch(url)

            if not parse_result.fetch_success:
                return ParseResult(
                    url=url,
                    platform=platform,
                    platform_type=platform_type,
                    content_type=content_type,
                    fetch_success=False,
                    error=parse_result.error or "Parse failed",
                )

            result = create_result_from_parser(parse_result)
            result.platform_type = platform_type
            result.content_type = content_type

            if result.metadata.get('note_type') == 'video':
                result.content_type = ContentType.VIDEO
                is_vid = True

            needs_transcription = (
                is_vid
                and config.transcribe.enabled
                and result.fetch_success
                and not result.has_transcription
            )
            if needs_transcription:
                result.transcription = await self._transcribe_audio(url, config.transcribe, platform)

            if is_vid and config.comprehension.enabled and result.fetch_success:
                comprehension = await self._run_comprehension(
                    url, config.comprehension, result.transcription
                )
                result.comprehension = comprehension

            return result

        finally:
            await parser.close()

    async def _transcribe_audio(self, url: str, transcribe_config, platform: str = "") -> TranscriptionResult:
        """音频转录 - B站优先走API直取音频流，其他走通用路径"""
        try:
            from .dependency_installer import ensure_transcribe_dependencies

            if not ensure_transcribe_dependencies(auto_install=True):
                return TranscriptionResult(success=False, error="Transcription dependencies not available")

            if platform == "bilibili":
                bili_result = await self._transcribe_bilibili_via_api(url, transcribe_config)
                if bili_result and bili_result.success:
                    return bili_result

            if FunASRTranscriber.is_available():
                engine = "funasr"
                transcriber = FunASRTranscriber(
                    model_size=transcribe_config.model_size,
                    device=transcribe_config.device,
                )
            else:
                engine = "whisper"
                transcriber = WhisperTranscriber(
                    model_size=transcribe_config.model_size,
                    device=transcribe_config.device,
                )

            loop = asyncio.get_event_loop()
            t_result = await loop.run_in_executor(
                None,
                lambda: transcriber.transcribe_from_url(
                    url,
                    language=transcribe_config.language,
                )
            )

            return TranscriptionResult(
                success=t_result.success,
                text=t_result.text,
                segments=t_result.segments,
                language=t_result.language or transcribe_config.language,
                duration=t_result.duration,
                engine=t_result.engine or engine,
                error=t_result.error,
            )

        except Exception as e:
            return TranscriptionResult(
                success=False,
                error=str(e),
            )

    async def _transcribe_bilibili_via_api(self, url: str, transcribe_config) -> TranscriptionResult:
        """B站专用转录：通过API直取音频流，比yt-dlp更快更稳"""
        import re as _re
        import tempfile
        import shutil
        from pathlib import Path as _Path

        try:
            from .dependency_installer import ensure_transcribe_dependencies
            if not ensure_transcribe_dependencies(auto_install=True):
                return TranscriptionResult(success=False, error="Transcription dependencies not available")
        except Exception:
            return TranscriptionResult(success=False, error="Transcription dependencies not available")

        bvid_match = _re.search(r'(BV[\w]+)', url)
        if not bvid_match:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.bilibili.com",
                }) as client:
                    resp = await client.head(url, timeout=10)
                    bvid_match = _re.search(r'(BV[\w]+)', str(resp.url))
            except Exception:
                pass

        if not bvid_match:
            return TranscriptionResult(success=False, error="No BV ID found", engine="funasr")

        bvid = bvid_match.group(1)

        try:
            import httpx

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
                "Referer": "https://www.bilibili.com",
            }

            async with httpx.AsyncClient(timeout=30, headers=headers) as client:
                resp = await client.get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")
                data = resp.json()

                if data.get("code") != 0:
                    return TranscriptionResult(success=False, error=f"API error: {data.get('message')}", engine="funasr")

                v = data["data"]
                cid = v.get("cid", 0)
                duration = v.get("duration", 0)

                if not cid or duration < 10:
                    return TranscriptionResult(success=False, error="Video too short or no CID", engine="funasr")

                resp2 = await client.get(
                    f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=0&fnver=0&fnval=16&fourk=0"
                )
                data2 = resp2.json()

                if data2.get("code") != 0:
                    return TranscriptionResult(success=False, error=f"Playurl error: {data2.get('message')}", engine="funasr")

                dash = data2.get("data", {}).get("dash", {})
                audio_list = dash.get("audio", [])

                if not audio_list:
                    durl_list = data2.get("data", {}).get("durl", [])
                    if durl_list:
                        audio_url = durl_list[0].get("url", "")
                    else:
                        return TranscriptionResult(success=False, error="No audio stream", engine="funasr")
                else:
                    best_audio = max(audio_list, key=lambda x: x.get("bandwidth", 0))
                    audio_url = best_audio.get("baseUrl") or best_audio.get("base_url") or best_audio.get("url", "")

                    if not audio_url:
                        backup_urls = best_audio.get("backupUrl", []) or best_audio.get("backup_url", [])
                        if backup_urls:
                            audio_url = backup_urls[0]

                if not audio_url:
                    return TranscriptionResult(success=False, error="No audio URL", engine="funasr")

                if audio_url.startswith("//"):
                    audio_url = "https:" + audio_url

            temp_dir = tempfile.mkdtemp(prefix="bili_audio_")
            try:
                raw_audio = str(_Path(temp_dir) / "audio.m4s")
                wav_audio = str(_Path(temp_dir) / "audio.wav")

                download_headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
                    "Referer": "https://www.bilibili.com",
                }

                async with httpx.AsyncClient(timeout=180, headers=download_headers, follow_redirects=True) as dl_client:
                    async with dl_client.stream("GET", audio_url) as response:
                        if response.status_code not in (200, 206):
                            return TranscriptionResult(success=False, error=f"Audio download failed: HTTP {response.status_code}", engine="funasr")
                        with open(raw_audio, "wb") as f:
                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                f.write(chunk)

                from .transcriber.base import convert_audio_for_funasr
                if not convert_audio_for_funasr(raw_audio, wav_audio):
                    return TranscriptionResult(success=False, error="Audio conversion failed", engine="funasr")

                if FunASRTranscriber.is_available():
                    transcriber = FunASRTranscriber(
                        model_size=transcribe_config.model_size,
                        device=transcribe_config.device,
                    )
                else:
                    transcriber = WhisperTranscriber(
                        model_size=transcribe_config.model_size,
                        device=transcribe_config.device,
                    )

                loop = asyncio.get_event_loop()
                t_result = await loop.run_in_executor(
                    None,
                    lambda: transcriber.transcribe(wav_audio, language=transcribe_config.language)
                )

                return TranscriptionResult(
                    success=t_result.success,
                    text=t_result.text,
                    segments=t_result.segments,
                    language=t_result.language or transcribe_config.language,
                    duration=float(duration),
                    engine=t_result.engine or "funasr",
                    error=t_result.error,
                )

            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            return TranscriptionResult(success=False, error=f"Bilibili API error: {str(e)[:200]}", engine="funasr")

    async def _run_comprehension(self, url, comp_config, transcription_result=None):
        """运行视频理解管线"""
        try:
            from .comprehension.models import (
                ComprehensionConfig as CompConfig,
                ComprehensionResult as CompResult,
            )

            config = CompConfig(
                enabled=comp_config.enabled,
                mode=comp_config.mode,
                engine=comp_config.engine,
                max_frames=comp_config.max_frames,
                scdet_threshold=comp_config.scdet_threshold,
                language=comp_config.language,
                temp_dir=comp_config.temp_dir,
            )

            loop = asyncio.get_event_loop()
            pipeline = ComprehensionPipeline(config)
            c_result = await loop.run_in_executor(
                None,
                lambda: pipeline.comprehend_from_url(url, transcription_result),
            )

            # Convert to models.ComprehensionResult
            return CompResult(
                success=c_result.success,
                mode=c_result.mode,
                visual_frames=c_result.visual_frames,
                timeline_summary=c_result.timeline_summary,
                merged_text=c_result.merged_text,
                engine=c_result.engine,
                frame_count=c_result.frame_count,
                error=c_result.error,
            )

        except Exception as e:
            from .comprehension.models import ComprehensionResult as CompResult
            return CompResult(
                success=False,
                error=str(e),
            )

    @staticmethod
    def _detect_platform_type(platform: str) -> PlatformType:
        platform_map = {
            'zhihu': PlatformType.ZHIHU,
            'bilibili': PlatformType.BILIBILI,
            'youtube': PlatformType.YOUTUBE,
            'weixin': PlatformType.WEIXIN,
            'xiaohongshu': PlatformType.XIAOHONGSHU,
            'github': PlatformType.GITHUB,
            'generic': PlatformType.GENERIC,
        }
        return platform_map.get(platform, PlatformType.UNKNOWN)

    _LOGIN_HINTS = {
        'zhihu': (
            '[提示] 知乎需要登录才能访问此内容。请尝试以下方法：\n'
            '  1. 在浏览器中登录知乎，然后重新运行\n'
            '  2. 运行: python -m urlparser.cookies_manager login zhihu\n'
            '  3. 使用 --cookies 参数指定 cookie 文件'
        ),
        'xiaohongshu': (
            '[提示] 小红书需要登录才能访问此内容。请尝试以下方法：\n'
            '  1. 在浏览器中登录小红书，然后重新运行\n'
            '  2. 运行: python -m urlparser.cookies_manager login xiaohongshu\n'
            '  3. 使用 --cookies 参数指定 cookie 文件'
        ),
        'weixin': (
            '[提示] 微信公众号文章可能需要特殊访问权限。请尝试：\n'
            '  1. 使用 --cookies 参数指定 cookie 文件\n'
            '  2. 运行: python -m urlparser.cookies_manager login weixin'
        ),
    }

    _COOKIE_REQUIRED_PLATFORMS = {'zhihu', 'xiaohongshu', 'weixin'}

    async def _ensure_cookies(self, platform: str):
        import sys
        if platform not in self._COOKIE_REQUIRED_PLATFORMS:
            return
        from .cookies_manager import CookieManager
        mgr = CookieManager()
        cookies_path = mgr.get_cookies_path(platform)
        if mgr._is_valid(cookies_path):
            return
        if not sys.stdin.isatty():
            return
        refreshed = mgr._refresh_from_browser(platform)
        if refreshed:
            return
        print(f"\n[Cookie 检查] 检测到 {platform} 无有效 cookie，正在打开浏览器登录...")
        print("请在浏览器中完成登录，然后回到终端按 Enter 继续。")
        try:
            await mgr.interactive_login(platform)
        except Exception:
            pass

    @staticmethod
    def _html_to_markdown(html: str, base_url: str = '') -> str:
        """
        将 HTML 转换为 Markdown，保持图片位置并进行内容清理
        使用 BeautifulSoup 更准确地解析 HTML
        """
        if not html:
            return ''
        from urllib.parse import urljoin, urlparse, unquote
        from bs4 import BeautifulSoup, Comment
        
        # 从 base_url 提取协议和域名
        base_scheme = ''
        base_domain = ''
        if base_url:
            parsed = urlparse(base_url)
            base_scheme = parsed.scheme
            base_domain = parsed.netloc
        
        soup = BeautifulSoup(html, 'lxml')
        
        # 1. 移除所有不需要的元素
        for element in soup.find_all(['script', 'style', 'noscript', 'svg', 'iframe', 'form']):
            element.decompose()
        
        # 2. 移除导航和侧边栏等布局元素
        for element in soup.find_all(['nav', 'aside', 'header', 'footer', 'menu']):
            element.decompose()
        
        # 3. 移除广告和推荐内容（基于 class 和 id）
        ad_keywords = ['ad', 'advert', 'banner', 'sponsor', 'promo', 'recommend', 'related', 'footer', 'sidebar', 'nav']
        for element in soup.find_all(class_=lambda x: x and any(key in str(x).lower() for key in ad_keywords)):
            element.decompose()
        
        for element in soup.find_all(id=lambda x: x and any(key in str(x).lower() for key in ad_keywords)):
            element.decompose()
        
        # 4. 移除注释
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        seen_urls = set()
        
        # 5. 处理图片
        for img in soup.find_all('img'):
            src = img.get('data-lazyload', '') or img.get('data-src', '') or img.get('src', '')
            if not src:
                img.decompose()
                continue
            
            # 检查是否从 data-lazyload 或 data-src 获取到真实 URL
            # 如果 src 是 data: URL，我们需要检查是否有 data-lazyload 或 data-src
            if src.startswith('data:'):
                # 尝试优先使用 data-lazyload 或 data-src
                real_src = img.get('data-lazyload', '') or img.get('data-src', '')
                if real_src and not real_src.startswith('data:'):
                    src = real_src
                else:
                    img.decompose()
                    continue
            
            # 补全协议相对 URL
            if src.startswith('//'):
                if base_scheme:
                    src = f'{base_scheme}:{src}'
                else:
                    src = f'https:{src}'
            # 补全相对路径 URL
            elif not src.startswith(('http://', 'https://')) and base_url:
                src = urljoin(base_url, src)
            
            # 去重
            if src in seen_urls:
                img.decompose()
                continue
            
            # 过滤小尺寸图片
            width = img.get('width', 0)
            height = img.get('height', 0)
            try:
                width = int(width) if width else 0
                height = int(height) if height else 0
            except (ValueError, TypeError):
                width = 0
                height = 0
            
            if width > 0 and height > 0 and width < 50 and height < 50:
                img.decompose()
                continue
            
            # 过滤 URL 包含广告关键词（匹配完整单词或路径段，避免误判哈希值）
            src_lower = src.lower()
            bad_keywords = ['logo', 'icon', 'qr', 'qrcode', 'avatar', 'profile', 'banner', 'tracking', 'pixel', 'stat']
            bad_keywords_with_boundaries = [
                # 匹配作为路径段或文件名的关键词，前后有 /、_、- 或 .
                '/logo/', '/logo_', '_logo.', 
                '/icon/', '/icon_', '_icon.',
                '/qr/', '/qr_', '_qr.',
                '/qrcode/', '/qrcode_', '_qrcode.',
                '/avatar/', '/avatar_', '_avatar.',
                '/profile/', '/profile_', '_profile.',
                '/banner/', '/banner_', '_banner.',
                '/tracking/', '/tracking_', '_tracking.',
                '/pixel/', '/pixel_', '_pixel.',
                '/stat/', '/stat_', '_stat.'
            ]
            # 简单检查完整路径中是否有作为独立路径段或文件名部分的关键词
            # 避免简单包含匹配，比如哈希值中的 'add' 被误判为 'ad'
            has_bad = False
            
            # 检查文件名和路径段
            parsed_url = urlparse(src_lower)
            path_parts = parsed_url.path.split('/')
            filename = path_parts[-1] if path_parts else ''
            
            # 检查文件名是否包含关键词作为前缀或后缀
            for kw in bad_keywords:
                if filename.startswith(kw + '_') or filename.endswith('_' + kw) or filename == kw or f'_{kw}_' in filename:
                    has_bad = True
                    break
                if any(part == kw or part.startswith(kw + '_') or part.endswith('_' + kw) for part in path_parts):
                    has_bad = True
                    break
            
            if has_bad:
                img.decompose()
                continue
            
            # 过滤静态资源路径
            bad_paths = ['/static/', '/assets/', '/img/icon', '/image/icon', '/images/icon']
            if any(path in src_lower for path in bad_paths):
                img.decompose()
                continue
            
            # 检查文件名
            path = urlparse(src).path
            filename = unquote(path.split('/')[-1].lower())
            bad_patterns = ['_w100', '_w200', '_h100', '_h200', '_s.png', '_s.jpg', '_thumb', '_small']
            if any(pat in filename for pat in bad_patterns):
                img.decompose()
                continue
            
            seen_urls.add(src)
            alt = img.get('alt', '') or img.get('title', '')
            img.replace_with(f'\n\n![{alt}]({src})\n\n')
        
        # 6. 处理标题
        for i in range(6, 0, -1):
            for h in soup.find_all(f'h{i}'):
                text = h.get_text(strip=True)
                if text:
                    h.replace_with(f'\n\n{"#" * i} {text}\n\n')
                else:
                    h.decompose()
        
        # 7. 处理段落和换行
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if text:
                p.replace_with(f'{text}\n\n')
            else:
                p.decompose()
        
        for br in soup.find_all('br'):
            br.replace_with('\n')
        
        # 8. 处理链接
        for a in soup.find_all('a'):
            href = a.get('href', '')
            text = a.get_text(strip=True)
            if not text:
                a.decompose()
                continue
            
            # 补全链接 URL
            if href:
                if href.startswith('//'):
                    if base_scheme:
                        href = f'{base_scheme}:{href}'
                    else:
                        href = f'https:{href}'
                elif not href.startswith(('http://', 'https://')) and base_url:
                    href = urljoin(base_url, href)
                
                a.replace_with(f'[{text}]({href})')
            else:
                a.replace_with(text)
        
        # 9. 处理列表
        for ul in soup.find_all('ul'):
            items = []
            for li in ul.find_all('li', recursive=False):
                items.append(f'- {li.get_text(strip=True)}')
            if items:
                ul.replace_with('\n'.join(items) + '\n\n')
            else:
                ul.decompose()
        
        for ol in soup.find_all('ol'):
            items = []
            for idx, li in enumerate(ol.find_all('li', recursive=False), 1):
                items.append(f'{idx}. {li.get_text(strip=True)}')
            if items:
                ol.replace_with('\n'.join(items) + '\n\n')
            else:
                ol.decompose()
        
        # 10. 提取最终文本并清理
        text = soup.get_text(separator='\n')
        
        # 处理 HTML 实体
        import html
        text = html.unescape(text)
        
        # 清理多余的换行
        lines = []
        last_line_was_empty = False
        for line in text.split('\n'):
            stripped_line = line.strip()
            if not stripped_line:
                if not last_line_was_empty:
                    lines.append('')
                last_line_was_empty = True
            else:
                lines.append(stripped_line)
                last_line_was_empty = False
        
        cleaned_text = '\n'.join(lines).strip()
        
        # 11. 清理末尾的广告和推荐内容（从常见关键词开始截断）
        cutoff_keywords = [
            '特别声明',
            'Notice:',
            '推荐',
            '### 精品有声',
            '### 好书精选',
            '凤凰V现场',
            '查看更多',
        ]
        
        for keyword in cutoff_keywords:
            idx = cleaned_text.find(keyword)
            if idx != -1:
                # 找到关键词，截断文本
                cleaned_text = cleaned_text[:idx].strip()
                break
        
        return cleaned_text

    def _build_login_hint(self, platform: str) -> str:
        return self._LOGIN_HINTS.get(platform, '')

    async def _try_interactive_login(self, platform: str) -> bool:
        from .cookies_manager import CookieManager, PLATFORM_DOMAINS
        if platform not in PLATFORM_DOMAINS:
            return False
        mgr = CookieManager()
        cookies_path = mgr.get_cookies_path(platform)
        return mgr._is_valid(cookies_path)

    async def _retry_with_saved_cookies(
        self, url: str, platform: str,
        platform_type: PlatformType, content_type: ContentType,
        config: ParseConfig,
    ) -> Optional[ParseResult]:
        from .cookies_manager import CookieManager
        mgr = CookieManager()
        cookies_path = mgr.get_cookies_path(platform)
        if not cookies_path.exists():
            return None
        try:
            from .fetcher import CookieFetcher, FetchConfig
        except ImportError:
            return None
        fc = FetchConfig(
            cookies_file=str(cookies_path),
            headless=config.browser.headless,
            compatibility_mode=config.browser.compatibility_mode,
            scroll_enabled=config.scroll.enabled,
            max_scrolls=config.scroll.max_scrolls,
            scroll_delay=config.scroll.scroll_delay,
            load_full_content=config.load_full_content,
            dismiss_popups=config.dismiss_popups,
        )
        try:
            async with CookieFetcher(fc) as fetcher:
                fetch_result = await fetcher.fetch(url)
            if not fetch_result or not fetch_result.success:
                return None
            candidate = self._fetch_result_to_parse_result(
                fetch_result, url, platform, platform_type, content_type
            )
            blocked = ContentQualityMixin.detect_access_restriction(
                platform, candidate.title, candidate.content
            )
            quality_ok, _ = ContentQualityMixin.validate_quality(
                candidate.title, candidate.content,
                min_length=config.retry.min_quality_length,
                platform=platform,
            )
            if not blocked and quality_ok:
                return candidate
        except Exception:
            pass
        return None

    async def parse_batch(
        self,
        urls: List[str],
        config: Optional[ParseConfig] = None,
        on_complete=None,
        on_error=None,
        concurrent: int = 3
    ) -> List[ParseResult]:
        """
        批量解析多个 URL

        Args:
            urls: URL 列表
            config: 配置
            on_complete: 单个完成回调 (result) -> None
            on_error: 错误回调 (url, error) -> None
            concurrent: 并发数

        Returns:
            List[ParseResult] 结果列表
        """
        cfg = config or self.config
        semaphore = asyncio.Semaphore(concurrent)

        async def _parse_one(url: str) -> ParseResult:
            async with semaphore:
                try:
                    result = await self.parse(url, cfg)
                    if on_complete:
                        on_complete(result)
                    return result
                except Exception as e:
                    if on_error:
                        on_error(url, e)
                    return ParseResult(
                        url=url,
                        platform="unknown",
                        fetch_success=False,
                        error=str(e),
                    )

        tasks = [_parse_one(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def close(self):
        """关闭解析器，释放资源"""
        if self._fetcher:
            try:
                await self._fetcher.close()
            except Exception:
                pass
            self._fetcher = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


async def parse(
    url: str,
    config: Optional[ParseConfig] = None,
    **kwargs
) -> ParseResult:
    """
    一键解析 URL（便捷函数）

    使用方式:
        from urlparser import parse

        result = await parse("https://www.bilibili.com/video/BVxxx")
        print(result.title)
        print(result.content)
    """
    async with UrlParser(config or ParseConfig()) as parser:
        return await parser.parse(url, **kwargs)


async def parse_batch(
    urls: List[str],
    config: Optional[ParseConfig] = None,
    **kwargs
) -> List[ParseResult]:
    """
    批量解析多个 URL（便捷函数）

    使用方式:
        from urlparser import parse_batch

        results = await parse_batch(["url1", "url2", "url3"])
    """
    async with UrlParser(config or ParseConfig()) as parser:
        return await parser.parse_batch(urls, config, **kwargs)


def parse_sync(url: str, **kwargs) -> ParseResult:
    """
    同步版本（自动创建事件循环）

    适用于脚本或 Jupyter 环境:
        from urlparser import parse_sync

        result = parse_sync("https://www.zhihu.com/question/xxx")
    """
    return asyncio.run(parse(url, **kwargs))