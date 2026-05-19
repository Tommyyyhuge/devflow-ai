"""配置管理 — 环境变量 + .env 文件 + Web 端持久化

支持三种配置来源（优先级从高到低）：
1. Web 端保存的配置（~/.devflow/config.json，API Key 加密存储）
2. 环境变量 / .env 文件
3. 默认值
"""

import json
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from devflow.encryption import decrypt_value, encrypt_value, is_encrypted


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
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    max_tokens_per_request: int = 8000

    @field_validator("max_tokens_per_request")
    @classmethod
    def validate_max_tokens(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_tokens_per_request 必须大于 0")
        if v > 128000:
            raise ValueError("max_tokens_per_request 不能超过 128000")
        return v

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url 必须以 http:// 或 https:// 开头")
        return v


class AgentConfig(BaseSettings):
    """Agent 行为配置"""
    model_config = SettingsConfigDict(
        env_prefix="DEVFLOW_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    context_budget: int = 140_000
    code_context_budget: int = 60_000
    auto_confirm: bool = False
    ask_on_failure: bool = True

    @field_validator("context_budget", "code_context_budget")
    @classmethod
    def validate_budget_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("预算必须大于 0")
        if v > 1_000_000:
            raise ValueError("预算不能超过 1,000,000")
        return v


class BudgetConfig(BaseSettings):
    """预算上限配置"""
    model_config = SettingsConfigDict(
        env_prefix="DEVFLOW_BUDGET_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    weekly_budget: float = 20.0
    budget_per_5h: float = 3.5

    @field_validator("weekly_budget", "budget_per_5h")
    @classmethod
    def validate_budget_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("预算必须大于 0")
        if v > 10000:
            raise ValueError("预算不能超过 10000")
        return v


class RouterConfig(BaseSettings):
    """智能路由配置"""
    model_config = SettingsConfigDict(
        env_prefix="DEVFLOW_ROUTER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    enabled: bool = True
    strategy: str = "smart"  # "smart" | "cheapest" | "fastest"


class DevFlowConfig(BaseSettings):
    """DevFlow 总配置"""
    model_config = SettingsConfigDict(env_prefix="DEVFLOW_")
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    router: RouterConfig = Field(default_factory=RouterConfig)
    log_level: str = "INFO"


def _get_config_file() -> Path:
    """获取配置文件路径"""
    config_dir = Path.home() / ".devflow"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


def load_config() -> DevFlowConfig:
    """加载配置：Web 端配置 → 环境变量 → 默认值

    优先级：
    1. Web 端保存的配置（~/.devflow/config.json）
    2. 环境变量 / .env 文件
    3. 默认值
    """
    # 首先加载默认配置（会从环境变量/.env 读取）
    config = DevFlowConfig()

    # 然后加载 Web 端保存的配置（优先级更高）
    config_file = _get_config_file()
    if config_file.exists():
        try:
            saved_config = json.loads(config_file.read_text(encoding="utf-8"))

            # 更新 LLM 配置
            if "llm" in saved_config:
                llm_data = saved_config["llm"]
                if "api_key_encrypted" in llm_data:
                    # 解密 API Key
                    encrypted = llm_data.pop("api_key_encrypted")
                    if encrypted:
                        llm_data["api_key"] = SecretStr(decrypt_value(encrypted))
                # 只更新非空值
                for key, value in llm_data.items():
                    if value and hasattr(config.llm, key):
                        setattr(config.llm, key, value)

            # 更新 Agent 配置
            if "agent" in saved_config:
                for key, value in saved_config["agent"].items():
                    if hasattr(config.agent, key):
                        setattr(config.agent, key, value)

            # 更新 Budget 配置
            if "budget" in saved_config:
                for key, value in saved_config["budget"].items():
                    if hasattr(config.budget, key):
                        setattr(config.budget, key, value)

            # 更新 Router 配置
            if "router" in saved_config:
                for key, value in saved_config["router"].items():
                    if hasattr(config.router, key):
                        setattr(config.router, key, value)

            # 更新日志级别
            if "log_level" in saved_config:
                config.log_level = saved_config["log_level"]

        except Exception:
            # 加载失败时回退到默认配置
            pass

    return config


def save_config(config: DevFlowConfig) -> None:
    """保存配置到 Web 端配置文件

    API Key 会被加密存储。
    """
    config_file = _get_config_file()

    # 备份旧配置
    if config_file.exists():
        backup_file = config_file.with_suffix(".json.bak")
        backup_file.write_bytes(config_file.read_bytes())

    # 构建保存数据
    save_data = {
        "version": "1.0",
        "llm": {
            "name": config.llm.name,
            "api_key_encrypted": encrypt_value(config.llm.api_key.get_secret_value()),
            "base_url": config.llm.base_url,
            "model": config.llm.model,
            "max_tokens_per_request": config.llm.max_tokens_per_request,
        },
        "agent": {
            "context_budget": config.agent.context_budget,
            "code_context_budget": config.agent.code_context_budget,
            "auto_confirm": config.agent.auto_confirm,
            "ask_on_failure": config.agent.ask_on_failure,
        },
        "budget": {
            "weekly_budget": config.budget.weekly_budget,
            "budget_per_5h": config.budget.budget_per_5h,
        },
        "router": {
            "enabled": config.router.enabled,
            "strategy": config.router.strategy,
        },
        "log_level": config.log_level,
    }

    config_file.write_text(
        json.dumps(save_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def get_config_dict(config: DevFlowConfig, include_api_key: bool = False) -> dict:
    """将配置转换为字典（用于 API 响应）

    Args:
        config: 配置对象
        include_api_key: 是否包含 API Key（默认 False，安全考虑）
    """
    result = {
        "llm": {
            "name": config.llm.name,
            "base_url": config.llm.base_url,
            "model": config.llm.model,
            "max_tokens_per_request": config.llm.max_tokens_per_request,
        },
        "agent": {
            "context_budget": config.agent.context_budget,
            "code_context_budget": config.agent.code_context_budget,
            "auto_confirm": config.agent.auto_confirm,
            "ask_on_failure": config.agent.ask_on_failure,
        },
        "budget": {
            "weekly_budget": config.budget.weekly_budget,
            "budget_per_5h": config.budget.budget_per_5h,
        },
        "router": {
            "enabled": config.router.enabled,
            "strategy": config.router.strategy,
        },
        "log_level": config.log_level,
    }

    if include_api_key:
        result["llm"]["api_key"] = config.llm.api_key.get_secret_value()

    return result
