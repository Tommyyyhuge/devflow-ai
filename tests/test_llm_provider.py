"""测试 LLM Provider 抽象基类。"""

import pytest

from devflow.llm.providers.base import ChatResponse, LLMProvider, TokenUsage


class FakeProvider(LLMProvider):
    """测试用的最小实现。"""

    def chat(self, messages, **kwargs):
        return ChatResponse(
            data={"choices": [{"message": {"content": "ok"}}]}
        )

    def chat_for_planning(self, messages):
        return self.chat(messages, thinking=True)

    def chat_for_execution(self, messages, tools):
        return self.chat(messages, tools=tools)

    def get_total_tokens(self):
        return 0


class TestLLMProvider:
    def test_abstract_class_cannot_instantiate(self):
        with pytest.raises(TypeError):
            LLMProvider()

    def test_fake_provider_chat(self):
        p = FakeProvider()
        r = p.chat([{"role": "user", "content": "hi"}])
        assert isinstance(r, ChatResponse)
        assert r.data["choices"][0]["message"]["content"] == "ok"

    def test_chat_response_default(self):
        r = ChatResponse()
        assert r.data == {}
        assert r.tokens.total_tokens == 0
        assert r.latency_ms == 0.0

    def test_token_usage(self):
        t = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        assert t.prompt_tokens == 10
        assert t.completion_tokens == 5
        assert t.total_tokens == 15
