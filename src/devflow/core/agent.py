"""Agent 主循环 — Plan → Execute → Verify

Week 1 简化版：基础 ReAct + Plan-Execute。
Week 3 升级：自适应轮次、分层重试、事件系统。
"""

from dataclasses import dataclass, field
from pathlib import Path

from devflow.core.executor import Executor, StepResult
from devflow.core.planner import Plan, Planner, Step
from devflow.core.verifier import Verdict, Verifier


@dataclass
class TaskResult:
    """任务执行结果"""
    success: bool
    task: str
    plan: Plan | None = None
    step_results: list[StepResult] = field(default_factory=list)
    verify_result: Verdict | None = None
    error: str = ""
    files_modified: list[str] = field(default_factory=list)


class Agent:
    """DevFlow Agent 主类"""

    def __init__(self, llm_client, tools, config=None):
        self.llm = llm_client
        self.tools = tools
        self.config = config
        self.planner = Planner(llm_client)
        self.executor = Executor(llm_client, tools)
        self.verifier = Verifier()

    async def run(self, task: str, repo_path: str | Path = ".") -> TaskResult:
        """执行完整的 AI 编程任务"""
        repo_path = Path(repo_path).resolve()

        # 1. 收集项目上下文（Week 2 升级：使用 RepoMap）
        from devflow.repo.repomap import RepoMapBuilder
        builder = RepoMapBuilder(repo_path)
        context = builder.get_context_for_task(task)
        # Fallback: 如果 RepoMap 无结果，用简化版
        if not context or len(builder.build().entries) == 0:
            from devflow.repo.scanner import ContextBuilder
            cb = ContextBuilder(repo_path)
            ctx = cb.build(task)
            context = self._format_context(ctx)

        # 2. 规划
        plan = self.planner.plan(task, context)

        # 3. 逐步执行
        step_results: list[StepResult] = []
        all_files_modified: list[str] = []

        for step in plan.steps:
            # Week 3: 使用分层重试替代基础执行
            result = await self.executor.execute_with_retry(step, context)
            step_results.append(result)

            if result.files_modified:
                all_files_modified.extend(result.files_modified)

            if not result.success and not self._should_continue(step, result):
                return TaskResult(
                    success=False,
                    task=task,
                    plan=plan,
                    step_results=step_results,
                    error=f"步骤 {step.index} 失败: {result.error}",
                    files_modified=all_files_modified,
                )

        # 4. 验证
        self.verifier.root = repo_path
        vr = self.verifier.verify_files(all_files_modified)

        return TaskResult(
            success=vr.passed and all(sr.success for sr in step_results),
            task=task,
            plan=plan,
            step_results=step_results,
            verify_result=vr,
            files_modified=all_files_modified,
        )

    @staticmethod
    def _format_context(ctx) -> str:
        """格式化项目上下文"""
        parts = [f"项目根目录: {ctx.root}"]
        parts.append(f"文件总数: {ctx.total_files}")
        if ctx.languages:
            langs = ", ".join(f"{k}({v})" for k, v in ctx.languages.items())
            parts.append(f"语言分布: {langs}")
        if ctx.relevant_files:
            parts.append("相关文件:")
            for f in ctx.relevant_files:
                parts.append(f"  {f.relative}")
        return "\n".join(parts)

    @staticmethod
    def _should_continue(step: Step, result: StepResult) -> bool:
        """判断步骤失败后是否继续执行"""
        from devflow.core.planner import StepType
        # READ 步骤失败可忽略（文件可能不存在）
        if step.type == StepType.READ:
            return True
        # VERIFY 失败也继续（最后统一报告）
        if step.type == StepType.VERIFY:
            return True
        return False
