"""Token 成本追踪器——让每次 LLM 调用的成本透明可见"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CostBreakdown:
    """单次 LLM 调用的成本明细"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model_name: str
    actual_cost_usd: Decimal
    gpt4o_equivalent_usd: Decimal
    savings_usd: Decimal
    savings_percent: float


class CostTracker:
    """Token 成本追踪器"""

    # 价格表：每 1M tokens 的美元价格
    PRICING: dict[str, dict[str, Decimal]] = {
        "deepseek-chat": {
            "input": Decimal("0.07"),
            "output": Decimal("0.28"),
        },
        "deepseek-coder": {
            "input": Decimal("0.14"),
            "output": Decimal("0.56"),
        },
        "gpt-4o": {
            "input": Decimal("2.50"),
            "output": Decimal("10.00"),
        },
    }

    def __init__(self):
        self._history: list[CostBreakdown] = []

    def calculate(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model_name: str,
    ) -> CostBreakdown:
        """计算单次调用的成本明细"""
        if model_name not in self.PRICING:
            raise ValueError(f"Unknown model: {model_name}")

        pricing = self.PRICING[model_name]
        gpt4o_pricing = self.PRICING["gpt-4o"]

        # 实际成本
        input_cost = Decimal(prompt_tokens) * pricing["input"] / Decimal("1000000")
        output_cost = Decimal(completion_tokens) * pricing["output"] / Decimal("1000000")
        actual_cost = input_cost + output_cost

        # GPT-4o 等效成本
        gpt4o_input = Decimal(prompt_tokens) * gpt4o_pricing["input"] / Decimal("1000000")
        gpt4o_output = Decimal(completion_tokens) * gpt4o_pricing["output"] / Decimal("1000000")
        gpt4o_cost = gpt4o_input + gpt4o_output

        # 节省金额和百分比
        savings = gpt4o_cost - actual_cost
        savings_percent = float(savings / gpt4o_cost * 100) if gpt4o_cost > 0 else 0.0

        breakdown = CostBreakdown(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model_name=model_name,
            actual_cost_usd=actual_cost.quantize(Decimal("0.00001")),
            gpt4o_equivalent_usd=gpt4o_cost.quantize(Decimal("0.00001")),
            savings_usd=savings.quantize(Decimal("0.00001")),
            savings_percent=round(savings_percent, 1),
        )

        self._history.append(breakdown)
        return breakdown

    def get_session_summary(self) -> dict:
        """返回本次会话的总花费和节省金额"""
        if not self._history:
            return {
                "call_count": 0,
                "total_tokens": 0,
                "total_cost_usd": Decimal("0"),
                "total_savings_usd": Decimal("0"),
            }

        return {
            "call_count": len(self._history),
            "total_tokens": sum(h.total_tokens for h in self._history),
            "total_cost_usd": sum(h.actual_cost_usd for h in self._history),
            "total_savings_usd": sum(h.savings_usd for h in self._history),
        }
