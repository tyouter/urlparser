"""
在线视频信息提取器

直接调用 LLM API 获取视频元数据，无需 yt-dlp 或浏览器。
"""

import os
import asyncio
from typing import Dict, Optional
from urllib.parse import urlparse


class OnlineVideoFetcher:
    """通过 LLM API 在线获取视频信息"""

    DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL = "qwen3.6-plus"

    SYSTEM_PROMPT = """你是一个视频信息提取助手。给定一个视频 URL，请提取视频的元数据信息并以 JSON 格式返回。

返回格式必须严格遵循以下 JSON schema（所有字段都是必需的）：
{
  "title": "视频标题",
  "author": "作者/UP主名称",
  "description": "视频描述/简介",
  "duration": "时长，格式为 MM:SS",
  "views": "播放量（带单位，如 '1.2万'）",
  "likes": "点赞数（带单位）",
  "favorites": "收藏数（带单位）",
  "publish_date": "发布日期，格式 YYYY-MM-DD",
  "tags": "标签，用逗号分隔",
  "platform": "平台名称（如 bilibili, youtube 等）",
  "subtitles": "是否有字幕（true/false）"
}

如果无法获取某些字段，用空字符串 "" 填充。
只返回 JSON，不要包含任何其他文字。"""

    def __init__(self):
        self.api_key = os.environ.get("QWEN_API_KEY", "")
        if not self.api_key:
            raise ValueError("QWEN_API_KEY 环境变量未设置")

    async def fetch(self, url: str) -> Dict:
        """
        调用 LLM API 获取视频信息

        Args:
            url: 视频 URL

        Returns:
            与 YtdlpExtractor.extract() 相同格式的 dict
        """
        try:
            result = await self._call_llm(url)
            return self._format_result(url, result)
        except Exception as e:
            return {
                'url': url,
                'platform': self._detect_platform(url),
                'fetch_success': False,
                'error': str(e),
                'title': '',
                'description': '',
                'raw_text': ''
            }

    async def _call_llm(self, url: str) -> Dict:
        """调用 LLM API"""
        user_prompt = f"请提取以下视频的元数据信息：{url}"

        # 尝试使用 openai SDK
        try:
            return await self._call_with_openai_sdk(user_prompt)
        except ImportError:
            pass

        # 降级到 httpx
        return await self._call_with_httpx(user_prompt)

    async def _call_with_openai_sdk(self, prompt: str) -> Dict:
        """使用 OpenAI SDK 调用"""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.DASHSCOPE_BASE_URL,
        )

        response = await client.chat.completions.create(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()
        import json

        # 清理可能的 markdown 代码块
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:].strip()

        return json.loads(content)

    async def _call_with_httpx(self, prompt: str) -> Dict:
        """使用 httpx 调用 API（SDK 不可用时）"""
        import httpx
        import json

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.MODEL,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.DASHSCOPE_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"].strip()
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:].strip()

        return json.loads(content)

    def _format_result(self, url: str, llm_result: Dict) -> Dict:
        """将 LLM 结果格式化为与 YtdlpExtractor 兼容的格式"""
        platform = llm_result.get("platform", self._detect_platform(url))

        # 格式化时长
        duration = llm_result.get("duration", "")

        # 构建原始文本
        parts = []
        if llm_result.get("title"):
            parts.append(llm_result["title"])
        if llm_result.get("description"):
            parts.append(llm_result["description"])
        if llm_result.get("tags"):
            parts.append(f"Tags: {llm_result['tags']}")

        return {
            'url': url,
            'platform': platform,
            'fetch_success': True,
            'source': 'llm_online',
            'title': llm_result.get("title", ""),
            'description': llm_result.get("description", ""),
            'author': llm_result.get("author", ""),
            'publish_date': llm_result.get("publish_date", ""),
            'publish_date_formatted': llm_result.get("publish_date", ""),
            'duration': duration,
            'views': llm_result.get("views", ""),
            'likes': llm_result.get("likes", ""),
            'coins': "",
            'favorites': llm_result.get("favorites", ""),
            'tags': llm_result.get("tags", ""),
            'subtitles': [],
            'raw_text': '\n\n'.join(parts),
        }

    def _detect_platform(self, url: str) -> str:
        """检测视频平台"""
        domain = urlparse(url).netloc.lower()

        platform_map = {
            'youtube.com': 'youtube',
            'youtu.be': 'youtube',
            'bilibili.com': 'bilibili',
            'b23.tv': 'bilibili',
            'douyin.com': 'douyin',
            'kuaishou.com': 'kuaishou',
            'vimeo.com': 'vimeo',
            'dailymotion.com': 'dailymotion',
            'twitch.tv': 'twitch',
        }

        for platform_domain, platform_name in platform_map.items():
            if platform_domain in domain:
                return platform_name

        return 'unknown'


async def fetch_video_online(url: str) -> dict:
    """
    在线获取视频信息的便捷函数

    Args:
        url: 视频 URL

    Returns:
        与 YtdlpExtractor.extract() 兼容的 dict
    """
    fetcher = OnlineVideoFetcher()
    return await fetcher.fetch(url)
