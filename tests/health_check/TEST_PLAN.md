# urlparser v3.3.0 综合健康度测试计划

> 生成时间: 2026-04-25
> 目标: 对 urlparser 库所有对外暴露的功能进行端到端验证，生成完整健康度报告

---

## 1. 测试 URL 选型

从 `D:\projects\claude\know how\source\cubox_export_20260309_172939.md` 中按平台抽取：

### 1.1 Bilibili (3 URLs - 视频平台)

| ID | URL | 选取理由 |
|----|-----|----------|
| BV1KBZkB6EJF | `https://www.bilibili.com/video/BV1KBZkB6EJF` | AI工具横评，中长视频 |
| BV1qNAqzxETr | `https://www.bilibili.com/video/BV1qNAqzxETr` | ObsidianCLI相关，中等长度 |
| BV19aPHzyEs5 | `https://www.bilibili.com/video/BV19aPHzyEs5` | 开源设计工具，短视频 |

### 1.2 知乎 (4 URLs - 文章/回答/专栏/想法)

| URL | 选取理由 |
|-----|----------|
| `https://www.zhihu.com/answer/2009429788666909340` | 回答页 - claude.md 写法 |
| `https://www.zhihu.com/answer/2012245758137631858` | 回答页 - 难调试的 bug |
| `https://zhuanlan.zhihu.com/p/2012158056595727644` | 专栏文章 |
| `https://www.zhihu.com/pin/2000370498543047460` | 想法（短内容） |

### 1.3 微信公众号 (3 URLs)

| URL | 选取理由 |
|-----|----------|
| `https://mp.weixin.qq.com/s/mpoOI3gAiVd9I-uuzSgxAw` | 公众号文章 |
| `https://mp.weixin.qq.com/s/ca9E87PPofjmEUVdP6EeTw` | 公众号文章 |
| `https://mp.weixin.qq.com/s/7oZuwJmGu9cswtE7tQm6Vg` | 年度报告类 |

### 1.4 小红书 (3 URLs)

| URL | 选取理由 |
|-----|----------|
| `https://www.xiaohongshu.com/login?redirectPath=%2Fexplore%2F69a90d81000000001d026a45` | 图文笔记 |
| `https://www.xiaohongshu.com/login?redirectPath=%2Fexplore%2F69a4107e000000001a025a82` | 图文笔记 |
| `https://www.xiaohongshu.com/login?redirectPath=%2Fdiscovery%2Fitem%2F691abae5000000000402247e` | 发现页 |

### 1.5 Dribbble (3 URLs - 设计平台)

| URL | 选取理由 |
|-----|----------|
| `https://dribbble.com/shots/23404996-Pitch-deck-presentation-slides` | 设计作品页 |
| `https://dribbble.com/shots/23397126-Investor-Pitch-Deck-Slides` | 设计作品页 |
| `https://dribbble.com/shots/23784886-Bento-Style-Presentation` | 设计作品页 |

### 1.6 GitHub (3 URLs - 代码仓库，补充)

| URL | 选取理由 |
|-----|----------|
| `https://github.com/anthropics/claude-code` | 仓库 README 解析 |
| `https://github.com/browser-use/browser-use` | 仓库 README 解析 |
| `https://github.com/open-webui/open-webui` | 仓库 README 解析 |

### 1.7 少数派 (1 URL)

| URL | 选取理由 |
|-----|----------|
| `https://sspai.com/post/97131` | 技术文章 |

### 1.8 通用网页 (2 URLs)

| URL | 选取理由 |
|-----|----------|
| `https://www.classicdriver.com/en/article/cars/tobias-suhlmann-follows-michael-mauer-porsches-new-head-design` | 英文汽车文章 |
| `https://ww2.mathworks.cn/videos/soa-development-for-software-defined-vehicles-1768287077070.html` | MathWorks技术视频页 |

---

## 2. 本地音视频素材

