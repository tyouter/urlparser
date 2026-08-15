---
name: urlparser
description: Parse any URL to extract content, transcribe video/audio, and convert websites to structured data. Use when the user asks to parse, extract, read, or transcribe any URL, link, video, or webpage.
version: "4.0.0"
license: MIT
platforms: [macos, linux, windows]
metadata:
  version: "4.0.0"
  author: "KnowHow Team"
  repository: "https://github.com/tyouter/urlparser"
  hermes:
    tags: [url, parser, content-extractor, transcriber, web-scraping]
    category: productivity
    requires_toolsets: [terminal]
---

# urlparser

Universal URL parser that auto-detects platform and extracts structured content.

## When to Use

- User asks to parse, read, extract, or transcribe content from a URL
- User shares a link and wants the content summarized or extracted
- User wants video/audio transcription from Bilibili, YouTube, etc.
- User needs structured data from web pages (articles, videos, repositories)

## Prerequisites

This skill requires the urlparser package. Check installation:

```bash
python -m urlparser --help
```

If not installed:

```bash
pip install -e .
```

Optional tools (auto-installed on first use if missing):
- bb-browser: `npm install -g bb-browser` (structured data + login-state browsing)
- ffmpeg: for audio/video processing
- Playwright browsers: `playwright install chromium`

## Usage

### Parse a URL (extract title, content, author)

```bash
python -m urlparser parse <url>
```

**Video URLs (Bilibili, YouTube) auto-trigger transcription** — no `--transcribe` needed.

### Parse with video transcription (explicit, for non-video URLs)

```bash
python -m urlparser parse <url> --transcribe
```

### Parse with video understanding (visual + audio)

```bash
python -m urlparser parse <url> --comprehension audio_video
```

### Online parse (LLM API, no browser/yt-dlp needed)

```bash
python -m urlparser parse <url> --parse-mode online
```

### Batch parse URLs from a file

```bash
python -m urlparser parse-batch <file>
```

### Transcribe a local audio/video file

```bash
python -m urlparser transcribe <file>
```

### Batch transcribe a folder

```bash
python -m urlparser transcribe-folder <directory>
```

### Get video metadata

```bash
python -m urlparser video-info <url>
```

### CLI v2 — 机器消费契约（v4）

```bash
# 快路径：仅元数据，不渲染不转录（秒级）
python -m urlparser parse <url> --metadata-only --json
# 强制策略 + 预算
python -m urlparser parse <url> --strategy http --budget 30000 --json
# 字段裁剪输出
python -m urlparser parse <url> --json --fields title,content,author
# stdin 批量 + manifest（机器消费）
cat urls.txt | python -m urlparser parse-batch - --manifest manifest.json
# daemon（常驻：浏览器/缓存复用）
python -m urlparser daemon start|stop|status
python -m urlparser job submit --url <url> --wait
python -m urlparser job list|show|result|cancel <job_id>
# 环境自检
python -m urlparser doctor [--json] [--fix]
# 站点级 URL 发现（sitemap + 列表页 → 供 parse-batch）
python -m urlparser discover <url> -o urls.txt
# 结构化抽取（填表，DeepSeek API，需 DEEPSEEK_API_KEY）
python -m urlparser extract --url <url> --schema schema.json
```

退出码契约：`0` 全部成功 ｜ `1` 部分失败（批量）｜ `2` 参数错误 ｜ `3` 依赖缺失 ｜ `4` 全部失败 ｜ `5` 预算超时 ｜ `130` 中断。
I/O 契约：stdout 仅结果（`--json` 为 Schema v1 JSON）；stderr 为日志与 `--progress` 进度事件（JSON-lines，四段 fetch/parse/transcribe/comprehension）。

### MCP 接入（Claude Code / Hermes / Cursor，v4 M2）

```json
// .mcp.json（或 claude_desktop_config.json）
{
  "mcpServers": {
    "urlparser": {
      "command": "python",
      "args": ["-m", "urlparser.mcp"]
    }
  }
}
```

