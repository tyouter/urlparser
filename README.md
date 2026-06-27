# urlparser

> 通用 URL 解析器 — 自动识别平台，提取结构化内容

[![PyPI version](https://badge.fury.io/py/urlparser.svg)](https://badge.fury.io/py/urlparser)
[![Python](https://img.shields.io/pypi/pyversions/urlparser.svg)](https://pypi.org/project/urlparser/)

## 特性

- **自动平台识别** — 支持知乎、B站、YouTube、微信、小红书、GitHub 等
- **智能内容提取** — 标题、作者、正文、视频元数据
- **图片下载支持** — 下载网页中的图片到本地，或转换为 Base64 嵌入
- **自适应浏览器内容访问** — 兼容模式、Cookie 认证、用户浏览器、AI 自动化
- **视频自动转录** — 视频 URL 强制转录，B站 FunASR 优先，其他 FunASR/Whisper
- **Windows 静默** — 后台子进程不弹 CMD 窗口
- **双层缓存** — 内存 + 磁盘，避免重复解析
- **批量处理** — 并发解析，进度追踪
- **SKILL 集成** — Claude Code / Trae / Hermes 开箱即用，自然语言触发
- **CLI + Python API** — 灵活使用方式

## 安装

```bash
pip install urlparser
```

### 核心依赖

```bash
pip install playwright
playwright install chromium
```

### 可选依赖

```bash
# 图片下载
pip install pillow requests

# 视频信息提取
pip install yt-dlp ffmpeg

# 音频转录
pip install funasr faster-whisper torch

# AI 自适应浏览器内容访问
pip install browser-use
```

## 快速开始

### SKILL 模式（推荐）

urlparser 可作为 **AI 编码助手的 Skill** 直接使用，无需手动调用 CLI 或 Python API。当你在对话中提到解析 URL 时，Skill 会自动触发。

| IDE / 助手 | Skill 路径 | 安装方式 |
|-----------|-----------|---------|
| **Claude Code** | `.claude/skills/urlparser/SKILL.md` | 克隆仓库，自动加载 |
| **Trae** | `.trae/skills/urlparser/SKILL.md` | 克隆仓库，自动加载 |
| **Hermes** | `skills/urlparser/SKILL.md` | `hermes skills install tyouter/urlparser` |

**安装方式**

**Claude Code / Trae**：克隆仓库后自动识别对应目录下的 SKILL.md

```bash
git clone https://github.com/tyouter/urlparser.git
cd urlparser
pip install -e .
```

**Hermes**：一条命令安装

```bash
hermes skills install tyouter/urlparser
```

**使用示例**

在任意支持的 IDE 中直接对话即可：

```
用户: 帮我解析这个知乎链接 https://www.zhihu.com/question/19550225
助手: [自动触发 urlparser Skill，调用 CLI 解析并返回结构化内容]

用户: 把这个B站视频转录一下 https://www.bilibili.com/video/BV1KBZkB6EJF
助手: [自动触发，视频URL强制转录]

用户: 批量解析这个文件里的所有URL urls.txt
助手: [自动触发 parse-batch 命令]
```

**支持的触发方式**

| 用户意图 | Skill 行为 |
|---------|-----------|
| 解析/读取/提取 URL 内容 | `python -m urlparser parse <url>` |
| 转录视频/音频 | `python -m urlparser parse <url>` (自动) |
| 视频理解（视觉+音频） | `urlparser parse <url> --comprehension audio_video` |
| 批量解析 | `python -m urlparser parse-batch <file>` |
| 转录本地文件 | `python -m urlparser transcribe <file>` |
| 视频元信息 | `python -m urlparser video-info <url>` |

**Cookie 管理**

需要登录的平台（知乎、小红书、B站、微信、GitHub 等）登录一次即可，登录态写入**持久化浏览器 profile**（`~/.urlparser/profiles/<平台>/`）：

```bash
# 交互式登录（扫码），登录态持久化到 profile
python -m urlparser.cookies_manager login zhihu
python -m urlparser.cookies_manager login bilibili

# 查看各平台 Cookie 状态
python -m urlparser.cookies_manager status
```

登录一次后**后续解析无需重复登录**：`parse()` 前自动检测 Cookie，过期（默认 7 天，`BrowserConfig.cookie_max_age_hours` 可调）则无扫码从持久 profile 刷新，仅 session 真失效时才弹窗重登。

### Python API

```python
import asyncio
from urlparser import parse, ParseConfig, ImageDownloader, ImageDownloadConfig

async def main():
    # 简单解析
    result = await parse("https://www.zhihu.com/question/xxx")
    print(result.title)
    print(result.content)

    # 视频 URL 自动转录（无需 enable_transcribe）
    result = await parse("https://www.bilibili.com/video/BVxxx")
    print(result.transcription.text)
    
    # 下载图片
    config = ParseConfig.with_image_download(
        mode="local",  # 或 "base64"
        image_dir="./article_images"
    )
    result = await parse(url, config=config)
    
    # 也可以先生成 Markdown，然后手动处理图片
    markdown = result.to_markdown()
    downloader = ImageDownloader(ImageDownloadConfig(enabled=True))
    processed_markdown, image_info = downloader.process_markdown(
        markdown, 
        output_dir="./article",
        base_url=url
    )
    downloader.cleanup()

asyncio.run(main())
```

### CLI

```bash
# 解析单个 URL
python -m urlparser parse https://www.zhihu.com/question/xxx

# 输出到文件
python -m urlparser parse <url> --output result.md

# 视频自动转录（无需 --transcribe）
python -m urlparser parse <url>

# 非视频 URL 显式转录
python -m urlparser parse <url> --transcribe

# 下载图片到本地（配合 --output 使用会自动将图片保存在输出文件同目录下）
python -m urlparser parse <url> --download-images --output article.md

# 图片模式：local（默认，下载到本地）或 base64（嵌入 Markdown）
python -m urlparser parse <url> --download-images --image-mode base64

# 自定义图片保存目录
python -m urlparser parse <url> --download-images --image-dir ./article_images

# 批量解析
python -m urlparser parse-batch urls.txt --output-dir ./results

# 缓存管理
python -m urlparser cache stats
python -m urlparser cache clear

# 视频信息
python -m urlparser video-info https://www.bilibili.com/video/BVxxx

# 音频转录
python -m urlparser transcribe audio.mp3 --engine funasr
```

## 支持平台

| 平台 | 内容类型 | 特殊处理 |
|------|---------|---------|
| 知乎 | 问答/文章 | Cookie 认证，自动加载完整内容 |
| B站 | 视频 | **强制 FunASR 转录**，API 直取音频流 |
| YouTube | 视频 | 多语言转录 |
| 微信公众号 | 文章 | Cookie 认证，图片占位符替换 |
| 小红书 | 笔记 | 访问适配 |
| GitHub | 仓库/Issue | README/代码提取 |
| 通用网页 | 文章 | 智能内容提取，视频平台触发转录 |

## 配置

```python
from urlparser import ParseConfig

# 简单配置
config = ParseConfig.simple()

# 带转录（非视频 URL）
config = ParseConfig.with_transcribe(engine="funasr")

# 带 Cookie
config = ParseConfig.with_cookies(cookies_file="cookies.json")

# 完整功能
config = ParseConfig.full_feature()

# 自定义配置
config = ParseConfig(
    enable_transcribe=True,
    transcribe_engine="whisper",
    cookies_file="cookies.json",
    use_user_chrome=True,
    headless=True,
    timeout=60000,
)
```

## 自适应浏览器内容访问

| 策略 | 适用场景 | 参数 |
|------|---------|------|
| 兼容模式 | 大部分公开页面 | 默认启用 |
| Cookie 认证 | 需要登录的页面 | `cookies_file` |
| 用户浏览器 | 高安全站点 | `use_user_chrome=True` |
| AI 自动化 | 复杂访问场景 | 需要 DEEPSEEK_API_KEY |

```python
# Cookie 认证
result = await parse(url, cookies_file="cookies.json")

# 用户浏览器（复用已登录状态）
result = await parse(url, use_user_chrome=True)

# AI 自动化（browser-use）
from urlparser import FetcherFactory, FetchStrategy
fetcher = FetcherFactory.create(strategy=FetchStrategy.BROWSER_USE)
result = await fetcher.fetch(url)
```

## 集成建议（Hermes 等上层应用）

Cookie 过期检测与自动刷新是**库内置行为**，挂在 `parse()` 流程里，上层无需自己定时刷新：

```python
from urlparser import parse

# 自动识别平台 → 用持久 profile → 过期自动无扫码刷新
result = await parse(url)
print(result.to_markdown())
```

| 调用方式 | 适用场景 | 自动刷新 |
|---------|---------|---------|
| `await parse(url)` / `parse_sync(url)` | 上层 Python 应用（**推荐**） | ✅ |
| 复用 `UrlParser()` 实例 | 批量解析（共享缓存） | ✅ |
| CLI `python -m urlparser parse` | 进程隔离 / 队列解耦 | ✅ |

> 只有**绕过 `parse()` 直接调 fetcher** 才会错过自动刷新，一般不用。
>
> **Hermes 集成**：`pip install -e .` 后 agent 直接 `await parse(url)` 即自动用上 profile 与自动刷新；旧 `parse_watcher` 的定时刷 Cookie（依赖已失效的 `browser_cookie3`）不再需要，库内按需自动刷新已取代它。

## 数据模型

```python
from urlparser import ParseResult, PlatformType, ContentType

result = await parse(url)

# 基本字段
result.url           # 原始 URL
result.title         # 标题
result.content       # 正文内容
result.author        # 作者
result.platform      # PlatformType.ZHIHU 等
result.content_type  # ContentType.ARTICLE / VIDEO
result.success       # 是否成功
result.error         # 错误信息（失败时）

# 视频元数据
result.video_metadata.title
result.video_metadata.duration
result.video_metadata.author
result.video_metadata.view_count

# 转录结果
result.transcription.text
result.transcription.segments
result.transcription.language
```

## 存储与缓存

```python
from urlparser import ResultCache, ResultStorage, StateManager

# 缓存操作
cache = ResultCache()
cache.get(url)        # 获取缓存
cache.set(url, result)  # 设置缓存
cache.delete(url)     # 删除缓存
cache.clear()         # 清空缓存
cache.stats()         # 统计信息

# 文件存储
storage = ResultStorage(output_dir="./output")
await storage.save(result, format="markdown")
await storage.save(result, format="json")

# 状态管理
state = StateManager()
state.mark_processed(url)
state.get_pending_urls()
state.get_statistics()
```

## 批量解析

```python
from urlparser import parse_batch

urls = ["url1", "url2", "url3"]

results = await parse_batch(
    urls,
    concurrent=3,           # 并发数
    enable_transcribe=True,
    output_dir="./results",  # 自动保存
)
```

## 转录引擎

> **视频 URL 自动强制转录**，无需手动开启。B站走 FunASR API 直取音频流。
> Windows 下所有子进程通过 `CREATE_NO_WINDOW` 静默运行。

```python
from urlparser import FunASRTranscriber, WhisperTranscriber

# FunASR（中文优化）
transcriber = FunASRTranscriber()
result = await transcriber.transcribe("audio.mp3")

# Whisper（多语言）
transcriber = WhisperTranscriber(model_size="large")
result = await transcriber.transcribe("audio.mp3", language="en")
```

## API 导出

```python
from urlparser import (
    # 核心 API
    parse, parse_batch, parse_sync, UrlParser,
    ParseConfig, BrowserConfig, ScrollConfig, TranscribeConfig, ImageDownloadConfig,

    # 数据模型
    ParseResult, PlatformType, ContentType,
    VideoMetadata, TranscriptionResult,

    # 图片下载
    ImageDownloader,

    # 存储层
    ResultCache, ResultStorage, StateManager, SourceDocumentManager,

    # 转录层
    FunASRTranscriber, WhisperTranscriber, extract_video_info,

    # Fetcher 层
    FetcherFactory, FetchStrategy, FetchConfig,
    PlaywrightFetcher, CookieFetcher, UserChromeFetcher, BrowserUseFetcher,

    # CLI
    _extract_urls_from_file,
)
```

## 开发

```bash
# 本地安装
pip install -e .

# 运行测试
pytest tests/

# 构建
pip install build
python -m build
```

## License

MIT