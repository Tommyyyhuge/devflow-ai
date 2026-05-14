"""LLM Provider 抽象基类。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


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
