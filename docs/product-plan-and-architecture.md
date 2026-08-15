# urlparser v4 — 本地 Agent 抓取工具产品规划与技术架构

> 版本：v1.0（草案）｜ 日期：2026-06 ｜ 状态：待评审
> 读者：产品负责人、Agent 集成方、核心开发者
> 前提输入：《工程能力分析》（会话内完成，未入库）、《SOTA 对标调研报告》（会话内完成，未入库）

---

## 1. 文档目的与范围

urlparser v3.3.x 是一个成熟的**本地库**，但作为**本地 Agent 的常驻搭配工具**存在三个结构性缺口：

1. **无服务形态**：只有 CLI + Python API + Skill（进程内调用），Agent 每次调用都要冷启动浏览器与模型；
2. **CLI 面向人而非 Agent**：输出格式、退出码、错误模型、进度事件、作业语义均未按机器消费设计；
3. **算力未被最大化**：模型每请求加载/卸载、浏览器每请求启动/销毁、GPU 仅用于转录且无调度。

本文档给出 v4 的产品功能规划与技术架构，目标一句话概括：

> **把 urlparser 从"每次调用都冷启动的库"升级为"本地常驻、面向 Agent、算力满负荷调度的抓取/转录/理解服务"。**

范围包含：现状诊断、产品规划（P0/P1/P2）、对外契约（MCP/HTTP/CLI v2/Schema）、技术架构（守护进程、调度器、浏览器池、模型注册表）、算力最大化设计、安全设计、实施路线图。不含具体代码实现。

---

## 2. 现状诊断：CLI 与 Agent 适配度差距清单

以下问题均已在 v3.3.1 源码中核实（`src/urlparser/cli.py`、`core.py`、`models.py`）。

### 2.1 功能缺失类（Agent 无法表达需求）

| # | 问题 | 影响 |
|---|---|---|
| C1 | 视频 URL **强制转录**，无 `--no-transcribe`/`--metadata-only` | Agent 只想拿 B 站视频标题/播放量时，被迫付几分钟转录成本 |
| C2 | 无 `--strategy`/`--no-render`/`--fast` 控制降级链 | 无法指定"只走 HTTP/trafilatura，失败就失败"，快路径不可达 |
| C3 | 无 `--timeout`/`--budget`；重试总超时写死 120s、浏览器 30s | Agent 的时效预算无法表达；单个坏 URL 拖死对话轮次 |
| C4 | 无 `--fields`/输出裁剪；`to_markdown` 分段硬截断 50 条 | 无法按需取子集；长转录 markdown 静默丢段 |
| C5 | 无配置文件/profile；每个参数都要重敲或重写 | Agent 每次调用要重建复杂参数；无"快速/高质量/视频"预设 |
| C6 | 无 `doctor` 一体化自检；`install-deps` 不检测 GPU/NPU/ffmpeg 型号 | 环境问题到运行时才爆，Agent 拿不到可执行建议 |
| C7 | 无代理参数、无 SSRF 防护（`file://`、内网 IP 无约束） | 本地 Agent 抓取即开放任意内网探测面 |
| C8 | 缓存与 parse 分离：无 TTL 控制、无命中信息、无主动失效 | 重复调用免费这件事对 Agent 不可见、不可控 |

### 2.2 契约缺失类（机器无法可靠消费）

| # | 问题 | 影响 |
|---|---|---|
| C9 | 结果无 `schema_version`；README 与实现不一致（如 `--engine` 参数实际不存在） | 上层解析脆弱，升级即碎 |
| C10 | 无退出码契约：成功/部分失败/全部失败/依赖缺失/超时不可区分 | Agent 只能靠解析自由文本猜成败 |
| C11 | 错误是自由文本（`error: str`），无错误码/可重试标记 | Agent 无法做程序化重试决策（429 vs 登录墙 vs 环境缺依赖） |
| C12 | 进度事件**仅在 FunASR 转录段发射**；fetch/parse/comprehension 全程静默 | 长任务的 Agent 监督链断裂 |
| C13 | stdout 混排人读日志与结果（`parse-batch` 的 `print`、Cookie 提示混进 stderr） | 机器解析 stdout 不可靠 |
| C14 | 无 stdin/管道输入；`parse-batch` 只接受文件 | 无法 `cat urls | urlparser parse-batch -`，Agent 管道式组合受限 |
| C15 | 无作业语义：长转录无提交/轮询/取消，Ctrl-C 即丢全部进度 | 数小时转录无法与 Agent 的事件循环解耦 |

### 2.3 架构性问题（效率与稳定性）

| # | 问题 | 影响 |
|---|---|---|
| C16 | 每次 CLI 调用独立启动 Playwright 浏览器，结束即销毁 | 单条解析 6–28s 中大量是浏览器冷启动；批量场景 N 次冷启动 |
| C17 | FunASR/Whisper/VLM 模型**每请求加载**（`AutoModel(...)` 在 transcribe 内） | 首次转录先付几十秒~分钟级模型加载；本机算力空转 |
| C18 | 单进程 asyncio：一个浏览器/模型崩溃影响整个批次 | `parse-batch` 中 1 个坏 URL 可拖垮全部 |
| C19 | 并发是纯 asyncio，无进程池/GPU 队列 | GPU 上多个转录任务无准入控制，显存 OOM 即连锁失败 |
| C20 | 结果缓存内存层（LRU）在 CLI 进程退出即失效，仅磁盘层生效 | 库内宣称的双层缓存在 CLI 场景退化为单层 |
| C21 | `urlparser` 控制台脚本在 Windows 需 `python -m` 前缀（SKILL 已知） | Agent 调用路径不一致，包装层要写平台分支 |

