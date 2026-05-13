"""Git 操作工具 — diff / log / status / commit / branch"""


from devflow.tools.base import Tool, ToolResult, _safe_path


class GitBranchTool(Tool):
    """创建或切换 Git 分支"""
    name = "git_branch"
    description = "创建新分支或切换到已有分支"
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "分支名称"},
            "create": {"type": "boolean", "description": "是否创建新分支（默认 true）"},
        },
        "required": ["name"],
    }

    def execute(self, name: str, create: bool = True, **kwargs) -> ToolResult:
        try:
            import git

            repo_root = _safe_path(".")
            repo = git.Repo(repo_root, search_parent_directories=True)

            if create:
                # 创建并切换到新分支
                new_branch = repo.create_head(name)
                new_branch.checkout()
                return ToolResult(success=True, output=f"创建并切换到分支: {name}")
            else:
                # 切换到已有分支
                repo.git.checkout(name)
                return ToolResult(success=True, output=f"切换到分支: {name}")
        except Exception as e:
            return ToolResult(success=False, error=f"分支操作失败: {e}")


class GitCommitTool(Tool):
    """提交代码改动"""
    name = "git_commit"
    description = "将所有改动提交到当前分支（自动 add + commit）"
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "提交信息"},
        },
        "required": ["message"],
    }

    def execute(self, message: str, **kwargs) -> ToolResult:
        try:
            import git

            repo_root = _safe_path(".")
            repo = git.Repo(repo_root, search_parent_directories=True)

            # 检查是否有改动
            if repo.is_dirty(untracked_files=True):
                # 添加所有改动
                repo.git.add(".")
                # 提交
                repo.index.commit(message)
                return ToolResult(success=True, output=f"已提交: {message}")
            else:
                return ToolResult(success=False, error="没有可提交的改动")
        except Exception as e:
            return ToolResult(success=False, error=f"提交失败: {e}")


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
