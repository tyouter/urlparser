"""
Auto Research Acceptance Criteria Checker

Validates parsed results against acceptance criteria:
    1. Parse success rate > 99% per platform and overall
    2. Structural completeness: title + content + platform detected
    3. Content completeness: meets min length thresholds
    4. Video transcription: must have transcription, verified by
       duration/text ratio and closing-phrase detection
    5. Platform coverage: ALL supported platforms tested
    6. Dataset size: >= 500 unique URLs
"""

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from .dataset import URLEntry, PLATFORM_RULES

CLOSING_PHRASES_ZH = [
    r"谢谢大家",
    r"谢谢观看",
    r"感谢大家",
    r"感谢观看",
    r"感谢您的观看",
    r"感谢收听",
    r"感谢支持",
    r"下期再见",
    r"咱们下期再见",
    r"我们下期再见",
    r"下次再见",
    r"拜拜",
    r"再见",
    r"今天就到这里了",
    r"今天就到这了",
    r"今天就先到这里",
    r"点个赞",
    r"点个关注",
    r"点个收藏",
    r"点赞关注",
    r"点赞收藏",
    r"关注我",
    r"关注我们",
    r"别忘了点赞",
    r"别忘了关注",
    r"别忘了收藏",
    r"别忘记点赞",
    r"别忘记关注",
    r"那就这样吧",
    r"那就这样了",
    r"以上就是",
    r"本期节目到这里就结束",
    r"本期视频到这里就结束",
    r"本期结束",
    r"希望对大家有帮助",
    r"希望对你有帮助",
    r"希望这期视频对大家有帮助",
    r"欢迎评论留言",
    r"欢迎在评论区留言",
    r"欢迎留言",
    r"记得点赞",
    r"记得关注",
    r"记得收藏",
    r"我们这期视频就到这里",
    r"咱们这期就到这里",
    r"我们下次再见",
    r"我们下期再见",
]

CLOSING_PHRASES_EN = [
    r"thank[s]?\s+(you\s+)?(for\s+)?(watching|listening|tuning)",
    r"(see|catch)\s+you\s+(next\s+time|later|soon)",
    r"(don't|do\s+not)\s+forget\s+to\s+(like|subscribe|follow)",
    r"(please\s+)?(like|subscribe|follow)\s+(if\s+you\s+)?(enjoyed|liked)",
    r"(that'?s?\s+)?(all|it)\s+(for\s+)?(today|now|this\s+video)",
    r"(until|till)\s+next\s+time",
    r"(hope\s+you\s+)?(enjoyed|liked)\s+(this|the\s+video)",
    r"(be\s+sure\s+to|make\s+sure\s+to)\s+(like|subscribe)",
    r"(stay\s+)?tuned\s+(for\s+)?(more|next)",
    r"that\s+wraps?\s+(it\s+)?up",
    r"(i\s+)?(will\s+)?see\s+you\s+(in\s+)?(the\s+)?next\s+(one|video|episode)",
    r"peace\s+out",
    r"take\s+care",
    r"good\s*(bye|night)",
]

_CLOSING_RE_ZH = re.compile("|".join(CLOSING_PHRASES_ZH), re.IGNORECASE)
_CLOSING_RE_EN = re.compile("|".join(CLOSING_PHRASES_EN), re.IGNORECASE)

MIN_CHARS_PER_SECOND = 1.5
MIN_CHARS_PER_SECOND_LENIENT = 0.8
TRANSCRIPTION_TAIL_WINDOW = 500


def _check_closing_phrase(text: str) -> bool:
    if not text:
        return False
    tail = text[-TRANSCRIPTION_TAIL_WINDOW:]
    if _CLOSING_RE_ZH.search(tail):
        return True
    if _CLOSING_RE_EN.search(tail):
        return True
    return False


def _check_transcription_completeness(
    trans_text: str,
    trans_duration: float,
    strict: bool = True,
) -> Tuple[bool, str]:
    text_len = len(trans_text.strip())
    if text_len == 0:
        return False, "transcription_empty"

    has_closing = _check_closing_phrase(trans_text)

    if trans_duration > 0:
        chars_per_second = text_len / trans_duration
        threshold = MIN_CHARS_PER_SECOND if strict else MIN_CHARS_PER_SECOND_LENIENT

        if chars_per_second >= threshold:
            if has_closing:
                return True, "ratio_pass+closing_detected"
            if chars_per_second >= threshold * 1.5:
                return True, "ratio_strong_pass"
            return True, "ratio_pass_no_closing"

        if has_closing and chars_per_second >= threshold * 0.5:
            return True, "closing_detected+ratio_marginal"

        return False, f"ratio_low({chars_per_second:.1f}<{threshold})"

    if text_len >= 200 and has_closing:
        return True, "text_long+closing_detected"
    if text_len >= 500:
        return True, "text_very_long"

    return False, "text_too_short_no_duration"


