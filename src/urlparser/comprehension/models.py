"""
视频理解数据模型

定义理解模式、VLM 后端、硬件配置、检测结果等。
ComprehensionResult 和 VisualFrameResult 定义在父级 models.py 中。
"""

from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum
from pathlib import Path

# Re-export from parent to avoid duplication
from ..models import VisualFrameResult, ComprehensionResult

# Model registry: identifier -> local filesystem path
# Models are stored under {package_root}/models/
_MODEL_REGISTRY = {
    "qwen3-vl-2b-int4": "models/qwen3-vl-2b-int4",
    "phi-4-multimodal-int4": "models/phi-4-multimodal-int4",
    "smolvlm-2.2b-gguf-q4": "models/smolvlm-2.2b-gguf-q4",
    "smolvlm-500m-gguf-q4": "models/smolvlm-500m-gguf-q4",
}


def resolve_model_path(model_id: str) -> str:
    """解析模型标识符为本地文件系统路径"""
    if Path(model_id).exists():
        return model_id  # Already a valid path
    rel = _MODEL_REGISTRY.get(model_id, model_id)
    # Try relative to project root (parent of src/)
    pkg_root = Path(__file__).parent.parent.parent
    candidate = pkg_root.parent / rel
    if candidate.exists():
        return str(candidate)
    # Try relative to package root (for packaged installs)
    candidate2 = pkg_root / rel
    if candidate2.exists():
        return str(candidate2)
    # Fallback: return as-is (will fail at load time with clear error)
    return str(candidate)


class ComprehensionMode(Enum):
    """视频理解模式"""
    AUDIO_ONLY = "audio_only"
    VIDEO_ONLY = "video_only"
    AUDIO_VIDEO = "audio_video"


class VLMBackend(Enum):
    """VLM 推理后端"""
    OPENVINO = "openvino"
    LLAMACPP = "llamacpp"


class HardwareProfile(Enum):
    """硬件配置文件"""
    INTEL_NPU = "intel_npu"
    INTEL_IGPU = "intel_igpu"
    CPU_HIGH = "cpu_high"
    CPU_LOW = "cpu_low"


@dataclass
class ComprehensionConfig:
    """视频理解配置 (用于管线内部)"""
    enabled: bool = False
    mode: str = "audio_video"
    engine: str = "auto"
    max_frames: int = 50
    scdet_threshold: int = 10
    language: str = "zh"
    temp_dir: Optional[str] = None


def detect_hardware() -> HardwareProfile:
    """自动检测硬件，返回最佳配置"""
    import psutil as _psutil
    import platform as _platform

    total_ram_gb = _psutil.virtual_memory().total / (1024 ** 3)

    # 检查 NPU / OpenVINO 可用性
    has_npu = False
    has_igpu = False
    try:
        import openvino as ov
        core = ov.Core()
        devices = core.available_devices
        has_npu = 'NPU' in devices
        has_igpu = 'GPU' in devices
    except (ImportError, Exception):
        pass

    if has_npu:
        return HardwareProfile.INTEL_NPU
    if has_igpu:
        return HardwareProfile.INTEL_IGPU

    # 按 RAM 决定 CPU 配置
    if total_ram_gb >= 16:
        return HardwareProfile.CPU_HIGH
    return HardwareProfile.CPU_LOW


def select_model(
    hardware: HardwareProfile,
    config: Optional['ComprehensionConfig'] = None
) -> Tuple[str, VLMBackend, str]:
    """
    根据硬件配置选择最佳模型。

    Returns:
        (model_name, backend, device)
    """
    engine_override = config.engine if config else "auto"

    if engine_override == "openvino":
        return _select_openvino_model(hardware)
    elif engine_override == "llamacpp":
        return _select_llamacpp_model(hardware)

    # 自动选择：优先 OpenVINO
    if hardware in (HardwareProfile.INTEL_NPU, HardwareProfile.INTEL_IGPU):
        return _select_openvino_model(hardware)
    else:
        return _select_llamacpp_model(hardware)


def _select_openvino_model(hardware: HardwareProfile) -> Tuple[str, VLMBackend, str]:
    # NPU 支持仍在完善中，优先使用 iGPU (更稳定)
    device = "GPU"
    return ("qwen3-vl-2b-int4", VLMBackend.OPENVINO, device)


def _select_llamacpp_model(hardware: HardwareProfile) -> Tuple[str, VLMBackend, str]:
    if hardware == HardwareProfile.CPU_LOW:
        return ("smolvlm-500m-gguf-q4", VLMBackend.LLAMACPP, "CPU")
    return ("smolvlm-2.2b-gguf-q4", VLMBackend.LLAMACPP, "CPU")
