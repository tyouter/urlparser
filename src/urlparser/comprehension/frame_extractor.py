"""
帧提取器 - 使用 ffmpeg 场景检测提取关键帧
"""

import subprocess
import re
import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict


class FrameExtractor:
    """
    从视频文件中检测场景并提取关键帧。

    使用 ffmpeg scdet 滤镜进行场景切换检测，在每个场景起始点提取单帧。
    """

    @staticmethod
    def detect_scenes(
        video_path: str,
        threshold: int = 10,
        noise_floor: float = 0.05
    ) -> List[Tuple[float, float]]:
        """
        检测视频场景切换点。

        Args:
            video_path: 视频文件路径
            threshold: 场景切换阈值 (scdet threshold)
            noise_floor: 噪声底限

        Returns:
            场景时间列表 [(start_seconds, end_seconds), ...]

        命令:
            ffmpeg -i video.mp4 -vf "scdet=threshold=10:noise_floor=0.05" -f null -
        """
        vf = f"scdet=threshold={threshold}:noise_floor={noise_floor}"
        cmd = [
            'ffmpeg', '-i', video_path,
            '-vf', vf,
            '-f', 'null', '-'
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise RuntimeError(f"ffmpeg 执行失败: {e}") from e

        # 解析 stderr 中的场景切换检测行
        scene_times: List[float] = []
        for line in result.stderr.split('\n'):
            if 'scene change detected' in line.lower():
                # 尝试提取时间戳: 格式如 "t:1.234" 或 "pts_time:1.234"
                match = re.search(r'(?:t|pts_time):([0-9.]+)', line)
                if match:
                    scene_times.append(float(match.group(1)))

        if not scene_times:
            # 未检测到场景切换，使用默认分段 (每 10 秒)
            duration = FrameExtractor._get_duration(video_path)
            if duration > 0:
                step = 10.0
                scene_times = [i * step for i in range(int(duration / step) + 1)]

        # 构建场景区间
        scenes: List[Tuple[float, float]] = []
        for i, start in enumerate(scene_times):
            if i + 1 < len(scene_times):
                end = scene_times[i + 1]
            else:
                end = FrameExtractor._get_duration(video_path)
            # 跳过过短场景
            if end - start >= 0.5:
                scenes.append((start, end))

        return scenes

    @staticmethod
    def extract_keyframes(
        video_path: str,
        scene_times: List[Tuple[float, float]],
        output_dir: str,
        max_frames: int = 50
    ) -> List[Dict]:
        """
        在每个场景起始点提取关键帧。

        Args:
            video_path: 视频文件路径
            scene_times: 场景时间区间列表
            output_dir: 输出目录
            max_frames: 最大帧数

        Returns:
            帧信息列表 [{"timestamp": float, "path": str}, ...]
        """
        os.makedirs(output_dir, exist_ok=True)

        # 如果场景数超过上限，均匀采样
        scenes = list(scene_times)
        if len(scenes) > max_frames:
            step = len(scenes) / max_frames
            indices = [int(i * step) for i in range(max_frames)]
            scenes = [scenes[i] for i in indices]

        frames = []
        for idx, (start, _end) in enumerate(scenes):
            frame_path = os.path.join(output_dir, f"frame_{idx:04d}.jpg")
            ok = FrameExtractor._extract_single_frame(video_path, start, frame_path)
            if ok:
                frames.append({"timestamp": start, "path": frame_path})

        return frames

    @staticmethod
    def _extract_single_frame(
        video_path: str,
        timestamp: float,
        output_path: str
    ) -> bool:
        """提取单个帧"""
        cmd = [
            'ffmpeg', '-ss', str(timestamp),
            '-i', video_path,
            '-frames:v', '1',
            '-q:v', '2',
            '-y',
            output_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            return result.returncode == 0 and os.path.exists(output_path)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def _get_duration(video_path: str) -> float:
        """获取视频时长（秒）"""
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return float(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            return 0.0
