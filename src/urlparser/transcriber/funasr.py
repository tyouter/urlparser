"""
FunASR 转录器

中文最佳转录引擎

注意: FunASR 处理长音频时存在内存分配缺陷，必须分段处理。
所有超过 MAX_DIRECT_DURATION 秒的音频都会被自动分段。
"""

import os
import gc
import logging
import re
import time
import tempfile
import shutil
from typing import Optional, Dict, List, Callable
from pathlib import Path

from .base import BaseTranscriber, TranscriptionResult, convert_audio_for_funasr

logger = logging.getLogger(__name__)


# Default segment constants (will be overridden based on device/GPU memory)
_DEFAULT_MAX_DIRECT_DURATION = 240.0
_DEFAULT_SEGMENT_DURATION = 240.0

SENSEVOICE_SPECIAL_TOKENS = re.compile(
    r'<\|[^|]*\|>'
)


class FunASRTranscriber(BaseTranscriber):
    engine_name = "funasr"

    def __init__(self, model_size: str = "large", device: str = "cuda"):
        self.model_size = model_size
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        self.device = device
        self._model = None
        self._max_direct_duration = _DEFAULT_MAX_DIRECT_DURATION
        self._segment_duration = _DEFAULT_SEGMENT_DURATION
        self._batch_size_s = 300
        self._gpu_memory_gb = 0.0
        self._on_progress: Optional[Callable] = None

        # GPU-adaptive tuning
        if self.device == "cuda":
            try:
                self._tune_for_gpu()
            except Exception:
                pass  # Fall back to defaults on any error

    @staticmethod
    def is_available() -> bool:
        try:
            import funasr
            return True
        except Exception:
            return False

    @staticmethod
    def detect_device() -> str:
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _tune_for_gpu(self):
        """Dynamically tune segment size and batch params based on GPU memory."""
        try:
            import torch
            if not torch.cuda.is_available():
                return

            props = torch.cuda.get_device_properties(0)
            gpu_mem_gb = props.total_memory / (1024 ** 3)
            self._gpu_memory_gb = gpu_mem_gb
            gpu_name = props.name

            # SenseVoice Small ~300MB model + audio features ~3x WAV size
            # Conservative: 1h 16kHz mono WAV ≈ 115MB → features ≈ 350MB
            # Total peak per segment: ~650MB + overhead
            usable_gb = gpu_mem_gb * 0.75  # 75% safety margin

            if usable_gb >= 8.0:
                self._segment_duration = 600.0   # 10 min per segment
                self._max_direct_duration = 600.0
                self._batch_size_s = 600
            elif usable_gb >= 4.0:
                self._segment_duration = 360.0   # 6 min per segment
                self._max_direct_duration = 360.0
                self._batch_size_s = 450
            elif usable_gb >= 2.0:
                self._segment_duration = 360.0   # 6 min (slight bump over default)
                self._max_direct_duration = 360.0
                self._batch_size_s = 360
            # else: stay with defaults (240s / 300 batch)

            logger.info(
                "[FunASR GPU] %s (%.1fGB usable) → seg=%.0fs, batch=%d",
                gpu_name, usable_gb,
                self._segment_duration, self._batch_size_s,
            )
        except Exception as e:
            logger.debug("GPU tuning skipped: %s", e)

    def set_progress_callback(self, on_progress: Optional[Callable]):
        """Set progress callback for structured progress events."""
        self._on_progress = on_progress

    def _emit(self, phase: str, step: int, total_steps: int,
              message: str, percentage: float, extra: dict = None):
        """Emit a progress event if callback is set."""
        if self._on_progress is None:
            return
        from ..models import ProgressEvent
        event = ProgressEvent(
            stage="transcribe", phase=phase, step=step, total_steps=total_steps,
            elapsed_sec=0, message=message, percentage=percentage, extra=extra or {},
        )
        try:
            self._on_progress(event)
        except Exception:
            pass

    def _load_model(self):
        if self._model is not None:
            return

        try:
            from funasr import AutoModel

            model_map = {
                'small': 'iic/SenseVoiceSmall',
                'base': 'iic/SenseVoiceSmall',
                'large': 'iic/SenseVoiceSmall',
                'sensevoice': 'iic/SenseVoiceSmall',
            }

            model_name = model_map.get(self.model_size, model_map['large'])

            logger.info("Loading FunASR model: %s", model_name)

            self._model = AutoModel(
                model=model_name,
                device=self.device,
                disable_update=True,
                disable_pbar=True,

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

        converted_file = None
        actual_path = audio_path

        try:
            suffix = Path(audio_path).suffix.lower()
            if suffix not in ('.wav',):
                converted_file = tempfile.mktemp(suffix='.wav', prefix='funasr_conv_')
                if convert_audio_for_funasr(audio_path, converted_file):
                    actual_path = converted_file
                else:
                    actual_path = audio_path

            from ..utils.media_utils import get_media_duration
            duration = get_media_duration(actual_path)

            if duration <= 0:
                duration = self._estimate_duration_from_wav(actual_path)

            if duration > self._max_direct_duration:
                return self._transcribe_segmented(actual_path, duration, language)

            return self._do_transcribe(actual_path, language)

        finally:
            if converted_file and os.path.exists(converted_file):
                try:
                    os.unlink(converted_file)
                except Exception:
                    pass

    def _estimate_duration_from_wav(self, wav_path: str) -> float:
        try:
            file_size = Path(wav_path).stat().st_size
            header_size = 44
            data_size = file_size - header_size
            sample_rate = 16000
            bits_per_sample = 16
            channels = 1
            bytes_per_second = sample_rate * (bits_per_sample // 8) * channels
            if bytes_per_second > 0:
                return data_size / bytes_per_second
        except Exception:
            pass
        return 0.0

    def _do_transcribe(self, audio_path: str, language: str = "zh") -> TranscriptionResult:
        try:
            result = self._model.generate(
                input=audio_path,
                batch_size_s=self._batch_size_s,
                use_itn=True,
            )

            if result and len(result) > 0:
                text = result[0].get('text', '')
                text = SENSEVOICE_SPECIAL_TOKENS.sub('', text).strip()

                segments = []
                if 'sentences' in result[0]:
                    for sent in result[0]['sentences']:
                        seg_text = SENSEVOICE_SPECIAL_TOKENS.sub('', sent.get('text', '')).strip()
                        if seg_text:
                            segments.append({
                                'start': sent.get('start', 0),
                                'end': sent.get('end', 0),
                                'text': seg_text
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

    def _transcribe_segmented(self, audio_path: str, duration: float, language: str = "zh") -> TranscriptionResult:
        from ..utils.media_utils import extract_audio_segment

        num_segments = int(duration / self._segment_duration) + (1 if duration % self._segment_duration > 0 else 0)

        logger.info("Segmented mode: %.0fs audio, %d segments of %.0fs each (batch=%d)",
                    duration, num_segments, self._segment_duration, self._batch_size_s)
        self._emit("start", 0, num_segments,
                   f"分段转录 {num_segments} 段 × {self._segment_duration:.0f}s",
                   0.0,
                   {"duration": duration, "segments": num_segments,
                    "seg_duration": self._segment_duration})

        all_text = []
        all_segments = []
        temp_dir = tempfile.mkdtemp(prefix='funasr_seg_')
        seg_files = []  # Track segment files for batch cleanup
        t_start = time.time()

        try:
            # Phase 1: Extract all segment audio files
            for i in range(num_segments):
                start = i * self._segment_duration
                end = min((i + 1) * self._segment_duration, duration)
                seg_wav = os.path.join(temp_dir, f"seg_{i:04d}.wav")

                convert_audio_for_funasr(audio_path, seg_wav, start, end)

                if not os.path.exists(seg_wav) or Path(seg_wav).stat().st_size < 1000:
                    seg_mp3 = os.path.join(temp_dir, f"seg_{i:04d}.mp3")
                    extract_audio_segment(audio_path, start, end, seg_mp3)
                    if os.path.exists(seg_mp3):
                        convert_audio_for_funasr(seg_mp3, seg_wav)
                        try:
                            os.unlink(seg_mp3)
                        except Exception:
                            pass

                if not os.path.exists(seg_wav) or Path(seg_wav).stat().st_size < 1000:
                    logger.warning("Seg %d/%d [%.0fs-%.0fs]: extraction failed, skip", i+1, num_segments, start, end)
                    seg_files.append(None)
                    continue

                seg_files.append(seg_wav)
                seg_size_mb = Path(seg_wav).stat().st_size / (1024 * 1024)
                extraction_pct = (i + 1) / num_segments * 15  # Extraction is ~15% of total
                self._emit("progress", i + 1, num_segments,
                          f"音频提取 [{i+1}/{num_segments}] {start:.0f}s-{end:.0f}s ({seg_size_mb:.1f}MB)",
                          extraction_pct,
                          {"sub_phase": "extraction", "seg_index": i,
                           "start": start, "end": end, "size_mb": seg_size_mb})

            # Phase 2: Batch transcribe all segments (GPU reuse, no gc between)
            for i in range(num_segments):
                start = i * self._segment_duration
                end = min((i + 1) * self._segment_duration, duration)
                seg_file = seg_files[i]

                if seg_file is None:
                    logger.warning("Seg %d/%d [%.0fs-%.0fs]: extraction failed, skip", i+1, num_segments, start, end)
                    continue

                seg_size_mb = Path(seg_file).stat().st_size / (1024 * 1024)
                base_pct = 15 + 85 * (i / max(num_segments, 1))
                self._emit("progress", i + 1, num_segments,
                          f"转录 [{i+1}/{num_segments}] {start:.0f}s-{end:.0f}s ({seg_size_mb:.1f}MB)",
                          base_pct,
                          {"sub_phase": "transcribe", "seg_index": i,
                           "start": start, "end": end, "size_mb": seg_size_mb})

                result = self._do_transcribe(seg_file, language)

                if result.success and result.text:
                    all_text.append(result.text)
                    for seg in result.segments:
                        all_segments.append({
                            'start': seg.get('start', 0) + start,
                            'end': seg.get('end', 0) + start,
                            'text': seg.get('text', ''),
                        })
                    preview = result.text[:50].replace('\n', ' ')
                    logger.debug("Seg %d/%d: OK -> %s...", i+1, num_segments, preview)
                elif result.success:
                    logger.debug("Seg %d/%d: OK (no speech)", i+1, num_segments)
                else:
                    logger.warning("Seg %d/%d: FAIL - %s", i+1, num_segments, result.error)

                # Skip gc.collect() on GPU — PyTorch manages GPU memory natively
                if self.device != "cuda":
                    gc.collect()

        finally:
            # Clean up all segment files
            for sf in seg_files:
                if sf and os.path.exists(sf):
                    try:
                        os.unlink(sf)
                    except Exception:
                        pass
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

        elapsed = time.time() - t_start
        logger.info("Segmented transcription done: %d segments in %.1fs (%.0fx realtime)",
                    len(all_segments), elapsed, duration / elapsed if elapsed > 0 else 0)

        merged_text = ''.join(all_text)

        return TranscriptionResult(
            success=True,
            text=merged_text,
            segments=all_segments,
            language=language,
            duration=duration,
            engine=f"{self.engine_name}(segmented-{num_segments})"
        )