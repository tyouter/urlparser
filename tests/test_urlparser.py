"""
urlparser 测试套件
"""

import pytest


class TestUrlParser:
    """UrlParser 核心功能测试"""

    def test_import_main_api(self):
        """测试主要 API 导入"""
        from urlparser import parse, parse_batch, parse_sync, UrlParser
        assert callable(parse)
        assert callable(parse_batch)
        assert callable(parse_sync)
        assert UrlParser

    def test_import_config(self):
        """测试配置导入"""
        from urlparser import ParseConfig, BrowserConfig, ScrollConfig, TranscribeConfig
        assert ParseConfig
        assert BrowserConfig
        assert ScrollConfig
        assert TranscribeConfig

    def test_import_models(self):
        """测试数据模型导入"""
        from urlparser import ParseResult, PlatformType, ContentType, VideoMetadata, TranscriptionResult
        assert ParseResult
        assert PlatformType
        assert ContentType
        assert VideoMetadata
        assert TranscriptionResult

    def test_import_storage(self):
        """测试存储层导入"""
        from urlparser import ResultCache, ResultStorage, StateManager, SourceDocumentManager
        assert ResultCache
        assert ResultStorage
        assert StateManager
        assert SourceDocumentManager

    def test_import_transcriber(self):
        """测试转录层导入"""
        from urlparser import FunASRTranscriber, WhisperTranscriber, extract_video_info
        assert FunASRTranscriber
        assert WhisperTranscriber
        assert callable(extract_video_info)

    def test_import_fetcher(self):
        """测试 Fetcher 层导入"""
        from urlparser import FetcherFactory, FetchStrategy, FetchConfig
        from urlparser import PlaywrightFetcher, CookieFetcher, UserChromeFetcher, BrowserUseFetcher
        assert FetcherFactory
        assert FetchStrategy
        assert FetchConfig
        assert PlaywrightFetcher
        assert CookieFetcher
        assert UserChromeFetcher
        assert BrowserUseFetcher

    def test_parse_config_simple(self):
        """测试简单配置"""
        from urlparser import ParseConfig
        config = ParseConfig.simple()
        assert config.transcribe.enabled == False
        assert config.browser.headless == True

    def test_parse_config_with_transcribe(self):
        """测试转录配置"""
        from urlparser import ParseConfig
        config = ParseConfig.with_transcribe(engine="funasr")
        assert config.transcribe.enabled == True
        assert config.transcribe.engine == "funasr"

    def test_parse_config_with_cookies(self):
        """测试 Cookie 配置"""
        from urlparser import ParseConfig
        config = ParseConfig.with_cookies(cookies_file="test.json")
        assert config.browser.cookies_file == "test.json"

    def test_platform_type_enum(self):
        """测试平台类型枚举"""
        from urlparser import PlatformType
        assert PlatformType.ZHIHU
        assert PlatformType.BILIBILI
        assert PlatformType.YOUTUBE
        assert PlatformType.WEIXIN
        assert PlatformType.XIAOHONGSHU
        assert PlatformType.GITHUB
        assert PlatformType.GENERIC
        assert PlatformType.UNKNOWN

    def test_content_type_enum(self):
        """测试内容类型枚举"""
        from urlparser import ContentType
        assert ContentType.ARTICLE
        assert ContentType.VIDEO
        assert ContentType.WEBPAGE
        assert ContentType.REPOSITORY
        assert ContentType.NOTE
        assert ContentType.UNKNOWN

    def test_fetch_strategy_enum(self):
        """测试读取策略枚举"""
        from urlparser import FetchStrategy
        assert FetchStrategy.DIRECT
        assert FetchStrategy.COOKIE
        assert FetchStrategy.USER_CHROME
        assert FetchStrategy.BROWSER_USE

    def test_url_normalizer(self):
        """测试 URL 规范化"""
        from urlparser.utils.url_utils import URLNormalizer, normalize_url, hash_url
        normalizer = URLNormalizer()

        # 测试基本规范化
        url = normalizer.normalize("https://www.zhihu.com/question/123")
        assert url.startswith("https://")

        # 测试哈希（使用独立函数）
        hash_val = hash_url("https://example.com")
        assert len(hash_val) == 32  # MD5 hex digest

    def test_detect_platform(self):
        """测试平台检测"""
        from urlparser.utils.url_utils import detect_platform

        # detect_platform 返回字符串
        assert detect_platform("https://www.zhihu.com/question/123") == "zhihu"
        assert detect_platform("https://www.bilibili.com/video/BV123") == "bilibili"
        assert detect_platform("https://www.youtube.com/watch?v=123") == "youtube"
        assert detect_platform("https://mp.weixin.qq.com/s/123") == "weixin"
        assert detect_platform("https://www.xiaohongshu.com/explore/123") == "xiaohongshu"
        assert detect_platform("https://github.com/user/repo") == "github"
        assert detect_platform("https://example.com/page") == "generic"

    def test_text_cleaner(self):
        """测试文本清洗"""
        from urlparser.utils.text_utils import clean_text

        # 测试去除多余空白
        text = "Hello   World\n\n\n"
        cleaned = clean_text(text)
        assert "Hello" in cleaned
        assert "World" in cleaned

    @pytest.mark.asyncio
    async def test_result_cache(self):
        """测试缓存功能"""
        from urlparser import ResultCache

        cache = ResultCache()

        # 测试统计（异步）
        stats = await cache.stats()
        assert "memory_count" in stats
        assert "disk_count" in stats

    def test_state_manager(self):
        """测试状态管理"""
        from urlparser import StateManager

        state = StateManager()

        # 测试完整性验证（返回 dict）
        report = state.validate_integrity()
        assert report is not None
        assert "valid" in report
        assert "summary" in report