| 文件 | 时长 | 大小 | 测试片段 |
|------|------|------|----------|
| `D:\boke\garden post factory\C0257_mixed_normalized.wav` | 86.1 min | 157.7 MB | 截取 0:00-1:00 (60s) |
| `D:\boke\garden post factory\C0257_mono_video.mp4` | 86.1 min | 34.8 GB | 截取 0:00-1:00 (60s, 仅提取音频) |

提取片段使用 ffmpeg：
```bash
ffmpeg -i input -ss 0 -t 60 -vn -acodec pcm_s16le -ar 16000 -ac 1 output.wav
```

---

## 3. 测试类别与覆盖矩阵

### P0: 基础设施 (不依赖网络, 共 8 大项)

| # | 测试项 | 验证内容 | 覆盖 API |
|---|--------|----------|----------|
| 1 | 包导入 | 所有 77+ 公共符号可导入 | `__init__.__all__` |
| 2 | URL 工具 | normalize_url, detect_platform, is_video_url, hash_url, URLNormalizer | `utils.url_utils` |
| 3 | 文本工具 | clean_text, remove_duplicate_lines, extract_main_content | `utils.text_utils` |
| 4 | 文件工具 | ensure_dir, safe_filename, read/write_json, read/write_text, list_files | `utils.file_utils` |
| 5 | 媒体工具 | is_audio/video/media_file, get_media_duration, format_duration | `utils.media_utils` |
| 6 | FFmpeg 工具 | find_ffmpeg, find_ffprobe | `utils.ffmpeg_utils` |
| 7 | 数据模型 | ParseResult 构造/序列化/to_markdown, VideoMetadata, RetryAttempt, TranscriptionResult | `models` |
| 8 | 配置系统 | 默认值, ParseConfig 工厂方法, to_parser_config 转换, RetryConfig | `config` |

### P1: 存储层 (不依赖网络, 共 4 大项)

| # | 测试项 | 验证内容 |
|---|--------|----------|
| 9 | 缓存 | ResultCache set/get/has/delete/stats/clear |
| 10 | 文件存储 | ResultStorage save/save_batch/list_saved/get_stats |
| 11 | 源文档管理 | SourceDocumentManager CRUD + 索引 |
| 12 | 状态管理 | StateManager normalize/hash/check_resource_state |

### P2: 反爬与质量检测 (共 2 大项)

| # | 测试项 | 验证内容 |
|---|--------|----------|
| 13 | AntiScrapingMixin | BLOCKED_PATTERNS, detect_blocked() 各模式, validate_quality() |
| 14 | Fetcher 工厂 | 各策略实例化, FetcherFactory.auto_select 逻辑 |

### P3: 网络解析 (依赖网络 + bb-browser, 共 22 URL)

| # | 测试项 | 验证内容 |
|---|--------|----------|
| 15 | Bilibili 解析 (3) | 视频元数据, 标题/作者/播放量 |
| 16 | 知乎解析 (4) | 反爬检测 + 自动重试, 回答/专栏/想法 |
| 17 | 微信解析 (3) | 公众号文章内容提取 |
| 18 | 小红书解析 (3) | 反爬检测 + 重试 |
| 19 | Dribbble 解析 (3) | 设计页内容提取 |
| 20 | GitHub 解析 (3) | README 提取 |
| 21 | SSPAI 解析 (1) | 少数派文章 |
| 22 | 通用网页解析 (2) | 自动平台检测 |

### P4: 解析管线验证 (共 5 大项)

| # | 测试项 | 验证内容 |
|---|--------|----------|
| 23 | parse() 重试管线 | retry_attempts, final_strategy 字段填充 |
| 24 | parse() 禁用重试 | RetryConfig(enabled=False) |
| 25 | parse_batch() | 批量解析，并发控制 |
| 26 | to_markdown() 格式 | 统一 MD: 策略/时间/视频信息/转录/重试记录 |
| 27 | 缓存命中/失效 | 二次走缓存, force_refresh 绕过 |

