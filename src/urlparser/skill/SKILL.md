---
name: urlparser
description: 通用 URL 解析器，自动识别平台提取内容
version: 3.1.0
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

## 核心能力

| 能力 | 描述 | CLI 命令 |
|------|------|---------|
| parse | 解析单个 URL，提取标题/内容/作者 | `urlparser parse <url>` |
| batch | 批量解析多个 URL | `urlparser parse-batch <file>` |
| transcribe | 视频音频转文字 | `urlparser transcribe <audio>` |
| video-info | 获取视频元数据信息 | `urlparser video-info <url>` |
| cache | 缓存管理（统计/清空/查询） | `urlparser cache stats` |
| status | 状态检查与数据验证 | `urlparser status validate` |

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

# 批量解析
from urlparser import parse_batch
results = await parse_batch(["url1", "url2"], concurrent=3)
```

### CLI

```bash
# 解析单个 URL
urlparser parse https://www.zhihu.com/question/xxx

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
```