"""
批量转录模块

提供批量转录本地音视频文件的功能

使用方式:
    from urlparser.batch_transcriber import BatchTranscriber, BatchTranscribeConfig

    config = BatchTranscribeConfig(skip_existing=True)
    processor = BatchTranscriber(config)

    # 扫描目录
    scan_result, preview = processor.scan_and_preview("./videos")
    print(preview)

    # 过滤待处理文件
    files = processor.filter_files_to_process(scan_result)

    # 执行转录
    result = processor.transcribe_all(files)
"""

from .scanner import MediaScanner, MediaFileInfo, ScanResult, generate_preview_text
from .segment import (
    SegmentHandler, SegmentInfo, SegmentationConfig,
    get_recommended_config, estimate_gpu_segment_size
)
from .writer import TranscriptionWriter, WriterConfig, generate_simple_md
from .processor import (
    BatchTranscriber, BatchTranscribeConfig, BatchResult, FileResult,
    format_batch_result_summary, create_progress_bar_description
)


__all__ = [
    # Scanner
    'MediaScanner',
    'MediaFileInfo',
    'ScanResult',
    'generate_preview_text',

    # Segment
    'SegmentHandler',
    'SegmentInfo',
    'SegmentationConfig',
    'get_recommended_config',
    'estimate_gpu_segment_size',

    # Writer
    'TranscriptionWriter',
    'WriterConfig',
    'generate_simple_md',

    # Processor
    'BatchTranscriber',
    'BatchTranscribeConfig',
    'BatchResult',
    'FileResult',
    'format_batch_result_summary',
    'create_progress_bar_description',
]