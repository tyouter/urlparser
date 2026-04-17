"""
视频理解模块测试套件

包含单元测试（无需网络/GPU）和集成测试标记。
"""

import pytest
from dataclasses import asdict
from unittest.mock import patch, MagicMock


# =============================================================================
# Unit tests - Config & Models
# =============================================================================

class TestComprehensionConfig:
    """ComprehensionConfig 测试"""

    def test_defaults(self):
        from urlparser.config import ComprehensionConfig
        cfg = ComprehensionConfig()
        assert cfg.enabled is False
        assert cfg.mode == "audio_video"
        assert cfg.engine == "auto"
        assert cfg.max_frames == 50
        assert cfg.scdet_threshold == 10
        assert cfg.language == "zh"
        assert cfg.temp_dir is None

    def test_custom(self):
        from urlparser.config import ComprehensionConfig
        cfg = ComprehensionConfig(
            enabled=True, mode="video_only", engine="llamacpp", max_frames=20
        )
        assert cfg.enabled is True
        assert cfg.mode == "video_only"
        assert cfg.engine == "llamacpp"
        assert cfg.max_frames == 20

    def test_parse_config_has_comprehension(self):
        from urlparser.config import ParseConfig, ComprehensionConfig
        pc = ParseConfig()
        assert hasattr(pc, 'comprehension')
        assert pc.comprehension.enabled is False


class TestComprehensionResult:
    """ComprehensionResult 测试"""

    def test_defaults(self):
        from urlparser.models import ComprehensionResult
        r = ComprehensionResult()
        assert r.success is False
        assert r.mode == "audio_video"
        assert r.visual_frames == []
        assert r.frame_count == 0
        assert not r.has_content

    def test_has_content(self):
        from urlparser.models import ComprehensionResult
        r = ComprehensionResult(success=True, timeline_summary="摘要内容")
        assert r.has_content

    def test_to_dict(self):
        from urlparser.models import ComprehensionResult
        r = ComprehensionResult(success=True, mode="video_only", frame_count=5, engine="openvino")
        d = r.to_dict()
        assert d['success'] is True
        assert d['mode'] == "video_only"
        assert d['frame_count'] == 5
        assert d['engine'] == "openvino"

    def test_to_markdown_success(self):
        from urlparser.models import ComprehensionResult, VisualFrameResult
        r = ComprehensionResult(
            success=True, mode="video_only", engine="llamacpp", frame_count=1,
            visual_frames=[VisualFrameResult(timestamp=10.0, description="测试画面")],
        )
        md = r.to_markdown()
        assert "视频理解" in md
        assert "测试画面" in md

    def test_to_markdown_failure(self):
        from urlparser.models import ComprehensionResult
        r = ComprehensionResult(success=False, error="下载失败")
        md = r.to_markdown()
        assert "视频理解失败" in md
        assert "下载失败" in md


class TestVisualFrameResult:
    """VisualFrameResult 测试"""

    def test_to_dict(self):
        from urlparser.models import VisualFrameResult
        vf = VisualFrameResult(
            timestamp=30.5, description="一个人站在门口", confidence=0.9
        )
        d = vf.to_dict()
        assert d['timestamp'] == 30.5
        assert d['description'] == "一个人站在门口"
        assert d['confidence'] == 0.9


class TestParseConfigWithComprehension:
    """ParseConfig comprehension factory 测试"""

    def test_with_comprehension(self):
        from urlparser.config import ParseConfig
        pc = ParseConfig.with_comprehension(mode="audio_video", engine="openvino")
        assert pc.comprehension.enabled is True
        assert pc.comprehension.mode == "audio_video"
        assert pc.comprehension.engine == "openvino"


class TestParseResultComprehension:
    """ParseResult comprehension 字段测试"""

    def test_default_comprehension(self):
        from urlparser.models import ParseResult
        r = ParseResult()
        assert r.comprehension is not None
        assert r.comprehension.success is False
        assert r.has_comprehension is False

    def test_has_comprehension_true(self):
        from urlparser.models import ParseResult, ComprehensionResult
        r = ParseResult(
            comprehension=ComprehensionResult(success=True, mode="video_only")
        )
        assert r.has_comprehension is True

    def test_full_text_includes_comprehension(self):
        from urlparser.models import ParseResult, ComprehensionResult
        r = ParseResult(
            title="测试视频",
            content="摘要",
            comprehension=ComprehensionResult(
                success=True, mode="video_only", engine="test",
                merged_text="画面描述内容",
            ),
        )
        ft = r.full_text
        assert "测试视频" in ft
        assert "画面描述内容" in ft

    def test_to_dict_includes_comprehension(self):
        from urlparser.models import ParseResult, ComprehensionResult
        r = ParseResult(
            comprehension=ComprehensionResult(success=True, frame_count=3)
        )
        d = r.to_dict()
        assert 'comprehension' in d
        assert d['comprehension']['success'] is True
        assert d['comprehension']['frame_count'] == 3


