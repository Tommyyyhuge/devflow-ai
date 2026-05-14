"""日志模块测试"""

import logging
import tempfile
from pathlib import Path

import pytest

from devflow.logging.logger import AgentLogger


class TestAgentLogger:
    @pytest.fixture
    def logger(self, tmp_path):
        log_file = tmp_path / "test.log"
        return AgentLogger(name="test", log_file=str(log_file))

    def test_logger_creation(self, logger):
        """测试日志器创建"""
        assert logger.name == "test"
        assert logger.level == logging.INFO

    def test_log_info(self, logger, tmp_path):
        """测试记录 INFO 级别日志"""
        logger.info("测试信息")

        log_file = tmp_path / "test.log"
        content = log_file.read_text(encoding="utf-8")
        assert "测试信息" in content

    def test_log_error(self, logger, tmp_path):
        """测试记录 ERROR 级别日志"""
        logger.error("错误信息")

        log_file = tmp_path / "test.log"
        content = log_file.read_text(encoding="utf-8")
        assert "错误信息" in content

    def test_log_with_context(self, logger, tmp_path):
        """测试带上下文的日志"""
        logger.info("处理任务", task_id="123", model="deepseek-chat")

        log_file = tmp_path / "test.log"
        content = log_file.read_text(encoding="utf-8")
        assert "处理任务" in content
