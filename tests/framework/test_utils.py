"""
测试框架共享工具

被 conftest.py 和各测试文件共同引用
"""

import hashlib
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


FRAMEWORK_DIR = Path(__file__).parent
SNAPSHOTS_DIR = FRAMEWORK_DIR / "snapshots"
SNAPSHOTS_DIR.mkdir(exist_ok=True)
REGRESSION_DIR = FRAMEWORK_DIR / "regression_reports"
REGRESSION_DIR.mkdir(exist_ok=True)


@dataclass
class URLFixture:
    platform: str
    name: str
    url: str
    content_type: str
    min_content_length: int = 100
    expected_platform: Optional[str] = None
    tags: List[str] = field(default_factory=list)


TEST_URLS = [
    URLFixture("bilibili", "爆肝5小时实测国产大模型横评",
            "https://www.bilibili.com/video/BV1KBZkB6EJF",
            "video", min_content_length=50, tags=["video"]),
    URLFixture("bilibili", "ObsidianCLI+ClaudeCode笔记工作流",
            "https://www.bilibili.com/video/BV1qNAqzxETr",
            "video", min_content_length=50, tags=["video"]),
    URLFixture("bilibili", "开源Figma-AI原生设计编辑器OpenPencil",
            "https://www.bilibili.com/video/BV19aPHzyEs5",
            "video", min_content_length=50, tags=["video"]),
    URLFixture("zhihu", "claude.md怎么写才能让Claude Code更高效",
            "https://www.zhihu.com/answer/2009429788666909340",
            "article", min_content_length=500, tags=["article", "zhihu_answer"]),
    URLFixture("zhihu", "普通人第一次用OpenClaw应该注意什么",
            "https://www.zhihu.com/answer/2010009329542140927",
            "article", min_content_length=100, tags=["article", "zhihu_answer"]),
    URLFixture("zhihu", "最难调试修复的bug是怎样的",
            "https://www.zhihu.com/answer/2012245758137631858",
            "article", min_content_length=500, tags=["article", "zhihu_answer"]),
    URLFixture("weixin", "龙虾越火越应该研究Skill",
            "https://mp.weixin.qq.com/s/mpoOI3gAiVd9I-uuzSgxAw",
            "article", min_content_length=500, tags=["article", "weixin"]),
    URLFixture("zhihu_zhuanlan", "知乎专栏-PlaywrightCLI隐藏技能",
            "https://zhuanlan.zhihu.com/p/2012158056595727644",
            "article", min_content_length=200, tags=["article", "zhihu_zhuanlan"]),
]


def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def compute_structure_fingerprint(content: str) -> Dict[str, Any]:
    lines = content.split('\n')
    headings = [l for l in lines if l.startswith('#')]
    sections = [l for l in lines if l.startswith('## ')]
    return {
        "total_lines": len(lines),
        "total_chars": len(content),
        "heading_count": len(headings),
        "section_count": len(sections),
        "section_titles": [s.strip('# ').strip() for s in sections],
        "content_hash": compute_content_hash(content),
    }