工具面（9 个）：`parse_url` / `parse_batch` / `transcribe` / `comprehend_video` / `get_job` / `cancel_job` / `cache_inspect` / `cache_invalidate` / `doctor`（`extract_structured` 随 M5 上线）。
执行优先经 urlparserd（自动拉起、浏览器/缓存复用），daemon 不可用时自动降级进程内。

### Output to file

```bash
python -m urlparser parse <url> --output result.md
python -m urlparser parse <url> --output result.json --format json
```

### Cookie management (interactive login)

```bash
python -c "from urlparser.cookies_manager import CookieManager; import asyncio; asyncio.run(CookieManager().interactive_login('xiaohongshu'))"
```

### Python API

```python
from urlparser import parse, ParseConfig

# Simple parse
result = await parse(url)

# For non-video URLs, explicit transcription
result = await parse(url, config=ParseConfig.with_transcribe())

# Online parse (LLM API)
result = await parse(url, config=ParseConfig.with_online_parse())

# Image download
result = await parse(url, config=ParseConfig.with_image_download(mode="local"))

# Markdown output
print(result.to_markdown())

# JSON output
print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
```

## Supported Platforms

| Platform | Content Type | Features |
|----------|-------------|----------|
| Bilibili | Video | **Forced transcription** (FunASR via API direct audio), metadata, subtitles |
| Zhihu | Article/Answer | Full text extraction, cookie-based authenticated access |
| WeChat | Article | Full text extraction, real image links (v4 M4) |
| Xiaohongshu | Post/Video | API signature + Playwright fallback, video note detection |
| YouTube | Video | **Forced transcription**, multi-language subtitles |
| GitHub | Repository | README extraction |
| Generic | Any webpage | Title + body text (video platforms trigger transcription) |

## Core Call Chain

```
parse(url) → UrlParser.parse()
  │
  ├─ detect_platform(url) → 平台识别
  ├─ is_video_url(url)    → 视频URL判断
  │
  ├─ [小红书] → 跳过 Fetcher, 直接走 XiaohongshuParser
  │              (API签名 → homefeed搜索token → Playwright降级)
  │
  ├─ [其他平台] → FetcherFactory.auto_select(url, config)
  │   │           ├─ bb-browser 可用 → BbBrowserFetcher (结构化数据)
  │   │           ├─ 有 cookies_file → CookieFetcher
  │   │           ├─ 有 user_data_dir → UserChromeFetcher
  │   │           └─ 默认 → PlaywrightFetcher
  │   │
  │   ├─ Fetcher 成功 + 未被封锁 → ParseResult
  │   │   └─ 视频URL → 强制转录 (无需 --transcribe)
  │   │       ├─ bilibili → _transcribe_bilibili_via_api() (API直取音频流→FunASR)
  │   │       └─ 其他 → FunASR/Whisper.transcribe_from_url()
  │   │
  │   └─ Fetcher 失败 → ParserFactory.create(url)
  │       ├─ VideoParser.fetch() → yt-dlp提取元数据+字幕
  │       │   ├─ 有字幕 → content含字幕文本, has_transcription=True
  │       │   └─ 无字幕 → needs_transcription=True
  │       ├─ ArticleParser.fetch() → Playwright提取
  │       └─ create_result_from_parser() → models.ParseResult
  │           └─ 视频且无转录 → _transcribe_audio()
  │
  └─ 内容级视频检测: metadata.note_type=='video' → 触发转录
```

### Transcription Rules

- **B站**: 强制走 FunASR，通过 `_transcribe_bilibili_via_api()` 直接获取音频流；FunASR 不可用时返回错误，不降级 Whisper
- **其他视频**: FunASR 优先，Whisper 备选
- **小红书视频笔记**: 解析后检测 `metadata.note_type=='video'`，动态触发转录
- **视频 URL**: 自动强制转录，无需 `--transcribe` 参数

### Retry Mechanism

