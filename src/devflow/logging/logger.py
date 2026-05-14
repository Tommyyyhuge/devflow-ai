"""结构化日志模块"""

import logging
import sys
from pathlib import Path

import structlog


class AgentLogger:
    """Agent 日志器"""

    def __init__(
        self,
        name: str = "devflow",
        level: int = logging.INFO,
        log_file: str | None = None,
        console: bool = True,
    ):
        self.name = name
        self.level = level

        # 配置 structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(ensure_ascii=False) if log_file else structlog.dev.ConsoleRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        self._logger = structlog.get_logger(name)
        self._logger.setLevel(level)

        # 配置文件输出
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(level)

            # 获取底层 logger 并添加 handler
            std_logger = logging.getLogger(name)
            std_logger.addHandler(file_handler)

    def debug(self, message: str, **kwargs):
        """记录 DEBUG 级别日志"""
        self._logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs):
        """记录 INFO 级别日志"""
        self._logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        """记录 WARNING 级别日志"""
        self._logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs):
        """记录 ERROR 级别日志"""
        self._logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs):
        """记录 CRITICAL 级别日志"""
        self._logger.critical(message, **kwargs)
