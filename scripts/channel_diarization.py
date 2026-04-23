"""
声道分离转录 - 获取精确时间戳和说话人区分

通过分离左右声道来区分说话人，然后用Whisper获取每句话的精确时间戳
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from urlparser.transcriber.whisper import WhisperTranscriber


def extract_channels(video_path: str, output_dir: str, duration: float = None):
    """提取左右声道"""
    left_path = os.path.join(output_dir, "left_channel.wav")
    right_path = os.path.join(output_dir, "right_channel.wav")

    # 时间参数
    time_param = f"-t {int(duration)}" if duration else ""

    # 提取左声道
    cmd_left = [
        "ffmpeg", "-i", video_path,
        "-ss", "0",  # 从开头开始
        "-af", "pan=mono|c0=FL",  # 只取左声道
        "-ar", "16000",  # 采样率
        "-c:a", "pcm_s16le",
        "-y", left_path
    ]
    if duration:
        cmd_left.insert(4, "-t")
        cmd_left.insert(5, str(int(duration)))

    # 提取右声道
    cmd_right = [
        "ffmpeg", "-i", video_path,
        "-ss", "0",
        "-af", "pan=mono|c0=FR",  # 只取右声道
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        "-y", right_path
    ]
    if duration:
        cmd_right.insert(4, "-t")
        cmd_right.insert(5, str(int(duration)))

    print("提取左声道...")
    subprocess.run(cmd_left, capture_output=True, check=True)

    print("提取右声道...")
    subprocess.run(cmd_right, capture_output=True, check=True)

    return left_path, right_path


def transcribe_channel(audio_path: str, speaker_label: str) -> List[Dict[str, Any]]:
    """转录单个声道，返回带时间戳的句子列表"""
    print(f"转录 {speaker_label} 声道: {audio_path}")

    transcriber = WhisperTranscriber(model_size="base", device="cuda")
    result = transcriber.transcribe(audio_path, language="zh")

    if not result.success:
        print(f"转录失败: {result.error}")
        return []

    segments = []
    for seg in result.segments:
        segments.append({
            "start": seg.get("start", 0),
            "end": seg.get("end", 0),
            "text": seg.get("text", "").strip(),
            "speaker": speaker_label
        })

    print(f"  获取 {len(segments)} 个句子片段")
    return segments


def merge_and_sort_segments(left_segments: List, right_segments: List) -> List:
    """合并左右声道的转录结果，按时间排序"""
    all_segments = left_segments + right_segments
    # 按开始时间排序
    all_segments.sort(key=lambda x: x["start"])
    return all_segments


def main():
    video_path = "D:/boke/20260418/C0257.MP4"
    output_dir = "D:/boke/20260418"
    output_json = "D:/boke/20260418/C0257_diarized.json"

    # 先测试前5分钟
    test_duration = 300  # 5分钟

    print("=" * 60)
    print("声道分离转录测试 (前5分钟)")
    print("=" * 60)

    # 提取声道
    left_path, right_path = extract_channels(video_path, output_dir, test_duration)

    # 分别转录
    print("\n转录左声道...")
    left_segments = transcribe_channel(left_path, "left")

    print("\n转录右声道...")
    right_segments = transcribe_channel(right_path, "right")

    # 合并排序
    all_segments = merge_and_sort_segments(left_segments, right_segments)

    print(f"\n合并后共 {len(all_segments)} 个句子片段")

    # 输出前20个片段供查看
    print("\n前20个片段:")
    print("-" * 60)
    for i, seg in enumerate(all_segments[:20]):
        time_str = f"[{seg['start']:.2f}s - {seg['end']:.2f}s]"
        print(f"{i+1}. {time_str} [{seg['speaker']}]: {seg['text'][:50]}...")

    # 保存JSON
    output_data = {
        "video_path": video_path,
        "test_duration": test_duration,
        "total_segments": len(all_segments),
        "segments": all_segments[:100]  # 只保存前100个供测试
    }

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n已保存到: {output_json}")


if __name__ == "__main__":
    main()