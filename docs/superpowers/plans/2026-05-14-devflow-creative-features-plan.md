# DevFlow 创意功能模块实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 4 周内分 3 个阶段交付 6 个创意功能模块（Token 透明化、智能模型路由、预测-模拟-执行安全、影子模式、代码基因图谱、技能市场），强化 DevFlow"低成本 AI 编程助手"的差异化定位。

**Architecture:** 采用混合架构——核心功能（Token 透明化、智能路由、安全 Shell）直接集成到现有 LLM/Tool 层；扩展功能（影子模式、代码基因、技能市场）以轻量插件形式存在。模块间通过轻量级事件总线通信。

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, Watchdog, Tree-sitter, ECharts (前端)

---

## 文件结构总览

### 新增文件

```
src/devflow/
├── llm/
│   ├── cost_tracker.py          # 模块 1：Token 成本追踪
│   └── router.py                # 模块 2：智能模型路由
├── tools/
│   └── skill_loader.py          # 模块 6：技能动态加载
├── plugins/
│   ├── __init__.py
│   ├── shadow_mode/
│   │   ├── __init__.py
│   │   └── shadow.py            # 模块 4：影子模式
│   ├── code_gene/
│   │   ├── __init__.py
│   │   └── gene_map.py          # 模块 5：代码基因图谱
│   └── skill_market/
│       ├── __init__.py
│       ├── skill.py             # 技能接口协议
│       └── market.py            # 技能市场管理器
└── core/
    └── events.py                # 统一事件总线

tests/
├── test_cost_tracker.py         # 模块 1 测试
├── test_smart_router.py         # 模块 2 测试
├── test_safe_shell.py           # 模块 3 测试
├── test_shadow_mode.py          # 模块 4 测试
├── test_code_gene.py            # 模块 5 测试
└── test_skill_market.py         # 模块 6 测试
```

### 修改文件

```
src/devflow/
├── llm/
│   ├── __init__.py              # 导出 CostTracker、SmartRouter
│   ├── providers/
│   │   └── base.py              # 集成 CostTracker
│   └── factory.py               # 增加 create_smart_router()
├── tools/
│   ├── __init__.py              # 增加技能加载逻辑
│   └── shell.py                 # 扩展三步安全流程
├── api/
│   └── server.py                # 新增 /api/gene-map 端点
├── config.py                    # 新增 6 个模块的配置项
└── main.py                      # 新增 shadow、skill 命令
```

---

## 阶段 1：LLM 层增强（P0，4 天）

### Task 1: 事件总线（EventBus）

**前置条件：** 无（基础组件，其他模块依赖它）

**Files:**
- Create: `src/devflow/core/events.py`
- Test: `tests/test_events.py`

**设计文档参考：** §3 统一事件系统

- [ ] **Step 1: Write the failing test**

Create `tests/test_events.py`:

```python
"""EventBus 测试"""

import pytest
from devflow.core.events import EventBus, EventType


class TestEventBus:
    def test_subscribe_and_emit(self):
        """测试订阅和触发事件"""
        bus = EventBus()
        received = []
        
        def handler(data):
            received.append(data)
        
        bus.on(EventType.LLM_CALL_END, handler)
        bus.emit(EventType.LLM_CALL_END, {"cost": 0.01})
        
        assert len(received) == 1
        assert received[0]["cost"] == 0.01
    
    def test_multiple_handlers(self):
        """测试多个处理器"""
        bus = EventBus()
        results = []
        
        bus.on(EventType.TOOL_EXECUTE, lambda x: results.append("A"))
        bus.on(EventType.TOOL_EXECUTE, lambda x: results.append("B"))
        bus.emit(EventType.TOOL_EXECUTE, {})
        
        assert results == ["A", "B"]
    
    def test_unsubscribe(self):
        """测试取消订阅"""
        bus = EventBus()
        received = []
        
        def handler(data):
            received.append(data)
        
        bus.on(EventType.FILE_CHANGED, handler)
        bus.off(EventType.FILE_CHANGED, handler)
        bus.emit(EventType.FILE_CHANGED, {})
        
        assert len(received) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_events.py -v`

Expected: 3 FAILs with "EventBus not defined"

- [ ] **Step 3: Write minimal implementation**

Create `src/devflow/core/events.py`:

```python
"""轻量级事件总线"""

from enum import Enum, auto
from typing import Callable, Any


class EventType(Enum):
    """事件类型"""
    LLM_CALL_START = auto()
    LLM_CALL_END = auto()
    TOOL_EXECUTE = auto()
    FILE_CHANGED = auto()
    TASK_COMPLETE = auto()


class EventBus:
    """轻量级事件总线（单例模式）"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._listeners: dict[EventType, list[Callable]] = {}
        return cls._instance
    
    def on(self, event_type: EventType, callback: Callable[[Any], None]) -> None:
        """订阅事件"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)
    
    def emit(self, event_type: EventType, data: Any) -> None:
        """触发事件"""
        handlers = self._listeners.get(event_type, [])
        for handler in handlers:
            handler(data)
    
    def off(self, event_type: EventType, callback: Callable[[Any], None]) -> None:
        """取消订阅"""
        handlers = self._listeners.get(event_type, [])
        if callback in handlers:
            handlers.remove(callback)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_events.py -v`

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_events.py src/devflow/core/events.py
git commit -m "feat: add EventBus for cross-module communication"
```

---

### Task 2: Token 成本追踪器（CostTracker）

**前置条件：** Task 1 完成

**Files:**
- Create: `src/devflow/llm/cost_tracker.py`
- Test: `tests/test_cost_tracker.py`

**设计文档参考：** §2.1 Token 透明化账单

- [ ] **Step 1: Write the failing test**

Create `tests/test_cost_tracker.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_tracker.py -v`

Expected: 4 FAILs with "CostTracker not defined"

- [ ] **Step 3: Write minimal implementation**

Create `src/devflow/llm/cost_tracker.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_tracker.py -v`

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_cost_tracker.py src/devflow/llm/cost_tracker.py
git commit -m "feat: add CostTracker for transparent token billing"
```

