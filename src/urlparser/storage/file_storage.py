"""
结果文件存储

Markdown / JSON 格式输出
"""

import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Any, Union
from datetime import datetime


class ResultStorage:
    """
    结果持久化到文件系统

    支持:
    - Markdown 格式（默认）
    - JSON 格式
    - 自动创建目录结构
    - 按平台/类型分类存储
    """

    def __init__(
        self,
        output_dir: Union[str, Path] = "./parsed_results",
        default_format: str = "markdown",
        group_by: str = "platform",
        filename_template: Optional[str] = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.default_format = default_format.lower()
        self.group_by = group_by.lower()

        self.filename_template = filename_template or "{url_hash}_{platform}_{timestamp}"

    def save(
        self,
        result_dict: Dict,
        format: Optional[str] = None,
        subfolder: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Path:
        fmt = (format or self.default_format).lower()

        target_dir = self._get_target_dir(result_dict, subfolder)
        target_dir.mkdir(parents=True, exist_ok=True)

        file_name = filename or self._generate_filename(result_dict)

        if fmt == "json":
            file_path = target_dir / f"{file_name}.json"
            content = json.dumps(result_dict, ensure_ascii=False, indent=2)
        else:
            file_path = target_dir / f"{file_name}.md"
            content = self._dict_to_markdown(result_dict)

        file_path.write_text(content, encoding='utf-8')

        return file_path

    def save_batch(
        self,
        results: List[Dict],
        format: Optional[str] = None,
    ) -> Dict[str, Path]:
        paths = {}

        for result in results:
            if result.get('fetch_success'):
                try:
                    url = result.get('url', '')
                    path = self.save(result, format=format)
                    paths[url] = path
                except Exception as e:
                    print(f"[ERROR] Save failed for {result.get('url', '')}: {e}")

        return paths

    def list_saved(
        self,
        platform: Optional[str] = None,
    ) -> List[Dict]:
        files = []

        pattern = "*.md" if self.default_format == "markdown" else "*.json"

        for file_path in self.output_dir.rglob(pattern):
            try:
                info = {
                    'path': str(file_path),
                    'relative': str(file_path.relative_to(self.output_dir)),
                    'size_kb': round(file_path.stat().st_size / 1024, 1),
                    'modified': datetime.fromtimestamp(
                        file_path.stat().st_mtime
                    ).isoformat(),
                }

                if file_path.suffix == '.json':
                    data = json.loads(file_path.read_text(encoding='utf-8'))
                    info['url'] = data.get('url', '')
                    info['platform'] = data.get('platform', '')
                    info['title'] = data.get('title', '')

                files.append(info)

            except Exception:
                files.append({
                    'path': str(file_path),
                    'relative': str(file_path.relative_to(self.output_dir)),
                    'error': '读取失败',
                })

        if platform:
            files = [f for f in files if f.get('platform') == platform]

        return sorted(files, key=lambda x: x.get('modified', ''), reverse=True)

    def get_stats(self) -> Dict[str, Any]:
        total_files = 0
        total_size = 0
        by_platform = {}

        for ext in ['*.md', '*.json']:
            for f in self.output_dir.rglob(ext):
                total_files += 1
                size = f.stat().st_size
                total_size += size

                parent = f.parent.name
                by_platform[parent] = by_platform.get(parent, 0) + 1

        return {
            'output_dir': str(self.output_dir),
            'total_files': total_files,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'by_platform': dict(sorted(by_platform.items(), key=lambda x: x[1], reverse=True)),
            'format': self.default_format,
            'group_by': self.group_by,
        }

    def _get_target_dir(self, result_dict: Dict, subfolder: Optional[str]) -> Path:
        if subfolder:
            return self.output_dir / subfolder

        if self.group_by == "platform":
            folder = result_dict.get('platform', 'unknown')
        elif self.group_by == "content_type":
            folder = result_dict.get('content_type', 'unknown')
        else:
            folder = ""

        return self.output_dir / folder if folder else self.output_dir

    def _generate_filename(self, result_dict: Dict) -> str:
        url = result_dict.get('url', '')
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        safe_title = ""
        title = result_dict.get('title', '')
        if title:
            safe_title = (
                title[:30]
                .replace('/', '_')
                .replace('\\', '_')
                .replace(':', '_')
                .replace('*', '_')
                .replace('?', '_')
                .replace('"', '_')
                .replace('<', '_')
                .replace('>', '_')
                .replace('|', '_')
                .strip()
            )

        template = self.filename_template
        filename = template.format(
            url_hash=url_hash,
            platform=result_dict.get('platform', 'unknown'),
            title=safe_title or "untitled",
            timestamp=timestamp,
        )

        return filename

    @staticmethod
    def _dict_to_markdown(data: Dict) -> str:
        md = []

        title = data.get('title', 'Untitled')
        md.append(f"# {title}\n")

        md.append("## 基本信息\n\n")
        if data.get('url'):
            md.append(f"- **URL**: {data['url']}")
        if data.get('platform'):
            md.append(f"- **平台**: {data['platform']}")
        if data.get('author'):
            md.append(f"- **作者**: {data['author']}")
        if data.get('publish_date'):
            md.append(f"- **发布日期**: {data['publish_date']}")

        md.append("")

        content = data.get('content', '') or data.get('raw_text', '')
        if content:
            md.append("## 内容\n\n")
            md.append(f"{content}\n")

        return "\n".join(md)