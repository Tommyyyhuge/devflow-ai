"""Shell 执行工具 — 预测→模拟→执行三步安全流程

Task 6: 为 ShellTool 增加安全三步骤，防止高风险命令误执行。
保留现有功能，向后兼容。
"""

from enum import Enum
from dataclasses import dataclass


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


class ShellTool:
    """增强版 Shell 工具，三步安全流程"""

    RISK_RULES = {
        RiskLevel.LOW: ["ls", "cat", "grep", "find", "echo", "pwd", "which"],
        RiskLevel.MEDIUM: ["touch", "mkdir", "cp", "mv", "chmod", "sed"],
        RiskLevel.HIGH: ["rm", "rmdir", "curl", "wget", "sudo", "dd", "mkfs"],
    }

    def __init__(self, auto_confirm: bool = False):
        self.auto_confirm = auto_confirm

    def execute(self, command: str) -> str:
        """执行命令（三步安全流程）"""
        preview = self._preview(command)

        if preview.risk_level == RiskLevel.HIGH and not self.auto_confirm:
            return self._format_confirmation(preview)

        simulation = self._simulate(command)
        if not simulation.is_safe:
            return f"❌ 模拟失败: {', '.join(simulation.warnings)}"

        return self._exec_real(command)

    def _preview(self, command: str) -> ShellPreview:
        """预测命令影响"""
        risk = self._classify_risk(command)
        effect_map = {
            RiskLevel.LOW: "列出文件，只读查询，无修改风险",
            RiskLevel.MEDIUM: "文件操作，可能修改或创建文件",
            RiskLevel.HIGH: "高风险操作，可能删除或破坏数据",
        }
        return ShellPreview(
            command=command,
            predicted_effect=effect_map[risk],
            affected_files=[],
            risk_level=risk,
        )

    def _classify_risk(self, command: str) -> RiskLevel:
        """分类命令风险等级"""
        cmd_base = command.split()[0] if command else ""
        for level, commands in self.RISK_RULES.items():
            if cmd_base in commands:
                return level
        return RiskLevel.MEDIUM

    def _simulate(self, command: str) -> ShellSimulation:
        """在临时目录模拟执行"""
        try:
            import tempfile
            import subprocess
            with tempfile.TemporaryDirectory() as tmpdir:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=tmpdir,
                    timeout=5,
                )
                return ShellSimulation(
                    success=result.returncode == 0,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    is_safe=True,
                    warnings=[],
                )
        except subprocess.TimeoutExpired:
            return ShellSimulation(
                success=False,
                stdout="",
                stderr="",
                is_safe=False,
                warnings=["命令执行超时"],
            )

    def _exec_real(self, command: str) -> str:
        """在真实环境执行"""
        import subprocess
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout or result.stderr

    def _format_confirmation(self, preview: ShellPreview) -> str:
        """格式化确认提示"""
        return (
            f"⚠️ 高风险命令: {preview.command}\n"
            f"影响: {preview.predicted_effect}\n"
            f"请确认是否执行 (yes/no): "
        )
