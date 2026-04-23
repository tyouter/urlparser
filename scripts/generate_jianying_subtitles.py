"""
生成剪映兼容的字幕文件

剪映支持SRT格式导入，也可以使用剪映专用的JSON格式。
"""

import json
import os
from datetime import timedelta
from typing import List, Dict


def format_timestamp_srt(seconds: float) -> str:
    """SRT时间格式: HH:MM:SS,mmm"""
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds:03d}"


def deduplicate_segments(segments: List[Dict], threshold: float = 1.0) -> List[Dict]:
    """
    去重左右声道的重复内容

    当两个声道在同一时间段有高度相似的文本时，只保留一个
    """
    deduped = []

    for i, seg in enumerate(segments):
        # 检查是否有时间重叠且文本相似的片段
        is_duplicate = False
        for existing in deduped:
            # 时间重叠检查
            time_overlap = (
                seg["start"] < existing["end"] + threshold and
                seg["end"] > existing["start"] - threshold
            )
            # 文本相似度检查（简单：包含关系或相同）
            text_similar = (
                seg["text"] in existing["text"] or
                existing["text"] in seg["text"] or
                seg["text"] == existing["text"]
            )
            if time_overlap and text_similar:
                is_duplicate = True
                break

        if not is_duplicate:
            deduped.append(seg)

    return deduped


def generate_srt(segments: List[Dict], output_path: str, include_speaker: bool = True):
    """生成SRT字幕文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            start = format_timestamp_srt(seg["start"])
            end = format_timestamp_srt(seg["end"])
            speaker = seg.get("speaker", "")
            text = seg["text"]

            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            if include_speaker and speaker:
                f.write(f"[{speaker}] {text}\n")
            else:
                f.write(f"{text}\n")
            f.write("\n")

    print(f"SRT文件已生成: {output_path}")
    print(f"共 {len(segments)} 条字幕")


def generate_jianying_json(segments: List[Dict], output_path: str):
    """
    生成剪映草稿JSON格式

    剪映的draft_content.json结构复杂，这里生成简化版本供参考
    """
    jianying_data = {
        "tracks": [
            {
                "type": "text",
                "segments": []
            }
        ]
    }

    for seg in segments:
        # 剪映使用毫秒作为时间单位
        start_ms = int(seg["start"] * 1000)
        end_ms = int(seg["end"] * 1000)
        duration_ms = end_ms - start_ms

        jianying_data["tracks"][0]["segments"].append({
            "material": {
                "content": seg["text"],
                "duration": duration_ms
            },
            "target_timerange": {
                "start": start_ms,
                "duration": duration_ms
            }
        })

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(jianying_data, f, ensure_ascii=False, indent=2)

    print(f"剪映JSON格式已生成: {output_path}")


def main():
    # 输入文件
    input_json = "D:/boke/20260418/C0257_5min_timestamps.json"

    # 输出文件
    output_dir = "D:/boke/20260418"
    output_srt = os.path.join(output_dir, "C0257_5min_subtitles.srt")
    output_srt_no_speaker = os.path.join(output_dir, "C0257_5min_subtitles_clean.srt")
    output_jianying = os.path.join(output_dir, "C0257_5min_jianying.json")

    # 读取数据
    with open(input_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    segments = data["segments"]
    print(f"原始数据: {len(segments)} 条")

    # 去重
    deduped = deduplicate_segments(segments)
    print(f"去重后: {len(deduped)} 条")

    # 按时间排序
    deduped.sort(key=lambda x: x["start"])

    # 生成SRT（带说话人标记）
    generate_srt(deduped, output_srt, include_speaker=True)

    # 生成SRT（不带说话人标记，更简洁）
    generate_srt(deduped, output_srt_no_speaker, include_speaker=False)

    # 生成剪映JSON
    generate_jianying_json(deduped, output_jianying)

    # 显示前10条字幕
    print("\n前10条字幕预览:")
    print("-" * 60)
    for i, seg in enumerate(deduped[:10]):
        time_str = f"[{seg['start']:.2f}s - {seg['end']:.2f}s]"
        print(f"{i+1}. {time_str} {seg['text']}")


if __name__ == "__main__":
    main()