**结论**：CLI 的问题是"人机界面 + 无服务形态"共同导致的。修 CLI 参数只是治标，治本是把执行面常驻化（daemon），CLI 退化为瘦客户端。

### 2.4 C1–C21 修复状态（M0+M1 交付后更新）

| 项 | 状态 | 说明 |
|---|---|---|
| C1 视频强制转录 | ✅ 已修复 | `mode=metadata` 快路径 + `--metadata-only`，零模型加载 |
| C2 策略控制 | ✅ 已修复 | `--strategy http/cffi/playwright/bb/cookie/user_chrome/browser_use` + `HttpFetcher` 毫秒级快路径 |
| C3 预算/超时 | ✅ 已修复 | `--budget/--timeout` → `E_BUDGET_EXCEEDED`（退出码 5） |
| C4 字段裁剪 | ✅ 已修复 | `--fields`（`apply_fields`，恒保留 schema_version/url） |
| C5 配置/profile | ✅ 已修复 | `~/.urlparser/config.toml` + `[profiles.*]`（`load_user_config/get_profile`） |
| C6 doctor | ✅ 已修复 | `python -m urlparser doctor [--json] [--fix]` |
| C7 代理/SSRF | ⏳ 待办 | 安全护栏留待 daemon 稳定后（§8.5） |
| C8 缓存 TTL | ⏳ 待办 | 缓存命中信息已入 Schema（`cache` 字段），TTL 参数待 M3 |
| C9 schema_version | ✅ 已修复 | Schema v1 + 契约测试 `test_schema_contract.py` |
| C10 退出码 | ✅ 已修复 | 0/1/2/3/4/5/130 全契约 + `test_cli_contract.py` |
| C11 错误码 | ✅ 已修复 | `ErrorCode` 10 码 + `error_detail` + 分类测试 ≥95% |
| C12 进度事件 | ✅ 已修复 | 四段全覆盖（core 编排 + comprehension 管线内部） |
| C13 stdout 混排 | ✅ 已修复 | stdout 仅结果；日志/提示归 stderr |
| C14 stdin 管道 | ✅ 已修复 | `parse-batch -` + `--manifest` |
| C15 作业语义 | ✅ 已修复 | daemon `job submit/list/show/result/cancel` + 进度订阅流 |
| C16 浏览器冷启动 | ✅ MVP 已修复 | daemon 内 fetcher 复用（`enable_fetcher_reuse`），失败自动重建 |
| C17 模型常驻 | ⏳ M3 | Model Registry 计划不变 |
| C18 进程隔离 | ✅ 已修复 | 作业级 asyncio.Task 隔离 + 取消 + 失败分类（子进程 worker 留 M3） |
| C19 GPU 准入 | ⏳ M3 | 调度器计划不变 |
| C20 跨进程缓存 | ✅ MVP 已修复 | daemon 进程内共享内存 LRU + 磁盘层 |
| C21 Windows 入口 | ⏳ 待办 | daemon/CLI 均以 `python -m` 验证；控制台脚本待打包验证 |

---

## 3. 产品定位与设计原则

### 3.1 定位

- **形态**：单机常驻服务 `urlparserd` + 三个一等公民入口：**MCP server**（Agent 首选）、**CLI v2**（人 + 脚本 + 瘦客户端）、**HTTP API**（跨语言/跨机集成）。
- **不变**：本地优先、中文平台深度适配（小红书/知乎/微信/B 站）。默认路径零 token 成本、数据不出本机；唯一例外是**结构化抽取（填表）默认走 DeepSeek API**（决策 D9，需显式调用），云端 ASR/VLM 仍为显式配置的降级/增强。
- **对标**：本地版的 Firecrawl（服务形态 + 工具面）× Crawl4AI（本地 LLM 抽取）× 自研中文平台护城河。

### 3.2 设计原则（后续所有决策的裁判标准）

| 原则 | 含义 |
|---|---|
| P1 Agent 优先 | 每个功能先回答"Agent 怎么用"：JSON 契约、确定性错误码、流式进度、幂等 |
| P2 算力常驻 | 浏览器、模型、缓存、登录态全部常驻复用；冷启动只发生一次 |
| P3 预算制 | 每个请求可声明时间/算力/成本预算，超预算优雅降级并报告，绝不无限等待 |
| P4 快路径优先 | 元数据/静态页走 HTTP + trafilatura + curl_cffi（毫秒级），浏览器只做兜底 |
| P5 可观测 | 每次调用返回耗时分解（fetch/parse/transcribe/comprehension）+ 策略轨迹 + 重试记录 |
| P6 本地护栏 | SSRF 防护、私有 IP 拦截、cookie 保险库加密、代理白名单；对外端口默认仅回环 |
| P7 渐进兼容 | v3 的 Python API 与 CLI 语义在过渡期保持可用；新契约用版本号隔离 |
| P8 进程隔离 | 浏览器、模型推理放在可重启的 worker 子进程；一个崩溃不影响全局 |

