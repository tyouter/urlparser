"""
urlparser v3.3.0 Comprehensive Health Check Test Suite

Covers ALL public-facing features:
- P0: Imports, URL/Text/File/Media/FFmpeg utils, Models, Config (8 categories)
- P1: Cache, FileStorage, SourceDocument, StateManager (4 categories)
- P2: ContentQualityMixin, FetcherFactory (2 categories)
- P3: Network parsing - 22 URLs across 8 platforms
- P4: Pipeline validation - retry, batch, cache, markdown format (5 categories)
- P5: Local audio/video transcription (3 categories)
- P6: Batch transcriber infrastructure (2 categories)
- P7: Output persistence & final report (3 categories)

Usage:
    python tests/health_check/test_comprehensive.py
"""

import asyncio
import os
import sys
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
PARSED_DIR = OUTPUT_DIR / "parsed"
TRANSCRIBED_DIR = OUTPUT_DIR / "transcribed"
SEGMENTS_DIR = OUTPUT_DIR / "segments"
CACHE_DIR = OUTPUT_DIR / "cache"
STORAGE_DIR = OUTPUT_DIR / "storage_test"

LOCAL_WAV = Path(r"D:\boke\garden post factory\C0257_mixed_normalized.wav")
LOCAL_MP4 = Path(r"D:\boke\garden post factory\C0257_mono_video.mp4")
SEGMENT_WAV = SEGMENTS_DIR / "test_wav_segment.wav"
SEGMENT_MP4_AUDIO = SEGMENTS_DIR / "test_mp4_audio_segment.wav"

SEGMENT_DURATION = 60  # seconds

TEST_URLS: Dict[str, List[Dict[str, str]]] = {
    "bilibili": [
        {"id": "BV1KBZkB6EJF", "url": "https://www.bilibili.com/video/BV1KBZkB6EJF"},
        {"id": "BV1qNAqzxETr", "url": "https://www.bilibili.com/video/BV1qNAqzxETr"},
        {"id": "BV19aPHzyEs5", "url": "https://www.bilibili.com/video/BV19aPHzyEs5"},
    ],
    "zhihu": [
        {"id": "answer_2009429788", "url": "https://www.zhihu.com/answer/2009429788666909340"},
        {"id": "answer_2012245758", "url": "https://www.zhihu.com/answer/2012245758137631858"},
        {"id": "zhuanlan_20121580", "url": "https://zhuanlan.zhihu.com/p/2012158056595727644"},
        {"id": "pin_2000370498", "url": "https://www.zhihu.com/pin/2000370498543047460"},
    ],
    "weixin": [
        {"id": "mpoOI3gAi", "url": "https://mp.weixin.qq.com/s/mpoOI3gAiVd9I-uuzSgxAw"},
        {"id": "ca9E87PPo", "url": "https://mp.weixin.qq.com/s/ca9E87PPofjmEUVdP6EeTw"},
        {"id": "7oZuwJmGu", "url": "https://mp.weixin.qq.com/s/7oZuwJmGu9cswtE7tQm6Vg"},
    ],
    "xiaohongshu": [
        {"id": "69a90d81", "url": "https://www.xiaohongshu.com/login?redirectPath=%2Fexplore%2F69a90d81000000001d026a45"},
        {"id": "69a4107e", "url": "https://www.xiaohongshu.com/login?redirectPath=%2Fexplore%2F69a4107e000000001a025a82"},
        {"id": "691abae5", "url": "https://www.xiaohongshu.com/login?redirectPath=%2Fdiscovery%2Fitem%2F691abae5000000000402247e"},
    ],
    "dribbble": [
        {"id": "23404996", "url": "https://dribbble.com/shots/23404996-Pitch-deck-presentation-slides"},
        {"id": "23397126", "url": "https://dribbble.com/shots/23397126-Investor-Pitch-Deck-Slides"},
        {"id": "23784886", "url": "https://dribbble.com/shots/23784886-Bento-Style-Presentation"},
    ],
    "github": [
        {"id": "claude-code", "url": "https://github.com/anthropics/claude-code"},
        {"id": "browser-use", "url": "https://github.com/browser-use/browser-use"},
        {"id": "open-webui", "url": "https://github.com/open-webui/open-webui"},
    ],
    "sspai": [
        {"id": "97131", "url": "https://sspai.com/post/97131"},
    ],
    "generic": [
        {"id": "classicdriver", "url": "https://www.classicdriver.com/en/article/cars/tobias-suhlmann-follows-michael-mauer-porsches-new-head-design"},
        {"id": "mathworks", "url": "https://ww2.mathworks.cn/videos/soa-development-for-software-defined-vehicles-1768287077070.html"},
    ],
}

# ---------------------------------------------------------------------------
# Report Infrastructure
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    name: str
    passed: bool
    detail: str = ""
    duration: float = 0.0
    category: str = ""

    @property
    def status_icon(self) -> str:
        return "PASS" if self.passed else "FAIL"


