"""
CLI v2 契约测试（v4 M1 任务 F）

进程内调用 cli.main()，验证退出码契约、JSON/--fields 输出、stdin 批量。
不发起真实网络请求（monkeypatch core 入口），不捕获子进程管道（沙箱限制）。
"""

import io
import json

import pytest

from urlparser import cli
from urlparser.models import ParseResult, PlatformType, ContentType


class _FakeParser:
    """替代 UrlParser 的假对象（供 cmd_parse/cmd_parse_batch 注入）"""

    def __init__(self, config=None):
        self.config = config

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def parse(self, url, **kwargs):
        r = ParseResult(
            url=url,
            platform="generic",
            platform_type=PlatformType.GENERIC,
            content_type=ContentType.ARTICLE,
            title="标题",
            content="正文内容 " * 50,
            author="作者",
            fetch_success=True,
            final_strategy="http",
            strategy_trace=["http"],
        )
        return r

    async def parse_batch(self, urls, concurrent=3, **kwargs):
        return [await self.parse(u) for u in urls]

    async def close(self):
        pass


def _run_main(argv, monkeypatch):
    monkeypatch.setattr("urlparser.core.UrlParser", _FakeParser)
    return cli.main(argv)


def test_exit_0_and_json_output(capsys, monkeypatch):
    code = _run_main(
        ["parse", "https://example.com", "--standalone", "--json"], monkeypatch,
    )
    out = capsys.readouterr().out
    d = json.loads(out)
    assert code == 0
    assert d["schema_version"] == "1.0"
    assert d["fetch_success"] is True
    assert d["title"] == "标题"
    assert d["timing"]["total_ms"] >= 0
    assert "error_detail" in d


def test_fields_subset(capsys, monkeypatch):
    code = _run_main(
        ["parse", "https://example.com", "--standalone", "--json",
         "--fields", "title,content_type"], monkeypatch,
    )
    d = json.loads(capsys.readouterr().out)
    assert code == 0
    assert set(d) == {"schema_version", "url", "title", "content_type"}


def test_budget_exit_code_5(monkeypatch):
    import asyncio
    from urlparser.core import UrlParser as RealUrlParser

    async def slow_do_parse(self, url, config, opts=None):
        await asyncio.sleep(0.05)
        return ParseResult(url=url, fetch_success=False)

    monkeypatch.setattr(RealUrlParser, "_do_parse", slow_do_parse)
    code = cli.main(["parse", "https://example.com", "--standalone", "--budget", "1"])
    assert code == 5


def test_unknown_strategy_argparse_exit_2():
    # main() 把 argparse 的 SystemExit(2) 归一为返回码 2
    code = cli.main(["parse", "https://example.com", "--strategy", "nope"])
    assert code == 2


def test_parse_batch_stdin_exit_0(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr("urlparser.core.UrlParser", _FakeParser)
    monkeypatch.setattr("sys.stdin", io.StringIO("https://a.example\nhttps://b.example\n"))

    code = cli.main([
        "parse-batch", "-", "--output-dir", str(tmp_path / "out"),
        "--manifest", str(tmp_path / "manifest.json"),
    ])
    err = capsys.readouterr().err
    assert code == 0
    assert "找到 2 个 URL" in err
    assert "2/2 成功" in err
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 2
    assert all(m["success"] for m in manifest)


def test_no_command_exit_0(capsys):
    code = cli.main([])
    assert code == 0
