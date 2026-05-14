"""配置管理 — 环境变量 + .env 文件"""

from pydantic import Field, SecretStr
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


class DevFlowConfig(BaseSettings):
    """DevFlow 总配置"""
    model_config = SettingsConfigDict(env_prefix="DEVFLOW_")
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    log_level: str = "INFO"


def load_config() -> DevFlowConfig:
    """加载配置：.env 文件 → 环境变量 → 默认值（pydantic-settings 自动处理 .env）"""
    return DevFlowConfig()
