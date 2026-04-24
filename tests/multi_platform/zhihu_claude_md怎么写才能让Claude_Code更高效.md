# claude.md怎么写才能让Claude Code更高效？ - 知乎

> Platform: zhihu
> URL: https://www.zhihu.com/answer/2009429788666909340
> Strategy: bb-browser
> Method: open_and_read

## Content

# claude.md怎么写才能让Claude Code更高效？ - 知乎

CLAUDE.md

里面加入下面几行：

# CLAUDE.md

  ## 工作原则
  - 非微小改动先说明方法。
  - 需求有歧义、风险高或影响大时，先澄清并获批，再开始写代码。
  - Plan 只写方案、范围、风险和验收标准，不写实现代码。
  - 坚持 Spec Coding，避免 Vibe Coding。
  - 优先小步迭代；必要时使用 `/loop`。
  - 完成后可执行 `/simplify`。
  - 实现与审查分离：先完成方案或代码，再独立复核。

  ## 编码约束
  - 代码中只使用英文。
  - Spec 不依赖行号定位代码。
  - 注释说明意图、约束和边界，不记录开发过程式说明。
  - 优先用概念、模块、职责和符号名定位代码；不要只依赖易漂移的行号，必要时可补充文件路径。
  - 不为未被请求的未来需求提前抽象、泛化或暴露配置。

  ## 架构与演进
  - 优先做分层设计；不同层次保持职责分离，只通过明确、稳定的接口交互。
  - 不要让上层依赖下层实现细节，也不要建立非必要的跨层耦合；若必须依赖，应收敛为单向、最小依赖。
  - 每个层次内优先做 primitive 设计；primitive 应是独立、可替换、可组合、可验证的最小功能单元。
  - 若项目采用多 Agent 协作，应按层次设计专用 agent 与 skill，使其职责、输入、输出和边界清晰。
  - 架构演进必须逐步验证；每一步新增特性或重构，都要确认不破坏已有接口、行为和关键路径。

  ## 拆分与沉淀
  - 将任务拆成低耦合、可独立验证的子任务；必要时使用 `/batch`。
  - 重复出现且边界稳定的流程，应沉淀为 Skill、脚本或检查清单。
  - 公共规则优先沉淀为文档、测试或自动化，而不是只停留在对话里。

  ## 质量与验证
  - 项目早期只保留最小必要质量标准：可运行、可验证、可回滚。
  - 优先保证关键路径、高风险改动和外部接口可验证。
  - 修复 bug 时，先复现，再修复，再验证。
  - 任何“已完成”“已修复”“已通过”的结论，都必须附验证方式、命令或结果摘要。
  - 若当前无法验证，必须明确说明原因、风险和未覆盖范围。

  ## 协作与纠错
  - 被纠正时，先验证问题，再调整做法。
  - 外部建议先核对是否适用于当前代码库，再决定是否采纳。
  - 对重复性问题，沉淀为明确规则、测试或自动检查。

  ## Codex 协作
  - Codex 是补充能力，不是默认执行者；当前 Agent 负责主线推进、需求澄清、关键决策、首轮实现和最终验收。
  - 仅在以下场景使用 Codex：独立只读代码评审、adversarial review、边界清晰且可并行的子任务、或长耗时调查与后台续跑；委派
  前必须先定义目标、约束、验收标准和边界。
  - 不要把需求澄清、方案收敛、架构取舍、小而集中的直接实现或需要持续用户交互的主线任务交给 Codex；Codex 的结果必须由当前
  Agent 整合并复核。

  ## Agent-Native 文档系统
  - 若仓库采用 Agent-Native 文档系统，使用两层结构，避免重复：
    - canonical skill docs：保存详细、长期维护的正式正文，供人类和 Agent 共读。
    - agent-facing index（如 `.claude/skills/`）：只负责把 Agent 路由到正确正文，不复述内容，也不要求与每份正文一一对
  应。
  - 文档应同时对人类和 Agent 可读：写清能力、前提、边界、依赖、接口和典型用法，避免只对单一读者成立的隐式上下文。
  - 仅 skill 文档必须包含 frontmatter：
    - `type`
    - `tags`
    - `requires`（仅写硬依赖）
  - Agent 读取文档时，应先通过索引定位主题，再进入正文；仅递归读取 `requires` 指向的硬依赖文档，其他相邻或参考文档按需读
  取，避免无界展开上下文。
  - 本地文档是当前仓库契约；外部资料、外部 skills 或示例实现只作参考，不覆盖本地约定。
  - 文档优先写能力、前提、边界和集成方式；量化结论必须带测试条件和适用范围。

  ## 禁止事项
  - 永远不要使用 `/init`，除非项目明确要求。
  - `CLAUDE.md` 必须按项目实际需求编写，不套用空泛模板。
  - 不要在代码注释、commit message 或 PR body 中使用描述开发进度的词，如 `FIXED`、`Step`、`Week`、`Section`、`Phase`、
  `AC-x`。
  - 不要在代码注释、commit message 或 PR body 中出现 AI 工具名称，如 Codex、Claude、Grok、Gemini 等。
  - 不要把外部实现细节、外部文档或外部技能树直接提升为当前项目的硬约束。

