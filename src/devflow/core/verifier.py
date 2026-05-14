"""Verifier — 结构化验证器

Week 3 升级：Verifier 从简单布尔值升级为结构化 Verdict + Diagnostic。
支撑 LSP 集成和 IDE 诊断。
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Diagnostic:
    """LSP 兼容的诊断信息（Week 3 新增）"""
    file: str
    line: int = 0
    column: int = 0
    severity: str = "error"   # "error" | "warning"
    message: str = ""
    source: str = "syntax"    # "syntax" | "type" | "behavior"


@dataclass
class Verdict:
    """结构化验证结果（Week 3 升级）"""
    passed: bool
    errors: list[Diagnostic] = field(default_factory=list)
    warnings: list[Diagnostic] = field(default_factory=list)
    needs_replan: bool = False
    summary: str = ""


class Verifier:
    """结构化验证器"""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else None

    def _resolve(self, file_path: str | Path) -> Path:
        """解析文件路径——相对路径基于 root 解析"""
        path = Path(file_path)
        if not path.is_absolute() and self.root:
            path = self.root / path
        return path

    def verify_syntax(self, file_path: str | Path) -> Verdict:
        """检查 Python 文件语法，返回结构化 Verdict"""
        path = self._resolve(file_path)
        verdict = Verdict(passed=True)

        if not path.exists():
            verdict.passed = False
            verdict.errors.append(Diagnostic(
                file=str(file_path), severity="error",
                message=f"文件不存在: {file_path}", source="behavior",
            ))
            return verdict

        if path.suffix != ".py":
            return verdict

        try:
            content = path.read_text(encoding="utf-8")
            ast.parse(content)
        except SyntaxError as e:
            verdict.passed = False
            verdict.errors.append(Diagnostic(
                file=str(file_path),
                line=e.lineno or 0,
                column=e.offset or 0,
                severity="error",
                message=e.msg,
                source="syntax",
            ))
        except OSError as e:
            verdict.warnings.append(Diagnostic(
                file=str(file_path), severity="warning",
                message=f"无法检查: {e}", source="behavior",
            ))
        except Exception:
            raise  # 严重异常（MemoryError 等）向上传播，不静默吞掉

        return verdict

    def verify_files(self, files: list[str]) -> Verdict:
        """批量检查文件"""
        verdict = Verdict(passed=True)
        for f in files:
            vr = self.verify_syntax(f)
            if not vr.passed:
                verdict.passed = False
                verdict.errors.extend(vr.errors)
            verdict.warnings.extend(vr.warnings)
        return verdict

    def verify_step(self, step, result) -> Verdict:
        """步骤执行后验证（Week 3 新增：整合执行结果判断）"""
        from devflow.core.planner import StepType

        verdict = Verdict(passed=True)

        # 语法检查
        for f in result.files_modified:
            vr = self.verify_syntax(f)
            if not vr.passed:
                verdict.passed = False
                verdict.errors.extend(vr.errors)

        # 行为检查（执行步骤非零退出）
        if step.type == StepType.VERIFY and result.exit_code != 0:
            verdict.passed = False
            verdict.errors.append(Diagnostic(
                file="<execution>", severity="error",
                message=f"exit_code={result.exit_code}",
                source="behavior",
            ))

        return verdict