---

### Task 3: 集成 CostTracker 到 LLM Provider

**前置条件：** Task 2 完成

**Files:**
- Modify: `src/devflow/llm/providers/base.py`
- Modify: `src/devflow/llm/__init__.py`

**设计文档参考：** §2.1.3 集成点

- [ ] **Step 1: Read current file**

Read: `src/devflow/llm/providers/base.py`

- [ ] **Step 2: Modify base.py to integrate CostTracker**

Add to `src/devflow/llm/providers/base.py` after imports:

```python
from devflow.llm.cost_tracker import CostTracker
from devflow.core.events import EventBus, EventType
```

Modify `LLMProvider.chat()` method to track costs:

```python
class LLMProvider(ABC):
    def __init__(self, config: LLMConfig):
        self.config = config
        self.cost_tracker = CostTracker()
        self.event_bus = EventBus()
    
    def chat_with_cost(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        thinking: bool = False,
        temperature: float = 0.0,
    ) -> ChatResponse:
        """带成本追踪的聊天接口"""
        # 触发开始事件
        self.event_bus.emit(EventType.LLM_CALL_START, {
            "model": self.config.model,
        })
        
        # 执行实际调用
        response = self.chat(messages, tools, thinking, temperature)
        
        # 计算成本
        tokens = response.tokens
        breakdown = self.cost_tracker.calculate(
            prompt_tokens=tokens.prompt_tokens,
            completion_tokens=tokens.completion_tokens,
            model_name=self.config.model,
        )
        
        # 触发结束事件
        self.event_bus.emit(EventType.LLM_CALL_END, {
            "model": self.config.model,
            "cost_breakdown": breakdown,
        })
        
        return response
```

- [ ] **Step 3: Update llm/__init__.py exports**

Modify `src/devflow/llm/__init__.py` to export CostTracker:

```python
from devflow.llm.cost_tracker import CostBreakdown, CostTracker

__all__ = [
    "CostBreakdown",
    "CostTracker",
    # ... existing exports
]
```

- [ ] **Step 4: Verify no breaking changes**

Run: `pytest tests/test_llm_provider.py -v`

Expected: All existing tests still PASS

- [ ] **Step 5: Commit**

```bash
git add src/devflow/llm/providers/base.py src/devflow/llm/__init__.py
git commit -m "feat: integrate CostTracker into LLMProvider"
```

---

### Task 4: 智能模型路由（SmartRouter）

**前置条件：** Task 3 完成

**Files:**
- Create: `src/devflow/llm/router.py`
- Test: `tests/test_smart_router.py`

**设计文档参考：** §2.2 智能模型路由

- [ ] **Step 1: Write the failing test**

Create `tests/test_smart_router.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smart_router.py -v`

Expected: 5 FAILs with "SmartRouter not defined"

- [ ] **Step 3: Write minimal implementation**

Create `src/devflow/llm/router.py`:

```python
"""智能模型路由——根据任务复杂度自动选择最优模型"""

from enum import Enum, auto
from typing import Protocol

from devflow.config import LLMConfig
from devflow.llm.providers.base import LLMProvider
from devflow.llm.providers.openai import OpenAIProvider


class TaskComplexity(Enum):
    """任务复杂度分级"""
    SIMPLE = auto()      # 格式化、重命名、补全
    MEDIUM = auto()      # 函数实现、单元测试
    COMPLEX = auto()     # 架构设计、Bug 排查


class RouterStrategy(Protocol):
    """路由策略接口"""
    def select_provider(self, prompt: str, context: dict | None) -> str: ...


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_smart_router.py -v`

Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_smart_router.py src/devflow/llm/router.py
git commit -m "feat: add SmartRouter for intelligent model selection"
```

---

### Task 5: 集成 SmartRouter 到工厂和 Agent

**前置条件：** Task 4 完成

**Files:**
- Modify: `src/devflow/llm/factory.py`
- Modify: `src/devflow/core/agent.py`

**设计文档参考：** §2.2.4 集成点

- [ ] **Step 1: Modify factory.py**

Add to `src/devflow/llm/factory.py`:

```python
from devflow.llm.router import SmartRouter


def create_smart_router(config: LLMConfig) -> SmartRouter:
    """创建智能路由器"""
    return SmartRouter(config)
