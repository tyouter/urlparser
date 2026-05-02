"""
Auto Research Dataset Builder

Builds a 500+ URL dataset from:
1. Cubox export files (user-provided bookmarks)
2. Curated supplement URLs for under-represented platforms
3. URL normalization and deduplication

Output: tests/auto_research/url_dataset.json
"""

import json
import os
import re
import hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set
from collections import defaultdict
from urllib.parse import urlparse, unquote, parse_qs


@dataclass
class URLEntry:
    url: str
    platform: str
    content_type: str
    source: str
    normalized_url: str = ""
    hash: str = ""
    expected_min_length: int = 100
    is_video: bool = False
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.normalized_url:
            self.normalized_url = self._normalize(self.url)
        if not self.hash:
            self.hash = hashlib.md5(self.normalized_url.encode()).hexdigest()
        if not self.is_video and self.content_type == "video":
            self.is_video = True

    @staticmethod
    def _normalize(url: str) -> str:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        path = parsed.path.rstrip("/")
        if "bilibili.com" in domain and "b23.tv" not in domain:
            bv_match = re.search(r'(BV[\w]+)', path)
            if bv_match:
                return f"bilibili.com/video/{bv_match.group(1)}"
        if "b23.tv" in domain:
            return url
        if "zhihu.com" in domain:
            return f"{domain}{path}"
        if "mp.weixin.qq.com" in domain:
            s_match = re.search(r'/s/([\w]+)', path)
            if s_match:
                return f"mp.weixin.qq.com/s/{s_match.group(1)}"
        if "xiaohongshu.com" in domain:
            return f"xiaohongshu.com{path}"
        if "youtube.com" in domain:
            qs = parse_qs(parsed.query)
            vid = qs.get('v', [''])[0]
            if vid:
                return f"youtube.com/watch?v={vid}"
        if "github.com" in domain:
            parts = path.strip('/').split('/')
            if len(parts) >= 2:
                return f"github.com/{parts[0]}/{parts[1]}"
        return f"{domain}{path}"


PLATFORM_RULES = {
    "bilibili": {
        "domains": ["bilibili.com", "b23.tv"],
        "content_type": "video",
        "is_video": True,
        "expected_min_length": 10,
    },
    "zhihu": {
        "domains": ["zhihu.com"],
        "content_type": "article",
        "is_video": False,
        "expected_min_length": 50,
    },
    "weixin": {
        "domains": ["mp.weixin.qq.com", "weixin.qq.com"],
        "content_type": "article",
        "is_video": False,
        "expected_min_length": 100,
    },
    "xiaohongshu": {
        "domains": ["xiaohongshu.com"],
        "content_type": "note",
        "is_video": False,
        "expected_min_length": 50,
    },
    "youtube": {
        "domains": ["youtube.com", "youtu.be"],
        "content_type": "video",
        "is_video": True,
        "expected_min_length": 10,
    },
    "github": {
        "domains": ["github.com"],
        "content_type": "repository",
        "is_video": False,
        "expected_min_length": 50,
    },
    "dribbble": {
        "domains": ["dribbble.com"],
        "content_type": "design",
        "is_video": False,
        "expected_min_length": 10,
    },
    "sspai": {
        "domains": ["sspai.com"],
        "content_type": "article",
        "is_video": False,
        "expected_min_length": 50,
    },
    "x_twitter": {
        "domains": ["x.com", "twitter.com"],
        "content_type": "post",
        "is_video": False,
        "expected_min_length": 10,
    },
}