class TestFetcherFactory:
    """Fetcher 工厂测试"""

    def test_factory_registry(self):
        """测试工厂注册表"""
        from urlparser import FetcherFactory, FetchStrategy

        assert FetchStrategy.DIRECT in FetcherFactory._registry
        assert FetchStrategy.COOKIE in FetcherFactory._registry
        assert FetchStrategy.USER_CHROME in FetcherFactory._registry
        assert FetchStrategy.BROWSER_USE in FetcherFactory._registry

    def test_factory_create_default(self):
        """测试默认创建"""
        from urlparser import FetcherFactory, FetchConfig, PlaywrightFetcher

        fetcher = FetcherFactory.create(FetchConfig())
        assert isinstance(fetcher, PlaywrightFetcher)

    def test_factory_create_with_strategy(self):
        """测试指定策略创建"""
        from urlparser import FetcherFactory, FetchStrategy, CookieFetcher, UserChromeFetcher

        fetcher = FetcherFactory.create(strategy=FetchStrategy.COOKIE)
        assert isinstance(fetcher, CookieFetcher)

        fetcher = FetcherFactory.create(strategy=FetchStrategy.USER_CHROME)
        assert isinstance(fetcher, UserChromeFetcher)


class TestParserFactory:
    """Parser 工厂测试"""

    def test_registry_platforms(self):
        """测试平台注册"""
        from urlparser.parser.factory import ParserRegistry

        # ParserRegistry._parsers 使用字符串键
        assert "zhihu" in ParserRegistry._parsers
        assert "bilibili" in ParserRegistry._parsers
        assert "youtube" in ParserRegistry._parsers
        assert "weixin" in ParserRegistry._parsers
        assert "xiaohongshu" in ParserRegistry._parsers
        assert "github" in ParserRegistry._parsers
        assert "default" in ParserRegistry._parsers


@pytest.mark.asyncio
class TestAsyncOperations:
    """异步操作测试"""

    async def test_parse_sync_wrapper(self):
        """测试同步包装器（不实际调用网络）"""
        from urlparser import parse_sync

        # 仅测试函数存在，不实际执行网络请求
        assert callable(parse_sync)


# 集成测试需要网络连接，标记为 skip
@pytest.mark.skip(reason="需要网络连接和 Playwright 安装")
class TestIntegration:
    """集成测试"""

    async def test_parse_zhihu(self):
        """测试知乎解析"""
        from urlparser import parse

        result = await parse("https://www.zhihu.com/question/19550225")
        assert result.fetch_success
        assert result.title

    async def test_parse_bilibili(self):
        """测试 B站解析"""
        from urlparser import parse

        result = await parse("https://www.bilibili.com/video/BV1xx411c7mD")
        assert result.fetch_success

    async def test_video_info(self):
        """测试视频信息提取"""
        from urlparser import extract_video_info

        info = await extract_video_info("https://www.bilibili.com/video/BV1xx411c7mD")
        assert info.title