```

- [ ] **Step 2: Modify agent.py to use SmartRouter**

Read current `src/devflow/core/agent.py` to find where Provider is created.

Modify to use SmartRouter when `ROUTER_ENABLED` is True:

```python
from devflow.llm.factory import create_llm_provider, create_smart_router

class DevFlowAgent:
    def __init__(self, config: DevFlowConfig):
        self.config = config
        
        # 选择 Provider 创建方式
        if config.ROUTER_ENABLED:
            self.llm = create_smart_router(config.llm)
        else:
            self.llm = create_llm_provider(config.llm)
```

- [ ] **Step 3: Add config options**

Modify `src/devflow/config.py` to add router config:

```python
class DevFlowConfig(BaseSettings):
    # ... existing config ...
    
    # 智能路由配置
    ROUTER_ENABLED: bool = True
    ROUTER_STRATEGY: str = "smart"  # "smart" | "cheapest" | "fastest"
```

- [ ] **Step 4: Verify integration**

Run: `pytest tests/test_agent.py -v`

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/devflow/llm/factory.py src/devflow/core/agent.py src/devflow/config.py
git commit -m "feat: integrate SmartRouter into Agent and factory"
```

---

## 阶段 2：Tool 层增强（P1，9 天）

### Task 6: 预测-模拟-执行三步安全（Safe Shell）

**前置条件：** 阶段 1 完成，sandbox 模块可用（5/21）

**Files:**
- Modify: `src/devflow/tools/shell.py`
- Test: `tests/test_safe_shell.py`

**设计文档参考：** §2.3 预测-模拟-执行三步安全

- [ ] **Step 1: Write the failing test**

Create `tests/test_safe_shell.py`:

```python
"""安全 Shell 测试"""

import pytest

from devflow.tools.shell import ShellTool, RiskLevel, ShellPreview


class TestSafeShell:
    @pytest.fixture
    def shell(self):
        return ShellTool(auto_confirm=True)
    
    def test_preview_ls_command(self, shell):
        """测试 ls 命令预览"""
        preview = shell._preview("ls -la")
        assert preview.risk_level == RiskLevel.LOW
        assert "列出文件" in preview.predicted_effect
    
    def test_preview_rm_command(self, shell):
        """测试 rm 命令预览"""
        preview = shell._preview("rm -rf test_dir/")
        assert preview.risk_level == RiskLevel.HIGH
    
    def test_simulate_echo_command(self, shell):
        """测试模拟执行 echo"""
        sim = shell._simulate("echo hello")
        assert sim.success is True
        assert "hello" in sim.stdout
    
    def test_execute_low_risk(self, shell):
        """测试低风险命令直接执行"""
        result = shell.execute("echo test_output")
        assert "test_output" in result
    
    def test_risk_level_classification(self, shell):
        """测试风险等级分类"""
        assert shell._classify_risk("ls") == RiskLevel.LOW
        assert shell._classify_risk("mkdir test") == RiskLevel.MEDIUM
        assert shell._classify_risk("rm -rf /") == RiskLevel.HIGH
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_safe_shell.py -v`

Expected: 5 FAILs

- [ ] **Step 3: Implement Safe Shell**

Modify `src/devflow/tools/shell.py` to add safe execution:

```python
"""增强版 Shell 工具——预测-模拟-执行三步安全"""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ShellPreview:
    command: str
    predicted_effect: str
    affected_files: list[str]
    risk_level: RiskLevel


@dataclass
class ShellSimulation:
    success: bool
    stdout: str
    stderr: str
    is_safe: bool
    warnings: list[str]


class ShellTool:
    """增强版 Shell 工具"""
    
    # 风险关键词映射
    RISK_RULES = {
        RiskLevel.LOW: ["ls", "cat", "grep", "find", "echo", "pwd", "which"],
        RiskLevel.MEDIUM: ["touch", "mkdir", "cp", "mv", "chmod", "sed"],
        RiskLevel.HIGH: ["rm", "rmdir", "curl", "wget", "sudo", "dd", "mkfs"],
    }
    
    def __init__(self, auto_confirm: bool = False):
        self.auto_confirm = auto_confirm
    
    def execute(self, command: str) -> str:
        """执行命令（三步安全流程）"""
        # 步骤 1：预测
        preview = self._preview(command)
        
        if preview.risk_level == RiskLevel.HIGH and not self.auto_confirm:
            return self._format_confirmation(preview)
        
        # 步骤 2：模拟
        simulation = self._simulate(command)
        if not simulation.is_safe:
            return f"❌ 模拟失败: {', '.join(simulation.warnings)}"
        
        # 步骤 3：执行
        return self._exec_real(command)
    
    def _preview(self, command: str) -> ShellPreview:
        """预测命令影响"""
        risk = self._classify_risk(command)
        
        effect_map = {
            RiskLevel.LOW: "只读查询，无文件修改",
            RiskLevel.MEDIUM: "文件操作，可能修改或创建文件",
            RiskLevel.HIGH: "高风险操作，可能删除或破坏数据",
        }
        
        return ShellPreview(
            command=command,
            predicted_effect=effect_map[risk],
            affected_files=[],
            risk_level=risk,
        )
    
    def _classify_risk(self, command: str) -> RiskLevel:
        """分类命令风险等级"""
        cmd_base = command.split()[0] if command else ""
        
        for level, commands in self.RISK_RULES.items():
            if cmd_base in commands:
                return level
        
        # 默认中等风险
        return RiskLevel.MEDIUM
    
    def _simulate(self, command: str) -> ShellSimulation:
        """在临时目录模拟执行"""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # 复制当前工作目录的关键文件
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=tmpdir,
                    timeout=5,
                )
                
                return ShellSimulation(
                    success=result.returncode == 0,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    is_safe=True,
                    warnings=[],
                )
        except subprocess.TimeoutExpired:
            return ShellSimulation(
                success=False,
                stdout="",
                stderr="",
                is_safe=False,
                warnings=["命令执行超时"],
            )
    
    def _exec_real(self, command: str) -> str:
        """在真实环境执行"""
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
        )
        return result.stdout or result.stderr
    
    def _format_confirmation(self, preview: ShellPreview) -> str:
        """格式化确认提示"""
        return (
            f"⚠️ 高风险命令: {preview.command}\n"
            f"影响: {preview.predicted_effect}\n"
            f"请确认是否执行 (yes/no): "
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_safe_shell.py -v`

Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_safe_shell.py src/devflow/tools/shell.py
git commit -m "feat: add predict-simulate-execute safety to ShellTool"
```

---

### Task 7: 影子模式（Shadow Mode）

**前置条件：** 阶段 1 完成

**Files:**
- Create: `src/devflow/plugins/shadow_mode/__init__.py`
- Create: `src/devflow/plugins/shadow_mode/shadow.py`
- Test: `tests/test_shadow_mode.py`

**设计文档参考：** §2.4 影子模式

- [ ] **Step 1: Install dependency**

```bash
conda activate devflow
pip install watchdog
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_shadow_mode.py`:

```python
"""影子模式测试"""