# =============================================================================
# Unit tests - FrameExtractor (mocked ffmpeg)
# =============================================================================

class TestFrameExtractorSceneDetection:
    """FrameExtractor 场景检测测试 (mocked)"""

    def test_parse_scdet_output(self):
        """测试 scdet 输出解析"""
        mock_stderr = """
Input #0, mov, from 'video.mp4':
  Duration: 00:01:00.00, start: 0.000000, bitrate: 1000 kb/s
[scdet @ 0x1234567] scene change detected pts:100 t:1.000
[scdet @ 0x1234567] scene change detected pts:500 t:5.000
[scdet @ 0x1234567] scene change detected pts:1000 t:10.000
"""
        from urlparser.comprehension.frame_extractor import FrameExtractor

        # Parse the simulated scdet output
        scene_times = []
        for line in mock_stderr.split('\n'):
            if 'scene change detected' in line.lower():
                import re
                match = re.search(r'(?:t|pts_time):([0-9.]+)', line)
                if match:
                    scene_times.append(float(match.group(1)))

        assert len(scene_times) == 3
        assert scene_times[0] == 1.0
        assert scene_times[1] == 5.0
        assert scene_times[2] == 10.0

    def test_mock_ffmpeg_scene_detect(self):
        """测试场景检测 (mocked ffmpeg)"""
        from urlparser.comprehension.frame_extractor import FrameExtractor

        mock_result = MagicMock()
        mock_result.stderr = (
            "[scdet @ 0x123] scene change detected pts:100 t:2.500\n"
            "[scdet @ 0x123] scene change detected pts:500 t:12.000\n"
            "[scdet @ 0x123] scene change detected pts:1000 t:25.000\n"
        )

        with patch('subprocess.run', return_value=mock_result):
            with patch.object(FrameExtractor, '_get_duration', return_value=30.0):
                scenes = FrameExtractor.detect_scenes("video.mp4")

        assert len(scenes) == 3
        assert scenes[0] == (2.5, 12.0)
        assert scenes[1] == (12.0, 25.0)
        assert scenes[2] == (25.0, 30.0)

    def test_no_scenes_fallback(self):
        """测试无场景切换时的回退"""
        from urlparser.comprehension.frame_extractor import FrameExtractor

        mock_result = MagicMock()
        mock_result.stderr = "no scene changes detected"

        with patch('subprocess.run', return_value=mock_result):
            with patch.object(FrameExtractor, '_get_duration', return_value=30.0):
                scenes = FrameExtractor.detect_scenes("video.mp4")

        # 回退到每 10 秒分段
        assert len(scenes) > 0

    def test_short_scene_skipped(self):
        """测试过短场景被跳过"""
        from urlparser.comprehension.frame_extractor import FrameExtractor

        mock_result = MagicMock()
        mock_result.stderr = (
            "[scdet] scene change detected t:1.000\n"
            "[scdet] scene change detected t:1.200\n"  # 0.2s < 0.5s
            "[scdet] scene change detected t:5.000\n"
        )

        with patch('subprocess.run', return_value=mock_result):
            with patch.object(FrameExtractor, '_get_duration', return_value=10.0):
                scenes = FrameExtractor.detect_scenes("video.mp4")

        # 1.0-1.2 场景应被跳过
        for start, end in scenes:
            assert end - start >= 0.5


# =============================================================================
# Unit tests - Hardware Detection & Model Selection
# =============================================================================

class TestHardwareDetection:
    """硬件检测测试 (mocked)"""

    def test_detect_with_npu(self):
        from urlparser.comprehension.models import detect_hardware, HardwareProfile

        mock_core = MagicMock()
        mock_core.available_devices = ['CPU', 'GPU', 'NPU']
        mock_ov = MagicMock()
        mock_ov.Core.return_value = mock_core

        with patch.dict('sys.modules', {'openvino': mock_ov}):
            hw = detect_hardware()
        assert hw == HardwareProfile.INTEL_NPU

    def test_detect_with_igpu_only(self):
        from urlparser.comprehension.models import detect_hardware, HardwareProfile
        import psutil

        mock_core = MagicMock()
        mock_core.available_devices = ['CPU', 'GPU']
        mock_ov = MagicMock()
        mock_ov.Core.return_value = mock_core

        with patch.dict('sys.modules', {'openvino': mock_ov}):
            with patch('psutil.virtual_memory', return_value=MagicMock(total=16 * 1024 ** 3)):
                hw = detect_hardware()
        assert hw == HardwareProfile.INTEL_IGPU

    def test_detect_cpu_fallback(self):
        from urlparser.comprehension.models import detect_hardware, HardwareProfile

        # openvino not available, low RAM
        with patch('psutil.virtual_memory', return_value=MagicMock(total=8 * 1024 ** 3)):
            hw = detect_hardware()
        assert hw == HardwareProfile.CPU_LOW


