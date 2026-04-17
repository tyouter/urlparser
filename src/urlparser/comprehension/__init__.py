"""
视频理解模块 - 本地 VLM 驱动的帧级分析

提供帧提取、场景检测、VLM 分析和时间轴合并能力。
"""

from .models import (
    ComprehensionMode, VLMBackend, HardwareProfile,
    ComprehensionConfig,
    detect_hardware, select_model,
)
# Re-export result types from parent models
from ..models import VisualFrameResult, ComprehensionResult
from .frame_extractor import FrameExtractor
from .vlm_engine import BaseVLMEngine, OpenVINOEngine, LlamaCppEngine
from .pipeline import ComprehensionPipeline
from .writer import TimelineWriter

__all__ = [
    'ComprehensionMode', 'VLMBackend', 'HardwareProfile',
    'ComprehensionConfig',
    'detect_hardware', 'select_model',
    'VisualFrameResult', 'ComprehensionResult',
    'FrameExtractor', 'BaseVLMEngine', 'OpenVINOEngine', 'LlamaCppEngine',
    'ComprehensionPipeline', 'TimelineWriter',
]
