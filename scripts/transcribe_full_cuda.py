"""
使用CUDA转录完整混音音频 - 生成高质量字幕

使用Whisper large-v3 + CUDA，处理完整86分钟视频
"""

import os
import sys
import json
import gc
import subprocess
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def format_timestamp_srt(seconds: float) -> str:
    """SRT时间格式: HH:MM:SS,mmm"""
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds:03d}"


def transcribe_full_cuda(audio_path: str, model_size: str = "large-v3"):
    """使用CUDA转录完整音频"""
    print(f"转录音频: {audio_path}")

    from faster_whisper import WhisperModel

    print(f"加载Whisper {model_size} (CUDA, float16)...")
    model = WhisperModel(model_size, device="cuda", compute_type="float16")

    print("开始转录完整视频...")
    segments, info = model.transcribe(
        audio_path,
        language='zh',
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300)
    )

    result = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            result.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": text
            })

    print(f"获取 {len(result)} 个句子片段")

    del model
    gc.collect()
    return result


def merge_short_segments(segments, min_duration=1.0):
    """合并过短的片段"""
    merged = []
    current = None

    for seg in segments:
        if current is None:
            current = seg.copy()
        else:
            gap = seg["start"] - current["end"]
            current_duration = current["end"] - current["start"]

            if current_duration < min_duration and gap < 0.5:
                current["end"] = seg["end"]
                current["text"] += " " + seg["text"]
            else:
                merged.append(current)
                current = seg.copy()

    if current:
        merged.append(current)

    return merged


def generate_srt(segments, output_path):
    """生成SRT字幕"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            start = format_timestamp_srt(seg["start"])
            end = format_timestamp_srt(seg["end"])
            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{seg['text']}\n")
            f.write("\n")
    print(f"SRT已保存: {output_path} ({len(segments)} 条)")


def main():
    audio_path = "D:/boke/20260418/C0257_mixed_normalized.wav"
    output_dir = "D:/boke/20260418"
    output_srt = os.path.join(output_dir, "C0257_full_mixed.srt")
    output_json = os.path.join(output_dir, "C0257_full_mixed.json")

    print("=" * 60)
    print("CUDA转录完整混音音频")
    print("=" * 60)

    # 转录
    segments = transcribe_full_cuda(audio_path, model_size="large-v3")

    # 合并短片段
    segments = merge_short_segments(segments, min_duration=1.0)

    # 生成SRT
    generate_srt(segments, output_srt)

    # 保存JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump({
            "segments": segments,
            "total": len(segments)
        }, f, ensure_ascii=False, indent=2)
    print(f"JSON已保存: {output_json}")

    # 预览
    print("\n前15条字幕:")
    print("-" * 60)
    for i, seg in enumerate(segments[:15]):
        print(f"{i+1}. [{seg['start']:.1f}s-{seg['end']:.1f}s] {seg['text']}")

    print("\n最后5条字幕:")
    print("-" * 60)
    for i, seg in enumerate(segments[-5:], len(segments)-4):
        print(f"{i}. [{seg['start']:.1f}s-{seg['end']:.1f}s] {seg['text']}")


if __name__ == "__main__":
    main()