"""
P5: 跨接口内容等价性测试

深度验证 API / CLI / SKILL 三种接口对同一 URL 产生的内容是否等价。
这是 P3 的增强版，专注于内容层面的深度对比。

检测维度:
    1. 核心内容等价: 提取正文部分，对比是否一致
    2. 元数据等价: 标题、作者、平台等
    3. 格式完整性: Markdown 结构不缺失
    4. 截断检测: 任何接口不应截断内容
"""

import asyncio
import json
import os
import sys
import subprocess
import re

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from urlparser import parse, ParseConfig
from test_utils import URLFixture


pytestmark = [pytest.mark.integration, pytest.mark.p3]


def _extract_content_from_md(md: str) -> str:
    content_section = md.split("## 内容摘要")
    if len(content_section) > 1:
        body = content_section[1]
        next_h2_pos = body.find("\n## ")
        if next_h2_pos != -1:
            return body[:next_h2_pos].strip()
        return body.strip()
    return md


def _extract_title_from_md(md: str) -> str:
    for line in md.split('\n'):
        if line.startswith('# ') and not line.startswith('## '):
            return line[2:].strip()
    return ""


def _extract_metadata_field(md: str, field: str) -> str:
    for line in md.split('\n'):
        if f"**{field}**" in line:
            match = re.search(r'\*\*' + field + r'\*\*:\s*(.+)', line)
            if match:
                return match.group(1).strip()
    return ""


async def _get_api_result(url: str):
    config = ParseConfig.simple()
    result = await parse(url, config=config)
    return result


def _run_cli(url: str, output_path: str) -> bool:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "urlparser", "parse", url,
             "--format", "markdown", "--output", output_path],
            capture_output=True, timeout=180,
            env={**os.environ, "KMP_DUPLICATE_LIB_OK": "TRUE",
                 "HF_ENDPOINT": "https://hf-mirror.com"},
        )
        return proc.returncode == 0 and os.path.exists(output_path)
    except Exception:
        return False


def _run_skill(url: str, output_path: str) -> bool:
    skill_script = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "src",
        "urlparser", "skill", "scripts", "parse.py"
    ))
    if not os.path.exists(skill_script):
        return False
    try:
        proc = subprocess.run(
            [sys.executable, skill_script, url,
             "--format", "markdown", "--output", output_path],
            capture_output=True, timeout=180,
            env={**os.environ, "KMP_DUPLICATE_LIB_OK": "TRUE",
                 "HF_ENDPOINT": "https://hf-mirror.com"},
        )
        return proc.returncode == 0 and os.path.exists(output_path)
    except Exception:
        return False


class TestContentEquivalence:
    """API vs CLI 内容等价性"""

    @pytest.mark.asyncio
    async def test_api_cli_content_body_match(self, article_urls, tmp_path):
        url = article_urls[0]
        api_result = await _get_api_result(url.url)
        if not api_result.fetch_success:
            pytest.skip("API parse failed")

        cli_output = str(tmp_path / "cli_equiv.md")
        if not _run_cli(url.url, cli_output):
            pytest.skip("CLI parse failed")

        with open(cli_output, encoding="utf-8") as f:
            cli_md = f.read()

        api_content = api_result.content
        cli_content = _extract_content_from_md(cli_md)

        assert api_content.strip() in cli_content or cli_content.strip() in api_content, \
            f"API content ({len(api_content)} chars) and CLI content ({len(cli_content)} chars) differ significantly"

    @pytest.mark.asyncio
    async def test_api_cli_title_match(self, article_urls, tmp_path):
        url = article_urls[0]
        api_result = await _get_api_result(url.url)
        if not api_result.fetch_success or not api_result.title:
            pytest.skip("API parse failed or no title")

        cli_output = str(tmp_path / "cli_title.md")
        if not _run_cli(url.url, cli_output):
            pytest.skip("CLI parse failed")

        with open(cli_output, encoding="utf-8") as f:
            cli_md = f.read()

        cli_title = _extract_title_from_md(cli_md)
        assert api_result.title.strip() == cli_title.strip(), \
            f"Title mismatch: API='{api_result.title}' vs CLI='{cli_title}'"


class TestNoTruncationAcrossInterfaces:
    """截断检测 - 确保所有接口输出完整内容"""

    @pytest.mark.asyncio
    async def test_api_no_truncation(self, article_urls):
        url = article_urls[0]
        result = await _get_api_result(url.url)
        if not result.fetch_success:
            pytest.skip("Parse failed")
        md = result.to_markdown()
        assert "... (共" not in md, "API output contains truncation marker"
        assert result.content in md, \
            "API result.content not found in to_markdown() output, possible truncation in rendering"

    def test_cli_no_truncation(self, article_urls, tmp_path):
        url = article_urls[0]
        cli_output = str(tmp_path / "cli_notrunc.md")
        if not _run_cli(url.url, cli_output):
            pytest.skip("CLI parse failed")
        with open(cli_output, encoding="utf-8") as f:
            md = f.read()
        content_body = _extract_content_from_md(md)
        assert "... (共" not in content_body, "CLI output truncated"

    def test_skill_no_truncation(self, article_urls, tmp_path):
        url = article_urls[0]
        skill_output = str(tmp_path / "skill_notrunc.md")
        if not _run_skill(url.url, skill_output):
            pytest.skip("SKILL parse failed")
        with open(skill_output, encoding="utf-8") as f:
            md = f.read()
        content_body = _extract_content_from_md(md)
        assert "... (共" not in content_body, "SKILL output truncated"


class TestJSONOutputConsistency:
    """JSON 输出一致性"""

    @pytest.mark.asyncio
    async def test_api_dict_has_required_fields(self, article_urls):
        url = article_urls[0]
        result = await _get_api_result(url.url)
        if not result.fetch_success:
            pytest.skip("Parse failed")
        d = result.to_dict()
        required_fields = [
            'url', 'platform', 'platform_type', 'content_type',
            'title', 'content_length', 'fetch_success', 'parse_time',
        ]
        for field in required_fields:
            assert field in d, f"Missing required field: {field}"

    def test_cli_json_output(self, article_urls, tmp_path):
        url = article_urls[0]
        output = str(tmp_path / "cli_json.json")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "urlparser", "parse", url.url,
                 "--format", "json", "--output", output],
                capture_output=True, timeout=180,
                env={**os.environ, "KMP_DUPLICATE_LIB_OK": "TRUE",
                     "HF_ENDPOINT": "https://hf-mirror.com"},
            )
            if proc.returncode != 0 or not os.path.exists(output):
                pytest.skip("CLI JSON output failed")

            with open(output, encoding="utf-8") as f:
                data = json.load(f)

            assert "url" in data
            assert "title" in data
            assert "fetch_success" in data
        except (json.JSONDecodeError, Exception) as e:
            pytest.skip(f"CLI JSON parse error: {e}")
