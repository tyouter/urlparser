"""
FunASR 转录器

中文最佳转录引擎

注意: FunASR 处理长音频时存在内存分配缺陷，必须分段处理。
所有超过 MAX_DIRECT_DURATION 秒的音频都会被自动分段。
"""

import os
import gc
import re
import tempfile
import shutil
from typing import Optional, Dict, List
from pathlib import Path

from .base import BaseTranscriber, TranscriptionResult, convert_audio_for_funasr


MAX_DIRECT_DURATION = 240.0
SEGMENT_DURATION = 240.0

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

            print(f"Loading FunASR model: {model_name}")

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

            if duration > MAX_DIRECT_DURATION:
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
                batch_size_s=300,
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

        num_segments = int(duration / SEGMENT_DURATION) + (1 if duration % SEGMENT_DURATION > 0 else 0)

        print(f"Segmented mode: {duration:.0f}s audio, {num_segments} segments of {SEGMENT_DURATION:.0f}s each")

        all_text = []
        all_segments = []
        temp_dir = tempfile.mkdtemp(prefix='funasr_seg_')

        try:
            for i in range(num_segments):
                start = i * SEGMENT_DURATION
                end = min((i + 1) * SEGMENT_DURATION, duration)

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
                    print(f"  Seg {i+1}/{num_segments} [{start:.0f}s-{end:.0f}s]: extraction failed, skip")
                    continue

                seg_size_mb = Path(seg_wav).stat().st_size / (1024 * 1024)
                print(f"  Seg {i+1}/{num_segments} [{start:.0f}s-{end:.0f}s] ({seg_size_mb:.1f}MB): transcribing...")

                result = self._do_transcribe(seg_wav, language)

                if result.success and result.text:
                    all_text.append(result.text)
                    for seg in result.segments:
                        all_segments.append({
                            'start': seg.get('start', 0) + start,
                            'end': seg.get('end', 0) + start,
                            'text': seg.get('text', ''),
                        })
                    preview = result.text[:50].replace('\n', ' ')
                    print(f"  Seg {i+1}/{num_segments}: OK -> {preview}...")
                elif result.success:
                    print(f"  Seg {i+1}/{num_segments}: OK (no speech)")
                else:
                    print(f"  Seg {i+1}/{num_segments}: FAIL - {result.error}")

                try:
                    os.unlink(seg_wav)
                except Exception:
                    pass

                gc.collect()

        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

        merged_text = ''.join(all_text)

        return TranscriptionResult(
            success=True,
            text=merged_text,
            segments=all_segments,
            language=language,
            duration=duration,
            engine=f"{self.engine_name}(segmented-{num_segments})"
        )
