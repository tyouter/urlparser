"""
AI 浏览器自动化读取器

使用 browser-use 库进行 AI 驱动的浏览器自动化
"""

import os
from typing import Optional, Dict
from urllib.parse import urlparse

from .base import BaseFetcher, FetchResult, FetchConfig, FetchStrategy


class BrowserUseFetcher(BaseFetcher):
    """
    AI 浏览器自动化读取器

    使用 DeepSeek 驱动的浏览器自动化，处理复杂页面交互场景

    特性:
    - AI 驱动的浏览器操作
    - 自动处理登录验证
    - 支持用户 Chrome 状态
    - 适合 Playwright 无法处理的场景

    依赖:
    - pip install browser-use
    - 需要设置 DEEPSEEK_API_KEY 环境变量
    """

    strategy = FetchStrategy.BROWSER_USE

    def __init__(self, config: Optional[FetchConfig] = None):
        super().__init__(config)
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            api_key = os.environ.get('DEEPSEEK_API_KEY')
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY environment variable not set")

            from browser_use.llm.litellm import ChatLiteLLM
            self._llm = ChatLiteLLM(
                model='deepseek/deepseek-chat',
                api_key=api_key,
                api_base='https://api.deepseek.com/v1'
            )
        return self._llm

    def _build_task(self, url: str, platform: str) -> str:
        base_task = f"打开网页 {url} 并提取主要内容。"

        platform_instructions = {
            'zhihu': "1. 等待页面完全加载 2. 提取文章标题 3. 提取作者名称 4. 提取文章正文内容（排除广告、推荐、评论） 5. 如果需要登录才能查看，请说明 返回格式：标题|作者|正文内容",
            'weixin': "1. 等待页面加载完成 2. 提取文章标题 3. 提取公众号名称 4. 提取文章正文内容 5. 提取发布时间 返回格式：标题|作者|发布时间|正文内容",
            'bilibili': "1. 等待视频页面加载 2. 提取视频标题 3. 提取UP主名称 4. 提取视频简介/描述 5. 提取播放量、点赞数等信息 返回格式：标题|UP主|简介|播放数据",
            'default': "1. 等待页面加载完成 2. 提取页面标题 3. 提取主要正文内容（排除导航、广告、侧边栏、评论） 4. 如果是文章，提取作者和发布时间 返回格式：标题|作者|正文内容",
        }

        instruction = platform_instructions.get(platform, platform_instructions['default'])
        return base_task + "\n" + instruction

    def _parse_result(self, result, url: str) -> FetchResult:
        try:
            if hasattr(result, 'final_result'):
                text = str(result.final_result)
            elif hasattr(result, 'content'):
                text = str(result.content)
            else:
                text = str(result)

            title = ''
            content = text

            parts = text.split('|')
            if len(parts) >= 1:
                title = parts[0].strip()
            if len(parts) >= 3:
                content = '|'.join(parts[2:]).strip()

            return FetchResult(
                url=url,
                text=content,
                title=title,
                strategy=self.strategy,
                success=True,
                metadata={'raw_text': text}
            )
        except Exception as e:
            return FetchResult(
                url=url,
                strategy=self.strategy,
                success=False,
                error=f"Parse result failed: {e}"
            )

    async def fetch(self, url: str, **kwargs) -> FetchResult:
        platform = kwargs.get('platform', 'default')

        try:
            from browser_use import Agent, Browser

            task = self._build_task(url, platform)

            if self.config.user_data_dir:
                browser = Browser.from_system_chrome(self.config.user_data_dir)
            else:
                browser = Browser()

            agent = Agent(
                task=task,
                llm=self._get_llm(),
                browser=browser
            )

            result = await agent.run()
            await browser.close()

            return self._parse_result(result, url)

        except ImportError as e:
            return FetchResult(
                url=url,
                strategy=self.strategy,
                success=False,
                error=f"browser-use not installed: {e}"
            )
        except Exception as e:
            return FetchResult(
                url=url,
                strategy=self.strategy,
                success=False,
                error=str(e)
            )