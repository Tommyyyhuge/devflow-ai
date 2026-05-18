"""LLM Provider 抽象基类。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from devflow.llm.cost_tracker import CostTracker


@dataclass
class TokenUsage:
    """Token 使用情况"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatResponse:
    """LLM 响应 + 元数据"""
    data: dict = field(default_factory=dict)
    tokens: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: float = 0.0
    retry_count: int = 0


class LLMProvider(ABC):
    """LLM 提供商抽象基类。

    所有 LLM 提供商必须实现此接口。
    """

    def __init__(self) -> None:
        """初始化成本追踪器和事件总线。"""
        self.cost_tracker = CostTracker()
        self._event_bus = None

    @property
    def event_bus(self):
        """延迟初始化事件总线，避免循环导入"""
        if self._event_bus is None:
            from devflow.core.events import EventBus
            self._event_bus = EventBus()
        return self._event_bus

    def chat_with_cost(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        thinking: bool = False,
        temperature: float = 0.0,
    ) -> ChatResponse:
        """带成本追踪的聊天接口。"""
        from devflow.core.events import EventType

        # 触发开始事件
        self.event_bus.emit(EventType.LLM_CALL_START, {
            "model": self.config.model,
        })

        # 执行实际调用
        response = self.chat(messages, tools, thinking, temperature)

        # 计算成本
        tokens = response.tokens
        breakdown = self.cost_tracker.calculate(
            prompt_tokens=tokens.prompt_tokens,
            completion_tokens=tokens.completion_tokens,
            model_name=self.config.model,
        )

        # 触发结束事件
        self.event_bus.emit(EventType.LLM_CALL_END, {
            "model": self.config.model,
            "cost_breakdown": breakdown,
        })

        return response

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        thinking: bool = False,
        temperature: float = 0.0,
        max_retries: int = 3,
    ) -> ChatResponse:
        """统一的聊天接口。"""
        ...

    @abstractmethod
    def chat_for_planning(self, messages: list[dict]) -> ChatResponse:
        """规划模式。"""
        ...

    @abstractmethod
    def chat_for_execution(
        self, messages: list[dict], tools: list[dict]
    ) -> ChatResponse:
        """执行模式。"""
        ...

    @abstractmethod
    def get_total_tokens(self) -> int:
        """获取累计 Token 使用量。"""
        ...