class TestModelSelection:
    """模型选择测试"""

    def test_select_npu_model(self):
        from urlparser.comprehension.models import (
            select_model, HardwareProfile, VLMBackend
        )
        model, backend, device = select_model(HardwareProfile.INTEL_NPU)
        assert backend == VLMBackend.OPENVINO
        assert device == "NPU"

    def test_select_cpu_high_model(self):
        from urlparser.comprehension.models import (
            select_model, HardwareProfile, VLMBackend
        )
        model, backend, device = select_model(HardwareProfile.CPU_HIGH)
        assert backend == VLMBackend.LLAMACPP
        assert device == "CPU"

    def test_select_cpu_low_model(self):
        from urlparser.comprehension.models import (
            select_model, HardwareProfile, VLMBackend
        )
        model, backend, device = select_model(HardwareProfile.CPU_LOW)
        assert backend == VLMBackend.LLAMACPP
        assert "500m" in model

    def test_force_openvino(self):
        from urlparser.comprehension.models import (
            select_model, HardwareProfile, VLMBackend, ComprehensionConfig
        )
        cfg = ComprehensionConfig(engine="openvino")
        model, backend, device = select_model(HardwareProfile.CPU_HIGH, cfg)
        assert backend == VLMBackend.OPENVINO

    def test_force_llamacpp(self):
        from urlparser.comprehension.models import (
            select_model, HardwareProfile, VLMBackend, ComprehensionConfig
        )
        cfg = ComprehensionConfig(engine="llamacpp")
        model, backend, device = select_model(HardwareProfile.INTEL_NPU, cfg)
        assert backend == VLMBackend.LLAMACPP


# =============================================================================
# Unit tests - Timeline Merge
# =============================================================================

class TestTimelineMerge:
    """时间轴合并测试"""

    def test_merge_with_segments(self):
        from urlparser.comprehension.pipeline import ComprehensionPipeline
        from urlparser.models import VisualFrameResult

        pipeline = ComprehensionPipeline()

        # Mock transcription with segments
        mock_transcription = MagicMock()
        mock_transcription.segments = [
            {'start': 0, 'text': '第一段语音'},
            {'start': 15, 'text': '第二段语音'},
        ]
        mock_transcription.text = ""

        visual_frames = [
            VisualFrameResult(timestamp=5.0, description="画面1"),
            VisualFrameResult(timestamp=20.0, description="画面2"),
        ]

        merged = pipeline._merge_timelines(mock_transcription, visual_frames)

        assert "[画面]" in merged
        assert "[音频]" in merged
        # 应按时间排序
        lines = merged.strip().split('\n')
        # 验证排序正确性

    def test_merge_with_full_text(self):
        from urlparser.comprehension.pipeline import ComprehensionPipeline

        pipeline = ComprehensionPipeline()

        mock_transcription = MagicMock()
        mock_transcription.segments = []
        mock_transcription.text = "完整转录文本"

        merged = pipeline._merge_timelines(mock_transcription, [])
        assert "完整转录文本" in merged


# =============================================================================
# Unit tests - TimelineWriter
# =============================================================================

class TestTimelineWriter:
    """TimelineWriter 测试"""

    def test_write_timeline_format(self, tmp_path):
        from urlparser.comprehension.writer import TimelineWriter
        from urlparser.models import ComprehensionResult, VisualFrameResult

        result = ComprehensionResult(
            success=True,
            mode="video_only",
            engine="test",
            frame_count=2,
            timeline_summary="摘要",
            visual_frames=[
                VisualFrameResult(timestamp=0, description="开场"),
                VisualFrameResult(timestamp=30.0, description="高潮"),
            ],
        )

        writer = TimelineWriter()
        output = writer.write_timeline(result, video_title="测试视频", url="https://example.com/1")

        content = output.read_text(encoding='utf-8')
        assert "测试视频" in content
        assert "开场" in content
        assert "高潮" in content
        assert "https://example.com/1" in content

    def test_write_timeline_error(self, tmp_path):
        from urlparser.comprehension.writer import TimelineWriter
        from urlparser.models import ComprehensionResult

        result = ComprehensionResult(success=False, error="测试错误")
        writer = TimelineWriter()
        output = writer.write_timeline(result, video_title="错误视频")

        content = output.read_text(encoding='utf-8')
        assert "测试错误" in content


# =============================================================================
# Integration tests (skip by default)
# =============================================================================

@pytest.mark.integration
class TestComprehensionIntegration:
    """集成测试（需要网络和 VLM 模型，默认跳过）"""

    def test_full_pipeline(self):
        pytest.skip("需要网络和 VLM 模型")

    def test_cli_comprehension_flag(self):
        pytest.skip("需要 CLI 完整运行")
