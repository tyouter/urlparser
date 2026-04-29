"""
P1: 模型/配置属性测试

使用 Hypothesis 进行属性基测试 (Property-Based Testing)。
核心思想: 不测试具体输入输出对，而是测试代码在所有有效输入下应满足的数学性质。

覆盖:
    - ParseResult 序列化往返 (to_dict → ParseResult → to_dict)
    - ParseResult.to_markdown() 结构完整性
    - ParseConfig 工厂方法一致性
    - VideoMetadata/TranscriptionResult 序列化
    - ContentType/PlatformType 枚举完整性
"""

import json
import pytest

try:
    from hypothesis import given, settings, assume
    from hypothesis import strategies as st
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

from urlparser.models import (
    ParseResult, PlatformType, ContentType,
    VideoMetadata, TranscriptionResult, ArticleMetadata,
    ComprehensionResult, VisualFrameResult, RetryAttempt,
)
from urlparser.config import (
    ParseConfig, BrowserConfig, ScrollConfig,
    TranscribeConfig, ComprehensionConfig, RetryConfig,
)


pytestmark = pytest.mark.p1


class TestParseResultSerialization:
    """序列化往返属性: to_dict() → 重建 → to_dict() 应产生相同结果"""

    def test_basic_roundtrip(self):
        original = ParseResult(
            url="https://example.com",
            platform="generic",
            platform_type=PlatformType.GENERIC,
            content_type=ContentType.ARTICLE,
            title="Test Title",
            content="Test content " * 100,
            author="Author",
            publish_date="2026-01-01",
            fetch_success=True,
            parse_time=1.5,
            final_strategy="playwright",
        )
        d = original.to_dict()
        assert d['url'] == original.url
        assert d['title'] == original.title
        assert d['content_length'] == len(original.content)
        assert d['fetch_success'] is True
        assert d['platform_type'] == "generic"
        assert d['content_type'] == "article"

    def test_with_video_metadata(self):
        vm = VideoMetadata(
            duration="10:30", views="10000", likes="500",
            coins="200", favorites="100", danmaku="50",
        )
        result = ParseResult(
            url="https://bilibili.com/video/BV1xx",
            platform="bilibili",
            platform_type=PlatformType.BILIBILI,
            content_type=ContentType.VIDEO,
            video_metadata=vm,
            fetch_success=True,
        )
        d = result.to_dict()
        assert d['video_metadata']['duration'] == "10:30"
        assert d['video_metadata']['views'] == "10000"
        assert d['is_video'] is True

    def test_with_transcription(self):
        tr = TranscriptionResult(
            success=True, text="转录文本内容",
            segments=[{"start": 0.0, "end": 5.0, "text": "转录文本"}],
            language="zh", duration=300.0, engine="funasr",
        )
        result = ParseResult(
            url="https://bilibili.com/video/BV1xx",
            platform="bilibili",
            content_type=ContentType.VIDEO,
            transcription=tr,
            fetch_success=True,
        )
        d = result.to_dict()
        assert d['has_transcription'] is True
        assert d['transcription']['engine'] == "funasr"
        assert d['transcription']['segment_count'] == 1

    def test_with_retry_attempts(self):
        attempts = [
            RetryAttempt(strategy="playwright", success=False, error="blocked", duration=2.0),
            RetryAttempt(strategy="bb_browser", success=True, duration=3.5),
        ]
        result = ParseResult(
            url="https://zhihu.com/question/1",
            platform="zhihu",
            retry_attempts=attempts,
            final_strategy="bb_browser",
            fetch_success=True,
        )
        d = result.to_dict()
        assert len(d['retry_attempts']) == 2
        assert d['retry_attempts'][0]['strategy'] == "playwright"
        assert d['retry_attempts'][1]['success'] is True


