"""Shell 执行工具 — 预测→模拟→执行三步安全流程

合并 RunShellTool + ShellTool：
- 继承 Tool 基类，LLM 可通过 function calling 调用
- 保留白名单/黑名单/危险参数的多层防护
- 保留风险分级和模拟执行能力
"""

import re
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum

from devflow.tools.base import Tool, ToolResult


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ShellPreview:
    command: str
    predicted_effect: str
    affected_files: list
    risk_level: RiskLevel


@dataclass
class ShellSimulation:
    success: bool
    stdout: str
    stderr: str
    is_safe: bool
    warnings: list


class ShellTool(Tool):
    """增强版 Shell 工具 — 多层安全防护 + 三步执行流程"""

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

    # === 白名单：只允许这些基础命令 ===
    ALLOWED_COMMANDS = frozenset([
        "python", "python3", "pytest", "pip", "pip3",
        "git", "ls", "cat", "grep", "find", "curl", "wget",
        "mkdir", "touch", "echo", "wc", "head", "tail",
        "pwd", "cd", "cp", "mv", "chmod", "diff", "sort",
        "uniq", "date", "which", "whoami", "env",
    ])

    # === 黑名单：额外防护层（大小写不敏感）===
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

    # === 禁止的基础命令（无论参数如何）===
    FORBIDDEN_BASE_COMMANDS = frozenset([
        "sudo", "su", "ssh", "telnet", "nc", "netcat",
        "bash", "sh", "zsh", "fish", "dash", "ksh",
        "eval", "exec", "source", ".",
    ])

    # === 危险参数检查：命令名 → 禁止参数正则列表 ===
    DANGEROUS_ARGUMENTS = {
        "python": [r"\s+-c\s+", r"\s+-m\s+subprocess", r"\s+-m\s+os"],
        "python3": [r"\s+-c\s+", r"\s+-m\s+subprocess", r"\s+-m\s+os"],
        "git": [r"\s+-c\s+\w+\.\w+\s*="],
    }

    # === 风险分级 ===
    RISK_RULES = {
        RiskLevel.LOW: ["ls", "cat", "grep", "find", "echo", "pwd", "which", "wc", "head", "tail", "date", "whoami", "env"],
        RiskLevel.MEDIUM: ["touch", "mkdir", "cp", "mv", "chmod", "sed", "diff", "sort", "uniq"],
        RiskLevel.HIGH: ["rm", "rmdir", "curl", "wget", "python", "python3", "pytest", "pip", "pip3", "git"],
    }

    def __init__(self, auto_confirm: bool = False):
        self.auto_confirm = auto_confirm

    # ---------- 静态安全检查（继承自 RunShellTool） ----------

    def _extract_base_command(self, command: str) -> str:
        """提取命令的基础名称（处理 sudo、路径等）"""
        try:
            parts = shlex.split(command.strip())
        except ValueError:
            parts = command.strip().split()

        if not parts:
            return ""

        if parts[0].lower() == "sudo":
            return "sudo"

        cmd = parts[0]
        return cmd.split("/")[-1].split("\\")[-1].lower()

    def _check_static_rules(self, command: str) -> tuple[bool, str]:
        """静态安全规则检查（白名单 + 黑名单 + 危险参数）

        Returns:
            (是否安全, 错误信息)
        """
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

        # 2c. 检查命令的危险参数
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

    # ---------- 三步执行流程（继承自 ShellTool） ----------

    def _classify_risk(self, command: str) -> RiskLevel:
        """分类命令风险等级"""
        cmd_base = self._extract_base_command(command)
        for level, commands in self.RISK_RULES.items():
            if cmd_base in commands:
                return level
        return RiskLevel.MEDIUM

    def _preview(self, command: str) -> ShellPreview:
        """预测命令影响"""
        risk = self._classify_risk(command)
        effect_map = {
            RiskLevel.LOW: "只读查询，无修改风险",
            RiskLevel.MEDIUM: "文件操作，可能修改或创建文件",
            RiskLevel.HIGH: "高风险操作，可能执行代码或修改数据",
        }
        return ShellPreview(
            command=command,
            predicted_effect=effect_map[risk],
            affected_files=[],
            risk_level=risk,
        )

    def _simulate(self, command: str) -> ShellSimulation:
        """在临时目录模拟执行"""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=tmpdir,
                    timeout=5,
                )
                warnings = []
                if result.returncode != 0:
                    warnings.append(f"模拟退出码: {result.returncode}")
                return ShellSimulation(
                    success=result.returncode == 0,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    is_safe=True,
                    warnings=warnings,
                )
        except subprocess.TimeoutExpired:
            return ShellSimulation(
                success=False, stdout="", stderr="",
                is_safe=False, warnings=["命令执行超时"],
            )
        except Exception as e:
            return ShellSimulation(
                success=False, stdout="", stderr="",
                is_safe=False, warnings=[f"模拟失败: {e}"],
            )

    def _exec_real(self, command: str, timeout: int = 30) -> ToolResult:
        """在真实环境执行"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
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

    # ---------- 公共接口 ----------

    def execute(self, command: str, timeout: int = 30, **kwargs) -> ToolResult:
        """执行 Shell 命令（多层安全 + 三步流程）"""
        # 空命令检查
        if not command or not command.strip():
            return ToolResult(success=False, error="命令不能为空")

        # Step 1: 静态安全检查（白名单/黑名单/危险参数）
        is_safe, error_msg = self._check_static_rules(command)
        if not is_safe:
            return ToolResult(success=False, error=error_msg)

        # Step 2: 风险预览
        preview = self._preview(command)

        # 高风险命令需要确认（除非 auto_confirm=True）
        if preview.risk_level == RiskLevel.HIGH and not self.auto_confirm:
            return ToolResult(
                success=False,
                error=(
                    f"⚠️ 高风险命令: {command}\n"
                    f"影响: {preview.predicted_effect}\n"
                    f"请在配置中启用 auto_confirm 以执行高风险命令"
                ),
            )

        # Step 3: 模拟执行
        simulation = self._simulate(command)
        if not simulation.is_safe:
            return ToolResult(
                success=False,
                error=f"模拟失败: {', '.join(simulation.warnings)}",
            )

        # Step 4: 真实执行
        return self._exec_real(command, timeout=timeout)
