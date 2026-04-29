# urlparser - Claude Code 集成文档

## 概述

urlparser 是一个通用 URL 解析器，支持自动识别平台、提取结构化内容、视频转录等功能。本文档说明如何在 Claude Code 中使用此 Skill。

## 安装

### pip 安装

```bash
pip install urlparser
```

### 本地开发安装

```bash
pip install -e .
```

### 依赖安装

```bash
# Playwright 浏览器
playwright install chromium

# 可选：音频转录
pip install funasr faster-whisper torch

# 可选：视频信息
pip install yt-dlp ffmpeg
```

## Skill 配置

### 方式 1: 自动识别

pip 安装后，Skill 文件位于 `{site-packages}/urlparser/skill/`

查找安装位置:
```bash
python -c "import urlparser; print(urlparser.__path__[0])"
```

### 方式 2: 符号链接

在项目 `.claude/skills/` 创建链接:
```bash
ln -s {site-packages}/urlparser/skill .claude/skills/urlparser
```

### 方式 3: settings.json 配置

```json
{
  "skills": {
    "urlparser": {
      "path": "{site-packages}/urlparser/skill",
      "enabled": true
    }
  }
}
```

## 使用方式

### 自然语言触发

```
用户: 帮我解析这个知乎链接 https://www.zhihu.com/question/xxx
Claude: [触发 urlparser Skill，调用 parse()]
```

```
用户: 批量处理 urls.txt 里的所有链接
Claude: [触发 urlparser Skill，调用 parse_batch()]
```

```
用户: 把这个视频转录成文字
Claude: [触发 urlparser Skill，调用 transcribe()]
```

### 显式 Skill 调用

```
用户: /urlparser parse https://...
```

## API 参考

### 核心函数

```python
from urlparser import parse, parse_batch, parse_sync, UrlParser

# 异步解析
result = await parse(url)

# 同步解析（内部封装 async）
result = parse_sync(url)

# 批量解析
results = await parse_batch(urls, concurrent=3)

# 类实例方式
parser = UrlParser()
result = await parser.parse(url)
await parser.close()
```

### 配置

```python
from urlparser import ParseConfig, BrowserConfig, ScrollConfig

# 简单配置
config = ParseConfig.simple()

# 带转录
config = ParseConfig.with_transcribe(engine="funasr")

# 带 Cookie
config = ParseConfig.with_cookies(cookies_file="path")

# 带在线解析（LLM API，无需浏览器）
config = ParseConfig.with_online_parse()
config = ParseConfig(parse_mode="online")

# 完整功能
config = ParseConfig.full_feature()
```

### 数据模型

```python
from urlparser import ParseResult, PlatformType, ContentType

result = await parse(url)
print(result.url)
print(result.title)
print(result.content)
print(result.author)
print(result.platform)  # PlatformType.ZHIHU
print(result.content_type)  # ContentType.ARTICLE
print(result.video_metadata)  # VideoMetadata | None
print(result.transcription)  # TranscriptionResult | None
```

### 存储与缓存

```python
from urlparser import ResultCache, ResultStorage, StateManager

# 缓存操作
cache = ResultCache()
entry = cache.get(url)
cache.set(url, result)
cache.delete(url)
cache.clear()

# 文件存储
storage = ResultStorage(output_dir="./output")
await storage.save(result, format="markdown")

# 状态管理
state = StateManager()
state.mark_processed(url)
state.get_pending_urls()
```

### 转录引擎

```python
from urlparser import FunASRTranscriber, WhisperTranscriber, extract_video_info

# FunASR（中文优化）
transcriber = FunASRTranscriber()
result = await transcriber.transcribe("audio.mp3")

# Whisper（多语言）
transcriber = WhisperTranscriber(model_size="large")
result = await transcriber.transcribe("audio.mp3", language="en")

# 视频信息
info = await extract_video_info("https://www.bilibili.com/video/BVxxx")
```

### Fetcher 层

```python
from urlparser import FetcherFactory, FetchStrategy, FetchConfig

# 自动选择
fetcher = FetcherFactory.create(config)

# 指定策略
fetcher = FetcherFactory.create(config, strategy=FetchStrategy.COOKIE)

# 自动选择最佳策略
fetcher = FetcherFactory.auto_select(url, config)
```

## CLI 命令

```bash
# 解析
urlparser parse <url> [--output file] [--transcribe] [--cookies-file path]

# 批量
urlparser parse-batch <file> [--output-dir dir] [--concurrent N]

# 缓存
urlparser cache stats|clear|get <url>|delete <url>

# 状态
urlparser status check <url>|validate|stats

# 视频信息
urlparser video-info <url>

# 转录
urlparser transcribe <audio> [--engine funasr|whisper] [--language zh]
```

## 错误处理

```python
result = await parse(url)
if not result.success:
    print(f"解析失败: {result.error}")
    # 常见错误:
    # - 网络超时: timeout
    # - 访问限制: restricted
    # - 需要登录: login_required
    # - 页面不存在: not_found
```

## 最佳实践

1. **优先使用缓存**: 默认启用双层缓存，避免重复解析
2. **选择合适策略**: 知乎/小红书等高安全站点使用 Cookie 或用户浏览器
3. **转录引擎选择**: 中文视频用 FunASR，多语言用 Whisper
4. **批量并发控制**: 建议并发数 3-5，避免触发访问限制
5. **输出格式**: Markdown 适合阅读，JSON 适合程序处理