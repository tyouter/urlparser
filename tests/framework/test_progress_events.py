"""
四段进度事件测试（v4 任务 B）

验证 parse 全链路发射 fetch/parse/transcribe/comprehension 四段
结构化进度事件（docs §7 契约，修复 C12）。
全部用 fake 对象，不发起真实网络/浏览器请求。
"""

import types

import pytest

from urlparser import UrlParser, ParseConfig
from urlparser.fetcher.base import FetchResult, FetchStrategy
from urlparser.models import TranscriptionResult, ComprehensionResult


def _collector():
    events = []
    return events, lambda e: events.append(e)


class _FakeFetcher:
    """成功返回内容的假 fetcher"""
    strategy = FetchStrategy.DIRECT

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


class _FakeParser:
    """成功返回文章结果的假 parser"""
    platform = "generic"

    async def fetch(self, url):
        return types.SimpleNamespace(
            url=url, platform="generic",
            content_type=types.SimpleNamespace(value="article"),
            title="T", content="x" * 300, raw_text="x" * 300,
            author="", publish_date="", metadata={},
            fetch_success=True, error=None, video_specific={},
        )

    async def close(self):
        pass


class _FakeFactory:
    @staticmethod
    def create(url, config=None, platform=None):
        return _FakeParser()


async def _fake_transcribe(self, url, cfg, platform, on_progress=None):
    return TranscriptionResult(success=True, text="t" * 50, engine="funasr", duration=1.0)


async def _fake_comprehension(self, url, cfg, transcription=None):
    return ComprehensionResult(success=True, mode="audio_video", engine="fake", frame_count=1)


@pytest.mark.asyncio
async def test_fetch_stage_events(monkeypatch):
    events, cb = _collector()
    cfg = ParseConfig(on_progress=cb)
    cfg.retry.enabled = False
    monkeypatch.setattr("urlparser.fetcher.factory.FetcherFactory.auto_select",
                        lambda url, fetch_config: _FakeFetcher())

    result = await UrlParser(cfg).parse("https://example.com/article")

    fetch_events = [e for e in events if e.stage == "fetch"]
    assert result.fetch_success
    assert any(e.phase == "start" for e in fetch_events)
    assert any(e.phase == "done" for e in fetch_events)
    assert all(e.extra.get("strategy") for e in fetch_events)


@pytest.mark.asyncio
async def test_parse_stage_events(monkeypatch):
    events, cb = _collector()
    cfg = ParseConfig(on_progress=cb)
    cfg.retry.enabled = False
    monkeypatch.setattr("urlparser.fetcher.factory.FetcherFactory.auto_select",
                        lambda url, fetch_config: None)
    monkeypatch.setattr("urlparser.core.ParserFactory", _FakeFactory)

    result = await UrlParser(cfg).parse("https://example.com/article")

    parse_events = [e for e in events if e.stage == "parse"]
    assert result.fetch_success
    assert any(e.phase == "start" for e in parse_events)
    assert any(e.phase == "done" and e.extra.get("success") for e in parse_events)


@pytest.mark.asyncio
async def test_transcribe_and_comprehension_events(monkeypatch):
    events, cb = _collector()
    cfg = ParseConfig(on_progress=cb)
    cfg.retry.enabled = False
    cfg.comprehension.enabled = True
    monkeypatch.setattr("urlparser.fetcher.factory.FetcherFactory.auto_select",
                        lambda url, fetch_config: _FakeFetcher())
    monkeypatch.setattr(UrlParser, "_transcribe_audio", _fake_transcribe)
    monkeypatch.setattr(UrlParser, "_run_comprehension", _fake_comprehension)

    result = await UrlParser(cfg).parse("https://www.bilibili.com/video/BV1xx411c7mD")

    stages = {e.stage for e in events}
    assert "fetch" in stages and "transcribe" in stages and "comprehension" in stages
    assert result.has_transcription and result.has_comprehension


def test_progress_event_json_contract():
    """进度事件可序列化为 JSON-lines（看门狗契约）"""
    from urlparser.models import ProgressEvent
    ev = ProgressEvent(stage="fetch", phase="start", message="m", percentage=5.0, extra={"strategy": "http"})
    line = ev.to_json_line()
    assert '"stage": "fetch"' in line
    assert '"phase": "start"' in line
