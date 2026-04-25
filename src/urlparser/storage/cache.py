"""
解析结果缓存

双层缓存：内存（快速） + 磁盘（持久）
"""

import json
import hashlib
import logging
import time
from pathlib import Path
from typing import Optional, Dict, List, Any, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    url: str
    result_dict: Dict
    cached_at: float
    expires_at: Optional[float] = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def age_seconds(self) -> float:
        return time.time() - self.cached_at


class ResultCache:
    """
    解析结果缓存

    特性:
    - 双层缓存：内存（快速） + 磁盘（持久）
    - URL 哈希作为 key，避免特殊字符问题
    - 可设置过期时间
    - 自动清理过期条目
    """

    def __init__(
        self,
        cache_dir: Optional[Union[str, Path]] = None,
        ttl_hours: float = 24.0,
        max_memory_size: int = 100,
    ):
        self.ttl_seconds = ttl_hours * 3600 if ttl_hours > 0 else None
        self.max_memory_size = max_memory_size

        self._memory_cache: Dict[str, CacheEntry] = {}

        if cache_dir:
            self.cache_dir = Path(cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._disk_enabled = True
        else:
            self.cache_dir = None
            self._disk_enabled = False

    @staticmethod
    def _hash_url(url: str) -> str:
        return hashlib.md5(url.encode('utf-8')).hexdigest()[:16]

    async def get(self, url: str) -> Optional[Dict]:
        key = self._hash_url(url)

        entry = self._memory_cache.get(key)
        if entry and not entry.is_expired:
            return entry.result_dict

        if self._disk_enabled:
            entry = await self._load_from_disk(key)
            if entry and not entry.is_expired:
                self._memory_cache[key] = entry
                return entry.result_dict

        return None

    async def set(self, result_dict: Dict, url: Optional[str] = None, ttl_hours: Optional[float] = None) -> bool:
        target_url = url or result_dict.get('url', '')
        if not target_url:
            return False

        key = self._hash_url(target_url)

        ttl = (ttl_hours * 3600) if ttl_hours else self.ttl_seconds
        now = time.time()

        entry = CacheEntry(
            url=target_url,
            result_dict=result_dict,
            cached_at=now,
            expires_at=(now + ttl) if ttl else None,
        )

        self._memory_cache[key] = entry
        self._evict_if_needed()

        if self._disk_enabled:
            await self._save_to_disk(key, entry)

        return True

    async def has(self, url: str) -> bool:
        return await self.get(url) is not None

    async def delete(self, url: str) -> bool:
        key = self._hash_url(url)

        if key in self._memory_cache:
            del self._memory_cache[key]

        if self._disk_enabled:
            cache_file = self.cache_dir / f"{key}.json"
            if cache_file.exists():
                cache_file.unlink()

        return True

    async def clear(self, include_disk: bool = True):
        self._memory_cache.clear()

        if self._disk_enabled and include_disk:
            for f in self.cache_dir.glob("*.json"):
                f.unlink()

    async def stats(self) -> Dict[str, Any]:
        disk_count = 0
        disk_size = 0

        if self._disk_enabled:
            for f in self.cache_dir.glob("*.json"):
                disk_count += 1
                disk_size += f.stat().st_size

        return {
            'memory_count': len(self._memory_cache),
            'disk_count': disk_count,
            'disk_size_mb': round(disk_size / (1024 * 1024), 2),
            'ttl_hours': (self.ttl_seconds or 0) / 3600,
            'cache_dir': str(self.cache_dir) if self.cache_dir else None,
        }

    def _evict_if_needed(self):
        while len(self._memory_cache) > self.max_memory_size:
            oldest_key = min(
                self._memory_cache.keys(),
                key=lambda k: self._memory_cache[k].cached_at
            )
            del self._memory_cache[oldest_key]

    async def _save_to_disk(self, key: str, entry: CacheEntry):
        try:
            cache_file = self.cache_dir / f"{key}.json"
            data = {
                'url': entry.url,
                'result': entry.result_dict,
                'cached_at': entry.cached_at,
                'expires_at': entry.expires_at,
            }
            cache_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        except Exception as e:
            logger.warning("Cache save failed: %s", e)

    async def _load_from_disk(self, key: str) -> Optional[CacheEntry]:
        try:
            cache_file = self.cache_dir / f"{key}.json"

            if not cache_file.exists():
                return None

            data = json.loads(cache_file.read_text(encoding='utf-8'))

            return CacheEntry(
                url=data['url'],
                result_dict=data['result'],
                cached_at=data['cached_at'],
                expires_at=data.get('expires_at'),
            )
        except Exception:
            return None