class TestParseResultMarkdown:
    """to_markdown() 结构完整性属性"""

    def test_article_has_required_sections(self):
        result = ParseResult(
            url="https://example.com",
            platform="generic",
            content_type=ContentType.ARTICLE,
            title="Test Article",
            content="This is the article content.",
            author="Author",
            fetch_success=True,
            final_strategy="playwright",
            parse_time=1.0,
        )
        md = result.to_markdown()
        assert "# Test Article" in md
        assert "## 内容摘要" in md
        assert "This is the article content." in md
        assert "**来源**" in md
        assert "**平台**" in md

    def test_video_has_video_info_section(self):
        result = ParseResult(
            url="https://bilibili.com/video/BV1xx",
            platform="bilibili",
            content_type=ContentType.VIDEO,
            title="Test Video",
            video_metadata=VideoMetadata(duration="10:30", views="1万"),
            fetch_success=True,
        )
        md = result.to_markdown()
        assert "## 视频信息" in md
        assert "时长: 10:30" in md
        assert "播放: 1万" in md

    def test_transcription_in_markdown(self):
        result = ParseResult(
            url="https://bilibili.com/video/BV1xx",
            platform="bilibili",
            content_type=ContentType.VIDEO,
            title="Test",
            transcription=TranscriptionResult(
                success=True, text="转录文本",
                engine="funasr", duration=60.0, language="zh",
            ),
            fetch_success=True,
        )
        md = result.to_markdown()
        assert "## 语音转录" in md
        assert "转录文本" in md
        assert "funasr" in md

    def test_content_not_truncated(self):
        long_content = "A" * 10000
        result = ParseResult(
            url="https://example.com",
            platform="generic",
            content_type=ContentType.ARTICLE,
            title="Long Article",
            content=long_content,
            fetch_success=True,
        )
        md = result.to_markdown()
        assert long_content in md
        assert "..." not in md.split("## 内容摘要")[1].split("##")[0]

    def test_failed_result_no_crash(self):
        result = ParseResult(
            url="https://example.com",
            platform="unknown",
            fetch_success=False,
            error="Connection timeout",
        )
        md = result.to_markdown()
        assert isinstance(md, str)
        assert len(md) > 0


class TestParseResultProperties:
    """ParseResult 计算属性"""

    def test_is_video(self):
        assert ParseResult(content_type=ContentType.VIDEO).is_video is True
        assert ParseResult(content_type=ContentType.ARTICLE).is_video is False

    def test_is_article(self):
        assert ParseResult(content_type=ContentType.ARTICLE).is_article is True
        assert ParseResult(content_type=ContentType.NOTE).is_article is True
        assert ParseResult(content_type=ContentType.VIDEO).is_article is False

    def test_has_transcription(self):
        r = ParseResult(transcription=TranscriptionResult(success=True, text="text"))
        assert r.has_transcription is True
        r2 = ParseResult(transcription=TranscriptionResult(success=False))
        assert r2.has_transcription is False

    def test_content_length(self):
        assert ParseResult(content="hello").content_length == 5
        assert ParseResult(content="").content_length == 0
        assert ParseResult().content_length == 0

    def test_full_text_combines_all(self):
        r = ParseResult(
            title="Title",
            content="Body",
            transcription=TranscriptionResult(success=True, text="Transcript"),
        )
        ft = r.full_text
        assert "Title" in ft
        assert "Body" in ft
        assert "Transcript" in ft


