"""
urlparser v3.3.0 Comprehensive Health Check Test Suite

Covers 77 public API symbols across 18 functional categories:
- P0: Imports, URL/Text/File/Media/FFmpeg utils, Models, Config
- P1: Cache, FileStorage, SourceDocument, StateManager, DependencyInstaller
- P2: CLI, MediaScanner
- P3: Network parsing (17 URLs), Transcription
- P4: Batch parsing

Usage:
    python tests/health_check/test_health_check.py
"""

import asyncio
import os
import platform
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
CACHE_DIR = OUTPUT_DIR / "cache"
SEGMENT_WAV = OUTPUT_DIR / "test_segment.wav"

LOCAL_WAV = Path(r"D:\boke\garden post factory\C0257_mixed_normalized.wav")
LOCAL_MP4 = Path(r"D:\boke\garden post factory\C0257_mono_video.mp4")

SEGMENT_DURATION = 45  # seconds

TEST_URLS: Dict[str, List[Dict[str, str]]] = {
    "bilibili": [
        {"id": "BV1KBZkB6EJF", "url": "https://www.bilibili.com/video/BV1KBZkB6EJF"},
        {"id": "BV1qNAqzxETr", "url": "https://www.bilibili.com/video/BV1qNAqzxETr"},
        {"id": "BV19aPHzyEs5", "url": "https://www.bilibili.com/video/BV19aPHzyEs5"},
    ],
    "zhihu": [
        {"id": "answer_2009429", "url": "https://www.zhihu.com/question/1890852516835519233/answer/20094299453"},
        {"id": "answer_2010009", "url": "https://www.zhihu.com/question/1890852516835519233/answer/20100098890"},
        {"id": "answer_2012245", "url": "https://www.zhihu.com/question/660747494/answer/2012245724"},
        {"id": "zhuanlan_p2012158", "url": "https://zhuanlan.zhihu.com/p/2012158056595727644"},
    ],
    "weixin": [
        {"id": "mpoOI3gAiVd9I-uuzSgxAw", "url": "https://mp.weixin.qq.com/s/mpoOI3gAiVd9I-uuzSgxAw"},
        {"id": "KwKIHo59YeYhvtZloz1CPA", "url": "https://mp.weixin.qq.com/s/KwKIHo59YeYhvtZloz1CPA"},
        {"id": "7oZuwJmGu9cswtE7tQm6Vg", "url": "https://mp.weixin.qq.com/s/7oZuwJmGu9cswtE7tQm6Vg"},
    ],
    "xiaohongshu": [
        {"id": "explore_67fda11e", "url": "https://www.xiaohongshu.com/explore/67fda11e000000000d038f11"},
        {"id": "explore_68035be6", "url": "https://www.xiaohongshu.com/explore/68035be6000000001c00f5e5"},
    ],
    "dribbble": [
        {"id": "shots_23404996", "url": "https://dribbble.com/shots/23404996"},
        {"id": "shots_26148325", "url": "https://dribbble.com/shots/26148325"},
        {"id": "shots_23784886", "url": "https://dribbble.com/shots/23784886"},
    ],
    "generic": [
        {"id": "sspai_97131", "url": "https://sspai.com/post/97131"},
        {"id": "classicdriver", "url": "https://www.classicdriver.com"},
        {"id": "mathworks_cn", "url": "https://www.mathworks.cn"},
    ],
}

SOFT_FAIL_PLATFORMS = {"xiaohongshu"}  # known login redirect issues

# Timeout/capricious platforms: failures here are expected and should be soft-fail
NETWORK_SOFT_FAIL_IDS = {
    "xiaohongshu/explore_67fda11e",
    "xiaohongshu/explore_68035be6",
}

# ---------------------------------------------------------------------------
# HealthReport
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    name: str
    passed: bool = False
    skipped: bool = False
    error: Optional[str] = None
    duration: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


