---
name: urlparser
description: Parse any URL to extract content, transcribe video/audio, and convert websites to structured data. Use when the user asks to parse, extract, read, or transcribe any URL, link, video, or webpage.
version: "3.3.0"
license: MIT
platforms: [macos, linux, windows]
metadata:
  version: "3.3.1"
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
| WeChat | Article | Full text extraction, image placeholder |
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

### Known Defects (v3.3.1)

| Defect | Status |
|--------|--------|
| `_extract_subtitles()` returns empty entries | OPEN — subtitle content download not implemented |
| Timestamps all zero in subtitle mode | OPEN — depends on subtitle content download |
| `platform` shows "default" instead of platform name | OPEN — bb_browser generic path domain mapping |
| Video `content` = description only | BY DESIGN — no AI summarization yet |
| `author` field contains biography text | OPEN — no text cleaning on author field |
| FunASR SenseVoiceSmall output without punctuation | SENSEVOICE_LIMITATION — needs model upgrade to Paraformer |

## Pitfalls

- Xiaohongshu requires cookies for API access; use `CookieManager.interactive_login()`
- B站 transcription requires FunASR in a working conda/pip env (torch + torchaudio + funasr)
- `conda run` may fail with GBK encoding issues on Windows; use direct Python path instead
- Content is cached locally; use `--no-cache` to force refresh
- Known issue: `urlparser` CLI command may not work on Windows without `python -m` prefix
