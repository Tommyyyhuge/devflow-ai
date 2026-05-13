"""单步 ReAct 执行器

Week 1 简化版：基础 ReAct 循环（Think → Act → Observe）。
Week 2 升级：日志记录、Token 跟踪、更好的错误处理。
"""

from dataclasses import dataclass, field

import structlog

from devflow.core.planner import Step, StepType

logger = structlog.get_logger()


@dataclass
class StepResult:
    """步骤执行结果"""
    success: bool
    step: Step
    output: str = ""
    error: str = ""
    files_modified: list[str] = field(default_factory=list)
    exit_code: int = 0
    tokens_used: int = 0


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: str = ""
    error: str = ""


class Executor:
    """基础 ReAct 执行器"""

    def __init__(self, llm_client, tools):
        self.llm = llm_client
        self.tools = tools

    async def execute(self, step: Step, context: str = "") -> StepResult:
        """执行单个步骤（ReAct 循环）"""
        max_rounds = self._rounds_for_type(step.type)
        messages = self._build_initial_messages(step, context)
        files_modified: list[str] = []
        total_tokens = 0

        logger.info("开始执行步骤", step_index=step.index, type=step.type.value,
                    description=step.description[:50])

        for round_num in range(max_rounds):
            chat_response = self.llm.chat_for_execution(
                messages,
                self.tools.get_schemas(),
            )

            # 记录 Token 使用
            total_tokens += chat_response.tokens.total_tokens

            # API 错误处理
            if "error" in chat_response.data:
                error_msg = chat_response.data["error"]
                logger.error("LLM API 错误", error=error_msg,
                            step_index=step.index)
                return StepResult(
                    success=False,
                    step=step,
                    error=f"API 错误: {error_msg}",
                    files_modified=files_modified,
                    tokens_used=total_tokens,
                )

            choice = chat_response.data.get("choices", [{}])[0]
            msg = choice.get("message", {})

            # API 错误处理（认证失败、速率限制等）
            if not msg and "error" in chat_response.data:
                error_msg = chat_response.data["error"]
                logger.error("LLM 返回错误", error=error_msg)
                return StepResult(
                    success=False,
                    step=step,
                    error=f"API 错误: {error_msg}",
                    files_modified=files_modified,
                    tokens_used=total_tokens,
                )

            # 检查是否是最终回答（无 tool_calls）
            if not msg.get("tool_calls"):
                output = msg.get("content", "")
                logger.info("步骤完成（直接回答）",
                          step_index=step.index,
                          output_length=len(output),
                          tokens_used=total_tokens)
                return StepResult(
                    success=True,
                    step=step,
                    output=output,
                    files_modified=files_modified,
                    tokens_used=total_tokens,
                )

            # 执行工具调用
            messages.append(msg)
            tool_calls = msg.get("tool_calls", [])
            logger.debug("执行工具调用",
                        step_index=step.index,
                        round=round_num + 1,
                        tools=[tc["function"]["name"] for tc in tool_calls])

            for tc in tool_calls:
                func = tc["function"]
                tool_result = self._execute_tool(
                    func["name"],
                    func.get("arguments", "{}"),
                )

                # 记录修改的文件
                if func["name"] in ("write_file", "edit_file"):
                    import json
                    try:
                        args = json.loads(func["arguments"])
                        if "path" in args:
                            files_modified.append(args["path"])
                            logger.info("文件被修改", path=args["path"])
                    except json.JSONDecodeError:
                        pass

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result.output or tool_result.error,
                })

            # 卡住检测：连续3次相同工具调用则提前终止
            if self.is_stuck(messages):
                logger.warning("检测到卡住，提前终止",
                             step_index=step.index,
                             round=round_num + 1)
                return StepResult(
                    success=False,
                    step=step,
                    error="检测到重复操作循环（卡住），已提前终止",
                    files_modified=files_modified,
                    tokens_used=total_tokens,
                )

        logger.warning("超过最大轮次",
                      step_index=step.index,
                      max_rounds=max_rounds)
        return StepResult(
            success=False,
            step=step,
            error=f"超过最大轮次 {max_rounds}",
            files_modified=files_modified,
            tokens_used=total_tokens,
        )

    def _execute_tool(self, name: str, arguments: str) -> ToolResult:
        """执行单个工具调用"""
        import json
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError:
            return ToolResult(success=False, error=f"参数解析失败: {arguments}")

        try:
            tool = self.tools.get(name)
            if not tool:
                return ToolResult(success=False, error=f"未知工具: {name}")
            result = tool.execute(**args)
            return ToolResult(
                success=result.success,
                output=result.output or "",
                error=result.error or "",
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _build_initial_messages(
        self, step: Step, context: str
    ) -> list[dict]:
        """构建 ReAct 循环的初始消息"""
        return [
            {
                "role": "system",
                "content": f"""你是一个编程助手。使用提供的工具完成任务。

## 上下文
{context if context else "(无上下文)"}

## 当前步骤
{step.description}

使用工具完成任务后，输出结果。不需要工具时直接回复。""",
            },
        ]

    @staticmethod
    def _rounds_for_type(step_type: StepType) -> int:
        """自适应轮次上限（Week 3 升级）"""
        return {
            StepType.READ: 3,      # 读文件/搜索（简单）
            StepType.WRITE: 10,    # 创建/编辑（中等）
            StepType.VERIFY: 15,   # 验证+调试（复杂）
        }.get(step_type, 8)

    async def execute_with_retry(self, step: Step, context: str = "") -> StepResult:
        """策略分层重试（Week 3 新增）：
        第1次：相同方法重试（处理临时错误）
        第2次：换思路（修改提示词）
        第3次：降级方案（跳过/标记失败）
        """
        for attempt in range(1, 4):
            result = await self.execute(step, context)
            if result.success:
                return result

            if attempt == 3:
                return StepResult(
                    success=False,
                    step=step,
                    error=f"3次重试全部失败: {result.error}",
                    files_modified=result.files_modified,
                )

            # 第2次：换思路
            if attempt == 2:
                context = f"{context}\n\n前一次尝试失败({result.error})。请换一种实现思路。"

        return StepResult(success=False, step=step, error="重试耗尽")

    @staticmethod
    def is_stuck(messages: list[dict], threshold: int = 3) -> bool:
        """卡住检测：最近 N 次 tool_call 是否完全重复"""
        recent_calls = [
            m for m in messages[-threshold * 2:]
            if m.get("role") == "assistant" and m.get("tool_calls")
        ]
        if len(recent_calls) < threshold:
            return False
        names = [
            [tc["function"]["name"] for tc in m.get("tool_calls", [])]
            for m in recent_calls
        ]
        return all(n == names[0] for n in names)