---

## 4. 目标用户与核心场景

| 场景 | 用户故事 | 关键诉求 |
|---|---|---|
| S1 资料抓取 | "帮我把这 30 个链接整理成带原文的笔记" | 批量、快路径、图片下载、缓存复用 |
| S2 视频消化 | "把这个 B 站视频转成文字再总结" | 元数据先行 → 转录 → 可选理解；长任务流式进度 |
| S3 研究调研 | "按这些关键词抓一批知乎/公众号文章并结构化" | 搜索/列表页 crawl（P2）、JSON Schema 抽取（P1） |
| S4 本地知识库 | "每晚把收藏夹增量转成 Markdown 入库" | 定时批量、断点续传、幂等 |
| S5 疑难站点 | "这个站要登录，帮我登录一次以后都能抓" | 交互式登录、登录态持久化与自动刷新 |

---

## 5. 产品功能规划

优先级定义：**P0** = v4.0 发布门槛；**P1** = v4.1–4.2；**P2** = 愿景。

### 5.1 P0 — 服务化与契约（发布门槛）

| 功能 | 描述 | 验收标准 |
|---|---|---|
| F1 守护进程 `urlparserd` | 常驻单机服务：浏览器池 + 模型注册表 + 任务队列 + SQLite 状态；CLI 自动拉起/附连（`urlparser parse` 无 daemon 时自动 `daemon start` 或降级 standalone） | 连续 100 次解析，浏览器/模型冷启动仅第 1 次；单条快路径解析 ≤1s |
| F2 MCP server | stdio 模式（默认，决策 D11 不做 HTTP 面）；工具面见 §7.3；与 Claude Code/Hermes/Cursor 即插即用 | `mcp list-tools` 可见全部工具；端到端示例 Agent 可用 |
| F3 结果 Schema v1 | 统一 JSON 结果含 `schema_version`、`job_id`、`timing` 分解、`strategy_trace`、结构化错误（见 §7.1/§7.2） | JSON Schema 文件随发布；P5 等价性测试升级为 schema 校验 |
| F4 元数据快路径 | `mode=metadata`：只走 API/yt-dlp/HTTP，**不转录、不渲染**；修复 C1 | B 站视频元数据 ≤2s 返回，零模型加载 |
| F5 CLI v2 契约化 | 退出码、stdout=结果 / stderr=事件、`--json`、`--fields`、`--budget`、`--strategy`、`--timeout`、`--metadata-only`、stdin 输入（见 §7.5） | 修复 C1–C5、C9–C15；shell 管道测试进 CI |
| F6 作业模型 | 长任务（转录/理解/批量）异步提交：`job submit → poll → stream → result/cancel`；进度事件覆盖 fetch/parse/transcribe/comprehend 四段（修复 C12） | 取消后 5s 内释放 GPU；重启后 job 可恢复或明确标记失败 |
| F7 结构化错误码 | `E_FETCH_BLOCKED / E_FETCH_LOGIN / E_FETCH_TIMEOUT / E_PARSE_EMPTY / E_TRANS_NO_GPU / E_DEP_MISSING / E_BUDGET_EXCEEDED …` 每码带 `retryable` 与 `hint` | 错误分类测试 ≥95% 命中率 |

### 5.2 P1 — 站点级图文提取优化 + 算力最大化与能力补齐

#### 5.2.1 P1 首发：站点级图文提取优化（打磨已有能力，决策 D12）

按 2026-06 决策，P1 首个交付是**站点级图文提取优化**——不是新造轮子，而是把 v3 已有的"解析 + 图片下载"能力打磨到可量产，再批量化。

| 项 | 现状问题（源码核实） | 优化动作 |
|---|---|---|
| 图片真实化 | 微信路径把图片替换为 `[图片:…]` 占位符，data-src 已取到却丢弃 | 输出真实 `![]()` 图片链接，保持文中位置 |
| 缩略图误杀 | `_html_to_markdown` 按 `_w100/_thumb/_s.png` 等后缀过滤，误伤正常图 | 改为"URL 规范化取原图"（剥离 imageMogr2/缩略后缀），而非直接删除 |
| 反盗链下载 | `ImageDownloader` 仅带 UA，微信/知乎/小红书图片大量 403 | 按平台注入 Referer/专用头；失败自动换浏览器下载兜底 |
| 下载异步化 | 图片下载在 parse 返回前串行阻塞 | daemon 内异步执行，产物登记进 `artifacts` 清单 |
| 链接/结构保留 | trafilatura favor_precision 过度剪枝（PHASE1 实测 3 例链接 0 分） | 双通道合并：trafilatura 正文 + BS4 重建链接/图片/表格 |
| 表格与代码块 | `<table>/<pre>` 未转 Markdown | 补表格/代码块转换 |
| 截断误伤 | cutoff 关键词含宽泛词"推荐" | 平台化截断词表 + 收紧位置保护 |
| 元数据清洗 | author 含简介文本（v3 已知缺陷） | author/摘要字段 clean 化 |
| 站点批量（轻量） | 无 URL 发现、无断点续传、无失败分类 | sitemap + 列表页链接发现 → 详情页图文抓取（job + resume + manifest；深度 crawl 仍留 P2） |

