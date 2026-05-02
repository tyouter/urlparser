"""
Auto Research Runner

Orchestrates iterative research cycles:
    1. Build/load dataset
    2. Parse all URLs with configurable concurrency
    3. Run acceptance criteria check
    4. Run efficiency benchmark
    5. Generate comprehensive report

Usage:
    runner = ResearchRunner()
    report = await runner.run()
    print(report)
"""

import asyncio
import json
import time
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from .dataset import DatasetBuilder, URLEntry
from .acceptance import AcceptanceChecker, AcceptanceVerdict
from .benchmark import EfficiencyBenchmark, BenchmarkVerdict


OUTPUT_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "auto_research"
DATASET_PATH = OUTPUT_DIR / "url_dataset.json"
REPORT_PATH = OUTPUT_DIR / "research_report.md"


@dataclass
class ResearchReport:
    timestamp: str = ""
    duration: float = 0.0
    dataset_total: int = 0
    dataset_platforms: Dict[str, int] = field(default_factory=dict)
    acceptance: Optional[dict] = None
    benchmark: Optional[dict] = None
    acceptance_pass: bool = False
    benchmark_pass: bool = False
    overall_pass: bool = False
    failures: List[Dict] = field(default_factory=list)
    platform_details: List[Dict] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            f"# urlparser Auto Research Report",
            f"",
            f"> Generated: {self.timestamp}",
            f"> Duration: {self.duration:.1f}s",
            f"> Dataset: {self.dataset_total} URLs across {len(self.dataset_platforms)} platforms",
            f"",
        ]

        status = "PASS" if self.overall_pass else "FAIL"
        lines.append(f"## Overall Verdict: **{status}**")
        lines.append("")

        if self.failures:
            lines.append("### Failures")
            lines.append("")
            for f in self.failures:
                lines.append(
                    f"- [{f.get('severity', '?')}] **{f.get('rule', '?')}**: "
                    f"expected {f.get('expected', '?')}, got {f.get('actual', '?')}"
                    + (f" (platform: {f['platform']})" if 'platform' in f else "")
                )
            lines.append("")

        lines.append("## Acceptance Criteria")
        lines.append("")
        if self.acceptance:
            acc = self.acceptance
            lines.append(f"- Total URLs: {acc.get('total_urls', 0)}")
            lines.append(f"- Passed: {acc.get('total_passed', 0)}")
            lines.append(f"- Overall Success Rate: {acc.get('overall_success_rate', 0):.2%}")
            lines.append(f"- Platforms Tested: {acc.get('platforms_tested', 0)}")
            lines.append(f"- Acceptance: {'PASS' if self.acceptance_pass else 'FAIL'}")
            lines.append("")

        if self.platform_details:
            lines.append("### Per-Platform Breakdown")
            lines.append("")
            lines.append("| Platform | Total | Passed | Rate | Avg Time | Issues |")
            lines.append("|----------|-------|--------|------|----------|--------|")
            for pd in self.platform_details:
                issues = []
                if pd.get("no_title", 0) > 0:
                    issues.append(f"no_title:{pd['no_title']}")
                if pd.get("content_too_short", 0) > 0:
                    issues.append(f"short:{pd['content_too_short']}")
                if pd.get("parse_errors", 0) > 0:
                    issues.append(f"errors:{pd['parse_errors']}")
                if pd.get("video_no_transcription", 0) > 0:
                    issues.append(f"no_trans:{pd['video_no_transcription']}")
                if pd.get("video_transcription_incomplete", 0) > 0:
                    issues.append(f"trans_inc:{pd['video_transcription_incomplete']}")
                lines.append(
                    f"| {pd['platform']} | {pd['total']} | {pd['passed']} | "
                    f"{pd.get('acceptance_rate', 0):.1%} | "
                    f"{pd.get('avg_parse_time', 0):.1f}s | "
                    f"{', '.join(issues) or '-'} |"
                )
            lines.append("")

        lines.append("## Efficiency Benchmark")
        lines.append("")
        if self.benchmark:
            bm = self.benchmark
            lines.append(f"- Non-video throughput: {bm.get('non_video_ppm', 0):.1f} parses/min (target: >= 10)")
            lines.append(f"- Overall throughput: {bm.get('overall_ppm', 0):.1f} parses/min")
            lines.append(f"- Benchmark: {'PASS' if self.benchmark_pass else 'FAIL'}")
            lines.append("")

            if bm.get("platform_benchmarks"):
                lines.append("### Per-Platform Throughput")
                lines.append("")
                lines.append("| Platform | Parsed | PPM | Avg Time | Video Eff. |")
                lines.append("|----------|--------|-----|----------|------------|")
                for p, pb in bm["platform_benchmarks"].items():
                    vid_eff = (
                        f"{pb.get('video_efficiency_rate', 1.0):.0%}"
                        if pb.get("is_video_platform") else "N/A"
                    )
                    lines.append(
                        f"| {p} | {pb.get('successful', 0)} | "
                        f"{pb.get('parses_per_minute', 0):.1f} | "
                        f"{pb.get('avg_parse_time', 0):.1f}s | {vid_eff} |"
                    )
                lines.append("")

        lines.append("---")
        lines.append(f"*Generated by urlparser auto_research v3.3.0*")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2, default=str)


