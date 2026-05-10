"""Quick parse & save for manual review of trafilatura results."""
import asyncio
import sys
sys.path.insert(0, r"D:\projects\claude\urlparser\src")

from urlparser import parse, ParseConfig
from pathlib import Path

OUT_DIR = Path(r"D:\projects\claude\urlparser\iteration\review_samples")
OUT_DIR.mkdir(parents=True, exist_ok=True)

URLS = [
    # bad_case: was 0.5KB navigation only → now 18/18
    ("difans", "https://www.difans.cn/post_byd_car/643.html"),
    # bad_case: dribbble
    ("dribbble_lumore", "https://dribbble.com/shots/26148325"),
    # general: porsche article
    ("porsche", "https://www.classicdriver.com/en/article/cars/tobias-suhlmann-follows-michael-mauer-porsches-new-head-design"),
    # general: feishu doc (perfect 18/18)
    ("feishu", "https://lcnziv86vkx6.feishu.cn/wiki/BOWXwqEL2iZKnFkbRBWcSq93nng"),
    # good_case: csdn (only good that worked)
    ("csdn", "https://blog.csdn.net/HeFlyYoung/article/details/124149314"),
    # good_case: cubox help
    ("cubox_help", "https://help.cubox.pro/hi/8218"),
]

async def main():
    for name, url in URLS:
        print(f"[{name}] parsing {url[:70]}...", end=" ", flush=True)
        try:
            result = await asyncio.wait_for(parse(url, config=ParseConfig.simple()), timeout=60)
            if result.fetch_success:
                content = result.content or result.raw_text or ""
                path = OUT_DIR / f"{name}.md"
                # Write full markdown with metadata header
                header = f"# {result.title or name}\n\n"
                header += f"> **来源**: {url}\n"
                header += f"> **平台**: {result.platform} | **策略**: {result.final_strategy}\n"
                header += f"> **内容长度**: {len(content)} chars\n\n"
                header += "---\n\n"
                path.write_text(header + content, encoding="utf-8")
                preview = content[:120].replace("\n", " ")
                print(f"OK | {len(content)} chars | preview: {preview}...")
                print(f"  Saved: {path}")
            else:
                print(f"FAIL: {result.error}")
        except asyncio.TimeoutError:
            print("TIMEOUT")
        except Exception as e:
            print(f"ERROR: {e}")

    print(f"\nAll samples saved to: {OUT_DIR}")

asyncio.run(main())
