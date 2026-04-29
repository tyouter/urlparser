"""
P0: 纯函数单元测试

无网络、无IO、毫秒级完成。
覆盖: URL工具、文本工具、文件工具、媒体工具
"""

import re
import pytest

from urlparser.utils.url_utils import (
    URLNormalizer, normalize_url, hash_url, detect_platform, is_video_url,
)
from urlparser.utils.text_utils import (
    clean_text, remove_duplicate_lines, extract_main_content,
    truncate_text, count_words, extract_summary,
)
from urlparser.utils.file_utils import safe_filename
from urlparser.utils.media_utils import (
    is_audio_file, is_video_file, is_media_file,
)


class TestURLNormalizer:
    def test_removes_tracking_params(self):
        url = "https://www.zhihu.com/question/123?utm_source=wechat&from_spmid=333"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "from_spmid" not in result
        assert "zhihu.com/question/123" in result

    def test_removes_bilibili_tracking(self):
        url = "https://www.bilibili.com/video/BV1xx?bvid=BV1xx&spm_id_from=333"
        result = normalize_url(url)
        assert "bvid=" not in result
        assert "spm_id_from" not in result
        assert "BV1xx" in result

    def test_removes_fragment(self):
        url = "https://example.com/page#section"
        result = normalize_url(url)
        assert "#" not in result
        assert result == "https://example.com/page"

    def test_strips_trailing_question_mark(self):
        url = "https://example.com/page?"
        result = normalize_url(url)
        assert not result.endswith("?")

    def test_idempotent(self):
        url = "https://www.zhihu.com/answer/123?utm_source=test&from=web"
        first = normalize_url(url)
        second = normalize_url(first)
        assert first == second

    def test_preserves_clean_url(self):
        url = "https://github.com/anthropics/claude-code"
        assert normalize_url(url) == url


class TestDetectPlatform:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.zhihu.com/question/123", "zhihu"),
        ("https://zhuanlan.zhihu.com/p/123", "zhihu"),
        ("https://www.bilibili.com/video/BV1xx", "bilibili"),
        ("https://www.youtube.com/watch?v=abc", "youtube"),
        ("https://mp.weixin.qq.com/s/abc", "weixin"),
        ("https://www.xiaohongshu.com/explore/123", "xiaohongshu"),
        ("https://github.com/anthropics/claude-code", "github"),
        ("https://dribbble.com/shots/123", "default"),
        ("https://b23.tv/abc123", "bilibili"),
        ("https://youtu.be/abc123", "youtube"),
        ("https://xhslink.com/abc", "xiaohongshu"),
    ])
    def test_known_platforms(self, url, expected):
        assert detect_platform(url) == expected

    def test_unknown_platform_returns_default(self):
        assert detect_platform("https://www.example.com/article") == "default"


class TestIsVideoURL:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.bilibili.com/video/BV1xx", True),
        ("https://www.youtube.com/watch?v=abc", True),
        ("https://www.zhihu.com/question/123", False),
        ("https://mp.weixin.qq.com/s/abc", False),
        ("https://github.com/anthropics/claude-code", False),
    ])
    def test_video_detection(self, url, expected):
        assert is_video_url(url) == expected


class TestHashURL:
    def test_deterministic(self):
        url = "https://www.zhihu.com/question/123"
        assert hash_url(url) == hash_url(url)

    def test_different_urls_different_hashes(self):
        h1 = hash_url("https://www.zhihu.com/question/1")
        h2 = hash_url("https://www.zhihu.com/question/2")
        assert h1 != h2

    def test_tracking_params_ignored(self):
        h1 = hash_url("https://example.com/page?utm_source=test")
        h2 = hash_url("https://example.com/page")
        assert h1 == h2


class TestCleanText:
    def test_removes_html_tags(self):
        assert "<b>" not in clean_text("Hello <b>world</b>")
        assert "Hello world" == clean_text("Hello <b>world</b>")

    def test_collapses_whitespace(self):
        result = clean_text("Hello   world\n\n\nfoo")
        assert "   " not in result

    def test_empty_input(self):
        assert clean_text("") == ""
        assert clean_text(None) == ""

    def test_strips(self):
        assert clean_text("  hello  ") == "hello"


class TestRemoveDuplicateLines:
    def test_removes_consecutive_duplicates(self):
        result = remove_duplicate_lines("line1\nline2\nline1\nline3")
        assert result.count("line1") == 1

    def test_preserves_order(self):
        result = remove_duplicate_lines("a\nb\nc")
        lines = result.split('\n')
        assert lines == ["a", "b", "c"]

    def test_empty_input(self):
        assert remove_duplicate_lines("") == ""
        assert remove_duplicate_lines(None) == ""


class TestTruncateText:
    def test_short_text_unchanged(self):
        assert truncate_text("hello", 10) == "hello"

    def test_long_text_truncated(self):
        result = truncate_text("a" * 100, 50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_custom_suffix(self):
        result = truncate_text("a" * 100, 50, suffix="…")
        assert result.endswith("…")


class TestCountWords:
    def test_chinese_text(self):
        assert count_words("你好世界") == 4

    def test_english_text(self):
        assert count_words("hello world") == 2

    def test_mixed_text(self):
        result = count_words("你好hello世界world")
        assert result >= 4

    def test_empty(self):
        assert count_words("") == 0


class TestExtractSummary:
    def test_short_text_unchanged(self):
        result = extract_summary("这是一句话。")
        assert "这是一句话" in result

    def test_long_text_truncated(self):
        text = "第一句。第二句。第三句。第四句。第五句。"
        result = extract_summary(text, max_sentences=3)
        assert result.count("。") <= 4

    def test_empty(self):
        assert extract_summary("") == ""


class TestSafeFilename:
    def test_removes_special_chars(self):
        result = safe_filename("hello/world:test?foo")
        assert "/" not in result
        assert ":" not in result
        assert "?" not in result

    def test_preserves_alphanumeric(self):
        result = safe_filename("hello_world_123")
        assert result == "hello_world_123"


class TestMediaFileDetection:
    @pytest.mark.parametrize("filename,expected", [
        ("audio.mp3", True),
        ("audio.wav", True),
        ("audio.flac", True),
        ("audio.aac", True),
        ("audio.ogg", True),
        ("audio.m4a", True),
        ("video.mp4", False),
        ("document.pdf", False),
        ("image.png", False),
    ])
    def test_audio_files(self, filename, expected):
        assert is_audio_file(filename) == expected

    @pytest.mark.parametrize("filename,expected", [
        ("video.mp4", True),
        ("video.mkv", True),
        ("video.avi", True),
        ("video.webm", True),
        ("video.mov", True),
        ("audio.mp3", False),
    ])
    def test_video_files(self, filename, expected):
        assert is_video_file(filename) == expected

    @pytest.mark.parametrize("filename,expected", [
        ("audio.mp3", True),
        ("video.mp4", True),
        ("document.pdf", False),
        ("image.png", False),
    ])
    def test_media_files(self, filename, expected):
        assert is_media_file(filename) == expected
