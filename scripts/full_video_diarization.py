"""
全量视频声道分离转录

处理完整的86分钟视频：
1. 提取左右声道
2. 使用Whisper获取精确时间戳
3. 合并去重，生成最终字幕文件
"""

import os
import sys
import json
import subprocess
import tempfile
import gc
from pathlib import Path
from typing import List, Dict, Any
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from urlparser.utils.media_utils import get_media_duration


def get_video_duration(video_path: str) -> float:
    """获取视频时长"""
    return get_media_duration(video_path)


def extract_channel(video_path: str, output_path: str, channel: str, duration: float = None):
    """提取单个声道"""
    if channel == "left":
        pan_filter = "pan=mono|c0=FL"
    else:
        pan_filter = "pan=mono|c0=FR"

    cmd = [
        "ffmpeg", "-i", video_path,
        "-af", pan_filter,
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        "-y", output_path
    ]
    if duration:
        cmd.insert(4, "-t")
        cmd.insert(5, str(int(duration)))

    print(f"提取{channel}声道 -> {output_path}")
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def transcribe_with_whisper(audio_path: str, speaker_label: str, model_size: str = "base") -> List[Dict[str, Any]]:
    """使用Whisper转录，返回带时间戳的句子列表"""
    print(f"转录 {speaker_label} 声道: {audio_path}")

    try:
        from faster_whisper import WhisperModel

        device = "cpu"
        compute_type = "int8"

        print(f"加载Whisper模型 {model_size} (device={device}, compute_type={compute_type})...")
        model = WhisperModel(model_size, device=device, compute_type=compute_type)

        print("开始转录...")
        segments, info = model.transcribe(
            audio_path,
            language='zh',
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        result = []
        for seg in segments:
            text = seg.text.strip()
            if text:
                result.append({
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": text,
                    "speaker": speaker_label
                })

        print(f"  获取 {len(result)} 个句子片段")
        del model
        gc.collect()
        return result

    except Exception as e:
        print(f"转录失败: {e}")
        return []


def merge_segments(left_segments: List, right_segments: List, threshold: float = 0.5) -> List:
    """
    合并左右声道，去除重复内容

    策略：当两个声道在同一时间段都有内容时，比较文本相似度
    如果高度相似，只保留音量更高的那个声道（假设更近的麦克风音量更大）
    """
    all_segments = []

    # 按时间排序
    left_sorted = sorted(left_segments, key=lambda x: x["start"])
    right_sorted = sorted(right_segments, key=lambda x: x["start"])

    # 简单合并策略：保留所有片段，后续可以通过相似度去重
    for seg in left_sorted:
        seg["speaker"] = "于传奇"  # 假设左声道是于传奇
        all_segments.append(seg)

    for seg in right_sorted:
        seg["speaker"] = "宋瑞"  # 假设右声道是宋瑞
        all_segments.append(seg)

    # 按开始时间排序
    all_segments.sort(key=lambda x: x["start"])

    return all_segments


def format_timestamp(seconds: float) -> str:
    """将秒数转换为SRT时间格式"""
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds:03d}"


def export_srt(segments: List[Dict], output_path: str):
    """导出SRT字幕文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            start = format_timestamp(seg["start"])
            end = format_timestamp(seg["end"])
            speaker = seg.get("speaker", "")
            text = seg["text"]

            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            if speaker:
                f.write(f"[{speaker}] {text}\n")
            else:
                f.write(f"{text}\n")
            f.write("\n")

    print(f"SRT字幕已保存: {output_path}")


def export_json(segments: List[Dict], output_path: str, video_path: str, duration: float):
    """导出JSON格式的转录结果"""
    output_data = {
        "video_path": video_path,
        "duration": duration,
        "total_segments": len(segments),
        "segments": segments
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"JSON已保存: {output_path}")


def main():
    video_path = "D:/boke/20260418/C0257.MP4"
    output_dir = "D:/boke/20260418"
    output_json = os.path.join(output_dir, "C0257_full_transcription.json")
    output_srt = os.path.join(output_dir, "C0257_full_subtitles.srt")

    print("=" * 60)
    print("全量视频声道分离转录")
    print("=" * 60)

    # 获取视频时长
    duration = get_video_duration(video_path)
    print(f"视频时长: {duration:.1f}秒 ({duration/60:.1f}分钟)")

    # 提取声道
    left_path = os.path.join(output_dir, "left_channel_full.wav")
    right_path = os.path.join(output_dir, "right_channel_full.wav")

    if not os.path.exists(left_path):
        extract_channel(video_path, left_path, "left")
    else:
        print(f"左声道已存在: {left_path}")

    if not os.path.exists(right_path):
        extract_channel(video_path, right_path, "right")
    else:
        print(f"右声道已存在: {right_path}")

    # 转录左声道
    print("\n" + "=" * 60)
    print("转录左声道...")
    print("=" * 60)
    left_segments = transcribe_with_whisper(left_path, "于传奇", model_size="base")

    # 转录右声道
    print("\n" + "=" * 60)
    print("转录右声道...")
    print("=" * 60)
    right_segments = transcribe_with_whisper(right_path, "宋瑞", model_size="base")

    # 合并结果
    print("\n" + "=" * 60)
    print("合并声道...")
    print("=" * 60)
    all_segments = merge_segments(left_segments, right_segments)

    print(f"左声道: {len(left_segments)} 片段")
    print(f"右声道: {len(right_segments)} 片段")
    print(f"合并后: {len(all_segments)} 片段")

    # 导出结果
    export_json(all_segments, output_json, video_path, duration)
    export_srt(all_segments, output_srt)

    # 显示前20个片段
    print("\n前20个片段预览:")
    print("-" * 60)
    for i, seg in enumerate(all_segments[:20]):
        time_str = f"[{seg['start']:.2f}s - {seg['end']:.2f}s]"
        print(f"{i+1}. {time_str} [{seg['speaker']}]: {seg['text'][:50]}...")


if __name__ == "__main__":
    main()