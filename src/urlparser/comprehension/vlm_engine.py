"""
VLM 引擎抽象层

提供统一的 VLM 接口，支持 OpenVINO (Intel NPU/iGPU) 和 llama.cpp (CPU) 后端。
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from pathlib import Path

import numpy as np
from PIL import Image

_DEFAULT_PROMPT = (
    "请描述这个视频帧的内容，包括场景类型、主要物体、人物动作、文字信息。"
    "用中文简要回答，不超过100字。"
)


def _load_image_tensor(image_path: str):
    """Load image as OpenVINO Tensor for VLMPipeline"""
    import openvino as ov
    pic = Image.open(image_path).convert("RGB")
    image_data = np.array(pic)[None]
    return ov.Tensor(image_data)


class BaseVLMEngine(ABC):
    """VLM 引擎基类"""

    @abstractmethod
    def load_model(self, model_name: str, device: str = "CPU") -> None:
        """加载模型到指定设备"""
        ...

    @abstractmethod
    def analyze_frame(self, image_path: str, prompt: str = _DEFAULT_PROMPT) -> str:
        """分析单帧图像，返回文本描述"""
        ...

    def analyze_frames(
        self,
        frames: List[Dict],
        prompt: str = _DEFAULT_PROMPT
    ) -> List[str]:
        """批量分析帧"""
        return [self.analyze_frame(f["path"], prompt) for f in frames]

    @abstractmethod
    def unload(self) -> None:
        """释放模型资源"""
        ...


class OpenVINOEngine(BaseVLMEngine):
    """
    OpenVINO VLM 引擎。

    支持 Intel NPU / iGPU 推理，加载 INT4 量化模型。
    需要 openvino 和 openvino-genai 包。
    """

    def __init__(self):
        self._model = None
        self._loaded = False
        self._model_name = ""
        self._device = "CPU"

    def load_model(self, model_name: str, device: str = "GPU") -> None:
        try:
            from openvino import Core
            from openvino_genai import VLMPipeline

            self._model = VLMPipeline(model_name, device=device)
            self._loaded = True
            self._model_name = model_name
            self._device = device
        except ImportError as e:
            raise ImportError(
                "OpenVINO 未安装。请运行: pip install openvino openvino-genai"
            ) from e

    def analyze_frame(self, image_path: str, prompt: str = _DEFAULT_PROMPT) -> str:
        if not self._loaded:
            raise RuntimeError("模型未加载")

        import openvino_genai as ov_genai

        image_tensor = _load_image_tensor(image_path)
        history = ov_genai.ChatHistory()
        history.append({"role": "user", "content": prompt})

        result = self._model.generate(
            history,
            images=[image_tensor],
            max_new_tokens=200,
        )
        return str(result.texts[0]).strip()

    def unload(self) -> None:
        self._model = None
        self._loaded = False


class LlamaCppEngine(BaseVLMEngine):
    """
    llama.cpp VLM 引擎。

    CPU 推理，加载 GGUF 格式模型。
    需要 llama-cpp-python 包。
    """

    def __init__(self):
        self._model = None
        self._loaded = False
        self._model_name = ""

    def load_model(self, model_name: str, device: str = "CPU") -> None:
        try:
            from llama_cpp import Llama
            # llama-cpp-python 用于 LLM，多模态需要 llama-cpp-python 的 VLM 支持
            # SmolVLM 支持需要特定的 VLM loader
            self._model_name = model_name
            self._model = Llama(
                model_path=model_name,
                n_ctx=4096,
                n_threads=4,
                n_gpu_layers=0,  # CPU only
                verbose=False,
            )
            self._loaded = True
        except ImportError as e:
            raise ImportError(
                "llama-cpp-python 未安装。请运行: pip install llama-cpp-python"
            ) from e

    def analyze_frame(self, image_path: str, prompt: str = _DEFAULT_PROMPT) -> str:
        if not self._loaded:
            raise RuntimeError("模型未加载")

        try:
            from PIL import Image
        except ImportError:
            raise ImportError("Pillow 未安装。请运行: pip install pillow")

        image = Image.open(image_path)

        # 构建消息格式
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        result = self._model.create_chat_completion(
            messages=messages,
            max_tokens=200,
        )

        content = result["choices"][0]["message"].get("content", "")
        return str(content).strip()

    def unload(self) -> None:
        self._model = None
        self._loaded = False
