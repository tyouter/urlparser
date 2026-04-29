"""
P2: 反爬/质量检测测试

验证 AntiScrapingMixin 的检测规则和内容质量验证逻辑。
这些是 urlparser 的核心防线 - 如果检测规则有误，会导致:
    - 漏检: 返回被拦截的垃圾内容给用户
    - 误判: 正常内容被判定为被拦截，触发不必要的重试

覆盖:
    - detect_blocked() 各平台各模式
    - validate_quality() 边界条件
    - BLOCKED_PATTERNS 完整性
    - 内容完整性检测
"""

import pytest

from urlparser.parser.mixins.anti_scraping import AntiScrapingMixin


pytestmark = pytest.mark.p2


class TestDetectBlockedZhihu:
    """知乎反爬检测"""

    def test_blocked_by_wasteland_text(self):
        reason = AntiScrapingMixin.detect_blocked(
            "zhihu", "没有知识存在的荒原", "你似乎来到了没有知识存在的荒原"
        )
        assert reason is not None
        assert "荒原" in reason

    def test_blocked_by_login_wall(self):
        content = "登录/注册" * 5
        reason = AntiScrapingMixin.detect_blocked(
            "zhihu", "知乎", content
        )
        assert reason is not None
        assert "login wall" in reason

    def test_not_blocked_normal_content(self):
        reason = AntiScrapingMixin.detect_blocked(
            "zhihu",
            "最难调试修复的bug是怎样的？",
            "这是一个关于调试bug的长回答，内容非常丰富和详细。" * 20,
        )
        assert reason is None

    def test_not_blocked_short_but_real(self):
        reason = AntiScrapingMixin.detect_blocked(
            "zhihu",
            "真实回答标题",
            "这是一条真实的短回答，虽然不长但没有登录墙关键词。",
        )
        assert reason is None


class TestDetectBlockedXiaohongshu:
    """小红书反爬检测"""

    def test_blocked_by_title_exact(self):
        reason = AntiScrapingMixin.detect_blocked(
            "xiaohongshu",
            "小红书 - 你的生活兴趣社区",
            "一些内容",
        )
        assert reason is not None
        assert "title" in reason

    def test_blocked_by_login_and_empty(self):
        reason = AntiScrapingMixin.detect_blocked(
            "xiaohongshu",
            "小红书",
            "登录",
        )
        assert reason is not None
        assert "login" in reason

    def test_not_blocked_normal_content(self):
        reason = AntiScrapingMixin.detect_blocked(
            "xiaohongshu",
            "我的旅行日记",
            "今天去了很多地方，拍了好多照片，非常开心！" * 10,
        )
        assert reason is None


class TestDetectBlockedWeixin:
    """微信反爬检测"""

    def test_blocked_by_login_and_empty(self):
        reason = AntiScrapingMixin.detect_blocked(
            "weixin",
            "微信",
            "登录",
        )
        assert reason is not None

    def test_not_blocked_normal_article(self):
        reason = AntiScrapingMixin.detect_blocked(
            "weixin",
            "公众号文章标题",
            "这是一篇正常的微信公众号文章内容，包含很多有价值的文字。" * 20,
        )
        assert reason is None


class TestDetectBlockedGeneric:
    """未配置平台的反爬检测"""

    def test_unknown_platform_never_blocked(self):
        reason = AntiScrapingMixin.detect_blocked(
            "generic", "Some Title", "Some content"
        )
        assert reason is None

    def test_github_never_blocked(self):
        reason = AntiScrapingMixin.detect_blocked(
            "github", "README", "Repository description and README content"
        )
        assert reason is None


