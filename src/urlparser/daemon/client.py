"""
urlparserd 本地客户端（v4 M1 任务 E，CLI/库共用）

支持：submit/result(轮询)/cancel/list/health/subscribe(事件流)/shutdown，
以及 ensure_started()（未运行则静默拉起守护进程）。
"""

import asyncio
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Optional

from .protocol import (
    encode_line, parse_line, make_request, make_result, make_error,
)

DEFAULT_PORT = 47611

_CREATE_NO_WINDOW = 0x08000000


class DaemonError(Exception):
    """daemon 协议错误"""


class DaemonClient:
    """urlparserd 客户端（异步）"""

    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_PORT):
        self.host = host
        self.port = port

    # ── 基础请求 ──────────────────────────────────────────────

    async def _request(self, op: str, payload: Optional[Dict[str, Any]] = None,
                       req_id: str = "", timeout: float = 15.0) -> Dict[str, Any]:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout,
        )
        try:
            writer.write(encode_line(make_request(op, payload, req_id)))
            await writer.drain()
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout)
                if not line:
                    raise DaemonError("connection closed by daemon")
                msg = parse_line(line.decode("utf-8", errors="replace"))
                if msg is None:
                    continue
                if msg.get("type") == "error":
                    err = msg.get("error", {})
                    raise DaemonError(f"{err.get('code', 'E_UNKNOWN')}: {err.get('message', '')}")
                if msg.get("type") == "result":
                    return msg.get("payload") or {}
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    # ── 操作面 ────────────────────────────────────────────────

    async def health(self, timeout: float = 5.0) -> Dict[str, Any]:
        return await self._request("health", timeout=timeout)

    async def submit(self, op: str, payload: Dict[str, Any]) -> str:
        data = await self._request("submit", {"op": op, "payload": payload})
        return data.get("job_id", "")

    async def result(self, job_id: str) -> Dict[str, Any]:
        return await self._request("result", {"job_id": job_id})

    async def wait(self, job_id: str, timeout: Optional[float] = None,
                   poll_interval: float = 0.5) -> Dict[str, Any]:
        """轮询直到作业终结"""
        deadline = None if timeout is None else time.time() + timeout
        while True:
            data = await self.result(job_id)
            if data.get("status") in ("succeeded", "failed", "cancelled"):
                return data
            if deadline is not None and time.time() > deadline:
                raise DaemonError(f"wait timeout for job {job_id}")
            await asyncio.sleep(poll_interval)

    async def cancel(self, job_id: str) -> bool:
        data = await self._request("cancel", {"job_id": job_id})
        return bool(data.get("cancelled"))

    async def list_jobs(self) -> List[Dict[str, Any]]:
        data = await self._request("list")
        return data.get("jobs", [])

    async def prewarm(self, models: Optional[List[str]] = None) -> Dict[str, Any]:
        """预热模型（M3）"""
        return await self._request("prewarm", {"models": models})

    async def models(self) -> Dict[str, Any]:
        """模型注册表状态（M3）"""
        return await self._request("models")

    async def shutdown(self) -> bool:
        data = await self._request("shutdown", timeout=5.0)
        return bool(data.get("ok"))

    async def subscribe(self, job_id: str,
                        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
                        timeout: Optional[float] = None) -> Dict[str, Any]:
        """订阅作业事件流（回放缓冲 + 实时），终结时返回结果视图"""
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), 5.0,
        )
        try:
            writer.write(encode_line(make_request("subscribe", {"job_id": job_id}, "sub")))
            await writer.drain()
            deadline = None if timeout is None else time.time() + timeout
            while True:
                if deadline is not None and time.time() > deadline:
                    raise DaemonError(f"subscribe timeout for job {job_id}")
                if timeout is None:
                    line = await reader.readline()
                else:
                    line = await asyncio.wait_for(reader.readline(), 5.0)
                if not line:
                    raise DaemonError("connection closed by daemon")
                msg = parse_line(line.decode("utf-8", errors="replace"))
                if msg is None:
                    continue
                if msg.get("type") == "event":
                    if on_event is not None:
                        on_event(msg.get("event") or {})
                elif msg.get("type") == "result":
                    return msg.get("payload") or {}
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    # ── 连接探测与自动拉起 ────────────────────────────────────

    @classmethod
    async def is_running(cls, host: str = "127.0.0.1",
                         port: int = DEFAULT_PORT) -> bool:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), 1.5,
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return True
        except Exception:
            return False

    @classmethod
    async def ensure_started(cls, host: str = "127.0.0.1",
                             port: int = DEFAULT_PORT,
                             wait_sec: float = 10.0) -> bool:
        """daemon 未运行时静默拉起（Windows 下无窗口），返回是否可用"""
        if await cls.is_running(host, port):
            return True
        try:
            flags = _CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.Popen(
                [sys.executable, "-m", "urlparser.daemon", "--port", str(port)],
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except Exception:
            return False
        deadline = time.time() + wait_sec
        while time.time() < deadline:
            if await cls.is_running(host, port):
                return True
            await asyncio.sleep(0.3)
        return False