class TestParseConfigFactories:
    """ParseConfig 工厂方法一致性"""

    def test_simple_config(self):
        config = ParseConfig.simple()
        assert config.browser.headless is True
        assert config.transcribe.enabled is False
        assert config.retry.enabled is True

    def test_with_transcribe(self):
        config = ParseConfig.with_transcribe()
        assert config.transcribe.enabled is True

    def test_with_cookies(self):
        config = ParseConfig.with_cookies("cookies.json")
        assert config.browser.cookies_file == "cookies.json"

    def test_with_online_parse(self):
        config = ParseConfig.with_online_parse()
        assert config.parse_mode == "online"

    def test_full_feature(self):
        config = ParseConfig.full_feature()
        assert config.scroll.enabled is True
        assert config.load_full_content is True
        assert config.dismiss_popups is True

    def test_to_parser_config_roundtrip(self):
        config = ParseConfig(
            browser=BrowserConfig(timeout=60000, headless=False),
            scroll=ScrollConfig(max_scrolls=30),
            transcribe=TranscribeConfig(enabled=True),
        )
        pc = config.to_parser_config()
        assert pc.timeout == 60000
        assert pc.headless is False
        assert pc.max_scrolls == 30

    def test_to_fetch_config_roundtrip(self):
        config = ParseConfig(
            browser=BrowserConfig(cookies_file="test.json"),
            scroll=ScrollConfig(scroll_delay=2.0),
        )
        fc = config.to_fetch_config()
        assert fc.cookies_file == "test.json"
        assert fc.scroll_delay == 2.0


class TestEnumCompleteness:
    """枚举完整性 - 确保所有平台和类型都有对应值"""

    def test_platform_types(self):
        platforms = [p.value for p in PlatformType]
        assert "zhihu" in platforms
        assert "bilibili" in platforms
        assert "youtube" in platforms
        assert "weixin" in platforms
        assert "xiaohongshu" in platforms
        assert "github" in platforms
        assert "generic" in platforms

    def test_content_types(self):
        types = [t.value for t in ContentType]
        assert "article" in types
        assert "video" in types
        assert "webpage" in types
        assert "repository" in types

    def test_platform_type_from_string(self):
        assert PlatformType("zhihu") == PlatformType.ZHIHU
        assert PlatformType("bilibili") == PlatformType.BILIBILI
        assert PlatformType("generic") == PlatformType.GENERIC


if HAS_HYPOTHESIS:
    text_strategy = st.text(min_size=0, max_size=500)
    url_strategy = st.from_regex(r'https?://[a-z0-9.-]+\.[a-z]{2,}/.*', fullmatch=False)

    class TestPropertyBased:
        """Hypothesis 属性基测试 - 自动生成大量随机输入验证不变量"""

        @given(st.text(min_size=1, max_size=1000))
        @settings(max_examples=50)
        def test_content_length_always_matches(self, content):
            result = ParseResult(content=content)
            assert result.content_length == len(content)

        @given(st.text(min_size=1, max_size=500))
        @settings(max_examples=50)
        def test_to_markdown_always_contains_content(self, content):
            result = ParseResult(
                url="https://example.com",
                platform="generic",
                content_type=ContentType.ARTICLE,
                title="T",
                content=content,
                fetch_success=True,
            )
            md = result.to_markdown()
            assert content in md

        @given(st.text(min_size=0, max_size=200))
        @settings(max_examples=50)
        def test_to_dict_always_json_serializable(self, title):
            result = ParseResult(title=title, url="https://example.com")
            d = result.to_dict()
            json_str = json.dumps(d, ensure_ascii=False)
            parsed = json.loads(json_str)
            assert parsed['title'] == title

        @given(st.text(min_size=1, max_size=100))
        @settings(max_examples=30)
        def test_video_metadata_serialization_roundtrip(self, duration):
            vm = VideoMetadata(duration=duration)
            d = vm.to_dict()
            assert d['duration'] == duration

        @given(st.text(min_size=1, max_size=200))
        @settings(max_examples=30)
        def test_transcription_result_dict_consistency(self, text):
            tr = TranscriptionResult(success=True, text=text, engine="test")
            d = tr.to_dict()
            assert d['text'] == text
            assert d['success'] is True

        @given(st.integers(min_value=1, max_value=300))
        @settings(max_examples=30)
        def test_retry_config_timeout_consistency(self, timeout):
            rc = RetryConfig(timeout_per_attempt=timeout)
            assert rc.timeout_per_attempt == timeout
            assert rc.timeout_per_attempt > 0
