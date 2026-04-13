"""
转录器抽象基类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any


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
        import os
        import tempfile
        from pathlib import Path

        temp_dir = tempfile.mkdtemp(prefix='transcriber_')
        audio_file = None

        try:
            import yt_dlp

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }

            if os.name == 'nt' and os.path.exists('C:/ffmpeg/bin/ffmpeg.exe'):
                ydl_opts['ffmpeg_location'] = 'C:/ffmpeg/bin/ffmpeg.exe'

            if use_audio_only:
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(title)s.%(ext)s')
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            else:
                ydl_opts['format'] = 'bestvideo+bestaudio/best'
                ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(title)s.%(ext)s')

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
        import os
        import tempfile
        import subprocess

        temp_audio_file = None

        try:
            if extract_audio_only:
                temp_audio_file = tempfile.mktemp(suffix='.mp3', prefix='audio_')

                cmd = [
                    'ffmpeg',
                    '-i', video_path,
                    '-vn',
                    '-acodec', 'libmp3lame',
                    '-ab', '192k',
                    '-y',
                    temp_audio_file
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    audio_path = video_path
                else:
                    audio_path = temp_audio_file
            else:
                audio_path = video_path

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