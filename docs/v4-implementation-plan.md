# urlparser v4 实施计划 — 阶段一：M0 底座 + M1 服务化 MVP

> 状态：待批准（批准后开始动代码）｜ 依据：`docs/product-plan-and-architecture.md`（决策 D1–D12）
> 本次执行范围：**M0 + M1**。M2–M5 为后续阶段大纲（见 §四）。

## 一、执行范围与目标

| 目标 | 验收标准 |
|---|---|
| 结果可被机器可靠消费 | Schema v1（`schema_version`/`timing`/`strategy_trace`/`artifacts`/`error.code`），契约测试全绿 |
| 错误可程序化决策 | 10 个错误码，每码带 `retryable+hint`；分类测试 ≥95% 命中 |
| 进度全程可监督 | fetch/parse/transcribe/comprehend 四段进度事件全覆盖（修复 C12） |
| 快路径可达 | `--metadata-only` ≤2s、`--strategy http` 毫秒级、`--budget` 预算制（修复 C1/C2/C3） |
| 常驻执行面 | `urlparserd` 守护进程：浏览器复用、作业提交/取消、跨进程缓存（修复 C16/C17/C20） |
| CLI 机器友好 | 退出码 0/1/2/3/4/5/130、stdout 纯结果/stderr 事件、stdin 管道、`--json/--fields`（修复 C9–C15） |
| 零回归 | v3 Python API 与 CLI 别名可用；现有 P0–P5 + health_check 全绿 |

## 二、任务分解（文件级）

### A. Schema v1 + 错误码（M0，约 300 行）
- `src/urlparser/schema.py`（新）：`SCHEMA_VERSION="1.0"`、`ErrorCode` 枚举（`E_FETCH_BLOCKED / E_FETCH_LOGIN_REQUIRED / E_FETCH_TIMEOUT / E_PARSE_EMPTY / E_DEP_MISSING / E_DEVICE_UNAVAILABLE / E_BUDGET_EXCEEDED / E_VALIDATION / E_MODEL_LOAD / E_INTERNAL`）、`StructuredError(code, message, retryable, hint)`、`TimingBreakdown`。
- `src/urlparser/models.py`：`ParseResult` 增 `schema_version / job_id / timing / strategy_trace / artifacts / cache`；`to_dict()` 输出 Schema v1 结构（旧字段保留，向后兼容）。
- `tests/framework/test_schema_contract.py`（新）：jsonschema 校验 `to_dict()` 输出。

### B. 四段进度事件（M0，约 150 行）
- `src/urlparser/core.py`：`_do_parse` / `_parse_with_retry` 在各 fetcher 策略调用点发射 `fetch` / `parse` 段事件（`extra.strategy` 标注策略名）；错误段带 `error_code`。
- `src/urlparser/comprehension/pipeline.py`：帧提取 / VLM 分析阶段发射 `comprehension` 段事件。
- 测试：mock `on_progress` 断言四段齐全、顺序正确、错误事件带码。

### C. 快路径 + 预算 + 策略控制（M0，约 200 行）
- `src/urlparser/core.py`：新增 `ParseOptions(mode=metadata|content|full, strategy, budget_ms, fields)`：
  - `metadata` 模式：仅 yt-dlp / 平台 API 元数据，跳过渲染与转录（修复 C1）；
  - `strategy` 强制/顺序控制接入 `FetcherFactory`（`http` = httpx/curl_cffi + trafilatura 毫秒级快路径）；
  - `budget_ms` 预算定时器，超时抛 `E_BUDGET_EXCEEDED` 并保存部分结果（修复 C3）。
- `src/urlparser/fetcher/http_fetcher.py`（新）：轻量 HTTP 快路径 fetcher（httpx + curl_cffi 可选 + trafilatura 提取）。
- 测试：metadata 模式不加载模型；budget 超时返回部分结果。

### D. 错误分类接入（M0，约 150 行）
- `src/urlparser/errors.py`（新）：`classify_error(exc, platform, stage)` 映射（登录墙 / 超时 / 依赖缺失 / 反爬 → 对应错误码）。
- 遍历 `core / fetcher / parser / transcriber` 的 `ParseResult(error=...)` 写入点统一替换。
- 测试：badcase 样本集分类命中率 ≥95%。

### E. urlparserd 守护进程（M1，约 600 行）
- `src/urlparser/daemon/`（新包）：
  - `__main__.py`：`python -m urlparser.daemon [--foreground]`；
  - `server.py`：asyncio 主循环，**回环 TCP + JSON-lines 私有控制协议**（非 HTTP 面，符合 D11）；
  - `jobstore.py`：SQLite WAL（jobs 表：状态 / 预算 / 产物路径），重启恢复排队任务；
  - `progress_hub.py`：四段事件扇出（订阅者拉流）；
  - `worker.py`：子进程执行壳（复用 core；崩溃由看门狗重启并只重放该 job，修复 C18）；
  - `client.py`：本地客户端库（CLI / 库共用）。
