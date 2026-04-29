---
name: urlparser
description: Parse any URL to extract content, transcribe video/audio, and convert websites to structured data. Use when the user asks to parse, extract, read, or transcribe any URL, link, video, or webpage.
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
- bb-browser: npm install -g bb-browser (for login-state browsing)
- ffmpeg: for audio/video processing

## Usage

### Parse a URL (extract title, content, author)
urlparser parse <url>

### Parse with video transcription
urlparser parse <url> --transcribe

### Parse with video understanding (visual + audio)
urlparser parse <url> --comprehension audio_video

### Batch parse URLs from a file
urlparser parse-batch <file>

### Transcribe a local audio/video file
urlparser transcribe <file>

### Batch transcribe a folder
urlparser transcribe-folder <directory>

### Get video metadata
urlparser video-info <url>

### Python API
from urlparser import parse, ParseConfig

result = await parse(url)
result = await parse(url, config=ParseConfig.with_transcribe())

## Supported Platforms

| Platform | Content Type | Features |
|----------|-------------|----------|
| Bilibili | Video | Transcription, metadata, audio download |
| Zhihu | Article/Answer | Full text extraction |
| WeChat | Article | Full text extraction |
| Xiaohongshu | Post/Video | Content extraction |
| YouTube | Video | Transcription, metadata |
| GitHub | Repository | README extraction |
| Generic | Any webpage | Title + body text |

## Strategy Selection (Automatic)

The tool automatically selects the best fetch strategy:

1. bb-browser (CDP) - reuses user's logged-in browser session
2. Playwright - headless browser with anti-scraping
3. Cookie-based - uses exported cookies
4. Direct fetch - for simple pages

No configuration needed. The tool retries with fallback strategies when content quality is insufficient.

## Notes

- Transcription uses FunASR (primary) or Whisper (fallback), auto-installed on first use
- Content is cached locally, re-parsing is fast
- Use --no-cache to force refresh
- Use --cookies <file> for authenticated access
