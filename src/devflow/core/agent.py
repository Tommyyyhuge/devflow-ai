"""Agent 主循环 — Plan → Execute → Verify

Week 1 简化版：基础 ReAct + Plan-Execute。
Week 2 升级：Token 预算、日志记录、更好的错误处理。
"""

from dataclasses import dataclass, field
from pathlib import Path

import structlog

from devflow.core.executor import Executor, StepResult
from devflow.core.planner import Plan, Planner, Step
from devflow.core.verifier import Verdict, Verifier

logger = structlog.get_logger()


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
    total_tokens: int = 0


class Agent:
    """DevFlow Agent 主类"""

    def __init__(self, llm_client, tools, config=None):
        self.llm = llm_client
        self.tools = tools
        self.config = config
        self.planner = Planner(llm_client)
        self.executor = Executor(llm_client, tools)
        self.verifier = Verifier()

    def _check_token_budget(self, current: int) -> bool:
        """检查是否超出 Token 预算"""
        if not self.config:
            return True
        budget = self.config.agent.context_budget
        if current >= budget:
            logger.warning("Token 预算即将耗尽",
                         current=current, budget=budget)
            return False
        # 80% 预警
        if current >= budget * 0.8:
            logger.warning("Token 使用超过 80%",
                         current=current, budget=budget)
        return True

    async def run(self, task: str, repo_path: str | Path = ".") -> TaskResult:
        """执行完整的 AI 编程任务"""
        repo_path = Path(repo_path).resolve()
        logger.info("开始执行任务", task=task[:100], repo_path=str(repo_path))

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
        logger.info("开始规划任务")
        plan = self.planner.plan(task, context)
        logger.info("规划完成", step_count=len(plan.steps))

        # 3. 逐步执行
        step_results: list[StepResult] = []
        all_files_modified: list[str] = []
        total_tokens = 0

        for step in plan.steps:
            # Token 预算检查
            if not self._check_token_budget(total_tokens):
                return TaskResult(
                    success=False,
                    task=task,
                    plan=plan,
                    step_results=step_results,
                    error=f"Token 预算已耗尽（已使用 {total_tokens} tokens）",
                    files_modified=all_files_modified,
                    total_tokens=total_tokens,
                )

            logger.info("执行步骤",
                       step_index=step.index,
                       type=step.type.value,
                       description=step.description[:50])

            # Week 3: 使用分层重试替代基础执行
            result = await self.executor.execute_with_retry(step, context)
            step_results.append(result)
            total_tokens += result.tokens_used

            if result.files_modified:
                all_files_modified.extend(result.files_modified)
                logger.info("步骤修改了文件",
                           step_index=step.index,
                           files=result.files_modified)

            if not result.success and not self._should_continue(step, result):
                logger.error("步骤失败，终止任务",
                           step_index=step.index,
                           error=result.error)
                return TaskResult(
                    success=False,
                    task=task,
                    plan=plan,
                    step_results=step_results,
                    error=f"步骤 {step.index} 失败: {result.error}",
                    files_modified=all_files_modified,
                    total_tokens=total_tokens,
                )

            logger.info("步骤完成",
                       step_index=step.index,
                       success=result.success,
                       tokens=result.tokens_used)

        # 4. 验证
        logger.info("开始验证")
        self.verifier.root = repo_path
        vr = self.verifier.verify_files(all_files_modified)

        success = vr.passed and all(sr.success for sr in step_results)
        logger.info("任务完成",
                   success=success,
                   total_steps=len(step_results),
                   total_tokens=total_tokens,
                   files_modified=len(all_files_modified))

        return TaskResult(
            success=success,
            task=task,
            plan=plan,
            step_results=step_results,
            verify_result=vr,
            files_modified=all_files_modified,
            total_tokens=total_tokens,
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
