"""
解析器工厂

根据URL自动选择合适的解析器
"""

from typing import Dict, Type, Optional, List
from urllib.parse import urlparse

from .base import BaseParser
from .models import ParserConfig, ParseResult, PlatformType
from .platforms import (
    ZhihuParser,
    XiaohongshuParser,
    BilibiliParser,
    YoutubeParser,
    WeixinParser,
    GithubParser,
    GenericParser,
)


class ParserRegistry:
    _parsers: Dict[str, Type[BaseParser]] = {}

    @classmethod
    def register(cls, parser_class: Type[BaseParser]):
        cls._parsers[parser_class.platform] = parser_class
        return parser_class

    @classmethod
    def get_parser(cls, platform: str) -> Optional[Type[BaseParser]]:
        return cls._parsers.get(platform)

    @classmethod
    def get_all_parsers(cls) -> Dict[str, Type[BaseParser]]:
        return cls._parsers.copy()

    @classmethod
    def detect_platform(cls, url: str) -> str:
        domain = urlparse(url).netloc.lower()

        for platform, parser_cls in cls._parsers.items():
            if parser_cls.can_handle(url):
                return platform

        return 'default'

    @classmethod
    def list_supported_platforms(cls) -> List[str]:
        return list(cls._parsers.keys())


ParserRegistry.register(ZhihuParser)
ParserRegistry.register(XiaohongshuParser)
ParserRegistry.register(BilibiliParser)
ParserRegistry.register(YoutubeParser)
ParserRegistry.register(WeixinParser)
ParserRegistry.register(GithubParser)
ParserRegistry.register(GenericParser)


class ParserFactory:

    @staticmethod
    def create(
        url: str,
        config: Optional[ParserConfig] = None,
        platform: Optional[str] = None
    ) -> BaseParser:
        detected_platform = platform or ParserRegistry.detect_platform(url)
        parser_class = ParserRegistry.get_parser(detected_platform) or GenericParser

        return parser_class(config or ParserConfig())

    @staticmethod
    async def fetch_url(
        url: str,
        config: Optional[ParserConfig] = None,
        **kwargs
    ):
        if config is None:
            config = ParserConfig(**{k: v for k, v in kwargs.items() if hasattr(ParserConfig, k)})

        async with ParserFactory.create(url, config) as parser:
            return await parser.fetch(url)

    @staticmethod
    async def batch_fetch(
        urls: List[str],
        config: Optional[ParserConfig] = None,
        on_complete=None,
        on_error=None
    ) -> List:
        results = []
        parser_config = config or ParserConfig()
        parser = None

        try:
            parser = ParserFactory.create(urls[0] if urls else "", parser_config)

            for i, url in enumerate(urls):
                try:
                    print(f"[{i+1}/{len(urls)}] Fetching: {url[:60]}...")
                    result = await parser.fetch(url)
                    results.append(result)

                    if on_complete:
                        on_complete(result)

                except Exception as e:
                    print(f"[ERROR] Failed to fetch {url}: {e}")

                    error_result = ParseResult(
                        url=url,
                        platform=ParserRegistry.detect_platform(url),
                        fetch_success=False,
                        error=str(e)
                    )
                    results.append(error_result)

                    if on_error:
                        on_error(url, e)

        finally:
            if parser:
                await parser.close()

        return results


def get_parser_for_url(url: str, config: Optional[ParserConfig] = None) -> BaseParser:
    return ParserFactory.create(url, config)


async def parse_url(url: str, **kwargs):
    return await ParserFactory.fetch_url(url, **kwargs)


async def parse_urls(urls: List[str], **kwargs):
    return await ParserFactory.batch_fetch(urls, **kwargs)


__all__ = [
    'ParserFactory',
    'ParserRegistry',
    'get_parser_for_url',
    'parse_url',
    'parse_urls',
]