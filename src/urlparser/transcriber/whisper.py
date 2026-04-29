"""
Whisper 转录器

支持 99 种语言的转录引擎
"""

import os
from typing import Optional
from pathlib import Path

from .base import BaseTranscriber, TranscriptionResult


class WhisperTranscriber(BaseTranscriber):
    """
    Whisper 转录器

    优势:
    - 支持 99 种语言
    - 开源社区广泛支持
    - 多种模型大小可选
    """

    engine_name = "whisper"

    def __init__(self, model_size: str = "base", device: str = "auto"):
        self.model_size = model_size
        self.device = device
        self._model = None

    @staticmethod
    def is_available() -> bool:
        try:
            import faster_whisper
            return True
        except ImportError:
            return False

    @staticmethod
    def detect_device() -> str:
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _load_model(self):
        if self._model is not None:
            return

        try:
            from faster_whisper import WhisperModel

            device = "cuda" if self.device in ["auto", "cuda"] else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"

            self._model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type
            )

        except ImportError:
            raise ImportError("faster-whisper not installed. Install with: pip install faster-whisper")
        except Exception as e:
            raise RuntimeError(f"Failed to load Whisper model: {e}")

    def transcribe(self, audio_path: str, language: str = "zh") -> TranscriptionResult:
        self._load_model()

        if not Path(audio_path).exists():
            return TranscriptionResult(
                success=False,
                error=f'File not found: {audio_path}',
                engine=self.engine_name
            )

        try:
            segments, info = self._model.transcribe(
                audio_path,
                language=language,
                vad_filter=True,
                word_timestamps=False
            )

            segment_list = list(segments)
            full_text = "".join([segment.text for segment in segment_list])

            formatted_segments = []
            for segment in segment_list:
                formatted_segments.append({
                    'start': segment.start,
                    'end': segment.end,
                    'text': segment.text.strip()
                })

            return TranscriptionResult(
                success=True,
                text=full_text,
                segments=formatted_segments,
                language=info.language,
                duration=info.duration,
                engine=self.engine_name
            )

        except Exception as e:
            return TranscriptionResult(
                success=False,
                error=str(e),
                engine=self.engine_name
            )