class ResearchRunner:
    def __init__(
        self,
        target_success_rate: float = 0.99,
        min_dataset_size: int = 500,
        target_ppm: float = 10.0,
        target_video_ratio: float = 0.1,
        max_concurrent: int = 3,
        quick_mode: bool = False,
        quick_sample: int = 50,
    ):
        self.target_success_rate = target_success_rate
        self.min_dataset_size = min_dataset_size
        self.target_ppm = target_ppm
        self.target_video_ratio = target_video_ratio
        self.max_concurrent = max_concurrent
        self.quick_mode = quick_mode
        self.quick_sample = quick_sample

        self.acceptance = AcceptanceChecker(
            target_success_rate=target_success_rate,
            min_dataset_size=min_dataset_size,
        )
        self.benchmark = EfficiencyBenchmark(
            target_ppm=target_ppm,
            target_video_ratio=target_video_ratio,
        )

    async def run(
        self,
        dataset_path: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> ResearchReport:
        start_time = time.time()
        report = ResearchReport(timestamp=datetime.now().isoformat())

        print("=" * 70)
        print("urlparser Auto Research")
        if self.quick_mode:
            print(f"  Mode: QUICK ({self.quick_sample} URLs)")
        else:
            print(f"  Mode: FULL")
        print(f"  Target success rate: >= {self.target_success_rate:.0%}")
        print(f"  Target throughput: >= {self.target_ppm} parses/min")
        print("=" * 70)

        print("\n[1/4] Building dataset...")
        entries = self._build_dataset(dataset_path)
        report.dataset_total = len(entries)
        report.dataset_platforms = dict(
            defaultdict(int, {e.platform: sum(1 for x in entries if x.platform == e.platform) for e in entries})
        )
        counts = defaultdict(int)
        for e in entries:
            counts[e.platform] += 1
        report.dataset_platforms = dict(counts)

        if self.quick_mode and len(entries) > self.quick_sample:
            import random
            random.seed(42)
            entries = random.sample(entries, self.quick_sample)
            print(f"  Quick mode: sampled {len(entries)} URLs")

        print(f"  Dataset: {report.dataset_total} URLs, {len(counts)} platforms")
        for p in sorted(counts.keys()):
            print(f"    {p}: {counts[p]}")

        print("\n[2/4] Parsing URLs...")
        results = await self._parse_all(entries)

        print("\n[3/4] Running acceptance check...")
        acc_verdict = self.acceptance.verdict()
        report.acceptance = {
            "total_urls": acc_verdict.total_urls,
            "total_passed": acc_verdict.total_passed,
            "overall_success_rate": acc_verdict.overall_success_rate,
            "platforms_tested": acc_verdict.platforms_tested,
            "platforms_required": acc_verdict.platforms_required,
            "min_platform_rate": acc_verdict.min_platform_rate,
            "worst_platform": acc_verdict.worst_platform,
        }
        report.acceptance_pass = acc_verdict.acceptance_pass
        report.platform_details = []
        for p, pr in sorted(acc_verdict.platform_reports.items()):
            report.platform_details.append({
                "platform": p,
                "total": pr.total,
                "passed": pr.passed,
                "acceptance_rate": pr.acceptance_rate,
                "avg_parse_time": pr.avg_parse_time,
                "no_title": pr.no_title,
                "no_content": pr.no_content,
                "content_too_short": pr.content_too_short,
                "parse_errors": pr.parse_errors,
                "video_total": pr.video_total,
                "video_no_transcription": pr.video_no_transcription,
                "video_transcription_incomplete": pr.video_transcription_incomplete,
            })

        print("\n[4/4] Running efficiency benchmark...")
        bm_verdict = self.benchmark.verdict()
        report.benchmark = {
            "non_video_ppm": bm_verdict.non_video_ppm,
            "overall_ppm": bm_verdict.overall_ppm,
            "target_ppm": bm_verdict.target_ppm,
            "platform_benchmarks": {
                p: {
                    "platform": bm.platform,
                    "is_video_platform": bm.is_video_platform,
                    "successful": bm.successful,
                    "parses_per_minute": bm.parses_per_minute,
                    "avg_parse_time": bm.avg_parse_time,
                    "video_efficiency_rate": bm.video_efficiency_rate,
                }
                for p, bm in bm_verdict.platform_benchmarks.items()
            },
        }
        report.benchmark_pass = bm_verdict.benchmark_pass

        all_failures = list(acc_verdict.failures) + list(bm_verdict.failures)
        report.failures = all_failures
        report.overall_pass = acc_verdict.acceptance_pass and bm_verdict.benchmark_pass
        report.duration = time.time() - start_time

        self._save_report(report, output_dir)

        print("\n" + "=" * 70)
        if report.overall_pass:
            print("RESULT: ALL PASS")
        else:
            print(f"RESULT: {len(all_failures)} FAILURE(S)")
            for f in all_failures[:10]:
                print(f"  [{f.get('severity')}] {f.get('rule')}: {f.get('actual')}")
        print(f"Duration: {report.duration:.1f}s")
        print("=" * 70)

        return report

    def _build_dataset(self, dataset_path: Optional[str] = None) -> List[URLEntry]:
        path = dataset_path or str(DATASET_PATH)

        if os.path.exists(path):
            print(f"  Loading existing dataset: {path}")
            return DatasetBuilder.load_json(path)

        print("  Building new dataset from source files...")
        builder = DatasetBuilder()
        entries = builder.build()
        builder.to_json(path)
        print(builder.summary())
        return entries

    async def _parse_all(self, entries: List[URLEntry]) -> list:
        from urlparser import parse, ParseConfig
        from urlparser.config import RetryConfig, TranscribeConfig

        base_config = ParseConfig(
            retry=RetryConfig(
                enabled=False,
                total_timeout=60,
            ),
            browser=ParseConfig.__dataclass_fields__['browser'].default_factory(),
        )
        base_config.browser.timeout = 20000

        semaphore = asyncio.Semaphore(self.max_concurrent)
        results = [None] * len(entries)

        async def _parse_one(idx: int, entry: URLEntry):
            cfg = base_config
            if entry.is_video:
                cfg = ParseConfig(
                    retry=base_config.retry,
                    browser=base_config.browser,
                    scroll=base_config.scroll,
                    transcribe=TranscribeConfig(enabled=True),
                )
                cfg.browser.timeout = 20000

            async with semaphore:
                t0 = time.time()
                try:
                    result = await parse(entry.url, config=cfg)
                except Exception as e:
                    from urlparser.models import ParseResult
                    result = ParseResult(
                        url=entry.url,
                        platform=entry.platform,
                        fetch_success=False,
                        error=str(e),
                    )
                elapsed = time.time() - t0

                self.acceptance.check_single(entry, result)
                self.benchmark.record(entry, result, elapsed)
                results[idx] = result

                status = "OK" if result.fetch_success else "FAIL"
                print(
                    f"  [{status}] [{entry.platform:12s}] {elapsed:5.1f}s "
                    f"{entry.url[:70]}..."
                )

        tasks = [_parse_one(i, e) for i, e in enumerate(entries)]
        await asyncio.gather(*tasks)
        return results

    def _save_report(self, report: ResearchReport, output_dir: Optional[str] = None):
        odir = Path(output_dir) if output_dir else OUTPUT_DIR
        odir.mkdir(parents=True, exist_ok=True)

        md_path = odir / "research_report.md"
        md_path.write_text(report.to_markdown(), encoding="utf-8")
        print(f"\n  Report saved: {md_path}")

        json_path = odir / "research_report.json"
        json_path.write_text(report.to_json(), encoding="utf-8")
        print(f"  JSON saved: {json_path}")
