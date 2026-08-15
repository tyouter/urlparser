"""
Schema v1 数据契约与结构化错误模型

v4 契约层（见 docs/product-plan-and-architecture.md §7.1/§7.2）：
- SCHEMA_VERSION: 结果 schema 版本，只增不改
- ErrorCode: 结构化错误码，每码带 retryable + hint 语义
- StructuredError: 取代自由文本 error 的机器可读错误
- TimingBreakdown: 各阶段耗时分解（可观测性）
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


SCHEMA_VERSION = "1.0"


class ErrorCode(str, Enum):
    """结构化错误码（v4 契约 §7.2）"""

    # 获取层
    E_FETCH_BLOCKED = "E_FETCH_BLOCKED"                # 被反爬/验证码拦截
    E_FETCH_LOGIN_REQUIRED = "E_FETCH_LOGIN_REQUIRED"  # 登录墙
    E_FETCH_TIMEOUT = "E_FETCH_TIMEOUT"                # 超时
    # 解析层
    E_PARSE_EMPTY = "E_PARSE_EMPTY"                    # 页面可取但正文为空
    # 转录/理解层
    E_DEVICE_UNAVAILABLE = "E_DEVICE_UNAVAILABLE"      # 指定设备不可用
    E_MODEL_LOAD = "E_MODEL_LOAD"                      # 模型加载失败
    # 环境与调用
    E_DEP_MISSING = "E_DEP_MISSING"                    # 依赖缺失（ffmpeg/funasr 等）
    E_BUDGET_EXCEEDED = "E_BUDGET_EXCEEDED"            # 超预算主动中止
    E_VALIDATION = "E_VALIDATION"                      # 输入非法（协议/内网等）
    E_INTERNAL = "E_INTERNAL"                          # 内部异常


@dataclass
class StructuredError:
    """机器可读错误（v4 契约 §7.2）"""

    code: Optional[ErrorCode] = None
    message: str = ""
    retryable: bool = False
    hint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code.value if self.code else None,
            "message": self.message or None,
            "retryable": self.retryable,
            "hint": self.hint,
        }

    def __str__(self) -> str:
        """兼容 v3 的自由文本读取"""
        return self.message or ""


# 错误码 → 默认 retryable / hint 语义（单一事实源）
ERROR_CODE_META: Dict[ErrorCode, Dict[str, Any]] = {
    ErrorCode.E_FETCH_BLOCKED: {
        "retryable": True,
        "hint": "切换策略（bb-browser/用户浏览器）或稍后重试",
    },
    ErrorCode.E_FETCH_LOGIN_REQUIRED: {
        "retryable": True,
        "hint": "运行: python -m urlparser.cookies_manager login <platform>",
    },
    ErrorCode.E_FETCH_TIMEOUT: {
        "retryable": True,
        "hint": "增大 --budget 或使用快路径 --strategy http",
    },
    ErrorCode.E_PARSE_EMPTY: {
        "retryable": False,
        "hint": "页面可能需要登录或为纯动态渲染",
    },
    ErrorCode.E_DEP_MISSING: {
        "retryable": False,
        "hint": "运行: python -m urlparser doctor --fix",
    },
    ErrorCode.E_DEVICE_UNAVAILABLE: {
        "retryable": False,
        "hint": "降级 device=cpu 或修改配置文件",
    },
    ErrorCode.E_BUDGET_EXCEEDED: {
        "retryable": True,
        "hint": "增大预算或降级 mode=metadata",
    },
    ErrorCode.E_VALIDATION: {
        "retryable": False,
        "hint": "检查 URL 协议与网络可达性",
    },
    ErrorCode.E_MODEL_LOAD: {
        "retryable": True,
        "hint": "切换 engine 或检查显存余量",
    },
    ErrorCode.E_INTERNAL: {
        "retryable": True,
        "hint": "幂等重试一次后报告",
    },
}


def make_error(
    code: ErrorCode,
    message: str,
    hint: Optional[str] = None,
    retryable: Optional[bool] = None,
) -> StructuredError:
    """按错误码构造 StructuredError，retryable/hint 取默认语义，可覆盖"""
    meta = ERROR_CODE_META.get(code, {})
    return StructuredError(
        code=code,
        message=message,
        retryable=meta.get("retryable", False) if retryable is None else retryable,
        hint=hint or meta.get("hint"),
    )


@dataclass
class TimingBreakdown:
    """各阶段耗时分解（毫秒），v4 可观测性契约"""

    fetch_ms: float = 0.0
    parse_ms: float = 0.0
    transcribe_ms: float = 0.0
    comprehension_ms: float = 0.0
    model_load_ms: float = 0.0
    total_ms: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "fetch_ms": round(self.fetch_ms, 1),
            "parse_ms": round(self.parse_ms, 1),
            "transcribe_ms": round(self.transcribe_ms, 1),
            "comprehension_ms": round(self.comprehension_ms, 1),
            "model_load_ms": round(self.model_load_ms, 1),
            "total_ms": round(self.total_ms, 1),
        }
