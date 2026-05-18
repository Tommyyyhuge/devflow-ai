"""基础工具系统 — 文件操作 + Shell 执行

提供文件读写、目录列表、安全路径校验等基础能力。
"""

import json
import structlog
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

logger = structlog.get_logger(__name__)

# 安全工作目录
_SAFE_ROOT: Path | None = None


def set_safe_root(root: str | Path | None):
    """设置工作目录边界。传入 None 表示取消限制。"""
    global _SAFE_ROOT
    if root is None:
        _SAFE_ROOT = None
    else:
        _SAFE_ROOT = Path(root).resolve()


def _safe_path(path: str) -> Path:
    """验证路径在安全边界内，拒绝越界访问。

    安全检查：
    1. 路径解析后必须位于 _SAFE_ROOT 下（使用 relative_to 防止绕过）
    2. 符号链接指向也必须位于 _SAFE_ROOT 下
    3. 路径规范化（resolve 消除 .. 和符号链接）
    """
    if _SAFE_ROOT is None:
        return Path(path)

    # 规范化路径（消除 .. 和符号链接）
    resolved = (_SAFE_ROOT / path).resolve()

    # 检查 1：解析后的路径必须在安全根目录下
    try:
        resolved.relative_to(_SAFE_ROOT)
    except ValueError:
        logger.warning(
            "路径遍历攻击被阻止",
            attempted_path=path,
            resolved_path=str(resolved),
            safe_root=str(_SAFE_ROOT),
        )
        raise PermissionError(f"拒绝越界访问: {path}")

    # 检查 2：如果路径存在且是符号链接，检查真实目标
    if resolved.exists() and resolved.is_symlink():
        real_target = resolved.readlink()
        if not real_target.is_absolute():
            real_target = (_SAFE_ROOT / real_target).resolve()
        try:
            real_target.relative_to(_SAFE_ROOT)
        except ValueError:
            logger.warning(
                "符号链接攻击被阻止",
                attempted_path=path,
                symlink_target=str(real_target),
                safe_root=str(_SAFE_ROOT),
            )
            raise PermissionError(f"拒绝符号链接越界: {path}")

    return resolved


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool = False
    output: str | None = None
    error: str | None = None

    def is_critical_failure(self) -> bool:
        return not self.success and self.error is not None


class Tool(ABC):
    """工具基类"""
    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        pass

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ReadFileTool(Tool):
    name = "read_file"
    description = "读取文件内容（支持指定行范围）"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（相对项目根目录）"},
            "start_line": {"type": "integer", "description": "起始行号（从1开始，可选）"},
            "end_line": {"type": "integer", "description": "结束行号（含，可选）"},
        },
        "required": ["path"],
    }

    def execute(self, path: str, start_line: int = 0,
                end_line: int = 0, **kwargs) -> ToolResult:
        try:
            file_path = _safe_path(path)
            if not file_path.exists():
                return ToolResult(success=False, error=f"文件不存在: {path}")
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            if start_line > 0:
                lines = lines[start_line - 1:end_line if end_line > 0 else None]

            return ToolResult(success=True, output="\n".join(lines))
        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=f"读取失败: {e}")


class WriteFileTool(Tool):
    name = "write_file"
    description = "创建或覆写文件"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（相对项目根目录）"},
            "content": {"type": "string", "description": "文件内容"},
        },
        "required": ["path", "content"],
    }

    def execute(self, path: str, content: str, **kwargs) -> ToolResult:
        try:
            file_path = _safe_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return ToolResult(success=True, output=f"已写入 {path}")
        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=f"写入失败: {e}")


class ListDirTool(Tool):
    name = "list_dir"
    description = "列出目录内容"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目录路径（相对项目根目录，默认根目录）"},
        },
        "required": [],
    }

    def execute(self, path: str = ".", **kwargs) -> ToolResult:
        try:
            dir_path = _safe_path(path)
            if not dir_path.exists():
                return ToolResult(success=False, error=f"目录不存在: {path}")
            entries = []
            for entry in sorted(dir_path.iterdir()):
                marker = "/" if entry.is_dir() else ""
                entries.append(f"{entry.name}{marker}")
            return ToolResult(success=True, output="\n".join(entries))
        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=f"列表失败: {e}")


class ToolRegistry:
    """工具注册表 — 兼容 Agent 和 LLM 调用"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_schemas(self) -> list[dict]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def execute(self, name: str, arguments: str | dict) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, error=f"未知工具: {name}")

        if isinstance(arguments, str):
            try:
                args = json.loads(arguments)
            except json.JSONDecodeError:
                return ToolResult(success=False, error="参数解析失败")
        else:
            args = arguments

        return tool.execute(**args)


# create_tool_registry 已迁移到 devflow.tools.__init__.py
# 使用自动发现机制替代手动注册
