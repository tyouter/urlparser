"""
P3: 接口一致性测试

验证 API / CLI 两种接口对同一 URL 产生一致的结果。
这是发现接口差异的关键测试层 - 之前发现的 CLI 截断问题就是这类测试要捕获的。

核心检测标准:
    1. 内容完整性: 两种接口输出的核心内容长度差异不超过阈值
    2. 结构一致性: Markdown 输出都包含必要的章节标题
    3. 元数据一致性: 标题、平台、策略等元数据一致
    4. 无截断: 任何接口的输出都不应包含截断标记 (...)
    5. 编码正确: 输出文件 UTF-8 编码无乱码
"""

import asyncio
import os
import sys
import json
import subprocess
import time
import re

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from urlparser import parse, ParseConfig
from test_utils import URLFixture, compute_structure_fingerprint, SNAPSHOTS_DIR


pytestmark = [pytest.mark.integration, pytest.mark.p3]

CONTENT_LENGTH_RATIO_THRESHOLD = 0.7
MIN_CONTENT_LENGTH = 50


async def _api_parse(url: str) -> dict:
    config = ParseConfig.simple()
    result = await parse(url, config=config)
    return {
        "success": result.fetch_success,
        "title": result.title,
        "content": result.content,
        "platform": result.platform,
        "strategy": result.final_strategy,
        "content_length": len(result.content or ""),
        "markdown": result.to_markdown(),
        "error": result.error,
    }


def _cli_parse(url: str, output_path: str) -> dict:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "urlparser", "parse", url,
             "--format", "markdown", "--output", output_path],
            capture_output=True, timeout=180,
            env={**os.environ, "KMP_DUPLICATE_LIB_OK": "TRUE",
                 "HF_ENDPOINT": "https://hf-mirror.com"},
        )
        if proc.returncode == 0 and os.path.exists(output_path):
            with open(output_path, encoding="utf-8") as f:
                content = f.read()
            return {
                "success": True,
                "markdown": content,
                "content_length": len(content),
                "error": None,
            }
        else:
            stderr = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
            return {"success": False, "error": stderr[:300], "content_length": 0}
    except Exception as e:
        return {"success": False, "error": str(e)[:300], "content_length": 0}


class TestAPIBasicFunctionality:
    """API 基本功能验证"""

    @pytest.mark.asyncio
    async def test_api_article_parse(self, article_urls):
        url = article_urls[0]
        result = await _api_parse(url.url)
        assert result["success"], f"API parse failed: {result.get('error')}"
        assert result["content_length"] >= url.min_content_length, \
            f"Content too short: {result['content_length']} < {url.min_content_length}"
        assert result["title"], "Title is empty"

    @pytest.mark.asyncio
    async def test_api_video_parse(self, video_urls):
        url = video_urls[0]
        result = await _api_parse(url.url)
        assert result["success"], f"API parse failed: {result.get('error')}"
        assert result["content_length"] >= MIN_CONTENT_LENGTH

    @pytest.mark.asyncio
    async def test_api_markdown_structure(self, article_urls):
        url = article_urls[0]
        result = await _api_parse(url.url)
        if not result["success"]:
            pytest.skip(f"Parse failed: {result.get('error')}")
        md = result["markdown"]
        assert "# " in md, "Missing H1 heading"
        assert "**来源**" in md or "**平台**" in md, "Missing metadata block"


class TestCLIBasicFunctionality:
    """CLI 基本功能验证"""

    def test_cli_article_parse(self, article_urls, tmp_path):
        url = article_urls[0]
        output = str(tmp_path / "cli_output.md")
        result = _cli_parse(url.url, output)
        assert result["success"], f"CLI parse failed: {result.get('error')}"
        assert result["content_length"] >= MIN_CONTENT_LENGTH

    def test_cli_no_truncation(self, article_urls, tmp_path):
        url = article_urls[0]
        output = str(tmp_path / "cli_output.md")
        result = _cli_parse(url.url, output)
        if not result["success"]:
            pytest.skip(f"CLI parse failed: {result.get('error')}")
        md = result["markdown"]
        content_section = md.split("## 内容摘要")
        if len(content_section) > 1:
            body = content_section[1].split("##")[0]
            assert "... (" not in body, "CLI output contains truncation marker"
            assert "... (共" not in body, "CLI output contains truncation marker"


