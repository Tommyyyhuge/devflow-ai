"""智能模型路由——根据任务复杂度自动选择最优模型"""

from enum import Enum, auto

from devflow.config import LLMConfig
from devflow.llm.providers.base import ChatResponse, LLMProvider
from devflow.llm.providers.openai import OpenAIProvider


class TaskComplexity(Enum):
    """任务复杂度分级"""
    SIMPLE = auto()      # 格式化、重命名、补全
    MEDIUM = auto()      # 函数实现、单元测试
    COMPLEX = auto()     # 架构设计、Bug 排查


class SmartRouter:
    """智能模型路由器"""
    
    # 复杂度关键词映射
    SIMPLE_KEYWORDS = ["格式化", "重命名", "补全", "缩进", "排序", "清理", "空格"]
    COMPLEX_KEYWORDS = ["架构", "设计", "重构", "排查", "优化", "迁移", "性能"]
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._providers: dict[TaskComplexity, LLMProvider] = {}
    
    def _get_provider(self, complexity: TaskComplexity) -> LLMProvider:
        """懒加载 Provider"""
        if complexity not in self._providers:
            model_map = {
                TaskComplexity.SIMPLE: "deepseek-chat",
                TaskComplexity.MEDIUM: "deepseek-coder",
                TaskComplexity.COMPLEX: "gpt-4o",
            }
            model = model_map[complexity]
            config = LLMConfig(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                model=model,
            )
            self._providers[complexity] = OpenAIProvider(config)
        return self._providers[complexity]
    
    def route(
        self,
        prompt: str,
        context: dict | None = None,
    ) -> LLMProvider:
        """根据任务特征选择最优 Provider"""
        complexity = self._analyze_complexity(prompt)
        return self._get_provider(complexity)
    
    def _analyze_complexity(self, prompt: str) -> TaskComplexity:
        """启发式复杂度分析"""
        prompt_lower = prompt.lower()
        
        # 规则 1：关键词匹配
        for keyword in self.COMPLEX_KEYWORDS:
            if keyword in prompt_lower:
                return TaskComplexity.COMPLEX
        
        for keyword in self.SIMPLE_KEYWORDS:
            if keyword in prompt_lower:
                return TaskComplexity.SIMPLE
        
        # 规则 2：Prompt 长度（超过 200 字视为复杂）
        if len(prompt) > 200:
            return TaskComplexity.COMPLEX
        
        # 规则 3：默认中等复杂度
        return TaskComplexity.MEDIUM

    def chat_for_planning(self, messages: list[dict]) -> ChatResponse:
        """规划模式 — 自动路由到合适的 Provider。

        Args:
            messages: 对话消息列表

        Returns:
            ChatResponse: LLM 响应
        """
        prompt = self._extract_prompt(messages)
        provider = self.route(prompt)
        return provider.chat_for_planning(messages)

    def chat_for_execution(
        self, messages: list[dict], tools: list[dict]
    ) -> ChatResponse:
        """执行模式 — 自动路由到合适的 Provider。

        Args:
            messages: 对话消息列表
            tools: 工具模式列表

        Returns:
            ChatResponse: LLM 响应
        """
        prompt = self._extract_prompt(messages)
        provider = self.route(prompt)
        return provider.chat_for_execution(messages, tools)

    def _extract_prompt(self, messages: list[dict]) -> str:
        """从消息列表中提取用户提示文本用于路由判断。"""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                return content if isinstance(content, str) else str(content)
        return ""
