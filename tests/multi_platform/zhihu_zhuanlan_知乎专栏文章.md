# Playwright CLI 的隐藏技能：帮 Claude Code 突破反爬虫，读到「读不了」的网页 - 知乎

> Platform: zhihu_zhuanlan
> URL: https://zhuanlan.zhihu.com/p/2012158056595727644
> Strategy: bb-browser
> Method: open_and_read

## Content

# Playwright CLI 的隐藏技能：帮 Claude Code 突破反爬虫，读到「读不了」的网页 - 知乎

上篇文章讲了 Playwright CLI 怎么让 Claude Code 自己看网页、调前端。今天聊一个我意外发现的用法——**用它帮 Claude Code 读那些「死活读不了」的网页内容。**

---

## 起因：一篇今日头条的文章

事情是这样的。

我在今日头条上看到一篇技术文章，想让 Claude Code 帮我分析一下内容、提炼要点。很自然地，我把链接丢给了它。

Claude Code 的第一反应是用内置的 `WebFetch` 工具去抓取页面内容。

结果？**失败了。**

返回的内容要么是空白，要么是一堆反爬虫的验证页面 HTML，根本拿不到文章正文。

Claude Code 没有放弃，它又试了 `curl`：

```bash
curl -s "https://www.toutiao.com/article/xxxxx"
```

结果更惨——拿到的是一个需要 JavaScript 渲染的空壳页面。今日头条的文章内容是动态加载的，`curl` 只能拿到一个骨架 HTML，正文一个字都没有。

这种情况太常见了。现在的网站，尤其是国内的内容平台，反爬虫做得越来越狠：

- **今日头条**：JS 动态渲染 + Cookie 验证
- **微信公众号文章**：UA 检测 + 防盗链
- **知乎专栏**：API 加密 + 登录墙
- **各种新闻站**：Cloudflare 人机验证

对 Claude Code 来说，这些网站就像上了锁的房间——它有钥匙（HTTP 请求能力），但锁换成了指纹锁。

---

## 转折：Claude Code 自己想到了 Playwright CLI

接下来发生的事情让我很惊喜。

Claude Code 在 `WebFetch` 和 `curl` 都失败后，**自己判断出这可能是反爬虫或 JS 渲染的问题**，然后它想起了系统里装过 Playwright CLI。

于是它主动执行了：

```bash
playwright-cli open "https://www.toutiao.com/article/xxxxx"
playwright-cli snapshot
```

Playwright CLI 打开了一个真实的 Chromium 浏览器，完整加载了页面——**JavaScript 执行了，动态内容渲染了，反爬虫检测也通过了**——然后用 `snapshot` 把页面的完整文本结构抓了下来。

文章标题、正文、配图描述，全部拿到了。

**整个过程我一个字都没打。** Claude Code 自己尝试了三种方案，前两种失败后自动切换到第三种，最终成功。

![curl 只能拿到空壳 HTML，而 Playwright CLI 成功渲染出完整文章内容]



---

## 为什么 Playwright CLI 能成功？

原理很简单：

| 工具 | 实际行为 | 网站视角 |
|------|---------|---------|
| `WebFetch` / `fetch` | 发一个 HTTP 请求 | 像爬虫，拦截 |
| `curl` | 发一个 HTTP 请求 | 像爬虫，拦截 |
| Playwright CLI | 打开一个真实的 Chrome 浏览器 | 像正常用户，放行 |

Playwright CLI 用的是真实的浏览器引擎（Chromium），完整执行 JavaScript，正常加载 CSS，处理 Cookie 和重定向。对网站来说，这跟你用 Chrome 打开网页没有任何区别。

所以那些靠 JS 渲染内容、靠 Cookie 验证身份、靠 UA 检测过滤爬虫的网站，在 Playwright CLI 面前通通失效——因为它根本不是在「爬」，它是在「看」。

---

## 这个能力有什么用？

你可能会说：我自己打开网页复制粘贴不就行了？

行，但有些场景下，让 Claude Code 自己读网页比你手动复制高效得多：

### 场景一：研究一篇长文章

