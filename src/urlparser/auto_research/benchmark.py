"""
Auto Research Efficiency Benchmark

Measures parse throughput and latency:
    - Non-video URLs: >= 10 parses/minute
    - Video URLs: parse time <= video_duration / 10
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict

from .dataset import URLEntry


@dataclass
class BenchmarkResult:
    url: str
    platform: str
    is_video: bool
    parse_time: float
    content_length: int
    success: bool
    video_duration: float = 0.0
    efficiency_ratio: float = 0.0

    @property
    def time_efficient(self) -> bool:
        if not self.success:
            return False
        if self.is_video and self.video_duration > 0:
            return self.efficiency_ratio <= 0.1
        return True


@dataclass
class PlatformBenchmark:
    platform: str
    is_video_platform: bool = False
    total: int = 0
    successful: int = 0
    total_time: float = 0.0
    parses_per_minute: float = 0.0
    avg_parse_time: float = 0.0
    video_efficiency_pass: int = 0
    video_efficiency_fail: int = 0
    video_efficiency_rate: float = 1.0

    def compute(self, results: List[BenchmarkResult]):
        self.total = len(results)
        successful = [r for r in results if r.success]
        self.successful = len(successful)
        self.total_time = sum(r.parse_time for r in successful)
        self.avg_parse_time = (
            self.total_time / self.successful if self.successful else 0
        )
        if self.total_time > 0:
            self.parses_per_minute = self.successful / (self.total_time / 60)

        video_results = [r for r in successful if r.is_video and r.video_duration > 0]
        if video_results:
            self.video_efficiency_pass = sum(1 for r in video_results if r.time_efficient)
            self.video_efficiency_fail = len(video_results) - self.video_efficiency_pass
            self.video_efficiency_rate = (
                self.video_efficiency_pass / len(video_results)
            )


@dataclass
class BenchmarkVerdict:
    non_video_ppm: float = 0.0
    target_ppm: float = 10.0
    video_efficiency_rate: float = 1.0
    target_video_ratio: float = 0.1
    platform_benchmarks: Dict[str, PlatformBenchmark] = field(default_factory=dict)
    overall_ppm: float = 0.0
    benchmark_pass: bool = False
    failures: List[Dict] = field(default_factory=list)

    def check(self) -> bool:
        failures = []

        if self.non_video_ppm < self.target_ppm:
            failures.append({
                "rule": "non_video_throughput",
                "expected": f">= {self.target_ppm:.0f} parses/min",
                "actual": f"{self.non_video_ppm:.1f} parses/min",
                "severity": "HIGH",
            })

        for p, bm in self.platform_benchmarks.items():
            if not bm.is_video_platform and bm.successful > 0:
                if bm.parses_per_minute < self.target_ppm:
                    failures.append({
                        "rule": "platform_throughput",
                        "platform": p,
                        "expected": f">= {self.target_ppm:.0f} parses/min",
                        "actual": f"{bm.parses_per_minute:.1f} parses/min",
                        "severity": "MEDIUM",
                    })
            if bm.is_video_platform and bm.video_efficiency_rate < 0.95:
                failures.append({
                    "rule": "video_efficiency",
                    "platform": p,
                    "expected": f">= 95% within {self.target_video_ratio:.0%} of duration",
                    "actual": f"{bm.video_efficiency_rate:.0%}",
                    "severity": "MEDIUM",
                })

        self.failures = failures
        self.benchmark_pass = len(failures) == 0
        return self.benchmark_pass


class EfficiencyBenchmark:
    def __init__(
        self,
        target_ppm: float = 10.0,
        target_video_ratio: float = 0.1,
    ):
        self.target_ppm = target_ppm
        self.target_video_ratio = target_video_ratio
        self.results: List[BenchmarkResult] = []

    def record(
        self,
        entry: URLEntry,
        parse_result,
        parse_time: float,
    ) -> BenchmarkResult:
        success = getattr(parse_result, 'fetch_success', False)
        content_length = len(getattr(parse_result, 'content', '') or '')

        video_duration = 0.0
        if entry.is_video and success:
            transcription = getattr(parse_result, 'transcription', None)
            if transcription and getattr(transcription, 'success', False):
                video_duration = getattr(transcription, 'duration', 0.0)

            if video_duration <= 0:
                video_metadata = getattr(parse_result, 'video_metadata', None)
                if video_metadata:
                    dur_str = getattr(video_metadata, 'duration', '') or ''
                    video_duration = self._parse_duration(dur_str)

        efficiency_ratio = (
            parse_time / video_duration if video_duration > 0 else 0
        )

        result = BenchmarkResult(
            url=entry.url,
            platform=entry.platform,
            is_video=entry.is_video,
            parse_time=parse_time,
            content_length=content_length,
            success=success,
            video_duration=video_duration,
            efficiency_ratio=efficiency_ratio,
        )
        self.results.append(result)
        return result

    @staticmethod
    def _parse_duration(dur_str: str) -> float:
        if not dur_str:
            return 0.0
        dur_str = dur_str.strip().rstrip('s')
        try:
            return float(dur_str)
        except ValueError:
            pass
        parts = dur_str.split(':')
        try:
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
        except (ValueError, IndexError):
            pass
        return 0.0

    def verdict(self) -> BenchmarkVerdict:
        v = BenchmarkVerdict(
            target_ppm=self.target_ppm,
            target_video_ratio=self.target_video_ratio,
        )

        non_video = [r for r in self.results if r.success and not r.is_video]
        if non_video:
            total_time = sum(r.parse_time for r in non_video)
            v.non_video_ppm = len(non_video) / (total_time / 60) if total_time > 0 else 0

        all_successful = [r for r in self.results if r.success]
        if all_successful:
            total_time = sum(r.parse_time for r in all_successful)
            v.overall_ppm = len(all_successful) / (total_time / 60) if total_time > 0 else 0

        by_platform: Dict[str, List[BenchmarkResult]] = defaultdict(list)
        for r in self.results:
            by_platform[r.platform].append(r)

        VIDEO_PLATFORMS = {"bilibili", "youtube"}
        for p, results in by_platform.items():
            bm = PlatformBenchmark(
                platform=p,
                is_video_platform=p in VIDEO_PLATFORMS,
            )
            bm.compute(results)
            v.platform_benchmarks[p] = bm

        v.check()
        return v

    def reset(self):
        self.results = []
