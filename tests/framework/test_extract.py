"""
结构化抽取测试（v4 M5 任务 F10，决策 D9：DeepSeek API）

parse_llm_json / extract_structured / MCP 工具 / CLI 入口。
网络调用（fetch_page_text / call_deepseek）全部 monkeypatch。
"""

import json

import pytest

from urlparser.extract import (
    parse_llm_json, extract_structured,
)

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "price": {"type": "string"},
    },
}


def test_parse_llm_json_plain():
    assert parse_llm_json('{"title": "x"}') == {"title": "x"}


def test_parse_llm_json_fenced():
    content = '```json\n{"title": "x", "price": null}\n```'
    assert parse_llm_json(content) == {"title": "x", "price": None}


def test_parse_llm_json_invalid():
    with pytest.raises(ValueError):
        parse_llm_json("no json here")


@pytest.mark.asyncio
async def test_extract_structured_merge(monkeypatch):
    async def fake_fetch(url, max_chars=12000):
        return f"page text of {url}"

    async def fake_llm(messages, api_key, base_url="", model="", temperature=0.1, timeout=120.0):
        user = messages[-1]["content"]
        assert "page text of" in user
        assert "schema" in user
        return '{"title": "T", "price": "99"}'

    monkeypatch.setattr("urlparser.extract.fetch_page_text", fake_fetch)
    monkeypatch.setattr("urlparser.extract.call_deepseek", fake_llm)

    result = await extract_structured(
        ["https://a.example", "https://b.example"], SCHEMA, api_key="sk-test",
    )
    assert result["schema_version"] == "1.0"
    assert result["data"] == {"title": "T", "price": "99"}
    assert result["model"] == "deepseek-chat"


@pytest.mark.asyncio
async def test_extract_structured_each(monkeypatch):
    async def fake_fetch(url, max_chars=12000):
        return "text"

    async def fake_llm(messages, api_key, base_url="", model="", temperature=0.1, timeout=120.0):
        return '{"title": "each"}'

    monkeypatch.setattr("urlparser.extract.fetch_page_text", fake_fetch)
    monkeypatch.setattr("urlparser.extract.call_deepseek", fake_llm)

    result = await extract_structured(
        ["https://a.example", "https://b.example"], SCHEMA,
        api_key="sk-test", combine="each",
    )
    assert len(result["data"]) == 2
    assert result["data"][0]["url"] == "https://a.example"


@pytest.mark.asyncio
async def test_extract_missing_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        await extract_structured(["https://a.example"], SCHEMA, api_key=None)


@pytest.mark.asyncio
async def test_extract_bad_schema():
    with pytest.raises(ValueError, match="properties"):
        await extract_structured(["https://a.example"], {"type": "object"}, api_key="sk")


@pytest.mark.asyncio
async def test_mcp_extract_structured_tool(monkeypatch):
    from urlparser.mcp_server import McpServer

    async def fake_extract(urls, schema, combine="merge"):
        return {"schema_version": "1.0", "data": {"title": "M"}, "model": "deepseek-chat"}

    server = McpServer()
    monkeypatch.setattr("urlparser.extract.extract_structured", fake_extract)

    out = await server.handle_line(json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "extract_structured",
                   "arguments": {"url": "https://a.example", "schema": SCHEMA}},
    }))
    resp = json.loads(out)
    assert resp["result"]["isError"] is False
    assert resp["result"]["structuredContent"]["data"]["title"] == "M"


@pytest.mark.asyncio
async def test_mcp_extract_local_backend_rejected(monkeypatch):
    from urlparser.mcp_server import McpServer

    server = McpServer()
    out = await server.handle_line(json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "extract_structured",
                   "arguments": {"url": "https://a.example", "schema": SCHEMA,
                                 "backend": "local"}},
    }))
    resp = json.loads(out)
    assert resp["result"]["isError"] is True


def test_cli_extract(monkeypatch, capsys, tmp_path):
    from urlparser import cli

    async def fake_extract(urls, schema, model="deepseek-chat", combine="merge"):
        return {"schema_version": "1.0", "data": {"title": "C"}, "model": model}

    monkeypatch.setattr("urlparser.extract.extract_structured", fake_extract)

    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps(SCHEMA), encoding="utf-8")

    code = cli.main(["extract", "--url", "https://a.example",
                     "--schema", str(schema_file)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["data"] == {"title": "C"}


def test_cli_extract_failure_exit_4(monkeypatch, tmp_path):
    from urlparser import cli

    async def failing(urls, schema, model="deepseek-chat", combine="merge"):
        raise RuntimeError("boom")

    monkeypatch.setattr("urlparser.extract.extract_structured", failing)
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps(SCHEMA), encoding="utf-8")

    code = cli.main(["extract", "--url", "https://a.example",
                     "--schema", str(schema_file)])
    assert code == 4