验收：20 站图文样例人工质量验收；图片下载成功率 ≥95%；批量断点续传可用。

> 交付状态（M4 后更新）：9 项全部实现（见 `docs/v4-implementation-plan.md` §七）；"20 站人工验收与 ≥95% 图片成功率"需在有外网与浏览器权限的真实环境执行，本机沙箱无法运行。

#### 5.2.2 其余 P1 能力

| 功能 | 描述 | 验收标准 |
|---|---|---|
| F8 算力调度器 | GPU/NPU/CPU 设备放置表 + 任务准入控制（显存申报）+ 转录流水线重叠（下载/转码在 CPU，与 GPU 推理并行）+ 跨任务动态批处理 | 双任务并发转录总时长 ≤ 1.5× 串行；OOM 事故为 0 |
| F9 模型常驻与预热 | FunASR/Whisper/SmolVLM 按策略常驻（keepalive + LRU 卸载 + 显存预算，见 §8.4）；`daemon prewarm` 命令 | 常驻命中请求无模型加载开销；卸载阈值可配 |
| F10 结构化抽取（填表，P1 后期） | `extract` 能力：JSON Schema → 结构化结果；**默认 DeepSeek API**（决策 D9），本地 llama.cpp/OpenVINO 小模型仅作离线降级档 | schema 一致性测试；离线档零 API key 可跑 |
| F11 平台广度 | 抖音/快手/微博/豆瓣 专用适配器（复用 yt-dlp + API 模式 + 登录态框架）；X/TikTok 走降级链 | 每平台健康度用例入 `auto_research` 数据集 |
| F12 PDF/文档 | Marker 2 集成（CPU 可跑）：PDF→Markdown，含公式/表格；文件输入走同一 `parse` 工具面 | PDF 解析质量对 OmniDocBench 样张人工抽检 |
| F13 字幕内容落地 | 修复 v3 已知缺陷：字幕内容下载、真实时间戳；yt-dlp 章节 + SponsorBlock 段标记 | 字幕分段时间戳非全零；SponsorBlock 段输出到 `chapters` 字段 |
| F14 说话人分离（可选件） | WhisperX/pyannote 作为 `diarize=true` 可选管线 | 双人播客样本说话人归并准确率达标 |

### 5.3 P2 — 愿景

| 功能 | 描述 |
|---|---|
| F15 站点级抓取（深度版） | `crawl/map`：sitemap 发现 + 深度控制 + 断点续传 + 速率限制（对齐 Firecrawl crawl、trafilatura focused crawl）；轻量版已在 P1 §5.2.1 落地 |
| F16 本地搜索集成 | 检索→抓取→入库闭环（对齐 Tavily/Exa），优先接本地搜索引擎避免云端依赖 |
| F17 云端增强开关 | Gemini/Qwen-VL-Max 视频理解、gpt-4o-transcribe 精度档、托管代理（ZenRows 类）——全部显式 `remote_backend` 配置 |
| F18 多机模式 | daemon 集群：抓取节点与 GPU 推理节点分离（`--worker-role`），兼容家用多机 |
| F19 增量订阅 | 定时任务 + 变更检测（hash 对比）自动重抓，产出变更 diff |

---

## 6. 核心用户旅程（v4 目标态）

**S2 视频消化（Agent 视角）**：

```
Agent: parse_url(url, mode="metadata")          → 2s 返回标题/时长/UP主（零模型加载）
Agent: transcribe(url, async_job=true)          → 立即返回 job_id + SSE 进度流（下载→转码→转录 四段事件）
Agent: 接收进度事件，监督完成                      → 结果带 schema_version + timing 分解
Agent: comprehend(url, mode="audio_video")       → 复用已缓存音频 + 常驻 VLM，不重复下载
Agent: cancel(job_id)                            → 5s 内释放 GPU
```

**S4 本地知识库（定时任务视角）**：

```
urlparser job submit-batch urls.txt --profile nightly --resume
  → 快路径优先，浏览器兜底；失败项分类（登录墙/反爬/死链）
  → 断点续传；输出 manifest.json（每 URL 的产物路径 + 状态 + 重试轨迹）
```

---

## 7. 对外契约设计

### 7.1 统一结果 Schema v1（节选）

```jsonc
{
  "schema_version": "1.0",
  "job_id": "j_01J...",
  "status": "succeeded",            // succeeded | partial | failed | cancelled
  "url": "https://...",
  "platform": "bilibili",
  "content_type": "video",
  "title": "…",
  "content": "…",                   // markdown
  "author": "…",
  "publish_date": "…",
  "metadata": { "…": "…" },
  "video_metadata": { "duration": "…", "views": "…", "chapters": [], "sponsor_segments": [] },
  "transcription": {
    "engine": "funasr", "language": "zh", "duration": 123.4,
    "text": "…", "segments": [{ "start": 0.0, "end": 2.1, "text": "…" }],
    "diarized": false
  },
  "comprehension": { "mode": "audio_video", "engine": "openvino/qwen3-vl-2b-int4", "timeline": [] },
  "extract": null,                  // P1 后期：结构化抽取结果（DeepSeek API，D9）
  "artifacts": {                    // 产物清单（修复图片/音频产物不可见问题）
    "images": ["out/article_1/images/xx.jpg"],
    "audio": "out/article_1/audio.wav",
    "markdown": "out/article_1/result.md"
  },
  "timing": {                       // 修复 P5：全链路可观测
    "fetch_ms": 812, "parse_ms": 96, "transcribe_ms": 4120, "comprehension_ms": 0,
    "model_load_ms": 0,             // 常驻命中为 0，暴露浪费
    "total_ms": 5028
  },
  "strategy_trace": ["http_fast", "curl_cffi", "playwright"],   // 实际走过的降级链
  "retry_attempts": [{ "strategy": "playwright", "error_code": "E_FETCH_TIMEOUT", "duration_ms": 30000 }],
  "cache": { "hit": false, "age_s": null },
  "error": null,                    // v3 兼容: 自由文本（字符串）
  "error_detail": {                 // v4 结构化错误
    "code": null, "message": null, "retryable": false, "hint": null
  }
}
```

