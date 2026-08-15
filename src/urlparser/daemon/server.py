"""
urlparserd 主进程（v4 M1 任务 E）

回环 TCP + JSON-lines 服务器 + 作业调度：
- 作业队列（并发准入 Semaphore）+ 提交/轮询/取消
- 四段进度事件缓冲与订阅流
- 默认 job runner 复用 core 的 parse/parse_batch（浏览器复用开启）
- 重启恢复（JobStore.recover）
"""

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, Set

from .jobstore import JobStore, Job, JobStatus
from .protocol import (
    encode_line, parse_line, make_request, make_result, make_error,
)
from ..model_registry import ModelRegistry

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = str(Path.home() / ".urlparser" / "daemon" / "jobs.db")

# 默认作业执行器共享的模型注册表（server 启动时注入；None 时不启用常驻）
MODEL_REGISTRY: Optional[ModelRegistry] = None

# job_runner(op, payload, on_progress) -> result dict
JobRunner = Callable[[str, Dict[str, Any], Optional[Callable]], Awaitable[Dict[str, Any]]]


async def default_job_runner(op: str, payload: Dict[str, Any],
                             on_progress: Optional[Callable] = None) -> Dict[str, Any]:
    """默认执行器：复用 core 的 parse / parse_batch（daemon 模式开浏览器复用）"""
    from ..core import UrlParser
    from ..config import ParseConfig, ComprehensionConfig

    if op == "transcribe":
        return await _run_transcribe_job(payload)

    url = payload.get("url")
    urls = payload.get("urls")

    cfg = ParseConfig(on_progress=on_progress)
    cfg.retry.enabled = bool(payload.get("retry", True))
    if payload.get("comprehension"):
        cfg.comprehension = ComprehensionConfig(
            enabled=True,
            mode=payload.get("comp_mode", "audio_video"),
            max_frames=int(payload.get("max_frames", 50)),
        )

    parser = UrlParser(cfg)
    parser.enable_fetcher_reuse = True
    try:
        if urls:
            results = await parser.parse_batch(
                urls,
                concurrent=int(payload.get("concurrent", 3)),
            )
            return {"results": [r.to_dict() for r in results]}

        if not url:
            raise ValueError("payload 缺少 url 或 urls")

        result = await parser.parse(
            url,
            mode=payload.get("mode", "full"),
            strategy=payload.get("strategy"),
            budget_ms=int(payload.get("budget_ms", 0)),
            force_refresh=bool(payload.get("no_cache", False)),
        )
        return {"results": [result.to_dict()]}
    finally:
        await parser.close()


async def _run_transcribe_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    """daemon op=transcribe：本地文件或 URL 转录（FunASR 优先，Whisper 备选）"""
    import asyncio

    from ..dependency_installer import ensure_transcribe_dependencies
    from ..transcriber import FunASRTranscriber, WhisperTranscriber

    if not ensure_transcribe_dependencies(auto_install=True):
        raise RuntimeError("转录依赖不完整（E_DEP_MISSING）")

    language = payload.get("language", "zh")
    engine = payload.get("engine", "auto")
    model_size = payload.get("model_size", "large")
    device = payload.get("device", "auto")

    # v4 M3：模型注册表可用时走常驻模型路径（避免每请求加载）
    if MODEL_REGISTRY is not None and not payload.get("no_registry"):
        return await _transcribe_via_registry(
            payload, language, engine, model_size, device,
        )

    if engine == "whisper" or (engine == "auto" and not FunASRTranscriber.is_available()):
        transcriber = WhisperTranscriber(model_size=model_size, device=device)
    else:
        transcriber = FunASRTranscriber(model_size=model_size, device=device)

    url = payload.get("url")
    file_path = payload.get("file_path")
    loop = asyncio.get_event_loop()

    if url:
        result = await loop.run_in_executor(
            None, lambda: transcriber.transcribe_from_url(url, language=language),
        )
    elif file_path:
        from ..utils.media_utils import is_video_file
        if is_video_file(file_path):
            result = await loop.run_in_executor(
                None,
                lambda: transcriber.transcribe_from_local_video(
                    file_path, language=language,
                ),
            )
        else:
            result = await loop.run_in_executor(
                None, lambda: transcriber.transcribe(file_path, language=language),
            )
    else:
        raise ValueError("transcribe 需要 url 或 file_path")

    return {"transcription": result.to_dict()}


