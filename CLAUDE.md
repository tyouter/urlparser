# urlparser - Claude Code 项目指南

## 项目概述

urlparser 是一个通用 URL 解析器，支持自动识别平台、提取结构化内容、视频转录。既是 Python 包，也是 Claude Code Skill。

版本: 3.3.0 | Python >= 3.9 | MIT License

## 架构

```
src/urlparser/
├── core.py              统一入口 (parse, parse_batch, UrlParser)
├── config.py            配置模型 (ParseConfig, BrowserConfig, TranscribeConfig...)
├── models.py            数据模型 (ParseResult, PlatformType, ContentType...)
├── cli.py               CLI 接口 (python -m urlparser)
├── dependency_installer.py  可选依赖自动安装
├── fetcher/             URL 读取层
│   ├── base.py          BaseFetcher, FetchResult, FetchStrategy
│   ├── factory.py       FetcherFactory (自动选择策略)
│   ├── playwright_fetcher.py   Playwright 兼容模式
│   ├── cookie_fetcher.py       Cookie 认证模式
│   ├── user_chrome_fetcher.py  用户浏览器 CDP 模式
│   ├── bb_browser_fetcher.py   bb-browser daemon 模式
│   └── browser_use_fetcher.py  AI 自动化模式
├── parser/              内容解析层
│   ├── base.py          BaseParser, VideoParser, ArticleParser
│   ├── factory.py       ParserFactory, ParserRegistry
│   ├── models.py        ParserConfig, ParserParseResult
│   ├── mixins/          可复用解析逻辑
│   │   ├── content_quality.py   内容质量检测与访问适配
│   │   ├── content_clean.py   内容清洗
│   │   └── scrolling.py       滚动加载
│   └── platforms/       平台适配器
│       ├── zhihu.py     知乎 (文章/问答/想法)
│       ├── bilibili.py  B站 (视频)
│       ├── weixin.py    微信公众号
│       ├── xiaohongshu.py  小红书
│       ├── youtube.py   YouTube
│       ├── github.py    GitHub
│       └── generic.py   通用网页
├── transcriber/         音视频转录
│   ├── base.py          BaseTranscriber
│   ├── funasr.py        FunASR (中文优化)
│   ├── whisper.py       Whisper (99 语言)
│   ├── online_video_fetch.py  在线视频获取
│   └── video_info.py    视频元数据
├── comprehension/       VLM 视频理解
│   ├── pipeline.py      完整流水线
│   ├── frame_extractor.py  帧提取
│   ├── vlm_engine.py    推理引擎 (OpenVINO/llama.cpp)
│   └── writer.py        结果写入
├── batch_transcriber/   批量转录
│   ├── processor.py     核心处理器
│   ├── scanner.py       媒体文件扫描
│   ├── segment.py       分段处理
│   └── writer.py        结果写入
├── storage/             存储层
│   ├── cache.py         双层缓存 (内存+磁盘)
│   ├── file_storage.py  文件存储
│   ├── source_document.py  源文档管理
│   └── state.py         状态管理
├── skill/               Claude Code Skill 集成包 (随 pip 分发)
│   ├── SKILL.md         Skill 定义与触发规则
│   ├── CLAUDE.md        Claude Code 集成文档
│   └── scripts/parse.py Skill 执行入口
└── utils/               工具集
    ├── url_utils.py     URL 规范化、平台检测
    ├── text_utils.py    文本清洗、去重
    ├── file_utils.py    文件读写、安全命名
    ├── media_utils.py   音视频时长、格式判断
    └── ffmpeg_utils.py  FFmpeg 封装
```

## 开发命令

```bash
# 本地安装 (开发模式)
pip install -e .

# 运行测试
pytest tests/

# 仅运行测试框架 (P0-P5)
pytest tests/framework/

# 运行特定层级
pytest tests/framework/test_p0_pure_functions.py
pytest tests/framework/test_p3_interface_consistency.py

# 构建
pip install build && python -m build

# Playwright 浏览器安装
playwright install chromium
```

## 核心调用链

```
parse(url) → UrlParser.parse()
  → FetcherFactory.create(config)  # 选择获取策略
    → PlaywrightFetcher / CookieFetcher / UserChromeFetcher / BrowserUseFetcher
  → ParserFactory.create(url)      # 选择解析器
    → ZhihuParser / BilibiliParser / GenericParser / ...
  → ParseResult                    # 统一输出
```

## 关键约定

- **异步优先**: 核心接口全部 async，`parse_sync()` 是同步包装
- **策略自动降级**: Fetcher 按优先级尝试，失败自动切换下一策略
- **双层缓存**: 内存 (LRU) + 磁盘 (SQLite)，`--no-cache` 跳过
- **可选依赖延迟加载**: transcriber/comprehension 模块在 `__init__.py` 中 try/except 导入
- **环境变量**: `KMP_DUPLICATE_LIB_OK`, `HF_ENDPOINT`, `QWEN_API_KEY`, `DEEPSEEK_API_KEY`
- **平台检测**: 基于 URL 模式匹配，在 `utils/url_utils.py` 中实现
- **访问限制检测**: `parser/mixins/content_quality.py` 检测访问限制/空白内容，触发策略切换

## 测试框架

`tests/framework/` 下 P0-P5 分层测试:

| 层级 | 文件 | 内容 |
|------|------|------|
| P0 | test_p0_pure_functions.py | 纯函数单元测试 (URL检测、文本清洗、模型构造) |
| P1 | test_p1_property_based.py | Hypothesis 属性测试 (随机输入不变量) |
| P2 | test_p2_content_quality.py | 访问限制检测验证 (登录墙、内容完整性) |
| P3 | test_p3_interface_consistency.py | API/CLI/SKILL 三接口一致性 |
| P4 | test_p4_regression.py | 回归快照测试 (结构指纹) |
| P5 | test_p5_equivalence.py | 内容等价性验证 (无截断、无丢失) |

## 注意事项

- CLI 输出不要截断内容: `ParseResult.to_markdown()` 已移除 5000 字符限制，不要恢复
- 测试产物在 `.gitignore` 中排除: `tests/output/`, `tests/framework/snapshots/`, `tests/multi_platform/`
- `_archive/` 是本地归档目录，不追踪
- `.claude/` 保留 Skill 定义和项目配置，仅排除会话数据 (todos/, projects/)
