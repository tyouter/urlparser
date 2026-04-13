"""
存储层

提供缓存、文件输出、源文档管理、状态管理能力
"""

from .cache import ResultCache, CacheEntry
from .file_storage import ResultStorage
from .source_document import SourceDocumentManager
from .state import StateManager, ProcessStatus, ResourceState

__all__ = [
    'ResultCache',
    'CacheEntry',
    'ResultStorage',
    'SourceDocumentManager',
    'StateManager',
    'ProcessStatus',
    'ResourceState',
]