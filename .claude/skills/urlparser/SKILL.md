---
name: urlparser
description: Parse any URL to extract content, transcribe video/audio, and convert websites to structured data. Use when the user asks to parse, extract, read, or transcribe any URL, link, video, or webpage.
license: MIT
metadata:
  version: "3.3.0"
  author: "KnowHow Team"
  repository: "https://github.com/tyouter/urlparser"
---

# urlparser

Universal URL parser that auto-detects platform and extracts structured content.

## Prerequisites

This skill requires the urlparser CLI tool.

Check if already installed:
urlparser --version

If not installed, install from this repository:
pip install -e .

Optional tools (auto-installed on first use if missing):
- bb-browser: npm install -g bb-browser (for login-state browsing with structured data)
- ffmpeg: for audio/video processing

## Usage

### Parse a URL (extract title, content, author)
urlparser parse <url>

### Parse with video transcription
urlparser parse <url> --transcribe

### Parse with video understanding (visual + audio)
urlparser parse <url> --comprehension audio_video

### Online parse (LLM API, no browser/yt-dlp needed)
urlparser parse <url> --parse-mode online

### Batch parse URLs from a file
urlparser parse-batch <file>

### Transcribe a local audio/video file
urlparser transcribe <file>

### Batch transcribe a folder
urlparser transcribe-folder <directory>

### Get video metadata
urlparser video-info <url>

### Cookie management (interactive login)
python -c "from urlparser.cookies_manager import CookieManager; import asyncio; asyncio.run(CookieManager().interactive_login('xiaohongshu'))"

### Python API
from urlparser import parse, ParseConfig

result = await parse(url)
result = await parse(url, config=ParseConfig.with_transcribe())
result = await parse(url, config=ParseConfig.with_online_parse())

## Supported Platforms

| Platform | Content Type | Features |
|----------|-------------|----------|
| Bilibili | Video | Transcription (API direct audio), metadata, subtitles |
| Zhihu | Article/Answer | Full text extraction, forced non-headless |
| WeChat | Article | Full text extraction, image placeholder |
| Xiaohongshu | Post/Video | API signature + Playwright fallback, video note detection |
| YouTube | Video | Transcription (yt-dlp), multi-language subtitles |
| GitHub | Repository | README extraction |
| Generic | Any webpage | Title + body text |

## Core Call Chain

Understanding the data flow is critical for debugging and extending. Every parse call follows this path:

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
  │   │   └─ 视频且无转录 → _transcribe_audio(url, config, platform)
  │   │       ├─ bilibili → _transcribe_bilibili_via_api() (API直取音频流)
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

### Key Principles

- **Transcription is orchestrated by `core.py` only**: VideoParser extracts metadata + subtitles, NEVER transcribes. This avoids duplicate transcription and field loss.
- **Subtitle → TranscriptionResult mapping**: When subtitles exist, `create_result_from_parser()` maps them to `TranscriptionResult(engine="subtitle")` automatically.
- **Strategy auto-fallback**: Fetcher tries bb-browser → Cookie → UserChrome → Playwright. On failure or access restriction, it automatically switches.
- **Content-level video detection**: Some platforms (e.g. Xiaohongshu) cannot distinguish video/image from URL alone. After parsing, `metadata.note_type=="video"` triggers transcription dynamically.
- **Retry mechanism**: When `config.retry.enabled=True`, failed parses try up to 5 strategies with access restriction detection + quality validation at each step.

### Data Flow: Fetcher → Parser → ParseResult

```
Fetcher (fetcher/)
  │  Returns FetchResult(title, text, metadata, success, error)
  │
  ├─ [bb-browser for bilibili] → extracts structured data (bvid, stat, author)
  │   → core._fetch_result_to_parse_result() maps to ParseResult
  │
  └─ [other fetchers] → returns raw HTML/text
      → ParserFactory creates platform-specific parser
      → parser.parse() returns parser.models.ParseResult
      → create_result_from_parser() maps to urlparser.models.ParseResult

Final: ParseResult.to_markdown() or ParseResult.to_dict()
```

### Two Interfaces, One Output

Both interfaces (Python API, CLI) MUST produce identical output by using the same standard methods:

| Interface | Entry Point | Output Method |
|-----------|------------|---------------|
| Python API | `await parse(url)` | `result.to_markdown()` / `result.to_dict()` |
| CLI | `python -m urlparser parse <url>` | `result.to_markdown()` / `json.dumps(result.to_dict(), ...)` |

**NEVER hand-craft output formatting in any interface.** All formatting logic lives in `models.py` (`to_markdown()` / `to_dict()`).

## Strategy Selection (Automatic)

The tool automatically selects the best fetch strategy:

1. bb-browser (CDP) - reuses user's logged-in browser session, provides structured data
2. Cookie-based - uses exported cookies for authenticated access
3. User Chrome - uses user's Chrome profile directory
4. Playwright - headless browser with compatibility mode (default)

No configuration needed. The tool retries with fallback strategies when content quality is insufficient.

## Transcription Architecture

Transcription is orchestrated by core.py, not by individual parsers:
- VideoParser only extracts metadata + subtitles, never transcribes
- Subtitles are mapped to TranscriptionResult(engine="subtitle") automatically
- Bilibili: uses API to directly fetch audio stream (faster than yt-dlp)
- Other platforms: yt-dlp downloads audio, then FunASR/Whisper transcribes
- Xiaohongshu video notes: detected via metadata.note_type=="video" after parsing

## Output Specification

Every parse call MUST produce output conforming to these specifications. Use `result.to_markdown()` or `result.to_dict()` directly — NEVER hand-craft output formatting.

### Markdown Output (default)

