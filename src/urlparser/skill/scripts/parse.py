#!/usr/bin/env python
"""
urlparser Skill 执行入口

Usage:
    python parse.py <url> [--output file] [--transcribe] [--cookies-file path]
    python parse.py --help
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="urlparser - 通用 URL 解析器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  parse.py https://www.zhihu.com/question/xxx
  parse.py https://www.bilibili.com/video/BVxxx --transcribe
  parse.py https://mp.weixin.qq.com/s/xxx --cookies-file cookies.json
  parse.py https://www.youtube.com/watch?v=xxx --output result.md
        """
    )

    parser.add_argument("url", help="要解析的 URL")
    parser.add_argument("--output", "-o", help="输出文件路径（默认打印到终端）")
    parser.add_argument("--format", "-f", choices=["markdown", "json"], default="markdown",
                        help="输出格式（默认 markdown）")
    parser.add_argument("--transcribe", "-t", action="store_true",
                        help="启用视频/音频转录")
    parser.add_argument("--cookies-file", "-c", help="Cookie 文件路径")
    parser.add_argument("--use-user-chrome", "-u", action="store_true",
                        help="使用用户 Chrome 浏览器状态")
    parser.add_argument("--no-cache", "-n", action="store_true",
                        help="跳过缓存，重新解析")
    parser.add_argument("--timeout", type=int, default=60000,
                        help="超时时间（毫秒，默认 60000）")
    parser.add_argument("--headless", action="store_true", default=True,
                        help="无头浏览器模式（默认启用）")
    parser.add_argument("--no-headless", action="store_false", dest="headless",
                        help="显示浏览器窗口")

    args = parser.parse_args()

    result = asyncio.run(_parse_url(args))

    if not result.fetch_success:
        print(f"解析失败: {result.error}", file=sys.stderr)
        sys.exit(1)

    output = _format_output(result, args.format)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"已保存到: {args.output}")
    else:
        print(output)


async def _parse_url(args):
    """执行 URL 解析"""
    from urlparser import parse, ParseConfig
    from urlparser.config import BrowserConfig, TranscribeConfig

    config = ParseConfig(
        transcribe=TranscribeConfig(enabled=args.transcribe),
        browser=BrowserConfig(
            cookies_file=args.cookies_file,
            use_user_chrome=args.use_user_chrome,
            headless=args.headless,
            timeout=args.timeout,
        ),
    )

    return await parse(args.url, config=config)


def _format_output(result, format_type):
    """格式化输出"""
    if format_type == "json":
        data = {
            "url": result.url,
            "title": result.title,
            "content": result.content,
            "author": result.author,
            "platform": result.platform,
            "content_type": result.content_type.value if result.content_type else None,
            "fetch_success": result.fetch_success,
            "error": result.error,
            "parse_time": result.parse_time,
            "final_strategy": result.final_strategy,
            "metadata": result.metadata,
        }
        if result.video_metadata and result.video_metadata.duration:
            data["video_metadata"] = {
                "duration": result.video_metadata.duration,
                "views": result.video_metadata.views,
                "likes": result.video_metadata.likes,
                "coins": result.video_metadata.coins,
                "favorites": result.video_metadata.favorites,
            }
        if result.has_transcription:
            data["transcription"] = {
                "text": result.transcription.text,
                "engine": result.transcription.engine,
            }
        return json.dumps(data, ensure_ascii=False, indent=2)

    lines = [
        f"# {result.title or '无标题'}",
        "",
        f"**作者**: {result.author or '未知'}",
        f"**平台**: {result.platform or '未知'}",
        f"**URL**: {result.url}",
        f"**策略**: {result.final_strategy or '未知'}",
        f"**耗时**: {result.parse_time:.1f}s" if result.parse_time else "**耗时**: 未知",
        "",
        "---",
        "",
    ]

    if result.video_metadata and result.video_metadata.duration:
        lines.extend([
            "## 视频信息",
            "",
            f"- **时长**: {result.video_metadata.duration}",
            f"- **播放量**: {result.video_metadata.views}",
            f"- **点赞**: {result.video_metadata.likes}",
            f"- **投币**: {result.video_metadata.coins}",
            f"- **收藏**: {result.video_metadata.favorites}",
            "",
        ])

    lines.extend([
        "## 正文内容",
        "",
        result.content or "无内容",
        "",
    ])

    if result.has_transcription:
        lines.extend([
            "## 转录文本",
            "",
            result.transcription.text,
            "",
        ])

    return "\n".join(lines)


if __name__ == "__main__":
    main()
