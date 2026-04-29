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
        **kwargs
    ) -> ParseResult:
        """
        解析单个 URL（主入口）

        Args:
            url: 要解析的 URL
            config: 可选配置（覆盖默认）
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
                )

                if not blocked and quality_ok:
                    result.final_strategy = strategy_name
                    result.retry_attempts = retry_attempts
                    return result

                reason = blocked or q_reason
                retry_attempts.append(RetryAttempt(
                    strategy=strategy_name,
                    success=False,
                    access_restriction_reason=reason,
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
                )

                if not blocked and quality_ok:
                    candidate.final_strategy = strategy_name
                    candidate.retry_attempts = retry_attempts

                    # Run transcription/comprehension if video
                    if is_vid and config.transcribe.enabled and candidate.fetch_success:
                        candidate.transcription = await self._transcribe_audio(url, config.transcribe)
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
                    reason = blocked or q_reason
                    retry_attempts.append(RetryAttempt(
                        strategy=strategy_name,
                        success=False,
                        access_restriction_reason=reason,
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
        """Playwright with cookies."""
        if not config.browser.cookies_file:
            return None
        try:
            from .fetcher import CookieFetcher, FetchConfig
        except ImportError:
            return None
        fc = FetchConfig(
            cookies_file=config.browser.cookies_file,
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

        return result

    async def _do_parse(self, url: str, config: ParseConfig) -> ParseResult:
        """执行实际解析：auto_select fetcher -> fallback parser -> transcribe"""
        platform = detect_platform(url)
        is_vid = is_video_url(url)

        content_type = ContentType.VIDEO if is_vid else ContentType.ARTICLE
        platform_type = self._detect_platform_type(platform)

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
                        if is_vid and config.transcribe.enabled and result.fetch_success:
                            result.transcription = await self._transcribe_audio(url, config.transcribe)
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

            if is_vid and config.transcribe.enabled and result.fetch_success:
                transcription = await self._transcribe_audio(url, config.transcribe)
                result.transcription = transcription

            if is_vid and config.comprehension.enabled and result.fetch_success:
                comprehension = await self._run_comprehension(
                    url, config.comprehension, result.transcription
                )
                result.comprehension = comprehension

            return result

        finally:
            await parser.close()

    async def _transcribe_audio(self, url: str, transcribe_config) -> TranscriptionResult:
        """音频转录 - 通过 ensure_transcribe_dependencies 保证依赖"""
        try:
            from .dependency_installer import ensure_transcribe_dependencies

            if not ensure_transcribe_dependencies(auto_install=True):
                return TranscriptionResult(success=False, error="Transcription dependencies not available")

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