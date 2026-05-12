"""DeepSeek API 客户端封装 — OpenAI 兼容协议"""

from openai import OpenAI

from devflow.config import LLMConfig


class DeepSeekClient:
    """MVP v0.1 统一使用 V4 Flash + thinking 模式"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key.get_secret_value(),
            base_url="https://api.deepseek.com",
        )

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        thinking: bool = False,
        temperature: float = 0.0,
    ) -> dict:
        """统一的聊天接口，返回 OpenAI 兼容的响应字典"""
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

        response = self.client.chat.completions.create(**kwargs)
        return response.model_dump()

    def chat_for_planning(self, messages: list[dict]) -> dict:
        """规划模式：thinking + 稍高温度"""
        return self.chat(messages, thinking=True, temperature=0.3)

    def chat_for_execution(self, messages: list[dict], tools: list[dict]) -> dict:
        """执行模式：非 thinking + 零温度"""
        return self.chat(messages, tools=tools, thinking=False, temperature=0.0)
