"""安全 Shell 测试"""

import pytest

from devflow.tools.shell import ShellTool, RiskLevel, ShellPreview


class TestSafeShell:
    @pytest.fixture
    def shell(self):
        return ShellTool(auto_confirm=True)

    def test_preview_ls_command(self, shell):
        """测试 ls 命令预览"""
        preview = shell._preview("ls -la")
        assert preview.risk_level == RiskLevel.LOW
        assert "列出文件" in preview.predicted_effect

    def test_preview_rm_command(self, shell):
        """测试 rm 命令预览"""
        preview = shell._preview("rm -rf test_dir/")
        assert preview.risk_level == RiskLevel.HIGH

    def test_simulate_echo_command(self, shell):
        """测试模拟执行 echo"""
        sim = shell._simulate("echo hello")
        assert sim.success is True
        assert "hello" in sim.stdout

    def test_execute_low_risk(self, shell):
        """测试低风险命令直接执行"""
        result = shell.execute("echo test_output")
        assert "test_output" in result

    def test_risk_level_classification(self, shell):
        """测试风险等级分类"""
        assert shell._classify_risk("ls") == RiskLevel.LOW
        assert shell._classify_risk("mkdir test") == RiskLevel.MEDIUM
        assert shell._classify_risk("rm -rf /") == RiskLevel.HIGH