andrej-karpathy-skills

核心规则：

先说清假设和歧义，不静默猜测
优先最简单方案，不做额外设计
只做必要的、外科手术式改动
先定义可验证的成功标准，再实现和验证
# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.





codex 避免黑话
请始终遵守以下回复协议。
注意你是一位文学大师，写作风格是《人月神话》，同时禁止继续给出新问题，或者要求展开内容。仅仅写下必要的回复。

1. 语言与段落结构
- 每一个输出段落都是有效信息的中文段落。
- 中文段落必须在含义、信息范围和顺序上准确。
- 单个段落内禁止中英文混写。
- 全文都必须保持这种成对段落结构。

2. 数学公式规范
- 所有数学公式与符号表达统一使用 LaTeX。
- 如果回复本身不涉及公式，不要人为加入无必要的公式。

3. 讲解风格
- 讲解必须深入、准确、技术上清晰。
- 使用专业但易懂的术语。
- 段落长度保持中等，每段内容要充分展开，但避免过度压缩或无效拉长。
- 重点放在概念精确性、逻辑结构和显式推理上。

4. 禁止的修辞风格
- 禁止使用比喻。
- 禁止使用类比。
- 禁止使用举例式说明。
- 禁止使用回避性、过度情绪化或表演化措辞。

5. 禁用表达
- 不得使用用户定义的任何禁用表达。
- 该限制适用于整条回复，包括正文、总结、过渡句和改写内容。

6. 输出质量
- 保持论述严谨、可读、结构清楚。
- 优先输出完整的分析性段落，而不是零散笔记。
- 在讨论约束或改写文本时，以清晰度、确定性和指令稳定性为优先目标。

避开：
切，伤，砍一刀，补一刀，更狠，狠一点，狠狠干，打坏，拍板，拍脑门，好，行，我先，说穿，不踩坑，简单的说，不是 而是，我先 再，一句话总结，痛点，根因，抠出来，揪出来，我不猜，不靠猜，不瞎猜，兜底，落盘，闭环，说穿，能吃，这轮，口径，拆开，说人话就是，补，接，核，进，顺，落，坏，跑，更硬，硬写，稳稳接住，压实，更稳，最稳，不稳，收口，收敛，收束，锁住，夹具，顺手，我先，如果你要，要不要我，我已确认，我立马开始，如果你愿意，只要你回复我，你就确认一点
这些词或者句子。




另外，codex 用 superpowers插件， claude用humanize 插件.

superpowers

https://github.com/obra/superpowers

Superpowers 是一套完整的软件开发流程，基于一套可组合的“skills”和一些初步指令，确保你的代理能使用这些技能。

核心是plan开始的时候很多细节做一些自主决策, tradeoff比较多

humanize

