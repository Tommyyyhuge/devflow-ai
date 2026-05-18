"""文件编辑工具 — 精确字符串替换 + Shell 执行 + 代码搜索"""

from devflow.tools.base import Tool, ToolResult, _safe_path


class EditFileTool(Tool):
    """精确字符串替换——old_string 必须在文件中有且仅有一处匹配"""
    name = "edit_file"
    description = "精确替换文件中的字符串。old_string 必须在文件中有且仅有一处匹配。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（相对项目根目录）"},
            "old_string": {"type": "string", "description": "要替换的原字符串"},
            "new_string": {"type": "string", "description": "替换后的新字符串"},
        },
        "required": ["path", "old_string", "new_string"],
    }

    def execute(self, path: str, old_string: str,
                new_string: str, **kwargs) -> ToolResult:
        try:
            # 防御：空字符串会导致 count("") 返回文件长度+1
            if not old_string:
                return ToolResult(success=False, error="old_string 不能为空")

            file_path = _safe_path(path)
            if not file_path.exists():
                return ToolResult(success=False, error=f"文件不存在: {path}")

            content = file_path.read_text(encoding="utf-8")
            count = content.count(old_string)

            if count == 0:
                # 提供诊断信息帮助 Agent 调试
                preview = old_string[:80].replace("\n", "\\n")
                return ToolResult(
                    success=False,
                    error=f"未找到匹配文本（前80字符）: {preview}"
                )
            if count > 1:
                return ToolResult(
                    success=False,
                    error=f"找到 {count} 处匹配，old_string 需要更具体的上下文"
                )

            new_content = content.replace(old_string, new_string, 1)
            file_path.write_text(new_content, encoding="utf-8")
            return ToolResult(success=True, output=f"已修改 {path}")
        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=f"编辑失败: {e}")


class SearchCodeTool(Tool):
    """代码搜索——封装 GrepSearch"""
    name = "search_code"
    description = "在项目文件中搜索文本模式（正则表达式）"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "搜索模式（正则表达式）"},
            "include": {"type": "string", "description": "文件过滤（如 *.py），默认所有文本文件"},
        },
        "required": ["pattern"],
    }

    def execute(self, pattern: str, include: str = "*", **kwargs) -> ToolResult:
        try:
            from devflow.repo.scanner import GrepSearch

            gs = GrepSearch(_safe_path("."))
            matches = gs.search(pattern, include=include, max_results=30)

            if not matches:
                return ToolResult(success=True, output=f"未找到匹配: {pattern}")

            lines = []
            for m in matches:
                lines.append(f"{m.file}:{m.line}: {m.content[:120]}")
            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, error=f"搜索失败: {e}")