The canonical Markdown structure produced by `result.to_markdown()`:

```markdown
# {title}

> **来源**: {url}
> **平台**: {platform} | **类型**: {content_type}
> **作者**: {author}
> **发布**: {publish_date}
> **解析策略**: {final_strategy}
> **解析时间**: {parse_time}s

## 视频信息          ← only when content_type=video
- 时长: {duration}
- 播放: {views}
- 点赞: {likes}
- 投币: {coins}
- 收藏: {favorites}
- 弹幕: {danmaku}
- 标签: {tags}

## 内容摘要
{content}

## 语音转录          ← only when has_transcription=true
> 引擎: {engine} | 时长: {duration}s | 语言: {language}

{transcription.text}

### 时间戳分段 ({segment_count} 段)
1. [00:01:23 - 00:01:45] segment text
2. [00:01:45 - 00:02:10] segment text

## 视频理解          ← only when has_comprehension=true
{comprehension output}

```

### JSON Output (`--format json`)

The canonical JSON structure produced by `result.to_dict()`:

```json
{
  "url": "string",
  "platform": "string",
  "platform_type": "zhihu|bilibili|youtube|weixin|xiaohongshu|github|dribbble|generic|unknown",
  "content_type": "article|video|webpage|repository|note|idea|unknown",
  "title": "string",
  "content_length": 0,
  "author": "string",
  "publish_date": "string",
  "is_video": false,
  "is_article": true,
  "has_transcription": false,
  "video_metadata": {
    "duration": "string",
    "views": "string",
    "likes": "string",
    "coins": "string",
    "favorites": "string",
    "tags": "string",
    "danmaku": "string",
    "subtitles": null
  },
  "transcription": {
    "success": false,
    "text": "string",
    "segment_count": 0,
    "language": "string",
    "duration": 0.0,
    "engine": "string",
    "error": null
  },
  "comprehension": {
    "success": false,
    "mode": "string",
    "frame_count": 0,
    "engine": "string",
    "timeline_summary": "string",
    "merged_text": "string",
    "error": null
  },
  "metadata": {},
  "fetch_success": true,
  "error": null,
  "parse_time": 0.0,
  "final_strategy": "string",
  "retry_attempts": []
}
```

### Quality Rules

These rules define the minimum acceptable quality for parse output. If any rule is violated, the result is defective.

#### Universal (all content types)

| Rule | Requirement | Rationale |
|------|-------------|-----------|
| `fetch_success` | MUST be `true` | Failed parses are not usable output |
| `title` | MUST be non-empty, length ≥ 2 | Title is the primary identifier |
| `content` | MUST be non-empty, length ≥ 50 | Content is the core value of parsing |
| `platform` | MUST be a known platform string, NOT "default" | "default" is an internal fallback, not a user-facing value |
| `author` | MUST be a clean name, NOT contain biographies or descriptions | Author field is for attribution only |
| `parse_time` | MUST be > 0 for successful parses | Zero parse time indicates the result was not actually measured |

#### Video-specific (content_type=video)

| Rule | Requirement | Rationale |
|------|-------------|-----------|
| `video_metadata.duration` | MUST be non-empty for video content | Duration is the most basic video attribute |
| `transcription.success` | MUST be `true` when subtitles are available | Available subtitles MUST be extracted |
| `transcription.text` | MUST be non-empty when `transcription.success=true` | Successful transcription with empty text is a bug |
| `transcription.segments[].start` | MUST be > 0 for at least some segments | All-zero timestamps indicate unpopulated segment data |
| `transcription.segments[].end` | MUST be > start for each segment | End time must be after start time |
| `transcription.segments[].text` | MUST be non-empty for each segment | Empty segment text is meaningless |

#### Article-specific (content_type=article)

| Rule | Requirement | Rationale |
|------|-------------|-----------|
| `content` length | MUST be ≥ 200 for articles | Articles should have substantial content |
| `content` quality | MUST NOT contain access restriction indicators | "登录/注册", "没有知识存在的荒原" etc. indicate blocked content |

#### GitHub-specific (content_type=repository)

| Rule | Requirement | Rationale |
|------|-------------|-----------|
| `content` | MUST contain README content | README is the primary content of a repository page |

### Output Method Contract

All interfaces MUST use the standard output methods:

- **Markdown**: `result.to_markdown()` — do NOT hand-craft Markdown
- **JSON**: `json.dumps(result.to_dict(), ensure_ascii=False, indent=2)` — do NOT hand-craft JSON

This ensures:
1. All output fields are present and consistent across API/CLI
2. Format changes in `models.py` automatically propagate to all interfaces
3. No fields are accidentally omitted

### Known Defects (as of v3.3.0)

These are documented defects that violate the Quality Rules above:

| Defect | Rule Violated | Status |
|--------|--------------|--------|
| `_extract_subtitles()` returns empty `entries` → transcription text is empty | transcription.text must be non-empty | OPEN — subtitle content download not implemented |
| Timestamps all zero `[00:00:00 - 00:00:00]` | segments[].start must be > 0 | OPEN — depends on subtitle content download |
| `platform` shows "default" instead of "generic" | platform must not be "default" | OPEN — platform_map mapping issue |
| Video `content` = description only | content should be a meaningful summary | BY DESIGN — no AI summarization yet |
| `author` field contains biography text | author must be a clean name | OPEN — no text cleaning on author field |

## Notes

- Transcription uses FunASR (primary) or Whisper (fallback), auto-installed on first use
- Content is cached locally, re-parsing is fast
- Use --no-cache to force refresh
- Use --cookies <file> for authenticated access
- Xiaohongshu requires cookies for API access; use CookieManager.interactive_login()
