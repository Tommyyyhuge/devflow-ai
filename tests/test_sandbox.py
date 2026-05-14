"""沙盒模块测试"""

import os
import tempfile
from pathlib import Path

import pytest

from devflow.sandbox.sandbox import Sandbox


class TestSandbox:
    def test_create_isolated_environment(self):
        """测试创建隔离环境"""
        sandbox = Sandbox()
        assert sandbox.temp_dir is not None
        assert Path(sandbox.temp_dir).exists()
    
    def test_copy_project_files(self):
        """测试复制项目文件到沙盒"""
        sandbox = Sandbox()
        sandbox.copy_project(".")
        
        # 检查是否复制了关键文件
        assert (Path(sandbox.temp_dir) / "pyproject.toml").exists()
    
    def test_execute_command_in_sandbox(self):
        """测试在沙盒中执行命令"""
        sandbox = Sandbox()
        sandbox.copy_project(".")
        
        result = sandbox.execute("echo hello")
        assert result["stdout"] == "hello\n"
        assert result["returncode"] == 0
    
    def test_get_file_changes(self):
        """测试获取文件变化"""
        sandbox = Sandbox()
        sandbox.copy_project(".")
        
        # 执行一个创建文件的命令
        sandbox.execute("type nul > new_file.txt")
        
        changes = sandbox.get_changes()
        assert "new_file.txt" in changes["added"]
    
    def test_cleanup(self):
        """测试清理临时目录"""
        sandbox = Sandbox()
        temp_dir = sandbox.temp_dir
        sandbox.cleanup()
        
        assert not Path(temp_dir).exists()
