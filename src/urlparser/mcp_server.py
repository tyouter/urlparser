"""
MCP (Model Context Protocol) stdio 服务器（v4 M2）

工具面（extract_structured 随 M5 上线）：
  parse_url / parse_batch / transcribe / comprehend_video /
  get_job / cancel_job / cache_inspect / cache_invalidate / doctor

协议：JSON-RPC 2.0，stdio 换行分隔 JSON（MCP 规范 2024-11-05）。
执行：优先经 urlparserd（算力复用，D10 共享 daemon），daemon 不可用自动降级进程内。
入口：python -m urlparser.mcp（供 Claude Code / Hermes 等 MCP 客户端直接挂载）
"""

import asyncio
import json
import sys
from typing import Any, Callable, Dict, List, Optional

SERVER_NAME = "urlparser"
SERVER_VERSION = "4.0.0"
PROTOCOL_VERSION = "2024-11-05"

# ── 工具定义（MCP tools/list 格式） ──────────────────────────

def _tool(name: str, description: str, properties: Dict[str, Any],
          required: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required or [],
        },
    }


TOOLS: List[Dict[str, Any]] = [
    _tool(
        "parse_url",
        "解析单个 URL 为结构化内容（Schema v1 JSON）。mode=metadata 为快路径（秒级、零转录）；"
        "strategy=http 为毫秒级 HTTP 快路径；budget_ms 超时返回 E_BUDGET_EXCEEDED。"
        "默认不含正文（防大 JSON）；需要正文时 include_content=true（截断至 max_content_chars）。",
        {
            "url": {"type": "string", "description": "目标 URL（http/https）"},
            "mode": {"type": "string", "enum": ["metadata", "content", "full"], "default": "full"},
            "strategy": {"type": "string", "enum": ["http", "cffi", "playwright", "bb", "cookie", "user_chrome", "browser_use"],
                         "description": "强制获取策略；省略则自动降级链"},
            "budget_ms": {"type": "integer", "description": "总时间预算（毫秒），0=不限"},
            "no_cache": {"type": "boolean", "default": False},
            "include_content": {"type": "boolean", "default": False,
                                "description": "需要正文时置 true：结果附加 content 字段（截断至 max_content_chars）"},
            "max_content_chars": {"type": "integer", "default": 20000,
                                  "description": "include_content 时的正文截断上限"},
        },
        ["url"],
    ),
    _tool(
        "parse_batch",
        "批量解析 URL 列表，返回逐条 Schema v1 结果（含错误码）。"
        "include_content=true 时每条附带正文（截断至 max_content_chars）。",
        {
            "urls": {"type": "array", "items": {"type": "string"}},
            "concurrent": {"type": "integer", "default": 3},
            "include_content": {"type": "boolean", "default": False},
            "max_content_chars": {"type": "integer", "default": 20000},
        },
        ["urls"],
    ),
    _tool(
        "transcribe",
        "音视频转录（URL 或本地文件）。FunASR 中文优先，Whisper 多语言备选；长任务经 daemon 异步执行。",
        {
            "url": {"type": "string", "description": "视频/音频 URL（与 file_path 二选一）"},
            "file_path": {"type": "string", "description": "本地音视频文件路径（与 url 二选一）"},
            "engine": {"type": "string", "enum": ["auto", "funasr", "whisper"], "default": "auto"},
            "language": {"type": "string", "default": "zh"},
        },
        [],
    ),
    _tool(
        "comprehend_video",
        "视频理解：场景关键帧 + 本地 VLM 逐帧描述 + 音画时间轴合并（需本地模型与 ffmpeg）。",
        {
            "url": {"type": "string"},
            "mode": {"type": "string", "enum": ["audio_only", "video_only", "audio_video"], "default": "audio_video"},
            "max_frames": {"type": "integer", "default": 50},
        },
        ["url"],
    ),
    _tool(
        "get_job",
        "查询 urlparserd 作业状态与结果（job_id 来自异步提交）。",
        {"job_id": {"type": "string"}},
        ["job_id"],
    ),
    _tool(
        "cancel_job",
        "取消 urlparserd 作业（5s 内释放 GPU）。",
        {"job_id": {"type": "string"}},
        ["job_id"],
    ),
    _tool(
        "cache_inspect",
        "查看本地解析缓存命中情况（hit / age_s）。",
        {"url": {"type": "string"}},
        ["url"],
    ),
    _tool(
        "cache_invalidate",
        "失效指定 URL 的本地缓存。",
        {"url": {"type": "string"}},
        ["url"],
    ),
    _tool(
        "doctor",
        "环境自检：python/依赖/ffmpeg/浏览器/GPU/daemon 健康报告。",
        {},
        [],
    ),
    _tool(
        "extract_structured",
        "结构化抽取（填表）：按 JSON Schema 从页面抽取字段。默认走 DeepSeek API（决策 D9，"
        "需 DEEPSEEK_API_KEY；仅本工具启用时页面文本发送至 DeepSeek）。",
        {
            "url": {"type": "string", "description": "单页 URL（与 urls 二选一）"},
            "urls": {"type": "array", "items": {"type": "string"}},
            "schema": {"type": "object", "description": "目标 JSON Schema（须含 properties）"},
            "combine": {"type": "string", "enum": ["merge", "each"], "default": "merge"},
            "backend": {"type": "string", "enum": ["deepseek", "local"], "default": "deepseek"},
        },
        ["schema"],
    ),
]


