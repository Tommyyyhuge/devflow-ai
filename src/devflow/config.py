"""配置管理 — 环境变量 + .env 文件"""

import os

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_dotenv():
    """手动加载 .env 到环境变量（避免 pydantic-settings 嵌套配置的 env_file 冲突）"""
    env_path = ".env"
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key not in os.environ:  # 不覆盖已设置的环境变量
                    os.environ[key] = value


class LLMConfig(BaseSettings):
    """LLM 相关配置"""
    model_config = SettingsConfigDict(env_prefix="DEEPSEEK_")
    api_key: SecretStr = SecretStr("")
    model: str = "deepseek-v4-flash"
    max_tokens_per_request: int = 8000


class AgentConfig(BaseSettings):
    """Agent 行为配置"""
    model_config = SettingsConfigDict(env_prefix="DEVFLOW_AGENT_")
    context_budget: int = 140_000
    code_context_budget: int = 60_000
    auto_confirm: bool = False
    ask_on_failure: bool = True


class BudgetConfig(BaseSettings):
    """预算上限配置"""
    model_config = SettingsConfigDict(env_prefix="DEVFLOW_BUDGET_")
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
    """加载配置：.env 文件 → 环境变量 → 默认值"""
    _load_dotenv()
    return DevFlowConfig()
