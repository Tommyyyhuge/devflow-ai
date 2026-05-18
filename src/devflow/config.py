"""配置管理 — 环境变量 + .env 文件"""

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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


def load_config() -> DevFlowConfig:
    """加载配置：.env 文件 → 环境变量 → 默认值（pydantic-settings 自动处理 .env）"""
    return DevFlowConfig()