约定：`schema_version` 变更只增不改；`P4/P5` 测试升级为**契约测试**（结构指纹 + 字段语义断言），替代目前的纯快照。

### 7.2 结构化错误码（节选）

| 码 | 语义 | retryable | Agent 处理建议 |
|---|---|---|---|
| `E_FETCH_BLOCKED` | 被反爬/验证码拦截 | true（换策略/代理） | 升级到浏览器策略或报告用户 |
| `E_FETCH_LOGIN_REQUIRED` | 登录墙 | true | 触发交互登录流程（一次性） |
| `E_FETCH_TIMEOUT` | 超预算超时 | true（加预算重试） | 重试或放弃 |
| `E_PARSE_EMPTY` | 页面可取但正文为空 | false | 报告为无内容 |
| `E_DEP_MISSING` | 依赖缺失（ffmpeg/funasr） | false | 执行 `urlparser doctor --fix` |
| `E_DEVICE_UNAVAILABLE` | GPU/NPU 不可用且配置要求 | false | 降级 CPU 或改配置 |
| `E_BUDGET_EXCEEDED` | 超预算主动中止 | false | 加预算或降级模式 |
| `E_VALIDATION` | 输入非法（非 http(s)/内网 IP） | false | 修正输入 |
| `E_MODEL_LOAD` | 模型加载失败 | true（换引擎） | 切换引擎 |
| `E_INTERNAL` | 内部异常 | true（幂等重试） | 重试一次后报告 |

### 7.3 MCP 工具面（小且正交，8 个）

| 工具 | 参数要点 | 返回 |
|---|---|---|
| `parse_url` | `url, mode(metadata|content|full), strategy, budget_ms, fields[]` | Schema v1 结果 |
| `parse_batch` | `urls[] 或 input_file, profile, concurrent, resume` | job（异步） |
| `transcribe` | `url 或 file_path, engine, language, diarize, async` | job 或结果 |
| `comprehend_video` | `url, mode, max_frames, engine` | job 或结果 |
| `extract_structured` | `url(s), json_schema, backend=deepseek|local` | 结构化对象（P1 后期，默认 DeepSeek API） |
| `get_job` / `cancel_job` | `job_id` | 状态 + 进度 / 取消确认 |
| `cache_inspect` / `cache_invalidate` | `url 或 pattern` | 命中信息 / 失效确认 |
| `doctor` | — | 环境健康报告（GPU/NPU/依赖/浏览器） |

设计要点：所有工具**同步返回小结果、异步返回 job_id**；进度统一经 MCP 的 progress/streaming 机制；错误统一为 §7.2 错误码。（M2 已交付：除 `extract_structured` 外的 9 个工具已实现于 `src/urlparser/mcp_server.py`，入口 `python -m urlparser.mcp`，stdio 冒烟通过。）

### 7.4 HTTP API（决策：暂不开发，D11）

按 2026-06 决策 **v4 暂不实现 HTTP 面**，只交付 MCP + CLI v2。Gateway 的校验/Schema/作业层与入口解耦，若未来有跨语言/跨机需求，可低成本补回原生 REST（`POST /v1/jobs` + `GET /v1/jobs/{id}/events` SSE），届时默认回环监听 + token 鉴权。

### 7.5 CLI v2 命令矩阵与 I/O 契约

```
urlparser daemon start|stop|status|prewarm|logs
urlparser parse <url> [--mode metadata|content|full]
           [--strategy http|cffi|playwright|bb|auto] [--budget 30s] [--timeout 15s]
           [--metadata-only] [--json] [--fields title,content] [--no-cache] [--ttl 48h]
           [--profile fast|quality|video] [--output DIR] [--progress]
urlparser parse-batch [FILE|-] [--resume] [--manifest manifest.json] ...
urlparser transcribe <url|file> [--async] [--engine funasr|whisper|auto] [--diarize] ...
urlparser job list|show|result|cancel <job_id>
urlparser extract <url> --schema schema.json
urlparser doctor [--fix]
```

**I/O 契约（机器消费约定，修复 C10/C13/C14）**：

| 通道 | 内容 |
|---|---|
| stdout | 仅结果（`--json` 单行 JSON；默认 markdown）；**零日志** |
| stderr | 人读诊断 + `--progress` 时 JSON-lines 进度事件（四段全覆盖） |
| 输入 | `parse-batch -` 接受 stdin，每行一个 URL；`--json-lines` 支持逐行 JSON 输入 |
| 退出码 | `0` 全部成功｜`1` 部分失败（带 manifest）｜`2` 输入/参数错误｜`3` 依赖缺失｜`4` 全部失败｜`5` 预算超时｜`130` 已取消 |
| 幂等 | 同 URL 同 profile 重复调用命中缓存返回 `cache.hit=true`，不重复计费算力 |