@dataclass
class AcceptanceResult:
    url: str
    platform: str
    success: bool
    has_title: bool
    has_content: bool
    platform_detected: bool
    content_length: int
    expected_min_length: int
    content_complete: bool
    structurally_complete: bool
    error: Optional[str] = None
    parse_time: float = 0.0
    is_video: bool = False
    has_transcription: bool = False
    transcription_complete: bool = False
    transcription_reason: str = ""

    @property
    def passed(self) -> bool:
        base = (
            self.success
            and self.structurally_complete
            and self.content_complete
        )
        if self.is_video:
            return base and self.has_transcription and self.transcription_complete
        return base


@dataclass
class PlatformReport:
    platform: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    no_title: int = 0
    no_content: int = 0
    platform_mismatch: int = 0
    content_too_short: int = 0
    parse_errors: int = 0
    avg_parse_time: float = 0.0
    success_rate: float = 0.0
    acceptance_rate: float = 0.0
    video_total: int = 0
    video_no_transcription: int = 0
    video_transcription_incomplete: int = 0

    def compute(self, results: List[AcceptanceResult]):
        if not results:
            return
        self.total = len(results)
        self.passed = sum(1 for r in results if r.passed)
        self.failed = self.total - self.passed
        self.no_title = sum(1 for r in results if not r.has_title)
        self.no_content = sum(1 for r in results if not r.has_content)
        self.platform_mismatch = sum(1 for r in results if not r.platform_detected)
        self.content_too_short = sum(1 for r in results if not r.content_complete)
        self.parse_errors = sum(1 for r in results if not r.success)
        self.video_total = sum(1 for r in results if r.is_video)
        self.video_no_transcription = sum(1 for r in results if r.is_video and not r.has_transcription)
        self.video_transcription_incomplete = sum(
            1 for r in results if r.is_video and r.has_transcription and not r.transcription_complete
        )
        times = [r.parse_time for r in results if r.parse_time > 0]
        self.avg_parse_time = sum(times) / len(times) if times else 0
        self.success_rate = self.passed / self.total if self.total else 0
        self.acceptance_rate = self.passed / self.total if self.total else 0


@dataclass
class AcceptanceVerdict:
    total_urls: int = 0
    total_passed: int = 0
    overall_success_rate: float = 0.0
    platforms_tested: int = 0
    platforms_required: int = 0
    platform_reports: Dict[str, PlatformReport] = field(default_factory=dict)
    min_platform_rate: float = 1.0
    worst_platform: str = ""
    acceptance_pass: bool = False
    failures: List[Dict] = field(default_factory=list)

    def check(
        self,
        target_success_rate: float = 0.99,
        min_dataset_size: int = 500,
        required_platforms: Optional[List[str]] = None,
    ) -> bool:
        if required_platforms is None:
            required_platforms = list(PLATFORM_RULES.keys()) + ["generic"]

        failures = []

        if self.total_urls < min_dataset_size:
            failures.append({
                "rule": "dataset_size",
                "expected": f">= {min_dataset_size}",
                "actual": str(self.total_urls),
                "severity": "CRITICAL",
            })

        if self.overall_success_rate < target_success_rate:
            failures.append({
                "rule": "overall_success_rate",
                "expected": f">= {target_success_rate:.0%}",
                "actual": f"{self.overall_success_rate:.2%}",
                "severity": "CRITICAL",
            })

        tested_platforms = set(self.platform_reports.keys())
        missing = set(required_platforms) - tested_platforms
        if missing:
            failures.append({
                "rule": "platform_coverage",
                "expected": f"All: {sorted(required_platforms)}",
                "actual": f"Missing: {sorted(missing)}",
                "severity": "CRITICAL",
            })

        for p, report in self.platform_reports.items():
            if report.total > 0 and report.acceptance_rate < target_success_rate:
                failures.append({
                    "rule": "platform_acceptance_rate",
                    "platform": p,
                    "expected": f">= {target_success_rate:.0%}",
                    "actual": f"{report.acceptance_rate:.2%}",
                    "severity": "HIGH",
                })

            if report.video_total > 0:
                if report.video_no_transcription > 0:
                    failures.append({
                        "rule": "video_no_transcription",
                        "platform": p,
                        "expected": "all videos must have transcription",
                        "actual": f"{report.video_no_transcription}/{report.video_total} missing",
                        "severity": "CRITICAL",
                    })
                if report.video_transcription_incomplete > 0:
                    failures.append({
                        "rule": "video_transcription_incomplete",
                        "platform": p,
                        "expected": "all transcriptions must be complete",
                        "actual": f"{report.video_transcription_incomplete}/{report.video_total} incomplete",
                        "severity": "HIGH",
                    })

        self.failures = failures
        self.acceptance_pass = len(failures) == 0
        return self.acceptance_pass


