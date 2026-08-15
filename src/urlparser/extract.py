"""
LLM 结构化抽取（v4 M5 任务 F10，决策 D9）

给定 URL(s) + JSON Schema → 返回结构化对象（"填表"）。
后端：**DeepSeek API**（OpenAI 兼容，默认）；本地小模型为离线降级档（M5 仅接云端）。

隐私边界（D9）：仅本工具启用时将页面文本发送至 DeepSeek API；其余链路全本地。
"""

import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"

_EXTRACT_SYSTEM_PROMPT = (
    "你是结构化信息抽取助手。给定网页正文与目标 JSON Schema，"
    "提取字段并只返回一个符合 Schema 的 JSON 对象。"
    "缺失字段填 null；不要编造内容；不要输出任何其他文字。"
)


def parse_llm_json(content: str) -> Dict[str, Any]:
    """解析 LLM 输出中的 JSON（容忍 markdown 代码块包裹）"""
    text = (content or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"LLM 输出不含 JSON 对象: {text[:200]}")
    return json.loads(text[start:end + 1])


async def fetch_page_text(url: str, max_chars: int = 12000) -> str:
    """抓取页面纯文本（HTTP 快路径 + trafilatura，供 LLM 抽取）"""
    from .fetcher.http_fetcher import _http_get

    loop = asyncio.get_event_loop()
    status, html, _ = await loop.run_in_executor(
        None, lambda: _http_get(url, 15.0),
    )
    if status >= 400:
        raise RuntimeError(f"页面获取失败: HTTP {status}")

    text = ""
    try:
        import trafilatura
        text = trafilatura.extract(
            html,
            include_formatting=False,
            include_links=False,
            include_images=False,
        ) or ""
    except Exception:
        pass
    if not text:
        from bs4 import BeautifulSoup
        text = BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True)
    return (text or "")[:max_chars]


async def call_deepseek(messages: List[Dict[str, str]], api_key: str,
                        base_url: str = DEFAULT_BASE_URL,
                        model: str = DEFAULT_MODEL,
                        temperature: float = 0.1,
                        timeout: float = 120.0) -> str:
    """DeepSeek chat/completions（httpx，无 SDK 依赖）"""
    import httpx

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers, json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


async def extract_structured(
    urls: List[str],
    schema: Dict[str, Any],
    api_key: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    per_page_max_chars: int = 12000,
    combine: str = "merge",
) -> Dict[str, Any]:
    """结构化抽取（填表）。

    Args:
        urls: 一个或多个页面 URL
        schema: 目标 JSON Schema（须含 properties）
        combine: "merge"=多页文本合并后一次抽取（单对象）；
                 "each"=每页一次抽取（对象列表）

    Returns:
        {"schema_version": "1.0", "data": {...} 或 [...], "model": ...}
    """
    if not urls:
        raise ValueError("urls 不能为空")
    if not isinstance(schema, dict) or not schema.get("properties"):
        raise ValueError("schema 必须为含 properties 的 JSON Schema 对象")

    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY 未设置（结构化抽取走 DeepSeek API，决策 D9）")

    if combine == "each":
        items = []
        for u in urls:
            text = await fetch_page_text(u, per_page_max_chars)
            user_prompt = json.dumps({"schema": schema, "page_text": text},
                                     ensure_ascii=False)
            content = await call_deepseek(
                [{"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
                 {"role": "user", "content": user_prompt}],
                api_key, base_url, model,
            )
            items.append({"url": u, "data": parse_llm_json(content)})
        return {"schema_version": "1.0", "data": items, "model": model}

    texts = [await fetch_page_text(u, per_page_max_chars) for u in urls]
    joined = "\n\n---\n\n".join(texts)
    user_prompt = json.dumps({"schema": schema, "page_text": joined},
                             ensure_ascii=False)
    content = await call_deepseek(
        [{"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
         {"role": "user", "content": user_prompt}],
        api_key, base_url, model,
    )
    return {"schema_version": "1.0", "data": parse_llm_json(content), "model": model}