### 7.6 配置与 profile

`~/.urlparser/config.toml`（层级：默认 → 用户配置 → 请求参数 → profile 覆盖）：

```toml
[profiles.fast]            # Agent 默认
strategy = "auto"          # http → cffi → playwright
budget = "30s"
render = "fallback"

[profiles.video]           # 视频消化
transcribe = true
engine = "auto"            # funasr(zh) / whisper(en) 自动路由
device = { asr = "cuda:0", vlm = "npu", fallback = "cpu" }

[models]                   # 常驻与显存预算（见 §8.4）
keepalive = { "funasr-sensevoice" = "always", "smolvlm-500m" = "idle-10m" }
vram_budget_gb = 4.0

[security]
allow_private_ips = false
allowed_schemes = ["http", "https"]
proxy = "http://127.0.0.1:7890"
cookies_vault = "~/.urlparser/vault/"

[remote]                   # ASR/VLM 默认关闭；结构化抽取默认 DeepSeek（D9）
llm_endpoint = "https://api.deepseek.com/v1"
llm_model = "deepseek-chat"
asr_endpoint = ""
vlm_endpoint = ""
```

---

## 8. 技术架构

### 8.1 总体架构

```
┌─────────────────────────── 入口层 (可多实例) ───────────────────────────┐
│  MCP Server (stdio)           CLI v2 (瘦客户端)    (HTTP API 暂缓, D11) │
│  ───────────────┬───────────────────┬───────────────────┬─────────────  │
│                 │ 统一 Gateway：鉴权 → 参数校验(SSRF) → profile 展开     │
│                 │            → 快路径路由 → 作业提交/同步执行             │
└─────────────────┴───────────────────┬───────────────────────────────────┘
                                      │
┌─────────────────────── 调度与状态层 (urlparserd 主进程) ─────────────────┐
│  Job Scheduler（优先级队列 / 预算与准入 / 设备放置 / 取消与看门狗）        │
│  Progress Hub（四段事件 → SSE / MCP progress / stderr JSONL 扇出）       │
│  Cache（磁盘 SQLite + 常驻内存层，修复 C20）  │  JobStore（SQLite/WAL）   │
│  Cookie Vault（AES-GCM 加密 + 过期自动刷新） │  Metrics/日志（结构化）    │
└───────────────┬───────────────────────────────────┬─────────────────────┘
                │ 任务下发                            │ 资源池管理
┌───────────────┴──────────────┐   ┌────────────────┴─────────────────────┐
│ Worker Pool（子进程隔离）      │   │ 资源池（常驻，修复 C16/C17）          │
│  ├ fetch worker × N           │   │  ├ Browser Pool：Playwright 实例池   │
│  │   (http/cffi 快路径线程)    │◄──┤  │    （预热页面、登录态 context 复用）│
│  ├ parse worker × N           │   │  ├ Model Registry：ASR/VLM/LLM 常驻  │
│  ├ transcribe worker (GPU 准入)│   │  │    （keepalive + LRU 卸载 + 预算） │
│  └ comprehension worker       │   │  └ 设备管理器：CUDA/NPU/iGPU/CPU 探测 │
└───────────────────────────────┘   └─────────────────────────────────────┘
                │ 结果/产物落盘（manifest.json 全量登记）
                ▼
       ~/.urlparser/{cache.db, jobs/, artifacts/, vault/}
```

要点：worker 子进程崩溃由看门狗重启并**只重放该 job**（修复 C18）；主进程无重计算负载，可长期稳定。

### 8.2 关键组件设计

| 组件 | 职责 | 关键决策 |
|---|---|---|
| Gateway | 入口唯一校验点 | SSRF 校验（scheme 白名单、DNS 解析后拦截私网 IP、`file://` 禁用）、profile 展开、预算声明 |
| Job Scheduler | 队列/准入/取消 | 三级优先级（interactive > batch > nightly）；GPU 任务按显存申报准入（修复 C19）；预算定时器到期强制优雅中止并回传部分结果 |
| Progress Hub | 四段事件扇出 | 统一 `stage=fetch/parse/transcribe/comprehend`、`phase=start/progress/done/error`；同一 job 可同时被 SSE 与 CLI stderr 消费（修复 C12） |
| Browser Pool | 浏览器复用 | 实例池 + 页面池；登录态 context 按平台缓存；空闲超时回收；崩溃自愈换新实例 |
| Model Registry | 模型生命周期 | 见 §8.4 |
| JobStore | 作业持久化 | SQLite WAL；重启可恢复排队任务（明确标记部分产物） |
| Worker Pool | 进程隔离执行 | 复用 v3 的 fetcher/parser/transcriber 代码，**不做重写**，仅加执行壳与事件上报 |

### 8.3 与 v3 代码的映射（最小改造原则）

