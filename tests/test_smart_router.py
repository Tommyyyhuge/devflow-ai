"""智能模型路由测试"""

import pytest

from devflow.llm.router import SmartRouter, TaskComplexity
from devflow.config import LLMConfig


class TestSmartRouter:
    @pytest.fixture
    def router(self):
        config = LLMConfig(
            api_key="test-key",
            model="deepseek-chat",
        )
        return SmartRouter(config)
    
    def test_simple_task_routes_to_cheap_model(self, router):
        """简单任务路由到便宜模型"""
        provider = router.route("格式化这段代码")
        assert provider.config.model == "deepseek-chat"
    
    def test_complex_task_routes_to_expensive_model(self, router):
        """复杂任务路由到高级模型"""
        provider = router.route("设计一个微服务架构")
        assert provider.config.model == "gpt-4o"
    
    def test_medium_task_routes_to_mid_model(self, router):
        """中等任务路由到中等模型"""
        provider = router.route("给这个函数写单元测试")
        assert provider.config.model == "deepseek-coder"
    
    def test_analyze_complexity_simple(self, router):
        """测试复杂度分析 - 简单"""
        complexity = router._analyze_complexity("缩进修正")
        assert complexity == TaskComplexity.SIMPLE
    
    def test_analyze_complexity_complex(self, router):
        """测试复杂度分析 - 复杂"""
        complexity = router._analyze_complexity("排查内存泄漏问题")
        assert complexity == TaskComplexity.COMPLEX
