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