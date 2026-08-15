"""
v4 doctor 模块测试（docs/v4-implementation-plan.md 任务 G）

同步测试（项目 asyncio_mode=auto，但本模块为同步实现）。
run_checks() 通过 module 级 fixture 只执行一次：其中 playwright_browsers
会真实启动 Chromium、gpu 会导入 torch/openvino，可能较慢，因此各测试
共用同一次结果，接受任意 status，只断言不抛异常且结构正确。
测试不联网、不下载任何东西。
"""

import json

import pytest

from urlparser.doctor import HealthReport, run_checks, main


@pytest.fixture(scope="module")
def report():
    """整个模块只运行一次真实自检（playwright/GPU 检查可能耗时）。"""
    return run_checks()


class TestRunChecks:
    def test_run_checks_no_exception(self, report):
        assert isinstance(report, HealthReport)
        assert report.checks  # 非空
        for check in report.checks:
            assert check.name  # 每个 check 有 name
            assert check.status in ("ok", "warn", "fail", "unknown")
            assert isinstance(check.detail, str)
            assert isinstance(check.fix_hint, (str, type(None)))


class TestReportSerialization:
    def test_report_serialization(self, report):
        d = report.to_dict()
        assert "healthy" in d
        assert isinstance(d["healthy"], bool)
        assert isinstance(d["checks"], list)
        assert d["checks"]
        for item in d["checks"]:
            assert "name" in item
            assert "status" in item
            assert "detail" in item
            assert "fix_hint" in item

        text = report.to_text()
        assert isinstance(text, str) and text

        parsed = json.loads(report.to_json())
        assert parsed["healthy"] == d["healthy"] == report.healthy
        assert parsed["checks"][0]["name"] == d["checks"][0]["name"]


class TestMain:
    def test_main_exit_codes(self, report, monkeypatch):
        # 复用同一次自检结果，避免 main 内部再次触发耗时的浏览器/GPU 探测
        monkeypatch.setattr("urlparser.doctor.run_checks", lambda: report)
        rc = main(["--json"])
        assert rc in (0, 1)  # healthy -> 0，否则 1，且不抛异常

    def test_main_unknown_arg_raises_system_exit(self):
        # argparse 对未知参数触发 SystemExit（退出码 2）
        with pytest.raises(SystemExit):
            main(["unknown-arg"])