你看到一篇 5000 字的技术文章，想让 Claude Code 帮你：
- 提炼核心观点
- 跟你的项目做关联分析
- 翻译摘要

手动做法：打开文章 → 全选复制 → 粘贴给 Claude Code → 提需求。

现在的做法：**直接丢链接**。Claude Code 自己打开、自己读、自己分析，一步到位。

### 场景二：对比多个网页内容

你在调研一个技术方案，想对比三篇不同平台的文章观点。

手动做法：打开三个标签页 → 分别复制三篇文章 → 分三次粘贴给 Claude Code → 让它对比。

现在的做法：丢三个链接，它自己挨个读完，直接给你对比分析。

### 场景三：抓取参考资料辅助开发

你在做一个功能，Stack Overflow 上有个相关的回答，但那个页面加载了一堆广告和侧边栏，复制正文很麻烦。

直接把链接给 Claude Code，它用 Playwright CLI 打开页面，用 `snapshot` 提取干净的文本结构——**没有广告，没有侧边栏，只有你需要的内容。**

### 场景四：阅读需要滚动加载的页面

有些页面内容是懒加载的，你不滚动到底部就看不到全部内容。`curl` 和 `fetch` 只能拿到首屏。

Playwright CLI 可以执行滚动操作：

```bash
playwright-cli open "https://example.com/long-article"
playwright-cli press Page_Down
playwright-cli press Page_Down
playwright-cli snapshot # 获取滚动后的完整内容
```

---

## 最妙的是：Claude Code 会自己判断什么时候该用它

这才是我觉得最值得说的一点。

我没有告诉 Claude Code「用 Playwright CLI 去读这个网页」。我只是给了它一个链接，说「帮我看看这篇文章讲了什么」。

它的决策链路是这样的：

1. 先用最轻量的方式（`WebFetch`）尝试 → 失败
2. 换一种方式（`curl`）尝试 → 还是失败
3. 分析失败原因：可能是反爬虫或 JS 渲染问题
4. 想到 Playwright CLI 能打开真实浏览器 → 尝试 → 成功

**这就是 AI Agent 该有的样子**——不是傻傻地报错「我读不了这个网页」，而是自己想办法解决问题。

而你只需要做一件事：**事先装好 Playwright CLI。** 剩下的，Claude Code 自己会判断什么时候该用它。

---

## 安装回顾

如果你还没装，就两行命令：

```bash
npm install -g @playwright/cli@latest
playwright-cli install-browser
```

再装上 Claude Code 的 Skill：

```bash
playwright-cli install --skills
```

装完之后，Claude Code 就多了一个「超能力」——遇到读不了的网页，它会自己拿出 Playwright CLI 来解决。

---

## 小结

1. **Playwright CLI 不只是前端调试工具**，它还是 Claude Code 的「万能网页阅读器」
2. **国内主流平台（头条、知乎、公众号）的反爬虫，对 Playwright CLI 基本无效**——因为它用的是真实浏览器
3. **Claude Code 会自动选择最合适的工具**——先尝试轻量方案，失败后自动升级到 Playwright CLI
4. **你不需要记住任何命令**——只要装好工具，Claude Code 自己知道什么时候该用它

上篇文章说 Playwright CLI 给了 Claude Code 一双「眼睛」。这篇想补充一点：**这双眼睛不挑食——什么网页都能看。**

---

## 关于 Claude Code 的使用门槛

文章里提到的这些玩法，前提是你得能正常用上 Claude Code。但现实是很多人卡在第一步——Claude 账号注册困难、封号频繁，还没体验到 Playwright CLI 的能力就被挡在门外了。

如果你遇到了这个问题，可以看看 **Code2AI**（console.code2ai.codes）——一个 Claude Code 中转服务。不需要自己注册 Claude 账号，两行环境变量就能接入：

```bash
export ANTHROPIC_BASE_URL="https://code2ai.codes"
export ANTHROPIC_AUTH_TOKEN="your_token_here"
claude
```

支持 Pro / Max 多种套餐，价格比官方直订便宜不少，不用担心封号问题。

---

*标签：Claude Code、Playwright CLI、反爬虫、AI编程、网页抓取、今日头条、AI开发工具、AgentTerm*
