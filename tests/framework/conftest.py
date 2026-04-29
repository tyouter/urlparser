"""
urlparser 测试框架 - 共享 fixtures 和配置

测试分层:
    P0 纯函数单元测试  (无网络, 无IO, 毫秒级)
    P1 模型/配置属性测试 (无网络, Hypothesis 属性基测试)
    P2 反爬/质量检测测试 (无网络, 规则引擎验证)
    P3 接口一致性测试   (需网络, API/CLI/SKILL 输出交叉验证)
    P4 回归快照测试     (需网络, 输出与基准快照对比)
    P5 跨接口等价性测试 (需网络, 深度内容对比)

运行方式:
    pytest tests/framework/ -m "not integration"    # 快速测试 (P0-P2)
    pytest tests/framework/ -m integration           # 集成测试 (P3-P5)
    pytest tests/framework/                          # 全部
    pytest tests/framework/ --snapshot-update        # 更新快照基准
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from test_utils import URLFixture, TEST_URLS, SNAPSHOTS_DIR

os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: marks tests requiring network (deselect with '-m \"not integration\"')")
    config.addinivalue_line("markers", "slow: marks slow tests (transcription, etc.)")
    config.addinivalue_line("markers", "p0: pure function unit tests, no IO")
    config.addinivalue_line("markers", "p1: model/config property-based tests")
    config.addinivalue_line("markers", "p2: anti-scraping/quality detection tests")
    config.addinivalue_line("markers", "p3: interface consistency tests (needs network)")
    config.addinivalue_line("markers", "p4: regression snapshot tests (needs network)")


@pytest.fixture
def test_urls():
    return TEST_URLS


@pytest.fixture
def article_urls():
    return [u for u in TEST_URLS if u.content_type == "article"]


@pytest.fixture
def video_urls():
    return [u for u in TEST_URLS if u.content_type == "video"]


@pytest.fixture
def snapshots_dir():
    return SNAPSHOTS_DIR


@pytest.fixture
def snapshot_update(request):
    return request.config.getoption("--snapshot-update", default=False)


def pytest_addoption(parser):
    parser.addoption("--snapshot-update", action="store_true", default=False,
                     help="Update snapshot baselines instead of comparing")