- 浏览器复用首版：worker 内 Playwright 实例池化复用（模型常驻留 M3）。
- 缓存：内存 LRU 移入 daemon 主进程（修复 C20），磁盘 SQLite 沿用。

### F. CLI v2 契约化（M1，约 500 行）
- `src/urlparser/cli.py` 重构：
  - 新增参数：`--json / --fields / --budget / --timeout / --strategy / --metadata-only / --profile / --progress`；
  - `parse-batch [FILE|-]` 支持 stdin；`job submit|list|show|result|cancel`；`doctor [--fix]`；`daemon start|stop|status`；
  - 退出码语义：0 全部成功 / 1 部分失败 / 2 参数错误 / 3 依赖缺失 / 4 全部失败 / 5 预算超时 / 130 已取消；
  - stdout 仅结果、stderr 人读诊断 + JSON-lines 事件（现有 Cookie 提示等日志全部归 stderr）。
- `src/urlparser/config.py`：`load_config()` 读 `~/.urlparser/config.toml` + profile 展开（fast/quality/video）。
- 自动附连：无 daemon 时自动 `daemon start`，失败降级 standalone（D1）。
- 测试：`test_p3_interface_consistency.py` 扩展退出码 / 管道 / JSON 契约。

### G. doctor 自检（M1，约 150 行）
- `src/urlparser/doctor.py`（新）：探测 python / ffmpeg / playwright / GPU（NV + Intel NPU）/ 关键依赖 / daemon 状态，输出健康报告；`--fix` 调 `dependency_installer`。

### H. 文档与测试收尾
- `SKILL.md` / README 增补 CLI v2 用法与退出码表；`docs/product-plan-and-architecture.md` §2 问题清单逐条标注"已修复 / 待办"。
- 全量回归：`pytest tests/` + health_check + auto_research 抽样。

## 三、执行顺序

1. A→D（M0 数据面，先行，可并行）
2. B→C（M0 行为面）
3. E（daemon 骨架 + 浏览器复用 + 作业语义）
4. F（CLI v2 挂在 client 上，含 G doctor）
5. H 收尾 + 全量回归 + 契约验收

## 四、后续阶段大纲（不在本次执行）

- **M2（下次）**：MCP stdio server 7 工具面 + `parse_url(mode=metadata)` + 端到端 Claude Code/Hermes 演示。
- **M3**：Model Registry 常驻 / 预热 / 显存预算 + GPU 准入队列 + 流水线重叠 + 设备放置。
- **M4**：§5.2.1 图文提取优化 9 项（图片真实化 / 反盗链 / 双通道合并 / 站点批量轻量版）。
- **M5**：DeepSeek API 结构化抽取（填表）+ MCP `extract_structured`。
- M6+：PDF / 字幕章节 / 新平台 / 深度 crawl（P2 视反馈）。

## 五、风险与对策

| 风险 | 对策 |
|---|---|
| Windows 命名管道 / 回环协议与沙箱限制冲突 | 实现时优先 TCP 回环 + JSON-lines；本机开发验证 |
| 浏览器实例池复用导致跨任务污染（cookie / 页面状态） | 按平台分池 + 任务后清理 context；首版实例级隔离兜底 |
| 现有测试断言 stdout 内容被 CLI 契约改动打破 | 逐一更新断言，P3 测试先行改写 |
| daemon 常驻内存占用（浏览器 ~1GB） | `idle` 超时回收 + `daemon stop` 一键释放；standalone 降级保证无服务可用 |
| 预算中止与 asyncio 取消的交互（部分结果保存） | 检查点式保存：每阶段结束写 JobStore，取消仅丢当前阶段 |

## 六、交付状态与自审修订（M0+M1 实施后）

**结论：M0 + M1 已交付**，`pytest tests/framework -m "not integration"` 177 passed / 22 deselected（集成测试因沙箱无外网与命名管道限制无法运行，与改动无关）。

### 交付清单

| 任务 | 产出 | 测试 |
|---|---|---|
| A Schema v1 + 错误码 | `schema.py`（10 错误码 + StructuredError + TimingBreakdown）；`models.py` 契约字段 | `test_schema_contract.py` 8 例 |
| D 错误分类 | `errors.py` + core 出口接入 | `test_error_classification.py` 15 例（命中率 100%） |
| B 四段进度事件 | core 编排 + `comprehension/pipeline.py` 内部事件 | `test_progress_events.py` 4 例 |
| C 快路径/预算/策略 | `ParseOptions` + `fetcher/http_fetcher.py` + `mode=metadata` + budget 包装 | `test_fast_path.py` 7 例 |
| E daemon | `daemon/`（protocol/jobstore/server/client/__main__）+ core fetcher 复用 | `test_daemon.py` 8 例 |
| F CLI v2 | 退出码/stdin/manifest/daemon/job/doctor 子命令 + profile | `test_cli_contract.py` 6 例 |
| G doctor | `doctor.py`（子代理交付） | `test_doctor.py` 4 例 |

