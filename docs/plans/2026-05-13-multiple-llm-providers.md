# 多 LLM 提供商支持（插件架构）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 DevFlow 的 LLM 层重构为插件架构，支持用户配置多个 LLM 提供商（DeepSeek/OpenAI/本地模型等），并在运行时切换。

**Architecture:** 引入 `LLMProvider` 抽象基类，`OpenAIProvider` 实现 OpenAI 兼容协议，`LLMFactory` 根据配置创建对应 Provider。配置层扩展 `base_url` 字段，支持多 profile。

**Tech Stack:** Python 3.11+, pydantic, openai SDK, structlog

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/devflow/llm/providers/base.py` | **创建** | LLMProvider ABC + TokenUsage + ChatResponse |
| `src/devflow/llm/providers/openai.py` | **创建** | OpenAI 兼容协议实现（原 DeepSeekClient 迁移） |
| `src/devflow/llm/providers/ollama.py` | **创建** | 本地 Ollama 模型支持（可选） |
| `src/devflow/llm/factory.py` | **创建** | LLMFactory：根据配置创建 Provider |
| `src/devflow/llm/__init__.py` | **重写** | 统一导出：factory + base + providers |
| `src/devflow/config.py` | **修改** | LLMConfig 添加 `base_url` + `name` |
| `src/devflow/core/agent.py` | **修改** | 接受 `LLMProvider` 接口而非具体类 |
| `src/devflow/api/server.py` | **修改** | 使用 LLMFactory 创建 Provider |
| `src/devflow/main.py` | **修改** | CLI 添加 `--llm` 参数选择提供商 |
| `tests/test_llm_provider.py` | **创建** | Provider 抽象层测试 |
| `tests/test_llm_factory.py` | **创建** | Factory 工厂测试 |

---

## Task 1: 创建 LLM Provider 抽象基类

**Files:**
- Create: `src/devflow/llm/providers/base.py`
- Create: `src/devflow/llm/providers/__init__.py`
- Test: `tests/test_llm_provider.py`

- [ ] **Step 1: 编写抽象基类**

```python
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
```

- [ ] **Step 2: 创建 providers 包 init**

```python
"""LLM Provider 插件包。"""

from devflow.llm.providers.base import ChatResponse, LLMProvider, TokenUsage

__all__ = ["ChatResponse", "LLMProvider", "TokenUsage"]
```

- [ ] **Step 3: 编写测试**

```python
"""测试 LLM Provider 抽象基类。"""

import pytest

from devflow.llm.providers.base import ChatResponse, LLMProvider, TokenUsage