https://github.com/humania-org/humanize

Humanize 不期待一次性产出完美，而是利用迭代反馈循环：

Claude 会执行你的计划
Codex 独立审查进展
问题被及早发现并加以解决
工作将持续进行，直到所有验收标准都满足

注意点：plan大型项目通常5-10页A4，一般2w字符左右；rlcr如果超过20轮没有build结束， 就需要考虑是不是plan写得不好

下面有一个示例：rlcr+蜂群用四个小时完成了gem5这个巨型仓库的构建系统从scons到cmake的彻底替换

一个大致的判断是，5k-10k行的代码改动，一个普通的rlcr就够了。10-30k，考虑上蜂群+rlcr。带batch的rlcr，我自己其实都没有用过，任务要足够大，大概一次性要改三万行以上才会需要用batch

humanize最佳开发模式:

- 白天双开, 一个项目开两个窗口, 同时改一个路径下面的项目.

- 单步前进, 每次只让AI做一个可验证的小步骤, 走claude code原生的plan mode.

- 每个路径, 一个窗口做plan, 一个窗口做实现.

- 这样并不会出现做出来的plan到实现的时候失效的问题, 因为避免了用行号锚定修改范围之后, 其实鲁棒性很高.

- 但是上述双开的模式, 并不能把人的时间全部占满, 所以需要再开一个docs, 写spec

- plan - code - spec, 这三个窗口轮流切换, 刚刚好把人类(我的时间全部沾满)

- 下班的时候: 用spec起humanize, 睡觉




另外附上插本地api用量的repo https://github.com/SihaoLiu/ai-usage

Skills
GPT的注意事项

GPT-5.4超过272k之后性能急剧下降，并且收费double，记得修改~/.codex/config.toml设置model_context_window = 272000

Claude的注意事项
auto compact如果开启，claude会预留12.5%的空间作为压缩上下文的buffer， 如果当前轮次的对话超过该buffer， 那么claude会 context fail. [ 切换到1M model compact ，再切换回来continue. ]

2. 如果嫌申请权限麻烦，使用 su - && cd / && claude --dangerously-skip-permissions 一键解决，不过仅限sandbox

3. 如果claude没有及时更新，并且使用了旧模型，anthropic可能是拉了一个严重降智的模型在兜底

4. claude 拥有极强的逆向和汇编能力，但是默认的道德约束会拒绝执行，通过一些提示词能够绕过防护

SWE Driven 开发

参考SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering

这里将写代码的流程从以人类为中心重新设计为以智能体为中心，实验流程如下：

SWE-bench ， 来自开源库的issue, 给定一个 Issue 描述，Agent 被扔进代码仓库，需要自己定位 Bug、修改代码。

验证， 不看生成的代码像不像，只看最终能不能通过开发者当年写的真实单元测试。

SWEbench的标准prompt
系统前缀说明
<issue>

<issue>
<code>

<code>
<patch示例>

<patch示例>
请生成patch来修复问题

这里我也在探索的流程中。

spec和plan的区别

spec 是对代码架构的理解；

plan是驱动工具从无到有生成代码的指令；

spec 是 写什么, 怎么写, 设计是啥；

plan 是 按照什么顺序写, 写到XX阶段要做什么测试, 测试达到XX程度才能继续写；

终点是spec描述的状态， plan是驱动到达终点的动力；

Vibe coding的本质是自然语言到编程语言的投影工具。




如何证明plan是有效的

在AI写代码之前，仔细阅读plan, 如果你读完能够得到一个感觉：这plan我随便找个本科生给我干一个月肯定能做完， 那么就可以了。

通常一个plan会附带5个spec, spec 的设计类似SIMT的思想，先让AI将所有可能性都进行尝试，最后在CLI Test部分筛去有问题的方案，而不是边实现边进行测试。

build exploration tool， not building tool while exploring

这里推荐一个值得学习的spec format https://github.com/PolyArch/loom/tree/main/docs




如何测试claude是否弱智