### P5: 本地音视频转录 (共 3 大项)

| # | 测试项 | 验证内容 |
|---|--------|----------|
| 28 | WAV 转录 | FunASR 引擎, 60s 片段 |
| 29 | MP4 转录 | 从视频提取音频后转录 |
| 30 | 转录 MD 输出 | TranscriptionResult.to_markdown() 格式 |

### P6: 批量转录基础设施 (共 2 大项)

| # | 测试项 | 验证内容 |
|---|--------|----------|
| 31 | MediaScanner | 扫描目录, 文件类型识别 |
| 32 | SegmentHandler | 分段逻辑, 阈值计算 |

### P7: 输出与报告 (共 3 大项)

| # | 测试项 | 验证内容 |
|---|--------|----------|
| 33 | 解析结果持久化 | 每个平台结果保存为独立 MD |
| 34 | 转录结果持久化 | 转录 MD 保存 |
| 35 | 综合健康度报告 | 汇总所有结果 |

---

## 4. 输出目录结构

```
tests/health_check/output/
├── health_report.md          # 综合健康度报告
├── parsed/                   # 各平台解析结果 MD
│   ├── bilibili_BV1KBZkB6EJF.md
│   ├── bilibili_BV1qNAqzxETr.md
│   ├── bilibili_BV19aPHzyEs5.md
│   ├── zhihu_answer_xxx.md
│   ├── zhihu_zhuanlan_xxx.md
│   ├── zhihu_pin_xxx.md
│   ├── weixin_xxx.md
│   ├── xiaohongshu_xxx.md
│   ├── dribbble_xxx.md
│   ├── github_xxx.md
│   ├── sspai_xxx.md
│   └── generic_xxx.md
├── transcribed/              # 转录结果 MD
│   ├── local_wav_segment.md
│   └── local_mp4_segment.md
├── segments/                 # 音视频片段
│   ├── test_wav_segment.wav
│   └── test_mp4_audio_segment.wav
├── cache/                    # 缓存测试
└── storage_test/             # 存储层测试
```

---

## 5. 通过标准

| 级别 | 标准 |
|------|------|
| P0 | 所有基础设施测试 PASS (8 项) |
| P1 | 所有存储层测试 PASS (4 项) |
| P2 | 反爬检测测试 PASS (2 项) |
| P3 | 网络解析 >= 70% URL 成功获取有效内容 (>= 15/22) |
| P4 | 管线验证全部 PASS (5 项) |
| P5 | 至少 1 个转录引擎工作 |
| P6 | 批量转录基础设施 PASS (2 项) |
| P7 | 输出文件全部生成 (3 项) |

**总体健康度 >= 80% 即判定为健康。**

---

## 7. 实测结果 (2026-04-25)

| 级别 | 通过/总数 | 通过率 | 状态 |
|------|-----------|--------|------|
| P0 基础设施 | 36/36 | 100% | 全通过 |
| P1 存储层 | 15/15 | 100% | 全通过 |
| P2 反爬/Fetcher | 7/7 | 100% | 全通过 |
| P3 网络解析 | 19/22 | 86% | 3个小红书被拦截(预期) |
| P4 管线验证 | 5/5 | 100% | 全通过 |
| P5 本地转录 | 5/5 | 100% | WAV+MP4转录均成功 |
| P6 批量基础设施 | 2/2 | 100% | 全通过 |
| P7 输出验证 | 3/3 | 100% | 37个MD文件已生成 |
| **总计** | **92/95** | **96.8%** | **健康** |

3个FAIL均为小红书登录重定向页被反爬检测正确拦截，属于预期行为。

---

## 6. 执行方式

```bash
cd D:\projects\claude\urlparser
python tests/health_check/test_comprehensive.py
```

所有结果自动写入 `tests/health_check/output/` 目录。