async def _transcribe_via_registry(payload: Dict[str, Any], language: str,
                                  engine: str, model_size: str,
                                  device: str) -> Dict[str, Any]:
    """经模型注册表取常驻模型转录（M3：模型加载只发生一次）"""
    import asyncio

    from ..transcriber import FunASRTranscriber, WhisperTranscriber

    reg = MODEL_REGISTRY
    if engine == "whisper" or (engine == "auto" and not FunASRTranscriber.is_available()):
        real_engine, vram_mb, keepalive = "whisper", 1200.0, "idle"
    else:
        real_engine, vram_mb, keepalive = "funasr", 650.0, "always"
    key = f"asr-{real_engine}-{model_size}-{device}"

    if not reg.is_registered(key):
        if real_engine == "funasr":
            def loader():
                t = FunASRTranscriber(model_size=model_size, device=device)
                t._load_model()
                return t._model
            reg.register(key, loader, vram_mb=vram_mb, keepalive=keepalive)
        else:
            def loader():
                t = WhisperTranscriber(model_size=model_size, device=device)
                t._load_model()
                return t._model
            reg.register(key, loader, vram_mb=vram_mb,
                         keepalive=keepalive, idle_sec=300.0)

    model = reg.acquire(key)
    try:
        if real_engine == "funasr":
            transcriber = FunASRTranscriber(
                model_size=model_size, device=device, preloaded_model=model,
            )
        else:
            transcriber = WhisperTranscriber(
                model_size=model_size, device=device, preloaded_model=model,
            )

        url = payload.get("url")
        file_path = payload.get("file_path")
        loop = asyncio.get_event_loop()
        if url:
            result = await loop.run_in_executor(
                None, lambda: transcriber.transcribe_from_url(url, language=language),
            )
        elif file_path:
            from ..utils.media_utils import is_video_file
            if is_video_file(file_path):
                result = await loop.run_in_executor(
                    None,
                    lambda: transcriber.transcribe_from_local_video(
                        file_path, language=language,
                    ),
                )
            else:
                result = await loop.run_in_executor(
                    None, lambda: transcriber.transcribe(file_path, language=language),
                )
        else:
            raise ValueError("transcribe 需要 url 或 file_path")

        return {"transcription": result.to_dict(),
                "model": {"registry_key": key, "engine": real_engine}}
    finally:
        reg.release(key)


class _WeightedGate:
    """GPU 显存准入（加权信号量，M3 任务 F8：显存申报排队，防 OOM）"""

    def __init__(self, capacity_mb: Optional[float]):
        self.capacity = capacity_mb
        self.used = 0.0
        self._cond = asyncio.Condition()

    async def acquire(self, amount_mb: float):
        if amount_mb <= 0:
            return
        async with self._cond:
            while self.capacity is not None and self.used + amount_mb > self.capacity:
                await self._cond.wait()
            self.used += amount_mb

    async def release(self, amount_mb: float):
        if amount_mb <= 0:
            return
        async with self._cond:
            self.used = max(0.0, self.used - amount_mb)
            self._cond.notify_all()


