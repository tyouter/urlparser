# urlparser - Claude Code 项目指南

## 项目概述

urlparser 是一个通用 URL 解析器，支持自动识别平台、提取结构化内容、视频转录。既是 Python 包，也是 Claude Code Skill。

版本: 3.3.0 | Python >= 3.9 | MIT License

## 架构

```
src/urlparser/
├── core.py              统一入口 (parse, parse_batch, UrlParser)
│                        转录编排 (_transcribe_audio, _transcribe_bilibili_via_api)
│                        重试调度 (_parse_with_retry)
├── config.py            配置模型 (ParseConfig, BrowserConfig, TranscribeConfig...)
├── models.py            数据模型 (ParseResult, PlatformType, ContentType...)
│                        字段映射 (create_result_from_parser)
├── cli.py               CLI 接口 (python -m urlparser)
├── cookies_manager.py   Cookie 管理 (CookieManager, 交互式登录/提取/存储)
├── dependency_installer.py  可选依赖自动安装
├── fetcher/             URL 读取层
│   ├── base.py          BaseFetcher, FetchResult, FetchStrategy
│   ├── factory.py       FetcherFactory (自动选择策略)
│   ├── playwright_fetcher.py   Playwright 兼容模式
│   ├── cookie_fetcher.py       Cookie 认证模式
│   ├── user_chrome_fetcher.py  用户浏览器 CDP 模式
│   ├── bb_browser_fetcher.py   bb-browser daemon 模式 (结构化数据+音频流)
│   └── browser_use_fetcher.py  AI 自动化模式
├── parser/              内容解析层
│   ├── base.py          BaseParser, VideoParser (仅提取,不做转录), ArticleParser
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
│       ├── xiaohongshu.py  小红书 (Parser-First, API签名+Playwright降级)
│       ├── youtube.py   YouTube
│       ├── github.py    GitHub
│       └── generic.py   通用网页
├── transcriber/         音视频转录
│   ├── base.py          BaseTranscriber, convert_audio_for_funasr
│   ├── funasr.py        FunASR (中文优化)
│   ├── whisper.py       Whisper (99 语言)
│   ├── online_video_fetch.py  在线视频获取 (LLM API)
│   └── video_info.py    视频元数据 (yt-dlp)
├── comprehension/       VLM 视频理解
│   ├── pipeline.py      完整流水线
│   ├── frame_extractor.py  帧提取
│   ├── vlm_engine.py    推理引擎 (OpenVINO/llama.cpp)
│   └── writer.py        结果写入
├── auto_research/       自动化验收与基准测试
│   ├── acceptance.py    验收逻辑 (转录完整性: 时长/文字比例+结束语检测)
│   ├── benchmark.py     性能基准
│   ├── dataset.py       测试数据集
│   └── runner.py        运行器
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
    ├── url_utils.py     URL 规范化、平台检测、视频URL判断
    ├── text_utils.py    文本清洗、去重
    ├── file_utils.py    文件读写、安全命名
    ├── media_utils.py   音视频时长、格式判断
    └── ffmpeg_utils.py  FFmpeg 封装
```

## 核心调用链

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

### 转录编排原则

转录统一由 `core.py` 编排，`VideoParser` 仅做元数据提取和字幕收集，不做转录：
- 有字幕 → `create_result_from_parser()` 映射为 `TranscriptionResult(engine="subtitle")`
- 无字幕 → `core._transcribe_audio()` 统一执行，B站走API直取音频流，其他走yt-dlp下载
- 小红书视频笔记 → 解析后检测 `metadata.note_type=='video'`，动态触发转录

### 重试机制

当 `config.retry.enabled=True` 时，解析失败依次尝试：
1. `_do_parse()` (auto_select Fetcher → Parser)
2. `_strategy_playwright_extended()` (更长超时+更多滚动)
3. `_strategy_bb_browser()` (CDP控制用户Chrome)
4. `_strategy_cookie_fetcher()` (Playwright+Cookie)
5. `_strategy_user_chrome()` (用户Chrome profile)

每次尝试检查访问限制检测 + 质量验证，已有转录则跳过重复转录。

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

# Cookie 管理 (交互式登录)
python -c "from urlparser.cookies_manager import CookieManager; import asyncio; asyncio.run(CookieManager().interactive_login('xiaohongshu'))"
```

## 各平台解析策略

| 平台 | Fetcher策略 | Parser策略 | 转录 | 特殊处理 |
|------|------------|-----------|------|---------|
| Bilibili | bb-browser(结构化)/Playwright | VideoParser(yt-dlp) | API直取音频流→FunASR | BV号提取, CID+playurl |
| YouTube | Playwright | VideoParser(yt-dlp) | yt-dlp下载→FunASR | 多语言字幕 |
| 知乎 | bb-browser(结构化)/Playwright | ArticleParser(Playwright) | 无 | 强制非无头模式 |
| 小红书 | **跳过Fetcher** | XiaohongshuParser(API签名) | 内容级检测note_type | xhshow签名+homefeed搜索token |
| 微信 | bb-browser(降级)/Playwright | ArticleParser(Playwright) | 无 | 图片替换为[图片:alt] |
| GitHub | Playwright | GithubParser(Playwright) | 无 | README优先作为content |
| 通用 | Playwright | GenericParser(Playwright) | 视频平台触发 | 选最长内容块 |

## 关键约定

- **异步优先**: 核心接口全部 async，`parse_sync()` 是同步包装
- **转录单一职责**: VideoParser 仅提取元数据+字幕，转录由 core.py 统一编排，避免重复转录
- **策略自动降级**: Fetcher 按优先级尝试 (bb-browser → Cookie → UserChrome → Playwright)，失败自动切换
- **双层缓存**: 内存 (LRU) + 磁盘 (SQLite)，`--no-cache` 跳过
- **可选依赖延迟加载**: transcriber/comprehension 模块在 `__init__.py` 中 try/except 导入
- **环境变量**: `KMP_DUPLICATE_LIB_OK`, `HF_ENDPOINT`, `QWEN_API_KEY`, `DEEPSEEK_API_KEY`
- **平台检测**: 基于 URL 模式匹配 + ParserRegistry 注册，在 `utils/url_utils.py` 中实现
- **访问限制检测**: `parser/mixins/content_quality.py` 检测访问限制/空白内容，触发策略切换
- **内容级视频检测**: 小红书等平台URL无法区分图文/视频，通过解析后 `metadata.note_type` 判断
- **Cookie管理**: `cookies_manager.py` 支持交互式浏览器登录，Cookie存储在 `cookies/` 目录

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
- **不要在 VideoParser 中添加转录逻辑**: 转录统一在 core.py 编排，VideoParser 只做提取
- **新增平台时**: 在 ParserRegistry 注册 + `url_utils.py` 添加域名映射 + 如需视频支持加入 `is_video_url()`
