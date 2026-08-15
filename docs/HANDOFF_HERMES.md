# HANDOFF：urlparser v4 交付交接文档（给 Hermes）

> 交接对象：Hermes（本地 Agent 集成方 / 后续维护者）
> 交接人：DeepSeek Agent（会话内自主实施 + 自审）
> 基线提交：`7041163 feat(v4): M0-M5 阶段一交付`（已推送 origin/main）
> 日期：2026-06

---

## 1. 本次交付了什么

urlparser 从 v3.3.x（纯库 + CLI + Skill）升级到 **v4.0.0**，成为**本地 Agent 的常驻抓取工具**。核心变化一句话：**执行面常驻化（urlparserd）、接口机器化（Schema v1 / 退出码 / MCP）、算力复用化（模型注册表 / 浏览器复用）**。

| 里程碑 | 内容 | 关键文件 |
|---|---|---|
| M0 底座 | Schema v1 结果契约、10 结构化错误码、四段进度事件、快路径/预算/策略控制 | `schema.py`、`errors.py`、`fetcher/http_fetcher.py` |
| M1 服务化 | `urlparserd` 守护进程、CLI v2 契约、doctor 自检 | `daemon/`、`cli.py`、`doctor.py` |
| M2 Agent 接入 | MCP stdio 服务器（10 工具面） | `mcp_server.py` + `mcp.py` 入口 |
| M3 算力 | 模型注册表（常驻/预热/显存预算/GPU 准入） | `model_registry.py` |
| M4 图文优化 | 图片原图还原、反盗链、表格/代码块、author 清洗、站点 URL 发现 | `site_crawl.py` + core 改造 |
| M5 填表 | DeepSeek API 结构化抽取 | `extract.py` |

规划与自审文档：`docs/product-plan-and-architecture.md`（产品/架构，含决策 D1–D12）、`docs/v4-implementation-plan.md`（实施计划 + 全部自审修订记录，**接手前必读 §六、§七**）。

---

## 2. Hermes 接入方式（三选一，推荐 MCP）

### 2.1 MCP（推荐，10 工具）

```json
{
  "mcpServers": {
    "urlparser": { "command": "python", "args": ["-m", "urlparser.mcp"] }
  }
}
```

工具面：`parse_url` / `parse_batch` / `transcribe` / `comprehend_video` / `get_job` / `cancel_job` / `cache_inspect` / `cache_invalidate` / `doctor` / `extract_structured`。

- 执行优先经 urlparserd（自动拉起、浏览器/缓存/模型复用），daemon 不可用自动降级进程内；
- 结果 = Schema v1 JSON（`schema_version/timing/strategy_trace/error_detail`）；
- **正文按需**：默认不含 `content`（防大 JSON）；`parse_url/parse_batch` 传 `include_content=true` 即附带正文（截断至 `max_content_chars`，默认 20000）。元数据探测用默认，要读正文再开开关，无需退回 CLI；
- 长任务（转录/理解）经 daemon 异步作业，`get_job`/`cancel_job` 管理；
- `extract_structured` 需 `DEEPSEEK_API_KEY`（决策 D9，唯一云端依赖）。

> Hermes 集成（2026-08 确认）：**同意挂到 Hermes config.yaml 的 `mcp_servers`**，此后 Hermes 直接调用 `mcp_urlparser_*` 工具（parse_url/parse_batch/transcribe/comprehend_video/extract_structured/get_job/cancel_job/cache_inspect/cache_invalidate/doctor），不再走 `python -m urlparser` 子进程。

### 2.2 CLI v2（脚本/管道）

```bash
python -m urlparser parse <url> --metadata-only --json          # 秒级快路径
python -m urlparser parse <url> --strategy http --budget 30000 --json
cat urls.txt | python -m urlparser parse-batch - --manifest manifest.json
python -m urlparser daemon start|stop|status|prewarm
python -m urlparser job submit --url <url> --wait
python -m urlparser discover <url> -o urls.txt                  # sitemap+列表页 URL 发现
python -m urlparser extract --url <url> --schema schema.json    # DeepSeek 填表
python -m urlparser doctor [--json] [--fix]
```

**契约**：退出码 `0` 全部成功 / `1` 部分失败 / `2` 参数 / `3` 依赖缺失 / `4` 失败 / `5` 预算超时 / `130` 中断；stdout 仅结果、stderr 日志与 `--progress` JSON-lines 四段事件。

### 2.3 Python API（兼容）

v3 的 `parse/parse_batch/UrlParser/ParseConfig` 全部兼容；新增 `ParseOptions(mode/strategy/budget_ms)`、`schema.py`（`ErrorCode/StructuredError/TimingBreakdown`）、`model_registry.ModelRegistry`、`extract.extract_structured`、`daemon.DaemonClient`。`ParseResult` 新增字段：`schema_version/job_id/timing/strategy_trace/artifacts/cache/structured_error`（`to_dict()` 输出 `error_detail`，旧 `error` 字符串保留）。

---

## 3. 能力速查

