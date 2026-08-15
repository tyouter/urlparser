"""
快路径 / 预算 / 策略控制测试（v4 任务 C）

覆盖 mode=metadata 快路径、--strategy 策略控制、budget_ms 预算超时。
全部用 fake 对象，不发起真实网络请求。
"""

import asyncio

import pytest

from urlparser import UrlParser, ParseConfig, ParseOptions
from urlparser.config import apply_fields
from urlparser.fetcher.base import FetchResult, FetchStrategy
from urlparser.schema import ErrorCode


class _FakeFetcher:
    strategy = FetchStrategy.HTTP

    async def fetch(self, url, **kwargs):
        return FetchResult(
            url=url,
            text="content " * 100,
            html="<p>content</p>",
            title="T",
            status_code=200,
            strategy=self.strategy,
            success=True,
        )

    async def close(self):
        pass


def test_parse_options_defaults():
    o = ParseOptions()
    assert o.mode == "full"
    assert o.strategy is None
    assert o.budget_ms == 0


def test_apply_fields():
    data = {"schema_version": "1.0", "url": "u", "title": "t", "content": "c"}
    out = apply_fields(data, ["title"])
    assert set(out) == {"schema_version", "url", "title"}
    assert apply_fields(data, None) == data


@pytest.mark.asyncio
async def test_metadata_mode_video(monkeypatch):
    events = []
    cfg = ParseConfig(on_progress=lambda e: events.append(e))
    cfg.retry.enabled = False

    fake_info = {
        "fetch_success": True, "title": "T", "description": "D", "author": "A",
        "publish_date_formatted": "2026-01-01", "duration": "1:23",
        "views": "1.2万", "likes": "", "coins": "", "favorites": "", "tags": "x",
    }
    monkeypatch.setattr(
        "urlparser.transcriber.video_info.extract_video_info",
        lambda url: fake_info,
    )

    result = await UrlParser(cfg).parse(
        "https://www.bilibili.com/video/BV1xx411c7mD", mode="metadata",
    )

    assert result.fetch_success
    assert result.final_strategy == "metadata"
    assert result.strategy_trace == ["metadata"]
    assert not result.has_transcription  # 快路径绝不转录
    assert result.video_metadata.duration == "1:23"
    assert all(e.stage == "fetch" for e in events)


@pytest.mark.asyncio
async def test_strategy_control(monkeypatch):
    captured = {}

    def fake_create(fetch_config, strategy=None):
        captured["strategy"] = strategy
        return _FakeFetcher()

    monkeypatch.setattr("urlparser.fetcher.factory.FetcherFactory.create", fake_create)

    cfg = ParseConfig()
    cfg.retry.enabled = False
    result = await UrlParser(cfg).parse("https://example.com/a", strategy="http")

    assert captured["strategy"] == FetchStrategy.HTTP
    assert result.fetch_success


@pytest.mark.asyncio
async def test_unknown_strategy_returns_validation_error(monkeypatch):
    cfg = ParseConfig()
    cfg.retry.enabled = False
    result = await UrlParser(cfg).parse("https://example.com/a", strategy="nope")
    assert not result.fetch_success
    assert result.structured_error is not None
    assert result.structured_error.code == ErrorCode.E_VALIDATION


@pytest.mark.asyncio
async def test_budget_exceeded(monkeypatch):
    async def slow_do_parse(self, url, config, opts=None):
        await asyncio.sleep(0.05)
        return None

    monkeypatch.setattr(UrlParser, "_do_parse", slow_do_parse)

    cfg = ParseConfig()
    cfg.retry.enabled = False
    result = await UrlParser(cfg).parse("https://example.com/a", budget_ms=1)

    assert not result.fetch_success
    assert result.structured_error is not None
    assert result.structured_error.code == ErrorCode.E_BUDGET_EXCEEDED