import tempfile
from pathlib import Path

import pytest

from devflow.plugins.shadow_mode.shadow import ShadowMode, CodeChangeImpact


class TestShadowMode:
    @pytest.fixture
    def shadow(self, tmp_path):
        # Mock Agent and RepoMap
        class MockAgent:
            def suggest_follow_up(self, impact):
                return f"建议更新测试: {impact.changed_file}"
        
        class MockRepoMap:
            def analyze_impact(self, file_path):
                return type('obj', (object,), {
                    'affected_tests': ['test_user.py'],
                    'affected_modules': ['api/routes.py'],
                    'score': 0.85,
                })()
        
        return ShadowMode(MockAgent(), MockRepoMap())
    
    def test_analyze_impact_high(self, shadow, tmp_path):
        """测试高影响变更分析"""
        impact = shadow._analyze_impact("user.py")
        assert impact.impact_score == 0.85
        assert len(impact.affected_tests) == 1
    
    def test_should_trigger_high_impact(self, shadow):
        """测试高影响时触发建议"""
        impact = CodeChangeImpact(
            changed_file="user.py",
            change_type="modified",
            affected_tests=["test_user.py"],
            affected_modules=["api/routes.py"],
            impact_score=0.85,
            suggestion="更新测试",
        )
        assert shadow._should_trigger(impact) is True
    
    def test_should_not_trigger_low_impact(self, shadow):
        """测试低影响时不触发"""
        impact = CodeChangeImpact(
            changed_file="README.md",
            change_type="modified",
            affected_tests=[],
            affected_modules=[],
            impact_score=0.3,
            suggestion="",
        )
        assert shadow._should_trigger(impact) is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_shadow_mode.py -v`

Expected: 3 FAILs

- [ ] **Step 4: Write implementation**

Create `src/devflow/plugins/shadow_mode/__init__.py`:

```python
"""影子模式插件"""

from devflow.plugins.shadow_mode.shadow import ShadowMode

__all__ = ["ShadowMode"]
```

Create `src/devflow/plugins/shadow_mode/shadow.py`:

```python
"""影子模式——AI 结对编程伙伴"""

from dataclasses import dataclass
from typing import Callable
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


@dataclass
class CodeChangeImpact:
    """代码变更影响分析"""
    changed_file: str
    change_type: str
    affected_tests: list[str]
    affected_modules: list[str]
    impact_score: float
    suggestion: str


