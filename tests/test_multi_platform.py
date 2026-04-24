import os
import sys
import time
import json
import asyncio
import re

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

OUTPUT_DIR = r"D:\projects\claude\urlparser\tests\multi_platform"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TEST_URLS = [
    {
        "platform": "bilibili",
        "name": "爆肝5小时实测国产大模型横评",
        "url": "https://www.bilibili.com/video/BV1KBZkB6EJF",
        "type": "video",
    },
    {
        "platform": "bilibili",
        "name": "ObsidianCLI+ClaudeCode笔记工作流",
        "url": "https://www.bilibili.com/video/BV1qNAqzxETr",
        "type": "video",
    },
    {
        "platform": "bilibili",
        "name": "开源Figma-AI原生设计编辑器OpenPencil",
        "url": "https://www.bilibili.com/video/BV19aPHzyEs5",
        "type": "video",
    },
    {
        "platform": "zhihu",
        "name": "claude.md怎么写才能让Claude Code更高效",
        "url": "https://www.zhihu.com/answer/2009429788666909340",
        "type": "article",
    },
    {
        "platform": "zhihu",
        "name": "普通人第一次用OpenClaw应该注意什么",
        "url": "https://www.zhihu.com/answer/2010009329542140927",
        "type": "article",
    },
    {
        "platform": "zhihu",
        "name": "最难调试修复的bug是怎样的",
        "url": "https://www.zhihu.com/answer/2012245758137631858",
        "type": "article",
    },
    {
        "platform": "weixin",
        "name": "龙虾越火越应该研究Skill",
        "url": "https://mp.weixin.qq.com/s/mpoOI3gAiVd9I-uuzSgxAw",
        "type": "article",
    },
    {
        "platform": "weixin",
        "name": "微信公众号文章2",
        "url": "https://mp.weixin.qq.com/s/KwKIHo59YeYhvtZloz1CPA",
        "type": "article",
    },
    {
        "platform": "zhihu_zhuanlan",
        "name": "知乎专栏-PlaywrightCLI隐藏技能",
        "url": "https://zhuanlan.zhihu.com/p/2012158056595727644",
        "type": "article",
    },
]

results = []


async def fetch_metadata(fetcher, item):
    platform = item["platform"]
    name = item["name"]
    url = item["url"]

    print(f"\n{'='*60}")
    print(f"[FETCH] [{platform}] {name}")

    t0 = time.time()
    result = await fetcher.fetch(url)
    elapsed = round(time.time() - t0, 2)

    status = "PASS" if result.success else "FAIL"
    print(f"  Status: {status} ({elapsed}s)")
    if result.success:
        print(f"  Title: {result.title}")
        print(f"  Text: {len(result.text)} chars")
        meta = result.metadata
        if meta.get("bvid"):
            cid = meta.get("pages", [{}])[0].get("cid") if meta.get("pages") else None
            print(f"  BVID: {meta['bvid']}, Duration: {meta.get('duration')}s, CID: {cid}")
        if meta.get("bb_method"):
            print(f"  Method: {meta['bb_method']}")
    else:
        print(f"  Error: {result.error}")

    return {
        "platform": platform,
        "name": name,
        "url": url,
        "type": item["type"],
        "fetch_status": status,
        "fetch_elapsed": elapsed,
        "title": result.title,
        "text_length": len(result.text) if result.text else 0,
        "error": result.error,
        "metadata": {k: v for k, v in result.metadata.items() if k != 'raw_data'},
    }


