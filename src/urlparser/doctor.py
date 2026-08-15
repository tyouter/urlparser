"""
urlparser doctor - 环境自检模块

v4 doctor 自检（docs/v4-implementation-plan.md 任务 G）

一键运行: python -m urlparser.doctor

探测内容:
    - python_version        Python 版本（要求 >= 3.9）
    - core_deps             核心依赖 (playwright / yt-dlp / bs4 / lxml / trafilatura)
    - ffmpeg                ffmpeg 可执行文件（PATH / imageio-ffmpeg / 常见安装路径）
    - playwright_browsers   Playwright Chromium 真实启动探测（仅当 playwright 可导入时）
    - gpu                   NV CUDA (torch) / Intel NPU/GPU (OpenVINO) 加速设备
    - optional_deps         可选依赖（转录 / 理解 / 图片等）
    - daemon                bb-browser daemon 控制端口连通性（v4 未构建则为 unknown）

CLI:
    python -m urlparser.doctor          输出人类可读报告
    python -m urlparser.doctor --json   输出机器可读 JSON（ensure_ascii=False, indent=2）
    python -m urlparser.doctor --fix    尝试自动安装缺失的核心 / 转录依赖

约定: 除标准库与无重依赖的 find_ffmpeg 外，所有第三方导入均在函数内部惰性执行，
      run_checks() 永不抛出异常。
"""

import argparse
import importlib.util
import json
import socket
import sys
from dataclasses import dataclass
from typing import List, Optional

# 顶层仅允许标准库 + 无重依赖的相对导入工具函数
from .utils.ffmpeg_utils import find_ffmpeg

__all__ = ["HealthCheck", "HealthReport", "run_checks", "main"]

# 核心依赖（任一缺失即为 fail）
CORE_MODULES = ("playwright", "yt_dlp", "bs4", "lxml", "trafilatura")

# 可选依赖（全部缺失为 warn，部分存在为 ok）
OPTIONAL_MODULES = (
    "funasr", "faster_whisper", "openvino", "openvino_genai",
    "llama_cpp", "curl_cffi", "requests", "pillow",
)

# daemon 默认控制端口（DaemonClient.DEFAULT_PORT 不存在时的兜底值）
DAEMON_DEFAULT_PORT = 47611


@dataclass
class HealthCheck:
    """单项检查结果。"""
    name: str
    status: str  # "ok" | "warn" | "fail" | "unknown"
    detail: str
    fix_hint: Optional[str] = None


