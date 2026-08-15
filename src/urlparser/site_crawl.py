"""
站点级 URL 发现（v4 M4 任务 9：轻量版）

sitemap.xml 解析 + 列表页同域链接提取，输出 URL 列表供 parse-batch 消费。
深度 crawl/map 仍留 P2（F15）。
"""

import asyncio
from typing import List
from urllib.parse import urljoin, urlparse

from .fetcher.http_fetcher import _http_get


def parse_sitemap(content: str) -> List[str]:
    """解析 sitemap XML（含 sitemap index），返回所有 <loc>"""
    from xml.etree import ElementTree as ET

    if not content or "<loc" not in content:
        return []
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
    locs = []
    for elem in root.iter():
        tag = elem.tag.rsplit("}", 1)[-1]
        if tag == "loc" and elem.text:
            text = elem.text.strip()
            if text and text not in locs:
                locs.append(text)
    return locs


def extract_list_page_links(html: str, base_url: str,
                            same_domain: bool = True,
                            max_urls: int = 100) -> List[str]:
    """从列表页 HTML 提取同域文章链接"""
    from bs4 import BeautifulSoup

    base_domain = urlparse(base_url).netloc.lower()
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full = urljoin(base_url, href).split("#")[0]
        if not full.startswith(("http://", "https://")):
            continue
        if same_domain and urlparse(full).netloc.lower() != base_domain:
            continue
        if full not in seen:
            seen.add(full)
            out.append(full)
            if len(out) >= max_urls:
                break
    return out


async def discover_urls(url: str, max_urls: int = 50,
                        include_sitemap: bool = True) -> dict:
    """站点级 URL 发现：sitemap + 列表页链接（去重合并）

    Returns:
        {"url", "sitemap_urls", "page_urls", "urls"}
    """
    result = {"url": url, "sitemap_urls": [], "page_urls": [], "urls": []}
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    loop = asyncio.get_event_loop()

    if include_sitemap:
        sitemap_url = f"{base}/sitemap.xml"
        try:
            status, content, _ = await loop.run_in_executor(
                None, lambda: _http_get(sitemap_url, 10.0),
            )
            if status < 400:
                result["sitemap_urls"] = parse_sitemap(content)[:max_urls]
        except Exception:
            pass

    try:
        status, html, _ = await loop.run_in_executor(
            None, lambda: _http_get(url, 10.0),
        )
        if status < 400:
            result["page_urls"] = extract_list_page_links(
                html, url, max_urls=max_urls,
            )
    except Exception:
        pass

    merged = []
    for u in result["sitemap_urls"] + result["page_urls"]:
        if u not in merged:
            merged.append(u)
    result["urls"] = merged[:max_urls]
    return result