async def download_and_transcribe(fetcher, item):
    platform = item["platform"]
    name = item["name"]
    meta = item.get("metadata", {})

    if item["type"] != "video":
        print(f"\n  [SKIP] {name} is not a video")
        item["transcription_status"] = "SKIP"
        return

    if item["fetch_status"] != "PASS":
        print(f"\n  [SKIP] {name} fetch failed")
        item["transcription_status"] = "SKIP"
        return

    bvid = meta.get("bvid")
    pages = meta.get("pages", [])
    if not bvid or not pages:
        print(f"\n  [SKIP] {name} no BVID/pages")
        item["transcription_status"] = "SKIP"
        return

    cid = pages[0].get("cid")
    if not cid:
        print(f"\n  [SKIP] {name} no CID")
        item["transcription_status"] = "SKIP"
        return

    print(f"\n{'='*60}")
    print(f"[DOWNLOAD] [{platform}] {name} (BVID={bvid}, CID={cid})")

    safe_name = re.sub(r'[^\w]', '_', name)[:30]
    wav_path = os.path.join(OUTPUT_DIR, f"{platform}_{safe_name}.wav")

    t0 = time.time()
    success = await fetcher.download_bilibili_audio(bvid, cid, wav_path)
    dl_elapsed = round(time.time() - t0, 2)

    if not success:
        print(f"  Download FAILED ({dl_elapsed}s)")
        item["transcription_status"] = "FAIL"
        item["transcription_error"] = "Audio download failed"
        return

    wav_size_mb = os.path.getsize(wav_path) / 1024 / 1024
    print(f"  Download OK ({dl_elapsed}s, {wav_size_mb:.1f} MB)")

    print(f"\n[TRANSCRIBE] [{platform}] {name}")
    from urlparser.transcriber.funasr import FunASRTranscriber

    transcriber = FunASRTranscriber(device="auto")
    print(f"  Engine: FunASR, Device: {transcriber.device}")

    t0 = time.time()
    try:
        result = transcriber.transcribe(wav_path, language="zh")
        trans_elapsed = round(time.time() - t0, 2)

        if result.success:
            text_len = len(result.text)
            print(f"  Transcription OK ({trans_elapsed}s, {text_len} chars)")

            output_path = os.path.join(OUTPUT_DIR, f"{platform}_{safe_name}_transcription.md")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"# {name} - 转录\n\n")
                f.write(f"> Platform: {platform}\n")
                f.write(f"> BVID: {bvid}\n")
                f.write(f"> Engine: FunASR (SenseVoice)\n")
                f.write(f"> Device: {transcriber.device}\n")
                f.write(f"> Download: {dl_elapsed}s\n")
                f.write(f"> Transcription: {trans_elapsed}s\n")
                f.write(f"> Text: {text_len} chars\n")
                f.write(f"> WAV: {wav_size_mb:.1f} MB\n\n")
                f.write(f"## 转录文本\n\n{result.text}\n")
            print(f"  Output: {output_path}")

            item["transcription_status"] = "PASS"
            item["transcription_elapsed"] = trans_elapsed
            item["transcription_text_length"] = text_len
            item["wav_size_mb"] = wav_size_mb
        else:
            print(f"  Transcription FAILED: {result.error}")
            item["transcription_status"] = "FAIL"
            item["transcription_error"] = result.error

    except Exception as e:
        trans_elapsed = round(time.time() - t0, 2)
        print(f"  Transcription ERROR ({trans_elapsed}s): {e}")
        item["transcription_status"] = "FAIL"
        item["transcription_error"] = str(e)

    if os.path.exists(wav_path):
        os.unlink(wav_path)


async def save_text_content(fetcher, item):
    if item["type"] == "video":
        return
    if item["fetch_status"] != "PASS":
        return

    platform = item["platform"]
    name = item["name"]
    title = item.get("title", name)

    safe_name = re.sub(r'[^\w]', '_', name)[:30]
    output_path = os.path.join(OUTPUT_DIR, f"{platform}_{safe_name}.md")

    result = await fetcher.fetch(item["url"])

    if result.success and result.text:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(f"> Platform: {platform}\n")
            f.write(f"> URL: {item['url']}\n")
            f.write(f"> Strategy: bb-browser\n")
            method = result.metadata.get("bb_method", "adapter")
            f.write(f"> Method: {method}\n\n")
            f.write(f"## Content\n\n{result.text}\n")
        print(f"  Text saved: {output_path} ({len(result.text)} chars)")
        item["text_saved"] = True
        item["saved_text_length"] = len(result.text)
    else:
        print(f"  Text save FAILED: {result.error}")
        item["text_saved"] = False


