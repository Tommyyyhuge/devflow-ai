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


class RunShellTool(Tool):
    """Shell 命令执行——Week 1 本地执行，Week 3 迁移到 Docker 沙箱

    安全策略：白名单 + 黑名单双重防护
    1. 只允许白名单中的基础命令
    2. 拒绝 sudo、间接执行（sh -c 等）
    3. 黑名单作为兜底防护
    """
    name = "run_shell"
    description = (
        "执行 Shell 命令并返回输出。超时 30 秒。"
        "只允许安全命令：python, pytest, pip, git, ls, cat, grep, find, "
        "curl, mkdir, touch, echo, wc, head, tail, pwd"
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 Shell 命令"},
            "timeout": {"type": "integer", "description": "超时秒数（默认30）"},
        },
        "required": ["command"],
    }

    # 白名单：只允许这些基础命令
    ALLOWED_COMMANDS = frozenset([
        "python", "python3", "pytest", "pip", "pip3",
        "git", "ls", "cat", "grep", "find", "curl", "wget",
        "mkdir", "touch", "echo", "wc", "head", "tail",
        "pwd", "cd", "cp", "mv", "chmod", "diff", "sort",
        "uniq", "date", "which", "whoami", "env",
    ])

    # 黑名单：额外防护层（大小写不敏感）
    DANGEROUS_PATTERNS = [
        r"rm\s+-[rRf]+\s+/",       # rm -rf / 及其变体
        r"rm\s+-[rRf]+\s+~",       # rm -rf ~
        r"mkfs\.",                  # 格式化文件系统
        r"dd\s+if=",               # 磁盘写入
        r":\(\)\s*\{\s*:\|:&\s*\}",  # fork bomb
        r"shutdown",                # 关机
        r"reboot",                  # 重启
        r">\s*/dev/sd",             # 覆盖磁盘设备
        r"curl\s+.*\s*\|",          # curl | sh 管道执行
        r"wget\s+.*\s*\|",          # wget | sh 管道执行
    ]

    # 禁止的基础命令（无论参数如何）
    FORBIDDEN_BASE_COMMANDS = frozenset([
        "sudo", "su", "ssh", "telnet", "nc", "netcat",
        "bash", "sh", "zsh", "fish", "dash", "ksh",
        "eval", "exec", "source", ".",
    ])

    # 危险参数检查：命令名 → 禁止参数正则列表
    DANGEROUS_ARGUMENTS = {
        "python": [r"\s+-c\s+", r"\s+-m\s+subprocess", r"\s+-m\s+os"],
        "python3": [r"\s+-c\s+", r"\s+-m\s+subprocess", r"\s+-m\s+os"],
        "git": [r"\s+-c\s+\w+\.\w+\s*="],
    }

    def _extract_base_command(self, command: str) -> str:
        """提取命令的基础名称（处理 sudo、路径等）"""
        import shlex
        try:
            parts = shlex.split(command.strip())
        except ValueError:
            # 引号不匹配，简单分割
            parts = command.strip().split()

        if not parts:
            return ""

        # 处理 sudo
        if parts[0].lower() == "sudo":
            return "sudo"

        # 提取命令名（去掉路径）
        cmd = parts[0]
        return cmd.split("/")[-1].split("\\")[-1].lower()

    def _check_command_chain(self, command: str) -> tuple[bool, str]:
        """检查命令链是否安全

        Returns:
            (是否安全, 错误信息)
        """
        import re
        import shlex

        # 1. 检查黑名单（兜底防护）
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"拒绝执行危险命令（匹配模式: {pattern}）"

        # 2. 提取并检查基础命令
        base = self._extract_base_command(command)

        # 2a. 明确禁止的命令
        if base in self.FORBIDDEN_BASE_COMMANDS:
            return False, f"命令 '{base}' 在禁止列表中"

        # 2b. 检查是否在白名单中
        if base not in self.ALLOWED_COMMANDS:
            return False, (
                f"命令 '{base}' 不在白名单中。"
                f"允许: {', '.join(sorted(self.ALLOWED_COMMANDS))}"
            )

        # 2c. 检查命令的危险参数（如 python -c, git -c 等）
        dangerous_args = self.DANGEROUS_ARGUMENTS.get(base, [])
        for pattern in dangerous_args:
            if re.search(pattern, command, re.IGNORECASE):
                return False, (
                    f"命令 '{base}' 使用了危险参数（匹配: {pattern}）。"
                    f"禁止通过 {base} 执行任意代码。"
                )

        # 3. 检查管道和命令链
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()

        # 检查管道中的每个命令
        pipe_commands = " ".join(parts).split("|")
        for pipe_cmd in pipe_commands:
            pipe_base = self._extract_base_command(pipe_cmd.strip())
            if pipe_base in self.FORBIDDEN_BASE_COMMANDS:
                return False, f"管道中的命令 '{pipe_base}' 被禁止"

        # 4. 检查重定向到危险路径
        redirect_patterns = [
            r">\s*/(etc|usr|bin|sbin|lib|dev|proc|sys|root)/",
            r">\s*/\.",
        ]
        for pattern in redirect_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, "拒绝写入系统目录"

        return True, ""

    def execute(self, command: str, timeout: int = 30, **kwargs) -> ToolResult:
        # 空命令检查
        if not command or not command.strip():
            return ToolResult(success=False, error="命令不能为空")

        # 安全检查
        is_safe, error_msg = self._check_command_chain(command)
        if not is_safe:
            return ToolResult(success=False, error=error_msg)

        try:
            import subprocess
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=_safe_path("."),
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            return ToolResult(
                success=result.returncode == 0,
                output=output[:4000],  # 限制输出长度
                error=f"exit_code={result.returncode}" if result.returncode != 0 else None,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"命令超时 ({timeout}s)")
        except Exception as e:
            return ToolResult(success=False, error=f"执行失败: {e}")


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
