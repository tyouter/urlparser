"""
时间轴写入器 - 生成视频理解 Markdown 报告
"""

from pathlib import Path
from typing import Optional
from datetime import datetime

from ..models import ComprehensionResult


class TimelineWriter:
    """生成时间轴 Markdown 报告和完整理解报告。"""

    @staticmethod
    def write_timeline(
        result: ComprehensionResult,
        video_title: str = "Untitled",
        url: str = ""
    ) -> Path:
        """
        生成时间轴 Markdown 文件。

        Args:
            result: 理解结果
            video_title: 视频标题
            url: 视频 URL

        Returns:
            输出文件路径
        """
        lines = []

        if video_title:
            lines.append(f"# {video_title}")
            lines.append("")

        lines.append(f"> **来源**: {url}")
        lines.append(f"> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"> **理解模式**: {result.mode}")
        lines.append(f"> **引擎**: {result.engine}")
        lines.append(f"> **关键帧数**: {result.frame_count}")
        lines.append("")

        if result.timeline_summary:
            lines.append("## 摘要")
            lines.append("")
            lines.append(result.timeline_summary)
            lines.append("")

        if result.visual_frames:
            lines.append("## 关键帧时间轴")
            lines.append("")
            for vf in result.visual_frames:
                h = int(vf.timestamp // 3600)
                m = int((vf.timestamp % 3600) // 60)
                s = int(vf.timestamp % 60)
                lines.append(f"### [{h:02d}:{m:02d}:{s:02d}]")
                lines.append("")
                lines.append(vf.description)
                lines.append("")

        if result.merged_text:
            lines.append("## 合并时间轴")
            lines.append("")
            lines.append(result.merged_text)
            lines.append("")

        if result.error:
            lines.append(f"## 错误")
            lines.append("")
            lines.append(result.error)
            lines.append("")

        output_path = Path(f"timeline_{video_title[:30]}.md")
        output_path.write_text('\n'.join(lines), encoding='utf-8')
        return output_path

    @staticmethod
    def write_merged_report(parse_result, output_path: Optional[str] = None) -> Path:
        """
        生成完整报告（元数据 + 内容 + 转录 + 理解）。

        Args:
            parse_result: ParseResult 对象
            output_path: 输出路径（可选）

        Returns:
            输出文件路径
        """
        if output_path:
            path = Path(output_path)
        else:
            title = getattr(parse_result, 'title', 'report')[:30]
            path = Path(f"report_{title}.md")

        path.write_text(parse_result.to_markdown(), encoding='utf-8')
        return path
