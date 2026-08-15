"""
urlparserd 本地守护进程包（v4 M1 任务 E，docs/v4-implementation-plan.md §E）

单机常驻执行面：浏览器复用、作业提交/取消、进度事件、跨进程缓存。
回环 TCP + JSON-lines 私有协议（决策 D11：非 HTTP 对外面）。
"""

from .client import DaemonClient, DEFAULT_PORT, DaemonError
from .jobstore import JobStore, Job, JobStatus
from .server import DaemonServer

__all__ = [
    'DaemonClient',
    'DEFAULT_PORT',
    'DaemonError',
    'JobStore',
    'Job',
    'JobStatus',
    'DaemonServer',
]