class TestValidateQuality:
    """内容质量验证"""

    def test_quality_ok(self):
        ok, reason = AntiScrapingMixin.validate_quality(
            "正常标题", "这是一段足够长的正常内容，超过了一百个字符的最低要求。" * 5
        )
        assert ok is True
        assert reason == "ok"

    def test_content_too_short(self):
        ok, reason = AntiScrapingMixin.validate_quality(
            "标题", "短"
        )
        assert ok is False
        assert "too short" in reason

    def test_content_empty(self):
        ok, reason = AntiScrapingMixin.validate_quality(
            "标题", ""
        )
        assert ok is False

    def test_content_none(self):
        ok, reason = AntiScrapingMixin.validate_quality(
            "标题", None
        )
        assert ok is False

    def test_title_empty(self):
        ok, reason = AntiScrapingMixin.validate_quality(
            "", "这是一段足够长的正常内容。" * 10
        )
        assert ok is False
        assert "title" in reason

    def test_title_too_short(self):
        ok, reason = AntiScrapingMixin.validate_quality(
            "A", "这是一段足够长的正常内容。" * 10
        )
        assert ok is False
        assert "title" in reason

    def test_custom_min_length(self):
        ok, reason = AntiScrapingMixin.validate_quality(
            "标题", "这是一段超过五个字的内容", min_length=5
        )
        assert ok is True

    def test_boundary_min_length(self):
        ok, _ = AntiScrapingMixin.validate_quality(
            "标题", "a" * 100, min_length=100
        )
        assert ok is True

        ok, _ = AntiScrapingMixin.validate_quality(
            "标题", "a" * 99, min_length=100
        )
        assert ok is False


class TestBlockedPatternsCompleteness:
    """BLOCKED_PATTERNS 配置完整性"""

    def test_all_chinese_platforms_have_patterns(self):
        chinese_platforms = ["zhihu", "xiaohongshu", "weixin"]
        for platform in chinese_platforms:
            assert platform in AntiScrapingMixin.BLOCKED_PATTERNS, \
                f"Missing BLOCKED_PATTERNS for {platform}"

    def test_patterns_have_required_fields(self):
        for platform, patterns in AntiScrapingMixin.BLOCKED_PATTERNS.items():
            for pat in patterns:
                assert "type" in pat, f"Pattern in {platform} missing 'type'"
                assert pat["type"] in [
                    "text_contains", "title_exact",
                    "login_wall", "login_and_empty"
                ], f"Unknown pattern type '{pat['type']}' in {platform}"

    def test_login_wall_pattern_has_required_fields(self):
        for platform, patterns in AntiScrapingMixin.BLOCKED_PATTERNS.items():
            for pat in patterns:
                if pat["type"] == "login_wall":
                    assert "login_keyword" in pat
                    assert "min_count" in pat
                    assert "max_text" in pat


class TestIsLoginBlocked:
    """登录拦截检测"""

    def test_zhihu_security_verification(self):
        assert AntiScrapingMixin.is_login_blocked("安全验证 - 知乎", "zhihu") is True

    def test_zhihu_login_page(self):
        assert AntiScrapingMixin.is_login_blocked("登录知乎", "zhihu") is True

    def test_zhihu_normal_page(self):
        assert AntiScrapingMixin.is_login_blocked("正常内容", "zhihu") is False

    def test_xiaohongshu_login_indicators(self):
        for indicator in ["登录后推荐", "扫码登录", "手机号登录"]:
            assert AntiScrapingMixin.is_login_blocked(indicator, "xiaohongshu") is True

    def test_generic_never_login_blocked(self):
        assert AntiScrapingMixin.is_login_blocked("登录", "generic") is False


class TestIsContentComplete:
    """内容完整性检测"""

    def test_zhihu_complete_content(self):
        content = "文章内容" * 100 + "北京智者天下科技有限公司"
        assert AntiScrapingMixin.is_content_complete(content, "zhihu") is True

    def test_zhihu_incomplete_content(self):
        content = "文章内容" * 100
        result = AntiScrapingMixin.is_content_complete(content, "zhihu")
        assert result is True

    def test_zhihu_long_content_without_signature(self):
        content = "这是一段很长的知乎内容" * 50
        assert len(content) > 500
        result = AntiScrapingMixin.is_content_complete(content, "zhihu")
        assert result is False

    def test_zhihu_short_content_skips_check(self):
        content = "短内容"
        assert AntiScrapingMixin.is_content_complete(content, "zhihu") is True

    def test_generic_always_complete(self):
        assert AntiScrapingMixin.is_content_complete("any content", "generic") is True
