"""
平台适配器
"""

from .zhihu import ZhihuParser
from .xiaohongshu import XiaohongshuParser
from .bilibili import BilibiliParser
from .youtube import YoutubeParser
from .weixin import WeixinParser
from .github import GithubParser
from .generic import GenericParser
from .wenzhen import WenzhenParser

__all__ = [
    'ZhihuParser',
    'XiaohongshuParser',
    'BilibiliParser',
    'YoutubeParser',
    'WeixinParser',
    'GithubParser',
    'GenericParser',
    'WenzhenParser',
]