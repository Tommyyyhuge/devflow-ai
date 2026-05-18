"""Token 成本追踪器——让每次 LLM 调用的成本透明可见

支持单次调用成本计算、会话累计、预算上限检查、持久化到磁盘。
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path


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


@dataclass
class BudgetStatus:
    """预算状态"""
    weekly_spent: Decimal
    weekly_limit: Decimal
    weekly_remaining: Decimal
    per_5h_spent: Decimal
    per_5h_limit: Decimal
    per_5h_remaining: Decimal
    is_weekly_exceeded: bool
    is_per_5h_exceeded: bool
    last_reset: datetime


class CostTracker:
    """Token 成本追踪器——支持预算上限检查与持久化"""

    # 价格表：每 1M tokens 的美元价格
    # deepseek-v4-flash: https://platform.deepseek.com/api-docs/pricing
    PRICING: dict[str, dict[str, Decimal]] = {
        "deepseek-v4-flash": {
            "input": Decimal("0.07"),
            "output": Decimal("0.28"),
        },
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

    def __init__(
        self,
        budget_file: str | Path | None = None,
        weekly_limit: float = 20.0,
        per_5h_limit: float = 3.5,
    ):
        self._history: list[CostBreakdown] = []
        self.weekly_limit = Decimal(str(weekly_limit))
        self.per_5h_limit = Decimal(str(per_5h_limit))

        # 持久化文件路径
        if budget_file is None:
            budget_file = Path.home() / ".devflow" / "budget.json"
        self._budget_file = Path(budget_file)
        self._budget_file.parent.mkdir(parents=True, exist_ok=True)

        # 加载历史累计数据
        self._weekly_spent, self._per_5h_spent, self._last_reset = self._load_budget()

    # ---------- 成本计算 ----------

    def calculate(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model_name: str,
    ) -> CostBreakdown:
        """计算单次调用的成本明细，并累计到预算"""
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
        self._weekly_spent += breakdown.actual_cost_usd
        self._per_5h_spent += breakdown.actual_cost_usd
        self._save_budget()

        return breakdown

    # ---------- 预算检查 ----------

    def check_budget(self) -> BudgetStatus:
        """检查当前预算状态

        Returns:
            BudgetStatus: 包含各项预算使用情况的结构化状态

        Raises:
            BudgetExceededError: 当任意预算上限被超出时
        """
        now = datetime.now()

        # 检查是否需要重置 5 小时窗口
        if now - self._last_reset > timedelta(hours=5):
            self._per_5h_spent = Decimal("0")
            self._last_reset = now
            self._save_budget()

        weekly_remaining = self.weekly_limit - self._weekly_spent
        per_5h_remaining = self.per_5h_limit - self._per_5h_spent

        status = BudgetStatus(
            weekly_spent=self._weekly_spent.quantize(Decimal("0.00001")),
            weekly_limit=self.weekly_limit,
            weekly_remaining=weekly_remaining.quantize(Decimal("0.00001")),
            per_5h_spent=self._per_5h_spent.quantize(Decimal("0.00001")),
            per_5h_limit=self.per_5h_limit,
            per_5h_remaining=per_5h_remaining.quantize(Decimal("0.00001")),
            is_weekly_exceeded=self._weekly_spent >= self.weekly_limit,
            is_per_5h_exceeded=self._per_5h_spent >= self.per_5h_limit,
            last_reset=self._last_reset,
        )

        if status.is_weekly_exceeded:
            raise BudgetExceededError(
                f"周预算已耗尽: ${status.weekly_spent} / ${status.weekly_limit}"
            )
        if status.is_per_5h_exceeded:
            raise BudgetExceededError(
                f"5小时预算已耗尽: ${status.per_5h_spent} / ${status.per_5h_limit}"
            )

        return status

    def get_budget_summary(self) -> dict:
        """返回预算使用摘要（不触发异常）"""
        now = datetime.now()
        if now - self._last_reset > timedelta(hours=5):
            per_5h_spent = Decimal("0")
            per_5h_remaining = self.per_5h_limit
        else:
            per_5h_spent = self._per_5h_spent
            per_5h_remaining = self.per_5h_limit - self._per_5h_spent

        return {
            "weekly": {
                "spent": float(self._weekly_spent.quantize(Decimal("0.00001"))),
                "limit": float(self.weekly_limit),
                "remaining": float((self.weekly_limit - self._weekly_spent).quantize(Decimal("0.00001"))),
            },
            "per_5h": {
                "spent": float(per_5h_spent.quantize(Decimal("0.00001"))),
                "limit": float(self.per_5h_limit),
                "remaining": float(per_5h_remaining.quantize(Decimal("0.00001"))),
                "last_reset": self._last_reset.isoformat(),
            },
            "session": self.get_session_summary(),
        }

    # ---------- 会话统计 ----------

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

    # ---------- 持久化 ----------

    def _load_budget(self) -> tuple[Decimal, Decimal, datetime]:
        """从磁盘加载预算累计数据"""
        if not self._budget_file.exists():
            return Decimal("0"), Decimal("0"), datetime.now()

        try:
            with open(self._budget_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 检查是否需要重置周预算（每周一重置）
            last_save = datetime.fromisoformat(data.get("saved_at", datetime.now().isoformat()))
            now = datetime.now()
            weekly_spent = Decimal(str(data.get("weekly_spent", "0")))

            # 如果跨越了周一，重置周预算
            if last_save.isocalendar()[1] != now.isocalendar()[1] or last_save.year != now.year:
                weekly_spent = Decimal("0")

            per_5h_spent = Decimal(str(data.get("per_5h_spent", "0")))
            last_reset = datetime.fromisoformat(data.get("last_reset", datetime.now().isoformat()))

            # 如果 5 小时窗口已过期，重置
            if now - last_reset > timedelta(hours=5):
                per_5h_spent = Decimal("0")
                last_reset = now

            return weekly_spent, per_5h_spent, last_reset

        except (json.JSONDecodeError, KeyError, ValueError):
            return Decimal("0"), Decimal("0"), datetime.now()

    def _save_budget(self) -> None:
        """保存预算累计数据到磁盘"""
        data = {
            "weekly_spent": str(self._weekly_spent),
            "per_5h_spent": str(self._per_5h_spent),
            "last_reset": self._last_reset.isoformat(),
            "saved_at": datetime.now().isoformat(),
        }
        with open(self._budget_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


class BudgetExceededError(Exception):
    """预算超出上限异常"""
    pass
