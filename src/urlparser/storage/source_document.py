"""
源文档管理

保存和检索 MD 格式的源文档
"""

import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List


class SourceDocumentManager:
    """管理 MD 格式源文档的保存和检索"""

    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)
        self.sources_dir = self.base_dir / "sources"
        self.sources_dir.mkdir(parents=True, exist_ok=True)

        self.articles_dir = self.sources_dir / "articles"
        self.videos_dir = self.sources_dir / "videos"
        self.papers_dir = self.sources_dir / "papers"
        self.webpages_dir = self.sources_dir / "webpages"

        for dir_path in [self.articles_dir, self.videos_dir, self.papers_dir, self.webpages_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        self.index_file = self.sources_dir / "index.json"
        self._index = self._load_index()

    def _load_index(self) -> Dict:
        if self.index_file.exists():
            try:
                content = self.index_file.read_text(encoding='utf-8')
                if content.strip():
                    return json.loads(content)
            except Exception:
                pass
        return {}

    def _save_index(self) -> None:
        try:
            self.index_file.write_text(
                json.dumps(self._index, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
        except Exception:
            pass

    def _get_content_dir(self, content_type: str) -> Path:
        type_map = {
            'article': self.articles_dir,
            'video': self.videos_dir,
            'paper': self.papers_dir,
            'webpage': self.webpages_dir,
            'articles': self.articles_dir,
            'videos': self.videos_dir,
            'papers': self.papers_dir,
            'webpages': self.webpages_dir
        }
        return type_map.get(content_type.lower(), self.webpages_dir)

    def _generate_filename(self, url: str, title: str = None) -> str:
        url_hash = hashlib.md5(url.encode()).hexdigest()

        if title:
            safe_title = "".join(
                c for c in title[:80]
                if c.isalnum() or c in (' ', '-', '_', '.')
            ).strip()
            safe_title = ' '.join(safe_title.split())
            if safe_title:
                return f"{url_hash[:8]}_{safe_title}.md"

        return f"{url_hash[:8]}.md"

    def update_index(self, url: str, file_path: str, content_type: str,
                    metadata: Dict = None) -> None:
        if url not in self._index:
            self._index[url] = {}

        self._index[url].update({
            'source_path': file_path,
            'content_type': content_type,
            'saved_at': datetime.now().isoformat()
        })

        if metadata:
            self._index[url]['metadata'] = metadata

        self._save_index()

    def get_from_index(self, url: str) -> Optional[Dict]:
        return self._index.get(url)

    def save_source_document(self, url: str, content: str, content_type: str,
                           metadata: Dict = None, title: str = None) -> str:
        target_dir = self._get_content_dir(content_type)
        filename = self._generate_filename(url, title)
        file_path = target_dir / filename

        try:
            file_path.write_text(content, encoding='utf-8')
            self.update_index(url, str(file_path), content_type, metadata)
            return str(file_path)
        except Exception as e:
            print(f"[ERROR] Failed to save source document: {e}")
            raise

    def get_source_document(self, url: str) -> Optional[str]:
        index_info = self.get_from_index(url)
        if not index_info or 'source_path' not in index_info:
            return None

        file_path = Path(index_info['source_path'])
        if not file_path.exists():
            return None

        try:
            return file_path.read_text(encoding='utf-8')
        except Exception:
            return None

    def generate_video_md(self, metadata: Dict, subtitles: List[Dict] = None,
                       raw_content: str = None, transcription: str = None) -> str:
        md = []

        title = metadata.get('title', 'Untitled Video')
        md.append(f"# {title}\n")

        md.append("## 视频信息\n\n")
        if metadata.get('author'):
            md.append(f"- **作者**: {metadata['author']}")
        if metadata.get('publish_date'):
            md.append(f"- **发布日期**: {metadata['publish_date']}")
        if metadata.get('duration'):
            md.append(f"- **时长**: {metadata['duration']}")
        if metadata.get('views'):
            md.append(f"- **观看数**: {metadata['views']}")
        if metadata.get('likes'):
            md.append(f"- **点赞数**: {metadata['likes']}")
        if metadata.get('coins'):
            md.append(f"- **投币数**: {metadata['coins']}")
        if metadata.get('favorites'):
            md.append(f"- **收藏数**: {metadata['favorites']}")

        tags = metadata.get('tags', '')
        if tags:
            if isinstance(tags, str):
                tags_list = [t.strip() for t in tags.split('\n') if t.strip()]
            else:
                tags_list = tags
            if tags_list:
                md.append(f"- **标签**: {', '.join(tags_list)}")

        md.append("")

        description = metadata.get('description', '')
        if description:
            md.append("## 简介\n\n")
            md.append(f"{description}\n")

        if subtitles and len(subtitles) > 0:
            md.append("## 字幕（平台提供）\n\n")
            for sub in subtitles:
                start = sub.get('start', 0)
                text = sub.get('text', '').strip()
                if text:
                    time_str = self._format_timestamp(start)
                    md.append(f"**[{time_str}]** {text}\n")
            md.append("")

        if transcription and len(transcription) > 0:
            md.append("## 语音转录\n\n")
            md.append(f"{transcription}\n")
            md.append("")
        elif raw_content:
            md.append("## 内容\n\n")
            md.append(f"{raw_content}\n")

        return "\n".join(md)

    def generate_article_md(self, content: Dict, raw_text: str = None) -> str:
        md = []

        title = content.get('title', 'Untitled Article')
        md.append(f"# {title}\n")

        md.append("## 文章信息\n\n")
        if content.get('author'):
            md.append(f"- **作者**: {content['author']}")
        if content.get('publish_date'):
            md.append(f"- **发布日期**: {content['publish_date']}")
        if content.get('platform'):
            md.append(f"- **平台**: {content['platform']}")

        md.append("")

        description = content.get('description', '')
        if description and len(description) > 50:
            md.append("## 摘要\n\n")
            md.append(f"{description}\n")

        md.append("## 内容\n\n")

        if raw_text:
            md.append(f"{raw_text}\n")
        elif content.get('content'):
            md.append(f"{content['content']}\n")

        return "\n".join(md)

    def _format_timestamp(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def list_sources(self, content_type: str = None) -> List[Dict]:
        results = []

        for url, info in self._index.items():
            if content_type and info.get('content_type', '').lower() != content_type.lower():
                continue

            file_path = Path(info.get('source_path', ''))
            exists = file_path.exists() if file_path else False

            results.append({
                'url': url,
                'path': info.get('source_path'),
                'content_type': info.get('content_type'),
                'saved_at': info.get('saved_at'),
                'exists': exists,
                'metadata': info.get('metadata', {})
            })

        return results

    def delete_source(self, url: str) -> bool:
        index_info = self.get_from_index(url)
        if not index_info or 'source_path' not in index_info:
            return False

        file_path = Path(index_info['source_path'])
        if file_path.exists():
            file_path.unlink()

        del self._index[url]
        self._save_index()
        return True

    def get_stats(self) -> Dict:
        stats = {
            'total': len(self._index),
            'by_type': {},
            'storage_size': 0,
            'exists_count': 0
        }

        for url, info in self._index.items():
            content_type = info.get('content_type', 'unknown')
            stats['by_type'][content_type] = stats['by_type'].get(content_type, 0) + 1

            file_path = Path(info.get('source_path', ''))
            if file_path.exists():
                stats['exists_count'] += 1
                stats['storage_size'] += file_path.stat().st_size

        return stats


_manager_instance: Optional[SourceDocumentManager] = None


def get_source_manager(base_dir: str = "data") -> SourceDocumentManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = SourceDocumentManager(base_dir)
    return _manager_instance