"""LLM Provider 工厂 — 根据配置创建对应 Provider。"""

from devflow.config import LLMConfig
from devflow.llm.providers.base import LLMProvider
from devflow.llm.providers.openai import OpenAIProvider

# 注册表：provider 名称 → 实现类
_PROVIDER_REGISTRY: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "deepseek": OpenAIProvider,  # DeepSeek 使用 OpenAI 兼容协议
}


def create_llm_provider(config: LLMConfig) -> LLMProvider:
    """根据配置创建 LLM Provider。

    Args:
        config: LLM 配置，包含 base_url, api_key, model 等

    Returns:
        对应的 LLMProvider 实例

    Raises:
        NotImplementedError: 当 base_url 无法匹配已知 provider 时
    """
    base_url = config.base_url.lower()

    if "ollama" in base_url or ":11434" in base_url:
        raise NotImplementedError("Ollama 支持即将推出")

    # 默认使用 OpenAI 兼容协议
    return OpenAIProvider(config)


def list_supported_providers() -> list[str]:
    """返回支持的 provider 名称列表。"""
    return list(_PROVIDER_REGISTRY.keys())
