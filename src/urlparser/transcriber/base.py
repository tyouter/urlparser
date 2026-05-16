"""
转录器抽象基类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
import subprocess
from ..utils._subprocess_win import run_nowindow as _run
import os
import logging

logger = logging.getLogger(__name__)

from ..utils.ffmpeg_utils import find_ffmpeg


def convert_audio_for_funasr(input_path: str, output_path: str,
                             start: Optional[float] = None, end: Optional[float] = None) -> bool:
    """
    Convert audio to 16kHz mono WAV format that FunASR expects.

    FunASR requires specific audio format to avoid memory allocation bugs.

    Args:
        input_path: Input audio/video file
        output_path: Output WAV file path
        start: Start time in seconds (optional, for segment extraction)
        end: End time in seconds (optional, for segment extraction)

    Returns:
        True if conversion successful
    """
    from pathlib import Path

    try:
        ffmpeg_cmd = find_ffmpeg()

        cmd = [ffmpeg_cmd]

        if start is not None:
            cmd.extend(['-ss', str(start)])
        if end is not None:
            cmd.extend(['-to', str(end)])

        cmd.extend([
            '-i', input_path,
            '-ar', '16000',
            '-ac', '1',
            '-f', 'wav',
            '-y',
            output_path
        ])

        result = _run(
            cmd,
            capture_output=True,
            timeout=600
        )

        if result.returncode == 0:
            output_file = Path(output_path)
            if output_file.exists():
                file_size = output_file.stat().st_size
                if file_size > 0:
                    return True
        else:
            logger.warning("FFmpeg stderr: %s", result.stderr[:500] if result.stderr else 'None')

        return False
    except Exception as e:
        logger.error("Audio conversion failed: %s", e)
        return False


@dataclass
class TranscriptionResult:
    success: bool = False
    text: str = ""
    segments: List[Dict[str, Any]] = field(default_factory=list)
    language: str = ""
    duration: float = 0.0
    engine: str = ""
    error: Optional[str] = None

    @property
    def has_text(self) -> bool:
        return bool(self.text and len(self.text) > 0)

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'text': self.text,
            'segments': self.segments,
            'language': self.language,
            'duration': self.duration,
            'engine': self.engine,
            'error': self.error,
        }


class BaseTranscriber(ABC):
    """转录器抽象基类"""

    engine_name: str = "base"

    @abstractmethod
    def transcribe(self, audio_path: str, language: str = "zh") -> TranscriptionResult:
        pass

    def transcribe_from_url(self, url: str, language: str = "zh", use_audio_only: bool = True) -> TranscriptionResult:
        import tempfile
        from pathlib import Path

        temp_dir = tempfile.mkdtemp(prefix='transcriber_')
        audio_file = None
        converted_file = None

        try:
            import yt_dlp

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }

            ffmpeg_path = find_ffmpeg()
            if os.path.isabs(ffmpeg_path):
                ydl_opts['ffmpeg_location'] = ffmpeg_path

            if use_audio_only:
                # Download best audio, keep original format first
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(title)s.%(ext)s')
            else:
                ydl_opts['format'] = 'bestvideo+bestaudio/best'
                ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(title)s.%(ext)s')

            import io
            from contextlib import redirect_stdout
            with redirect_stdout(io.StringIO()):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    downloaded_file = ydl.prepare_filename(info)

                    if downloaded_file and not Path(downloaded_file).exists():
                        for f in Path(temp_dir).iterdir():
                            if f.is_file():
                                downloaded_file = str(f)
                                break

                if downloaded_file and Path(downloaded_file).exists():
                    audio_file = downloaded_file

            if not audio_file:
                return TranscriptionResult(
                    success=False,
                    error='Failed to download audio',
                    engine=self.engine_name
                )

            # For FunASR, convert to 16kHz mono WAV to avoid memory bugs
            if self.engine_name == "funasr":
                converted_file = os.path.join(temp_dir, 'audio_converted.wav')
                logger.info("Converting audio for FunASR: %s -> %s", audio_file, converted_file)
                if convert_audio_for_funasr(audio_file, converted_file):
                    from pathlib import Path
                    file_size = Path(converted_file).stat().st_size
                    logger.info("Conversion successful, output size: %d bytes", file_size)
                    audio_file = converted_file
                else:
                    logger.warning("Conversion failed, using original file")
                    # Fallback: try original file
                    pass

            return self.transcribe(audio_file, language)

        except Exception as e:
            return TranscriptionResult(
                success=False,
                error=f'Download/transcription failed: {str(e)}',
                engine=self.engine_name
            )

        finally:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

    def transcribe_from_local_video(self, video_path: str, language: str = "zh",
                                     extract_audio_only: bool = False) -> TranscriptionResult:
        import tempfile
        from pathlib import Path

        temp_audio_file = None

        try:
            audio_path = video_path

            # For FunASR, convert to 16kHz mono WAV to avoid memory bugs
            if self.engine_name == "funasr":
                temp_audio_file = tempfile.mktemp(suffix='.wav', prefix='funasr_audio_')
                if convert_audio_for_funasr(video_path, temp_audio_file):
                    audio_path = temp_audio_file
                else:
                    # Fallback to original
                    audio_path = video_path
            elif extract_audio_only:
                # For other engines, extract audio if requested
                temp_audio_file = tempfile.mktemp(suffix='.mp3', prefix='audio_')

                ffmpeg_cmd = find_ffmpeg()

                cmd = [
                    ffmpeg_cmd,
                    '-i', video_path,
                    '-vn',
                    '-acodec', 'libmp3lame',
                    '-ab', '192k',
                    '-y',
                    temp_audio_file
                ]

                # Use binary mode to avoid Windows encoding issues
                result = _run(cmd, capture_output=True, timeout=60)

                if result.returncode == 0 and Path(temp_audio_file).exists():
                    audio_path = temp_audio_file

            return self.transcribe(audio_path, language)

        except Exception as e:
            return TranscriptionResult(
                success=False,
                error=f'Transcription failed: {str(e)}',
                engine=self.engine_name
            )

        finally:
            if temp_audio_file and os.path.exists(temp_audio_file) and temp_audio_file != video_path:
                try:
                    os.unlink(temp_audio_file)
                except Exception:
                    pass