"""Agent 主循环 — Plan → Execute → Verify

支持 Token 预算检查、对话历史持久化、结构化验证。
"""

from dataclasses import dataclass, field
from pathlib import Path

import structlog

from devflow.core.executor import Executor, StepResult
from devflow.core.planner import Plan, Planner, Step
from devflow.core.verifier import Verdict, Verifier
from devflow.history.store import ConversationStore
from devflow.llm.cost_tracker import BudgetExceededError, CostTracker
from devflow.llm.factory import create_llm_provider, create_smart_router

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
    total_cost_usd: float = 0.0


class Agent:
    """DevFlow Agent 主类"""

    def __init__(self, llm_client=None, tools=None, config=None, event_queue=None):
        self.tools = tools
        self.config = config
        self.event_queue = event_queue  # SSE 事件队列（可选）

        # 智能路由：根据配置自动选择 Provider 创建方式
        if config is not None and config.router.enabled:
            self.llm = create_smart_router(config.llm)
        else:
            self.llm = llm_client

        self.planner = Planner(self.llm)
        self.executor = Executor(self.llm, tools)
        self.verifier = Verifier()

        # 成本追踪器（如配置存在，启用预算检查）
        self.cost_tracker: CostTracker | None = None
        if config is not None:
            self.cost_tracker = CostTracker(
                weekly_limit=config.budget.weekly_budget,
                per_5h_limit=config.budget.budget_per_5h,
            )

    async def _emit(self, event_type: str, data: dict) -> None:
        """发射 SSE 事件到队列"""
        if self.event_queue is not None:
            await self.event_queue.put({"type": event_type, "data": data})

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

    async def run(self, task: str, repo_path: str | Path = ".",
                  conversation_id: str | None = None) -> TaskResult:
        """执行完整的 AI 编程任务

        Args:
            task: 任务描述
            repo_path: 项目路径
            conversation_id: 可选，关联到已有会话（用于恢复）
        """
        repo_path = Path(repo_path).resolve()
        logger.info("开始执行任务", task=task[:100], repo_path=str(repo_path))

        # --- 成本预算检查 ---
        if self.cost_tracker is not None:
            try:
                budget_status = self.cost_tracker.check_budget()
                logger.info(
                    "预算检查通过",
                    weekly=f"${budget_status.weekly_spent}/${budget_status.weekly_limit}",
                    per_5h=f"${budget_status.per_5h_spent}/${budget_status.per_5h_limit}",
                )
            except BudgetExceededError as e:
                logger.error("预算已耗尽", error=str(e))
                return TaskResult(
                    success=False,
                    task=task,
                    error=f"预算上限已触发: {e}",
                )

        # 初始化对话历史存储
        store = ConversationStore()
        conv_id = conversation_id

        # 如果没有提供会话 ID，创建新会话
        if not conv_id:
            project_name = repo_path.name
            conv = store.create_conversation(project_name, task)
            conv_id = conv.id
            logger.info("创建会话", conversation_id=conv_id)

        # 添加用户任务消息
        store.add_message(conv_id, "user", task)

        # --- Git 工作流：创建 feature 分支 ---
        import re
        branch_name = "feat/" + re.sub(r'[^\w\s-]', '', task.lower())[:30].replace(' ', '-')
        try:
            import git
            repo = git.Repo(repo_path, search_parent_directories=True)
            if not repo.is_dirty():
                # 只有工作区干净时才创建新分支
                new_branch = repo.create_head(branch_name)
                new_branch.checkout()
                logger.info("创建 feature 分支", branch=branch_name)
                store.add_message(conv_id, "system", f"创建分支: {branch_name}",
                                metadata={"type": "git_branch", "branch": branch_name})
        except Exception as e:
            logger.warning("创建分支失败", error=str(e))

        # 1. 收集项目上下文（RepoMap 主路径，scanner 兜底）
        from devflow.repo.repomap import RepoMapBuilder
        builder = RepoMapBuilder(repo_path)
        repomap = builder.build()

        if repomap.entries:
            # RepoMap 主路径：基于符号和关键词匹配
            context = builder.get_context_for_task(task)
            logger.info("使用 RepoMap 构建上下文",
                       files=len(repomap.entries),
                       symbols=repomap.total_symbols)
        else:
            # Fallback: 无代码文件可解析，用简化版 scanner
            from devflow.repo.scanner import ContextBuilder
            cb = ContextBuilder(repo_path)
            ctx = cb.build(task)
            context = self._format_context(ctx)
            logger.info("RepoMap 无可用条目，fallback 到 scanner",
                       files=ctx.total_files)

        # 更新状态为执行中
        store.update_status(conv_id, "running")

        # 2. 规划
        logger.info("开始规划任务")
        plan = self.planner.plan(task, context)
        logger.info("规划完成", step_count=len(plan.steps))

        # 添加规划消息
        plan_text = "\n".join([f"{s.index}. [{s.type.value}] {s.description}" for s in plan.steps])
        store.add_message(conv_id, "assistant", f"执行计划：\n{plan_text}",
                         metadata={"type": "plan", "step_count": len(plan.steps)})

        # 发射 plan 事件
        await self._emit("plan", {
            "steps": [{"index": s.index, "type": s.type.value, "description": s.description} for s in plan.steps]
        })

        # 3. 执行步骤（支持并行调度）
        step_results: list[StepResult] = []
        all_files_modified: list[str] = []
        total_tokens = 0
        shared_context = context  # 共享可追加上下文

        # 检查是否有依赖关系：无依赖时保持串行（向后兼容）
        has_dependencies = any(s.depends_on for s in plan.steps)

        if has_dependencies:
            # 批处理并行调度
            step_results, all_files_modified, total_tokens = await self._execute_parallel(
                plan, shared_context, store, conv_id
            )
        else:
            # 串行执行（向后兼容）
            step_results, all_files_modified, total_tokens = await self._execute_sequential(
                plan, shared_context, store, conv_id
            )

        # 4. 验证
        logger.info("开始验证")
        self.verifier.root = repo_path
        vr = self.verifier.verify_files(all_files_modified)

        success = vr.passed and all(sr.success for sr in step_results)

        # 更新会话状态为完成
        store.update_status(conv_id, "completed", success=success,
                          total_tokens=total_tokens,
                          files_modified=all_files_modified)

        # 添加完成消息
        if success:
            store.add_message(conv_id, "system", "任务完成", metadata={"type": "completed"})
        else:
            errors = [e.message for e in vr.errors] if vr else []
            store.add_message(conv_id, "system", f"验证失败: {', '.join(errors)}",
                            metadata={"type": "verification_failed", "errors": errors})

        # --- Git 工作流：自动提交 ---
        if all_files_modified:
            try:
                import git
                repo = git.Repo(repo_path, search_parent_directories=True)
                if repo.is_dirty(untracked_files=True):
                    repo.git.add(".")
                    commit_msg = f"{'feat' if success else 'wip'}: {task[:50]}"
                    repo.index.commit(commit_msg)
                    logger.info("自动提交代码", commit_msg=commit_msg)
                    store.add_message(conv_id, "system", f"提交代码: {commit_msg}",
                                    metadata={"type": "git_commit", "message": commit_msg})
            except Exception as e:
                logger.warning("自动提交失败", error=str(e))

        # 计算本次任务总成本
        total_cost = 0.0
        if self.cost_tracker is not None:
            session = self.cost_tracker.get_session_summary()
            total_cost = float(session.get("total_cost_usd", 0))

        await self._emit("complete", {
            "success": success,
            "total_steps": len(step_results),
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "files_modified": all_files_modified,
        })

        logger.info("任务完成",
                   success=success,
                   total_steps=len(step_results),
                   total_tokens=total_tokens,
                   total_cost=f"${total_cost:.5f}",
                   files_modified=len(all_files_modified))

        return TaskResult(
            success=success,
            task=task,
            plan=plan,
            step_results=step_results,
            verify_result=vr,
            files_modified=all_files_modified,
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
        )

    async def _execute_sequential(
        self, plan: Plan, context: str, store: ConversationStore, conv_id: str
    ) -> tuple[list[StepResult], list[str], int]:
        """串行执行步骤（向后兼容）"""
        step_results: list[StepResult] = []
        all_files_modified: list[str] = []
        total_tokens = 0
        shared_context = context

        for step in plan.steps:
            if not self._check_token_budget(total_tokens):
                error_msg = f"Token 预算已耗尽（已使用 {total_tokens} tokens）"
                store.update_status(conv_id, "failed", error=error_msg, total_tokens=total_tokens)
                return step_results, all_files_modified, total_tokens

            result = await self._execute_single_step(step, shared_context, store, conv_id)
            step_results.append(result)
            total_tokens += result.tokens_used

            if result.output:
                shared_context += f"\n\n步骤 {result.step.index} ({result.step.type.value}):\n{result.output[:500]}"

            if result.files_modified:
                all_files_modified.extend(result.files_modified)

            if not result.success and not self._should_continue(step, result):
                return step_results, all_files_modified, total_tokens

        return step_results, all_files_modified, total_tokens

    async def _execute_parallel(
        self, plan: Plan, context: str, store: ConversationStore, conv_id: str
    ) -> tuple[list[StepResult], list[str], int]:
        """批处理并行执行步骤"""
        import asyncio

        step_results: list[StepResult] = []
        all_files_modified: list[str] = []
        total_tokens = 0
        shared_context = context
        completed_indices: set[int] = set()
        remaining = list(plan.steps)

        while remaining:
            # 找出所有就绪步骤（依赖已全部完成）
            ready = [s for s in remaining if all(d in completed_indices for d in s.depends_on)]
            if not ready:
                raise ValueError("依赖关系有误，存在无法到达的步骤")

            logger.info("并行执行批次", step_indices=[s.index for s in ready])
            await self._emit("batch_start", {"steps": [s.index for s in ready]})

            # 并行执行就绪步骤
            batch_results = await asyncio.gather(*[
                self._execute_single_step(s, shared_context, store, conv_id)
                for s in ready
            ])

            # 收集结果
            for result in batch_results:
                completed_indices.add(result.step.index)
                step_results.append(result)
                total_tokens += result.tokens_used
                remaining = [s for s in remaining if s.index != result.step.index]

                if result.output:
                    shared_context += f"\n\n步骤 {result.step.index} ({result.step.type.value}):\n{result.output[:500]}"

                if result.files_modified:
                    all_files_modified.extend(result.files_modified)

            # 检查是否有失败且不应继续的步骤
            for result in batch_results:
                if not result.success and not self._should_continue(result.step, result):
                    return step_results, all_files_modified, total_tokens

        return step_results, all_files_modified, total_tokens

    async def _execute_single_step(
        self, step: Step, context: str, store: ConversationStore, conv_id: str
    ) -> StepResult:
        """执行单个步骤"""
        logger.info("执行步骤",
                   step_index=step.index,
                   type=step.type.value,
                   description=step.description[:50])

        await self._emit("step_start", {
            "index": step.index,
            "type": step.type.value,
            "description": step.description,
        })

        result = await self.executor.execute_with_retry(step, context)

        # 添加步骤执行消息
        msg = (
            f"步骤 {step.index}: {result.output[:200]}"
            if result.success
            else f"失败: {result.error}"
        )
        store.add_message(
            conv_id, "tool", msg,
            metadata={
                "type": "step_result",
                "step_index": step.index,
                "success": result.success,
                "tokens": result.tokens_used,
            }
        )

        await self._emit("step_complete", {
            "index": step.index,
            "type": step.type.value,
            "success": result.success,
            "output": (result.output or "")[:300],
            "error": result.error if not result.success else None,
        })

        if result.files_modified:
            for f in result.files_modified:
                await self._emit("file_modified", {"path": f})

        if not result.success:
            logger.error("步骤失败", step_index=step.index, error=result.error)
        else:
            logger.info("步骤完成", step_index=step.index, success=result.success)

        return result

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