| v3 模块 | v4 角色 | 改造点 |
|---|---|---|
| `core.py` | 迁移为 worker 内的执行引擎 | 拆出 `strategy_trace` 上报、预算检查点、四段进度事件 |
| `fetcher/*` | fetch worker | 每个策略增加 `cost_ms/error_code` 上报；快路径策略补 URL 直取入口 |
| `parser/*` | parse worker | 平台适配器加注 Schema 字段；新增平台沿用 ParserRegistry 注册 |
| `transcriber/*` | transcribe worker | 模型加载改为经 Model Registry 取常驻实例；字幕内容落地（F13） |
| `comprehension/*` | comprehension worker | VLM 常驻化；新增 OpenAI 兼容远端后端（F17） |
| `storage/*` | Cache/JobStore | 缓存跨进程共享 + manifest 输出 |
| `auto_research/*` | 质量门禁 | 契约测试升级：Schema 校验 + 错误码分类 + 常驻命中率基准 |
| `skill/*` | 迁移为 MCP 的宣发入口 | SKILL.md 改为"装 MCP + 装 daemon"引导 |

### 8.4 算力本地最大化设计（P2 原则落地）

**8.4.1 设备放置表（默认，可由 profile 覆盖）**

| 负载 | 首选设备 | 次选 | 说明 |
|---|---|---|---|
| FunASR（中文转录） | NVIDIA CUDA | CPU | 复用 v3 的显存自适应分段逻辑，提升为注册表级常驻 |
| faster-whisper（英文/多语言） | NVIDIA CUDA | CPU（whisper.cpp GGML） | 按 `language` 自动路由引擎 |
| VLM 逐帧理解 | Intel NPU / iGPU（OpenVINO int4） | CPU（llama.cpp smolvlm） | 与 ASR **分设备并行**：同一视频转录+理解可同时跑 |
| 结构化抽取 LLM | **DeepSeek API**（默认，D9） | 本地 llama.cpp 小模型（离线档） | P1 后期引入 |
| 下载/转码/图片 | CPU | — | ffmpeg 保持 CPU，与 GPU 推理流水线重叠 |

**8.4.2 模型常驻与显存预算（修复 C17）**

- 每个模型在 Registry 声明：`显存占用 / 加载耗时 / 卸载策略`。例：SenseVoiceSmall ≈0.3GB、SmolVLM-500M int4 ≈0.8GB、Qwen3-VL-2B int4 ≈2GB。
- 策略三档：`always`（核心模型，如 SenseVoice）、`idle-Nm`（空闲 N 分钟卸载）、`never`（即用即载，超预算时优先淘汰）。
- 准入控制：job 提交即申报显存，调度器保证 `Σ 常驻 + 在跑 ≤ vram_budget_gb`，超出排队（修复 C19）。
- 预热：`daemon prewarm` 提前加载，Agent 会话开始即热。

**8.4.3 流水线重叠与批处理**

```
单个视频 job：
  [CPU: 下载+转码] ──▶ [GPU: ASR 分段推理] ──▶ [NPU: VLM 逐帧] (与下一 job 的 CPU 段重叠)
批量转录：
  CPU 提前转码 2~3 个任务的音频 → GPU 连续推理（跨任务 dynamic batch，复用 v3 batch_size_s）
```

目标指标：GPU 空闲率 <20%（对批量场景）；同机"转录 + 理解"双任务总时长 ≤ 1.5× 串行。

**8.4.4 结果缓存跨进程常驻（修复 C20）**

- 内存层移入 daemon 主进程，LRU 1000 条；磁盘 SQLite 保留。
- 中间产物缓存分级：`页面HTML / 下载音频 / 转录文本 / 关键帧`，下游任务（理解）可复用上游产物，**同 URL 第二次视频理解零下载、零转录**。

### 8.5 安全设计（P6）

| 面 | 措施 |
|---|---|
| SSRF | scheme 白名单 `http/https`；DNS 解析后拦截私网/回环/链路本地 IP（默认开，`allow_private_ips` 显式关闭）；重定向逐跳重校验 |
| 凭据 | Cookie 从明文 JSON 迁移到 AES-GCM 加密保险库（`cookies_vault`），仅在 worker 内存中解密使用 |
| 网络 | 统一代理出口（`security.proxy`）；按域名速率限制（防对单一站点形成攻击性抓取） |
| 服务暴露 | v4 无 HTTP 面（D11）；MCP stdio 由 Agent 进程拉起；日志脱敏（cookie/authorization 不落盘） |
| 内容安全 | 抓取内容按数据落盘，不入日志；`artifacts/` 默认 30 天清理策略 |
| 隐私边界 | 仅结构化抽取（填表）启用时将页面文本发送至 DeepSeek API（D9）；可配 `allow_remote_extract=false` 强制离线；其余链路全本地 |

### 8.6 可靠性与可观测性

- **看门狗**：worker 心跳 + 崩溃重启 + job 重放（幂等）；主进程自身由 systemd / `daemon start --foreground` 管理。
- **预算执行**：每 job 挂预算定时器，超时走优雅中止（保存部分结果 + `E_BUDGET_EXCEEDED`），修复 C3。
- **指标**：常驻命中率、模型加载次数、GPU 利用率、策略成功率矩阵（平台 × 策略），喂回 `auto_research` 形成持续回归。
- **审计**：每次调用记录 `timing + strategy_trace + error_code`，可直接回放定位。

---

## 9. 实施路线图

