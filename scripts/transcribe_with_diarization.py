"""
转录并说话人分离

获取每句话的精确时间戳和说话人身份
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from urlparser.transcriber.funasr import FunASRTranscriber
from urlparser.utils.media_utils import get_media_duration, extract_audio_segment


def transcribe_with_timestamps(video_path: str, output_json: str):
    """转录并获取时间戳"""

    print(f"正在转录: {video_path}")
    print(f"输出到: {output_json}")

    # 创建转录器
    transcriber = FunASRTranscriber(model_size="large", device="cuda")

    # 获取时长
    duration = get_media_duration(video_path)
    print(f"视频时长: {duration:.1f} 秒 ({duration/60:.1f} 分钟)")

    # 转录
    result = transcriber.transcribe(video_path, language="zh")

    if not result.success:
        print(f"转录失败: {result.error}")
        return None

    print(f"转录成功，共 {len(result.segments)} 个句子片段")

    # 构建输出数据
    output_data = {
        "video_path": video_path,
        "duration": duration,
        "total_text": result.text,
        "segments": result.segments,  # 每句话的时间戳
        "engine": result.engine,
    }

    # 保存JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"已保存到: {output_json}")

    return output_data


def main():
    video_path = "D:/boke/20260418/C0257.MP4"
    output_json = "D:/boke/20260418/C0257_segments.json"

    transcribe_with_timestamps(video_path, output_json)


if __name__ == "__main__":
    main()