class AcceptanceChecker:
    def __init__(
        self,
        target_success_rate: float = 0.99,
        min_dataset_size: int = 500,
    ):
        self.target_success_rate = target_success_rate
        self.min_dataset_size = min_dataset_size
        self.results: List[AcceptanceResult] = []

    def check_single(
        self,
        entry: URLEntry,
        parse_result,
    ) -> AcceptanceResult:
        success = getattr(parse_result, 'fetch_success', False)
        title = getattr(parse_result, 'title', '') or ''
        content = getattr(parse_result, 'content', '') or ''
        platform = getattr(parse_result, 'platform', '') or ''
        error = getattr(parse_result, 'error', None)
        parse_time = getattr(parse_result, 'parse_time', 0.0)
        content_length = len(content)

        has_title = len(title.strip()) >= 2
        has_content = content_length > 0
        platform_detected = platform != '' and platform != 'unknown'

        expected_platform = entry.platform
        if expected_platform == 'x_twitter':
            expected_platform in ['x_twitter', 'x', 'twitter']
        platform_match = (
            platform == expected_platform
            or (expected_platform == 'x_twitter' and platform in ['x', 'twitter', 'x_twitter'])
            or (expected_platform == 'generic' and platform in ['generic', 'default', 'unknown'])
        )

        has_transcription = False
        transcription_complete = False
        transcription_reason = ""

        if entry.is_video and success:
            transcription = getattr(parse_result, 'transcription', None)
            trans_success = transcription and getattr(transcription, 'success', False)

            if trans_success:
                has_transcription = True
                trans_text = getattr(transcription, 'text', '') or ''
                trans_duration = getattr(transcription, 'duration', 0.0)

                complete, reason = _check_transcription_completeness(
                    trans_text, trans_duration, strict=True
                )
                transcription_complete = complete
                transcription_reason = reason
            else:
                trans_error = getattr(transcription, 'error', None) if transcription else "no_transcription"
                transcription_reason = f"transcription_failed({trans_error})"

            content_complete = has_transcription and transcription_complete
        elif success:
            content_complete = content_length >= entry.expected_min_length
        else:
            content_complete = False

        title_required = entry.content_type not in ('video',)
        structurally_complete = (
            (has_title or not title_required)
            and (has_content or (entry.is_video and content_complete))
            and platform_detected
        )

        result = AcceptanceResult(
            url=entry.url,
            platform=entry.platform,
            success=success,
            has_title=has_title,
            has_content=has_content,
            platform_detected=platform_match,
            content_length=content_length,
            expected_min_length=entry.expected_min_length,
            content_complete=content_complete,
            structurally_complete=structurally_complete,
            error=error,
            parse_time=parse_time,
            is_video=entry.is_video,
            has_transcription=has_transcription,
            transcription_complete=transcription_complete,
            transcription_reason=transcription_reason,
        )
        self.results.append(result)
        return result

    def verdict(self) -> AcceptanceVerdict:
        v = AcceptanceVerdict()
        v.total_urls = len(self.results)
        v.total_passed = sum(1 for r in self.results if r.passed)
        v.overall_success_rate = v.total_passed / v.total_urls if v.total_urls else 0

        by_platform: Dict[str, List[AcceptanceResult]] = defaultdict(list)
        for r in self.results:
            by_platform[r.platform].append(r)

        for p, results in by_platform.items():
            report = PlatformReport(platform=p)
            report.compute(results)
            v.platform_reports[p] = report

        v.platforms_tested = len(by_platform)
        v.platforms_required = len(PLATFORM_RULES) + 1

        if by_platform:
            worst_p = min(by_platform.items(), key=lambda x: sum(1 for r in x[1] if r.passed) / len(x[1]) if x[1] else 0)
            v.worst_platform = worst_p[0]
            worst_results = worst_p[1]
            passed = sum(1 for r in worst_results if r.passed)
            v.min_platform_rate = passed / len(worst_results) if worst_results else 0

        v.check(
            target_success_rate=self.target_success_rate,
            min_dataset_size=self.min_dataset_size,
        )
        return v

    def reset(self):
        self.results = []