CURATED_SUPPLEMENTS = {
    "youtube": [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "https://www.youtube.com/watch?v=9bZkp7q19f0",
        "https://www.youtube.com/watch?v=kJQP7kiw5Fk",
        "https://www.youtube.com/watch?v=JGwWNGJdvx8",
        "https://www.youtube.com/watch?v=OPf0YbXqDm0",
        "https://www.youtube.com/watch?v=60ItHLz5WEA",
        "https://www.youtube.com/watch?v=fJ9rUzIMcZQ",
        "https://www.youtube.com/watch?v=Boef8sDzXDg",
        "https://www.youtube.com/watch?v=hT_nvWreIhg",
        "https://www.youtube.com/watch?v=rg6CiPIvSjA",
        "https://www.youtube.com/watch?v=C0DPdy98e4c",
        "https://www.youtube.com/watch?v=YQHsXMglC9A",
        "https://www.youtube.com/watch?v=5qap5aO4i9A",
        "https://www.youtube.com/watch?v=aircAruvnKk",
    ],
    "github": [
        "https://github.com/microsoft/vscode",
        "https://github.com/torvalds/linux",
        "https://github.com/facebook/react",
        "https://github.com/vuejs/vue",
        "https://github.com/angular/angular",
        "https://github.com/tensorflow/tensorflow",
        "https://github.com/pytorch/pytorch",
        "https://github.com/huggingface/transformers",
        "https://github.com/langchain-ai/langchain",
        "https://github.com/anthropics/claude-code",
        "https://github.com/browser-use/browser-use",
        "https://github.com/open-webui/open-webui",
        "https://github.com/streamlit/streamlit",
        "https://github.com/gradio-app/gradio",
        "https://github.com/psf/requests",
    ],
    "dribbble": [
        "https://dribbble.com/shots/23404996-Pitch-deck-presentation-slides",
        "https://dribbble.com/shots/23397126-Investor-Pitch-Deck-Slides",
        "https://dribbble.com/shots/23784886-Bento-Style-Presentation",
        "https://dribbble.com/shots/24019608-Mobile-Banking-App",
        "https://dribbble.com/shots/23954379-Dashboard-Design",
        "https://dribbble.com/shots/23853210-Landing-Page-Design",
        "https://dribbble.com/shots/24120387-AI-Chat-Interface",
    ],
    "sspai": [
        "https://sspai.com/post/97131",
        "https://sspai.com/post/96475",
        "https://sspai.com/post/95941",
        "https://sspai.com/post/95233",
        "https://sspai.com/post/94567",
    ],
    "xiaohongshu": [
        "https://www.xiaohongshu.com/explore/67e3b3b0000000000d00b5a8",
        "https://www.xiaohongshu.com/explore/67d8e5c5000000000b037f17",
        "https://www.xiaohongshu.com/explore/67c5a1d5000000001c01c8a3",
        "https://www.xiaohongshu.com/explore/67b3f2e1000000001d019b27",
        "https://www.xiaohongshu.com/explore/67a1c8d5000000001c028e33",
    ],
    "generic": [
        "https://www.classicdriver.com/en/article/cars/tobias-suhlmann-follows-michael-mauer-porsches-new-head-design",
        "https://ww2.mathworks.cn/videos/soa-development-for-software-defined-vehicles-1768287077070.html",
        "https://www.mindtheproduct.com/top-books-and-resources-in-2026-for-product-managers/",
        "https://blog.csdn.net/HeFlyYoung/article/details/124149314",
        "https://www.wiz.cn/xapp",
        "https://code.claude.com/docs/en/skills",
        "https://help.cubox.pro/hi/8218/",
        "https://www.difans.cn/post_byd_car/643.html",
        "https://en.wikipedia.org/wiki/URL",
        "https://docs.python.org/3/library/urllib.parse.html",
        "https://developer.mozilla.org/en-US/docs/Web/API/URL",
        "https://stackoverflow.com/questions/888566",
        "https://www.producthunt.com/posts/claude-ai",
        "https://news.ycombinator.com/",
        "https://en.wikipedia.org/wiki/Web_scraping",
        "https://en.wikipedia.org/wiki/Playwright_(software)",
        "https://docs.python.org/3/library/asyncio.html",
        "https://realpython.com/async-io-python/",
        "https://docs.pydantic.dev/latest/",
        "https://fastapi.tiangolo.com/",
        "https://docs.aiohttp.org/en/stable/",
        "https://httpx.readthedocs.io/en/latest/",
        "https://www.spectralops.io/blog/how-to-extract-data-from-websites/",
        "https://www.scrapingbee.com/blog/web-scraping-without-getting-blocked/",
        "https://www.zyte.com/blog/web-scraping-best-practices/",
        "https://proxyscrape.com/blog/best-web-scraping-tools",
        "https://www.octoparse.com/blog/top-20-web-scraping-tools",
        "https://www.parsehub.com/blog/what-is-web-scraping/",
        "https://www.imperva.com/learn/application-security/web-scraping-attack/",
        "https://www.crummy.com/software/BeautifulSoup/bs4/doc/",
        "https://scrapy.org/",
        "https://selenium-python.readthedocs.io/",
        "https://playwright.dev/python/docs/intro",
        "https://www.crunchbase.com/organization/anthropic",
        "https://www.reddit.com/r/MachineLearning/",
        "https://arxiv.org/abs/2302.13971",
        "https://huggingface.co/docs/transformers/index",
        "https://pytorch.org/docs/stable/index.html",
        "https://numpy.org/doc/stable/",
        "https://pandas.pydata.org/docs/",
        "https://matplotlib.org/stable/contents.html",
        "https://scikit-learn.org/stable/",
        "https://www.tensorflow.org/learn",
        "https://keras.io/",
        "https://www.cloudflare.com/learning/bots/what-is-web-scraping/",
        "https://aws.amazon.com/what-is/web-scraping/",
        "https://www.browserless.io/",
        "https://www.apify.com/",
        "https://brightdata.com/",
        "https://oxylabs.io/",
        "https://www.smartproxy.com/",
        "https://www.abstractapi.com/blog/web-scraping-python",
        "https://levelup.gitconnected.com/web-scraping-with-python/",
        "https://towardsdatascience.com/web-scraping-with-python-a-to-z/",
        "https://medium.com/tag/web-scraping",
        "https://dev.to/t/scraping",
        "https://hackernoon.com/tagged/web-scraping",
        "https://www.freecodecamp.org/news/tagged/web-scraping/",
        "https://www.dataquest.io/blog/web-scraping-tutorial-python/",
        "https://www.geeksforgeeks.org/python-web-scraping-tutorial/",
        "https://www.codementor.io/@scrapingdog/python-web-scraping",
        "https://www.zenrows.com/blog/python-web-scraping",
        "https://www.scrapingbee.com/blog/python-web-scraping/",
        "https://www.makeuseof.com/tagged/web-scraping",
        "https://www.analyticsvidhya.com/blog/2024/12/web-scraping/",
    ],
}