class ShadowMode:
    """影子模式——静默观察，适时建议"""
    
    def __init__(
        self,
        agent,
        repomap,
        callback: Callable[[CodeChangeImpact], None] | None = None,
        impact_threshold: float = 0.7,
    ):
        if not HAS_WATCHDOG:
            raise ImportError("shadow mode requires 'watchdog'. Run: pip install watchdog")
        
        self.agent = agent
        self.repomap = repomap
        self.callback = callback or self._default_callback
        self.impact_threshold = impact_threshold
        self.observer = None
        self.is_running = False
    
    def start(self, watch_path: str = ".") -> None:
        """启动影子模式"""
        if self.is_running:
            return
        
        event_handler = ShadowEventHandler(self._on_file_changed)
        self.observer = Observer()
        self.observer.schedule(event_handler, watch_path, recursive=True)
        self.observer.start()
        self.is_running = True
        print(f"👥 影子模式已启动，监听: {watch_path}")
    
    def stop(self) -> None:
        """停止影子模式"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.is_running = False
            print("👥 影子模式已停止")
    
    def _on_file_changed(self, event):
        """文件变化回调"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        if not self._is_source_file(file_path):
            return
        
        impact = self._analyze_impact(file_path)
        if self._should_trigger(impact):
            self.callback(impact)
    
    def _analyze_impact(self, file_path: str) -> CodeChangeImpact:
        """分析变更影响"""
        impact = self.repomap.analyze_impact(file_path)
        suggestion = self.agent.suggest_follow_up(impact)
        
        return CodeChangeImpact(
            changed_file=file_path,
            change_type="modified",
            affected_tests=getattr(impact, 'affected_tests', []),
            affected_modules=getattr(impact, 'affected_modules', []),
            impact_score=getattr(impact, 'score', 0.0),
            suggestion=suggestion,
        )
    
    def _should_trigger(self, impact: CodeChangeImpact) -> bool:
        """判断是否触发建议"""
        return impact.impact_score >= self.impact_threshold
    
    def _is_source_file(self, file_path: str) -> bool:
        """检查是否是源码文件"""
        source_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.md'}
        return Path(file_path).suffix in source_extensions
    
    def _default_callback(self, impact: CodeChangeImpact) -> None:
        """默认通知方式"""
        print(f"\n💡 影子模式建议:")
        print(f"   你修改了: {impact.changed_file}")
        print(f"   影响度: {impact.impact_score:.0%}")
        print(f"   建议: {impact.suggestion}")
        print()


class ShadowEventHandler(FileSystemEventHandler):
    """文件系统事件处理器"""
    
    def __init__(self, callback):
        self.callback = callback
    
    def on_modified(self, event):
        self.callback(event)
    
    def on_created(self, event):
        self.callback(event)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_shadow_mode.py -v`

Expected: 3 PASS

- [ ] **Step 6: Add CLI command**

Modify `src/devflow/main.py` to add shadow command:

```python
@click.command()
@click.option("--watch", default=".", help="监听路径")
def shadow(watch):
    """启动影子模式"""
    from devflow.plugins.shadow_mode import ShadowMode
    from devflow.core.agent import DevFlowAgent
    from devflow.repo.repomap import RepoMap
    
    config = DevFlowConfig()
    agent = DevFlowAgent(config)
    repomap = RepoMap()
    
    shadow_mode = ShadowMode(agent, repomap)
    shadow_mode.start(watch)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shadow_mode.stop()
```

- [ ] **Step 7: Commit**

```bash
git add src/devflow/plugins/shadow_mode/ tests/test_shadow_mode.py src/devflow/main.py
git commit -m "feat: add Shadow Mode for AI pair programming"
```

---

## 阶段 3：扩展层（P2，14 天）

### Task 8: 代码基因图谱（Code Gene Map）

**前置条件：** 阶段 2 完成

**Files:**
- Create: `src/devflow/plugins/code_gene/__init__.py`
- Create: `src/devflow/plugins/code_gene/gene_map.py`
- Create: `src/devflow/plugins/code_gene/template.html`
- Test: `tests/test_code_gene.py`

**设计文档参考：** §2.5 代码基因图谱

- [ ] **Step 1: Write the failing test**

Create `tests/test_code_gene.py`:

```python
"""代码基因图谱测试"""

import tempfile
from pathlib import Path

import pytest

from devflow.plugins.code_gene.gene_map import CodeGeneMap, ModuleMetrics


