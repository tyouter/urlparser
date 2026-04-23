"""
使用混音版本生成字幕

从混音音频转录，生成单行、去重的字幕文件
"""

import os
import sys
import json
import gc
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _check_cuda():
    """检查CUDA是否可用"""
    try:
        import torch
        return torch.cuda.is_available()
    except:
        return False


def format_timestamp_srt(seconds: float) -> str:
    """SRT时间格式: HH:MM:SS,mmm"""
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds:03d}"


def transcribe_mixed(audio_path: str, model_size: str = "large-v3"):
    """使用Whisper转录混音音频"""
    print(f"转录混音音频: {audio_path}")

    from faster_whisper import WhisperModel

    device = "cuda" if _check_cuda() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"

    print(f"加载Whisper {model_size} (device={device}, compute_type={compute_type})...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    print("开始转录...")
    segments, info = model.transcribe(
        audio_path,
        language='zh',
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300)  # 更短的静音检测，获得更多断句
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


def generate_srt(segments, output_path):
    """生成简洁的SRT字幕（单行，无说话人标记）"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            start = format_timestamp_srt(seg["start"])
            end = format_timestamp_srt(seg["end"])

            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{seg['text']}\n")
            f.write("\n")

    print(f"SRT已保存: {output_path} ({len(segments)} 条)")


def merge_short_segments(segments, min_duration=1.5):
    """合并过短的片段，保证字幕可读性"""
    merged = []
    current = None

    for seg in segments:
        if current is None:
            current = seg.copy()
        else:
            # 如果当前片段太短，且与下一个片段时间接近，合并
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


def main():
    audio_path = "D:/boke/20260418/C0257_mixed_normalized.wav"
    output_dir = "D:/boke/20260418"

    # 5分钟测试
    test_duration = 300
    test_audio = os.path.join(output_dir, "mixed_5min.wav")

    # 提取5分钟测试音频
    if not os.path.exists(test_audio):
        import subprocess
        cmd = [
            "ffmpeg", "-i", audio_path,
            "-t", str(test_duration),
            "-c:a", "copy",
            "-y", test_audio
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        print(f"提取5分钟测试音频: {test_audio}")

    # 转录
    print("\n转录5分钟混音音频...")
    segments = transcribe_mixed(test_audio, model_size="base")

    # 合并短片段
    segments = merge_short_segments(segments, min_duration=1.0)

    # 生成SRT
    output_srt = os.path.join(output_dir, "C0257_mixed_5min.srt")
    generate_srt(segments, output_srt)

    # 保存JSON
    output_json = os.path.join(output_dir, "C0257_mixed_5min.json")
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump({
            "segments": segments,
            "total": len(segments)
        }, f, ensure_ascii=False, indent=2)
    print(f"JSON已保存: {output_json}")

    # 预览
    print("\n前20条字幕:")
    print("-" * 60)
    for i, seg in enumerate(segments[:20]):
        print(f"{i+1}. [{seg['start']:.1f}s-{seg['end']:.1f}s] {seg['text']}")


if __name__ == "__main__":
    main()