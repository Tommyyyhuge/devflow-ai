"""安全测试 — 路径遍历、命令注入等防护验证"""

import pytest
from pathlib import Path

from devflow.tools.base import _safe_path, set_safe_root
from devflow.tools.shell import ShellTool


class TestPathSecurity:
    """路径安全测试"""

    @pytest.fixture(autouse=True)
    def setup_safe_root(self, tmp_path):
        """每个测试前设置安全根目录"""
        set_safe_root(tmp_path)
        yield
        set_safe_root(None)

    def test_path_traversal_blocked(self, tmp_path):
        """测试路径遍历被阻止"""
        # Linux/Unix 风格路径遍历
        with pytest.raises(PermissionError, match="拒绝越界访问"):
            _safe_path("../../../etc/passwd")

        # Windows 风格路径遍历
        with pytest.raises(PermissionError, match="拒绝越界访问"):
            _safe_path("..\\..\\windows\\system32")

        # 多重遍历
        with pytest.raises(PermissionError, match="拒绝越界访问"):
            _safe_path("a/b/../../../../../etc/passwd")

    def test_safe_path_allowed(self, tmp_path):
        """测试正常路径允许访问"""
        # 相对路径
        path = _safe_path("subdir/file.txt")
        assert path == tmp_path / "subdir" / "file.txt"

        # 当前目录
        path = _safe_path("./file.txt")
        assert path == tmp_path / "file.txt"

        # 子目录
        path = _safe_path("a/b/c/d.txt")
        assert path == tmp_path / "a" / "b" / "c" / "d.txt"

    def test_absolute_path_blocked(self, tmp_path):
        """测试绝对路径被阻止（当设置了 SAFE_ROOT 时）"""
        with pytest.raises(PermissionError, match="拒绝越界访问"):
            _safe_path("/etc/passwd")

    def test_symlink_attack_blocked(self, tmp_path):
        """测试符号链接攻击被阻止"""
        # 创建指向外部的符号链接
        symlink = tmp_path / "link"
        try:
            symlink.symlink_to("/etc")
            with pytest.raises(PermissionError, match="拒绝符号链接越界"):
                _safe_path("link/passwd")
        except OSError:
            pytest.skip("当前系统不支持创建符号链接")

    def test_symlink_inside_allowed(self, tmp_path):
        """测试指向安全目录内部的符号链接允许访问"""
        # 创建子目录和文件
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        target = subdir / "target.txt"
        target.write_text("hello")

        # 创建指向内部的符号链接
        symlink = tmp_path / "link"
        try:
            symlink.symlink_to(subdir)
            path = _safe_path("link/target.txt")
            assert path == tmp_path / "link" / "target.txt"
        except OSError:
            pytest.skip("当前系统不支持创建符号链接")

    def test_null_bytes_blocked(self, tmp_path):
        """测试空字节注入被阻止"""
        with pytest.raises((PermissionError, ValueError)):
            _safe_path("file.txt\x00")


class TestShellSecurity:
    """Shell 安全测试"""

    @pytest.fixture
    def shell_tool(self):
        return ShellTool()

    def test_dangerous_command_blocked(self, shell_tool):
        """测试危险命令被阻止"""
        # rm -rf /
        is_safe, _ = shell_tool.validate_command("rm -rf /")
        assert not is_safe

        # mkfs
        is_safe, _ = shell_tool.validate_command("mkfs.ext4 /dev/sda")
        assert not is_safe

    def test_command_injection_blocked(self, shell_tool):
        """测试命令注入被阻止"""
        # Python 代码注入
        is_safe, _ = shell_tool.validate_command(
            'python -c "import os; os.system(\'rm -rf /\')"'
        )
        assert not is_safe

        # Git 配置注入
        is_safe, _ = shell_tool.validate_command('git -c core.editor=vim status')
        assert not is_safe

    def test_allowed_commands(self, shell_tool):
        """测试允许的命令"""
        # 基础命令
        is_safe, _ = shell_tool.validate_command("ls -la")
        assert is_safe

        # Git 命令
        is_safe, _ = shell_tool.validate_command("git status")
        assert is_safe

        # Python 测试
        is_safe, _ = shell_tool.validate_command("pytest tests/")
        assert is_safe

    def test_pipe_blocked(self, shell_tool):
        """测试管道操作被阻止"""
        is_safe, _ = shell_tool.validate_command("ls | cat")
        assert not is_safe

    def test_redirection_blocked(self, shell_tool):
        """测试重定向操作被阻止"""
        is_safe, _ = shell_tool.validate_command("echo hello > file.txt")
        assert not is_safe