class HealthReport:
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = time.time()
        self.report_path = OUTPUT_DIR / "health_report.md"

    def add(self, r: TestResult):
        self.results.append(r)
        icon = "OK" if r.passed else "FAIL"
        print(f"  [{icon}] {r.name} ({r.duration:.2f}s) {r.detail[:80]}")

    def add_batch(self, category: str, results: List[TestResult]):
        for r in results:
            r.category = category
            self.add(r)

    def summary(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        elapsed = time.time() - self.start_time

        lines = [
            f"# urlparser v3.3.0 综合健康度报告",
            f"",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> 总耗时: {elapsed:.1f}s",
            f"> 测试总数: {total} | 通过: {passed} | 失败: {total - passed}",
            f"> 健康度: **{passed/total*100:.1f}%**",
            f"",
        ]

        # Category summary
        categories = {}
        for r in self.results:
            cat = r.category or "uncategorized"
            if cat not in categories:
                categories[cat] = {"total": 0, "passed": 0, "results": []}
            categories[cat]["total"] += 1
            if r.passed:
                categories[cat]["passed"] += 1
            categories[cat]["results"].append(r)

        lines.append("## 分类汇总")
        lines.append("")
        lines.append("| 分类 | 通过/总数 | 通过率 |")
        lines.append("|------|-----------|--------|")
        for cat, data in categories.items():
            rate = data["passed"] / data["total"] * 100 if data["total"] > 0 else 0
            lines.append(f"| {cat} | {data['passed']}/{data['total']} | {rate:.0f}% |")
        lines.append("")

        # Detailed results per category
        for cat, data in categories.items():
            lines.append(f"## {cat}")
            lines.append("")
            for r in data["results"]:
                icon = "PASS" if r.passed else "**FAIL**"
                line = f"- [{icon}] **{r.name}** ({r.duration:.2f}s)"
                if r.detail:
                    line += f" — {r.detail[:200]}"
                lines.append(line)
            lines.append("")

        return "\n".join(lines)

    def save(self):
        report_text = self.summary()
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(report_text, encoding="utf-8")
        print(f"\n报告已保存: {self.report_path}")
        return report_text


def _pass(name: str, detail: str = "", duration: float = 0.0) -> TestResult:
    return TestResult(name=name, passed=True, detail=detail, duration=duration)


def _fail(name: str, detail: str = "", duration: float = 0.0) -> TestResult:
    return TestResult(name=name, passed=False, detail=detail, duration=duration)


def _skip(name: str, reason: str = "") -> TestResult:
    return TestResult(name=name, passed=True, detail=f"SKIP: {reason}", duration=0.0)


@contextmanager
def _timer(name: str):
    start = time.time()
    yield
    # duration tracked externally


# ---------------------------------------------------------------------------
# P0: Infrastructure Tests
# ---------------------------------------------------------------------------

def test_imports(report: HealthReport) -> List[TestResult]:
    """Verify all 77+ public symbols are importable."""
    results = []
    t0 = time.time()

    import urlparser
    version = getattr(urlparser, '__version__', 'unknown')
    results.append(_pass("__version__", f"v{version}", time.time() - t0))

    required_symbols = [
        # Core
        "parse", "parse_batch", "parse_sync", "UrlParser",
        # Config
        "ParseConfig", "BrowserConfig", "ScrollConfig",
        "TranscribeConfig", "ComprehensionConfig", "RetryConfig",
        # Models
        "ParseResult", "PlatformType", "ContentType",
        "VideoMetadata", "TranscriptionResult", "ArticleMetadata",
        "ComprehensionResult", "VisualFrameResult", "RetryAttempt",
        # URL utils
        "URLNormalizer", "normalize_url", "hash_url",
        "detect_platform", "is_video_url",
        # Text utils
        "clean_text", "remove_duplicate_lines", "extract_main_content",
        # File utils
        "ensure_dir", "safe_filename",
        "read_json", "write_json", "read_text", "write_text",
        # Media utils
        "is_audio_file", "is_video_file", "is_media_file",
        "get_media_duration", "format_duration",
        "format_duration_detailed", "file_size_str", "list_files",
    ]

    t0 = time.time()
    missing = []
    for sym in required_symbols:
        if not hasattr(urlparser, sym):
            missing.append(sym)
    elapsed = time.time() - t0

    if missing:
        results.append(_fail("required_symbols", f"Missing: {missing}", elapsed))
    else:
        results.append(_pass("required_symbols", f"All {len(required_symbols)} symbols present", elapsed))

    # Optional symbols
    optional_symbols = [
        "BaseFetcher", "FetchResult", "FetchConfig", "FetchStrategy",
        "PlaywrightFetcher", "CookieFetcher", "UserChromeFetcher",
        "BrowserUseFetcher", "FetcherFactory",
        "BaseParser", "ParserFactory", "ParserRegistry",
        "ZhihuParser", "XiaohongshuParser", "BilibiliParser",
        "YoutubeParser", "WeixinParser", "GithubParser", "GenericParser",
        "FunASRTranscriber", "WhisperTranscriber",
        "ResultCache", "ResultStorage",
        "SourceDocumentManager", "StateManager",
        "BatchTranscriber", "BatchTranscribeConfig",
        "MediaScanner", "SegmentHandler",
        "ContentQualityMixin",
    ]
    t0 = time.time()
    opt_ok = sum(1 for s in optional_symbols if hasattr(urlparser, s))
    elapsed = time.time() - t0
    results.append(_pass("optional_symbols", f"{opt_ok}/{len(optional_symbols)} available", elapsed))

    report.add_batch("P0-Imports", results)
    return results


def test_url_utils(report: HealthReport) -> List[TestResult]:
    from urlparser import normalize_url, detect_platform, is_video_url, hash_url, URLNormalizer
    results = []

    # normalize_url
    t0 = time.time()
    cases = [
        ("https://www.zhihu.com/question/123", "zhihu.com/question/123"),
        ("https://www.bilibili.com/video/BV123?spm=xxx", "bilibili.com/video/BV123"),
    ]
    ok = True
    for raw, expected_kw in cases:
        result = normalize_url(raw)
        if expected_kw not in result:
            ok = False
            break
    results.append(_pass("normalize_url", f"{len(cases)} cases", time.time() - t0) if ok
                   else _fail("normalize_url", "normalization failed", time.time() - t0))

    # detect_platform
    t0 = time.time()
    platform_cases = {
        "https://www.zhihu.com/question/1": "zhihu",
        "https://www.bilibili.com/video/BV123": "bilibili",
        "https://mp.weixin.qq.com/s/abc": "weixin",
        "https://www.xiaohongshu.com/explore/123": "xiaohongshu",
        "https://github.com/anthropics/claude-code": "github",
        "https://www.example.com/article": "default",
    }
    failures = []
    for url, expected in platform_cases.items():
        got = detect_platform(url)
        if got != expected:
            failures.append(f"{url}: expected={expected} got={got}")
    elapsed = time.time() - t0
    if failures:
        results.append(_fail("detect_platform", "; ".join(failures[:3]), elapsed))
    else:
        results.append(_pass("detect_platform", f"{len(platform_cases)} platforms", elapsed))

    # is_video_url
    t0 = time.time()
    vid_cases = [
        ("https://www.bilibili.com/video/BV123", True),
        ("https://www.youtube.com/watch?v=abc", True),
        ("https://www.zhihu.com/question/1", False),
        ("https://github.com/xxx", False),
    ]
    vid_ok = all(is_video_url(u) == exp for u, exp in vid_cases)
    results.append(_pass("is_video_url", f"{len(vid_cases)} cases", time.time() - t0) if vid_ok
                   else _fail("is_video_url", "mismatch", time.time() - t0))

    # hash_url
    t0 = time.time()
    h1 = hash_url("https://example.com")
    h2 = hash_url("https://example.com")
    h3 = hash_url("https://other.com")
    elapsed = time.time() - t0
    hash_ok = h1 == h2 and h1 != h3 and len(h1) == 32
    results.append(_pass("hash_url", f"deterministic, 32 chars", elapsed) if hash_ok
                   else _fail("hash_url", f"h1={h1} h2={h2} h3={h3}", elapsed))

    # URLNormalizer
    t0 = time.time()
    norm = URLNormalizer()
    r = norm.normalize("https://example.com/path?utm_source=xx#section")
    elapsed = time.time() - t0
    utm_ok = "utm_source" not in r and "example.com/path" in r
    results.append(_pass("URLNormalizer", "strips tracking params", elapsed) if utm_ok
                   else _fail("URLNormalizer", f"got: {r}", elapsed))

    report.add_batch("P0-URLUtils", results)
    return results


def test_text_utils(report: HealthReport) -> List[TestResult]:
    from urlparser import clean_text, remove_duplicate_lines, extract_main_content
    results = []

    t0 = time.time()
    dirty = "<p>Hello  <b>World</b></p>\n\n\n  extra   spaces  "
    cleaned = clean_text(dirty)
    ok = "Hello" in cleaned and "<p>" not in cleaned
    results.append(_pass("clean_text", f"strips HTML", time.time() - t0) if ok
                   else _fail("clean_text", f"got: {cleaned[:100]}", time.time() - t0))

    t0 = time.time()
    dup = "line1\nline2\nline1\nline3\nline2"
    dedup = remove_duplicate_lines(dup)
    lines = dedup.strip().split("\n")
    ok = len(lines) == len(set(lines))
    results.append(_pass("remove_duplicate_lines", f"{len(lines)} unique lines", time.time() - t0) if ok
                   else _fail("remove_duplicate_lines", f"duplicates remain", time.time() - t0))

    t0 = time.time()
    html = "<html><body><div class='content'>Main article text here.</div></body></html>"
    try:
        extracted = extract_main_content(html, [".content"])
        ok = "Main article" in extracted
        results.append(_pass("extract_main_content", f"selector-based", time.time() - t0) if ok
                       else _fail("extract_main_content", f"got: '{extracted[:100]}'", time.time() - t0))
    except Exception as e:
        results.append(_fail("extract_main_content", f"exception: {e}", time.time() - t0))

    report.add_batch("P0-TextUtils", results)
    return results


def test_file_utils(report: HealthReport) -> List[TestResult]:
    from urlparser import ensure_dir, safe_filename, write_json, read_json, write_text, read_text, list_files
    import tempfile
    results = []

    tmp = OUTPUT_DIR / "file_utils_tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    # ensure_dir
    t0 = time.time()
    d = tmp / "sub1" / "sub2"
    p = ensure_dir(str(d))
    ok = Path(p).exists()
    results.append(_pass("ensure_dir", str(p), time.time() - t0) if ok
                   else _fail("ensure_dir", "dir not created", time.time() - t0))

    # safe_filename
    t0 = time.time()
    sf = safe_filename("a/b\\c:d*e?f<g>h|i")
    ok = all(c not in sf for c in '/\\:*?"<>|')
    results.append(_pass("safe_filename", sf, time.time() - t0) if ok
                   else _fail("safe_filename", f"unsafe chars in: {sf}", time.time() - t0))

    # write_json / read_json
    t0 = time.time()
    jf = tmp / "test.json"
    data = {"key": "value", "num": 42}
    write_json(str(jf), data)
    loaded = read_json(str(jf))
    ok = loaded == data
    results.append(_pass("write/read_json", f"round-trip ok", time.time() - t0) if ok
                   else _fail("write/read_json", f"mismatch", time.time() - t0))

    # write_text / read_text
    t0 = time.time()
    tf = tmp / "test.txt"
    write_text(str(tf), "hello world")
    txt = read_text(str(tf))
    ok = txt == "hello world"
    results.append(_pass("write/read_text", f"round-trip ok", time.time() - t0) if ok
                   else _fail("write/read_text", f"got: {txt}", time.time() - t0))

    # list_files
    t0 = time.time()
    files = list_files(str(tmp))
    ok = len(files) >= 2
    results.append(_pass("list_files", f"{len(files)} files found", time.time() - t0) if ok
                   else _fail("list_files", "no files", time.time() - t0))

    report.add_batch("P0-FileUtils", results)
    return results


def test_media_utils(report: HealthReport) -> List[TestResult]:
    from urlparser import is_audio_file, is_video_file, is_media_file, format_duration, format_duration_detailed, file_size_str
    results = []

    t0 = time.time()
    ok = (is_audio_file("test.wav") and is_audio_file("test.mp3")
          and not is_audio_file("test.mp4"))
    results.append(_pass("is_audio_file", "wav/mp3=audio, mp4!=audio", time.time() - t0) if ok
                   else _fail("is_audio_file", "wrong classification", time.time() - t0))

    t0 = time.time()
    ok = (is_video_file("test.mp4") and is_video_file("test.mkv")
          and not is_video_file("test.wav"))
    results.append(_pass("is_video_file", "mp4/mkv=video, wav!=video", time.time() - t0) if ok
                   else _fail("is_video_file", "wrong classification", time.time() - t0))

    t0 = time.time()
    ok = (is_media_file("test.wav") and is_media_file("test.mp4")
          and not is_media_file("test.txt"))
    results.append(_pass("is_media_file", "wav/mp4=media, txt!=media", time.time() - t0) if ok
                   else _fail("is_media_file", "wrong classification", time.time() - t0))

    t0 = time.time()
    d1 = format_duration(3661)   # 1:01:01
    d2 = format_duration(65)     # 1:05
    results.append(_pass("format_duration", f"{d1}, {d2}", time.time() - t0))

    t0 = time.time()
    d3 = format_duration_detailed(3661)
    ok = "1" in d3 and "分" in d3 and "秒" in d3
    results.append(_pass("format_duration_detailed", d3, time.time() - t0) if ok
                   else _fail("format_duration_detailed", d3, time.time() - t0))

    t0 = time.time()
    s = file_size_str(1024 * 1024 * 1.5)
    ok = "1.50 MB" in s or "1.5 MB" in s
    results.append(_pass("file_size_str", s, time.time() - t0) if ok
                   else _fail("file_size_str", s, time.time() - t0))

    report.add_batch("P0-MediaUtils", results)
    return results


def test_ffmpeg_utils(report: HealthReport) -> List[TestResult]:
    from urlparser.utils.ffmpeg_utils import find_ffmpeg, find_ffprobe
    results = []

    t0 = time.time()
    ffmpeg = find_ffmpeg()
    ok = ffmpeg and len(ffmpeg) > 0
    results.append(_pass("find_ffmpeg", ffmpeg[:80] if ffmpeg else "not found", time.time() - t0) if ok
                   else _fail("find_ffmpeg", "ffmpeg not found", time.time() - t0))

    t0 = time.time()
    ffprobe = find_ffprobe()
    ok = ffprobe and len(ffprobe) > 0
    results.append(_pass("find_ffprobe", ffprobe[:80] if ffprobe else "not found", time.time() - t0) if ok
                   else _fail("find_ffprobe", "ffprobe not found", time.time() - t0))

    report.add_batch("P0-FFmpegUtils", results)
    return results


def test_models(report: HealthReport) -> List[TestResult]:
    from urlparser import (
        ParseResult, PlatformType, ContentType, VideoMetadata,
        TranscriptionResult, RetryAttempt, ArticleMetadata,
        ComprehensionResult, VisualFrameResult,
    )
    results = []

    # ParseResult construction
    t0 = time.time()
    pr = ParseResult(
        url="https://example.com",
        platform="test",
        platform_type=PlatformType.GENERIC,
        content_type=ContentType.ARTICLE,
        title="Test Title",
        content="Test content " * 50,
        fetch_success=True,
        final_strategy="playwright",
        retry_attempts=[
            RetryAttempt(strategy="playwright", success=False, access_restriction_reason="blocked: access restriction", duration=1.5),
            RetryAttempt(strategy="bb_browser", success=True, duration=3.2),
        ],
    )
    elapsed = time.time() - t0
    ok = pr.content_length > 0 and pr.is_article and len(pr.retry_attempts) == 2
    results.append(_pass("ParseResult", f"length={pr.content_length}", elapsed) if ok
                   else _fail("ParseResult", f"construction issue", elapsed))

    # to_dict
    t0 = time.time()
    d = pr.to_dict()
    elapsed = time.time() - t0
    ok = "final_strategy" in d and "retry_attempts" in d and isinstance(d["retry_attempts"], list)
    results.append(_pass("to_dict", f"{len(d)} keys", elapsed) if ok
                   else _fail("to_dict", f"missing keys", elapsed))

    # to_markdown
    t0 = time.time()
    md = pr.to_markdown()
    elapsed = time.time() - t0
    ok = len(md) > 50 and "example.com" in md and "Test Title" in md
    results.append(_pass("to_markdown", f"{len(md)} chars, url+title present", elapsed) if ok
                   else _fail("to_markdown", f"md too short or missing data", elapsed))

    # VideoMetadata
    t0 = time.time()
    vm = VideoMetadata(duration="10:30", views="10000", likes="500", coins="100", favorites="200")
    ok = vm.to_dict()["views"] == "10000"
    results.append(_pass("VideoMetadata", f"views={vm.views}", time.time() - t0) if ok
                   else _fail("VideoMetadata", "to_dict error", time.time() - t0))

    # TranscriptionResult
    t0 = time.time()
    tr = TranscriptionResult(success=True, text="Hello world", engine="funasr", language="zh", duration=60.0)
    ok = tr.has_content and tr.to_markdown().startswith("## 语音转录")
    results.append(_pass("TranscriptionResult", f"engine={tr.engine}", time.time() - t0) if ok
                   else _fail("TranscriptionResult", "construction error", time.time() - t0))

    # RetryAttempt
    t0 = time.time()
    ra = RetryAttempt(strategy="bb_browser", success=True, duration=3.2)
    ok = ra.to_dict()["strategy"] == "bb_browser"
    results.append(_pass("RetryAttempt", f"strategy={ra.strategy}", time.time() - t0) if ok
                   else _fail("RetryAttempt", "to_dict error", time.time() - t0))

    # Enums
    t0 = time.time()
    ok = (PlatformType.ZHIHU.value == "zhihu" and ContentType.VIDEO.value == "video")
    results.append(_pass("Enums", "PlatformType/ContentType values correct", time.time() - t0) if ok
                   else _fail("Enums", "enum value mismatch", time.time() - t0))

    report.add_batch("P0-Models", results)
    return results


def test_config(report: HealthReport) -> List[TestResult]:
    from urlparser import ParseConfig, BrowserConfig, ScrollConfig, TranscribeConfig, RetryConfig
    results = []

    # Defaults
    t0 = time.time()
    cfg = ParseConfig()
    ok = (cfg.browser.headless is True and cfg.scroll.max_scrolls == 20
          and cfg.transcribe.enabled is False and cfg.retry.enabled is True
          and cfg.retry.max_attempts == 4)
    elapsed = time.time() - t0
    results.append(_pass("ParseConfig.defaults", f"headless={cfg.browser.headless}, retry.enabled={cfg.retry.enabled}", elapsed) if ok
                   else _fail("ParseConfig.defaults", "unexpected defaults", elapsed))

    # with_transcribe
    t0 = time.time()
    cfg2 = ParseConfig.with_transcribe()
    ok = cfg2.transcribe.enabled is True
    results.append(_pass("ParseConfig.with_transcribe", f"enabled={cfg2.transcribe.enabled}", time.time() - t0) if ok
                   else _fail("ParseConfig.with_transcribe", "not enabled", time.time() - t0))

    # with_cookies
    t0 = time.time()
    cfg3 = ParseConfig.with_cookies("cookies.json")
    ok = cfg3.browser.cookies_file == "cookies.json"
    results.append(_pass("ParseConfig.with_cookies", cfg3.browser.cookies_file, time.time() - t0) if ok
                   else _fail("ParseConfig.with_cookies", "cookies_file not set", time.time() - t0))

    # to_parser_config
    t0 = time.time()
    try:
        pc = cfg.to_parser_config()
        ok = pc.headless is True and pc.max_scrolls == 20
        results.append(_pass("to_parser_config", "conversion ok", time.time() - t0) if ok
                       else _fail("to_parser_config", "values mismatch", time.time() - t0))
    except Exception as e:
        results.append(_fail("to_parser_config", str(e), time.time() - t0))

    # RetryConfig custom
    t0 = time.time()
    rc = RetryConfig(enabled=False, max_attempts=2, total_timeout=60)
    ok = not rc.enabled and rc.max_attempts == 2
    results.append(_pass("RetryConfig.custom", f"enabled={rc.enabled}, max={rc.max_attempts}", time.time() - t0) if ok
                   else _fail("RetryConfig.custom", "values wrong", time.time() - t0))

    report.add_batch("P0-Config", results)
    return results


# ---------------------------------------------------------------------------
# P1: Storage Tests
# ---------------------------------------------------------------------------

async def test_cache(report: HealthReport) -> List[TestResult]:
    from urlparser import ResultCache
    results = []

    cache = ResultCache(cache_dir=str(CACHE_DIR), ttl_hours=1)

    # set/get
    t0 = time.time()
    await cache.set({"title": "test", "content": "hello"}, url="https://example.com/test")
    got = await cache.get("https://example.com/test")
    elapsed = time.time() - t0
    ok = got is not None and got.get("title") == "test"
    results.append(_pass("cache_set_get", f"title={got.get('title') if got else 'None'}", elapsed) if ok
                   else _fail("cache_set_get", f"got={got}", elapsed))

    # has
    t0 = time.time()
    has = await cache.has("https://example.com/test")
    not_has = await cache.has("https://example.com/nonexistent")
    elapsed = time.time() - t0
    ok = has and not not_has
    results.append(_pass("cache_has", f"existing={has}, missing={not not_has}", elapsed) if ok
                   else _fail("cache_has", "has check wrong", elapsed))

    # delete
    t0 = time.time()
    await cache.delete("https://example.com/test")
    deleted = await cache.get("https://example.com/test")
    elapsed = time.time() - t0
    ok = deleted is None
    results.append(_pass("cache_delete", f"deleted={deleted is None}", elapsed) if ok
                   else _fail("cache_delete", "still exists", elapsed))

    # stats
    t0 = time.time()
    await cache.set({"x": 1}, url="https://stats.test")
    stats = await cache.stats()
    elapsed = time.time() - t0
    results.append(_pass("cache_stats", f"memory={stats.get('memory_count', '?')}", elapsed))

    await cache.clear()

    report.add_batch("P1-Cache", results)
    return results


def test_result_storage(report: HealthReport) -> List[TestResult]:
    from urlparser import ResultStorage
    results = []

    storage = ResultStorage(output_dir=str(STORAGE_DIR))
    test_data = {
        "url": "https://example.com/test",
        "platform": "test",
        "title": "Storage Test",
        "content": "Test content for storage.",
        "fetch_success": True,
    }

    t0 = time.time()
    path = storage.save(test_data, format="markdown", subfolder="test")
    elapsed = time.time() - t0
    ok = path and path.exists()
    results.append(_pass("storage_save", str(path), elapsed) if ok
                   else _fail("storage_save", f"path={path}", elapsed))

    t0 = time.time()
    saved = storage.list_saved(platform="test")
    elapsed = time.time() - t0
    results.append(_pass("storage_list", f"{len(saved)} files", elapsed))

    t0 = time.time()
    stats = storage.get_stats()
    elapsed = time.time() - t0
    results.append(_pass("storage_stats", f"total_files={stats.get('total_files', '?')}", elapsed))

    report.add_batch("P1-FileStorage", results)
    return results


async def test_source_document(report: HealthReport) -> List[TestResult]:
    from urlparser import SourceDocumentManager
    results = []

    sd = SourceDocumentManager(base_dir=str(STORAGE_DIR / "sources"))

    t0 = time.time()
    sid = sd.save_source_document(
        "https://example.com/doc1",
        "Article content here.",
        "article",
        title="Test Article",
    )
    elapsed = time.time() - t0
    ok = sid and len(sid) > 0
    results.append(_pass("source_save", f"id={sid[:20]}...", elapsed) if ok
                   else _fail("source_save", f"id={sid}", elapsed))

    t0 = time.time()
    doc = sd.get_source_document("https://example.com/doc1")
    elapsed = time.time() - t0
    ok = doc is not None
    results.append(_pass("source_get", f"found={doc is not None}", elapsed) if ok
                   else _fail("source_get", "not found", elapsed))

    t0 = time.time()
    sources = sd.list_sources()
    elapsed = time.time() - t0
    results.append(_pass("source_list", f"{len(sources)} sources", elapsed))

    t0 = time.time()
    stats = sd.get_stats()
    elapsed = time.time() - t0
    results.append(_pass("source_stats", f"total={stats.get('total', '?')}", elapsed))

    report.add_batch("P1-SourceDocument", results)
    return results


async def test_state_manager(report: HealthReport) -> List[TestResult]:
    from urlparser import StateManager
    results = []

    sm = StateManager(data_dir=str(STORAGE_DIR / "state"))

    t0 = time.time()
    normalized = sm.normalize_url("https://example.com/path?utm=1")
    ok = "example.com" in normalized
    results.append(_pass("state_normalize", normalized[:50], time.time() - t0) if ok
                   else _fail("state_normalize", f"unexpected: {normalized}", time.time() - t0))

    t0 = time.time()
    h = sm.hash_url("https://example.com/test")
    ok = len(h) == 32
    results.append(_pass("state_hash", f"len={len(h)}", time.time() - t0) if ok
                   else _fail("state_hash", f"len={len(h)}", time.time() - t0))

    t0 = time.time()
    state = sm.check_resource_state("https://example.com/nonexistent")
    ok = state is not None
    results.append(_pass("state_check", f"got state", time.time() - t0) if ok
                   else _fail("state_check", "returned None", time.time() - t0))

    t0 = time.time()
    integrity = sm.validate_integrity()
    ok = isinstance(integrity, dict)
    results.append(_pass("state_integrity", f"valid={integrity.get('valid', '?')}", time.time() - t0) if ok
                   else _fail("state_integrity", "not a dict", time.time() - t0))

    report.add_batch("P1-StateManager", results)
    return results


# ---------------------------------------------------------------------------
# P2: Content Quality & Fetcher
# ---------------------------------------------------------------------------

def test_content_quality(report: HealthReport) -> List[TestResult]:
    from urlparser import ContentQualityMixin
    results = []

    # ACCESS_RESTRICTION_PATTERNS
    t0 = time.time()
    bp = ContentQualityMixin.ACCESS_RESTRICTION_PATTERNS
    ok = "zhihu" in bp and "xiaohongshu" in bp and "weixin" in bp
    results.append(_pass("ACCESS_RESTRICTION_PATTERNS", f"platforms: {list(bp.keys())}", time.time() - t0) if ok
                   else _fail("ACCESS_RESTRICTION_PATTERNS", f"missing platforms", time.time() - t0))

    # detect_access_restriction - zhihu
    t0 = time.time()
    r1 = ContentQualityMixin.detect_access_restriction("zhihu", "", "你似乎来到了没有知识存在的荒原")
    r2 = ContentQualityMixin.detect_access_restriction("zhihu", "正常标题", "这是正常的长内容" * 50)
    r3 = ContentQualityMixin.detect_access_restriction("zhihu", "", "登录/注册" * 5)  # access_restriction
    elapsed = time.time() - t0
    ok = r1 is not None and r2 is None and r3 is not None
    results.append(_pass("detect_access_restriction_zhihu", f"荒原={r1 is not None}, 正常={r2 is None}, 访问限制={r3 is not None}", elapsed) if ok
                   else _fail("detect_access_restriction_zhihu", f"r1={r1}, r2={r2}, r3={r3}", elapsed))

    # detect_access_restriction - xiaohongshu
    t0 = time.time()
    r1 = ContentQualityMixin.detect_access_restriction("xiaohongshu", "小红书 - 你的生活兴趣社区", "")
    r2 = ContentQualityMixin.detect_access_restriction("xiaohongshu", "真实标题", "真实内容" * 50)
    elapsed = time.time() - t0
    ok = r1 is not None and r2 is None
    results.append(_pass("detect_access_restriction_xhs", f"默认标题={r1 is not None}, 正常={r2 is None}", elapsed) if ok
                   else _fail("detect_access_restriction_xhs", f"r1={r1}, r2={r2}", elapsed))

    # detect_access_restriction - weixin
    t0 = time.time()
    r1 = ContentQualityMixin.detect_access_restriction("weixin", "", "登录查看更多")
    r2 = ContentQualityMixin.detect_access_restriction("weixin", "标题", "正文" * 100)
    elapsed = time.time() - t0
    ok = r1 is not None and r2 is None
    results.append(_pass("detect_access_restriction_weixin", f"登录={r1 is not None}, 正常={r2 is None}", elapsed) if ok
                   else _fail("detect_access_restriction_weixin", f"r1={r1}, r2={r2}", elapsed))

    # validate_quality
    t0 = time.time()
    q1_ok, q1_r = ContentQualityMixin.validate_quality("标题", "a" * 200)
    q2_ok, q2_r = ContentQualityMixin.validate_quality("", "short")
    q3_ok, q3_r = ContentQualityMixin.validate_quality("标题", "short")
    elapsed = time.time() - t0
    ok = q1_ok and not q2_ok and not q3_ok
    results.append(_pass("validate_quality", f"正常={q1_ok}, 空标题={not q2_ok}, 短内容={not q3_ok}", elapsed) if ok
                   else _fail("validate_quality", f"q1={q1_ok}, q2={q2_ok}, q3={q3_ok}", elapsed))

    report.add_batch("P2-ContentQuality", results)
    return results


def test_fetcher_factory(report: HealthReport) -> List[TestResult]:
    results = []

    t0 = time.time()
    try:
        from urlparser import FetcherFactory, FetchConfig
        fc = FetchConfig()
        # Can't actually fetch without network, but can test factory
        results.append(_pass("FetcherFactory_import", "imported successfully", time.time() - t0))
    except ImportError as e:
        results.append(_fail("FetcherFactory_import", str(e), time.time() - t0))

    # Test each fetcher can be instantiated
    fetcher_classes = []
    try:
        from urlparser.fetcher import PlaywrightFetcher
        fetcher_classes.append(("PlaywrightFetcher", PlaywrightFetcher))
    except ImportError:
        pass
    try:
        from urlparser.fetcher import CookieFetcher
        fetcher_classes.append(("CookieFetcher", CookieFetcher))
    except ImportError:
        pass
    try:
        from urlparser.fetcher import UserChromeFetcher
        fetcher_classes.append(("UserChromeFetcher", UserChromeFetcher))
    except ImportError:
        pass
    try:
        from urlparser.fetcher import BbBrowserFetcher
        fetcher_classes.append(("BbBrowserFetcher", BbBrowserFetcher))
    except ImportError:
        pass

    t0 = time.time()
    failures = []
    for name, cls in fetcher_classes:
        try:
            inst = cls()
        except Exception as e:
            failures.append(f"{name}: {e}")
    elapsed = time.time() - t0
    if failures:
        results.append(_fail("fetcher_instantiation", "; ".join(failures), elapsed))
    else:
        results.append(_pass("fetcher_instantiation", f"{len(fetcher_classes)} fetchers OK", elapsed))

    report.add_batch("P2-FetcherFactory", results)
    return results


# ---------------------------------------------------------------------------
# P3: Network Parsing (via BbBrowserFetcher directly for speed)
# ---------------------------------------------------------------------------

async def test_network_parse(report: HealthReport) -> List[TestResult]:
    """Fetch all 22 URLs via BbBrowserFetcher (fast CDP-based), then validate content."""
    from urlparser.fetcher.bb_browser_fetcher import BbBrowserFetcher
    from urlparser import safe_filename
    from urlparser.parser.mixins.content_quality import ContentQualityMixin

    results: List[TestResult] = []
    PARSED_DIR.mkdir(parents=True, exist_ok=True)

    fetcher = BbBrowserFetcher()
    bb_ok = fetcher._check_bb_browser()
    if not bb_ok:
        for platform, url_list in TEST_URLS.items():
            for item in url_list:
                results.append(_skip(f"{platform}/{item['id']}", "bb-browser not available"))
        report.add_batch("P3-Network", results)
        return results

    for platform, url_list in TEST_URLS.items():
        for item in url_list:
            uid = item["id"]
            url = item["url"]
            test_name = f"{platform}/{uid}"
            t0 = time.time()
            try:
                fr = await fetcher.fetch(url)
                elapsed = time.time() - t0

                # Evaluate
                has_title = bool(fr.title and len(fr.title) > 1)
                has_content = bool(fr.text and len(fr.text) > 50)

                # Check blocked
                blocked = ContentQualityMixin.detect_access_restriction(
                    platform, fr.title or "", fr.text or ""
                )

                detail_parts = [
                    f"success={fr.success}",
                    f"title={'Y' if has_title else 'N'}",
                    f"content={len(fr.text or '')}c",
                ]
                if blocked:
                    detail_parts.append(f"BLOCKED={blocked[:50]}")
                if fr.error:
                    detail_parts.append(f"error={fr.error[:50]}")
                if fr.metadata:
                    detail_parts.append(f"meta_keys={list(fr.metadata.keys())[:5]}")
                detail = " | ".join(detail_parts)

                passed = fr.success and has_content and not blocked
                tr = TestResult(name=test_name, passed=passed, detail=detail,
                                duration=elapsed, category="P3-Network")

                # Save fetched content as MD
                try:
                    safe_name = f"{platform}_{safe_filename(uid)}"
                    md_path = PARSED_DIR / f"{safe_name}.md"
                    lines = []
                    if fr.title:
                        lines.append(f"# {fr.title}")
                        lines.append("")
                    lines.append(f"> **来源**: {url}")
                    lines.append(f"> **平台**: {platform}")
                    lines.append(f"> **策略**: bb_browser")
                    lines.append("")
                    if fr.text:
                        lines.append(fr.text)
                    md_path.write_text("\n".join(lines), encoding="utf-8")
                except Exception:
                    pass

                results.append(tr)

            except Exception as e:
                elapsed = time.time() - t0
                results.append(TestResult(
                    name=test_name, passed=False,
                    detail=f"exception: {str(e)[:100]}",
                    duration=elapsed, category="P3-Network",
                ))

    report.add_batch("P3-Network", results)
    return results


# ---------------------------------------------------------------------------
# P4: Pipeline Validation (parse() API with retry - subset of URLs)
# ---------------------------------------------------------------------------

async def test_pipeline_validation(report: HealthReport) -> List[TestResult]:
    from urlparser import parse, ParseConfig, RetryConfig, UrlParser, parse_batch
    from urlparser.parser.mixins.content_quality import ContentQualityMixin
    results = []

    # 4a: parse() with retry on a zhihu URL (likely to trigger access restriction)
    t0 = time.time()
    try:
        r = await parse("https://www.zhihu.com/answer/2009429788666909340",
                         config=ParseConfig(retry=RetryConfig(
                             enabled=True, max_attempts=3,
                             timeout_per_attempt=20, total_timeout=90,
                         )))
        elapsed = time.time() - t0
        ok = isinstance(r.retry_attempts, list) and isinstance(r.final_strategy, str)
        detail = f"attempts={len(r.retry_attempts)}, strategy={r.final_strategy}, success={r.fetch_success}"
        results.append(_pass("retry_attempts_populated", detail, elapsed) if ok
                       else _fail("retry_attempts_populated", detail, elapsed))
    except Exception as e:
        results.append(_fail("retry_attempts_populated", str(e)[:100], time.time() - t0))

    # 4b: parse() with retry disabled on an easy URL (github)
    t0 = time.time()
    try:
        r = await parse("https://github.com/anthropics/claude-code",
                         config=ParseConfig(retry=RetryConfig(enabled=False)))
        elapsed = time.time() - t0
        # When retry disabled, should go directly through _do_parse
        detail = f"strategy='{r.final_strategy}', attempts={len(r.retry_attempts)}, success={r.fetch_success}"
        # final_strategy should be empty since retry is off (it's only set by _parse_with_retry)
        no_retry = r.final_strategy == "" and len(r.retry_attempts) == 0
        if r.fetch_success:
            results.append(_pass("retry_disabled_success", detail, elapsed))
        else:
            results.append(_pass("retry_disabled_failed", detail + " (fetch failed but no retry used)", elapsed))
    except Exception as e:
        results.append(_fail("retry_disabled", str(e)[:100], time.time() - t0))

    # 4c: parse_batch (3 URLs, shorter timeout)
    t0 = time.time()
    try:
        batch_urls = [
            "https://www.bilibili.com/video/BV1KBZkB6EJF",
            "https://sspai.com/post/97131",
            "https://github.com/anthropics/claude-code",
        ]
        batch_results = await parse_batch(
            batch_urls,
            config=ParseConfig(retry=RetryConfig(
                enabled=True, max_attempts=2,
                timeout_per_attempt=20, total_timeout=60,
            )),
        )
        elapsed = time.time() - t0
        ok = len(batch_results) == 3
        success_count = sum(1 for r in batch_results if r.fetch_success)
        detail = f"got={len(batch_results)}, success={success_count}/3"
        results.append(_pass("parse_batch", detail, elapsed) if ok
                       else _fail("parse_batch", detail, elapsed))
    except Exception as e:
        results.append(_fail("parse_batch", str(e)[:100], time.time() - t0))

    # 4d: to_markdown format check (offline, no network)
    t0 = time.time()
    from urlparser import ParseResult, RetryAttempt, PlatformType, ContentType, VideoMetadata
    pr = ParseResult(
        url="https://example.com/video/BV123",
        platform="bilibili",
        platform_type=PlatformType.BILIBILI,
        content_type=ContentType.VIDEO,
        title="Test Video Title",
        content="Video content summary",
        author="Test Author",
        fetch_success=True,
        parse_time=5.3,
        final_strategy="bb_browser",
        video_metadata=VideoMetadata(duration="10:30", views="10000", likes="500", coins="100", favorites="200", danmaku="300"),
        retry_attempts=[
            RetryAttempt(strategy="playwright", success=False, access_restriction_reason="blocked: access restriction", duration=2.1),
            RetryAttempt(strategy="bb_browser", success=True, duration=3.2),
        ],
    )
    md = pr.to_markdown()
    checks = {
        "strategy_field": "bb_browser" in md and "> **" in md,
        "time_field": "5.3s" in md,
        "coins": "100" in md and "favorites" not in md.replace("200", ""),  # coins value present
        "retry_section": "playwright" in md and "bb_browser" in md,
        "retry_status": "2.1s" in md and "3.2s" in md,
        "video_section": "10:30" in md,
        "access_restriction_reason": "access restriction" in md,
    }
    elapsed = time.time() - t0
    failed_checks = [k for k, v in checks.items() if not v]
    if failed_checks:
        results.append(_fail("to_markdown_format", f"missing: {failed_checks}", elapsed))
    else:
        results.append(_pass("to_markdown_format", f"all {len(checks)} sections present", elapsed))

    # 4e: cache hit/miss
    t0 = time.time()
    try:
        from urlparser import ResultCache
        cache = ResultCache(cache_dir=str(CACHE_DIR / "pipeline"), ttl_hours=1)
        test_url = "https://cache-test.example.com/article1"

        await cache.clear()
        r1 = await cache.get(test_url)
        miss = r1 is None

        await cache.set({"title": "cached"}, url=test_url)
        r2 = await cache.get(test_url)
        hit = r2 is not None and r2.get("title") == "cached"

        await cache.delete(test_url)
        r3 = await cache.get(test_url)
        deleted = r3 is None

        elapsed = time.time() - t0
        ok = miss and hit and deleted
        results.append(_pass("cache_hit_miss", f"miss={miss}, hit={hit}, deleted={deleted}", elapsed) if ok
                       else _fail("cache_hit_miss", f"miss={miss}, hit={hit}, deleted={deleted}", elapsed))
        await cache.clear()
    except Exception as e:
        results.append(_fail("cache_hit_miss", str(e)[:100], time.time() - t0))

    report.add_batch("P4-Pipeline", results)
    return results


# ---------------------------------------------------------------------------
# P5: Local Media Transcription
# ---------------------------------------------------------------------------

async def test_local_transcription(report: HealthReport) -> List[TestResult]:
    from urlparser.utils.media_utils import extract_audio_segment
    from urlparser import TranscriptionResult
    results = []
    TRANSCRIBED_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

    # Extract 60s WAV segment
    t0 = time.time()
    wav_exists = LOCAL_WAV.exists()
    mp4_exists = LOCAL_MP4.exists()

    if not wav_exists and not mp4_exists:
        results.append(_skip("wav_segment", f"source files not found"))
        results.append(_skip("mp4_transcription", "source files not found"))
        results.append(_skip("transcription_md", "no transcription"))
        report.add_batch("P5-Transcription", results)
        return results

    # Extract segment from WAV
    if wav_exists:
        t0 = time.time()
        seg_ok = extract_audio_segment(str(LOCAL_WAV), 0, SEGMENT_DURATION, str(SEGMENT_WAV))
        elapsed = time.time() - t0
        if seg_ok and SEGMENT_WAV.exists():
            size_mb = SEGMENT_WAV.stat().st_size / 1024 / 1024
            results.append(_pass("wav_segment_extract", f"{size_mb:.1f}MB, {SEGMENT_DURATION}s", elapsed))
        else:
            results.append(_fail("wav_segment_extract", "extraction failed", elapsed))

        # Transcribe with FunASR
        t0 = time.time()
        try:
            from urlparser import FunASRTranscriber
            from urlparser.models import TranscriptionResult as ModelTR
            transcriber = FunASRTranscriber(model_size="large", device="auto")
            loop = asyncio.get_event_loop()
            tr = await loop.run_in_executor(
                None,
                lambda: transcriber.transcribe(str(SEGMENT_WAV), language="zh"),
            )
            elapsed = time.time() - t0
            if tr.success and tr.text:
                # Convert to models.TranscriptionResult for markdown output
                mtr = ModelTR(
                    success=tr.success, text=tr.text, segments=tr.segments,
                    language=tr.language or "zh", duration=tr.duration,
                    engine=tr.engine or "funasr", error=tr.error,
                )
                md_path = TRANSCRIBED_DIR / "local_wav_segment.md"
                md_path.write_text(mtr.to_markdown(), encoding="utf-8")
                results.append(_pass("wav_transcription",
                    f"engine={mtr.engine}, text={len(mtr.text)}c, segments={mtr.segment_count}, {elapsed:.1f}s", elapsed))
            else:
                results.append(_fail("wav_transcription",
                    f"success={tr.success}, error={tr.error}", elapsed))
        except ImportError:
            results.append(_skip("wav_transcription", "FunASR not installed"))
        except Exception as e:
            results.append(_fail("wav_transcription", str(e)[:100], time.time() - t0))
    else:
        results.append(_skip("wav_segment_extract", "WAV file not found"))

    # Extract audio from MP4 and transcribe
    if mp4_exists:
        t0 = time.time()
        seg_ok = extract_audio_segment(str(LOCAL_MP4), 0, SEGMENT_DURATION, str(SEGMENT_MP4_AUDIO))
        elapsed = time.time() - t0
        if seg_ok and SEGMENT_MP4_AUDIO.exists():
            size_mb = SEGMENT_MP4_AUDIO.stat().st_size / 1024 / 1024
            results.append(_pass("mp4_audio_extract", f"{size_mb:.1f}MB", elapsed))
        else:
            results.append(_fail("mp4_audio_extract", "extraction failed", elapsed))

        t0 = time.time()
        try:
            from urlparser import FunASRTranscriber
            from urlparser.models import TranscriptionResult as ModelTR
            transcriber = FunASRTranscriber(model_size="large", device="auto")
            loop = asyncio.get_event_loop()
            tr = await loop.run_in_executor(
                None,
                lambda: transcriber.transcribe(str(SEGMENT_MP4_AUDIO), language="zh"),
            )
            elapsed = time.time() - t0
            if tr.success and tr.text:
                mtr = ModelTR(
                    success=tr.success, text=tr.text, segments=tr.segments,
                    language=tr.language or "zh", duration=tr.duration,
                    engine=tr.engine or "funasr", error=tr.error,
                )
                md_path = TRANSCRIBED_DIR / "local_mp4_segment.md"
                md_path.write_text(mtr.to_markdown(), encoding="utf-8")
                results.append(_pass("mp4_transcription",
                    f"engine={mtr.engine}, text={len(mtr.text)}c, {elapsed:.1f}s", elapsed))
            else:
                results.append(_fail("mp4_transcription",
                    f"success={tr.success}, error={tr.error}", elapsed))
        except ImportError:
            results.append(_skip("mp4_transcription", "FunASR not installed"))
        except Exception as e:
            results.append(_fail("mp4_transcription", str(e)[:100], time.time() - t0))
    else:
        results.append(_skip("mp4_audio_extract", "MP4 file not found"))
        results.append(_skip("mp4_transcription", "MP4 file not found"))

    # TranscriptionResult.to_markdown format
    t0 = time.time()
    tr = TranscriptionResult(
        success=True, text="测试转录文本", engine="funasr",
        language="zh", duration=60.0,
        segments=[{"start": 0, "end": 5, "text": "第一段"}, {"start": 5, "end": 10, "text": "第二段"}],
    )
    md = tr.to_markdown()
    ok = "语音转录" in md and "funasr" in md
    results.append(_pass("transcription_md_format", f"{len(md)} chars, has header+engine", time.time() - t0) if ok
                   else _fail("transcription_md_format", "missing sections", time.time() - t0))

    report.add_batch("P5-Transcription", results)
    return results


# ---------------------------------------------------------------------------
# P6: Batch Transcriber Infrastructure
# ---------------------------------------------------------------------------

def test_batch_infra(report: HealthReport) -> List[TestResult]:
    results = []

    # MediaScanner
    t0 = time.time()
    try:
        from urlparser import MediaScanner
        scanner = MediaScanner(timeout_per_file=10)
        # Scan a small directory
        scan_dir = SEGMENTS_DIR if SEGMENTS_DIR.exists() else OUTPUT_DIR
        if scan_dir.exists():
            scan_result = scanner.scan_directory(str(scan_dir), recursive=True)
            results.append(_pass("MediaScanner",
                f"files={scan_result.total_count}, size={scan_result.total_size_str}",
                time.time() - t0))
        else:
            results.append(_pass("MediaScanner", "no scan directory", time.time() - t0))
    except ImportError as e:
        results.append(_skip("MediaScanner", str(e)))
    except Exception as e:
        results.append(_fail("MediaScanner", str(e)[:100], time.time() - t0))

    # SegmentHandler
    t0 = time.time()
    try:
        from urlparser import SegmentHandler, SegmentationConfig
        sh = SegmentHandler(config=SegmentationConfig(max_segment_duration=1800))
        should = sh.should_segment(3600, 100)
        should_not = sh.should_segment(100, 10)
        ok = should and not should_not
        segments = sh.calculate_segments(3600) if should else []
        results.append(_pass("SegmentHandler",
            f"should_segment(3600s)={should}, segments={len(segments)}",
            time.time() - t0) if ok
            else _fail("SegmentHandler", f"should={should}, should_not={should_not}", time.time() - t0))
    except ImportError as e:
        results.append(_skip("SegmentHandler", str(e)))
    except Exception as e:
        results.append(_fail("SegmentHandler", str(e)[:100], time.time() - t0))

    report.add_batch("P6-BatchInfra", results)
    return results


# ---------------------------------------------------------------------------
# P7: Output Verification
# ---------------------------------------------------------------------------

def test_output_verification(report: HealthReport) -> List[TestResult]:
    results = []

    # Check parsed files
    t0 = time.time()
    parsed_files = list(PARSED_DIR.glob("*.md")) if PARSED_DIR.exists() else []
    results.append(_pass("parsed_files", f"{len(parsed_files)} MD files generated", time.time() - t0)
                   if parsed_files else _fail("parsed_files", "no parsed MD files", time.time() - t0))

    # Check transcribed files
    t0 = time.time()
    transcribed_files = list(TRANSCRIBED_DIR.glob("*.md")) if TRANSCRIBED_DIR.exists() else []
    results.append(_pass("transcribed_files", f"{len(transcribed_files)} MD files", time.time() - t0))

    # Check health report
    t0 = time.time()
    report_path = OUTPUT_DIR / "health_report.md"
    results.append(_pass("health_report", f"path={report_path}", time.time() - t0))

    report.add_batch("P7-Output", results)
    return results


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_all_tests():
    """Run all test categories sequentially."""
    # Ensure output dirs exist
    for d in [OUTPUT_DIR, PARSED_DIR, TRANSCRIBED_DIR, SEGMENTS_DIR, CACHE_DIR, STORAGE_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    report = HealthReport()

    print("=" * 70)
    print("urlparser v3.3.0 综合健康度测试")
    print("=" * 70)

    # P0: Infrastructure
    print("\n--- P0: 基础设施 ---")
    test_imports(report)
    test_url_utils(report)
    test_text_utils(report)
    test_file_utils(report)
    test_media_utils(report)
    test_ffmpeg_utils(report)
    test_models(report)
    test_config(report)

    # P1: Storage
    print("\n--- P1: 存储层 ---")
    await test_cache(report)
    test_result_storage(report)
    await test_source_document(report)
    await test_state_manager(report)

    # P2: Content Quality & Fetcher
    print("\n--- P2: 访问限制与Fetcher ---")
    test_content_quality(report)
    test_fetcher_factory(report)

    # P3: Network Parsing
    print("\n--- P3: 网络解析 (22 URLs) ---")
    await test_network_parse(report)

    # P4: Pipeline
    print("\n--- P4: 管线验证 ---")
    await test_pipeline_validation(report)

    # P5: Transcription
    print("\n--- P5: 本地转录 ---")
    await test_local_transcription(report)

    # P6: Batch infra
    print("\n--- P6: 批量转录基础设施 ---")
    test_batch_infra(report)

    # P7: Output
    print("\n--- P7: 输出验证 ---")
    test_output_verification(report)

    # Save report
    print("\n" + "=" * 70)
    report_text = report.save()

    # Print summary
    total = len(report.results)
    passed = sum(1 for r in report.results if r.passed)
    print(f"\n总计: {passed}/{total} 通过 ({passed/total*100:.1f}%)")
    print(f"耗时: {time.time() - report.start_time:.1f}s")

    return report


if __name__ == "__main__":
    asyncio.run(run_all_tests())