async def main():
    print("=" * 60)
    print("Multi-Platform Test with bb-browser Integration")
    print("=" * 60)

    from urlparser.fetcher.bb_browser_fetcher import BbBrowserFetcher
    fetcher = BbBrowserFetcher()
    print(f"bb-browser available: {fetcher._check_bb_browser()}")

    for item in TEST_URLS:
        r = await fetch_metadata(fetcher, item)
        results.append(r)

    for item in results:
        await download_and_transcribe(fetcher, item)

    for item in results:
        await save_text_content(fetcher, item)

    report_path = os.path.join(OUTPUT_DIR, "test_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Multi-Platform Transcription Test Report\n\n")
        f.write("> Date: 2026-04-23\n")
        f.write("> Strategy: bb-browser (CDP) + FunASR\n")
        f.write("> Key: bb-browser fetch bypasses Bilibili 412\n\n")

        f.write("## Results\n\n")
        f.write("| # | Platform | Name | Type | Fetch | Transcribe | Text Length |\n")
        f.write("|---|----------|------|------|-------|------------|-------------|\n")
        for i, r in enumerate(results, 1):
            ts = r.get("transcription_status", "N/A")
            tl = r.get("transcription_text_length", r.get("saved_text_length", r.get("text_length", "-")))
            f.write(f"| {i} | {r['platform']} | {r['name'][:25]} | {r['type']} | {r['fetch_status']} | {ts} | {tl} |\n")

        f.write("\n## Summary\n\n")
        fetch_pass = sum(1 for r in results if r["fetch_status"] == "PASS")
        trans_pass = sum(1 for r in results if r.get("transcription_status") == "PASS")
        text_pass = sum(1 for r in results if r.get("text_saved") or r.get("transcription_status") == "PASS")
        f.write(f"- Fetch: {fetch_pass}/{len(results)} PASS\n")
        f.write(f"- Transcription (video): {trans_pass} PASS\n")
        f.write(f"- Content saved (article): {text_pass} PASS\n")

        f.write("\n## Completeness Verification\n\n")
        f.write("| # | Platform | Name | Type | Chars/Sec | Assessment |\n")
        f.write("|---|----------|------|------|-----------|------------|\n")
        for i, r in enumerate(results, 1):
            if r["type"] == "video" and r.get("transcription_status") == "PASS":
                wav_mb = r.get("wav_size_mb", 0)
                text_len = r.get("transcription_text_length", 0)
                if wav_mb > 0 and text_len > 0:
                    duration_sec = (wav_mb * 1024 * 1024) / 32000
                    chars_per_sec = text_len / duration_sec
                    assessment = "GOOD" if 2.5 <= chars_per_sec <= 8 else "SUSPICIOUS"
                    f.write(f"| {i} | {r['platform']} | {r['name'][:25]} | video | {chars_per_sec:.2f} | {assessment} |\n")
                else:
                    f.write(f"| {i} | {r['platform']} | {r['name'][:25]} | video | N/A | N/A |\n")
            elif r["type"] == "article" and r.get("text_saved"):
                text_len = r.get("saved_text_length", 0)
                assessment = "GOOD" if text_len >= 100 else "SHORT"
                f.write(f"| {i} | {r['platform']} | {r['name'][:25]} | article | {text_len} chars | {assessment} |\n")
            else:
                f.write(f"| {i} | {r['platform']} | {r['name'][:25]} | {r['type']} | N/A | SKIP |\n")

        all_pass = fetch_pass == len(results) and text_pass == len(results)
        f.write(f"\n## Overall: {'ALL PASS' if all_pass else 'HAS FAILURES'}\n")

    print(f"\nReport: {report_path}")


asyncio.run(main())
