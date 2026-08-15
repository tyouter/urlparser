"""
模型注册表测试（v4 M3 任务 F8/F9）

覆盖：引用计数生命周期、keepalive 三策略、显存预算与回收、预热、统计。
"""

import time

import pytest

from urlparser.model_registry import ModelRegistry


def _loader(counter):
    def load():
        counter[0] += 1
        return object()
    return load


def test_acquire_release_lifecycle():
    reg = ModelRegistry()
    counter = [0]
    reg.register("m", _loader(counter), vram_mb=100, keepalive="never")

    m1 = reg.acquire("m")
    m2 = reg.acquire("m")
    assert m1 is m2
    assert counter[0] == 1  # 只加载一次
    assert reg.stats()["vram_used_mb"] == 100

    reg.release("m")
    assert reg.stats()["models"][0]["loaded"] is True  # refcount 仍 >0
    reg.release("m")
    assert reg.stats()["models"][0]["loaded"] is False  # never 立即卸载
    assert reg.stats()["vram_used_mb"] == 0


def test_always_keepalive_keeps_after_release():
    reg = ModelRegistry()
    reg.register("m", _loader([0]), vram_mb=100, keepalive="always")
    reg.acquire("m")
    reg.release("m")
    assert reg.stats()["models"][0]["loaded"] is True
    assert reg.unload("m") is False  # always 需要 force
    assert reg.unload("m", force=True) is True


def test_idle_keepalive_times_out():
    reg = ModelRegistry()
    reg.register("m", _loader([0]), vram_mb=100, keepalive="idle", idle_sec=0.0)
    reg.acquire("m")
    reg.release("m")
    assert reg.stats()["models"][0]["loaded"] is True
    unloaded = reg.unload_idle()
    assert unloaded == ["m"]
    assert reg.stats()["models"][0]["loaded"] is False


def test_vram_budget_exceeded_raises():
    reg = ModelRegistry(vram_budget_mb=100)
    reg.register("a", _loader([0]), vram_mb=80, keepalive="always")
    reg.register("b", _loader([0]), vram_mb=50, keepalive="never")
    reg.acquire("a")
    with pytest.raises(RuntimeError, match="budget"):
        reg.acquire("b")


def test_budget_evicts_unreferenced():
    reg = ModelRegistry(vram_budget_mb=100)
    reg.register("a", _loader([0]), vram_mb=80, keepalive="never")
    reg.register("b", _loader([0]), vram_mb=50, keepalive="never")
    reg.acquire("a")
    reg.release("a")  # never → 已卸载
    reg.acquire("b")  # 预算内可加载
    assert reg.stats()["vram_used_mb"] == 50


def test_prewarm_and_stats():
    reg = ModelRegistry()
    counter = [0]
    reg.register("m", _loader(counter), vram_mb=100, keepalive="always")
    report = reg.prewarm(["m"])
    assert report["loaded"] == ["m"]
    assert report["failed"] == []
    assert reg.stats()["models"][0]["refcount"] == 1
    assert counter[0] == 1


def test_unregistered_model_raises():
    reg = ModelRegistry()
    with pytest.raises(KeyError):
        reg.acquire("nope")


def test_stats_json_serializable():
    import json
    reg = ModelRegistry(vram_budget_mb=500)
    reg.register("m", _loader([0]), vram_mb=100, keepalive="idle")
    json.dumps(reg.stats(), ensure_ascii=False)
