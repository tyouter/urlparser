"""
批量转录模块测试套件

测试文件扫描、分段处理、批量转录等核心功能
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os


class TestMediaUtils:
    """音视频工具测试"""

    def test_import_media_utils(self):
        """测试音视频工具导入"""
        from urlparser.utils.media_utils import (
            is_audio_file, is_video_file, is_media_file,
            get_media_duration, format_duration, format_duration_detailed,
            AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, MEDIA_EXTENSIONS
        )
        assert callable(is_audio_file)
        assert callable(is_video_file)
        assert callable(is_media_file)
        assert callable(get_media_duration)
        assert callable(format_duration)
        assert callable(format_duration_detailed)

    def test_audio_extensions(self):
        """测试音频扩展名识别"""
        from urlparser.utils.media_utils import is_audio_file, AUDIO_EXTENSIONS

        # 测试常见音频格式
        assert '.mp3' in AUDIO_EXTENSIONS
        assert '.wav' in AUDIO_EXTENSIONS
        assert '.flac' in AUDIO_EXTENSIONS
        assert '.m4a' in AUDIO_EXTENSIONS

        assert is_audio_file('test.mp3')
        assert is_audio_file('test.wav')
        assert is_audio_file('/path/to/file.m4a')
        assert not is_audio_file('test.mp4')
        assert not is_audio_file('test.txt')

    def test_video_extensions(self):
        """测试视频扩展名识别"""
        from urlparser.utils.media_utils import is_video_file, VIDEO_EXTENSIONS

        # 测试常见视频格式
        assert '.mp4' in VIDEO_EXTENSIONS
        assert '.mkv' in VIDEO_EXTENSIONS
        assert '.avi' in VIDEO_EXTENSIONS
        assert '.mov' in VIDEO_EXTENSIONS

        assert is_video_file('test.mp4')
        assert is_video_file('test.mkv')
        assert is_video_file('/path/to/file.avi')
        assert not is_video_file('test.mp3')
        assert not is_video_file('test.txt')

    def test_media_extensions(self):
        """测试音视频扩展名识别"""
        from urlparser.utils.media_utils import is_media_file, MEDIA_EXTENSIONS

        assert '.mp3' in MEDIA_EXTENSIONS
        assert '.mp4' in MEDIA_EXTENSIONS

        assert is_media_file('test.mp3')
        assert is_media_file('test.mp4')
        assert not is_media_file('test.txt')
        assert not is_media_file('test.pdf')

    def test_format_duration(self):
        """测试时长格式化"""
        from urlparser.utils.media_utils import format_duration

        assert format_duration(0) == "00:00"
        assert format_duration(60) == "01:00"
        assert format_duration(90) == "01:30"
        assert format_duration(3600) == "1:00:00"
        assert format_duration(3661) == "1:01:01"

    def test_format_duration_detailed(self):
        """测试详细时长格式化"""
        from urlparser.utils.media_utils import format_duration_detailed

        assert format_duration_detailed(0) == "未知"
        assert format_duration_detailed(60) == "1分"  # 0秒不显示
        assert format_duration_detailed(90) == "1分30秒"
        assert format_duration_detailed(3600) == "1小时"
        assert format_duration_detailed(3661) == "1小时1分1秒"


class TestScanner:
    """文件扫描器测试"""

    def test_import_scanner(self):
        """测试扫描器导入"""
        from urlparser.batch_transcriber import (
            MediaScanner, MediaFileInfo, ScanResult, generate_preview_text
        )
        assert MediaScanner
        assert MediaFileInfo
        assert ScanResult
        assert callable(generate_preview_text)

    def test_media_file_info_creation(self):
        """测试 MediaFileInfo 创建"""
        from urlparser.batch_transcriber import MediaFileInfo

        info = MediaFileInfo(
            path=Path('/test/video.mp4'),
            size_bytes=1024 * 1024 * 100,  # 100MB
            duration_seconds=1800,  # 30分钟
            is_video=True,
            existing_md=None
        )

        assert info.filename == 'video.mp4'
        assert info.extension == '.mp4'
        assert info.is_video
        assert not info.has_existing_md

    def test_media_file_info_properties(self):
        """测试 MediaFileInfo 属性"""
        from urlparser.batch_transcriber import MediaFileInfo

        info = MediaFileInfo(
            path=Path('/test/audio.mp3'),
            size_bytes=1024 * 1024 * 50,
            duration_seconds=600,
            is_video=False,
            existing_md=Path('/test/audio.md')
        )

        assert info.size_str == '50.0 MB'
        # Note: has_existing_md checks if the file exists on disk
        # In tests, the file doesn't exist, so it returns False
        assert not info.has_existing_md  # File doesn't exist on disk
        assert info.md_path == Path('/test/audio.md')
        assert info.existing_md == Path('/test/audio.md')  # The path is set

    def test_scan_result_properties(self):
        """测试 ScanResult 属性"""
        from urlparser.batch_transcriber import ScanResult

        result = ScanResult(
            total_count=10,
            audio_count=5,
            video_count=5,
            total_size_bytes=1024 * 1024 * 1000,
            total_duration_seconds=3600,
            existing_md_count=3
        )

        assert result.pending_count == 7
        assert result.total_size_str == '1000.0 MB'

    def test_media_scanner_creation(self):
        """测试 MediaScanner 创建"""
        from urlparser.batch_transcriber import MediaScanner

        scanner = MediaScanner(timeout_per_file=30.0)
        assert scanner.timeout_per_file == 30.0

    def test_media_scanner_filter_pending(self):
        """测试待处理文件过滤"""
        from urlparser.batch_transcriber import MediaScanner, MediaFileInfo

        scanner = MediaScanner()

        files = [
            MediaFileInfo(
                path=Path('/test/file1.mp3'),
                size_bytes=1000,
                duration_seconds=60,
                is_video=False,
                existing_md=None  # 无转录
            ),
            MediaFileInfo(
                path=Path('/test/file2.mp4'),
                size_bytes=2000,
                duration_seconds=120,
                is_video=True,
                existing_md=None  # 设置为 None，文件不存在
            ),
        ]

        # 跳过已有转录（但测试文件不存在，所以两个都应该被处理）
        pending = scanner.filter_pending(files, skip_existing=True)
        assert len(pending) == 2  # 两个文件的 MD 都不存在

        # 不跳过
        pending = scanner.filter_pending(files, skip_existing=False)
        assert len(pending) == 2

    def test_media_scanner_filter_by_duration(self):
        """测试时长过滤"""
        from urlparser.batch_transcriber import MediaScanner, MediaFileInfo

        scanner = MediaScanner()

        files = [
            MediaFileInfo(path=Path('/a'), size_bytes=0, duration_seconds=60, is_video=False),
            MediaFileInfo(path=Path('/b'), size_bytes=0, duration_seconds=120, is_video=False),
            MediaFileInfo(path=Path('/c'), size_bytes=0, duration_seconds=300, is_video=False),
        ]

        filtered = scanner.filter_by_duration(files, min_duration=100, max_duration=200)
        assert len(filtered) == 1
        assert filtered[0].duration_seconds == 120

    def test_generate_preview_text(self):
        """测试预览文本生成"""
        from urlparser.batch_transcriber import (
            ScanResult, MediaFileInfo, generate_preview_text
        )

        result = ScanResult(
            files=[
                MediaFileInfo(
                    path=Path('/test/video.mp4'),
                    size_bytes=1024 * 1024,
                    duration_seconds=120,
                    is_video=True,
                    existing_md=None
                )
            ],
            total_count=1,
            audio_count=0,
            video_count=1,
            total_size_bytes=1024 * 1024,
            total_duration_seconds=120,
            existing_md_count=0
        )

        preview = generate_preview_text(result)
        assert '总文件数: 1' in preview
        assert '视频文件: 1' in preview
        assert '待处理文件: 1' in preview


class TestSegment:
    """分段处理测试"""

    def test_import_segment(self):
        """测试分段模块导入"""
        from urlparser.batch_transcriber import (
            SegmentHandler, SegmentInfo, SegmentationConfig,
            get_recommended_config, estimate_gpu_segment_size
        )
        assert SegmentHandler
        assert SegmentInfo
        assert SegmentationConfig
        assert callable(get_recommended_config)
        assert callable(estimate_gpu_segment_size)

    def test_segment_info_creation(self):
        """测试 SegmentInfo 创建"""
        from urlparser.batch_transcriber import SegmentInfo

        seg = SegmentInfo(start=0, end=1800, index=0)
        assert seg.duration == 1800
        assert seg.range_str == "00:00 - 30:00"

    def test_segmentation_config_defaults(self):
        """测试分段配置默认值"""
        from urlparser.batch_transcriber import SegmentationConfig

        config = SegmentationConfig()
        assert config.max_segment_duration == 1800.0  # 30分钟
        assert config.max_segment_size_mb == 500.0
        assert config.overlap_seconds == 2.0

    def test_segment_handler_should_segment(self):
        """测试分段判断"""
        from urlparser.batch_transcriber import SegmentHandler, SegmentationConfig

        config = SegmentationConfig(
            max_segment_duration=1800.0,
            max_segment_size_mb=500.0
        )
        handler = SegmentHandler(config)

        # 短小文件不分段
        assert not handler.should_segment(600, 100)  # 10分钟, 100MB

        # 长文件分段
        assert handler.should_segment(2400, 100)  # 40分钟

        # 大文件分段
        assert handler.should_segment(600, 600)  # 600MB

    def test_segment_handler_calculate_segments(self):
        """测试分段计算"""
        from urlparser.batch_transcriber import SegmentHandler, SegmentationConfig

        config = SegmentationConfig(max_segment_duration=1800.0)
        handler = SegmentHandler(config)

        # 短文件单段
        segments = handler.calculate_segments(600)
        assert len(segments) == 1
        assert segments[0].start == 0
        assert segments[0].end == 600

        # 长文件多段
        segments = handler.calculate_segments(3600)  # 1小时
        assert len(segments) >= 2

    def test_estimate_gpu_segment_size(self):
        """测试 GPU 分段大小估算"""
        from urlparser.batch_transcriber import estimate_gpu_segment_size

        # 低显存 (< 4GB)
        assert estimate_gpu_segment_size(2) == 900.0  # 15分钟
        assert estimate_gpu_segment_size(3.9) == 900.0

        # 中等显存 (4GB <= x < 8GB)
        assert estimate_gpu_segment_size(4) == 1800.0  # 30分钟
        assert estimate_gpu_segment_size(6) == 1800.0  # 30分钟
        assert estimate_gpu_segment_size(7.9) == 1800.0

        # 较高显存 (8GB <= x < 16GB)
        assert estimate_gpu_segment_size(8) == 3600.0  # 60分钟
        assert estimate_gpu_segment_size(12) == 3600.0  # 60分钟
        assert estimate_gpu_segment_size(15.9) == 3600.0

        # 高显存 (>= 16GB)
        assert estimate_gpu_segment_size(16) == 7200.0  # 120分钟
        assert estimate_gpu_segment_size(32) == 7200.0  # 120分钟

    def test_get_recommended_config(self):
        """测试推荐配置获取"""
        from urlparser.batch_transcriber import get_recommended_config

        # 小文件 (< 500MB, < 30分钟)
        config = get_recommended_config(100, 600)  # 100MB, 10分钟
        assert config.max_segment_duration == 1800.0  # 默认30分钟

        # 大文件 (> 1GB)
        config = get_recommended_config(1200, 7200)  # 1.2GB, 2小时
        assert config.max_segment_duration == 900.0  # 15分钟 (因文件>1GB)

        # 中等文件 (> 500MB)
        config = get_recommended_config(600, 1800)  # 600MB, 30分钟
        assert config.max_segment_duration == 1200.0  # 20分钟 (因文件>500MB)

        # 考虑 GPU 显存
        config = get_recommended_config(500, 1800, gpu_memory_gb=4)
        # GPU显存4GB返回1800秒(30分钟), 和默认相同
        assert config.max_segment_duration == 1800.0


class TestWriter:
    """转录结果写入测试"""

    def test_import_writer(self):
        """测试写入器导入"""
        from urlparser.batch_transcriber import (
            TranscriptionWriter, WriterConfig, generate_simple_md
        )
        assert TranscriptionWriter
        assert WriterConfig
        assert callable(generate_simple_md)

    def test_writer_config_defaults(self):
        """测试写入配置默认值"""
        from urlparser.batch_transcriber import WriterConfig

        config = WriterConfig()
        assert config.include_metadata
        assert config.include_timestamps
        assert config.include_segments
        assert config.max_segments_display == 100

    def test_transcription_writer_init(self):
        """测试写入器初始化"""
        from urlparser.batch_transcriber import TranscriptionWriter, WriterConfig

        writer = TranscriptionWriter()
        assert writer.config

        config = WriterConfig(include_timestamps=False)
        writer = TranscriptionWriter(config)
        assert writer.config.include_timestamps == False

    def test_format_segment_time(self):
        """测试分段时间格式化"""
        from urlparser.batch_transcriber import TranscriptionWriter

        writer = TranscriptionWriter()

        time_str = writer._format_segment_time(0, 60)
        assert time_str == "00:00 - 01:00"

        time_str = writer._format_segment_time(3600, 3661)
        assert time_str == "01:00:00 - 01:01:01"


class TestProcessor:
    """批量处理器测试"""

    def test_import_processor(self):
        """测试处理器导入"""
        from urlparser.batch_transcriber import (
            BatchTranscriber, BatchTranscribeConfig, BatchResult, FileResult,
            format_batch_result_summary, create_progress_bar_description
        )
        assert BatchTranscriber
        assert BatchTranscribeConfig
        assert BatchResult
        assert FileResult
        assert callable(format_batch_result_summary)
        assert callable(create_progress_bar_description)

    def test_batch_transcribe_config_defaults(self):
        """测试批量配置默认值"""
        from urlparser.batch_transcriber import BatchTranscribeConfig

        config = BatchTranscribeConfig()
        assert config.engine == "auto"
        assert config.model_size == "large"
        assert config.language == "zh"
        assert config.recursive
        assert config.skip_existing
        assert config.segment_threshold_min == 30.0
        assert config.max_file_size_mb == 500.0

    def test_batch_transcribe_config_methods(self):
        """测试批量配置方法"""
        from urlparser.batch_transcriber import BatchTranscribeConfig

        config = BatchTranscribeConfig(segment_threshold_min=30.0)
        assert config.get_segment_threshold_seconds() == 1800.0

        config = BatchTranscribeConfig(max_file_size_mb=500.0)
        assert config.get_max_file_size_bytes() == 500 * 1024 * 1024

    def test_file_result_creation(self):
        """测试 FileResult 创建"""
        from urlparser.batch_transcriber import FileResult, MediaFileInfo
        from urlparser.transcriber.base import TranscriptionResult

        file_info = MediaFileInfo(
            path=Path('/test/video.mp4'),
            size_bytes=1024 * 1024,
            duration_seconds=600,
            is_video=True
        )

        result = FileResult(
            file_info=file_info,
            transcription=TranscriptionResult(success=True, text="test"),
            process_time=120,
            success=True
        )

        assert result.speed_factor == 0.2  # 120/600

    def test_batch_result_properties(self):
        """测试 BatchResult 属性"""
        from urlparser.batch_transcriber import BatchResult

        result = BatchResult(
            total_files=10,
            success_count=8,
            failed_count=2,
            total_duration=3600,
            total_time=1200
        )

        assert result.success_rate == 0.8
        assert result.total_time_str == "20:00"

    def test_batch_transcriber_creation(self):
        """测试 BatchTranscriber 创建"""
        from urlparser.batch_transcriber import BatchTranscriber, BatchTranscribeConfig

        config = BatchTranscribeConfig(engine="funasr")
        processor = BatchTranscriber(config)
        assert processor.config.engine == "funasr"
        assert processor.scanner
        assert processor.writer

    def test_format_batch_result_summary(self):
        """测试批量结果摘要"""
        from urlparser.batch_transcriber import BatchResult, format_batch_result_summary

        result = BatchResult(
            total_files=10,
            success_count=8,
            failed_count=2,
            total_duration=3600,
            total_time=1200
        )

        summary = format_batch_result_summary(result)
        assert '总文件数: 10' in summary
        assert '成功: 8' in summary
        assert '失败: 2' in summary
        assert '成功率' in summary


class TestTopLevelExports:
    """顶层导出测试"""

    def test_import_batch_transcriber_from_top(self):
        """测试从顶层导入批量转录模块"""
        from urlparser import (
            BatchTranscriber, BatchTranscribeConfig,
            MediaScanner, MediaFileInfo, ScanResult,
            SegmentHandler, SegmentationConfig,
            TranscriptionWriter, WriterConfig,
        )
        assert BatchTranscriber
        assert BatchTranscribeConfig
        assert MediaScanner
        assert MediaFileInfo
        assert ScanResult
        assert SegmentHandler
        assert SegmentationConfig
        assert TranscriptionWriter
        assert WriterConfig

    def test_import_media_utils_from_top(self):
        """测试从顶层导入音视频工具"""
        from urlparser import (
            is_audio_file, is_video_file, is_media_file,
            get_media_duration, format_duration, format_duration_detailed,
            file_size_str, list_files,
        )
        assert callable(is_audio_file)
        assert callable(is_video_file)
        assert callable(is_media_file)
        assert callable(get_media_duration)
        assert callable(format_duration)
        assert callable(format_duration_detailed)
        assert callable(file_size_str)
        assert callable(list_files)

    def test_batch_transcribe_config_in_config_module(self):
        """测试 BatchTranscribeConfig 在 config 模块中"""
        from urlparser.config import BatchTranscribeConfig
        assert BatchTranscribeConfig


class TestCLI:
    """CLI 命令测试"""

    def test_transcribe_folder_parser_creation(self):
        """测试 transcribe-folder 命令解析器"""
        from urlparser.cli import create_parser

        parser = create_parser()

        # 测试命令存在 - 使用有效参数而非 --help (会导致 SystemExit)
        args = parser.parse_args(['transcribe-folder', './test_dir', '--preview'])
        assert args.command == 'transcribe-folder'
        assert args.directory == './test_dir'
        assert args.preview == True


# 集成测试标记为 skip（需要真实文件）
@pytest.mark.skip(reason="需要真实音视频文件和 ffmpeg")
class TestIntegrationRealFiles:
    """真实文件集成测试"""

    def test_scan_real_directory(self):
        """测试扫描真实目录"""
        from urlparser.batch_transcriber import MediaScanner

        scanner = MediaScanner()
        result = scanner.scan_directory('./test_media')

        assert result.total_count > 0

    def test_transcribe_real_file(self):
        """测试转录真实文件"""
        from urlparser.batch_transcriber import BatchTranscriber, BatchTranscribeConfig
        from urlparser.batch_transcriber import MediaFileInfo

        config = BatchTranscribeConfig(engine="funasr")
        processor = BatchTranscriber(config)

        file_info = MediaFileInfo(
            path=Path('./test_media/audio.mp3'),
            size_bytes=1024 * 1024,
            duration_seconds=60,
            is_video=False
        )

        result = processor.transcribe_single(file_info)
        assert result.success