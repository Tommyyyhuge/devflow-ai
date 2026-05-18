"""工具自动发现 — 扫描 tools 包自动注册所有 Tool 子类

遍历包内模块，自动实例化并注册所有 Tool 子类。
"""

import importlib
import pkgutil

import structlog

from devflow.tools.base import Tool, ToolRegistry

logger = structlog.get_logger()


def discover_tools() -> ToolRegistry:
    """自动发现并注册所有 Tool 子类"""
    registry = ToolRegistry()
    failed_tools: list[dict] = []

    # 扫描当前包的所有模块
    package = importlib.import_module("devflow.tools")
    for _, module_name, _ in pkgutil.iter_modules(
        package.__path__, package.__name__ + "."
    ):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue

        # 查找模块中的所有 Tool 子类
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, Tool)
                and attr is not Tool
                and not getattr(attr, "__abstractmethods__", None)
            ):
                try:
                    tool = attr()
                    registry.register(tool)
                except Exception as e:
                    failed_tools.append({"tool": attr_name, "module": module_name, "error": str(e)})
                    logger.warning(
                        "工具注册失败",
                        tool=attr_name,
                        module=module_name,
                        error=str(e),
                    )

    if failed_tools:
        logger.warning("部分工具加载失败", count=len(failed_tools), failed=failed_tools)

    return registry


def create_tool_registry() -> ToolRegistry:
    """创建工具注册表（兼容旧接口）"""
    return discover_tools()