When `config.retry.enabled=True` (default), parsing failures fall back through:
1. `_do_parse()` (auto_select Fetcher → Parser)
2. `_strategy_playwright_extended()` (longer timeout + more scrolling)
3. `_strategy_bb_browser()` (CDP-controlled user Chrome)
4. `_strategy_cookie_fetcher()` (Playwright + Cookie)
5. `_strategy_user_chrome()` (user Chrome profile)

Each attempt checks access restriction + quality validation; existing transcriptions skip re-transcription.

### Key Conventions

- **Async-first**: All core interfaces are `async`; `parse_sync()` is the sync wrapper
- **Transcription single-responsibility**: VideoParser only extracts metadata/subtitles; transcription is orchestrated by `core.py`
- **Auto strategy fallback**: Fetcher tries priority order (bb-browser → Cookie → UserChrome → Playwright)
- **Dual-layer cache**: Memory (LRU) + Disk (SQLite); `--no-cache` to bypass
- **Windows subprocess silencing**: All `subprocess.run` calls use `_subprocess_win.run_nowindow()` with `CREATE_NO_WINDOW` to prevent background CMD popups
- **Optional dependency lazy loading**: transcriber/comprehension modules use try/except imports

## Quality Contract

Every parse result MUST satisfy these rules. Violations indicate defects.

### Universal (all content types)

| Rule | Requirement |
|------|-------------|
| `fetch_success` | MUST be `true` |
| `title` | MUST be non-empty, length ≥ 2 |
| `content` | MUST be non-empty, length ≥ 50 |
| `platform` | MUST be a known platform string, NOT "default" |
| `author` | MUST be a clean name, NOT contain biographies |
| `parse_time` | MUST be > 0 for successful parses |

### Video-specific (content_type=video)

| Rule | Requirement |
|------|-------------|
| `video_metadata.duration` | MUST be non-empty |
| `transcription.success` | MUST be `true` when subtitles available |
| `transcription.text` | MUST be non-empty when `success=true` |
| `transcription.engine` | MUST be "funasr" for B站 |
| `transcription.error` | MUST be displayed when `success=false` |

### Article-specific (content_type=article)

| Rule | Requirement |
|------|-------------|
| `content` length | MUST be ≥ 200 |
| `content` quality | MUST NOT contain access restriction indicators |

### Output Method Contract

All interfaces MUST use standard output methods:
- **Markdown**: `result.to_markdown()` — do NOT hand-craft Markdown
- **JSON**: `json.dumps(result.to_dict(), ensure_ascii=False, indent=2)` — do NOT hand-craft JSON

### Known Defects (v4.0.0)

| Defect | Status |
|--------|--------|
| `_extract_subtitles()` returns empty entries | OPEN — subtitle content download not implemented |
| Timestamps all zero in subtitle mode | OPEN — depends on subtitle content download |
| `platform` shows "default" instead of platform name | OPEN — generic path domain mapping（v3 既有缺陷） |
| Video `content` = description only | BY DESIGN — no AI summarization yet |
| `author` field contains biography text | **FIXED (v4 M4)** — `clean_author` 清洗 |
| FunASR SenseVoiceSmall output without punctuation | **FIXED (v4)** — punc_model=ct-punc 标点恢复（不换主模型，失败自动降级无标点） |
| `--resume` batch 断点续传 | TODO (M6+) — manifest 已交付，resume 未实现 |
| 代理/SSRF 安全护栏 | TODO (M6+) — 架构文档 §8.5 规划 |
| 本地离线结构化抽取档 | TODO (M6+) — M5 仅 DeepSeek API（D9） |

## Pitfalls

- Xiaohongshu requires cookies for API access; use `CookieManager.interactive_login()`
- B站 transcription requires FunASR in a working conda/pip env (torch + torchaudio + funasr)
- `conda run` may fail with GBK encoding issues on Windows; use direct Python path instead
- Content is cached locally; use `--no-cache` to force refresh
- Known issue: `urlparser` CLI command may not work on Windows without `python -m` prefix
