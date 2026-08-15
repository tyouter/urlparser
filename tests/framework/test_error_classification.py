"""
错误分类测试（v4 任务 D）

验证 classify_exception / classify_message / classify_result_error
按 docs §7.2 的错误码语义工作，分类命中率 ≥95%。
"""

import asyncio

import pytest

from urlparser.errors import classify_exception, classify_message, classify_result_error
from urlparser.models import ParseResult, RetryAttempt
from urlparser.schema import ErrorCode, make_error


# (输入异常, 平台, 期望错误码) —— 分类命中率样本集
CASES = [
    (TimeoutError("connection timed out"), "", ErrorCode.E_FETCH_TIMEOUT),
    (asyncio.TimeoutError(), "", ErrorCode.E_FETCH_TIMEOUT),
    (ImportError("No module named 'funasr'"), "", ErrorCode.E_DEP_MISSING),
    (ModuleNotFoundError("No module named 'yt_dlp'"), "", ErrorCode.E_DEP_MISSING),
    (RuntimeError("HTTP 412 Precondition Failed"), "", ErrorCode.E_FETCH_BLOCKED),
    (RuntimeError("Cloudflare blocked the request"), "", ErrorCode.E_FETCH_BLOCKED),
    (RuntimeError("页面需要登录后查看"), "zhihu", ErrorCode.E_FETCH_LOGIN_REQUIRED),
    (RuntimeError("Failed to load FunASR model"), "", ErrorCode.E_MODEL_LOAD),
    (RuntimeError("CUDA out of memory"), "", ErrorCode.E_DEVICE_UNAVAILABLE),
    (RuntimeError("something unexpected"), "", ErrorCode.E_INTERNAL),
]


@pytest.mark.parametrize("exc,platform,expected", CASES)
def test_classify_exception(exc, platform, expected):
    se = classify_exception(exc, platform)
    assert se.code == expected


def test_classify_message_never_none():
    # 任意文本都必须给出错误码（不返回 None）
    for text in ["", "???", "unknown", "null", "404"]:
        se = classify_message(text)
        assert se.code is not None
        assert se.code in ErrorCode


def test_retryable_and_hint_defaults():
    se = classify_message("timed out")
    assert se.retryable is True
    assert se.hint


def test_result_classification_from_restriction():
    r = ParseResult(url="u", platform="zhihu", fetch_success=False)
    attempts = [RetryAttempt(strategy="cookie", access_restriction_reason="restricted: login wall")]
    se = classify_result_error(r, attempts)
    assert se.code == ErrorCode.E_FETCH_LOGIN_REQUIRED


def test_result_classification_from_text():
    r = ParseResult(url="u", platform="generic", fetch_success=False, error="HTTP 412")
    assert classify_result_error(r, []).code == ErrorCode.E_FETCH_BLOCKED


def test_result_classification_fallback():
    r = ParseResult(url="u", platform="generic", fetch_success=False)
    assert classify_result_error(r, []).code == ErrorCode.E_INTERNAL


def test_make_error_override():
    se = make_error(ErrorCode.E_FETCH_TIMEOUT, "t", retryable=False, hint="x")
    assert se.retryable is False
    assert se.hint == "x"


def test_classification_hit_rate():
    """分类样本集命中率 100%（验收阈值 ≥95%）"""
    hits = sum(
        1 for exc, platform, expected in CASES
        if classify_exception(exc, platform).code == expected
    )
    assert hits == len(CASES)