class DaemonServer:
    """urlparserd 服务器"""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 47611,
        job_runner: Optional[JobRunner] = None,
        db_path: Optional[str] = None,
        max_concurrent: int = 3,
        vram_budget_mb: Optional[float] = None,
        model_registry: Optional[ModelRegistry] = None,
    ):
        global MODEL_REGISTRY
        self.host = host
        self.port = port
        self.job_runner = job_runner or default_job_runner
        self._store = JobStore(db_path if db_path is not None else ":memory:")
        self._sem = asyncio.Semaphore(max_concurrent)
        # M3：模型常驻注册表 + GPU 显存准入门
        MODEL_REGISTRY = model_registry if model_registry is not None else ModelRegistry(vram_budget_mb)
        self._registry = MODEL_REGISTRY
        self._gate = _WeightedGate(vram_budget_mb)
        self._server: Optional[asyncio.Server] = None
        self._jobs: Dict[str, Job] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._events: Dict[str, list] = {}
        self._writers: Set[asyncio.StreamWriter] = set()
        self._stop_requested = False

    # ── 生命周期 ──────────────────────────────────────────────

    async def start(self):
        self._store.recover()
        for job in self._store.list_all():
            self._jobs[job.id] = job
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port,
        )
        self.port = self._server.sockets[0].getsockname()[1]
        logger.info("urlparserd listening on %s:%s", self.host, self.port)

    async def serve_forever(self):
        if self._server is None:
            await self.start()
        async with self._server:
            await self._server.serve_forever()

    async def stop(self):
        self._stop_requested = True
        for task in list(self._tasks.values()):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        if self._server is not None:
            self._server.close()
            try:
                await self._server.wait_closed()
            except Exception:
                pass
        self._store.close()

    # ── 客户端处理 ────────────────────────────────────────────

    async def _handle_client(self, reader: asyncio.StreamReader,
                             writer: asyncio.StreamWriter):
        self._writers.add(writer)
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                msg = parse_line(line.decode("utf-8", errors="replace"))
                if msg is None:
                    continue
                await self._dispatch(writer, msg)
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        except Exception as e:
            logger.debug("client error: %s", e)
        finally:
            self._writers.discard(writer)
            try:
                writer.close()
            except Exception:
                pass

    async def _dispatch(self, writer: asyncio.StreamWriter, msg: Dict[str, Any]):
        req_id = msg.get("id", "")
        op = msg.get("op", "")
        payload = msg.get("payload") or {}

        try:
            if op == "health":
                await self._send(writer, make_result(req_id, {
                    "status": "ok",
                    "jobs": {s: sum(1 for j in self._jobs.values() if j.status == s)
                             for s in ("queued", "running", "succeeded", "failed", "cancelled")},
                }))
            elif op == "echo":
                await self._send(writer, make_result(req_id, {"echo": payload}))
            elif op == "submit":
                job_id = self._submit(payload.get("op", "parse"), payload.get("payload", {}))
                await self._send(writer, make_result(req_id, {"job_id": job_id}))
            elif op == "result":
                job = self._jobs.get(payload.get("job_id", ""))
                if job is None:
                    await self._send(writer, make_error(req_id, "E_JOB_NOT_FOUND", "job not found"))
                else:
                    await self._send(writer, make_result(req_id, self._job_view(job)))
            elif op == "list":
                await self._send(writer, make_result(req_id, {
                    "jobs": [self._job_view(j) for j in self._jobs.values()],
                }))
            elif op == "prewarm":
                await self._send(writer, make_result(req_id, self._registry.prewarm(payload.get("models"))))
            elif op == "models":
                await self._send(writer, make_result(req_id, self._registry.stats()))
            elif op == "cancel":
                job_id = payload.get("job_id", "")
                task = self._tasks.get(job_id)
                if task is not None and not task.done():
                    task.cancel()
                    await self._send(writer, make_result(req_id, {"job_id": job_id, "cancelled": True}))
                else:
                    await self._send(writer, make_result(req_id, {"job_id": job_id, "cancelled": False}))
            elif op == "subscribe":
                await self._send(writer, {"type": "ready", "id": req_id})
                await self._stream_subscription(writer, payload.get("job_id", ""))
            elif op == "shutdown":
                await self._send(writer, make_result(req_id, {"ok": True}))
                asyncio.get_running_loop().create_task(self.stop())
            else:
                await self._send(writer, make_error(req_id, "E_UNKNOWN_OP", f"unknown op: {op}"))
        except Exception as e:
            logger.warning("dispatch error for op=%s: %s", op, e)
            try:
                await self._send(writer, make_error(req_id, "E_INTERNAL", str(e)))
            except Exception:
                pass

    async def _send(self, writer: asyncio.StreamWriter, obj: Dict[str, Any]):
        writer.write(encode_line(obj))
        await writer.drain()

    async def _stream_subscription(self, writer: asyncio.StreamWriter, job_id: str):
        """订阅：先回放已缓冲事件，再流式推送，作业终结时发送 result"""
        job = self._jobs.get(job_id)
        if job is None:
            await self._send(writer, make_error("", "E_JOB_NOT_FOUND", "job not found"))
            return
        cursor = 0
        while True:
            events = self._events.get(job_id, [])
            for ev in events[cursor:]:
                await self._send(writer, {"type": "event", "job_id": job_id, "event": ev})
            cursor = len(events)
            if job.status in JobStatus.TERMINAL:
                await self._send(writer, make_result("", self._job_view(job)))
                return
            await asyncio.sleep(0.2)

    def _job_view(self, job: Job) -> Dict[str, Any]:
        return {
            "job_id": job.id,
            "op": job.op,
            "status": job.status,
            "result": job.result,
            "error": job.error,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }

    # ── 作业调度 ──────────────────────────────────────────────

    def _submit(self, op: str, payload: Dict[str, Any]) -> str:
        job = Job(id=uuid.uuid4().hex[:16], op=op, payload=payload)
        self._jobs[job.id] = job
        self._store.add(job)
        self._tasks[job.id] = asyncio.get_running_loop().create_task(
            self._execute_job(job),
        )
        return job.id

    async def _execute_job(self, job: Job):
        vram_mb = float(job.payload.get("vram_mb", 0) or 0)
        async with self._sem:
            await self._gate.acquire(vram_mb)
            try:
                job.status = JobStatus.RUNNING
                job.updated_at = time.time()
                self._store.update(job)
                self._broadcast({"type": "job_status", "job_id": job.id, "status": job.status})

                def on_progress(ev):
                    data = {
                        "stage": getattr(ev, "stage", ""),
                        "phase": getattr(ev, "phase", ""),
                        "message": getattr(ev, "message", ""),
                        "percentage": getattr(ev, "percentage", 0.0),
                        "extra": dict(getattr(ev, "extra", {}) or {}),
                    }
                    self._events.setdefault(job.id, []).append(data)
                    self._broadcast({"type": "event", "job_id": job.id, "event": data})

                try:
                    job.result = await self.job_runner(job.op, job.payload, on_progress)
                    job.status = JobStatus.SUCCEEDED
                    job.error = None
                except asyncio.CancelledError:
                    job.status = JobStatus.CANCELLED
                    job.error = "cancelled"
                    raise
                except Exception as e:
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    logger.warning("job %s failed: %s", job.id, e)
                finally:
                    job.updated_at = time.time()
                    self._store.update(job)
                    self._broadcast({"type": "job_status", "job_id": job.id, "status": job.status})
            finally:
                await self._gate.release(vram_mb)

    def _broadcast(self, obj: Dict[str, Any]):
        dead = []
        for writer in list(self._writers):
            try:
                writer.write(encode_line(obj))
            except Exception:
                dead.append(writer)
        for w in dead:
            self._writers.discard(w)