### 自审修订（与计划的偏离，均已回写文档）

1. **`error_detail` 而非 `error` 对象**：Schema v1 保留 `error` 字符串（v3 兼容），结构化错误放 `error_detail`；架构文档 §7.1 已同步。
2. **HTTP API 面未实现**（D11）：daemon 仅回环 TCP 私有协议。
3. **进程隔离为任务级**：MVP 用 asyncio.Task 隔离 + 取消；子进程 worker 与模型常驻留 M3。
4. **daemon 复用仅 fetcher 级**：`enable_fetcher_reuse` 单实例跨请求复用 Playwright，失败自动重建；模型常驻按计划留 M3。
5. **测试方式**：CLI/daemon 测试全部进程内（沙箱禁止子进程管道）；`cli.main(argv)` 接受参数以便测试。
6. **daemon 路径暂不支持 --cookies/--comprehension 透传**（MVP 默认配置），standalone 路径完整支持；M2 前补齐 payload 透传。
7. **`--resume` 断点续传未实现**（计划 §F 中留作 TODO）：manifest + stdin 已交付，resume 依赖 JobStore 恢复逻辑，并入 M3。

## 七、M2–M5 交付状态与自审修订

**结论：M2 + M3 + M4 + M5 已交付**，非集成测试 **216 passed** / 22 deselected。

### 交付清单

| 里程碑 | 产出 | 测试 |
|---|---|---|
| M2 MCP | `mcp_server.py` + `mcp.py` 入口（JSON-RPC stdio，10 工具面）；daemon runner 支持 transcribe/comprehension；SKILL 接入文档；UTF-8 强制 | `test_mcp_server.py` 12 例 + stdio 管道冒烟 |
| M3 算力 | `model_registry.py`（常驻/预热/keepalive 三策略/显存预算/回收）；FunASR/Whisper `preloaded_model` 注入；daemon `_WeightedGate` 显存准入 + `prewarm`/`models` 操作 + CLI `daemon prewarm` | `test_model_registry.py` 8 例 |
| M4 图文优化 | 微信图片真实化、缩略图还原 `_normalize_image_url`（替代误杀删除）、`ImageDownloader` 反盗链 Referer、图片下载 executor 异步化、trafilatura favor_recall 二次通道、表格/代码块转换、截断词表收紧、author 清洗 `clean_author`、`site_crawl.py` 站点 URL 发现 + CLI `discover` | `test_site_crawl.py` 8 例 |
| M5 填表 | `extract.py`（DeepSeek API 结构化抽取，merge/each 模式）；MCP `extract_structured`；CLI `extract --schema` | `test_extract.py` 11 例 |

### 自审修订

1. **`python -m urlparser.mcp` 入口**：实现文件为 `mcp_server.py`，新增 `mcp.py` 薄入口满足模块路径。
2. **Windows stdio 编码**：MCP 要求 UTF-8，`main()` 强制 `stdout/stderr.reconfigure(utf-8)`（GBK 管道下中文工具描述曾乱码）。
3. **M3 范围务实收窄**：常驻/预热/显存预算/准入门已交付；**流水线重叠与跨任务动态批处理未实现**（需 worker 流水线重构，留 M6+）；设备放置表落为文档配置而非代码默认（FunASR→CUDA、VLM→OpenVINO NPU/iGPU 已由现有 detect 逻辑支撑）。
4. **M4 缩略图策略反转**：从"按后缀删除"改为"URL 还原原图"，保留更多有效图片（原先 `_w100/_thumb` 等被误删）。
5. **M5 本地离线档未接入**：`backend=local` 明确报错（llama.cpp/OpenVINO 小模型抽取留待 M6+）；默认 DeepSeek（D9）。
6. **已知遗留（跨里程碑）**：C7 代理/SSRF 护栏、C8 缓存 TTL 参数、C17 模型常驻在 standalone/CLI 进程侧（daemon 侧已交付）、C21 Windows 控制台脚本打包验证、`--resume` 断点续传、daemon 透传 `--cookies/--comprehension`、`platform="default"` 泛平台映射（v3 既有缺陷）。

### 端到端冒烟记录（本机实测）

- `python -m urlparser.mcp`：initialize + tools/list + tools/call(doctor) 全部正确（UTF-8 中文正常）。
- `python -m urlparser parse https://example.com --standalone --strategy http --json`：Schema v1 全字段返回，1.29s，退出码 0。
- `python -m urlparser doctor --json`：检出 RTX 4060 Ti CUDA + 核心依赖全装；退出码契约 1/0/2 正确。
- `python -m urlparser extract` 缺 API key/坏 schema：stderr 报错 + 退出码 4（契约正确）。
