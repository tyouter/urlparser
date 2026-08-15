"""
FunASR 标点模型测试（Hermes brief：SenseVoice 输出带标点，不换主模型）

验证：punc_model=ct-punc 传入 AutoModel、加载失败时优雅降级无标点、
punc_model="" 时完全跳过。
模型真实加载/网络下载不在此测试范围（monkeypatch AutoModel）。
"""

import pytest

# 守卫原则（v4 固化）：可选依赖缺失 → SKIP，绝不 FAIL。
# 只查 funasr 不够：funasr 的 AutoModel 是 lazy export，
# 首次访问才触发 import torch/modelscope；缺 torch 时 monkeypatch.setattr
# 会 ImportError 导致 FAIL。因此守卫必须实际解析 AutoModel。
try:
    import torch  # noqa: F401
    import funasr  # noqa: F401
    from funasr import AutoModel  # noqa: F401  # 触发 lazy export，验证依赖齐备
    HAS_FUNASR = True
except ImportError:
    HAS_FUNASR = False

pytestmark = pytest.mark.skipif(not HAS_FUNASR, reason="funasr/torch 依赖缺失")

from urlparser.transcriber.funasr import FunASRTranscriber  # noqa: E402


class _FakeModel:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def generate(self, input, batch_size_s=300, use_itn=True):
        return [{"text": "你好，世界。", "sentences": []}]


def test_load_model_passes_punc_model(monkeypatch):
    captured = {}

    def fake_automodel(**kwargs):
        captured.update(kwargs)
        return _FakeModel(**kwargs)

    monkeypatch.setattr("funasr.AutoModel", fake_automodel)

    t = FunASRTranscriber(model_size="large", device="cpu")
    t._load_model()
    assert captured.get("punc_model") == "ct-punc"
    assert captured.get("model") == "iic/SenseVoiceSmall"


def test_punc_failure_falls_back_without_punc(monkeypatch):
    calls = []

    def fake_automodel(**kwargs):
        calls.append(kwargs)
        if kwargs.get("punc_model"):
            raise RuntimeError("punc download failed")
        return _FakeModel(**kwargs)

    monkeypatch.setattr("funasr.AutoModel", fake_automodel)

    t = FunASRTranscriber(model_size="large", device="cpu")
    t._load_model()  # 不抛异常：降级成功
    assert t._model is not None
    assert calls[0].get("punc_model") == "ct-punc"
    assert "punc_model" not in calls[1]


def test_empty_punc_model_skips_punc(monkeypatch):
    captured = {}

    def fake_automodel(**kwargs):
        captured.update(kwargs)
        return _FakeModel(**kwargs)

    monkeypatch.setattr("funasr.AutoModel", fake_automodel)

    t = FunASRTranscriber(model_size="large", device="cpu", punc_model="")
    t._load_model()
    assert "punc_model" not in captured


def test_preloaded_model_with_punc_param():
    # M3 常驻注入 + punc 参数共存：preloaded 时不再加载
    t = FunASRTranscriber(model_size="large", device="cpu",
                          preloaded_model=_FakeModel(), punc_model="ct-punc")
    assert t._punc_model == "ct-punc"
