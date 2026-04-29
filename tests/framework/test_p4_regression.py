"""
P4: 回归快照测试

核心思想: 将解析结果的结构指纹保存为快照基准，后续运行时对比。
如果结构发生意外变化（如章节丢失、内容截断、格式变更），测试失败。

与简单字符串快照不同，我们使用「结构指纹」:
    - 不比对完整内容（内容会随源站更新而变化）
    - 比对结构特征：章节数、标题列表、内容长度范围、内容哈希
    - 允许内容自然变化，但捕获结构性回归

运行方式:
    pytest tests/framework/test_p4_regression.py          # 对比快照
    pytest tests/framework/test_p4_regression.py --snapshot-update  # 更新快照
"""

import asyncio
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from urlparser import parse, ParseConfig
from test_utils import (
    URLFixture, compute_structure_fingerprint,
    compute_content_hash, SNAPSHOTS_DIR,
)


pytestmark = [pytest.mark.integration, pytest.mark.p4]


def _snapshot_path(test_url: URLFixture) -> str:
    safe_name = test_url.name[:30].replace(" ", "_")
    filename = f"snapshot_{test_url.platform}_{safe_name}.json"
    return str(SNAPSHOTS_DIR / filename)


def _load_snapshot(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_snapshot(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def _get_parse_fingerprint(url: str) -> dict:
    config = ParseConfig.simple()
    result = await parse(url, config=config)

    md = result.to_markdown()
    fingerprint = compute_structure_fingerprint(md)

    return {
        "url": url,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "fetch_success": result.fetch_success,
        "platform": result.platform,
        "content_type": result.content_type.value,
        "title": result.title[:100] if result.title else "",
        "strategy": result.final_strategy,
        "content_length": len(result.content or ""),
        "markdown_length": len(md),
        "fingerprint": fingerprint,
        "error": result.error,
    }


class TestRegressionSnapshots:
    """回归快照测试 - 对比当前结果与历史基准"""

    @pytest.mark.asyncio
    async def test_article_snapshots(self, article_urls, snapshot_update):
        regressions = []

        for test_url in article_urls:
            current = await _get_parse_fingerprint(test_url.url)
            snap_path = _snapshot_path(test_url)

            if snapshot_update:
                _save_snapshot(snap_path, current)
                continue

            baseline = _load_snapshot(snap_path)

            if not baseline:
                _save_snapshot(snap_path, current)
                continue

            if not current["fetch_success"]:
                continue

            checks = _compare_snapshots(baseline, current, test_url)
            regressions.extend(checks)

        if regressions and not snapshot_update:
            report_lines = ["\n=== REGRESSION REPORT ===\n"]
            for r in regressions:
                report_lines.append(f"  [{r['severity']}] {r['check']}: {r['message']}")
            report_lines.append("\nRun with --snapshot-update to accept changes.")
            pytest.fail("\n".join(report_lines))

    @pytest.mark.asyncio
    async def test_video_snapshots(self, video_urls, snapshot_update):
        for test_url in video_urls:
            current = await _get_parse_fingerprint(test_url.url)
            snap_path = _snapshot_path(test_url)

            if snapshot_update:
                _save_snapshot(snap_path, current)
                continue

            baseline = _load_snapshot(snap_path)
            if not baseline:
                _save_snapshot(snap_path, current)


def _compare_snapshots(
    baseline: dict, current: dict, test_url: URLFixture
) -> list:
    """对比快照，返回回归列表"""
    regressions = []

    if not current["fetch_success"] and baseline.get("fetch_success"):
        regressions.append({
            "severity": "CRITICAL",
            "check": "fetch_success",
            "message": f"Previously successful URL now fails: {current.get('error', 'unknown')}",
        })
        return regressions

    b_fp = baseline.get("fingerprint", {})
    c_fp = current.get("fingerprint", {})

    if c_fp.get("section_count", 0) < b_fp.get("section_count", 0):
        regressions.append({
            "severity": "HIGH",
            "check": "section_count",
            "message": f"Sections decreased: {b_fp['section_count']} → {c_fp['section_count']}",
        })

    baseline_sections = set(b_fp.get("section_titles", []))
    current_sections = set(c_fp.get("section_titles", []))
    missing = baseline_sections - current_sections
    if missing:
        regressions.append({
            "severity": "HIGH",
            "check": "missing_sections",
            "message": f"Missing sections: {missing}",
        })

    b_len = baseline.get("content_length", 0)
    c_len = current.get("content_length", 0)
    if b_len > 0 and c_len > 0:
        ratio = c_len / b_len
        if ratio < 0.5:
            regressions.append({
                "severity": "CRITICAL",
                "check": "content_length_regression",
                "message": f"Content length dropped significantly: {b_len} → {c_len} ({ratio:.1%})",
            })
        elif ratio < 0.7:
            regressions.append({
                "severity": "MEDIUM",
                "check": "content_length_regression",
                "message": f"Content length decreased: {b_len} → {c_len} ({ratio:.1%})",
            })

    if c_len < test_url.min_content_length:
        regressions.append({
            "severity": "HIGH",
            "check": "min_content_length",
            "message": f"Below minimum: {c_len} < {test_url.min_content_length}",
        })

    b_md_len = baseline.get("markdown_length", 0)
    c_md_len = current.get("markdown_length", 0)
    if b_md_len > 0 and c_md_len > 0:
        md_ratio = c_md_len / b_md_len
        if md_ratio < 0.5:
            regressions.append({
                "severity": "HIGH",
                "check": "markdown_length_regression",
                "message": f"Markdown length dropped: {b_md_len} → {c_md_len} ({md_ratio:.1%})",
            })

    return regressions


class TestContentIntegrity:
    """内容完整性专项检测 - 不依赖快照"""

    @pytest.mark.asyncio
    async def test_no_truncation_in_markdown(self, article_urls):
        config = ParseConfig.simple()
        for test_url in article_urls:
            result = await parse(test_url.url, config=config)
            if not result.fetch_success:
                continue

            md = result.to_markdown()
            content_section = md.split("## 内容摘要")
            if len(content_section) > 1:
                body = content_section[1].split("##")[0]
                assert "... (共" not in body, \
                    f"[{test_url.platform}] Content truncated with '... (共'"
                assert "... (" not in body or "..." in result.content, \
                    f"[{test_url.platform}] Suspicious truncation marker in output"

    @pytest.mark.asyncio
    async def test_content_matches_raw(self, article_urls):
        """验证 to_markdown() 输出的内容与 result.content 一致"""
        config = ParseConfig.simple()
        for test_url in article_urls:
            result = await parse(test_url.url, config=config)
            if not result.fetch_success or not result.content:
                continue

            md = result.to_markdown()
            assert result.content in md, \
                f"[{test_url.platform}] result.content not found in to_markdown() output"

    @pytest.mark.asyncio
    async def test_all_urls_fetch_success(self, test_urls):
        config = ParseConfig.simple()
        failures = []
        for test_url in test_urls:
            result = await parse(test_url.url, config=config)
            if not result.fetch_success:
                failures.append(f"[{test_url.platform}] {test_url.name}: {result.error}")

        if failures:
            pytest.fail(f"Fetch failures:\n" + "\n".join(failures))
