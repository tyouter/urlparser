---
name: urlparser
description: 通用 URL 解析器，自动识别平台提取内容
version: 3.3.0
---

# urlparser Skill

## 触发条件

用户要求解析/提取/爬取/抓取/读取任何 URL 或链接内容时触发。

**触发关键词**:
- 解析 URL / 解析链接
- 提取内容 / 提取文章
- 爬取页面 / 抓取网页
- 读取网页内容
- 视频转录 / 音频转文字
- 批量处理 URL

## Agent 模式选择指南

当用户要求解析视频 URL 时，根据用户表达选择 parse_mode：

**使用 local 模式（默认，不传 --parse-mode）:**
- "帮我解析这个链接"
- "parse this URL"
- 未特别说明模式的普通解析请求

**使用 online 模式（传 --parse-mode online）:**
- "用在线解析解析这个视频"
- "online parse this URL"
- "用大模型/AI 解析"
- "不要下载视频"
- "快速解析"（强调速度）

CLI: `urlparser parse <url> --parse-mode online`
Python: `await parse(url, config=ParseConfig(parse_mode="online"))`
Python: `await parse(url, config=ParseConfig.with_online_parse())`

## 核心能力

| 能力 | 描述 | CLI 命令 |
|------|------|---------|
| parse | 解析单个 URL，提取标题/内容/作者 | `urlparser parse <url>` |
| batch | 批量解析多个 URL | `urlparser parse-batch <file>` |
| transcribe | 视频音频转文字 | `urlparser transcribe <audio>` |
| comprehend | 视频理解：画面分析+音频转录合并 | `urlparser parse <url> --comprehension audio_video` |
| video-info | 获取视频元数据信息 | `urlparser video-info <url>` |
| cache | 缓存管理（统计/清空/查询） | `urlparser cache stats` |
| status | 状态检查与数据验证 | `urlparser status validate` |

## 视频理解模式

当解析视频 URL 时，可使用 `--comprehension` 参数启用 VLM 驱动的画面分析：

| 模式 | 行为 | 场景 |
|------|------|------|
| `audio` | 仅音频转录 | 播客/音乐/纯内容视频 |
| `video` | 仅画面分析（VLM 逐帧） | 无声视频/PPT/截图 |
| `audio_video` | 音频+画面合并时间轴 | 教程/演讲/纪录片 |

CLI 参数:
- `--comprehension audio\|video\|audio_video` — 启用视频理解
- `--comp-engine auto\|openvino\|llamacpp` — 推理引擎
- `--comp-max-frames N` — 最大分析帧数（默认 50）

示例:
```bash
# 快速音频转录
urlparser parse <bilibili_url> --comprehension audio

# 完整视频理解（画面+声音）
urlparser parse <bilibili_url> --comprehension audio_video --comp-max-frames 20

# 强制使用 CPU 引擎
urlparser parse <youtube_url> --comprehension audio_video --comp-engine llamacpp
```

## 支持平台

| 平台 | 内容类型 | 特殊处理 |
|------|---------|---------|
| 知乎 | 问答/文章 | 自动展开全文、关闭登录弹窗 |
| B站 | 视频 | 视频信息提取、转录支持 |
| YouTube | 视频 | 多语言转录 |
| 微信公众号 | 文章 | Cookie 认证支持 |
| 小红书 | 笔记 | 反爬绕过 |
| GitHub | 仓库/Issue | README/代码提取 |
| 通用网页 | 文章 | 智能内容提取 |

## 反爬策略

| 策略 | 适用场景 | 参数 |
|------|---------|------|
| Stealth 模式 | 大部分公开页面 | 默认启用 |
| Cookie 认证 | 需要登录的页面 | `--cookies-file path` |
| 用户浏览器 | 强反爬站点 | `--use-user-chrome` |
| AI 自动化 | 极端反爬 | 需要 DEEPSEEK_API_KEY |

## 使用示例

### Python API

```python
from urlparser import parse, ParseConfig

# 简单解析
result = await parse("https://www.zhihu.com/question/xxx")
print(result.title, result.content)

# 带视频转录
result = await parse(url, enable_transcribe=True)

# 使用 Cookie
result = await parse(url, cookies_file="cookies.json")

# 在线解析（LLM API，无需浏览器/yt-dlp）
result = await parse(url, config=ParseConfig(parse_mode="online"))
result = await parse(url, config=ParseConfig.with_online_parse())

# 批量解析
from urlparser import parse_batch
results = await parse_batch(["url1", "url2"], concurrent=3)
```

### CLI

```bash
# 解析单个 URL
urlparser parse https://www.zhihu.com/question/xxx

# 在线解析视频（LLM API，快速无需浏览器）
urlparser parse https://www.bilibili.com/video/BVxxx --parse-mode online

# 视频理解：画面+音频完整时间轴
urlparser parse https://www.bilibili.com/video/BVxxx --comprehension audio_video

# 输出到文件
urlparser parse <url> --output ./result.md

# 启用转录
urlparser parse <url> --transcribe

# 使用 Cookie
urlparser parse <url> --cookies-file cookies.json

# 批量解析
urlparser parse-batch urls.txt --output-dir ./results

# 缓存管理
urlparser cache stats
urlparser cache clear

# 状态检查
urlparser status validate
```

## 输出格式

### Markdown 格式

```markdown
# 标题

**作者**: xxx
**平台**: 知乎
**URL**: https://...
**解析时间**: 2024-01-01

---

正文内容...
```

### JSON 格式

```json
{
  "url": "https://...",
  "title": "标题",
  "content": "正文",
  "author": "作者",
  "platform": "zhihu",
  "metadata": {}
}
```

## 执行脚本

- `scripts/parse.py` - CLI 入口脚本

## 依赖

```bash
# 核心依赖
pip install playwright
playwright install chromium

# 视频处理（可选）
pip install yt-dlp ffmpeg

# 音频转录（可选）
pip install funasr faster-whisper torch

# 在线解析（可选，LLM API 模式）
# 需要设置 QWEN_API_KEY 环境变量
export QWEN_API_KEY="your-api-key"
```