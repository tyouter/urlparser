"""
状态管理

提供去重、状态检查、数据完整性验证
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from ..utils.url_utils import URLNormalizer


class ProcessStatus(Enum):
    NOT_PROCESSED = "not_processed"
    PROCESSED_NO_CONTENT = "processed_no_content"
    PROCESSED_WITH_CONTENT = "processed_with_content"
    PROCESSED_WITH_ANALYSIS = "processed_with_analysis"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    ERROR = "error"


@dataclass
class ResourceState:
    url: str
    normalized_url: str
    url_hash: str
    processed: bool
    processed_at: Optional[str]
    content_fetched: bool
    source_path: Optional[str]
    source_exists: bool
    analyzed: bool
    analyzed_at: Optional[str]
    analysis_complete: bool
    in_processed_json: bool
    in_analysis_json: bool
    in_sources_index: bool
    in_resources_json: bool
    file_size: Optional[int]
    file_content_length: Optional[int]
    duplicate_urls: List[str]
    duplicate_files: List[str]


class StateManager:
    """统一状态管理器，提供去重和状态检查"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)

        self.processed_file = self.data_dir / "processed.json"
        self.analysis_file = self.data_dir / "analysis.json"
        self.resources_file = self.data_dir / "resources.json"
        self.url_mapping_file = self.data_dir / "url_mapping.json"
        self.sources_dir = self.data_dir / "sources"
        self.sources_index_file = self.sources_dir / "index.json"

        self._processed = None
        self._analysis = None
        self._resources = None
        self._url_mapping = None
        self._sources_index = None

        self._url_normalizer = URLNormalizer()

    def normalize_url(self, url: str) -> str:
        return self._url_normalizer.normalize(url)

    def hash_url(self, url: str) -> str:
        normalized = self.normalize_url(url)
        return hashlib.md5(normalized.encode()).hexdigest()

    def check_resource_state(self, url: str) -> ResourceState:
        normalized_url = self.normalize_url(url)
        normalized_hash = self.hash_url(url)
        original_hash = hashlib.md5(url.encode()).hexdigest()

        self._load_all_data()

        in_processed_json = (
            self._check_in_processed(normalized_url, normalized_hash) or
            self._check_in_processed(normalized_url, original_hash)
        )
        processed_info = (
            self._get_processed_info(normalized_url, normalized_hash) or
            self._get_processed_info(normalized_url, original_hash)
        )

        in_analysis_json, analysis_info = self._find_analysis_by_normalized_url(normalized_url)

        source_path = (
            self._get_source_path(normalized_url, normalized_hash) or
            self._get_source_path(normalized_url, original_hash) or
            (analysis_info.get('analysis', {}).get('source_path') if analysis_info else None)
        )
        source_exists = source_path and Path(source_path).exists()

        url_hash = processed_info.get('hash') if processed_info else original_hash

        in_sources_index = normalized_url in self._sources_index
        in_resources_json = normalized_url in self._resources

        file_size = None
        file_content_length = None
        if source_exists:
            try:
                file_stat = Path(source_path).stat()
                file_size = file_stat.st_size
                if file_size < 10 * 1024 * 1024:
                    try:
                        content = Path(source_path).read_text(encoding='utf-8')
                        file_content_length = len(content)
                    except Exception:
                        pass
            except Exception:
                pass

        duplicate_urls = self._find_duplicate_urls(url_hash)
        duplicate_files = self._find_duplicate_files(source_path) if source_path else []

        processed_at = None
        if processed_info:
            processed_at = processed_info.get('processed_at')

        analyzed_at = None
        if analysis_info:
            analyzed_at = analysis_info.get('stored_at')

        analysis_complete = False
        if in_analysis_json:
            analysis = analysis_info.get('analysis', {})
            if isinstance(analysis, dict):
                analysis_complete = self._is_analysis_complete(analysis)

        content_fetched = False
        if in_analysis_json:
            analysis = analysis_info.get('analysis', {})
            if isinstance(analysis, dict):
                content_fetched = analysis.get('content_fetched', False)

        return ResourceState(
            url=url,
            normalized_url=normalized_url,
            url_hash=url_hash,
            processed=in_processed_json,
            processed_at=processed_at,
            content_fetched=content_fetched,
            source_path=source_path,
            source_exists=source_exists,
            analyzed=in_analysis_json,
            analyzed_at=analyzed_at,
            analysis_complete=analysis_complete,
            in_processed_json=in_processed_json,
            in_analysis_json=in_analysis_json,
            in_sources_index=in_sources_index,
            in_resources_json=in_resources_json,
            file_size=file_size,
            file_content_length=file_content_length,
            duplicate_urls=duplicate_urls,
            duplicate_files=duplicate_files
        )

    def get_process_status(self, url: str) -> ProcessStatus:
        state = self.check_resource_state(url)

        if not state.processed:
            return ProcessStatus.NOT_PROCESSED

        if not state.source_exists or not state.content_fetched:
            return ProcessStatus.PROCESSED_NO_CONTENT

        if not state.analyzed or not state.analysis_complete:
            return ProcessStatus.PROCESSED_WITH_CONTENT

        if not (state.in_processed_json and
                state.in_analysis_json and
                state.source_exists):
            return ProcessStatus.INCOMPLETE

        return ProcessStatus.COMPLETE

    def check_all_resources(self) -> List[ResourceState]:
        self._load_all_data()

        all_urls = set()

        if self._processed:
            for item in self._processed:
                if isinstance(item, dict):
                    url = item.get('url', '')
                    if url:
                        all_urls.add(url)

        if self._analysis:
            for hash_key, data in self._analysis.items():
                if isinstance(data, dict):
                    url = data.get('url', '')
                    if url:
                        all_urls.add(url)

        if self._sources_index:
            all_urls.update(self._sources_index.keys())

        states = []
        for url in all_urls:
            if url:
                try:
                    state = self.check_resource_state(url)
                    states.append(state)
                except Exception:
                    pass

        return states

    def find_duplicates(self) -> Dict[str, List[ResourceState]]:
        all_states = self.check_all_resources()
        duplicates = {}

        hash_groups: Dict[str, List[ResourceState]] = {}
        for state in all_states:
            if state.url_hash not in hash_groups:
                hash_groups[state.url_hash] = []
            hash_groups[state.url_hash].append(state)

        for hash_key, states in hash_groups.items():
            unique_urls = set(s.url for s in states)
            if len(unique_urls) > 1:
                duplicates[hash_key] = states

        return duplicates

    def validate_integrity(self) -> Dict:
        self._load_all_data()

        report = {
            'valid': True,
            'issues': [],
            'warnings': [],
            'summary': {}
        }

        processed_hashes = set()
        if self._processed:
            for item in self._processed:
                if isinstance(item, dict):
                    processed_hashes.add(item.get('hash', ''))

        analysis_hashes = set(self._analysis.keys()) if self._analysis else set()

        processed_only = processed_hashes - analysis_hashes
        analysis_only = analysis_hashes - processed_hashes

        if processed_only:
            report['issues'].append({
                'type': 'processed_without_analysis',
                'count': len(processed_only),
                'hashes': list(processed_only)[:10]
            })
            report['valid'] = False

        if analysis_only:
            report['warnings'].append({
                'type': 'analysis_without_processed',
                'count': len(analysis_only),
                'hashes': list(analysis_only)[:10]
            })

        missing_files = []
        if self._analysis:
            for hash_key, data in self._analysis.items():
                if isinstance(data, dict):
                    analysis = data.get('analysis', {})
                    if isinstance(analysis, dict):
                        source_path = analysis.get('source_path')
                        if source_path and not Path(source_path).exists():
                            missing_files.append({
                                'hash': hash_key,
                                'url': data.get('url', ''),
                                'source_path': source_path
                            })

        if missing_files:
            report['issues'].append({
                'type': 'missing_source_files',
                'count': len(missing_files),
                'files': missing_files[:10]
            })
            report['valid'] = False

        if self._sources_index:
            for url, info in self._sources_index.items():
                source_path = info.get('source_path')
                if source_path and not Path(source_path).exists():
                    report['warnings'].append({
                        'type': 'index_file_missing',
                        'url': url,
                        'source_path': source_path
                    })

        all_states = self.check_all_resources()
        file_map = {}
        for state in all_states:
            if state.source_path and state.source_exists:
                if state.source_path in file_map:
                    report['warnings'].append({
                        'type': 'duplicate_file_reference',
                        'file': state.source_path,
                        'urls': [file_map[state.source_path], state.url]
                    })
                else:
                    file_map[state.source_path] = state.url

        report['summary'] = {
            'total_processed': len(self._processed) if self._processed else 0,
            'total_analyzed': len(self._analysis) if self._analysis else 0,
            'total_in_index': len(self._sources_index) if self._sources_index else 0,
            'processed_only_count': len(processed_only),
            'analysis_only_count': len(analysis_only),
            'missing_files_count': len(missing_files)
        }

        return report

    def _load_all_data(self):
        self._load_processed()
        self._load_analysis()
        self._load_resources()
        self._load_url_mapping()
        self._load_sources_index()

    def _load_processed(self):
        if self._processed is None:
            if self.processed_file.exists():
                try:
                    content = self.processed_file.read_text(encoding='utf-8')
                    self._processed = json.loads(content) if content.strip() else []
                except Exception:
                    self._processed = []
            else:
                self._processed = []

    def _load_analysis(self):
        if self._analysis is None:
            if self.analysis_file.exists():
                try:
                    content = self.analysis_file.read_text(encoding='utf-8')
                    self._analysis = json.loads(content) if content.strip() else {}
                except Exception:
                    self._analysis = {}
            else:
                self._analysis = {}

    def _load_resources(self):
        if self._resources is None:
            if self.resources_file.exists():
                try:
                    content = self.resources_file.read_text(encoding='utf-8')
                    self._resources = json.loads(content) if content.strip() else {}
                except Exception:
                    self._resources = {}
            else:
                self._resources = {}

    def _load_url_mapping(self):
        if self._url_mapping is None:
            if self.url_mapping_file.exists():
                try:
                    content = self.url_mapping_file.read_text(encoding='utf-8')
                    self._url_mapping = json.loads(content) if content.strip() else {}
                except Exception:
                    self._url_mapping = {}
            else:
                self._url_mapping = {}

    def _load_sources_index(self):
        if self._sources_index is None:
            if self.sources_index_file.exists():
                try:
                    content = self.sources_index_file.read_text(encoding='utf-8')
                    self._sources_index = json.loads(content) if content.strip() else {}
                except Exception:
                    self._sources_index = {}
            else:
                self._sources_index = {}

    def _check_in_processed(self, normalized_url: str, url_hash: str) -> bool:
        if not self._processed:
            return False

        for item in self._processed:
            if isinstance(item, dict):
                if item.get('hash') == url_hash:
                    return True
                stored_url = item.get('url', '')
                if stored_url:
                    stored_normalized = self.normalize_url(stored_url)
                    if stored_normalized == normalized_url:
                        return True
        return False

    def _get_processed_info(self, normalized_url: str, url_hash: str) -> Optional[Dict]:
        if not self._processed:
            return None

        for item in self._processed:
            if isinstance(item, dict):
                if item.get('hash') == url_hash:
                    return item
                stored_url = item.get('url', '')
                if stored_url:
                    stored_normalized = self.normalize_url(stored_url)
                    if stored_normalized == normalized_url:
                        return item
        return None

    def _find_analysis_by_normalized_url(self, normalized_url: str) -> tuple:
        if not self._analysis:
            return False, {}

        normalized_hash = self.hash_url(normalized_url)
        if normalized_hash in self._analysis:
            return True, self._analysis[normalized_hash]

        for hash_key, data in self._analysis.items():
            if isinstance(data, dict):
                stored_url = data.get('url', '')
                if stored_url:
                    stored_normalized = self.normalize_url(stored_url)
                    if stored_normalized == normalized_url:
                        return True, data

        return False, {}

    def _get_source_path(self, normalized_url: str, url_hash: str) -> Optional[str]:
        if self._analysis and url_hash in self._analysis:
            analysis = self._analysis[url_hash].get('analysis', {})
            if isinstance(analysis, dict) and 'source_path' in analysis:
                return analysis['source_path']

        if self._sources_index and normalized_url in self._sources_index:
            info = self._sources_index[normalized_url]
            if isinstance(info, dict) and 'source_path' in info:
                return info['source_path']

        return None

    def _is_analysis_complete(self, analysis: Dict) -> bool:
        required_fields = ['essence', 'expertise_level', 'primary_topics', 'knowledge_value']
        return all(field in analysis for field in required_fields)

    def _find_duplicate_urls(self, url_hash: str) -> List[str]:
        duplicates = []

        if self._processed:
            for item in self._processed:
                if isinstance(item, dict) and item.get('hash') == url_hash:
                    url = item.get('url', '')
                    if url and url not in duplicates:
                        duplicates.append(url)

        return duplicates

    def _find_duplicate_files(self, source_path: str) -> List[str]:
        if not source_path:
            return []

        duplicates = []
        file_path = Path(source_path)

        if not file_path.exists():
            return duplicates

        stem = file_path.stem
        parts = stem.split('_')
        if not parts:
            return []

        hash_prefix = parts[0]

        for sibling in file_path.parent.glob(f"{hash_prefix}*"):
            if sibling != file_path:
                duplicates.append(str(sibling))

        return duplicates