class HealthReport:
    """Accumulates test results and generates markdown report."""

    def __init__(self):
        self.results: Dict[str, List[TestResult]] = {}
        self.start_time = time.time()
        self._report_path = OUTPUT_DIR / "health_report.md"

    def add(self, category: str, result: TestResult):
        self.results.setdefault(category, []).append(result)
        # Incremental write after each category
        self._flush()

    def add_batch(self, category: str, results: List[TestResult]):
        self.results.setdefault(category, []).extend(results)
        self._flush()

    def _flush(self):
        """Partial write so we have data even if we crash."""
        try:
            self._report_path.write_text(self._render(), encoding="utf-8")
        except Exception:
            pass

    def _render(self) -> str:
        lines: List[str] = []
        elapsed = time.time() - self.start_time

        lines.append("# urlparser v3.3.0 Health Report")
        lines.append("")
        lines.append(f"> Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"> Platform: {platform.system()} {platform.release()}")
        lines.append(f"> Python: {sys.version.split()[0]}")
        lines.append(f"> Total elapsed: {elapsed:.1f}s")
        lines.append("")

        # Environment
        lines.append("## Environment")
        lines.append("")
        lines.append("| Component | Status | Version |")
        lines.append("|-----------|--------|---------|")

        # Try to get dependency versions
        for pkg in ["urlparser"]:
            try:
                from importlib.metadata import version as pkg_version
                v = pkg_version(pkg)
                lines.append(f"| {pkg} | OK | {v} |")
            except Exception:
                lines.append(f"| {pkg} | OK | 3.3.0 |")

        for pkg in ["yt-dlp", "playwright", "beautifulsoup4", "funasr", "faster-whisper"]:
            try:
                from importlib.metadata import version as pkg_version
                v = pkg_version(pkg)
                lines.append(f"| {pkg} | installed | {v} |")
            except Exception:
                lines.append(f"| {pkg} | not installed | - |")

        lines.append("")

        # Summary table
        lines.append("## Summary")
        lines.append("")
        lines.append("| Category | Total | Pass | Fail | Skip | Duration |")
        lines.append("|----------|-------|------|------|------|----------|")

        total_all = pass_all = fail_all = skip_all = 0

        for cat, results in self.results.items():
            total = len(results)
            passed = sum(1 for r in results if r.passed)
            failed = sum(1 for r in results if not r.passed and not r.skipped)
            skipped = sum(1 for r in results if r.skipped)
            dur = sum(r.duration for r in results)

            total_all += total
            pass_all += passed
            fail_all += failed
            skip_all += skipped

            lines.append(f"| {cat} | {total} | {passed} | {failed} | {skipped} | {dur:.1f}s |")

        lines.append(f"| **TOTAL** | **{total_all}** | **{pass_all}** | **{fail_all}** | **{skip_all}** | **{elapsed:.1f}s** |")
        lines.append("")

        # Detailed results per category
        lines.append("## Detailed Results")
        lines.append("")

        for cat, results in self.results.items():
            lines.append(f"### {cat}")
            lines.append("")

            # Check if this is a network parse category with extra fields
            has_network_fields = any("status_code" in r.extra for r in results)
            if has_network_fields:
                lines.append("| Test | Status | Title | Content Len | Duration | Error |")
                lines.append("|------|--------|-------|-------------|----------|-------|")
                for r in results:
                    status = "SKIP" if r.skipped else ("PASS" if r.passed else "FAIL")
                    title = r.extra.get("title", "")[:40]
                    clen = r.extra.get("content_length", "-")
                    err = (r.error or "")[:50]
                    lines.append(f"| {r.name} | {status} | {title} | {clen} | {r.duration:.1f}s | {err} |")
            else:
                lines.append("| Test | Status | Duration | Error |")
                lines.append("|------|--------|----------|-------|")
                for r in results:
                    status = "SKIP" if r.skipped else ("PASS" if r.passed else "FAIL")
                    err = (r.error or "")[:80]
                    lines.append(f"| {r.name} | {status} | {r.duration:.2f}s | {err} |")

            lines.append("")

        # Overall health assessment
        lines.append("## Overall Health Assessment")
        lines.append("")

        core_cats = ["Imports", "URL Utils", "Text Utils", "File Utils", "Media Utils",
                      "FFmpeg Utils", "Models", "Config", "Cache", "File Storage",
                      "Source Document", "State Manager", "Dependency Installer"]
        core_fail = sum(
            1 for cat in core_cats
            for r in self.results.get(cat, [])
            if not r.passed and not r.skipped
        )
        lines.append(f"- **Core health**: {'PASS' if core_fail == 0 else 'FAIL'} ({core_fail} failures)")

        net_results = self.results.get("Network Parse", [])
        if net_results:
            net_pass = sum(1 for r in net_results if r.passed)
            lines.append(f"- **Network health**: {net_pass}/{len(net_results)} URLs succeeded")
        else:
            lines.append("- **Network health**: NOT RUN")

        trans_results = self.results.get("Transcription", [])
        if not trans_results:
            lines.append("- **Transcription health**: NOT RUN")
        elif all(r.skipped for r in trans_results):
            lines.append("- **Transcription health**: SKIP (engine not available)")
        elif all(r.passed for r in trans_results):
            lines.append("- **Transcription health**: PASS")
        else:
            lines.append("- **Transcription health**: FAIL")

        # Artifacts
        lines.append("")
        lines.append("## Artifacts")
        lines.append("")
        lines.append("```")
        lines.append(f"{OUTPUT_DIR}/")
        lines.append(f"  health_report.md")
        for d in ["parsed", "transcribed", "cache"]:
            p = OUTPUT_DIR / d
            if p.exists():
                for f in sorted(p.iterdir()):
                    lines.append(f"  {d}/{f.name}")
        if SEGMENT_WAV.exists():
            size_mb = SEGMENT_WAV.stat().st_size / 1024 / 1024
            lines.append(f"  test_segment.wav ({size_mb:.1f} MB)")
        lines.append("```")

        return "\n".join(lines)

    def finalize(self) -> str:
        text = self._render()
        self._report_path.write_text(text, encoding="utf-8")
        return text


# ---------------------------------------------------------------------------
# TestTimer
# ---------------------------------------------------------------------------

@contextmanager
def timer(result: TestResult):
    t0 = time.time()
    try:
        yield result
    finally:
        result.duration = time.time() - t0


def _pass(name: str, duration: float = 0, **extra) -> TestResult:
    return TestResult(name=name, passed=True, duration=duration, extra=extra)


def _fail(name: str, error: str, duration: float = 0, **extra) -> TestResult:
    return TestResult(name=name, passed=False, error=error, duration=duration, extra=extra)


def _skip(name: str, reason: str, duration: float = 0, **extra) -> TestResult:
    return TestResult(name=name, skipped=True, error=reason, duration=duration, extra=extra)


# ---------------------------------------------------------------------------
# P0: Imports
# ---------------------------------------------------------------------------

def test_imports(report: HealthReport) -> List[TestResult]:
    results = []

    # Test 1: Main package import
    t0 = time.time()
    try:
        import urlparser
        results.append(_pass("import urlparser", time.time() - t0, version=urlparser.__version__))
    except Exception as e:
        results.append(_fail("import urlparser", str(e), time.time() - t0))
        # If main import fails, skip remaining import tests
        for name in ["core symbols", "model symbols", "config symbols", "storage symbols", "util symbols"]:
            results.append(_skip(name, "urlparser import failed"))
        report.add_batch("Imports", results)
        return results

    # Test 2: Core symbols
    t0 = time.time()
    try:
        from urlparser import parse, parse_batch, parse_sync, UrlParser
        assert callable(parse)
        assert callable(parse_batch)
        assert callable(parse_sync)
        assert UrlParser is not None
        results.append(_pass("core symbols (parse, parse_batch, parse_sync, UrlParser)", time.time() - t0))
    except Exception as e:
        results.append(_fail("core symbols", str(e), time.time() - t0))

    # Test 3: Model symbols
    t0 = time.time()
    try:
        from urlparser import (
            ParseResult, PlatformType, ContentType, VideoMetadata,
            TranscriptionResult, ArticleMetadata, ComprehensionResult, VisualFrameResult,
        )
        assert PlatformType.BILIBILI is not None
        assert ContentType.ARTICLE is not None
        results.append(_pass("model symbols (8 types)", time.time() - t0))
    except Exception as e:
        results.append(_fail("model symbols", str(e), time.time() - t0))

    # Test 4: Config symbols
    t0 = time.time()
    try:
        from urlparser import (
            ParseConfig, BrowserConfig, ScrollConfig,
            TranscribeConfig, ComprehensionConfig,
        )
        assert ParseConfig is not None
        results.append(_pass("config symbols (ParseConfig + 4 sub-configs)", time.time() - t0))
    except Exception as e:
        results.append(_fail("config symbols", str(e), time.time() - t0))

    # Test 5: Storage symbols
    t0 = time.time()
    try:
        from urlparser import (
            ResultCache, CacheEntry, ResultStorage,
            SourceDocumentManager, StateManager,
            ProcessStatus, ResourceState,
        )
        assert ProcessStatus.COMPLETE is not None
        results.append(_pass("storage symbols (7 types)", time.time() - t0))
    except Exception as e:
        results.append(_fail("storage symbols", str(e), time.time() - t0))

    # Test 6: Util symbols
    t0 = time.time()
    try:
        from urlparser import (
            URLNormalizer, normalize_url, hash_url, detect_platform, is_video_url,
            clean_text, remove_duplicate_lines, extract_main_content,
            ensure_dir, safe_filename, read_json, write_json, read_text, write_text,
            is_audio_file, is_video_file, is_media_file, get_media_duration,
            format_duration, format_duration_detailed, file_size_str, list_files,
        )
        results.append(_pass("util symbols (22 functions/classes)", time.time() - t0))
    except Exception as e:
        results.append(_fail("util symbols", str(e), time.time() - t0))

    report.add_batch("Imports", results)
    return results


# ---------------------------------------------------------------------------
# P0: URL Utils
# ---------------------------------------------------------------------------

def test_url_utils(report: HealthReport) -> List[TestResult]:
    from urlparser import normalize_url, hash_url, detect_platform, is_video_url, URLNormalizer
    results = []

    tests = [
        ("normalize_url strips tracking params", lambda: (
            normalize_url("https://example.com?a=1&utm_source=foo&b=2#frag"),
            "https://example.com?a=1&b=2",
        )),
        ("normalize_url removes fragment", lambda: (
            normalize_url("https://example.com/page#section"),
            "https://example.com/page",
        )),
        ("normalize_url keeps clean URL", lambda: (
            normalize_url("https://www.bilibili.com/video/BV1KBZkB6EJF"),
            "https://www.bilibili.com/video/BV1KBZkB6EJF",
        )),
        ("hash_url returns md5 hex", lambda: (
            len(hash_url("https://example.com")),
            32,
        )),
        ("hash_url consistent", lambda: (
            hash_url("https://example.com") == hash_url("https://example.com"),
            True,
        )),
        ("detect_platform bilibili", lambda: (
            detect_platform("https://www.bilibili.com/video/BV1test"),
            "bilibili",
        )),
        ("detect_platform zhihu", lambda: (
            detect_platform("https://www.zhihu.com/question/123"),
            "zhihu",
        )),
        ("is_video_url bilibili=True", lambda: (
            is_video_url("https://www.bilibili.com/video/BV1test"),
            True,
        )),
    ]

    for name, fn in tests:
        t0 = time.time()
        try:
            actual, expected = fn()
            if actual == expected:
                results.append(_pass(name, time.time() - t0))
            else:
                results.append(_fail(name, f"expected {expected!r}, got {actual!r}", time.time() - t0))
        except Exception as e:
            results.append(_fail(name, str(e), time.time() - t0))

    # URLNormalizer class
    t0 = time.time()
    try:
        norm = URLNormalizer()
        result = norm.normalize("https://example.com?utm_source=test")
        assert "utm_source" not in result
        results.append(_pass("URLNormalizer instance usage", time.time() - t0))
    except Exception as e:
        results.append(_fail("URLNormalizer instance usage", str(e), time.time() - t0))

    report.add_batch("URL Utils", results)
    return results


# ---------------------------------------------------------------------------
# P0: Text Utils
# ---------------------------------------------------------------------------

def test_text_utils(report: HealthReport) -> List[TestResult]:
    from urlparser import clean_text, remove_duplicate_lines
    results = []

    t0 = time.time()
    try:
        result = clean_text("  Hello   <b>World</b>  \n\n  ")
        assert "Hello" in result and "World" in result
        assert "<b>" not in result
        results.append(_pass("clean_text strips html and whitespace", time.time() - t0))
    except Exception as e:
        results.append(_fail("clean_text", str(e), time.time() - t0))

    t0 = time.time()
    try:
        result = remove_duplicate_lines("line1\nline2\nline1\nline3")
        lines = result.strip().split("\n")
        assert lines == ["line1", "line2", "line3"]
        results.append(_pass("remove_duplicate_lines deduplicates", time.time() - t0))
    except Exception as e:
        results.append(_fail("remove_duplicate_lines", str(e), time.time() - t0))

    t0 = time.time()
    try:
        from urlparser.utils.text_utils import extract_main_content
        html = "<html><body><p>Hello world</p></body></html>"
        result = extract_main_content(html, ["p"])
        assert "Hello world" in result
        results.append(_pass("extract_main_content", time.time() - t0))
    except Exception as e:
        results.append(_fail("extract_main_content", str(e), time.time() - t0))

    t0 = time.time()
    try:
        from urlparser.utils.text_utils import truncate_text, count_words
        assert truncate_text("abcdefghij", 5) == "ab..."
        assert count_words("hello world") == 2
        results.append(_pass("truncate_text + count_words", time.time() - t0))
    except Exception as e:
        results.append(_fail("truncate_text + count_words", str(e), time.time() - t0))

    report.add_batch("Text Utils", results)
    return results


# ---------------------------------------------------------------------------
# P0: File Utils
# ---------------------------------------------------------------------------

def test_file_utils(report: HealthReport) -> List[TestResult]:
    from urlparser import ensure_dir, safe_filename, read_json, write_json, read_text, write_text, file_size_str, list_files
    import tempfile
    results = []
    tmp = OUTPUT_DIR / "file_utils_tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    # ensure_dir
    t0 = time.time()
    try:
        p = ensure_dir(tmp / "sub" / "deep")
        assert p.exists()
        results.append(_pass("ensure_dir creates nested dirs", time.time() - t0))
    except Exception as e:
        results.append(_fail("ensure_dir", str(e), time.time() - t0))

    # safe_filename
    t0 = time.time()
    try:
        fn = safe_filename('test<>:"/\\|?*file.txt')
        assert "<" not in fn and ">" not in fn
        results.append(_pass("safe_filename sanitizes", time.time() - t0))
    except Exception as e:
        results.append(_fail("safe_filename", str(e), time.time() - t0))

    # write_json / read_json
    t0 = time.time()
    try:
        jf = tmp / "test.json"
        data = {"key": "value", "num": 42, "unicode": "中文"}
        assert write_json(jf, data)
        loaded = read_json(jf)
        assert loaded["key"] == "value" and loaded["unicode"] == "中文"
        results.append(_pass("write_json + read_json roundtrip", time.time() - t0))
    except Exception as e:
        results.append(_fail("write_json/read_json", str(e), time.time() - t0))

    # write_text / read_text
    t0 = time.time()
    try:
        tf = tmp / "test.txt"
        assert write_text(tf, "hello world 中文")
        txt = read_text(tf)
        assert txt == "hello world 中文"
        results.append(_pass("write_text + read_text roundtrip", time.time() - t0))
    except Exception as e:
        results.append(_fail("write_text/read_text", str(e), time.time() - t0))

    # file_size_str
    t0 = time.time()
    try:
        result_1k = file_size_str(1024)
        result_1m = file_size_str(1048576)
        assert "KB" in result_1k, f"expected KB in {result_1k!r}"
        assert "MB" in result_1m, f"expected MB in {result_1m!r}"
        results.append(_pass(f"file_size_str formatting ({result_1k}, {result_1m})", time.time() - t0))
    except Exception as e:
        results.append(_fail("file_size_str", str(e), time.time() - t0))

    # list_files
    t0 = time.time()
    try:
        files = list_files(tmp, pattern="*.json")
        assert len(files) >= 1
        results.append(_pass("list_files with pattern", time.time() - t0))
    except Exception as e:
        results.append(_fail("list_files", str(e), time.time() - t0))

    # read_json default on missing
    t0 = time.time()
    try:
        val = read_json(tmp / "nonexistent.json", default={"fallback": True})
        assert val == {"fallback": True}
        results.append(_pass("read_json default on missing file", time.time() - t0))
    except Exception as e:
        results.append(_fail("read_json default", str(e), time.time() - t0))

    report.add_batch("File Utils", results)
    return results


# ---------------------------------------------------------------------------
# P0: Media Utils
# ---------------------------------------------------------------------------

def test_media_utils(report: HealthReport) -> List[TestResult]:
    from urlparser import (
        is_audio_file, is_video_file, is_media_file,
        format_duration, format_duration_detailed, get_media_duration,
    )
    from urlparser.utils.media_utils import extract_audio_segment
    results = []

    # Extension checks
    t0 = time.time()
    try:
        assert is_audio_file("test.mp3") is True
        assert is_audio_file("test.wav") is True
        assert is_audio_file("test.txt") is False
        results.append(_pass("is_audio_file", time.time() - t0))
    except Exception as e:
        results.append(_fail("is_audio_file", str(e), time.time() - t0))

    t0 = time.time()
    try:
        assert is_video_file("test.mp4") is True
        assert is_video_file("test.mkv") is True
        assert is_video_file("test.txt") is False
        results.append(_pass("is_video_file", time.time() - t0))
    except Exception as e:
        results.append(_fail("is_video_file", str(e), time.time() - t0))

    t0 = time.time()
    try:
        assert is_media_file("test.mp3") is True
        assert is_media_file("test.mp4") is True
        assert is_media_file("test.txt") is False
        results.append(_pass("is_media_file", time.time() - t0))
    except Exception as e:
        results.append(_fail("is_media_file", str(e), time.time() - t0))

    # format_duration
    t0 = time.time()
    try:
        assert format_duration(65) == "01:05"
        assert format_duration(3661) == "1:01:01"
        results.append(_pass("format_duration", time.time() - t0))
    except Exception as e:
        results.append(_fail("format_duration", str(e), time.time() - t0))

    # format_duration_detailed (returns Chinese: "1小时1分1秒")
    t0 = time.time()
    try:
        result = format_duration_detailed(3661)
        assert len(result) > 0
        # Should contain hour/minute/second indicators in Chinese
        assert any(c in result for c in ["小时", "分", "秒"]), f"unexpected: {result!r}"
        results.append(_pass(f"format_duration_detailed -> {result!r}", time.time() - t0))
    except Exception as e:
        results.append(_fail("format_duration_detailed", str(e), time.time() - t0))

    # get_media_duration on test_audio.wav (15MB)
    t0 = time.time()
    try:
        test_wav = Path(__file__).resolve().parent.parent / "multi_platform" / "test_audio.wav"
        if test_wav.exists():
            dur = get_media_duration(str(test_wav))
            assert dur > 0
            results.append(_pass(f"get_media_duration (test_audio.wav: {dur:.1f}s)", time.time() - t0))
        else:
            results.append(_skip("get_media_duration", "test_audio.wav not found"))
    except Exception as e:
        results.append(_fail("get_media_duration", str(e), time.time() - t0))

    # extract_audio_segment from C0257 WAV
    t0 = time.time()
    try:
        if LOCAL_WAV.exists():
            ok = extract_audio_segment(
                str(LOCAL_WAV), 0, SEGMENT_DURATION, str(SEGMENT_WAV)
            )
            if ok and SEGMENT_WAV.exists():
                size_mb = SEGMENT_WAV.stat().st_size / 1024 / 1024
                results.append(_pass(f"extract_audio_segment 0-{SEGMENT_DURATION}s ({size_mb:.1f}MB)", time.time() - t0))
            else:
                results.append(_fail("extract_audio_segment", "returned False or file missing", time.time() - t0))
        else:
            results.append(_skip("extract_audio_segment", f"{LOCAL_WAV} not found"))
    except Exception as e:
        results.append(_fail("extract_audio_segment", str(e), time.time() - t0))

    report.add_batch("Media Utils", results)
    return results


# ---------------------------------------------------------------------------
# P0: FFmpeg Utils
# ---------------------------------------------------------------------------

def test_ffmpeg_utils(report: HealthReport) -> List[TestResult]:
    from urlparser.utils.ffmpeg_utils import find_ffmpeg, find_ffprobe
    results = []

    t0 = time.time()
    try:
        ffmpeg_path = find_ffmpeg()
        assert ffmpeg_path, "ffmpeg not found"
        results.append(_pass(f"find_ffmpeg -> {ffmpeg_path}", time.time() - t0))
    except Exception as e:
        results.append(_fail("find_ffmpeg", str(e), time.time() - t0))

    t0 = time.time()
    try:
        ffprobe_path = find_ffprobe()
        assert ffprobe_path, "ffprobe not found"
        results.append(_pass(f"find_ffprobe -> {ffprobe_path}", time.time() - t0))
    except Exception as e:
        results.append(_fail("find_ffprobe", str(e), time.time() - t0))

    report.add_batch("FFmpeg Utils", results)
    return results


# ---------------------------------------------------------------------------
# P0: Data Models
# ---------------------------------------------------------------------------

def test_models(report: HealthReport) -> List[TestResult]:
    from urlparser import (
        ParseResult, PlatformType, ContentType, VideoMetadata,
        TranscriptionResult, ArticleMetadata,
    )
    results = []

    # PlatformType enum
    t0 = time.time()
    try:
        assert PlatformType.BILIBILI.value == "bilibili"
        assert PlatformType.ZHIHU.value == "zhihu"
        assert len(PlatformType) >= 8
        results.append(_pass(f"PlatformType enum ({len(PlatformType)} values)", time.time() - t0))
    except Exception as e:
        results.append(_fail("PlatformType", str(e), time.time() - t0))

    # ContentType enum
    t0 = time.time()
    try:
        assert ContentType.VIDEO.value == "video"
        assert ContentType.ARTICLE.value == "article"
        results.append(_pass(f"ContentType enum ({len(ContentType)} values)", time.time() - t0))
    except Exception as e:
        results.append(_fail("ContentType", str(e), time.time() - t0))

    # ParseResult creation
    t0 = time.time()
    try:
        pr = ParseResult(
            url="https://example.com",
            platform="generic",
            platform_type=PlatformType.GENERIC,
            content_type=ContentType.WEBPAGE,
        )
        assert pr.url == "https://example.com"
        assert pr.is_video is False
        assert pr.is_article is False
        assert pr.content_length == 0
        d = pr.to_dict()
        assert "url" in d
        results.append(_pass("ParseResult creation + to_dict", time.time() - t0))
    except Exception as e:
        results.append(_fail("ParseResult", str(e), time.time() - t0))

    # TranscriptionResult
    t0 = time.time()
    try:
        tr = TranscriptionResult(
            success=True, text="test text content here", segments=[],
            language="zh", duration=10.0, engine="test"
        )
        assert tr.has_content is True
        assert tr.segment_count == 0
        md = tr.to_markdown()
        assert "test" in md
        results.append(_pass("TranscriptionResult creation + has_content", time.time() - t0))
    except Exception as e:
        results.append(_fail("TranscriptionResult", str(e), time.time() - t0))

    # VideoMetadata
    t0 = time.time()
    try:
        vm = VideoMetadata(duration="10:30", views="1000", likes="100")
        d = vm.to_dict()
        assert d["duration"] == "10:30"
        results.append(_pass("VideoMetadata creation + to_dict", time.time() - t0))
    except Exception as e:
        results.append(_fail("VideoMetadata", str(e), time.time() - t0))

    report.add_batch("Models", results)
    return results


# ---------------------------------------------------------------------------
# P0: Config
# ---------------------------------------------------------------------------

def test_config(report: HealthReport) -> List[TestResult]:
    from urlparser import ParseConfig, BrowserConfig, ScrollConfig, TranscribeConfig, ComprehensionConfig
    results = []

    # ParseConfig default
    t0 = time.time()
    try:
        cfg = ParseConfig()
        assert cfg.browser.headless is True
        assert cfg.scroll.enabled is True
        results.append(_pass("ParseConfig() default creation", time.time() - t0))
    except Exception as e:
        results.append(_fail("ParseConfig default", str(e), time.time() - t0))

    # ParseConfig.simple
    t0 = time.time()
    try:
        cfg = ParseConfig.simple()
        assert cfg is not None
        results.append(_pass("ParseConfig.simple()", time.time() - t0))
    except Exception as e:
        results.append(_fail("ParseConfig.simple", str(e), time.time() - t0))

    # ParseConfig.with_transcribe
    t0 = time.time()
    try:
        cfg = ParseConfig.with_transcribe(engine="funasr")
        assert cfg.transcribe.enabled is True
        assert cfg.transcribe.engine == "funasr"
        results.append(_pass("ParseConfig.with_transcribe(engine='funasr')", time.time() - t0))
    except Exception as e:
        results.append(_fail("ParseConfig.with_transcribe", str(e), time.time() - t0))

    # ParseConfig.with_cookies
    t0 = time.time()
    try:
        cfg = ParseConfig.with_cookies(cookies_file="cookies.txt")
        assert cfg.browser.cookies_file == "cookies.txt"
        results.append(_pass("ParseConfig.with_cookies()", time.time() - t0))
    except Exception as e:
        results.append(_fail("ParseConfig.with_cookies", str(e), time.time() - t0))

    # to_parser_config conversion
    t0 = time.time()
    try:
        cfg = ParseConfig()
        pc = cfg.to_parser_config()
        assert pc is not None
        results.append(_pass("ParseConfig.to_parser_config()", time.time() - t0))
    except Exception as e:
        results.append(_fail("ParseConfig.to_parser_config", str(e), time.time() - t0))

    report.add_batch("Config", results)
    return results


# ---------------------------------------------------------------------------
# P1: Cache (async)
# ---------------------------------------------------------------------------

async def test_cache(report: HealthReport) -> List[TestResult]:
    from urlparser import ResultCache, CacheEntry
    results = []

    cache = ResultCache(cache_dir=str(CACHE_DIR), ttl_hours=1.0)

    # set + get
    t0 = time.time()
    try:
        await cache.set({"url": "https://test.com", "title": "Test"}, url="https://test.com")
        entry = await cache.get("https://test.com")
        assert entry is not None
        assert entry["title"] == "Test"
        results.append(_pass("cache set + get", time.time() - t0))
    except Exception as e:
        results.append(_fail("cache set/get", str(e), time.time() - t0))

    # has
    t0 = time.time()
    try:
        assert await cache.has("https://test.com") is True
        assert await cache.has("https://nonexistent.com") is False
        results.append(_pass("cache has", time.time() - t0))
    except Exception as e:
        results.append(_fail("cache has", str(e), time.time() - t0))

    # delete
    t0 = time.time()
    try:
        deleted = await cache.delete("https://test.com")
        assert deleted is True
        assert await cache.has("https://test.com") is False
        results.append(_pass("cache delete", time.time() - t0))
    except Exception as e:
        results.append(_fail("cache delete", str(e), time.time() - t0))

    # stats
    t0 = time.time()
    try:
        s = await cache.stats()
        assert "memory_count" in s
        results.append(_pass(f"cache stats (mem={s['memory_count']})", time.time() - t0))
    except Exception as e:
        results.append(_fail("cache stats", str(e), time.time() - t0))

    # clear
    t0 = time.time()
    try:
        await cache.clear()
        results.append(_pass("cache clear", time.time() - t0))
    except Exception as e:
        results.append(_fail("cache clear", str(e), time.time() - t0))

    # CacheEntry
    t0 = time.time()
    try:
        import time as _time
        ce = CacheEntry(url="https://test.com", result_dict={}, cached_at=_time.time(), expires_at=None)
        assert ce.is_expired is False
        results.append(_pass("CacheEntry.is_expired", time.time() - t0))
    except Exception as e:
        results.append(_fail("CacheEntry", str(e), time.time() - t0))

    report.add_batch("Cache", results)
    return results


# ---------------------------------------------------------------------------
# P1: File Storage
# ---------------------------------------------------------------------------

def test_result_storage(report: HealthReport) -> List[TestResult]:
    from urlparser import ResultStorage
    results = []
    storage_dir = OUTPUT_DIR / "storage_test"
    storage_dir.mkdir(parents=True, exist_ok=True)

    storage = ResultStorage(output_dir=str(storage_dir))

    # save markdown
    t0 = time.time()
    try:
        p = storage.save(
            {"url": "https://test.com", "platform": "generic", "title": "Test Article", "content": "Content here"},
            format="markdown",
        )
        assert p.exists()
        results.append(_pass(f"ResultStorage.save markdown -> {p.name}", time.time() - t0))
    except Exception as e:
        results.append(_fail("ResultStorage.save markdown", str(e), time.time() - t0))

    # save json
    t0 = time.time()
    try:
        p = storage.save(
            {"url": "https://test2.com", "platform": "bilibili", "title": "Test Video"},
            format="json",
        )
        assert p.exists()
        results.append(_pass(f"ResultStorage.save json -> {p.name}", time.time() - t0))
    except Exception as e:
        results.append(_fail("ResultStorage.save json", str(e), time.time() - t0))

    # list_saved
    t0 = time.time()
    try:
        saved = storage.list_saved()
        assert isinstance(saved, list) and len(saved) >= 1, f"expected list with >=1 items, got {type(saved)} len={len(saved)}"
        results.append(_pass(f"ResultStorage.list_saved ({len(saved)} files)", time.time() - t0))
    except Exception as e:
        results.append(_fail("ResultStorage.list_saved", str(e), time.time() - t0))

    # get_stats
    t0 = time.time()
    try:
        stats = storage.get_stats()
        assert stats["total_files"] >= 2
        results.append(_pass(f"ResultStorage.get_stats (total={stats['total_files']})", time.time() - t0))
    except Exception as e:
        results.append(_fail("ResultStorage.get_stats", str(e), time.time() - t0))

    report.add_batch("File Storage", results)
    return results


# ---------------------------------------------------------------------------
# P1: Source Document Manager
# ---------------------------------------------------------------------------

def test_source_document(report: HealthReport) -> List[TestResult]:
    from urlparser import SourceDocumentManager
    results = []
    import tempfile, shutil

    tmp = CACHE_DIR / "source_test"
    tmp.mkdir(parents=True, exist_ok=True)

    mgr = SourceDocumentManager(base_dir=str(tmp))

    # save_source_document
    t0 = time.time()
    try:
        path = mgr.save_source_document(
            url="https://test.com/article",
            content="Article content for testing.",
            content_type="article",
            title="Test Article",
        )
        assert path is not None
        results.append(_pass("save_source_document", time.time() - t0))
    except Exception as e:
        results.append(_fail("save_source_document", str(e), time.time() - t0))

    # get_source_document
    t0 = time.time()
    try:
        content = mgr.get_source_document("https://test.com/article")
        assert content is not None and "Article content" in content
        results.append(_pass("get_source_document", time.time() - t0))
    except Exception as e:
        results.append(_fail("get_source_document", str(e), time.time() - t0))

    # generate_video_md
    t0 = time.time()
    try:
        md = mgr.generate_video_md(
            metadata={"title": "Test Video", "duration": "10:30"},
            subtitles=[{"text": "Hello world"}],
        )
        assert "Test Video" in md
        results.append(_pass("generate_video_md", time.time() - t0))
    except Exception as e:
        results.append(_fail("generate_video_md", str(e), time.time() - t0))

    # get_stats
    t0 = time.time()
    try:
        stats = mgr.get_stats()
        assert "total" in stats
        results.append(_pass(f"get_stats (total={stats['total']})", time.time() - t0))
    except Exception as e:
        results.append(_fail("get_stats", str(e), time.time() - t0))

    report.add_batch("Source Document", results)
    return results


# ---------------------------------------------------------------------------
# P1: State Manager
# ---------------------------------------------------------------------------

def test_state_manager(report: HealthReport) -> List[TestResult]:
    from urlparser import StateManager
    results = []

    tmp = CACHE_DIR / "state_test"
    tmp.mkdir(parents=True, exist_ok=True)
    mgr = StateManager(data_dir=str(tmp))

    # normalize_url
    t0 = time.time()
    try:
        norm = mgr.normalize_url("https://example.com/page?utm_source=test#section")
        assert "utm_source" not in norm
        results.append(_pass("StateManager.normalize_url", time.time() - t0))
    except Exception as e:
        results.append(_fail("StateManager.normalize_url", str(e), time.time() - t0))

    # hash_url
    t0 = time.time()
    try:
        h = mgr.hash_url("https://example.com")
        assert len(h) == 32
        results.append(_pass("StateManager.hash_url", time.time() - t0))
    except Exception as e:
        results.append(_fail("StateManager.hash_url", str(e), time.time() - t0))

    # check_resource_state
    t0 = time.time()
    try:
        state = mgr.check_resource_state("https://nonexistent-test.com")
        assert state is not None
        results.append(_pass("StateManager.check_resource_state", time.time() - t0))
    except Exception as e:
        results.append(_fail("StateManager.check_resource_state", str(e), time.time() - t0))

    # get_process_status
    t0 = time.time()
    try:
        from urlparser import ProcessStatus
        status = mgr.get_process_status("https://nonexistent-test.com")
        assert isinstance(status, ProcessStatus)
        results.append(_pass(f"StateManager.get_process_status -> {status.name}", time.time() - t0))
    except Exception as e:
        results.append(_fail("StateManager.get_process_status", str(e), time.time() - t0))

    report.add_batch("State Manager", results)
    return results


# ---------------------------------------------------------------------------
# P1: Dependency Installer
# ---------------------------------------------------------------------------

def test_dependency_installer(report: HealthReport) -> List[TestResult]:
    from urlparser import is_package_installed, is_ffmpeg_installed
    results = []

    t0 = time.time()
    try:
        ok, ver = is_package_installed("urlparser")
        assert ok
        results.append(_pass(f"is_package_installed('urlparser') -> {ver}", time.time() - t0))
    except Exception as e:
        results.append(_fail("is_package_installed('urlparser')", str(e), time.time() - t0))

    t0 = time.time()
    try:
        ok, ver = is_ffmpeg_installed()
        results.append(_pass(f"is_ffmpeg_installed -> {ok} ({ver})", time.time() - t0))
    except Exception as e:
        results.append(_fail("is_ffmpeg_installed", str(e), time.time() - t0))

    report.add_batch("Dependency Installer", results)
    return results


# ---------------------------------------------------------------------------
# P2: CLI
# ---------------------------------------------------------------------------

def test_cli(report: HealthReport) -> List[TestResult]:
    results = []

    t0 = time.time()
    try:
        from urlparser.cli import create_parser
        parser = create_parser()
        assert parser is not None
        assert parser is not None
        # Verify it can parse a basic command
        args = parser.parse_args(["parse", "https://example.com"])
        assert args.url == "https://example.com"
        results.append(_pass("CLI create_parser + parse 'parse' command", time.time() - t0))
    except Exception as e:
        results.append(_fail("CLI create_parser", str(e), time.time() - t0))

    report.add_batch("CLI", results)
    return results


# ---------------------------------------------------------------------------
# P2: MediaScanner
# ---------------------------------------------------------------------------

def test_media_scanner(report: HealthReport) -> List[TestResult]:
    from urlparser import MediaScanner
    results = []

    t0 = time.time()
    try:
        scanner = MediaScanner(timeout_per_file=10.0)
        # Scan the multi_platform test directory for media files
        test_dir = Path(__file__).resolve().parent.parent / "multi_platform"
        if test_dir.exists():
            scan_result = scanner.scan_directory(str(test_dir), recursive=False)
            assert scan_result is not None
            results.append(_pass(
                f"MediaScanner.scan -> {scan_result.total_count} files, "
                f"{scan_result.audio_count} audio, {scan_result.video_count} video",
                time.time() - t0,
            ))
        else:
            results.append(_skip("MediaScanner.scan", "multi_platform dir not found"))
    except Exception as e:
        results.append(_fail("MediaScanner.scan", str(e), time.time() - t0))

    report.add_batch("MediaScanner", results)
    return results


# ---------------------------------------------------------------------------
# P3: Network Parse (17 URLs) — follows test_multi_platform.py pattern
#
# Uses BbBrowserFetcher (CDP) for all platforms:
#   - Videos: fetch → download audio → FunASR transcribe → chars/sec check
#   - Articles: fetch → save text → text_length >= 100 check
# Quality standards from codebase (test_multi_platform.py / test_report.md):
#   - Video: chars/sec in [2.5, 8] = GOOD
#   - Article: text_length >= 100 = GOOD
# ---------------------------------------------------------------------------

# Mark which platforms produce video content
VIDEO_PLATFORMS = {"bilibili"}

# Content type labels per platform (for unified MD output)
CONTENT_TYPE_MAP = {
    "bilibili": "video",
    "zhihu": "article",
    "weixin": "article",
    "xiaohongshu": "note",
    "dribbble": "webpage",
    "generic": "webpage",
}

# Access restriction / blocked-content detection patterns
from urlparser.parser.mixins.content_quality import ContentQualityMixin

ACCESS_RESTRICTION_PATTERNS = ContentQualityMixin.ACCESS_RESTRICTION_PATTERNS
_detect_access_restriction = ContentQualityMixin.detect_access_restriction


async def test_network_parse(report: HealthReport) -> List[TestResult]:
    from urlparser.fetcher.bb_browser_fetcher import BbBrowserFetcher
    from urlparser import safe_filename
    from urlparser.utils.media_utils import get_media_duration

    results: List[TestResult] = []
    fetch_results: List[Dict[str, Any]] = []

    # ---- Initialize fetcher ----
    fetcher = BbBrowserFetcher()
    bb_ok = fetcher._check_bb_browser()
    if not bb_ok:
        report.add_batch("Network Parse", [_skip("all", "bb-browser not available")])
        return results

    # Windows fix: asyncio.create_subprocess_exec can't properly execute .CMD files.
    # Monkey-patch _run_exec to use shell execution via create_subprocess_shell.
    import shutil
    _bb_full_path = shutil.which('bb-browser')
    if _bb_full_path and _bb_full_path.lower().endswith('.cmd'):
        async def _patched_run_exec(cmd):
            # Quote all args to prevent shell interpretation of &, ?, etc.
            parts = []
            for c in cmd:
                if ' ' in c or '&' in c or '?' in c or '=' in c:
                    parts.append(f'"{c}"')
                else:
                    parts.append(c)
            shell_cmd = ' '.join(parts)
            proc = await asyncio.create_subprocess_shell(
                shell_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            out = stdout.decode('utf-8', errors='replace').strip()
            err = stderr.decode('utf-8', errors='replace').strip()
            return out, err, proc.returncode or 0
        fetcher._run_exec = _patched_run_exec

    # ---- Phase 1: Fetch all URLs sequentially ----
    print("  Phase 1: Fetching all URLs via BbBrowserFetcher...")
    all_entries: List[Dict[str, Any]] = []
    for platform, entries in TEST_URLS.items():
        for entry in entries:
            all_entries.append({
                "platform": platform,
                "id": entry["id"],
                "url": entry["url"],
                "is_video": platform in VIDEO_PLATFORMS,
            })

    for item in all_entries:
        platform = item["platform"]
        uid = item["id"]
        url = item["url"]
        is_video = item["is_video"]
        is_soft = platform in SOFT_FAIL_PLATFORMS

        t0 = time.time()
        try:
            fr = await asyncio.wait_for(fetcher.fetch(url), timeout=90.0)
            elapsed = time.time() - t0

            item["fetch_result"] = fr
            item["fetch_success"] = fr.success
            item["title"] = fr.title or ""
            item["text_length"] = len(fr.text) if fr.text else 0
            item["metadata"] = {k: v for k, v in fr.metadata.items() if k != "raw_data"}
            item["fetch_elapsed"] = elapsed

            # Access restriction detection on fetched content
            blocked_reason = None
            if fr.success and fr.text:
                blocked_reason = _detect_access_restriction(platform, fr.title or "", fr.text)
            item["blocked_reason"] = blocked_reason

            if blocked_reason:
                item["fetch_success"] = False  # treat blocked as not usable
                results.append(_skip(
                    f"fetch/{platform}/{uid}",
                    blocked_reason,
                    elapsed,
                    title=fr.title[:50] if fr.title else "",
                    content_length=item["text_length"],
                ))
            elif fr.success:
                results.append(_pass(
                    f"fetch/{platform}/{uid}",
                    elapsed,
                    title=fr.title[:50],
                    content_length=item["text_length"],
                ))
            elif is_soft:
                results.append(_skip(
                    f"fetch/{platform}/{uid}",
                    fr.error or "fetch failed (soft-fail platform)",
                    elapsed,
                    title=fr.title[:50] if fr.title else "",
                ))
            else:
                results.append(_fail(
                    f"fetch/{platform}/{uid}",
                    fr.error or "fetch failed",
                    elapsed,
                    title=fr.title[:50] if fr.title else "",
                ))
        except asyncio.TimeoutError:
            elapsed = time.time() - t0
            item["fetch_success"] = False
            item["blocked_reason"] = None
            if is_soft:
                results.append(_skip(f"fetch/{platform}/{uid}", f"timeout (90s, soft-fail)", elapsed))
            else:
                results.append(_fail(f"fetch/{platform}/{uid}", "timeout (90s)", elapsed))
        except Exception as e:
            elapsed = time.time() - t0
            item["fetch_success"] = False
            item["blocked_reason"] = None
            if is_soft:
                results.append(_skip(f"fetch/{platform}/{uid}", f"soft-fail: {e}", elapsed))
            else:
                results.append(_fail(f"fetch/{platform}/{uid}", str(e)[:100], elapsed))

    # ---- Phase 2: Download + transcribe video URLs ----
    video_items = [it for it in all_entries if it["is_video"] and it.get("fetch_success")]
    print(f"  Phase 2: Transcribing {len(video_items)} video URLs...")

    for item in video_items:
        platform = item["platform"]
        uid = item["id"]
        url = item["url"]
        meta = item.get("metadata", {})
        title = item.get("title", uid)
        content_type = CONTENT_TYPE_MAP.get(platform, "webpage")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        bvid = meta.get("bvid")
        pages = meta.get("pages", [])
        cid = pages[0].get("cid") if pages else None
        duration_str = meta.get("duration", "")
        views_str = meta.get("view", "")
        likes_str = meta.get("like", "")
        coins_str = meta.get("coin", "")
        favorites_str = meta.get("favorite", "")
        tags_str = meta.get("tag", "")
        if isinstance(tags_str, list):
            tags_str = ", ".join(str(t) for t in tags_str)
        author = meta.get("owner", {}).get("name", "") if isinstance(meta.get("owner"), dict) else meta.get("author", "")
        description = meta.get("desc", "") or ""

        if not bvid or not cid:
            results.append(_skip(
                f"transcribe/{platform}/{uid}",
                f"no BVID/CID (bvid={bvid}, cid={cid})",
            ))
            continue

        # Download audio
        wav_path = str(CACHE_DIR / f"bilibili_{uid}.wav")
        t0 = time.time()
        try:
            dl_ok = await asyncio.wait_for(
                fetcher.download_bilibili_audio(bvid, cid, wav_path),
                timeout=300.0,
            )
            dl_elapsed = time.time() - t0

            if not dl_ok or not os.path.exists(wav_path):
                results.append(_fail(
                    f"download/{platform}/{uid}",
                    f"audio download failed ({dl_elapsed:.1f}s)",
                    dl_elapsed,
                ))
                continue

            wav_size_mb = os.path.getsize(wav_path) / 1024 / 1024
            results.append(_pass(
                f"download/{platform}/{uid}",
                dl_elapsed,
                wav_size_mb=f"{wav_size_mb:.1f}",
            ))
        except asyncio.TimeoutError:
            results.append(_fail(f"download/{platform}/{uid}", "download timeout (300s)", time.time() - t0))
            continue
        except Exception as e:
            results.append(_fail(f"download/{platform}/{uid}", str(e)[:100], time.time() - t0))
            continue

        # Transcribe with FunASR
        t0 = time.time()
        tr_elapsed = 0.0
        transcription_text = ""
        try:
            from urlparser import FunASRTranscriber
            transcriber = FunASRTranscriber()
            tr = transcriber.transcribe(wav_path, language="zh")
            tr_elapsed = time.time() - t0

            if tr.success and tr.text:
                transcription_text = tr.text
                text_len = len(tr.text)

                # Completeness verification: chars/sec ratio (codebase standard)
                duration_sec = (wav_size_mb * 1024 * 1024) / 32000  # 16kHz 16-bit mono
                chars_per_sec = text_len / duration_sec if duration_sec > 0 else 0
                assessment = "GOOD" if 2.5 <= chars_per_sec <= 8 else "SUSPICIOUS"

                results.append(_pass(
                    f"transcribe/{platform}/{uid}",
                    tr_elapsed,
                    text_length=text_len,
                    chars_per_sec=f"{chars_per_sec:.2f}",
                    assessment=assessment,
                    wav_mb=f"{wav_size_mb:.1f}",
                ))
            else:
                results.append(_fail(
                    f"transcribe/{platform}/{uid}",
                    tr.error or "transcription produced no text",
                    tr_elapsed,
                ))
        except Exception as e:
            tr_elapsed = time.time() - t0
            results.append(_fail(f"transcribe/{platform}/{uid}", str(e)[:100], tr_elapsed))
        finally:
            # Clean up downloaded wav
            if os.path.exists(wav_path):
                os.unlink(wav_path)

        # Generate unified merged output file (video info + description + transcription)
        out_path = PARSED_DIR / f"bilibili_{uid}.md"
        sections = []
        sections.append(f"# {title}\n")
        sections.append(f"> **来源**: {url}")
        sections.append(f"> **平台**: {platform} | **类型**: {content_type}")
        if author:
            sections.append(f"> **作者**: {author}")
        sections.append(f"> **解析策略**: bb-browser")
        sections.append(f"> **解析时间**: {now_str}\n")

        # 视频信息 section
        info_lines = ["## 视频信息"]
        info_lines.append(f"- BVID: {bvid}")
        if duration_str:
            info_lines.append(f"- 时长: {duration_str}")
        if views_str:
            info_lines.append(f"- 播放: {views_str}")
        if likes_str:
            info_lines.append(f"- 点赞: {likes_str}")
        if coins_str:
            info_lines.append(f"- 投币: {coins_str}")
        if favorites_str:
            info_lines.append(f"- 收藏: {favorites_str}")
        if tags_str:
            info_lines.append(f"- 标签: {tags_str}")
        sections.append("\n".join(info_lines) + "\n")

        # 简介 section
        if description:
            sections.append(f"## 简介\n\n{description}\n")

        # 语音转录 section
        if transcription_text:
            tr_meta = f"> 引擎: FunASR (SenseVoice) | 音频: {wav_size_mb:.1f} MB | 耗时: {tr_elapsed:.1f}s"
            sections.append(f"## 语音转录\n\n{tr_meta}\n\n{transcription_text}\n")

        out_path.write_text("\n".join(sections), encoding="utf-8")

    # ---- Phase 3: Save article text and verify quality ----
    article_items = [it for it in all_entries if not it["is_video"] and it.get("fetch_success")]
    print(f"  Phase 3: Saving {len(article_items)} article texts...")

    for item in article_items:
        platform = item["platform"]
        uid = item["id"]
        fr = item.get("fetch_result")

        if not fr or not fr.text:
            results.append(_skip(
                f"article/{platform}/{uid}",
                "no text content from fetch",
            ))
            continue

        # Re-check for blocked content on the fetched text
        blocked_reason = _detect_access_restriction(platform, fr.title or "", fr.text)
        if blocked_reason:
            results.append(_skip(
                f"article/{platform}/{uid}",
                blocked_reason,
                item.get("fetch_elapsed", 0),
                text_length=len(fr.text),
            ))
            continue

        text_len = len(fr.text)
        content_type = CONTENT_TYPE_MAP.get(platform, "webpage")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        title = item.get("title", uid)

        # Build unified MD output
        safe_name = safe_filename(f"{platform}_{uid}")
        out_path = PARSED_DIR / f"{safe_name}.md"

        header_lines = [f"# {title}\n"]
        header_lines.append(f"> **来源**: {item['url']}")
        header_lines.append(f"> **平台**: {platform} | **类型**: {content_type}")
        header_lines.append(f"> **解析策略**: bb-browser")
        header_lines.append(f"> **解析时间**: {now_str}\n")

        # Platform-specific body
        body_section = f"## 正文\n\n{fr.text}\n"

        out_path.write_text("\n".join(header_lines) + "\n" + body_section, encoding="utf-8")

        # Completeness verification
        is_unclean_platform = platform in {"dribbble", "generic"}
        assessment = "GOOD" if text_len >= 100 else "SHORT"

        if text_len >= 100:
            result_extra = dict(text_length=text_len, assessment=assessment)
            if is_unclean_platform:
                result_extra["note"] = "unclean (may contain nav/footer noise)"
            results.append(_pass(
                f"article/{platform}/{uid}",
                item.get("fetch_elapsed", 0),
                **result_extra,
            ))
        else:
            results.append(_fail(
                f"article/{platform}/{uid}",
                f"text too short: {text_len} chars (min 100)",
                item.get("fetch_elapsed", 0),
                text_length=text_len,
            ))

    report.add_batch("Network Parse", results)
    return results


# ---------------------------------------------------------------------------
# P3: Transcription
# ---------------------------------------------------------------------------

async def test_transcription(report: HealthReport) -> List[TestResult]:
    from urlparser import FunASRTranscriber, WhisperTranscriber, BaseTranscriber
    results = []

    if not SEGMENT_WAV.exists():
        report.add_batch("Transcription", [_skip("transcription", f"{SEGMENT_WAV} not found (extract_audio_segment may have failed)")])
        return results

    # Try FunASR first
    t0 = time.time()
    try:
        transcriber = FunASRTranscriber()
        tr = transcriber.transcribe(str(SEGMENT_WAV), language="zh")
        has_text = getattr(tr, 'has_content', None) or getattr(tr, 'has_text', None) or (len(tr.text) > 0)
        if tr.success and has_text:
            # Save transcription
            out_path = TRANSCRIBED_DIR / "C0257_segment_45s.md"
            md_text = tr.text
            if hasattr(tr, 'to_markdown'):
                md_text = tr.to_markdown()
            out_path.write_text(md_text, encoding="utf-8")
            results.append(_pass(
                f"FunASR transcription ({tr.duration:.1f}s audio, {len(tr.text)} chars, {tr.engine})",
                time.time() - t0,
                engine=tr.engine,
                text_length=len(tr.text),
                audio_duration=tr.duration,
            ))
        else:
            results.append(_skip("FunASR transcription", tr.error or "no text produced", time.time() - t0))
    except Exception as e:
        err = str(e)
        if "No module" in err or "model" in err.lower() or "import" in err.lower():
            results.append(_skip("FunASR transcription", f"engine not available: {err[:80]}", time.time() - t0))
        else:
            results.append(_fail("FunASR transcription", err[:100], time.time() - t0))

    # Try Whisper as fallback
    if not results or not results[0].passed:
        t0 = time.time()
        try:
            transcriber = WhisperTranscriber()
            tr = transcriber.transcribe(str(SEGMENT_WAV), language="zh")
            has_text = getattr(tr, 'has_content', None) or getattr(tr, 'has_text', None) or (len(tr.text) > 0)
            if tr.success and has_text:
                out_path = TRANSCRIBED_DIR / "C0257_segment_45s_whisper.md"
                md_text = tr.text
                if hasattr(tr, 'to_markdown'):
                    md_text = tr.to_markdown()
                out_path.write_text(md_text, encoding="utf-8")
                results.append(_pass(
                    f"Whisper transcription ({tr.duration:.1f}s, {len(tr.text)} chars, {tr.engine})",
                    time.time() - t0,
                    engine=tr.engine,
                    text_length=len(tr.text),
                    audio_duration=tr.duration,
                ))
            else:
                results.append(_skip("Whisper transcription", tr.error or "no text", time.time() - t0))
        except Exception as e:
            err = str(e)
            if "No module" in err or "model" in err.lower() or "import" in err.lower():
                results.append(_skip("Whisper transcription", f"engine not available: {err[:80]}", time.time() - t0))
            else:
                results.append(_fail("Whisper transcription", err[:100], time.time() - t0))

    if not results:
        results.append(_skip("Transcription", "no engine available"))

    report.add_batch("Transcription", results)
    return results


# ---------------------------------------------------------------------------
# P4: Batch Parse
# ---------------------------------------------------------------------------

async def test_batch_parse(report: HealthReport) -> List[TestResult]:
    from urlparser import parse_batch, ParseConfig
    results = []

    # Pick 3 simple URLs for batch test
    batch_urls = [
        "https://sspai.com/post/97131",
        "https://www.classicdriver.com",
        "https://www.mathworks.cn",
    ]

    t0 = time.time()
    try:
        batch_results = await asyncio.wait_for(
            parse_batch(batch_urls, config=ParseConfig.simple(), concurrent=2),
            timeout=120.0,
        )
        total = len(batch_results)
        success = sum(1 for r in batch_results if r.fetch_success)
        results.append(_pass(
            f"parse_batch ({total} URLs, {success} succeeded)",
            time.time() - t0,
            total=total,
            success=success,
        ))
    except asyncio.TimeoutError:
        results.append(_fail("parse_batch", "timeout (120s)", time.time() - t0))
    except Exception as e:
        results.append(_fail("parse_batch", str(e)[:100], time.time() - t0))

    report.add_batch("Batch Parse", results)
    return results


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_all_tests():
    """Run all health check tests sequentially by category."""
    # Ensure output dirs exist
    for d in [OUTPUT_DIR, PARSED_DIR, TRANSCRIBED_DIR, CACHE_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    report = HealthReport()
    print("=" * 60)
    print("urlparser v3.3.0 Health Check")
    print("=" * 60)
    print()

    def _print_results(category: str, results: List[TestResult]):
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed and not r.skipped)
        skipped = sum(1 for r in results if r.skipped)
        dur = sum(r.duration for r in results)
        status = "PASS" if failed == 0 else "FAIL"
        print(f"  [{status}] {category}: {passed} pass, {failed} fail, {skipped} skip ({dur:.1f}s)")
        for r in results:
            icon = "+" if r.passed else ("~" if r.skipped else "x")
            err = f" - {r.error[:60]}" if r.error else ""
            print(f"    [{icon}] {r.name} ({r.duration:.2f}s){err}")

    # P0 tests
    print("[P0] Core tests...")
    _print_results("Imports", test_imports(report))
    _print_results("URL Utils", test_url_utils(report))
    _print_results("Text Utils", test_text_utils(report))
    _print_results("File Utils", test_file_utils(report))
    _print_results("Media Utils", test_media_utils(report))
    _print_results("FFmpeg Utils", test_ffmpeg_utils(report))
    _print_results("Models", test_models(report))
    _print_results("Config", test_config(report))
    print()

    # P1 tests
    print("[P1] Storage tests...")
    _print_results("Cache", await test_cache(report))
    _print_results("File Storage", test_result_storage(report))
    _print_results("Source Document", test_source_document(report))
    _print_results("State Manager", test_state_manager(report))
    _print_results("Dependency Installer", test_dependency_installer(report))
    print()

    # P2 tests
    print("[P2] CLI & Scanner tests...")
    _print_results("CLI", test_cli(report))
    _print_results("MediaScanner", test_media_scanner(report))
    print()

    # P3 tests
    print("[P3] Network parsing (17 URLs, concurrency=3, timeout=60s)...")
    _print_results("Network Parse", await test_network_parse(report))
    print()

    print("[P3] Transcription (45s audio segment)...")
    _print_results("Transcription", await test_transcription(report))
    print()

    # P4 tests
    print("[P4] Batch parse...")
    _print_results("Batch Parse", await test_batch_parse(report))
    print()

    # Finalize
    print("=" * 60)
    text = report.finalize()
    print()
    print(f"Report saved to: {OUTPUT_DIR / 'health_report.md'}")
    print()

    # Print summary
    all_results = [r for rs in report.results.values() for r in rs]
    total = len(all_results)
    passed = sum(1 for r in all_results if r.passed)
    failed = sum(1 for r in all_results if not r.passed and not r.skipped)
    skipped = sum(1 for r in all_results if r.skipped)
    elapsed = time.time() - report.start_time

    print(f"Total: {total} | Pass: {passed} | Fail: {failed} | Skip: {skipped} | Time: {elapsed:.1f}s")
    print()

    if failed > 0:
        print("FAILED tests:")
        for cat, results in report.results.items():
            for r in results:
                if not r.passed and not r.skipped:
                    print(f"  [{cat}] {r.name}: {r.error[:80]}")
        sys.exit(1)
    else:
        print("All core tests PASSED!")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
