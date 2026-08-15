"""
urlparserd 守护进程测试（v4 M1 任务 E）

本机回环 TCP，fake job runner，不发真实网络请求。
覆盖：JobStore 持久化/恢复、协议往返、作业生命周期、取消、进度事件流。
"""

import asyncio

import pytest

from urlparser.daemon.client import DaemonClient, DaemonError
from urlparser.daemon.jobstore import Job, JobStatus, JobStore
from urlparser.daemon.server import DaemonServer
from urlparser.models import ProgressEvent


@pytest.fixture
def store(tmp_path):
    s = JobStore(str(tmp_path / "jobs.db"))
    yield s
    s.close()


def test_jobstore_roundtrip(store):
    job = Job(id="j1", op="parse", payload={"url": "https://x"})
    store.add(job)
    got = store.get("j1")
    assert got.op == "parse"
    assert got.payload["url"] == "https://x"

    got.status = JobStatus.SUCCEEDED
    got.result = {"ok": True}
    store.update(got)
    assert store.get("j1").status == JobStatus.SUCCEEDED
    assert store.get("j1").result == {"ok": True}


def test_jobstore_recover(store):
    store.add(Job(id="q", op="parse", status=JobStatus.QUEUED))
    store.add(Job(id="r", op="parse", status=JobStatus.RUNNING))
    store.recover()
    assert store.get("q").status == JobStatus.QUEUED
    assert store.get("r").status == JobStatus.FAILED
    assert "restarted" in (store.get("r").error or "")


async def _start_test_server(job_runner=None):
    srv = DaemonServer(host="127.0.0.1", port=0, job_runner=job_runner,
                       db_path=None)
    await srv.start()
    return srv


@pytest.mark.asyncio
async def test_health_and_echo():
    srv = await _start_test_server()
    client = DaemonClient(port=srv.port)
    try:
        h = await client.health()
        assert h["status"] == "ok"
        r = await client._request("echo", {"x": 1})
        assert r["echo"]["x"] == 1
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_job_lifecycle_success():
    async def runner(op, payload, on_progress=None):
        if on_progress is not None:
            on_progress(ProgressEvent(stage="fetch", phase="start",
                                      message="fake", percentage=5))
        await asyncio.sleep(0.05)
        return {"results": [{"url": payload["url"], "title": "ok"}]}

    srv = await _start_test_server(runner)
    client = DaemonClient(port=srv.port)
    try:
        job_id = await client.submit("parse", {"url": "https://example.com"})
        assert job_id
        data = await client.wait(job_id, timeout=5)
        assert data["status"] == "succeeded"
        assert data["result"]["results"][0]["title"] == "ok"
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_job_cancel():
    async def slow_runner(op, payload, on_progress=None):
        await asyncio.sleep(30)
        return {"results": []}

    srv = await _start_test_server(slow_runner)
    client = DaemonClient(port=srv.port)
    try:
        job_id = await client.submit("parse", {"url": "https://example.com"})
        await asyncio.sleep(0.2)
        assert await client.cancel(job_id) is True
        data = await client.wait(job_id, timeout=5)
        assert data["status"] == "cancelled"
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_progress_events_stream():
    async def runner(op, payload, on_progress=None):
        on_progress(ProgressEvent(stage="fetch", phase="start", message="s", percentage=5))
        on_progress(ProgressEvent(stage="parse", phase="done", message="d", percentage=45))
        return {"results": []}

    srv = await _start_test_server(runner)
    client = DaemonClient(port=srv.port)
    try:
        job_id = await client.submit("parse", {"url": "https://example.com"})
        events = []
        final = await client.subscribe(job_id, on_event=events.append, timeout=5)
        assert final["status"] == "succeeded"
        assert any(e["stage"] == "fetch" for e in events)
        assert any(e["stage"] == "parse" for e in events)
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_unknown_job_raises():
    srv = await _start_test_server()
    client = DaemonClient(port=srv.port)
    try:
        with pytest.raises(DaemonError):
            await client.result("nonexistent")
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_failed_job_surfaces_error():
    async def failing_runner(op, payload, on_progress=None):
        raise RuntimeError("boom")

    srv = await _start_test_server(failing_runner)
    client = DaemonClient(port=srv.port)
    try:
        job_id = await client.submit("parse", {"url": "https://example.com"})
        data = await client.wait(job_id, timeout=5)
        assert data["status"] == "failed"
        assert "boom" in (data["error"] or "")
    finally:
        await srv.stop()
