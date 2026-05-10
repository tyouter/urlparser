"""
Badcase Benchmark v2: evaluate trafilatura impact on 50 generic-webpage degraded docs.

All 50 are generic (non-video) webpages — trafilatura applies to all.
Measures size distribution shift (not per-doc quality).

Usage:
    python iteration/harness/badcase_bench.py
"""
import asyncio
import re
import sys
import time
from pathlib import Path
from dataclasses import dataclass

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from urlparser import parse, ParseConfig

BENCH_DIR = REPO_ROOT / "output" / "urlparser testcases" / "badcase_benchmark"


@dataclass
class Entry:
    filename: str
    url: str
    platform: str
    baseline_len: int


def scan_files() -> list[Entry]:
    entries = []
    for f in sorted(BENCH_DIR.glob("badcase_*.md")):
        text = f.read_text(encoding="utf-8")

        # Strategy 1: standard format "> **来源**: URL"
        url_m = re.search(r'> \*\*来源\*\*: (https?://\S+)', text)
        plat_m = re.search(r'> \*\*平台\*\*: (\S+)', text)

        if url_m:
            url = url_m.group(1)
            platform = plat_m.group(1) if plat_m else "unknown"
        else:
            # Strategy 2: try to find URL in body text
            url_m2 = re.search(r'https?://[^\s\n"\'\)]+', text)
            if url_m2:
                url = url_m2.group(0).rstrip('.,;:')
                platform = "default"  # assume generic
            else:
                print(f"  SKIP {f.name}: no URL found")
                continue

        # Extract baseline content
        content_m = re.search(r'## 内容摘要\s*\n(.*?)(?=\n## |\n---|\Z)', text, re.DOTALL)
        if not content_m:
            content_m = re.search(r'## 内容\s*\n(.*?)(?=\n## |\n---|\Z)', text, re.DOTALL)
        baseline = content_m.group(1).strip() if content_m else text

        entries.append(Entry(f.name, url, platform, len(baseline)))

    return entries


async def main():
    print("=" * 70)
    print("Badcase Benchmark v2 — 50 generic-webpage degraded docs")
    print("=" * 70)
    print()

    entries = scan_files()
    print(f"Scanned {len(entries)} files with URLs\n")

    results = []       # (entry, after_len, error)
    fetch_errors = 0

    for i, e in enumerate(entries, 1):
        print(f"[{i:2d}/{len(entries)}] {e.filename}: {e.url[:70]}...", end=" ", flush=True)
        try:
            result = await asyncio.wait_for(
                parse(e.url, config=ParseConfig.simple()), timeout=60
            )
        except asyncio.TimeoutError:
            print("TIMEOUT")
            fetch_errors += 1
            results.append((e, 0, "timeout"))
            continue

        if not result.fetch_success:
            print(f"FETCH FAIL: {(result.error or 'unknown')[:45]}")
            fetch_errors += 1
            results.append((e, 0, result.error or "fetch failed"))
            continue

        after_len = len((result.content or result.raw_text or "").strip())
        delta = after_len - e.baseline_len
        sign = "+" if delta >= 0 else ""
        ratio = f"{after_len/e.baseline_len:.1f}x" if e.baseline_len > 0 else "new"
        mark = " <<<" if after_len >= 1024 and e.baseline_len < 1024 else ""
        print(f"{after_len:>6}B | {sign}{delta:+d} ({ratio}){mark}")
        results.append((e, after_len, None))

    elapsed = 0  # approximate
    total_before = sum(e.baseline_len for e in entries)
    total_after = sum(al for _, al, _ in results)

    # ---- Size bracket distribution ----
    brackets = [(0, 1024), (1024, 3072), (3072, 5120), (5120, 10240), (10240, 999999)]
    before_dist = {b: 0 for b in brackets}
    after_dist = {b: 0 for b in brackets}
    for e in entries:
        for lo, hi in brackets:
            if lo <= e.baseline_len < hi:
                before_dist[(lo, hi)] += 1
                break
    for _, al, _ in results:
        for lo, hi in brackets:
            if lo <= al < hi:
                after_dist[(lo, hi)] += 1
                break

    print("\n" + "=" * 75)
    print("SIZE DISTRIBUTION SHIFT")
    print("=" * 75)
    print(f"{'Bracket':<15} {'Before':>8} {'After':>8} {'Change':>8}")
    print("-" * 75)
    for lo, hi in brackets:
        label = f"<1KB" if hi == 1024 else f"{lo//1024}-{hi//1024}KB" if hi < 999999 else f"{lo//1024}KB+"
        b = before_dist[(lo, hi)]
        a = after_dist[(lo, hi)]
        ch = f"+{a-b}" if a >= b else f"{a-b}"
        print(f"{label:<15} {b:>8} {a:>8} {ch:>8}")

    # ---- Bar chart ----
    print(f"\n{'Before':>8}: ", end="")
    for lo, hi in brackets:
        label = "<1K" if hi == 1024 else f"{lo//1024}-{hi//1024}K"
        bar = "█" * before_dist[(lo, hi)]
        print(f"{label}:{bar} {before_dist[(lo, hi)]}  ", end="")
    print(f"\n{'After':>8}: ", end="")
    for lo, hi in brackets:
        label = "<1K" if hi == 1024 else f"{lo//1024}-{hi//1024}K"
        bar = "█" * after_dist[(lo, hi)]
        print(f"{label}:{bar} {after_dist[(lo, hi)]}  ", end="")
    print()

    # ---- Key metrics ----
    print("\n" + "=" * 70)
    print("KEY METRICS (per README)")
    print("=" * 70)

    before_under1k = before_dist[(0, 1024)]
    after_under1k = after_dist[(0, 1024)]
    print(f"\n1. 完全失败率 (<1KB):    {before_under1k}/50 = {before_under1k/50*100:.0f}%  ->  {after_under1k}/50 = {after_under1k/50*100:.0f}%  (target: <20%)")

    before_under3k = before_dist[(0, 1024)] + before_dist[(1024, 3072)]
    after_under3k = after_dist[(0, 1024)] + after_dist[(1024, 3072)]
    print(f"2. 严重残缺率 (<3KB):    {before_under3k}/50 = {before_under3k/50*100:.0f}%  ->  {after_under3k}/50 = {after_under3k/50*100:.0f}%  (target: <50%)")

    avg_before = total_before / max(len(entries), 1)
    avg_after = total_after / max(len(entries), 1)
    ratio_all = total_after / total_before if total_before > 0 else 0
    print(f"3. 平均内容量:           {avg_before/1024:.1f}KB  ->  {avg_after/1024:.1f}KB  ({ratio_all:.1f}x)  (target: >=2x)")

    zero_to_one = sum(1 for e, al, _ in results if e.baseline_len < 1024 and al >= 1024)
    print(f"4. 零到一率 (<1KB->>1KB): {zero_to_one}/{before_under1k}  (target: >= {before_under1k//2})")

    print(f"\n5. Fetch errors: {fetch_errors}/{len(entries)}")
    print(f"   (timeouts/404s/blocked pages cannot be improved by trafilatura)")


if __name__ == "__main__":
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    asyncio.run(main())
