"""
契约测试: Schema v1 输出结构（v4 任务 A）

验证 ParseResult.to_dict() 满足 v4 Schema v1 契约（docs §7.1）：
必需键、类型、结构化错误形状、耗时分解形状。

不引入 jsonschema 依赖，用手写断言保持零新依赖。
"""

from urlparser import ParseResult
from urlparser.schema import (
    SCHEMA_VERSION, ErrorCode, StructuredError, TimingBreakdown,
)

REQUIRED_KEYS = {
    "schema_version", "url", "platform", "platform_type", "content_type",
    "title", "content_length", "author", "publish_date",
    "is_video", "is_article", "has_transcription",
    "video_metadata", "transcription", "comprehension", "metadata",
    "fetch_success", "error", "error_detail", "parse_time",
    "final_strategy", "retry_attempts",
    # v4 契约字段
    "job_id", "timing", "strategy_trace", "artifacts", "cache",
}

TIMING_KEYS = {"fetch_ms", "parse_ms", "transcribe_ms",
               "comprehension_ms", "model_load_ms", "total_ms"}


def test_schema_version():
    d = ParseResult(url="https://example.com").to_dict()
    assert d["schema_version"] == SCHEMA_VERSION == "1.0"


def test_required_keys_present():
    d = ParseResult(url="https://example.com").to_dict()
    missing = REQUIRED_KEYS - set(d)
    assert not missing, f"missing keys: {missing}"


def test_error_detail_shape_with_structured_error():
    r = ParseResult(url="u", fetch_success=False)
    r.structured_error = StructuredError(
        code=ErrorCode.E_FETCH_TIMEOUT, message="t", retryable=True, hint="h",
    )
    d = r.to_dict()
    assert d["error_detail"] == {
        "code": "E_FETCH_TIMEOUT", "message": "t", "retryable": True, "hint": "h",
    }
    # v3 兼容: error 仍是字符串字段
    assert d["error"] is None


def test_error_detail_shape_legacy_string():
    r = ParseResult(url="u", fetch_success=False, error="boom")
    d = r.to_dict()
    assert d["error"] == "boom"
    ed = d["error_detail"]
    assert ed["code"] is None
    assert ed["message"] == "boom"
    assert ed["retryable"] is False
    assert ed["hint"] is None


def test_timing_shape():
    r = ParseResult(url="u")
    r.timing = TimingBreakdown(fetch_ms=1.0, total_ms=2.0)
    t = r.to_dict()["timing"]
    assert set(t) == TIMING_KEYS
    assert t["fetch_ms"] == 1.0
    assert t["total_ms"] == 2.0


def test_trace_artifacts_cache_defaults():
    d = ParseResult(url="u").to_dict()
    assert d["strategy_trace"] == []
    assert d["artifacts"] == {}
    assert d["cache"] == {}
    assert d["job_id"] is None