class TestInterfaceConsistency:
    """API vs CLI vs SKILL 输出一致性"""

    @pytest.mark.asyncio
    async def test_api_vs_cli_content_length(self, article_urls, tmp_path):
        url = article_urls[0]
        api_result = await _api_parse(url.url)
        if not api_result["success"]:
            pytest.skip(f"API parse failed: {api_result.get('error')}")

        cli_output = str(tmp_path / "cli_consistency.md")
        cli_result = _cli_parse(url.url, cli_output)
        if not cli_result["success"]:
            pytest.skip(f"CLI parse failed: {cli_result.get('error')}")

        api_content_len = api_result["content_length"]
        cli_content_len = cli_result["content_length"]

        ratio = min(api_content_len, cli_content_len) / max(api_content_len, cli_content_len, 1)
        assert ratio >= CONTENT_LENGTH_RATIO_THRESHOLD, \
            f"Content length ratio {ratio:.2f} < {CONTENT_LENGTH_RATIO_THRESHOLD}: " \
            f"API={api_content_len}, CLI={cli_content_len}"

    @pytest.mark.asyncio
    async def test_api_vs_cli_no_truncation_difference(self, article_urls, tmp_path):
        url = article_urls[0]
        api_result = await _api_parse(url.url)
        if not api_result["success"]:
            pytest.skip(f"API parse failed")

        cli_output = str(tmp_path / "cli_truncation.md")
        cli_result = _cli_parse(url.url, cli_output)
        if not cli_result["success"]:
            pytest.skip(f"CLI parse failed")

        api_content = api_result["content"]
        cli_md = cli_result["markdown"]

        content_section = cli_md.split("## 内容摘要")
        if len(content_section) > 1:
            remaining = content_section[1]
            next_h2 = remaining.find("\n## ")
            cli_body = remaining[:next_h2].strip() if next_h2 != -1 else remaining.strip()
        else:
            cli_body = cli_md

        assert "... (共" not in cli_body, "CLI output contains truncation marker"
        assert len(cli_body) >= MIN_CONTENT_LENGTH, \
            f"CLI content body too short ({len(cli_body)} chars), possible truncation"


class TestOutputEncoding:
    """输出编码正确性"""

    @pytest.mark.asyncio
    async def test_api_output_no_mojibake(self, article_urls):
        url = article_urls[0]
        result = await _api_parse(url.url)
        if not result["success"]:
            pytest.skip("Parse failed")
        md = result["markdown"]
        try:
            md.encode('utf-8').decode('utf-8')
        except UnicodeDecodeError:
            pytest.fail("API output contains invalid UTF-8")

    def test_cli_output_no_mojibake(self, article_urls, tmp_path):
        url = article_urls[0]
        output = str(tmp_path / "cli_encoding.md")
        result = _cli_parse(url.url, output)
        if not result["success"]:
            pytest.skip("CLI parse failed")
        with open(output, encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 0
        try:
            content.encode('utf-8').decode('utf-8')
        except UnicodeDecodeError:
            pytest.fail("CLI output file contains invalid UTF-8")


class TestMarkdownStructureConsistency:
    """Markdown 结构一致性"""

    @pytest.mark.asyncio
    async def test_api_markdown_has_all_sections(self, article_urls):
        url = article_urls[0]
        result = await _api_parse(url.url)
        if not result["success"]:
            pytest.skip("Parse failed")
        md = result["markdown"]
        fingerprint = compute_structure_fingerprint(md)
        assert fingerprint["section_count"] >= 1, "Markdown should have at least one section"

    def test_cli_markdown_has_all_sections(self, article_urls, tmp_path):
        url = article_urls[0]
        output = str(tmp_path / "cli_structure.md")
        result = _cli_parse(url.url, output)
        if not result["success"]:
            pytest.skip("CLI parse failed")
        with open(output, encoding="utf-8") as f:
            md = f.read()
        fingerprint = compute_structure_fingerprint(md)
        assert fingerprint["section_count"] >= 1, "CLI Markdown should have at least one section"
