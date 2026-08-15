"""
错误分类器（v4 任务 D，docs §7.2）

把异常对象 / 失败文本分类为结构化错误码，统一挂到 ParseResult.structured_error。

设计（D8 最小改造）：分类集中在 core 的公开结果出口处执行，
不改各 fetcher/parser/transcriber 内部错误点；内部点照旧填 error 文本。
"""

import asyncio
from typing import List, Optional

from .schema import ErrorCode, StructuredError, make_error

_TIMEOUT_TYPES = (TimeoutError, asyncio.TimeoutError)
_TIMEOUT_TEXT = ("timeout", "超时", "timed out")

_BLOCKED_TEXT = (
    "412", "cloudflare", "captcha", "验证码", "blocked", "access denied",
    "waf", "forbidden", "anti-bot", "安全验证", "风控",
)

_LOGIN_TEXT = ("登录", "login", "sign in", "登录后", "扫码登录")

_DEP_TEXT = (
    "not installed", "no module named", "unavailable (needed",
    "dependencies not available", "ffmpeg not found", "ffmpeg 未",
    "install with", "pip install",
)

_MODEL_TEXT = ("failed to load", "模型加载", "model load")

_DEVICE_TEXT = ("cuda", "out of memory", "显存", "gpu not available", "device unavailable")


def classify_exception(exc: BaseException, platform: str = "") -> StructuredError:
    """分类异常对象"""
    if isinstance(exc, _TIMEOUT_TYPES):
        return make_error(ErrorCode.E_FETCH_TIMEOUT, str(exc) or exc.__class__.__name__)
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return make_error(ErrorCode.E_DEP_MISSING, str(exc))
    return classify_message(str(exc), platform)


def classify_message(text: str, platform: str = "") -> StructuredError:
    """分类失败文本"""
    lower = (text or "").lower()
    if not lower.strip():
        return make_error(ErrorCode.E_INTERNAL, text or "unknown error")

    if any(k in lower for k in _TIMEOUT_TEXT):
        return make_error(ErrorCode.E_FETCH_TIMEOUT, text)
    if any(k in lower for k in _BLOCKED_TEXT):
        return make_error(ErrorCode.E_FETCH_BLOCKED, text)
    if platform in ("zhihu", "xiaohongshu", "weixin", "bilibili") and any(k in lower for k in _LOGIN_TEXT):
        return make_error(ErrorCode.E_FETCH_LOGIN_REQUIRED, text)
    if any(k in lower for k in _DEP_TEXT):
        return make_error(ErrorCode.E_DEP_MISSING, text)
    if any(k in lower for k in _MODEL_TEXT):
        return make_error(ErrorCode.E_MODEL_LOAD, text)
    if any(k in lower for k in _DEVICE_TEXT):
        return make_error(ErrorCode.E_DEVICE_UNAVAILABLE, text)
    return make_error(ErrorCode.E_INTERNAL, text)


def classify_result_error(result, retry_attempts: Optional[List] = None) -> StructuredError:
    """从 ParseResult + 重试记录推导结构化错误（core 出口统一调用）。

    优先级：访问受限记录（→ 登录墙）> error 文本分类 > 兜底 INTERNAL。
    """
    attempts = retry_attempts if retry_attempts is not None else getattr(result, "retry_attempts", []) or []
    restriction = next(
        (a.access_restriction_reason for a in attempts
         if getattr(a, "access_restriction_reason", None)),
        None,
    )
    if restriction:
        return make_error(ErrorCode.E_FETCH_LOGIN_REQUIRED, restriction)

    text = getattr(result, "error", None) or ""
    if text:
        return classify_message(text, getattr(result, "platform", ""))
    return make_error(ErrorCode.E_INTERNAL, "unknown error")
