"""Token 成本追踪器测试"""

from decimal import Decimal

import pytest

from devflow.llm.cost_tracker import CostBreakdown, CostTracker


class TestCostTracker:
    def test_calculate_deepseek_chat(self):
        """测试 DeepSeek Chat 成本计算"""
        tracker = CostTracker()
        result = tracker.calculate(
            prompt_tokens=1000,
            completion_tokens=500,
            model_name="deepseek-chat",
        )

        # 输入: 1000 * $0.07/1M = $0.00007
        # 输出: 500 * $0.28/1M = $0.00014
        # 总计: $0.00021
        assert result.actual_cost_usd == Decimal("0.00021")
        assert result.model_name == "deepseek-chat"

    def test_calculate_gpt4o_equivalent(self):
        """测试 GPT-4o 等效成本计算"""
        tracker = CostTracker()
        result = tracker.calculate(
            prompt_tokens=1000,
            completion_tokens=500,
            model_name="deepseek-chat",
        )

        # GPT-4o 成本:
        # 输入: 1000 * $2.50/1M = $0.0025
        # 输出: 500 * $10.00/1M = $0.005
        # 总计: $0.0075
        assert result.gpt4o_equivalent_usd == Decimal("0.0075")
        assert result.savings_usd == Decimal("0.00729")
        assert result.savings_percent == pytest.approx(97.2, rel=0.1)

    def test_session_summary(self):
        """测试会话汇总"""
        tracker = CostTracker()

        # 模拟两次调用
        tracker.calculate(1000, 500, "deepseek-chat")
        tracker.calculate(2000, 1000, "deepseek-chat")

        summary = tracker.get_session_summary()
        assert summary["call_count"] == 2
        assert summary["total_cost_usd"] > 0
        assert summary["total_savings_usd"] > 0

    def test_unknown_model_raises_error(self):
        """测试未知模型报错"""
        tracker = CostTracker()

        with pytest.raises(ValueError, match="Unknown model"):
            tracker.calculate(100, 100, "unknown-model")
