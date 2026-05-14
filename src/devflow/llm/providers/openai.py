"""OpenAI 兼容协议的 LLM Provider 实现。

支持 DeepSeek、OpenAI、Claude（通过兼容端点）、Ollama 等。
"""

import re
import time
from typing import Dict, List, Union

import structlog
from openai import APIError, OpenAI, RateLimitError

from devflow.config import LLMConfig
from devflow.llm.providers.base import ChatResponse, LLMProvider, TokenUsage

logger = structlog.get_logger()

# 类型别名
ChatCompletionMessage = Dict[str, str]
ChatCompletionChoice = Dict[str, ChatCompletionMessage]
OpenAIResponse = Dict[str, Union[List[ChatCompletionChoice], Dict]]


class OpenAIProvider(LLMProvider):
    """OpenAI 兼容协议的 LLM Provider。"""

    def __init__(self, config: LLMConfig):
        super().__init__()
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key.get_secret_value(),
            base_url=config.base_url,
        )
        self._total_tokens_used = 0

    def _sanitize_error(self, error_msg: str) -> str:
        """过滤错误消息中的敏感信息。"""
        sanitized = re.sub(
            r"(sk-[a-zA-Z0-9]{4})[a-zA-Z0-9]*",
            r"\1***",
            error_msg,
        )
        sanitized = re.sub(
            r"(?i)(authorization[:\s]+)[^\s]+",
            r"\1***",
            sanitized,
        )
        return sanitized

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        thinking: bool = False,
        temperature: float = 0.0,
        max_retries: int = 3,
    ) -> ChatResponse:
        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.config.max_tokens_per_request,
        }
        if tools:
            kwargs["tools"] = tools
        if thinking:
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}

        result = ChatResponse()

        for attempt in range(max_retries):
            start = time.perf_counter()
            try:
                response = self.client.chat.completions.create(**kwargs)
                latency = (time.perf_counter() - start) * 1000

                data = response.model_dump()
                result.data = data
                result.latency_ms = latency
                result.retry_count = attempt

                usage = data.get("usage", {})
                result.tokens = TokenUsage(
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                )
                self._total_tokens_used += result.tokens.total_tokens

                logger.info(
                    "LLM 调用成功",
                    latency_ms=round(latency, 2),
                    tokens=result.tokens.total_tokens,
                    retry_count=attempt,
                    model=self.config.model,
                )

                return result

            except RateLimitError as e:
                logger.warning(
                    "遇到速率限制",
                    attempt=attempt + 1,
                    error=self._sanitize_error(str(e)),
                )
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"等待 {wait_time}s 后重试...")
                    time.sleep(wait_time)
                else:
                    result.data = {
                        "error": f"速率限制，已重试 {max_retries} 次: {e}"
                    }
                    return result

            except APIError as e:
                logger.error(
                    "API 错误",
                    attempt=attempt + 1,
                    error=self._sanitize_error(str(e)),
                )
                if attempt == max_retries - 1:
                    result.data = {"error": f"API 错误: {e}"}
                    return result
                time.sleep(1)

            except Exception as e:
                logger.error(
                    "未知错误",
                    attempt=attempt + 1,
                    error=self._sanitize_error(str(e)),
                )
                result.data = {"error": f"调用失败: {e}"}
                return result

        return result

    def chat_for_planning(self, messages: list[dict]) -> ChatResponse:
        """规划模式：thinking + 稍高温度。"""
        return self.chat(
            messages,
            thinking=True,
            temperature=0.3,
        )

    def chat_for_execution(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> ChatResponse:
        """执行模式：非 thinking + 零温度。"""
        return self.chat(
            messages,
            tools=tools,
            thinking=False,
            temperature=0.0,
        )

    def get_total_tokens(self) -> int:
        """获取累计 Token 使用量。"""
        return self._total_tokens_used
