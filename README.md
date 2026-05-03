# urlparser

> 通用 URL 解析器 — 自动识别平台，提取结构化内容

[![PyPI version](https://badge.fury.io/py/urlparser.svg)](https://badge.fury.io/py/urlparser)
[![Python](https://img.shields.io/pypi/pyversions/urlparser.svg)](https://pypi.org/project/urlparser/)

## 特性

- **自动平台识别** — 支持知乎、B站、YouTube、微信、小红书、GitHub 等
- **智能内容提取** — 标题、作者、正文、视频元数据
- **自适应浏览器内容访问** — 兼容模式、Cookie 认证、用户浏览器、AI 自动化
- **视频转录** — FunASR（中文优化）/ Whisper（99 语言）
- **双层缓存** — 内存 + 磁盘，避免重复解析
- **批量处理** — 并发解析，进度追踪
- **CLI + Python API** — 灵活使用方式
- **Claude Code Skill** — 开箱即用，自然语言触发，自动识别解析意图

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
# 视频信息提取
pip install yt-dlp ffmpeg

# 音频转录
pip install funasr faster-whisper torch

# AI 自适应浏览器内容访问
pip install browser-use
```

## 快速开始

### Python API

```python
import asyncio
from urlparser import parse, ParseConfig

async def main():
    # 简单解析
    result = await parse("https://www.zhihu.com/question/xxx")
    print(result.title)
    print(result.content)

    # 带视频转录
    result = await parse(
        "https://www.bilibili.com/video/BVxxx",
        enable_transcribe=True
    )
    print(result.transcription.text)

asyncio.run(main())
```

### CLI

```bash
# 解析单个 URL
urlparser parse https://www.zhihu.com/question/xxx

# 输出到文件
urlparser parse <url> --output result.md

# 启用转录
urlparser parse <url> --transcribe

# 批量解析
urlparser parse-batch urls.txt --output-dir ./results

# 缓存管理
urlparser cache stats
urlparser cache clear

# 视频信息
urlparser video-info https://www.bilibili.com/video/BVxxx

# 音频转录
urlparser transcribe audio.mp3 --engine funasr
```

## 支持平台

| 平台 | 内容类型 | 特殊处理 |
|------|---------|---------|
| 知乎 | 问答/文章 | 自动加载完整内容、处理页面弹窗 |
| B站 | 视频 | 视频信息、转录支持 |
| YouTube | 视频 | 多语言转录 |
| 微信公众号 | 文章 | Cookie 认证 |
| 小红书 | 笔记 | 访问适配 |
| GitHub | 仓库/Issue | README/代码提取 |
| 通用网页 | 文章 | 智能内容提取 |

## 配置

```python
from urlparser import ParseConfig

# 简单配置
config = ParseConfig.simple()

# 带转录
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

```python
from urlparser import FunASRTranscriber, WhisperTranscriber

# FunASR（中文优化）
transcriber = FunASRTranscriber()
result = await transcriber.transcribe("audio.mp3")

# Whisper（多语言）
transcriber = WhisperTranscriber(model_size="large")
result = await transcriber.transcribe("audio.mp3", language="en")
```

## Claude Code 集成

urlparser 可作为 **Claude Code Skill** 直接使用，无需手动调用 CLI 或 Python API。当你在 Claude Code 中提到解析 URL 时，Skill 会自动触发。

### 安装方式

**方式一：克隆仓库（推荐）**

```bash
git clone https://github.com/tyouter/urlparser.git
cd urlparser
pip install -e .
```

Claude Code 会自动识别项目根目录下的 `.claude/skills/urlparser/SKILL.md`，无需额外配置。

**方式二：pip 安装 + 手动配置 Skill**

```bash
pip install urlparser
```

然后在你的项目 `.claude/skills/` 目录下创建 Skill 文件，内容参考 [SKILL.md](.claude/skills/urlparser/SKILL.md)。

### 使用示例

在 Claude Code 中直接对话即可：

```
用户: 帮我解析这个知乎链接 https://www.zhihu.com/question/19550225
Claude: [自动触发 urlparser Skill，调用 CLI 解析并返回结构化内容]

用户: 把这个B站视频转录一下 https://www.bilibili.com/video/BV1KBZkB6EJF
Claude: [自动触发，带 --transcribe 参数解析]

用户: 批量解析这个文件里的所有URL urls.txt
Claude: [自动触发 parse-batch 命令]
```

### 支持的触发方式

| 用户意图 | Skill 行为 |
|---------|-----------|
| 解析/读取/提取 URL 内容 | `urlparser parse <url>` |
| 转录视频/音频 | `urlparser parse <url> --transcribe` |
| 视频理解（视觉+音频） | `urlparser parse <url> --comprehension audio_video` |
| 批量解析 | `urlparser parse-batch <file>` |
| 转录本地文件 | `urlparser transcribe <file>` |
| 视频元信息 | `urlparser video-info <url>` |

### Cookie 管理

首次解析需要登录的平台（知乎、小红书、微信）时，urlparser 会自动检测 Cookie 状态，若缺失则提示交互式登录：

```bash
# 手动管理 Cookie
python -c "from urlparser.cookies_manager import CookieManager; import asyncio; asyncio.run(CookieManager().interactive_login('zhihu'))"
```

登录一次后 Cookie 会持久化保存，后续解析无需重复登录。

## API 导出

```python
from urlparser import (
    # 核心 API
    parse, parse_batch, parse_sync, UrlParser,
    ParseConfig, BrowserConfig, ScrollConfig, TranscribeConfig,

    # 数据模型
    ParseResult, PlatformType, ContentType,
    VideoMetadata, TranscriptionResult,

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