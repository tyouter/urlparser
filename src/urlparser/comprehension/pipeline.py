"""
视频理解管线 - 编排下载、帧提取、VLM 分析、时间轴合并
"""

import os
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .models import (
    ComprehensionConfig, ComprehensionMode,
)
from .models import detect_hardware, select_model, resolve_model_path
from .frame_extractor import FrameExtractor
from .vlm_engine import BaseVLMEngine, OpenVINOEngine, LlamaCppEngine

# Import result types from parent to avoid circular imports
from ..models import VisualFrameResult, ComprehensionResult
from ..utils.ffmpeg_utils import find_ffmpeg, find_ffprobe


class ComprehensionPipeline:
    """
    视频理解管线

    编排 yt-dlp 下载 -> ffmpeg 场景检测 -> VLM 逐帧分析 -> 时间轴合并。
    参照 BaseTranscriber.transcribe_from_url() 模式设计。
    """

    def __init__(self, config: Optional[ComprehensionConfig] = None):
        self.config = config or ComprehensionConfig()
        self._temp_dir: Optional[str] = None
        self._frame_dir: Optional[str] = None
        self._vlm: Optional[BaseVLMEngine] = None

    def comprehend_from_url(
        self,
        url: str,
        transcription_result=None
    ) -> ComprehensionResult:
        """
        从 URL 执行视频理解。

        Args:
            url: 视频 URL
            transcription_result: 已有的转录结果（用于合并时间轴）

        Returns:
            ComprehensionResult
        """
        mode = self.config.mode

        # audio_only 模式：不下载/分析画面
        if mode == "audio_only":
            return ComprehensionResult(
                success=True,
                mode="audio_only",
                timeline_summary="音频转录模式，跳过画面分析",
                engine="none",
            )

        self._temp_dir = tempfile.mkdtemp(prefix="urlparser_comp_")
        self._frame_dir = os.path.join(self._temp_dir, "frames")

        # 查找 ffmpeg
        ffmpeg_path = find_ffmpeg()

        try:
            # 1. 下载视频
            video_path = self._download_video(url, ffmpeg_path)
            if not video_path:
                return ComprehensionResult(
                    success=False, mode=mode, error="视频下载失败"
                )

            # 2. 场景检测 + 关键帧提取
            scenes = FrameExtractor.detect_scenes(
                video_path, threshold=self.config.scdet_threshold,
                ffmpeg_path=ffmpeg_path,
            )
            if not scenes:
                return ComprehensionResult(
                    success=False, mode=mode, error="未检测到有效场景"
                )

            frames = FrameExtractor.extract_keyframes(
                video_path, scenes, self._frame_dir,
                max_frames=self.config.max_frames,
                ffmpeg_path=ffmpeg_path,
            )
            if not frames:
                return ComprehensionResult(
                    success=False, mode=mode, error="关键帧提取失败"
                )

            # 3. 选择并加载 VLM
            hardware = detect_hardware()
            model_id, backend, device = select_model(hardware, self.config)
            model_path = resolve_model_path(model_id)
            self._vlm = self._create_engine(backend)
            self._vlm.load_model(model_path, device)

            # 4. 批量分析
            descriptions = self._vlm.analyze_frames(frames)

            # 5. 构建结果
            visual_frames = []
            for frame_info, desc in zip(frames, descriptions):
                visual_frames.append(VisualFrameResult(
                    timestamp=frame_info["timestamp"],
                    frame_path=frame_info["path"],
                    description=desc,
                ))

            timeline_summary = self._generate_summary(visual_frames)

            # 6. 合并时间轴（如有转录结果）
            merged_text = ""
            if transcription_result:
                merged_text = self._merge_timelines(transcription_result, visual_frames)

            # 清理帧路径（不保留临时文件引用）
            for vf in visual_frames:
                vf.frame_path = ""

            self._vlm.unload()

            return ComprehensionResult(
                success=True,
                mode=mode,
                visual_frames=visual_frames,
                timeline_summary=timeline_summary,
                merged_text=merged_text,
                engine=f"{backend.value}/{model_id}",
                frame_count=len(visual_frames),
            )

        except Exception as e:
            return ComprehensionResult(
                success=False, mode=mode, error=str(e)
            )
        finally:
            self.cleanup()

    def _download_video(self, url: str, ffmpeg_path: Optional[str] = None) -> Optional[str]:
        """使用 yt-dlp Python API 下载视频文件"""
        try:
            import yt_dlp

            output_path = os.path.join(self._temp_dir, "video")
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
                'outtmpl': output_path,
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
            }
            if ffmpeg_path and os.path.isabs(ffmpeg_path):
                ydl_opts['ffmpeg_location'] = ffmpeg_path

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # yt-dlp may output different filenames than expected
                if info.get('_filename'):
                    return info['_filename']

            # Fallback: search temp dir for video files
            for f in os.listdir(self._temp_dir):
                fp = os.path.join(self._temp_dir, f)
                if os.path.isfile(fp) and f.endswith(('.mp4', '.mkv', '.webm', '.flv')):
                    return fp

            return None
        except Exception:
            return None

    def _create_engine(self, backend) -> BaseVLMEngine:
        if backend.value == "openvino":
            return OpenVINOEngine()
        return LlamaCppEngine()

    def _generate_summary(self, visual_frames) -> str:
        """生成时间轴摘要"""
        if not visual_frames:
            return "无画面分析结果"

        lines = [f"共分析 {len(visual_frames)} 个关键帧："]
        for vf in visual_frames:
            h = int(vf.timestamp // 3600)
            m = int((vf.timestamp % 3600) // 60)
            s = int(vf.timestamp % 60)
            lines.append(f"  [{h:02d}:{m:02d}:{s:02d}] {vf.description}")
        return '\n'.join(lines)

    def _merge_timelines(self, transcription_result, visual_frames) -> str:
        """按时间顺序交错音频转录和画面描述"""
        segments = []

        # 转录分段
        if hasattr(transcription_result, 'segments') and transcription_result.segments:
            for seg in transcription_result.segments:
                segments.append({
                    'time': seg.get('start', 0),
                    'type': 'audio',
                    'text': seg.get('text', ''),
                })
        elif hasattr(transcription_result, 'text') and transcription_result.text:
            segments.append({
                'time': 0,
                'type': 'audio',
                'text': transcription_result.text,
            })

        # 画面分段
        for vf in visual_frames:
            segments.append({
                'time': vf.timestamp,
                'type': 'visual',
                'text': vf.description,
            })

        # 按时间排序
        segments.sort(key=lambda x: x['time'])

        # 格式化
        lines = ["## 完整时间轴\n"]
        for seg in segments:
            h = int(seg['time'] // 3600)
            m = int((seg['time'] % 3600) // 60)
            s = int(seg['time'] % 60)
            tag = "[画面]" if seg['type'] == 'visual' else "[音频]"
            lines.append(f"[{h:02d}:{m:02d}:{s:02d}] {tag} {seg['text']}")

        return '\n'.join(lines)

    def cleanup(self):
        """清理临时文件"""
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
            self._frame_dir = None
