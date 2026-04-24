import asyncio
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from urlparser.fetcher.bb_browser_fetcher import BbBrowserFetcher

async def test():
    f = BbBrowserFetcher()
    print(f"bb-browser available: {f._check_bb_browser()}")

    urls = [
        ("Bilibili", "https://www.bilibili.com/video/BV1KBZkB6EJF"),
        ("Zhihu", "https://www.zhihu.com/answer/2009429788666909340"),
        ("Weixin", "https://mp.weixin.qq.com/s/mpoOI3gAiVd9I-uuzSgxAw"),
        ("Xiaohongshu", "https://www.xiaohongshu.com/login?redirectPath=https%3A%2F%2Fwww.xiaohongshu.com%2Fexplore%2F69a90d81000000001d026a45"),
    ]

    for name, url in urls:
        adapter_args = BbBrowserFetcher._extract_adapter_and_args(url)
        print(f"\n{name}: adapter={adapter_args}")

    print("\n--- Fetching Bilibili video ---")
    r = await f.fetch("https://www.bilibili.com/video/BV1KBZkB6EJF")
    print(f"Success: {r.success}")
    print(f"Title: {r.title}")
    print(f"Text length: {len(r.text)}")
    print(f"Error: {r.error}")
    print(f"Metadata: {r.metadata}")

asyncio.run(test())
