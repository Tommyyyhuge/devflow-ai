"""LLM Provider 集成测试。

验证 Factory、多配置、Provider 切换等功能。
"""

import pytest

from devflow.config import LLMConfig
from devflow.llm import create_llm_provider, list_supported_providers
from devflow.llm.providers.base import LLMProvider
from devflow.llm.providers.openai import OpenAIProvider


class TestLLMFactory:
    """LLM Factory 集成测试"""

    def test_list_providers(self):
        """验证支持的提供商列表"""
        providers = list_supported_providers()
        assert "openai" in providers
        assert "deepseek" in providers

    def test_create_openai_provider(self):
        """创建 OpenAI 提供商"""
        config = LLMConfig(
            name="openai-test",
            api_key="sk-test1234",
            base_url="https://api.openai.com",
            model="gpt-4o",
        )
        provider = create_llm_provider(config)
        assert isinstance(provider, LLMProvider)
        assert isinstance(provider, OpenAIProvider)

    def test_create_deepseek_provider(self):
        """创建 DeepSeek 提供商（使用 OpenAI 兼容协议）"""
        config = LLMConfig(
            name="deepseek-test",
            api_key="sk-test1234",
            base_url="https://api.deepseek.com",
            model="deepseek-v4",
        )
        provider = create_llm_provider(config)
        assert isinstance(provider, LLMProvider)
        assert isinstance(provider, OpenAIProvider)

    def test_create_custom_endpoint(self):
        """创建自定义端点提供商"""
        config = LLMConfig(
            name="custom",
            api_key="sk-test1234",
            base_url="https://my-llm.company.com",
            model="custom-model",
        )
        provider = create_llm_provider(config)
        assert isinstance(provider, LLMProvider)

    def test_provider_base_url_from_config(self):
        """验证 Provider 正确读取配置的 base_url"""
        config = LLMConfig(
            api_key="sk-test1234",
            base_url="https://custom.api.com",
            model="test-model",
        )
        provider = OpenAIProvider(config)
        assert provider.config.base_url == "https://custom.api.com"

    def test_ollama_not_implemented(self):
        """Ollama 尚未实现，应抛出异常"""
        config = LLMConfig(
            api_key="",
            base_url="http://localhost:11434",
            model="llama2",
        )
        with pytest.raises(NotImplementedError):
            create_llm_provider(config)


class TestLLMConfig:
    """LLM 配置测试"""

    def test_default_base_url(self):
        """默认 base_url 为 DeepSeek"""
        c = LLMConfig()
        assert c.base_url == "https://api.deepseek.com"

    def test_custom_base_url(self):
        """自定义 base_url"""
        c = LLMConfig(base_url="https://api.openai.com")
        assert c.base_url == "https://api.openai.com"

    def test_config_name(self):
        """配置名称"""
        c = LLMConfig(name="公司OpenAI")
        assert c.name == "公司OpenAI"
