"""
内容清理 Mixin
"""

import re


class ContentCleanMixin:

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""

        text = re.sub(r'[\xa0\u200b\u200c\u200d\ufeff]+', ' ', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'^\s+|\s+$', '', text, flags=re.MULTILINE)

        return text.strip()

    @staticmethod
    def extract_main_content(html: str, selectors: list) -> str:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            for selector in selectors:
                element = soup.select_one(selector)
                if element:
                    return element.get_text(separator='\n', strip=True)

            return soup.get_text(separator='\n', strip=True)

        except ImportError:
            text = re.sub(r'<[^>]+>', ' ', html)
            return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def truncate_text(text: str, max_length: int = 10000, suffix='...') -> str:
        if len(text) <= max_length:
            return text
        return text[:max_length] + suffix

    @staticmethod
    def remove_duplicate_lines(text: str) -> str:
        lines = text.split('\n')
        seen = set()
        result = []

        for line in lines:
            stripped = line.strip()
            if stripped and stripped not in seen:
                seen.add(stripped)
                result.append(line)
            elif not stripped:
                result.append(line)

        return '\n'.join(result)

    @staticmethod
    def clean_weixin_text(text: str) -> str:
        if not text:
            return ""

        _WEIXIN_NOISE_PATTERNS = [
            r'预览时标签不可点',
            r'^关闭$',
            r'^更多$',
            r'^名称已清空$',
            r'微信扫一扫赞赏作者',
            r'赞赏后展示我的头像',
            r'^作品$',
            r'^暂无作品$',
            r'喜欢作者',
            r'^其它金额$',
            r'^¥$',
            r'^最低赞赏 ¥\d+$',
            r'^确定$',
            r'^返回$',
            r'^赞赏金额$',
            r'^\d$',
            r'^留言$',
            r'^暂无留言$',
            r'^\d+条留言$',
            r'^发消息$',
            r'^写留言:?$',
            r'继续滑动看下一个',
            r'轻触阅读原文',
            r'^继续访问$',
            r'^取消$',
            r'^允许$',
            r'^知道了$',
            r'^×$',
            r'微信扫一扫可打开此内容',
            r'使用完整服务',
            r'^分析$',
            r'^赞$',
            r'^分享$',
            r'^在小说阅读器读本章$',
            r'^去阅读$',
            r'在小说阅读器中沉浸阅读',
            r'^调整当前正文文字大小$',
            r'^\d+%$',
            r'^留言$',
            r'^写留言$',
            r'微信公众平台广告规范指引',
            r'微信扫一扫关注该公众号',
            r'微信扫一扫',
            r'^向上滑动看下一个$',
        ]

        text = ContentCleanMixin.clean_text(text)

        text = re.sub(r'\[([^\]]*)\]\(javascript[^)]*\)', r'\1', text)
        text = re.sub(r'\[([^\]]*)\]\(javacript[^)]*\)', r'\1', text)

        text = re.sub(r'^\s*使用小程序\s*$', '', text, flags=re.MULTILINE)

        lines = text.split('\n')
        cleaned = []
        for line in lines:
            stripped = line.strip()
            skip = False
            for pattern in _WEIXIN_NOISE_PATTERNS:
                if re.match(pattern, stripped):
                    skip = True
                    break
            if not skip:
                cleaned.append(line)

        text = '\n'.join(cleaned)
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()