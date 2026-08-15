"""
站点级 URL 发现测试（v4 M4 任务 9）

sitemap 解析、列表页链接提取、discover 合并去重、CLI 入口。
网络层用 monkeypatch 的 _http_get，不发真实请求。
"""

import json

import pytest

from urlparser.site_crawl import (
    parse_sitemap, extract_list_page_links, discover_urls,
)

SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/a</loc></url>
  <url><loc>https://example.com/b</loc></url>
</urlset>
"""

SITEMAP_INDEX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap>
</sitemapindex>
"""

LIST_PAGE_HTML = """
<html><body>
<a href="/article/1">一</a>
<a href="/article/2?x=1">二</a>
<a href="https://example.com/article/3">三</a>
<a href="https://other.com/x">外部</a>
<a href="#top">锚点</a>
<a href="javascript:void(0)">js</a>
</body></html>
"""


def test_parse_sitemap_urlset():
    locs = parse_sitemap(SITEMAP_XML)
    assert locs == ["https://example.com/a", "https://example.com/b"]


def test_parse_sitemap_index():
    locs = parse_sitemap(SITEMAP_INDEX_XML)
    assert locs == ["https://example.com/sitemap-1.xml"]


def test_parse_sitemap_invalid():
    assert parse_sitemap("") == []
    assert parse_sitemap("not xml at all") == []


def test_extract_list_page_links_same_domain():
    urls = extract_list_page_links(LIST_PAGE_HTML, "https://example.com/index")
    assert "https://example.com/article/1" in urls
    assert "https://example.com/article/2?x=1" in urls  # 非跟踪参数保留
    assert "https://example.com/article/3" in urls
    assert not any("other.com" in u for u in urls)
    assert not any(u.startswith("#") or "javascript" in u for u in urls)


def test_extract_list_page_links_dedup_and_cap():
    html = "".join(f'<a href="/p/{i}">x</a>' * 2 for i in range(30))
    urls = extract_list_page_links(html, "https://example.com/", max_urls=10)
    assert len(urls) == 10
    assert len(set(urls)) == 10


@pytest.mark.asyncio
async def test_discover_urls_merges(monkeypatch):
    def fake_http_get(url, timeout):
        if url.endswith("sitemap.xml"):
            return 200, SITEMAP_XML, url
        return 200, LIST_PAGE_HTML, url

    monkeypatch.setattr("urlparser.site_crawl._http_get", fake_http_get)

    data = await discover_urls("https://example.com/index", max_urls=20)
    assert len(data["sitemap_urls"]) == 2
    assert len(data["page_urls"]) == 3
    assert data["urls"][:2] == ["https://example.com/a", "https://example.com/b"]
    assert "https://example.com/article/1" in data["urls"]


@pytest.mark.asyncio
async def test_discover_urls_sitemap_failure_graceful(monkeypatch):
    def fake_http_get(url, timeout):
        if url.endswith("sitemap.xml"):
            raise RuntimeError("boom")
        return 200, LIST_PAGE_HTML, url

    monkeypatch.setattr("urlparser.site_crawl._http_get", fake_http_get)

    data = await discover_urls("https://example.com/index")
    assert data["sitemap_urls"] == []
    assert len(data["page_urls"]) == 3


def test_cli_discover(monkeypatch, capsys, tmp_path):
    from urlparser import cli

    async def fake_discover(url, max_urls=50):
        return {"url": url, "sitemap_urls": [], "page_urls": [],
                "urls": ["https://example.com/a", "https://example.com/b"]}

    monkeypatch.setattr("urlparser.site_crawl.discover_urls", fake_discover)

    out_file = tmp_path / "urls.txt"
    code = cli.main(["discover", "https://example.com", "-o", str(out_file)])
    assert code == 0
    lines = out_file.read_text(encoding="utf-8").splitlines()
    assert lines == ["https://example.com/a", "https://example.com/b"]