| 里程碑 | 内容 | 验收 |
|---|---|---|
| **M0 底座（2 周）** | Schema v1 + 错误码 + 契约测试框架；`core` 四段进度事件补齐（修复 C12） | P0–P5 测试全绿且含 schema 校验 |
| **M1 服务化 MVP（3 周）** | `urlparserd` 主进程 + JobStore + Progress Hub + Browser Pool 首版；CLI v2 瘦客户端 + 退出码/stdin/`--json`（C9–C15 修复） | 连续 100 次解析仅 1 次冷启动；快路径 ≤1s |
| **M2 Agent 接入（2 周）** | MCP server（stdio）+ 7 工具面（`extract_structured` 随 M5 上线）+ `parse_url(mode=metadata)` + 作业提交/取消（F1–F7） | Claude Code/Hermes 端到端演示通过 |
| **M3 算力最大化（4 周）** | Model Registry 常驻/预热/预算 + GPU 准入队列 + 流水线重叠 + 设备放置（F8/F9）；`doctor --fix` | 双任务并发 ≤1.5× 串行；OOM=0；常驻命中率可观测 |
| **M4 图文提取优化（4 周）** | §5.2.1 全项：图片真实化/反盗链/双通道合并/表格代码块/站点批量轻量版 | 20 站图文样例验收；图片成功率 ≥95%；断点续传可用 |
| **M5 结构化抽取（2 周）** | F10 填表（默认 DeepSeek API）+ MCP `extract_structured` 上线 | schema 一致性测试；端到端 Agent 演示 |
| M6+ | PDF（F12）、字幕/章节/SponsorBlock（F13）、抖音/微博（F11）、说话人分离（F14） | auto_research 数据集扩至新平台并达标 |
| M7+ | crawl/map 深度版、搜索集成、多机、订阅（P2 视反馈排期） | — |

每个里程碑同时产出：功能验收 + 契约测试 + 文档更新；`skill/` 目录随 M2 同步改为 MCP 引导。

## 10. 兼容与迁移策略

- **Python API**：v3 的 `parse/parse_batch/UrlParser` 保持可用（内部升级为自动连接本机 daemon，失败降级内嵌执行）——上层 Hermes 集成零迁移。
- **CLI**：v3 命令保留别名；`--transcribe` 语义不变；新增 `--metadata-only` 等为增量参数；退出码语义文档化后进入 1 个版本宽限期。
- **Skill**：v4 起 SKILL 引导装 MCP；老 Skill 路径保留一个版本。
- **Schema**：`schema_version` 前置；v3 字段映射为 v4 子集，保证旧消费者不碎。

## 11. 风险与开放问题

| 风险/问题 | 缓解 |
|---|---|
| daemon 长期驻留的资源占用（常驻模型 + 浏览器 ≈ 1–4GB 内存） | 全部策略可配；`idle` 默认卸载；`daemon stop` 一键释放 |
| MCP 与 HTTP 双面带来的攻击面 | 默认回环 + token + SSRF 护栏（§8.5） |
| 上游 API（小红书 xhshow、B 站 playurl）签名失效的维护成本 | 平台适配器版本化 + `E_FETCH_BLOCKED` 快速感知 + 降级链兜底 |
| GPU 调度复杂度（批处理 vs 延迟冲突） | interactive 任务优先抢占、batch 任务可拆分 |
| ~~开放问题 ①~~ **已决策（D9）**：结构化抽取后端 | 默认 DeepSeek API；本地小模型仅作离线降级档 |
| ~~开放问题 ②~~ **已决策（D10）**：多 Agent 共享同一 daemon | 共享（缓存/模型复用最大化），任务可见性按 token 隔离 |
| ~~开放问题 ③~~ **已决策（D11/D12）**：范围与优先级 | 暂不做 HTTP；先站点级图文提取优化，后结构化抽取 |

## 12. 附录：决策记录（ADR 摘要）

| ID | 决策 |
|---|---|
| D1 | 引入常驻 daemon，CLI 瘦客户端化；standalone 降级模式保证单机无服务可用 |
| D2 | MCP 为一等入口；HTTP 为可选面；三入口共享同一 Gateway 与 Schema |
| D3 | 结果 Schema v1 含 `timing/strategy_trace/artifacts`，修复"结果不可观测" |
| D4 | 错误码模型替代自由文本；每码带 `retryable + hint` |
| D5 | 预算制贯穿（时间/显存/设备），替代写死超时 |
| D6 | 算力：模型常驻 + 分设备并行 + 跨任务批处理 + 流水线重叠 |
| D7 | 安全：SSRF 拦截、cookie 加密保险库、默认回环监听 |
| D8 | 最小改造：复用 v3 四层代码，只加执行壳、事件与注册表 |
| D9 | 结构化抽取默认后端 = DeepSeek API（用户决策）；本地小模型仅离线降级 |
| D10 | 多 Agent 共享同一 daemon；任务可见性按 token 隔离（用户决策） |
| D11 | HTTP API 暂不开发；Gateway 与入口解耦以便日后低成本补回（用户决策） |
| D12 | 优先站点级图文提取优化（打磨已有能力），其次结构化抽取（用户决策） |

---

*本文档基于 v3.3.1 源码核实的问题清单（§2）撰写；所有优先级可在 M1 交付后按实测数据调整。*