class McpServer:
    """MCP stdio 服务器（每行一个 JSON-RPC 消息）"""

    def __init__(self):
        self._tools = {t["name"]: t for t in TOOLS}

    # ── 协议层 ───────────────────────────────────────────────

    @staticmethod
    def _resp(req_id, result: Dict[str, Any]) -> str:
        return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result},
                          ensure_ascii=False)

    @staticmethod
    def _error(req_id, code: int, message: str) -> str:
        return json.dumps({"jsonrpc": "2.0", "id": req_id,
                           "error": {"code": code, "message": message}},
                          ensure_ascii=False)

    async def handle_line(self, line: str) -> Optional[str]:
        try:
            msg = json.loads(line)
        except Exception:
            return self._error(None, -32700, "Parse error")
        if not isinstance(msg, dict):
            return self._error(None, -32600, "Invalid Request")
        return await self.handle_message(msg)

    async def handle_message(self, msg: Dict[str, Any]) -> Optional[str]:
        method = msg.get("method", "")
        req_id = msg.get("id")
        is_notification = "id" not in msg

        if method == "initialize":
            return self._resp(req_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            })
        if is_notification:
            return None  # notifications/initialized 等无需响应
        if method == "ping":
            return self._resp(req_id, {})
        if method == "tools/list":
            return self._resp(req_id, {"tools": TOOLS})
        if method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name", "")
            arguments = params.get("arguments") or {}
            return self._resp(req_id, await self._call_tool(name, arguments))
        return self._error(req_id, -32601, f"Method not found: {method}")

    # ── 工具分发 ─────────────────────────────────────────────

    async def _call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self._tools:
            return {"content": [{"type": "text", "text": f"未知工具: {name}"}],
                    "isError": True}
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return {"content": [{"type": "text", "text": f"工具未实现: {name}"}],
                    "isError": True}
        try:
            result = await handler(arguments)
            text = json.dumps(result, ensure_ascii=False, indent=2)
            return {"content": [{"type": "text", "text": text}],
                    "structuredContent": result, "isError": False}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"{e}"}], "isError": True}

    # ── 工具实现（daemon 优先，进程内降级） ───────────────────

    async def _via_daemon(self, op: str, payload: Dict[str, Any],
                          local_fn: Callable, wait_sec: float = 8.0) -> Dict[str, Any]:
        from .daemon.client import DaemonClient

        try:
            if not await DaemonClient.ensure_started(wait_sec=wait_sec):
                raise RuntimeError("daemon 无法启动")
            client = DaemonClient()
            job_id = await client.submit(op, payload)
            data = await client.wait(job_id, timeout=None)
            if data.get("status") != "succeeded":
                raise RuntimeError(data.get("error") or data.get("status") or "job failed")
            return data.get("result") or {}
        except Exception:
            return await local_fn()

    async def _tool_parse_url(self, args: Dict[str, Any]) -> Dict[str, Any]:
        include_content = bool(args.get("include_content", False))
        max_chars = int(args.get("max_content_chars", 20000))

        async def _local():
            from .core import UrlParser
            from .config import ParseConfig

            async with UrlParser(ParseConfig()) as parser:
                result = await parser.parse(
                    args.get("url", ""),
                    mode=args.get("mode", "full"),
                    strategy=args.get("strategy"),
                    budget_ms=int(args.get("budget_ms", 0) or 0),
                    force_refresh=bool(args.get("no_cache", False)),
                )
                d = result.to_dict()
                if include_content:
                    d["content"] = (result.content or "")[:max_chars]
                return {"results": [d]}

        data = await self._via_daemon("parse", {
            "url": args.get("url", ""),
            "mode": args.get("mode", "full"),
            "strategy": args.get("strategy"),
            "budget_ms": int(args.get("budget_ms", 0) or 0),
            "no_cache": bool(args.get("no_cache", False)),
            "include_content": include_content,
            "max_content_chars": max_chars,
        }, _local)
        results = data.get("results") or []
        return results[0] if results else {"error": "empty result"}

    async def _tool_parse_batch(self, args: Dict[str, Any]) -> Dict[str, Any]:
        include_content = bool(args.get("include_content", False))
        max_chars = int(args.get("max_content_chars", 20000))

        async def _local():
            from .core import UrlParser
            from .config import ParseConfig

            async with UrlParser(ParseConfig()) as parser:
                results = await parser.parse_batch(
                    args.get("urls", []),
                    concurrent=int(args.get("concurrent", 3)),
                )
                out = []
                for r in results:
                    d = r.to_dict()
                    if include_content:
                        d["content"] = (r.content or "")[:max_chars]
                    out.append(d)
                return {"results": out}

        data = await self._via_daemon("parse", {
            "urls": args.get("urls", []),
            "concurrent": int(args.get("concurrent", 3)),
            "include_content": include_content,
            "max_content_chars": max_chars,
        }, _local)
        return {"results": data.get("results") or []}

    async def _tool_transcribe(self, args: Dict[str, Any]) -> Dict[str, Any]:
        async def _local():
            from .daemon.server import _run_transcribe_job
            return await _run_transcribe_job({
                "url": args.get("url"),
                "file_path": args.get("file_path"),
                "engine": args.get("engine", "auto"),
                "language": args.get("language", "zh"),
            })

        if not args.get("url") and not args.get("file_path"):
            raise ValueError("transcribe 需要 url 或 file_path")
        return await self._via_daemon("transcribe", {
            "url": args.get("url"),
            "file_path": args.get("file_path"),
            "engine": args.get("engine", "auto"),
            "language": args.get("language", "zh"),
        }, _local)

    async def _tool_comprehend_video(self, args: Dict[str, Any]) -> Dict[str, Any]:
        async def _local():
            from .core import UrlParser
            from .config import ParseConfig, ComprehensionConfig

            cfg = ParseConfig()
            cfg.comprehension = ComprehensionConfig(
                enabled=True,
                mode=args.get("mode", "audio_video"),
                max_frames=int(args.get("max_frames", 50)),
            )
            async with UrlParser(cfg) as parser:
                result = await parser.parse(args.get("url", ""))
                return {"results": [result.to_dict()]}

        data = await self._via_daemon("parse", {
            "url": args.get("url", ""),
            "comprehension": True,
            "comp_mode": args.get("mode", "audio_video"),
            "max_frames": int(args.get("max_frames", 50)),
        }, _local)
        results = data.get("results") or []
        return results[0] if results else {"error": "empty result"}

    async def _tool_get_job(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from .daemon.client import DaemonClient
        return await DaemonClient().result(args.get("job_id", ""))

    async def _tool_cancel_job(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from .daemon.client import DaemonClient
        ok = await DaemonClient().cancel(args.get("job_id", ""))
        return {"job_id": args.get("job_id", ""), "cancelled": ok}

    async def _tool_cache_inspect(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from .storage import ResultCache
        cache = ResultCache(cache_dir="./parser_cache")
        hit = await cache.get(args.get("url", ""))
        return {"url": args.get("url", ""), "hit": hit is not None,
                "result": hit if hit is not None else None}

    async def _tool_cache_invalidate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from .storage import ResultCache
        cache = ResultCache(cache_dir="./parser_cache")
        await cache.delete(args.get("url", ""))
        return {"url": args.get("url", ""), "invalidated": True}

    async def _tool_doctor(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from .doctor import run_checks
        return run_checks().to_dict()

    async def _tool_extract_structured(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from .extract import extract_structured

        backend = args.get("backend", "deepseek")
        if backend != "deepseek":
            raise ValueError("backend=local 离线档未接入（M5 仅 DeepSeek API，决策 D9）")
        urls = list(args.get("urls") or [])
        if args.get("url"):
            urls.insert(0, args["url"])
        schema = args.get("schema")
        return await extract_structured(
            urls, schema, combine=args.get("combine", "merge"),
        )

    # ── stdio 循环 ───────────────────────────────────────────

    async def run_stdio(self) -> None:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _reader():
            for line in sys.stdin:
                line = line.strip()
                if line:
                    loop.call_soon_threadsafe(queue.put_nowait, line)
            loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, _reader)
        while True:
            line = await queue.get()
            if line is None:
                break
            resp = await self.handle_line(line)
            if resp is not None:
                print(resp, flush=True)


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="urlparser.mcp", description="urlparser MCP stdio 服务器")
    p.add_argument("--version", action="store_true")
    args = p.parse_args(argv)
    if args.version:
        print(f"urlparser MCP server {SERVER_VERSION}")
        return 0
    # MCP 协议要求 UTF-8；Windows 控制台默认 GBK，强制重配
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        asyncio.run(McpServer().run_stdio())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