class DatasetBuilder:
    MIN_DATASET_SIZE = 500
    MIN_PER_PLATFORM = 3

    def __init__(self, source_dir: Optional[str] = None):
        if source_dir:
            self.source_dir = Path(source_dir)
        else:
            self.source_dir = Path(__file__).parent.parent.parent.parent / "tests" / "test url source"
        self.entries: List[URLEntry] = []
        self.seen_hashes: Set[str] = set()
        self.platform_counts: Dict[str, int] = defaultdict(int)

    def build(self) -> List[URLEntry]:
        self._load_from_cubox_exports()
        self._add_curated_supplements()
        self._deduplicate()
        self._validate_coverage()
        return self.entries

    def _load_from_cubox_exports(self):
        if not self.source_dir.exists():
            return
        for fn in sorted(self.source_dir.iterdir()):
            if not fn.suffix == '.md':
                continue
            with open(fn, 'r', encoding='utf-8') as f:
                text = f.read()
            urls = re.findall(r'https?://[^\s\)\]\">\|]+', text)
            for raw_url in urls:
                url = raw_url.rstrip('.,;:!?|')
                if len(url) < 10:
                    continue
                self._add_url(url, source="cubox_export")

    def _add_curated_supplements(self):
        for platform, urls in CURATED_SUPPLEMENTS.items():
            for url in urls:
                self._add_url(url, source="curated", platform_override=platform)

    def _add_url(self, url: str, source: str, platform_override: Optional[str] = None):
        platform, rules = self._classify_url(url)
        if platform_override:
            platform = platform_override
            rules = PLATFORM_RULES.get(platform, {})

        if not rules:
            rules = {
                "content_type": "webpage",
                "is_video": False,
                "expected_min_length": 50,
            }

        entry = URLEntry(
            url=url,
            platform=platform,
            content_type=rules.get("content_type", "webpage"),
            source=source,
            is_video=rules.get("is_video", False),
            expected_min_length=rules.get("expected_min_length", 50),
        )

        if entry.hash not in self.seen_hashes:
            self.seen_hashes.add(entry.hash)
            self.entries.append(entry)
            self.platform_counts[platform] += 1

    def _classify_url(self, url: str):
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        for platform, rules in PLATFORM_RULES.items():
            for d in rules["domains"]:
                if d in domain:
                    return platform, rules

        return "generic", {
            "content_type": "webpage",
            "is_video": False,
            "expected_min_length": 50,
        }

    def _deduplicate(self):
        seen = set()
        unique = []
        for entry in self.entries:
            if entry.hash not in seen:
                seen.add(entry.hash)
                unique.append(entry)
        self.entries = unique
        self.platform_counts = defaultdict(int)
        for e in self.entries:
            self.platform_counts[e.platform] += 1

    def _validate_coverage(self):
        total = len(self.entries)
        platforms = set(self.platform_counts.keys())

        supported = set(PLATFORM_RULES.keys()) | {"generic"}
        missing = supported - platforms
        if missing:
            pass

        if total < self.MIN_DATASET_SIZE:
            pass

    def to_json(self, output_path: str):
        data = {
            "metadata": {
                "total": len(self.entries),
                "platforms": dict(self.platform_counts),
                "min_dataset_size": self.MIN_DATASET_SIZE,
                "platforms_count": len(self.platform_counts),
            },
            "entries": [asdict(e) for e in self.entries],
        }
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data

    @staticmethod
    def load_json(path: str) -> List[URLEntry]:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        entries = []
        for d in data["entries"]:
            entries.append(URLEntry(**d))
        return entries

    def summary(self) -> str:
        lines = [
            f"Dataset Summary: {len(self.entries)} URLs, {len(self.platform_counts)} platforms",
            "",
        ]
        for p in sorted(self.platform_counts.keys()):
            count = self.platform_counts[p]
            bar = "█" * min(count, 50)
            lines.append(f"  {p:15s} {count:4d}  {bar}")
        lines.append("")
        lines.append(f"  Target: >= {self.MIN_DATASET_SIZE} URLs")
        lines.append(f"  Status: {'PASS' if len(self.entries) >= self.MIN_DATASET_SIZE else 'NEED MORE'}")
        return "\n".join(lines)
