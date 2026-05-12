"""Git 操作工具 — diff / log / status / commit"""


from devflow.tools.base import Tool, ToolResult, _safe_path


class GitDiffTool(Tool):
    """查看工作区改动"""
    name = "git_diff"
    description = "查看当前工作区的 git diff（未暂存和已暂存的改动）"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（可选，不传则显示全部）"},
        },
        "required": [],
    }

    def execute(self, path: str | None = None, **kwargs) -> ToolResult:
        try:
            import git

            repo_root = _safe_path(".")
            repo = git.Repo(repo_root, search_parent_directories=True)
            diff_text = repo.git.diff(path or "--", color=False)
            staged_text = repo.git.diff("--cached", color=False)

            output = diff_text
            if staged_text:
                output += f"\n--- 已暂存 ---\n{staged_text}"
            if not output.strip():
                output = "(无改动)"
            return ToolResult(success=True, output=output[:4000])
        except Exception as e:
            return ToolResult(success=False, error=f"git diff 失败: {e}")


class GitLogTool(Tool):
    """查看提交历史"""
    name = "git_log"
    description = "查看最近的 git 提交历史"
    parameters = {
        "type": "object",
        "properties": {
            "count": {"type": "integer", "description": "显示条数（默认10）"},
        },
        "required": [],
    }

    def execute(self, count: int = 10, **kwargs) -> ToolResult:
        try:
            import git

            repo_root = _safe_path(".")
            repo = git.Repo(repo_root, search_parent_directories=True)
            log = repo.git.log(f"-{count}", "--oneline", "--decorate")
            return ToolResult(success=True, output=log[:4000])
        except Exception as e:
            return ToolResult(success=False, error=f"git log 失败: {e}")


class GitStatusTool(Tool):
    """查看仓库状态"""
    name = "git_status"
    description = "查看 git 仓库的当前状态（修改/新增/删除的文件）"
    parameters = {"type": "object", "properties": {}, "required": []}

    def execute(self, **kwargs) -> ToolResult:
        try:
            import git

            repo_root = _safe_path(".")
            repo = git.Repo(repo_root, search_parent_directories=True)
            status = repo.git.status("--short")
            if not status.strip():
                status = "(干净的工作区)"
            return ToolResult(success=True, output=status[:4000])
        except Exception as e:
            return ToolResult(success=False, error=f"git status 失败: {e}")
