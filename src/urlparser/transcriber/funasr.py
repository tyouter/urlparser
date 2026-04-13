"""
FunASR 转录器

中文最佳转录引擎
"""

import os
from typing import Optional, Dict, List
from pathlib import Path

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from .base import BaseTranscriber, TranscriptionResult


class FunASRTranscriber(BaseTranscriber):
    """
    FunASR 转录器

    优势:
    - 中文识别精度高（比 Whisper 高 10-20%）
    - 非自回归架构，推理速度快
    - 自动标点
    - GPU 显存需求低（2-4GB）
    """

    engine_name = "funasr"

    def __init__(self, model_size: str = "large", device: str = "cuda"):
        self.model_size = model_size
        self.device = device
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return

        try:
            from funasr import AutoModel

            model_map = {
                'small': 'iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch',
                'large': 'iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch',
                'sensevoice': 'iic/SenseVoiceSmall',
            }

            model_name = model_map.get(self.model_size, model_map['large'])

            self._model = AutoModel(
                model=model_name,
                device=self.device,
                disable_update=True,
            )

        except ImportError:
            raise ImportError("funasr not installed. Install with: pip install funasr modelscope")
        except Exception as e:
            raise RuntimeError(f"Failed to load FunASR model: {e}")

    def transcribe(self, audio_path: str, language: str = "zh") -> TranscriptionResult:
        self._load_model()

        if not Path(audio_path).exists():
            return TranscriptionResult(
                success=False,
                error=f'File not found: {audio_path}',
                engine=self.engine_name
            )

        try:
            result = self._model.generate(
                input=audio_path,
                batch_size_s=300,
            )

            if result and len(result) > 0:
                text = result[0].get('text', '')

                segments = []
                if 'sentences' in result[0]:
                    for sent in result[0]['sentences']:
                        segments.append({
                            'start': sent.get('start', 0),
                            'end': sent.get('end', 0),
                            'text': sent.get('text', '').strip()
                        })

                return TranscriptionResult(
                    success=True,
                    text=text,
                    segments=segments,
                    language=language,
                    engine=self.engine_name
                )
            else:
                return TranscriptionResult(
                    success=False,
                    error='No transcription result',
                    engine=self.engine_name
                )

        except Exception as e:
            return TranscriptionResult(
                success=False,
                error=str(e),
                engine=self.engine_name
            )