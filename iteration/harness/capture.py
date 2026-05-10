"""
Harness Gate Script: capture parse output for test URLs.

Usage:
    python iteration/harness/capture.py --output-dir iteration/harness/baseline
    python iteration/harness/capture.py --output-dir iteration/harness/after

Expected environment:
    - urlparser installed (pip install -e .)
    - Playwright browsers installed
    - KMP_DUPLICATE_LIB_OK=TRUE (Windows)
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Ensure urlparser is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from urlparser import parse, ParseConfig

# ============================================================
# Test URL Set: 10 generic webpages + 3 known-platform controls
# ============================================================
GENERIC_URLS = [
    # News
    ("36kr_news", "https://36kr.com/p/3214567890123456"),
    ("bbc_future", "https://www.bbc.com/future/article/20240101-the-hidden-cost-of-our-digital-lives"),
    # Blogs
    ("devto_blog", "https://dev.to/lydiahallie/javascript-visualized-event-loop-3dif"),
    # Docs / tutorials
    ("python_docs", "https://docs.python.org/3/tutorial/classes.html"),
    ("mdn_js", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Functions"),
    # Long-form
    ("wiki_ai", "https://en.wikipedia.org/wiki/Artificial_intelligence"),
    ("arxiv_abs", "https://arxiv.org/abs/1706.03762"),
    # Mixed / complex layouts
    ("github_readme", "https://github.com/psf/requests"),
    ("medium_blog", "https://medium.com/towards-data-science/a-beginners-guide-to-natural-language-processing-8dc045ddb7f6"),
    ("stackoverflow", "https://stackoverflow.com/questions/11227809/why-is-processing-a-sorted-array-faster-than-processing-an-unsorted-array"),
]

KNOWN_PLATFORM_URLS = [
    # Regression controls — must be unchanged after the patch
    ("bilibili_ctrl", "https://www.bilibili.com/video/BV1GJ411x7h7"),
    ("zhihu_ctrl", "https://www.zhihu.com/question/19550225"),
    ("weixin_ctrl", "https://mp.weixin.qq.com/s/CS0L-Z5NGqKoFqrhAJMv2g"),
]

ALL_URLS = GENERIC_URLS + KNOWN_PLATFORM_URLS


async def capture_one(name: str, url: str) -> dict:
    """Parse a single URL and return structured result."""
    start = time.time()
    try:
        config = ParseConfig.simple()
        result = await parse(url, config=config)
        elapsed = round(time.time() - start, 2)
        return {
            "name": name,
            "url": url,
            "success": result.fetch_success,
            "platform": result.platform,
            "title": result.title[:200] if result.title else "",
            "content_length": len(result.content or ""),
            "raw_text_length": len(result.raw_text or ""),
            "content": result.content or "",
            "raw_text": result.raw_text or "",
            "error": result.error,
            "parse_time": elapsed,
        }
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        return {
            "name": name,
            "url": url,
            "success": False,
            "error": str(e),
            "parse_time": elapsed,
        }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, help="Directory to save captured outputs")
    parser.add_argument("--timeout", type=int, default=30, help="Per-URL timeout in seconds")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {"captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "urls": {}}

    for name, url in ALL_URLS:
        print(f"[capture] {name}: {url[:80]}...", end=" ", flush=True)
        try:
            result = await asyncio.wait_for(capture_one(name, url), timeout=args.timeout)
        except asyncio.TimeoutError:
            result = {"name": name, "url": url, "success": False, "error": "timeout"}

        status = "OK" if result["success"] else f"FAIL ({result.get('error', 'unknown')[:50]})"
        print(f"{status} | content: {result.get('content_length', 0)} chars | {result.get('parse_time', 0)}s")

        # Save individual content file
        content_file = out_dir / f"{name}.md"
        content_file.write_text(result.get("content", "") or "", encoding="utf-8")

        # Save metadata JSON
        meta = {k: v for k, v in result.items() if k != "content"}
        meta_file = out_dir / f"{name}.json"
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        summary["urls"][name] = meta

    # Write summary
    summary_path = out_dir / "_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[capture] Done. Summary: {summary_path}")


if __name__ == "__main__":
    asyncio.run(main())
