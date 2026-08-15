"""
文本处理工具

内容清洗、去重、提取
"""

import re
from typing import List, Optional


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r'<[^>]+>', '', text)

    text = re.sub(r'\s+', ' ', text)

    text = text.strip()

    text = re.sub(r'\n{3,}', '\n\n', text)

    return text


def remove_duplicate_lines(text: str) -> str:
    if not text:
        return ""

    lines = text.split('\n')
    seen = set()
    result = []

    for line in lines:
        stripped = line.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            result.append(line)

    return '\n'.join(result)


def extract_main_content(html: str, selectors: List[str]) -> str:
    if not html:
        return ""

    for selector in selectors:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            elements = soup.select(selector)
            if elements:
                texts = [el.get_text(strip=True) for el in elements]
                return '\n'.join(texts)
        except ImportError:
            pass
        except Exception:
            pass

    return ""


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def clean_author(name: str) -> str:
    """清洗作者名（v4 M4：修复 author 混入简介文本缺陷）

    - 取首行（简介通常从换行后开始）
    - 去 emoji/不可见字符
    - 超长（>30 字符）截断取前段
    """
    if not name:
        return ""
    name = name.split('\n')[0].strip()
    name = re.sub(r'[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]+', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    if len(name) > 30:
        name = name[:30].rstrip()
    return name


def count_words(text: str) -> int:
    if not text:
        return 0

    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))

    return chinese_chars + english_words


def extract_summary(text: str, max_sentences: int = 3) -> str:
    if not text:
        return ""

    sentences = re.split(r'[。！？.!?]', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= max_sentences:
        return '。'.join(sentences) + ('。' if sentences else '')

    return '。'.join(sentences[:max_sentences]) + '...'