@dataclass
class HealthReport:
    """整体自检报告。"""
    checks: List[HealthCheck]

    @property
    def healthy(self) -> bool:
        """无任何 fail 项即为健康。"""
        return not any(c.status == "fail" for c in self.checks)

    def to_text(self) -> str:
        """人类可读报告。"""
        fail_count = sum(1 for c in self.checks if c.status == "fail")
        warn_count = sum(1 for c in self.checks if c.status == "warn")
        lines = [
            "=" * 58,
            "urlparser 环境自检报告",
            "=" * 58,
            "检查项: {} | fail: {} | warn: {} | 结论: {}".format(
                len(self.checks), fail_count, warn_count,
                "HEALTHY" if self.healthy else "UNHEALTHY",
            ),
            "-" * 58,
        ]
        for check in self.checks:
            lines.append("[{:7s}] {}: {}".format(check.status.upper(), check.name, check.detail))
            if check.fix_hint:
                lines.append("        修复: {}".format(check.fix_hint))
        lines.append("-" * 58)
        if self.healthy:
            lines.append("结论: 环境健康，可以正常使用 urlparser。")
        else:
            lines.append("结论: 存在 fail 项，请按上方修复提示处理后再试。")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """机器可读字典。"""
        return {
            "healthy": self.healthy,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "detail": c.detail,
                    "fix_hint": c.fix_hint,
                }
                for c in self.checks
            ],
        }

    def to_json(self) -> str:
        """机器可读 JSON（ensure_ascii=False, indent=2）。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 单项检查实现（每个都完全防御，不向外抛异常）
# ---------------------------------------------------------------------------

def _check_python_version() -> HealthCheck:
    """Python 版本检查: < 3.9 为 fail。"""
    ver = sys.version_info
    version_str = "{}.{}.{}".format(ver.major, ver.minor, ver.micro)
    if ver < (3, 9):
        return HealthCheck(
            name="python_version",
            status="fail",
            detail="Python {} 版本过低，urlparser 要求 >= 3.9".format(version_str),
            fix_hint="请升级 Python 到 3.9 或更高版本",
        )
    return HealthCheck(
        name="python_version",
        status="ok",
        detail="Python {}（要求 >= 3.9）".format(version_str),
    )


def _check_core_deps() -> HealthCheck:
    """核心依赖检查: 任一缺失为 fail。"""
    missing = []
    for name in CORE_MODULES:
        try:
            if importlib.util.find_spec(name) is None:
                missing.append(name)
        except (ImportError, ValueError, AttributeError):
            missing.append(name)
    if missing:
        return HealthCheck(
            name="core_deps",
            status="fail",
            detail="缺失核心依赖: " + ", ".join(missing),
            fix_hint="请执行: pip install urlparser[core]"
                     "（或 pip install playwright yt-dlp beautifulsoup4 lxml trafilatura）",
        )
    return HealthCheck(
        name="core_deps",
        status="ok",
        detail="核心依赖全部已安装: " + ", ".join(CORE_MODULES),
    )


def _check_ffmpeg() -> HealthCheck:
    """ffmpeg 检查: 未找到 / 不可执行为 warn。"""
    hint = "请安装 ffmpeg 并加入 PATH（例如 https://ffmpeg.org/download.html 或 winget install ffmpeg）"
    try:
        path = find_ffmpeg()
    except Exception as e:  # noqa: BLE001 - doctor 检查必须完全防御
        return HealthCheck(
            name="ffmpeg",
            status="warn",
            detail="ffmpeg 检测异常: {}".format(e),
            fix_hint=hint,
        )
    if not path:
        return HealthCheck(
            name="ffmpeg",
            status="warn",
            detail="未找到 ffmpeg",
            fix_hint=hint,
        )
    # find_ffmpeg 在极端情况下会兜底返回字面量 "ffmpeg"，此处再探测一次真实可执行性
    try:
        from .utils._subprocess_win import run_nowindow
        result = run_nowindow([path, "-version"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return HealthCheck(
                name="ffmpeg",
                status="warn",
                detail="ffmpeg 命令不可用（returncode={}）: {}".format(result.returncode, path),
                fix_hint=hint,
            )
    except Exception as e:  # noqa: BLE001
        return HealthCheck(
            name="ffmpeg",
            status="warn",
            detail="ffmpeg 不可用: {}（{}）".format(path, e),
            fix_hint=hint,
        )
    return HealthCheck(
        name="ffmpeg",
        status="ok",
        detail="ffmpeg: {}".format(path),
    )


def _check_playwright_browsers() -> HealthCheck:
    """Playwright Chromium 启动检查（仅当 playwright 可导入时执行）。

    整个探测包在 try/except/finally 中，任何异常均记录为 fail，绝不向外抛出；
    launch 显式设置 30 秒超时上限（Windows 下 signal 超时不可靠，用简单 try 即可）。
    """
    try:
        if importlib.util.find_spec("playwright") is None:
            return HealthCheck(
                name="playwright_browsers",
                status="unknown",
                detail="playwright 未安装，跳过浏览器启动检查",
                fix_hint="请执行: pip install urlparser[core] 后再运行 python -m playwright install chromium",
            )
    except Exception as e:  # noqa: BLE001
        return HealthCheck(
            name="playwright_browsers",
            status="unknown",
            detail="playwright 探测失败: {}".format(e),
        )
    pw = None
    browser = None
    try:
        import contextlib
        import gc
        import io
        import logging
        # 失败路径（如沙箱禁止派生驱动进程）会遗留未回收的 asyncio Future，
        # 其 __del__ 会向 stderr 打印 "Future exception was never retrieved"。
        # 因此异常必须在窗口内捕获（释放 traceback 对 loop/future 的引用），
        # 再抬高 asyncio 日志级别并强制 GC，把这类噪音收进窗口内。
        _async_logger = logging.getLogger("asyncio")
        _old_level = _async_logger.level
        _async_logger.setLevel(logging.CRITICAL)
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                try:
                    from playwright.sync_api import sync_playwright
                    pw = sync_playwright().start()
                    # 30 秒超时上限；启动失败（缺浏览器 / 缺 DLL / 沙箱限制）一律按 fail 记录
                    browser = pw.chromium.launch(headless=True, timeout=30_000)
                    browser.close()
                    browser = None
                except Exception as e:  # noqa: BLE001
                    return HealthCheck(
                        name="playwright_browsers",
                        status="fail",
                        detail="Playwright 浏览器启动失败: {}".format(e),
                        fix_hint="请执行: python -m playwright install chromium",
                    )
        finally:
            gc.collect()
            _async_logger.setLevel(_old_level)
    finally:
        # 资源回收: 无论成功失败都确保浏览器与驱动进程被关闭
        if browser is not None:
            try:
                browser.close()
            except Exception:  # noqa: BLE001
                pass
        if pw is not None:
            try:
                pw.stop()
            except Exception:  # noqa: BLE001
                pass
    return HealthCheck(
        name="playwright_browsers",
        status="ok",
        detail="Playwright Chromium 可正常启动",
    )


def _check_gpu() -> HealthCheck:
    """GPU/NPU 检查: 未检测到加速设备时仍为 ok（转录/理解将走 CPU）。"""
    # 1) NV CUDA: torch.cuda.is_available()
    try:
        import torch  # 惰性导入
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            return HealthCheck(
                name="gpu",
                status="ok",
                detail="CUDA GPU 可用: {}".format(device_name),
            )
    except Exception:  # noqa: BLE001 - torch 缺失/损坏均走下一级探测
        pass
    # 2) Intel NPU/GPU: OpenVINO available_devices
    try:
        import openvino as ov  # 惰性导入
        devices = list(ov.Core().available_devices or [])
        accel = [
            d for d in devices
            if d.upper() in ("NPU", "GPU")
            or d.upper().startswith(("NPU.", "GPU."))
        ]
        if accel:
            return HealthCheck(
                name="gpu",
                status="ok",
                detail="OpenVINO 加速设备: " + ", ".join(accel),
            )
    except Exception:  # noqa: BLE001
        pass
    return HealthCheck(
        name="gpu",
        status="ok",
        detail="未检测到 GPU/NPU，转录/理解将走 CPU",
    )


def _check_optional_deps() -> HealthCheck:
    """可选依赖检查: 全部缺失为 warn，部分存在为 ok。"""
    installed, missing = [], []
    for name in OPTIONAL_MODULES:
        probe = name
        if name == "pillow":
            probe = "PIL"  # pillow 的模块名为 PIL，find_spec("pillow") 会落空
        found = False
        try:
            if importlib.util.find_spec(probe) is not None:
                found = True
        except (ImportError, ValueError, AttributeError):
            found = False
        (installed if found else missing).append(name)
    if not installed:
        return HealthCheck(
            name="optional_deps",
            status="warn",
            detail="可选依赖全部未安装: " + ", ".join(missing),
            fix_hint="如需转录/理解/图片能力，请按需安装: "
                     "pip install urlparser[transcribe] / urlparser[comprehension] / urlparser[images]",
        )
    detail = "已安装: " + ", ".join(installed)
    if missing:
        detail += "；未安装: " + ", ".join(missing)
    return HealthCheck(
        name="optional_deps",
        status="ok",
        detail=detail,
    )


def _check_daemon() -> HealthCheck:
    """daemon 控制端口检查: 未安装为 unknown；端口不通为 warn；任何意外异常为 unknown。"""
    try:
        # 注意: 不能用相对导入 ..daemon.client —— urlparser.doctor 的
        # __package__ 是 "urlparser"，一级相对导入即越出顶层包
        from urlparser.daemon.client import DaemonClient  # 惰性导入，v4 阶段可能未构建
    except ImportError:
        return HealthCheck(
            name="daemon",
            status="unknown",
            detail="daemon 模块未安装（v4 阶段未构建）",
        )
    except Exception as e:  # noqa: BLE001
        return HealthCheck(
            name="daemon",
            status="unknown",
            detail="daemon 模块导入异常: {}".format(e),
        )
    try:
        port = int(getattr(DaemonClient, "DEFAULT_PORT", DAEMON_DEFAULT_PORT))
    except Exception as e:  # noqa: BLE001
        return HealthCheck(
            name="daemon",
            status="unknown",
            detail="读取 daemon 控制端口失败: {}".format(e),
        )
    try:
        sock = socket.create_connection(("127.0.0.1", port), timeout=2)
    except OSError as e:
        return HealthCheck(
            name="daemon",
            status="warn",
            detail="daemon 控制端口 127.0.0.1:{} 无法连接: {}".format(port, e),
            fix_hint="请先启动 bb-browser / daemon 服务后再试",
        )
    except Exception as e:  # noqa: BLE001
        return HealthCheck(
            name="daemon",
            status="unknown",
            detail="daemon 连通性检测异常: {}".format(e),
        )
    try:
        sock.close()
    except Exception:  # noqa: BLE001
        pass
    return HealthCheck(
        name="daemon",
        status="ok",
        detail="daemon 控制端口 127.0.0.1:{} 可连接".format(port),
    )


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def run_checks() -> HealthReport:
    """执行全部环境自检并返回报告（每个单项均防御式实现，不会抛出异常）。"""
    checks = [
        _check_python_version(),
        _check_core_deps(),
        _check_ffmpeg(),
        _check_playwright_browsers(),
        _check_gpu(),
        _check_optional_deps(),
        _check_daemon(),
    ]
    return HealthReport(checks=checks)


def main(argv=None) -> int:
    """CLI 入口: python -m urlparser.doctor [--json] [--fix]"""
    parser = argparse.ArgumentParser(
        prog="urlparser.doctor",
        description="urlparser 环境自检（v4 doctor，docs/v4-implementation-plan.md 任务 G）",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出报告（机器可读）")
    parser.add_argument("--fix", action="store_true", help="尝试自动安装缺失的核心 / 转录依赖")
    args = parser.parse_args(argv)

    report = run_checks()

    def _msg(text: str) -> None:
        # --json 模式下修复提示走 stderr，保证 stdout 是纯净 JSON
        if args.json:
            print(text, file=sys.stderr)
        else:
            print(text)

    if args.json:
        print(report.to_json())
    else:
        print(report.to_text())

    if args.fix:
        _msg("自动修复依赖")
        try:
            # 同 _check_daemon: 相对导入会越出顶层包，此处用绝对导入
            from urlparser.dependency_installer import (
                ensure_core_dependencies,
                ensure_transcribe_dependencies,
            )
        except Exception as e:  # noqa: BLE001
            _msg("警告: 无法加载依赖安装器: {}".format(e))
            return 0 if report.healthy else 1
        for fn in (ensure_core_dependencies, ensure_transcribe_dependencies):
            fn_name = getattr(fn, "__name__", str(fn))
            try:
                try:
                    fn(auto_install=True)
                except TypeError:
                    # 兼容不接受 auto_install 关键字参数的旧签名
                    fn()
            except Exception as e:  # noqa: BLE001
                _msg("警告: {} 执行失败: {}".format(fn_name, e))

    return 0 if report.healthy else 1


if __name__ == "__main__":
    sys.exit(main())
