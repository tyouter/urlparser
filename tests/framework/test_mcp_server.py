"""
MCP 服务器测试（v4 M2）

进程内调用 McpServer.handle_line 验证 JSON-RPC 协议与工具面，
不启动 stdio 管道、不发真实网络请求（工具实现用 monkeypatch 替换）。
"""

import json

import pytest

from urlparser.mcp_server import McpServer, TOOLS


@pytest.fixture
def server():
    return McpServer()


async def _call(server, method, params=None, msg_id=1):
    out = await server.handle_line(json.dumps({
        "jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {},
    }))
    return json.loads(out)


@pytest.mark.asyncio
async def test_initialize(server):
    resp = await _call(server, "initialize",
                       {"protocolVersion": "2024-11-05", "capabilities": {}})
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert resp["result"]["serverInfo"]["name"] == "urlparser"
    assert "tools" in resp["result"]["capabilities"]


@pytest.mark.asyncio
async def test_tools_list_covers_m2_surface(server):
    resp = await _call(server, "tools/list")
    names = {t["name"] for t in resp["result"]["tools"]}
    expected = {
        "parse_url", "parse_batch", "transcribe", "comprehend_video",
        "get_job", "cancel_job", "cache_inspect", "cache_invalidate", "doctor",
        "extract_structured",  # M5 已上线
    }
    assert expected <= names


@pytest.mark.asyncio
async def test_notification_no_response(server):
    out = await server.handle_line(
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
    )
    assert out is None


@pytest.mark.asyncio
async def test_ping(server):
    resp = await _call(server, "ping")
    assert resp["result"] == {}


@pytest.mark.asyncio
async def test_unknown_method(server):
    resp = await _call(server, "nope")
    assert resp["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_tool_call_parse_url(server, monkeypatch):
    async def fake_parse_url(args):
        return {"url": args["url"], "fetch_success": True, "schema_version": "1.0",
                "final_strategy": "http"}
    monkeypatch.setattr(server, "_tool_parse_url", fake_parse_url)

    resp = await _call(server, "tools/call",
                       {"name": "parse_url",
                        "arguments": {"url": "https://example.com", "mode": "metadata"}})
    assert resp["result"]["isError"] is False
    assert resp["result"]["structuredContent"]["final_strategy"] == "http"
    assert resp["result"]["content"][0]["type"] == "text"


@pytest.mark.asyncio
async def test_tool_call_unknown_tool(server):
    resp = await _call(server, "tools/call", {"name": "nope", "arguments": {}})
    assert resp["result"]["isError"] is True


@pytest.mark.asyncio
async def test_tool_call_error_is_error(server, monkeypatch):
    async def failing(args):
        raise ValueError("boom")
    monkeypatch.setattr(server, "_tool_transcribe", failing)

    resp = await _call(server, "tools/call", {"name": "transcribe",
                                              "arguments": {"url": "https://x"}})
    assert resp["result"]["isError"] is True
    assert "boom" in resp["result"]["content"][0]["text"]


@pytest.mark.asyncio
async def test_transcribe_missing_input_validation(server):
    resp = await _call(server, "tools/call", {"name": "transcribe", "arguments": {}})
    assert resp["result"]["isError"] is True


class _FakeReport:
    def to_dict(self):
        return {"healthy": True, "checks": []}


@pytest.mark.asyncio
async def test_doctor_tool(server, monkeypatch):
    monkeypatch.setattr("urlparser.doctor.run_checks", lambda: _FakeReport())
    resp = await _call(server, "tools/call", {"name": "doctor", "arguments": {}})
    assert resp["result"]["isError"] is False
    assert resp["result"]["structuredContent"]["healthy"] is True


@pytest.mark.asyncio
async def test_parse_error_line(server):
    out = await server.handle_line("not json")
    d = json.loads(out)
    assert d["error"]["code"] == -32700


def test_tool_schemas_valid():
    for t in TOOLS:
        assert t["name"] and t["description"]
        props = t["inputSchema"]["properties"]
        for req in t["inputSchema"]["required"]:
            assert req in props


def test_parse_url_schema_has_content_opt_in():
    """Hermes 反馈缺口：parse_url 支持 include_content/max_content_chars"""
    tool = next(t for t in TOOLS if t["name"] == "parse_url")
    props = tool["inputSchema"]["properties"]
    assert props["include_content"]["default"] is False
    assert props["max_content_chars"]["default"] == 20000

    batch = next(t for t in TOOLS if t["name"] == "parse_batch")
    assert "include_content" in batch["inputSchema"]["properties"]