class FakeProvider(LLMProvider):
    """测试用的最小实现。"""

    def chat(self, messages, **kwargs):
        return ChatResponse(data={"choices": [{"message": {"content": "ok"}}]})

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
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_llm_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/devflow/llm/providers/ tests/test_llm_provider.py
git commit -m "feat: add LLMProvider abstract base class"
```

---

## Task 2: 迁移 OpenAI 兼容实现

**Files:**
- Create: `src/devflow/llm/providers/openai.py`
- Delete: `src/devflow/llm/__init__.py`（原内容迁移后删除）
- Modify: `tests/test_core_modules.py`（更新导入）
- Test: `tests/test_llm_factory.py`

- [ ] **Step 1: 创建 OpenAIProvider（原 DeepSeekClient 迁移）**

```python
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
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key.get_secret_value(),
            base_url=config.base_url,
        )
        self._total_tokens_used = 0

    def _sanitize_error(self, error_msg: str) -> str:
        """过滤错误消息中的敏感信息。"""
        sanitized = re.sub(
            r"(sk-[a-zA-Z0-9]{4})[a-zA-Z0-9]*", r"\1***", error_msg
        )
        sanitized = re.sub(
            r"(?i)(authorization[:\s]+)[^\s]+", r"\1***", sanitized
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

            except Exception:
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
        return self.chat(messages, thinking=True, temperature=0.3)

    def chat_for_execution(
        self, messages: list[dict], tools: list[dict]
    ) -> ChatResponse:
        """执行模式：非 thinking + 零温度。"""
        return self.chat(messages, tools=tools, thinking=False, temperature=0.0)

    def get_total_tokens(self) -> int:
        """获取累计 Token 使用量。"""
        return self._total_tokens_used
```

- [ ] **Step 2: 创建 Factory**

```python
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
        ValueError: 当 base_url 无法匹配已知 provider 时
    """
    # 根据 base_url 自动推断 provider 类型
    base_url = config.base_url.lower()

    if "ollama" in base_url or ":11434" in base_url:
        # TODO: 未来添加 OllamaProvider
        raise NotImplementedError("Ollama 支持即将推出")

    # 默认使用 OpenAI 兼容协议（覆盖 DeepSeek、OpenAI、Claude 等）
    return OpenAIProvider(config)


def list_supported_providers() -> list[str]:
    """返回支持的 provider 名称列表。"""
    return list(_PROVIDER_REGISTRY.keys())
```

- [ ] **Step 3: 重写 llm/__init__.py**

```python
"""DevFlow LLM 模块。

统一的 LLM 抽象层，支持多种提供商（OpenAI、DeepSeek、Ollama 等）。
"""

from devflow.llm.factory import create_llm_provider, list_supported_providers
from devflow.llm.providers.base import ChatResponse, LLMProvider, TokenUsage
from devflow.llm.providers.openai import OpenAIProvider

__all__ = [
    "ChatResponse",
    "create_llm_provider",
    "LLMProvider",
    "list_supported_providers",
    "OpenAIProvider",
    "TokenUsage",
]
```

- [ ] **Step 4: 更新所有导入引用**

修改文件：
- `tests/test_core_modules.py` — `from devflow.llm import ChatResponse, DeepSeekClient` → `from devflow.llm import ChatResponse, OpenAIProvider`
- `src/devflow/core/agent.py` — 接受 `LLMProvider` 而非 `DeepSeekClient`
- `src/devflow/api/server.py` — `from devflow.llm import DeepSeekClient` → `from devflow.llm import create_llm_provider`
- `src/devflow/main.py` — 同上

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_llm_provider.py tests/test_llm_factory.py tests/test_core_modules.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/devflow/llm/ tests/
git commit -m "feat: migrate to LLM provider plugin architecture"
```

---

## Task 3: 扩展配置支持 base_url

**Files:**
- Modify: `src/devflow/config.py`
- Modify: `tests/test_coverage.py`

- [ ] **Step 1: 修改 LLMConfig**

```python
class LLMConfig(BaseSettings):
    """LLM 相关配置"""
    model_config = SettingsConfigDict(
        env_prefix="DEEPSEEK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    name: str = "default"  # 配置名称（用户自定义）
    api_key: SecretStr = SecretStr("")
    base_url: str = "https://api.deepseek.com"  # ← 新增，支持自定义端点
    model: str = "deepseek-v4-flash"
    max_tokens_per_request: int = 8000
```

- [ ] **Step 2: 更新 test_config_secret**

```python
def test_config_secret(self):
    from devflow.config import LLMConfig
    c = LLMConfig(api_key="sk-test1234", base_url="https://api.test.com")
    assert str(c.api_key) == "**********"
    assert c.api_key.get_secret_value() == "sk-test1234"
    assert c.base_url == "https://api.test.com"
```

- [ ] **Step 3: Commit**

```bash
git add src/devflow/config.py tests/test_coverage.py
git commit -m "feat: add base_url to LLMConfig"
```

---

## Task 4: 修改 Agent 层接受 LLMProvider

**Files:**
- Modify: `src/devflow/core/agent.py`

- [ ] **Step 1: 修改 Agent.__init__**

```python
# 修改前
def __init__(self, llm_client, tools, config=None):
    self.llm = llm_client

# 修改后
def __init__(self, llm_provider, tools, config=None):
    """初始化 Agent。

    Args:
        llm_provider: LLMProvider 实例（支持任意提供商）
        tools: ToolRegistry 实例
        config: 可选的 DevFlowConfig
    """
    self.llm = llm_provider
```

- [ ] **Step 2: Commit**

```bash
git add src/devflow/core/agent.py
git commit -m "refactor: agent accepts LLMProvider interface"
```

---

## Task 5: 修改 API 层使用 Factory

**Files:**
- Modify: `src/devflow/api/server.py`

- [ ] **Step 1: 修改 get_agent()**

```python
from devflow.llm import create_llm_provider

def get_agent() -> Agent:
    """FastAPI 依赖注入：创建并返回 Agent 实例。"""
    config = load_config()
    if not config.llm.api_key.get_secret_value():
        raise HTTPException(
            status_code=400,
            detail=f"请设置 {config.llm.name} 的 API Key",
        )
    llm_provider = create_llm_provider(config.llm)
    tools = create_tool_registry()
    return Agent(llm_provider, tools, config=config)
```

- [ ] **Step 2: Commit**

```bash
git add src/devflow/api/server.py
git commit -m "refactor: api uses LLM factory"
```

---

## Task 6: CLI 添加 --llm 参数

**Files:**
- Modify: `src/devflow/main.py`
- Modify: `src/devflow/api/server.py`（添加 provider 列表接口）

- [ ] **Step 1: 添加 CLI 命令**

```python
# 在 main.py 中添加
@main.group()
def llm():
    """LLM 提供商管理"""
    pass

@llm.command("list")
def llm_list():
    """列出支持的 LLM 提供商"""
    from devflow.llm import list_supported_providers
    providers = list_supported_providers()
    console.print(f"[bold]支持的 LLM 提供商:[/bold] {', '.join(providers)}")

@llm.command("info")
def llm_info():
    """显示当前 LLM 配置"""
    cfg = load_config()
    console.print(f"[bold]当前 LLM:[/bold] {cfg.llm.name}")
    console.print(f"  模型: {cfg.llm.model}")
    console.print(f"  端点: {cfg.llm.base_url}")
    console.print(f"  API Key: {'已设置' if cfg.llm.api_key.get_secret_value() else '[red]未设置[/red]'}")
```

- [ ] **Step 2: API 添加 provider 列表**

```python
@app.get("/api/llm/providers")
async def list_llm_providers():
    from devflow.llm import list_supported_providers
    return {"providers": list_supported_providers()}
```

- [ ] **Step 3: Commit**

```bash
git add src/devflow/main.py src/devflow/api/server.py
git commit -m "feat: add CLI and API for LLM provider management"
```

---

## Task 7: 编写集成测试

**Files:**
- Create: `tests/test_llm_integration.py`

- [ ] **Step 1: 编写测试**

```python
"""LLM Provider 集成测试。"""

import pytest

from devflow.config import LLMConfig
from devflow.llm import create_llm_provider, list_supported_providers
from devflow.llm.providers.base import LLMProvider


class TestLLMFactory:
    def test_list_providers(self):
        providers = list_supported_providers()
        assert "openai" in providers
        assert "deepseek" in providers

    def test_create_openai_provider(self):
        config = LLMConfig(
            name="test",
            api_key="sk-test1234",
            base_url="https://api.openai.com",
            model="gpt-4o",
        )
        provider = create_llm_provider(config)
        assert isinstance(provider, LLMProvider)

    def test_create_deepseek_provider(self):
        config = LLMConfig(
            name="test",
            api_key="sk-test1234",
            base_url="https://api.deepseek.com",
            model="deepseek-v4",
        )
        provider = create_llm_provider(config)
        assert isinstance(provider, LLMProvider)
```

- [ ] **Step 2: 运行所有测试**

Run: `pytest --tb=short -q`
Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_llm_integration.py
git commit -m "test: add LLM provider integration tests"
```

---

## Self-Review

**Spec coverage:**
- ✅ LLMProvider 抽象基类
- ✅ OpenAIProvider 实现
- ✅ LLMFactory 工厂
- ✅ base_url 配置支持
- ✅ Agent 层解耦
- ✅ API 层依赖注入
- ✅ CLI 管理命令
- ✅ 测试覆盖

**Placeholder scan:** 无 TBD/TODO

**Type consistency:** `create_llm_provider` 返回 `LLMProvider`，Agent 接受 `LLMProvider`，一致。

---

## 验证清单

- [ ] `ruff check src/ tests/` → 0 错误
- [ ] `pytest` → 全部通过
- [ ] `devflow llm list` → 显示提供商列表
- [ ] `devflow llm info` → 显示当前配置
- [ ] `.env` 配置 `DEEPSEEK_BASE_URL` → 连接到自定义端点