| 需求 | 用什么 |
|---|---|
| 只拿视频元数据（不转录） | `parse --metadata-only` |
| 静态页毫秒级抓取 | `parse --strategy http`（curl_cffi 伪装→httpx，trafilatura 提取） |
| 限时抓取 | `--budget`（超时返回 E_BUDGET_EXCEEDED，退出码 5） |
| 中文视频转录 | `transcribe`（FunASR 常驻，daemon 内经注册表复用） |
| 视频理解 | `comprehend_video`（本地 VLM，需模型文件 + ffmpeg） |
| 批量站点图文 | `discover` 出 URL 列表 → `parse-batch -`（断点续传 TODO） |
| 页面填表 | `extract --schema`（DeepSeek） |
| 环境排障 | `doctor --json --fix` |

---

## 4. 已知遗留（接手时按此清单排期，详见计划文档 §七.6）

| # | 事项 | 建议优先级 |
|---|---|---|
| 1 | `--resume` 批量断点续传（manifest 已交付，resume 未实现；Hermes 认可排期） | 高 |
| 2 | SSRF/代理安全护栏（架构文档 §8.5 已规划未实现） | 低（单 Agent 本地用不急；多 Agent / 对外暴露时提级） |
| 3 | 缓存 TTL 参数、daemon 透传 `--cookies/--comprehension` | 中 |
| 4 | 流水线重叠与跨任务动态批处理（M3 收窄项） | 中 |
| 5 | 本地离线结构化抽取档（当前 `backend=local` 明确报错，仅 DeepSeek） | 低（D9 已定） |
| 6 | 字幕内容下载（时间戳全 0，v3 既有缺陷） | 中 |
| 7 | `platform="default"` 泛平台映射（v3 既有缺陷） | 低 |
| 8 | 新平台适配（抖音/微博/豆瓣/X）、PDF 支持、深度 crawl/map | P2 |

> 注：SenseVoice 无标点缺陷已按 Hermes brief（`.claude/brief_punc.md`）修复：`funasr.py` 加 `punc_model="ct-punc"`（不换主模型），加载失败自动降级无标点；测试 `test_funasr_punc.py` 4 例。

---

## 5. 环境与运维注意事项

- **Windows**：所有子进程经 `_subprocess_win.run_nowindow` 静默；MCP/CLI 强制 UTF-8 stdout；`urlparser` 控制台脚本建议统一用 `python -m` 前缀。
- **模型**：FunASR/Whisper 缓存目录由 `__init__.py` 预置（`MODELSCOPE_CACHE`/`HF_HOME`）；comprehension VLM 模型需放在 `{repo}/models/` 下（`comprehension/models.py` 的 `_MODEL_REGISTRY`）。
- **daemon**：默认端口 `127.0.0.1:47611`，作业库 `~/.urlparser/daemon/jobs.db`（SQLite WAL，重启恢复 running→failed）；`daemon prewarm` 预热 ASR 模型。
- **测试**：`pytest tests/framework -m "not integration"`（本机基线 220 passed；**数量随环境可选依赖浮动**——funasr/curl_cffi 等未装时对应测试 skip 属正常，非缺陷）；integration 标记的 P3/P4/P5 与 health_check 需要真实外网 + 浏览器。
- **测试守卫原则（2026-08 固化）**：可选依赖缺失 → 测试必须 **SKIP 绝不 FAIL**。注意 lazy export 陷阱：`import funasr` 成功不代表依赖齐备，需实际 `from funasr import AutoModel`（触发 torch/modelscope 解析）才算守卫有效（`test_funasr_punc.py` 已按此修复）。
- **运行环境**：仓库内 `.venv` 是**空壳占位**（无依赖，勿直接使用）；实际运行/测试环境为 Hermes venv（依赖齐全）。新维护者先 `pip install -e .` 或复用 Hermes venv。
- **版本**：v4.0.0 已全量同步（pyproject.toml / `__version__` / SKILL×3 / README / MCP serverInfo）。
- **隐私**：本次提交已审计——无密钥/路径/Cookie 泄露。注意 `docs/bilibili_412_bypass.md:92` 有一处历史遗留的本地绝对路径（非本次引入），建议清理。
- **SKILL**：三份 `SKILL.md`（`skills/`、`.claude/`、`.trae/`）已同步至 4.0.0 且哈希一致；Hermes 侧走 `hermes skills install tyouter/urlparser` 或直接挂 MCP。

---

## 6. 给后续维护者的三条原则（继承自设计决策）

1. **算力常驻**：任何"每请求加载/启动"的回归都是缺陷——浏览器、模型、缓存必须在 daemon 内复用（D1/D2/D6）。
2. **契约只增不改**：Schema v1 字段变更要升 `schema_version`；退出码/错误码语义不许变（D3/D4）。
3. **本地优先**：云端能力只做显式开关（唯一例外 D9：结构化抽取默认 DeepSeek）；新增任何网络出口前先过安全护栏（D9/D11/P6）。

*本交接文档基于 commit 7041163 的代码与测试状态；接手后先跑 `python -m urlparser doctor` 与 `pytest tests/framework -m "not integration"` 确认环境基线。*
