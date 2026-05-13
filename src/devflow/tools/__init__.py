"""工具自动发现 — 扫描 tools 包自动注册所有 Tool 子类

Week 2 升级：告别手动注册，自动发现所有工具。
"""

import importlib
import pkgutil

from devflow.tools.base import Tool, ToolRegistry


def discover_tools() -> ToolRegistry:
    """自动发现并注册所有 Tool 子类"""
    registry = ToolRegistry()

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
                except Exception:
                    pass  # 忽略实例化失败的工具

    return registry


def create_tool_registry() -> ToolRegistry:
    """创建工具注册表（兼容旧接口）"""
    return discover_tools()