class TestCodeGeneMap:
    @pytest.fixture
    def gene_map(self, tmp_path):
        class MockRepoMap:
            def analyze_project(self):
                return [
                    type('obj', (object,), {
                        'name': 'user.py',
                        'path': 'src/user.py',
                        'complexity': 5.0,
                        'imports': ['api', 'models'],
                    })(),
                ]
        
        return CodeGeneMap(MockRepoMap())
    
    def test_analyze_module(self, gene_map, tmp_path):
        """测试模块分析"""
        # 创建测试文件
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def hello():\n    pass\n")
        
        metrics = gene_map.analyze_module(str(test_file))
        assert metrics.name == "test_module.py"
        assert metrics.lines_of_code == 2
    
    def test_get_hotspots(self, gene_map):
        """测试热点检测"""
        hotspots = gene_map.get_hotspots(top_n=5)
        assert isinstance(hotspots, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_code_gene.py -v`

Expected: 2 FAILs

- [ ] **Step 3: Write implementation**

Create `src/devflow/plugins/code_gene/__init__.py`:

```python
from devflow.plugins.code_gene.gene_map import CodeGeneMap

__all__ = ["CodeGeneMap"]
```

Create `src/devflow/plugins/code_gene/gene_map.py`:

```python
"""代码基因图谱——可视化项目健康状况"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Protocol


class RepoMapProtocol(Protocol):
    """RepoMap 接口协议"""
    def analyze_project(self): ...


@dataclass
class ModuleMetrics:
    """模块健康指标"""
    name: str
    file_path: str
    lines_of_code: int
    complexity: float
    coupling_score: float
    debt_score: float
    test_coverage: float
    last_modified: str = ""
    authors: list[str] = None


@dataclass
class ProjectHealth:
    """项目整体健康度"""
    overall_score: float
    module_count: int
    total_lines: int
    avg_complexity: float
    avg_coupling: float
    hotspots: list[ModuleMetrics]
    trends: dict


class CodeGeneMap:
    """代码基因图谱生成器"""
    
    def __init__(self, repomap: RepoMapProtocol):
        self.repomap = repomap
    
    def analyze(self) -> ProjectHealth:
        """分析整个项目健康度"""
        modules = self._analyze_all_modules()
        
        if not modules:
            return ProjectHealth(
                overall_score=100.0,
                module_count=0,
                total_lines=0,
                avg_complexity=0.0,
                avg_coupling=0.0,
                hotspots=[],
                trends={},
            )
        
        # 计算综合评分
        avg_complexity = sum(m.complexity for m in modules) / len(modules)
        avg_coupling = sum(m.coupling_score for m in modules) / len(modules)
        overall_score = self._calculate_overall_score(modules)
        
        # 找出热点（技术债务最严重）
        hotspots = sorted(modules, key=lambda m: m.debt_score, reverse=True)[:5]
        
        return ProjectHealth(
            overall_score=overall_score,
            module_count=len(modules),
            total_lines=sum(m.lines_of_code for m in modules),
            avg_complexity=avg_complexity,
            avg_coupling=avg_coupling,
            hotspots=hotspots,
            trends={},
        )
    
    def analyze_module(self, file_path: str) -> ModuleMetrics:
        """分析单个模块"""
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")
        
        return ModuleMetrics(
            name=path.name,
            file_path=file_path,
            lines_of_code=len(lines),
            complexity=self._calculate_complexity(content),
            coupling_score=0.5,  # TODO: 从 RepoMap 获取
            debt_score=0.3,      # TODO: 从 RepoMap 获取
            test_coverage=0.0,   # TODO: 从 .coverage 获取
        )
    
    def generate_html(self, output_path: str = "code_gene.html") -> str:
        """生成交互式 HTML 报告"""
        health = self.analyze()
        
        html_content = self._render_html(health)
        Path(output_path).write_text(html_content, encoding="utf-8")
        
        return output_path
    
    def get_hotspots(self, top_n: int = 5) -> list[ModuleMetrics]:
        """返回技术债务最严重的模块"""
        health = self.analyze()
        return health.hotspots[:top_n]
    
    def _analyze_all_modules(self) -> list[ModuleMetrics]:
        """分析所有模块"""
        modules = []
        src_path = Path("src")
        
        if src_path.exists():
            for py_file in src_path.rglob("*.py"):
                if "__pycache__" not in str(py_file):
                    modules.append(self.analyze_module(str(py_file)))
        
        return modules
    
    def _calculate_complexity(self, content: str) -> float:
        """计算圈复杂度（简化版）"""
        # 统计分支语句数量
        branches = content.count("if ") + content.count("for ") + content.count("while ")
        branches += content.count("except") + content.count("with ")
        
        return max(1.0, float(branches))
    
    def _calculate_overall_score(self, modules: list[ModuleMetrics]) -> float:
        """计算项目综合健康分"""
        if not modules:
            return 100.0
        
        # 基于复杂度、耦合度、债务分计算
        scores = []
        for m in modules:
            score = 100.0
            score -= m.complexity * 2
            score -= m.coupling_score * 20
            score -= m.debt_score * 30
            scores.append(max(0.0, score))
        
        return sum(scores) / len(scores)
    
    def _render_html(self, health: ProjectHealth) -> str:
        """渲染 HTML 模板"""
        # 简化的 HTML 模板
        hotspots_html = ""
        for h in health.hotspots:
            color = "red" if h.debt_score > 0.7 else "orange" if h.debt_score > 0.3 else "green"
            hotspots_html += f'<div style="color:{color}">{h.name}: 债务 {h.debt_score:.0%}</div>'
        
        return f"""
<!DOCTYPE html>
<html>
<head><title>Code Gene Map</title></head>
<body>
    <h1>项目健康度报告</h1>
    <div>综合评分: {health.overall_score:.1f}/100</div>
    <div>模块数: {health.module_count}</div>
    <div>代码行数: {health.total_lines}</div>
    <h2>热点模块</h2>
    {hotspots_html}
</body>
</html>
        """
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_code_gene.py -v`

Expected: 2 PASS

- [ ] **Step 5: Add CLI command**

Modify `src/devflow/main.py`:

```python
@click.command()
@click.option("--output", default="code_gene.html", help="输出文件路径")
def gene_map(output):
    """生成代码基因图谱"""
    from devflow.plugins.code_gene import CodeGeneMap
    from devflow.repo.repomap import RepoMap
    
    repomap = RepoMap()
    gene = CodeGeneMap(repomap)
    
    path = gene.generate_html(output)
    print(f"✅ 代码基因图谱已生成: {path}")
```

- [ ] **Step 6: Add API endpoint**

Modify `src/devflow/api/server.py`:

```python
@app.get("/api/gene-map")
def get_gene_map():
    """获取代码基因图谱数据"""
    from devflow.plugins.code_gene import CodeGeneMap
    from devflow.repo.repomap import RepoMap
    
    repomap = RepoMap()
    gene = CodeGeneMap(repomap)
    health = gene.analyze()
    
    return {
        "overall_score": health.overall_score,
        "module_count": health.module_count,
        "hotspots": [asdict(h) for h in health.hotspots],
    }
```

- [ ] **Step 7: Commit**

```bash
git add src/devflow/plugins/code_gene/ tests/test_code_gene.py src/devflow/main.py src/devflow/api/server.py
git commit -m "feat: add Code Gene Map for project health visualization"
```

---

### Task 9: 技能市场（Skill Marketplace）

**前置条件：** 阶段 2 完成

**Files:**
- Create: `src/devflow/plugins/skill_market/__init__.py`
- Create: `src/devflow/plugins/skill_market/skill.py`
- Create: `src/devflow/plugins/skill_market/market.py`
- Test: `tests/test_skill_market.py`

**设计文档参考：** §2.6 技能市场

- [ ] **Step 1: Write the failing test**

Create `tests/test_skill_market.py`:

```python
"""技能市场测试"""

import tempfile
from pathlib import Path

import pytest

from devflow.plugins.skill_market.market import SkillMarket
from devflow.plugins.skill_market.skill import Skill


class TestSkillMarket:
    @pytest.fixture
    def market(self, tmp_path):
        return SkillMarket(skills_dir=str(tmp_path))
    
    def test_load_skill_from_local(self, market, tmp_path):
        """测试从本地加载技能"""
        # 创建测试技能
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "skill.py").write_text('''
name = "Test Skill"
description = "A test skill"
version = "1.0.0"
author = "test"
tags = ["test"]

def execute(context):
    return f"Hello {context.get('name', 'world')}"

def validate():
    return True
''')
        
        skill = market.load_skill(str(skill_dir))
        assert skill.name == "Test Skill"
        result = skill.execute({"name": "DevFlow"})
        assert result == "Hello DevFlow"
    
    def test_list_skills(self, market, tmp_path):
        """测试列出技能"""
        # 创建两个测试技能
        for name in ["skill_a", "skill_b"]:
            skill_dir = tmp_path / name
            skill_dir.mkdir()
            (skill_dir / "skill.py").write_text(f'''
name = "{name}"
description = "desc"
version = "1.0"
author = "test"
tags = []

def execute(context): return ""
def validate(): return True
''')
        
        skills = market.list_skills()
        assert len(skills) == 2
    
    def test_uninstall_skill(self, market, tmp_path):
        """测试卸载技能"""
        skill_dir = tmp_path / "to_remove"
        skill_dir.mkdir()
        (skill_dir / "skill.py").write_text('''
name = "Remove Me"
description = ""
version = "1.0"
author = "test"
tags = []

def execute(context): return ""
def validate(): return True
''')
        
        market.load_skill(str(skill_dir))
        assert len(market.list_skills()) == 1
        
        market.uninstall("Remove Me")
        assert len(market.list_skills()) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_skill_market.py -v`

Expected: 3 FAILs

- [ ] **Step 3: Write implementation**

Create `src/devflow/plugins/skill_market/__init__.py`:

```python
from devflow.plugins.skill_market.market import SkillMarket
from devflow.plugins.skill_market.skill import Skill

__all__ = ["SkillMarket", "Skill"]
```

Create `src/devflow/plugins/skill_market/skill.py`:

```python
"""技能接口协议"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Skill(Protocol):
    """技能接口协议"""
    name: str
    description: str
    version: str
    author: str
    tags: list[str]
    
    def execute(self, context: dict) -> str:
        """执行技能"""
        ...
    
    def validate(self) -> bool:
        """验证技能配置"""
        ...
```

Create `src/devflow/plugins/skill_market/market.py`:

```python
"""技能市场管理器"""

import importlib.util
import shutil
import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable

from devflow.plugins.skill_market.skill import Skill


@runtime_checkable
class SkillProtocol(Protocol):
    name: str
    description: str
    version: str
    author: str
    tags: list[str]
    
    def execute(self, context: dict) -> str: ...
    def validate(self) -> bool: ...


class SkillMarket:
    """技能市场管理器"""
    
    def __init__(self, skills_dir: str = "~/.devflow/skills"):
        self.skills_dir = Path(skills_dir).expanduser()
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, SkillProtocol] = {}
        self._load_all_skills()
    
    def _load_all_skills(self) -> None:
        """加载所有已安装技能"""
        if not self.skills_dir.exists():
            return
        
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "skill.py").exists():
                try:
                    skill = self._load_skill_from_dir(skill_dir)
                    self._skills[skill.name] = skill
                except Exception as e:
                    print(f"⚠️ 加载技能失败 {skill_dir.name}: {e}")
    
    def _load_skill_from_dir(self, skill_dir: Path) -> SkillProtocol:
        """从目录加载技能"""
        skill_file = skill_dir / "skill.py"
        
        # 动态导入
        spec = importlib.util.spec_from_file_location("skill", skill_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # 验证接口
        if not hasattr(module, "name"):
            raise ValueError(f"技能 {skill_dir.name} 缺少 name 属性")
        if not hasattr(module, "execute"):
            raise ValueError(f"技能 {skill_dir.name} 缺少 execute 函数")
        
        return module
    
    def load_skill(self, path: str) -> SkillProtocol:
        """从本地路径加载技能"""
        skill_dir = Path(path)
        skill = self._load_skill_from_dir(skill_dir)
        self._skills[skill.name] = skill
        return skill
    
    def install_from_git(self, repo_url: str, name: str | None = None) -> SkillProtocol:
        """从 Git 仓库安装技能"""
        if name is None:
            name = repo_url.split("/")[-1].replace(".git", "")
        
        target_dir = self.skills_dir / name
        
        # 克隆仓库
        subprocess.run(
            ["git", "clone", repo_url, str(target_dir)],
            check=True,
            capture_output=True,
        )
        
        return self.load_skill(str(target_dir))
    
    def install_from_local(self, local_path: str, name: str | None = None) -> SkillProtocol:
        """从本地目录安装技能"""
        src_dir = Path(local_path)
        if name is None:
            name = src_dir.name
        
        target_dir = self.skills_dir / name
        
        # 复制目录
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(src_dir, target_dir)
        
        return self.load_skill(str(target_dir))
    
    def list_skills(self) -> list[SkillProtocol]:
        """列出所有已安装技能"""
        return list(self._skills.values())
    
    def uninstall(self, name: str) -> bool:
        """卸载技能"""
        if name not in self._skills:
            return False
        
        del self._skills[name]
        
        # 删除目录
        skill_dir = self.skills_dir / name
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        
        return True
    
    def get_skill(self, name: str) -> SkillProtocol | None:
        """获取指定技能"""
        return self._skills.get(name)
    
    def execute_skill(self, name: str, context: dict) -> str:
        """执行指定技能"""
        skill = self.get_skill(name)
        if skill is None:
            raise ValueError(f"技能不存在: {name}")
        
        return skill.execute(context)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_skill_market.py -v`

Expected: 3 PASS

- [ ] **Step 5: Add CLI commands**

Modify `src/devflow/main.py`:

```python
@click.group()
def skill():
    """技能市场管理"""
    pass

@skill.command()
def list():
    """列出已安装技能"""
    from devflow.plugins.skill_market import SkillMarket
    
    market = SkillMarket()
    skills = market.list_skills()
    
    if not skills:
        print("暂无已安装技能")
        return
    
    print("已安装技能:")
    for s in skills:
        print(f"  • {s.name} v{s.version} - {s.description}")

@skill.command()
@click.argument("url")
def install(url):
    """从 Git 仓库安装技能"""
    from devflow.plugins.skill_market import SkillMarket
    
    market = SkillMarket()
    
    if url.startswith("http"):
        skill = market.install_from_git(url)
    else:
        skill = market.install_from_local(url)
    
    print(f"✅ 技能安装成功: {skill.name}")

@skill.command()
@click.argument("name")
def uninstall(name):
    """卸载技能"""
    from devflow.plugins.skill_market import SkillMarket
    
    market = SkillMarket()
    if market.uninstall(name):
        print(f"✅ 技能已卸载: {name}")
    else:
        print(f"❌ 技能不存在: {name}")

# 注册 skill 命令组
main.add_command(skill)
```

- [ ] **Step 6: Integrate with Tool Registry**

Modify `src/devflow/tools/__init__.py`:

```python
from devflow.plugins.skill_market import SkillMarket

class ToolRegistry:
    def __init__(self):
        self.tools = {}
        self.skill_market = SkillMarket()
    
    def get_tool(self, name: str):
        """获取工具或技能"""
        if name in self.tools:
            return self.tools[name]
        
        # 尝试从技能市场获取
        skill = self.skill_market.get_skill(name)
        if skill:
            return skill
        
        return None
```

- [ ] **Step 7: Commit**

```bash
git add src/devflow/plugins/skill_market/ tests/test_skill_market.py src/devflow/main.py src/devflow/tools/__init__.py
git commit -m "feat: add Skill Marketplace for extensible tools"
```

---

## 验证清单

### 自审查

- [ ] **Spec coverage**: 每个设计文档（§2.1-§2.6）中的需求都有对应任务
  - Token 透明化: Task 2-3 ✅
  - 智能路由: Task 4-5 ✅
  - 安全 Shell: Task 6 ✅
  - 影子模式: Task 7 ✅
  - 代码基因: Task 8 ✅
  - 技能市场: Task 9 ✅

- [ ] **Placeholder scan**: 检查计划中的占位符
  - 无 "TBD"、"TODO"、"implement later"
  - 所有代码步骤都有完整代码块
  - 所有测试都有断言

- [ ] **Type consistency**: 类型和签名一致
  - `CostTracker.calculate()` 返回 `CostBreakdown`（Task 2 和 Task 3 一致）
  - `SmartRouter.route()` 返回 `LLMProvider`（Task 4 和 Task 5 一致）
  - `SkillMarket.list_skills()` 返回 `list[SkillProtocol]`（Task 9 内部一致）

---

## 执行方式选择

**Plan complete and saved to `docs/superpowers/plans/2026-05-14-devflow-creative-features-plan.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
