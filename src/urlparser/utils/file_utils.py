"""
文件操作工具

目录创建、安全文件名、JSON/文本读写
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union


def ensure_dir(path: Union[str, Path]) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_filename(name: str, max_length: int = 80) -> str:
    if not name:
        return "untitled"

    safe = (
        name[:max_length]
        .replace('/', '_')
        .replace('\\', '_')
        .replace(':', '_')
        .replace('*', '_')
        .replace('?', '_')
        .replace('"', '_')
        .replace('<', '_')
        .replace('>', '_')
        .replace('|', '_')
        .replace('\n', '_')
        .replace('\r', '_')
        .strip()
    )

    return safe or "untitled"


def read_json(file_path: Union[str, Path], default: Any = None) -> Any:
    p = Path(file_path)
    if not p.exists():
        return default

    try:
        content = p.read_text(encoding='utf-8')
        if not content.strip():
            return default
        return json.loads(content)
    except Exception:
        return default


def write_json(file_path: Union[str, Path], data: Any, indent: int = 2) -> bool:
    p = Path(file_path)
    ensure_dir(p.parent)

    try:
        content = json.dumps(data, ensure_ascii=False, indent=indent)
        p.write_text(content, encoding='utf-8')
        return True
    except Exception:
        return False


def read_text(file_path: Union[str, Path], encoding: str = 'utf-8') -> Optional[str]:
    p = Path(file_path)
    if not p.exists():
        return None

    try:
        return p.read_text(encoding=encoding)
    except Exception:
        return None


def write_text(file_path: Union[str, Path], content: str, encoding: str = 'utf-8') -> bool:
    p = Path(file_path)
    ensure_dir(p.parent)

    try:
        p.write_text(content, encoding=encoding)
        return True
    except Exception:
        return False


def file_size_str(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def list_files(directory: Union[str, Path], pattern: str = "*", recursive: bool = False) -> list:
    p = Path(directory)
    if not p.exists():
        return []

    if recursive:
        return list(p.rglob(pattern))
    else:
        return list(p.glob(pattern))