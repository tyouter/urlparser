"""
模型注册表（v4 M3 任务 F8/F9）

常驻/预热/显存预算：模型按 key 注册（loader/vram/keepalive），
acquire 加载并计数引用，release 按 keepalive 策略卸载；
显存超预算时拒绝新加载（daemon 层负责排队等待）。

keepalive 策略：
- "always"：引用归零也不卸载（核心模型，如 SenseVoice）
- "idle"：引用归零后空闲 idle_sec 秒卸载（空闲回收）
- "never"：引用归零立即卸载（即用即载）
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ModelEntry:
    model_id: str
    loader: Callable[[], Any]
    vram_mb: float = 0.0
    keepalive: str = "idle"
    idle_sec: float = 600.0
    model: Any = None
    refcount: int = 0
    last_used: float = 0.0
    load_ms: float = 0.0

    @property
    def loaded(self) -> bool:
        return self.model is not None


class ModelRegistry:
    """本地模型常驻注册表（修复 C17：模型每请求加载的浪费）"""

    def __init__(self, vram_budget_mb: Optional[float] = None):
        self._entries: Dict[str, ModelEntry] = {}
        self.vram_budget_mb = vram_budget_mb  # None = 不限制

    def register(self, model_id: str, loader: Callable[[], Any],
                 vram_mb: float = 0.0, keepalive: str = "idle",
                 idle_sec: float = 600.0) -> None:
        if keepalive not in ("always", "idle", "never"):
            raise ValueError(f"unknown keepalive: {keepalive}")
        self._entries[model_id] = ModelEntry(
            model_id=model_id, loader=loader, vram_mb=float(vram_mb),
            keepalive=keepalive, idle_sec=idle_sec,
        )

    def is_registered(self, model_id: str) -> bool:
        return model_id in self._entries

    def loaded_vram_mb(self) -> float:
        return sum(e.vram_mb for e in self._entries.values() if e.loaded)

    def acquire(self, model_id: str) -> Any:
        """取用模型：未加载则加载（受显存预算约束），引用计数 +1"""
        entry = self._entries.get(model_id)
        if entry is None:
            raise KeyError(f"model not registered: {model_id}")

        if not entry.loaded:
            projected = self.loaded_vram_mb() + entry.vram_mb
            if self.vram_budget_mb is not None and projected > self.vram_budget_mb:
                # 先回收 never/idle 的未引用模型，仍超则拒绝
                self._evict_for(entry.vram_mb)
                projected = self.loaded_vram_mb() + entry.vram_mb
                if projected > self.vram_budget_mb:
                    raise RuntimeError(
                        f"VRAM budget exceeded: need {entry.vram_mb}MB, "
                        f"used {self.loaded_vram_mb()}MB, budget {self.vram_budget_mb}MB",
                    )
            t0 = time.time()
            entry.model = entry.loader()
            entry.load_ms = round((time.time() - t0) * 1000, 1)

        entry.refcount += 1
        entry.last_used = time.time()
        return entry.model

    def release(self, model_id: str) -> None:
        """释放一次引用；按 keepalive 策略决定是否卸载"""
        entry = self._entries.get(model_id)
        if entry is None:
            return
        entry.refcount = max(0, entry.refcount - 1)
        if entry.refcount == 0:
            if entry.keepalive == "never":
                self.unload(model_id, force=True)
            # idle 策略由 unload_idle() 按超时回收；always 保留

    def unload(self, model_id: str, force: bool = False) -> bool:
        entry = self._entries.get(model_id)
        if entry is None or not entry.loaded:
            return False
        if entry.refcount > 0:
            return False
        if entry.keepalive == "always" and not force:
            return False
        entry.model = None
        return True

    def unload_idle(self, now: Optional[float] = None) -> List[str]:
        """回收 idle 策略下空闲超时的模型，返回卸载的 model_id 列表"""
        now = now if now is not None else time.time()
        unloaded = []
        for entry in self._entries.values():
            if not entry.loaded or entry.refcount > 0:
                continue
            if entry.keepalive == "idle" and (now - entry.last_used) >= entry.idle_sec:
                entry.model = None
                unloaded.append(entry.model_id)
        return unloaded

    def prewarm(self, model_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """预热模型：加载并保持（refcount +1 常驻）"""
        targets = model_ids or list(self._entries.keys())
        loaded, failed = [], []
        for mid in targets:
            try:
                self.acquire(mid)
                loaded.append(mid)
            except Exception as e:
                failed.append({"model_id": mid, "error": str(e)})
        return {"loaded": loaded, "failed": failed, "stats": self.stats()}

    def stats(self) -> Dict[str, Any]:
        return {
            "vram_budget_mb": self.vram_budget_mb,
            "vram_used_mb": self.loaded_vram_mb(),
            "models": [
                {
                    "model_id": e.model_id,
                    "loaded": e.loaded,
                    "refcount": e.refcount,
                    "vram_mb": e.vram_mb,
                    "keepalive": e.keepalive,
                    "load_ms": e.load_ms,
                    "idle_sec": round(max(0.0, time.time() - e.last_used), 1) if e.loaded else None,
                }
                for e in self._entries.values()
            ],
        }

    def _evict_for(self, need_mb: float) -> None:
        """为腾出 need_mb 空间回收未引用的 never/idle 模型"""
        candidates = sorted(
            (e for e in self._entries.values()
             if e.loaded and e.refcount == 0 and e.keepalive in ("never", "idle")),
            key=lambda e: e.last_used,
        )
        for entry in candidates:
            if self.loaded_vram_mb() + need_mb <= (self.vram_budget_mb or float("inf")):
                break
            entry.model = None
