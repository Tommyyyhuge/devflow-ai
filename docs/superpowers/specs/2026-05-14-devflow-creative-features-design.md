# DevFlow 创意功能模块设计文档

> **版本**：v1.0  
> **日期**：2026-05-14  
> **架构方案**：混合架构（核心功能直接集成 + 扩展功能轻量插件）  
> **目标**：在 4 周内交付 6 个创意功能模块，强化 DevFlow"低成本 AI 编程助手"的差异化定位

---

## 一、总体架构

### 1.1 架构选型：混合架构

采用**混合架构**：核心功能（与 LLM 层、Tool 层紧密相关）直接集成到现有代码；扩展功能（独立性强）以**轻量插件**形式存在。

```
devflow/
├── core/              # 核心引擎（Agent/Planner/Executor/Verifier）
├── llm/               # LLM 层（新增 Token 透明化 + 智能路由）
│   ├── providers/     # Provider 实现
│   ├── factory.py     # 工厂模式
│   ├── router.py      # 【新增】智能模型路由
│   └── cost_tracker.py # 【新增】Token 成本追踪
├── tools/             # 工具层（新增预测-模拟-执行 + 技能加载器）
│   ├── shell.py       # 【扩展】三步安全 Shell
│   └── skill_loader.py # 【新增】技能动态加载
├── repo/              # 代码理解层（RepoMap/Scanner/Parser）
├── plugins/           # 【新增】轻量插件目录
│   ├── shadow_mode/   # 影子模式
│   ├── code_gene/     # 代码基因图谱
│   └── skill_market/  # 技能市场
├── api/               # Web UI（新增插件配置页面）
└── main.py            # CLI 入口（新增插件命令）
```

### 1.2 设计原则

1. **渐进式演进**：v0.2.0 用混合架构快速交付，v0.4.0 再评估完整插件系统
2. **接口优先**：每个模块先定义接口，再实现细节，确保模块间松耦合
3. **可测试性**：每个模块独立可测，不依赖其他模块的具体实现
4. **低成本优先**：所有设计决策以"不增加用户成本"为约束

### 1.3 模块依赖关系

```
阶段 1（P0，4 天）：
┌─────────────────┐     ┌─────────────────┐
│ Token 透明化     │────→│ 智能模型路由     │
│ cost_tracker.py │     │ router.py       │
└─────────────────┘     └────────┬────────┘
                                 │
                                 ↓
                    ┌──────────────────────┐
                    │ 核心 Agent            │
                    │ (通过工厂注入)         │
                    └──────────────────────┘

阶段 2（P1，9 天）：
┌─────────────────┐     ┌─────────────────┐
│ 预测-模拟-执行   │     │ 影子模式         │
│ shell.py        │     │ shadow_mode.py  │
│（扩展现有）      │     │（轻量插件）      │
└─────────────────┘     └────────┬────────┘
                                 │
                    ┌────────────┘
                    ↓
         ┌──────────────────────┐
         │ watchdog（文件监听）   │
         └──────────────────────┘

阶段 3（P2，14 天）：
┌─────────────────┐     ┌─────────────────┐
│ 代码基因图谱     │     │ 技能市场         │
│ code_gene.py    │     │ skill_market.py │
│（轻量插件）      │     │（轻量插件）      │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ↓
         ┌──────────────────────┐
         │ RepoMap / tools/      │
         └──────────────────────┘
```

---

## 二、模块详细设计

### 2.1 模块 1：Token 透明化账单（Token Bill）

**优先级**：P0  
**工期**：1 天  
**类型**：直接集成（LLM 层）  
**依赖**：无

#### 2.1.1 设计目标
每次 LLM 调用后，自动计算并展示成本 breakdown，让用户真实感受到"省了多少钱"。

#### 2.1.2 核心接口

```python
# src/devflow/llm/cost_tracker.py
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CostBreakdown:
    """单次 LLM 调用的成本明细"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model_name: str
    actual_cost_usd: Decimal          # 本次实际花费
    gpt4o_equivalent_usd: Decimal     # 如果用 GPT-4o 会花多少
    savings_usd: Decimal              # 节省了多少钱
    savings_percent: float            # 节省百分比


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
    
    def calculate(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model_name: str,
    ) -> CostBreakdown:
        """计算单次调用的成本明细"""
        ...
    
    def get_session_summary(self) -> dict:
        """返回本次会话的总花费和节省金额"""
        ...
```

#### 2.1.3 集成点

1. **LLM Provider 层**：在 `llm/providers/base.py` 的 `chat()` 方法返回前，调用 `CostTracker.calculate()`
2. **CLI 层**：在 `main.py` 的任务完成输出中，增加成本展示
3. **Web UI 层**：在 `/api/chat` 响应中增加 `cost` 字段

#### 2.1.4 数据流

```
用户发送请求
    ↓
Agent 调用 LLM Provider
    ↓
Provider 返回 ChatResponse（含 TokenUsage）
    ↓
【新增】CostTracker.calculate() 计算成本
    ↓
CLI 展示：✅ 任务完成 | 💰 成本 $0.003（节省 99%）
```

#### 2.1.5 输出示例

**CLI 输出**：
```bash
$ devflow run "创建 hello.py"
✅ 任务完成
💰 成本: $0.003 | 节省 $0.47（比 GPT-4o 便宜 99%）
📊 Token: 输入 1,240 | 输出 856 | 总计 2,096
```

**Web UI 响应**：
```json
{
  "result": "...",
  "cost": {
    "actual": 0.003,
    "gpt4o_equivalent": 0.47,
    "savings": 0.467,
    "savings_percent": 99.3
  }
}
```

---

### 2.2 模块 2：智能模型路由（Smart Router）

**优先级**：P0  
**工期**：3 天  
**类型**：直接集成（LLM 层）  
**依赖**：多 Provider 架构 ✅

#### 2.2.1 设计目标
根据任务复杂度自动选择最便宜的模型，在"成本"和"质量"之间智能权衡。

#### 2.2.2 核心接口

```python
# src/devflow/llm/router.py
from enum import Enum, auto
from typing import Protocol


class TaskComplexity(Enum):
    """任务复杂度分级"""
    SIMPLE = auto()      # 格式化、重命名、补全
    MEDIUM = auto()      # 函数实现、单元测试
    COMPLEX = auto()     # 架构设计、Bug 排查


class RouterStrategy(Protocol):
    """路由策略接口"""
    def select_provider(
        self,
        prompt: str,
        context: dict | None,
    ) -> str: ...


class SmartRouter:
    """智能模型路由器"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.providers = {
            TaskComplexity.SIMPLE: self._create_provider("deepseek-chat"),
            TaskComplexity.MEDIUM: self._create_provider("deepseek-coder"),
            TaskComplexity.COMPLEX: self._create_provider("gpt-4o"),
        }
    
    def route(
        self,
        prompt: str,
        context: dict | None = None,
    ) -> LLMProvider:
        """根据任务特征选择最优 Provider"""
        complexity = self._analyze_complexity(prompt)
        return self.providers[complexity]
    
    def _analyze_complexity(self, prompt: str) -> TaskComplexity:
        """启发式复杂度分析"""
        # 规则 1：关键词匹配
        simple_keywords = ["格式化", "重命名", "补全", "缩进", "排序"]
        complex_keywords = ["架构", "设计", "重构", "排查", "优化"]
        
        # 规则 2：Prompt 长度（长 prompt 通常更复杂）
        # 规则 3：上下文文件数量
        ...
    
    def _create_provider(self, model: str) -> LLMProvider:
        """创建指定模型的 Provider"""
        ...
```

#### 2.2.3 路由规则

| 任务特征 | 复杂度 | 选择模型 | 预估成本 |
|----------|--------|----------|----------|
| "格式化代码"、"重命名变量" | SIMPLE | DeepSeek Chat | $0.005 |
| "实现函数"、"写单元测试" | MEDIUM | DeepSeek Coder | $0.01 |
| "设计架构"、"排查 Bug" | COMPLEX | GPT-4o | $0.50 |

#### 2.2.4 集成点

1. **工厂层**：扩展 `llm/factory.py`，增加 `create_smart_router()` 函数
2. **Agent 层**：在 `core/agent.py` 中，用 `SmartRouter` 替代直接使用单一 Provider
3. **配置层**：在 `config.py` 中增加 `ROUTER_STRATEGY` 配置项

#### 2.2.5 数据流

```
用户发送请求："给这个函数写单元测试"
    ↓
Agent 调用 SmartRouter.route()
    ↓
Router 分析 prompt → 匹配关键词 "单元测试" → MEDIUM
    ↓
返回 DeepSeek Coder Provider
    ↓
执行调用 → CostTracker 计算成本
    ↓
展示：本次使用 DeepSeek Coder，成本 $0.01（比 GPT-4o 节省 $0.49）
```

---

### 2.3 模块 3：预测-模拟-执行三步安全（Safe Shell）

**优先级**：P1  
**工期**：5 天  
**类型**：直接集成（Tool 层）  
**依赖**：sandbox 模块（5/21 完成）

#### 2.3.1 设计目标
AI 执行 Shell 命令前，必须经过"预测→模拟→执行"三步验证，确保用户代码安全。

#### 2.3.2 核心接口

```python
# src/devflow/tools/shell.py（扩展）
from dataclasses import dataclass
from enum import Enum


class RiskLevel(Enum):
    LOW = "low"        # 只读命令（ls, cat, grep）
    MEDIUM = "medium"  # 文件操作（touch, mkdir, cp）
    HIGH = "high"      # 破坏性命令（rm, mv, dd）


@dataclass
class ShellPreview:
    """命令预测结果"""
    command: str
    predicted_effect: str          # AI 预测的影响（自然语言）
    affected_files: list[str]      # 可能影响的文件列表
    risk_level: RiskLevel
    estimated_time: str            # 预计执行时间


@dataclass
class ShellSimulation:
    """命令模拟结果"""
    success: bool
    stdout: str
    stderr: str
    file_changes: dict[str, str]   # 文件路径 → diff
    is_safe: bool                  # 是否通过安全检测
    warnings: list[str]            # 警告信息


class ShellTool:
    """增强版 Shell 工具（三步安全）"""
    
    def __init__(self, auto_confirm: bool = False):
        self.auto_confirm = auto_confirm
    
    def execute(self, command: str) -> str:
        """执行命令（三步安全流程）"""
        # 步骤 1：预测
        preview = self._preview(command)
        
        if preview.risk_level == RiskLevel.HIGH and not self.auto_confirm:
            return self._ask_user_confirmation(preview)
        
        # 步骤 2：模拟
        simulation = self._simulate(command)
        if not simulation.is_safe:
            return f"❌ 模拟失败: {simulation.warnings}"
        
        # 步骤 3：执行
        return self._exec_real(command)
    
    def _preview(self, command: str) -> ShellPreview:
        """AI 预测命令影响"""
        ...
    
    def _simulate(self, command: str) -> ShellSimulation:
        """在临时目录模拟执行"""
        ...
    
    def _exec_real(self, command: str) -> str:
        """在真实环境执行"""
        ...
```

#### 2.3.3 安全规则

| 命令类型 | 示例 | 风险等级 | 处理方式 |
|----------|------|----------|----------|
| 只读查询 | `ls`, `cat`, `grep`, `find` | LOW | 直接执行 |
| 文件创建 | `touch`, `mkdir`, `cp` | MEDIUM | 模拟后执行 |
| 文件修改 | `mv`, `sed`, `chmod` | MEDIUM | 模拟后执行 |
| 文件删除 | `rm`, `rmdir` | HIGH | 必须用户确认 |
| 网络操作 | `curl`, `wget` | HIGH | 必须用户确认 |
| 系统命令 | `sudo`, `dd`, `mkfs` | HIGH | 拒绝执行 |

#### 2.3.4 集成点

1. **Tool 层**：扩展 `tools/shell.py`，保持向后兼容
2. **Agent 层**：Agent 调用 ShellTool 时自动触发三步流程
3. **配置层**：增加 `SHELL_AUTO_CONFIRM` 选项（默认 False）

#### 2.3.5 数据流

```
Agent 决定执行 Shell 命令："rm -rf old_code/"
    ↓
步骤 1：预测
  → AI 分析："此命令将删除 old_code/ 目录及其中所有文件"
  → 风险等级：HIGH
  → 需要用户确认
    ↓
步骤 2：模拟
  → 在临时目录执行 rm -rf old_code/
  → 对比文件变化：old_code/ 被删除
  → 通过安全检测
    ↓
步骤 3：执行（需用户确认）
  → 展示："即将删除 old_code/（含 15 个文件），确认？"
  → 用户输入 "yes"
  → 真实执行
```

---

### 2.4 模块 4：影子模式（Shadow Mode）

**优先级**：P1  
**工期**：4 天  
**类型**：轻量插件  
**依赖**：watchdog（需安装到 devflow 环境）

#### 2.4.1 设计目标
AI 在后台静默监控代码编辑，不主动打扰，但在关键时刻给出精准建议。

#### 2.4.2 核心接口

```python
# src/devflow/plugins/shadow_mode/shadow.py
from dataclasses import dataclass
from typing import Callable


@dataclass
class CodeChangeImpact:
    """代码变更影响分析"""
    changed_file: str
    change_type: str              # "modified" | "created" | "deleted"
    affected_tests: list[str]     # 受影响的测试文件
    affected_modules: list[str]   # 受影响的模块
    impact_score: float           # 影响度 0-1
    suggestion: str               # AI 建议


class ShadowMode:
    """影子模式——AI 结对编程伙伴"""
    
    def __init__(
        self,
        agent: DevFlowAgent,
        repomap: RepoMap,
        callback: Callable[[CodeChangeImpact], None] | None = None,
    ):
        self.agent = agent
        self.repomap = repomap
        self.callback = callback or self._default_callback
        self.observer = None
        self.is_running = False
    
    def start(self, watch_path: str = ".") -> None:
        """启动影子模式"""
        ...
    
    def stop(self) -> None:
        """停止影子模式"""
        ...
    
    def _on_file_changed(self, event) -> None:
        """文件变化回调"""
        ...
    
    def _analyze_impact(self, file_path: str) -> CodeChangeImpact:
        """分析变更影响"""
        ...
    
    def _default_callback(self, impact: CodeChangeImpact) -> None:
        """默认通知方式（打印到终端）"""
        ...
```

#### 2.4.3 触发规则

影子模式不会每次文件变化都触发，而是根据以下条件判断：

1. **影响度阈值**：`impact_score > 0.7` 时才触发
2. **防抖机制**：同一文件 30 秒内只触发一次
3. **忽略文件**：`.git/`, `__pycache__/`, `.pytest_cache/` 等
4. **文件类型**：只监听 `.py`, `.js`, `.ts`, `.md` 等源码文件

#### 2.4.4 集成点

1. **CLI 入口**：在 `main.py` 中增加 `devflow shadow --watch .` 命令
2. **轻量插件**：放在 `plugins/shadow_mode/` 目录，通过事件钩子与核心交互
3. **依赖管理**：`watchdog` 作为可选依赖（`pip install devflow-ai[shadow]`）

#### 2.4.5 数据流

```
开发者修改 user.py（增加一个字段）
    ↓
watchdog 检测到文件变化
    ↓
ShadowMode._on_file_changed()
    ↓
RepoMap.analyze_impact("user.py")
  → 发现 test_user.py 依赖 user.py
  → 发现 api/routes.py 使用了 user 模型
  → impact_score = 0.85（高影响）
    ↓
触发通知：
  "你修改了 user.py，建议同步更新：
   - tests/test_user.py（新增字段的测试）
   - api/routes.py（API 序列化）
   要我帮你生成这些修改吗？"
```

---

### 2.5 模块 5：代码基因图谱（Code Gene Map）

**优先级**：P2  
**工期**：7 天  
**类型**：轻量插件  
**依赖**：RepoMap ✅

#### 2.5.1 设计目标
基于 RepoMap 的 AST 数据，生成可视化图谱，直观展示项目健康状况。

#### 2.5.2 核心接口

```python
# src/devflow/plugins/code_gene/gene_map.py
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModuleMetrics:
    """模块健康指标"""
    name: str
    file_path: str
    lines_of_code: int
    complexity: float              # 圈复杂度
    coupling_score: float          # 耦合度 0-1（越高越危险）
    debt_score: float             # 技术债务 0-1
    test_coverage: float          # 测试覆盖率
    last_modified: str            # 最后修改时间
    authors: list[str]            # 贡献者列表


@dataclass
class ProjectHealth:
    """项目整体健康度"""
    overall_score: float           # 综合评分 0-100
    module_count: int
    total_lines: int
    avg_complexity: float
    avg_coupling: float
    hotspots: list[ModuleMetrics]  # 问题最严重的模块
    trends: dict[str, float]      # 趋势数据（周环比）


class CodeGeneMap:
    """代码基因图谱生成器"""
    
    def __init__(self, repomap: RepoMap):
        self.repomap = repomap
    
    def analyze(self) -> ProjectHealth:
        """分析整个项目健康度"""
        ...
    
    def analyze_module(self, file_path: str) -> ModuleMetrics:
        """分析单个模块"""
        ...
    
    def generate_html(self, output_path: str = "code_gene.html") -> str:
        """生成交互式 HTML 可视化报告"""
        ...
    
    def get_hotspots(self, top_n: int = 5) -> list[ModuleMetrics]:
        """返回技术债务最严重的模块"""
        ...
```

#### 2.5.3 可视化设计

**热力图**：用颜色表示模块健康度
- 🟢 绿色：健康（debt_score < 0.3）
- 🟡 黄色：关注（debt_score 0.3-0.7）
- 🔴 红色：危险（debt_score > 0.7）

**网络图**：模块间依赖关系
- 节点大小 = 代码行数
- 边粗细 = 耦合度
- 红色边 = 循环依赖

#### 2.5.4 集成点

1. **CLI 入口**：`devflow gene-map --output report.html`
2. **Web UI**：FastAPI 增加 `/api/gene-map` 端点，前端用 ECharts 渲染
3. **数据导出**：支持 JSON、HTML、Markdown 三种格式

#### 2.5.5 数据流

```
用户运行：devflow gene-map
    ↓
CodeGeneMap.analyze()
    ↓
遍历 src/ 下所有 Python 文件
    ↓
对每个文件：
  - Tree-sitter 解析 AST
  - 计算圈复杂度
  - 分析导入依赖（计算耦合度）
  - 读取 .coverage 数据（测试覆盖率）
  - 读取 git log（最后修改时间、作者）
    ↓
生成 ProjectHealth 对象
    ↓
渲染 HTML 报告（内嵌 ECharts）
    ↓
用户用浏览器打开 report.html
```

---

### 2.6 模块 6：技能市场（Skill Marketplace）

**优先级**：P2  
**工期**：7 天  
**类型**：轻量插件  
**依赖**：tools/ 注册机制

#### 2.6.1 设计目标
把工具抽象成可插拔的"技能卡片"，支持社区分享和动态加载。

#### 2.6.2 核心接口

```python
# src/devflow/plugins/skill_market/skill.py
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
        """验证技能配置是否合法"""
        ...


# src/devflow/plugins/skill_market/market.py
class SkillMarket:
    """技能市场管理器"""
    
    def __init__(self, skills_dir: str = "~/.devflow/skills"):
        self.skills_dir = Path(skills_dir).expanduser()
        self.skills: dict[str, Skill] = {}
    
    def load_skill(self, path: str) -> Skill:
        """从本地路径加载技能"""
        ...
    
    def install_from_git(self, repo_url: str, name: str | None = None) -> Skill:
        """从 Git 仓库安装技能"""
        ...
    
    def install_from_local(self, local_path: str) -> Skill:
        """从本地目录安装技能"""
        ...
    
    def list_skills(self) -> list[Skill]:
        """列出所有已安装技能"""
        ...
    
    def uninstall(self, name: str) -> bool:
        """卸载技能"""
        ...
    
    def get_skill(self, name: str) -> Skill | None:
        """获取指定技能"""
        ...
```

#### 2.6.3 技能包格式

技能是一个独立的 Python 包，最小结构：

```
~/.devflow/skills/react_component/
├── skill.py          # 技能实现（必须）
├── config.yaml       # 技能配置（可选）
├── README.md         # 使用说明（可选）
└── requirements.txt  # 额外依赖（可选）
```

**skill.py 示例**：
```python
name = "React Component Generator"
description = "根据自然语言描述生成 React 组件"
version = "1.0.0"
author = "@tommy"
tags = ["react", "frontend", "component"]

def execute(context: dict) -> str:
    prompt = f"生成 React 组件: {context['description']}"
    # 调用 LLM 生成代码
    return generated_code

def validate() -> bool:
    return True
```

#### 2.6.4 集成点

1. **Tool 层**：在 `tools/__init__.py` 中增加技能加载逻辑，技能与原生工具统一接口
2. **CLI 入口**：
   - `devflow skill list` —— 列出技能
   - `devflow skill install <url>` —— 安装技能
   - `devflow skill uninstall <name>` —— 卸载技能
3. **Agent 层**：Agent 无需区分原生工具和技能，统一通过 `ToolRegistry` 调用

#### 2.6.5 数据流

```
用户安装技能：devflow skill install https://github.com/user/react-skill
    ↓
SkillMarket.install_from_git()
  → git clone 到 ~/.devflow/skills/react-skill/
  → 验证 skill.py 接口
  → 加载到内存
    ↓
用户在 prompt 中使用："用 React 技能生成一个登录表单"
    ↓
Agent 识别到 "React" 关键词
    ↓
ToolRegistry 查找匹配的技能
    ↓
调用 Skill.execute({"description": "登录表单"})
    ↓
返回生成的 React 组件代码
```

---

## 三、统一事件系统

### 3.1 设计目标
6 个模块需要跨层通信（如影子模式需要通知 Agent，Token 追踪需要记录到日志），设计一个轻量级事件总线。

### 3.2 接口设计

```python
# src/devflow/core/events.py
from typing import Callable, Any
from enum import Enum, auto


class EventType(Enum):
    """事件类型"""
    LLM_CALL_START = auto()       # LLM 调用开始
    LLM_CALL_END = auto()         # LLM 调用结束（含成本）
    TOOL_EXECUTE = auto()         # 工具执行
    FILE_CHANGED = auto()         # 文件变化
    TASK_COMPLETE = auto()        # 任务完成


class EventBus:
    """轻量级事件总线"""
    
    def __init__(self):
        self._listeners: dict[EventType, list[Callable]] = {}
    
    def on(self, event_type: EventType, callback: Callable) -> None:
        """订阅事件"""
        ...
    
    def emit(self, event_type: EventType, data: Any) -> None:
        """触发事件"""
        ...
    
    def off(self, event_type: EventType, callback: Callable) -> None:
        """取消订阅"""
        ...
```

### 3.3 事件流示例

```
用户发送请求
    ↓
EventBus.emit(LLM_CALL_START, {"model": "deepseek-chat"})
    ↓
Agent 执行任务
    ↓
EventBus.emit(LLM_CALL_END, {
    "model": "deepseek-chat",
    "cost": 0.003,
    "tokens": {"prompt": 1240, "completion": 856}
})
    ↓
CostTracker 监听 LLM_CALL_END → 更新会话总成本
ShadowMode 监听 FILE_CHANGED → 分析影响
```

---

## 四、配置管理

### 4.1 新增配置项

```python
# src/devflow/config.py（扩展）
class DevFlowConfig(BaseSettings):
    # 现有配置...
    
    # 模块 2：智能路由
    ROUTER_ENABLED: bool = True
    ROUTER_STRATEGY: str = "smart"  # "smart" | "cheapest" | "fastest"
    
    # 模块 3：安全 Shell
    SHELL_SAFE_MODE: bool = True
    SHELL_AUTO_CONFIRM: bool = False  # 是否自动确认低风险命令
    
    # 模块 4：影子模式
    SHADOW_ENABLED: bool = False
    SHADOW_WATCH_PATH: str = "."
    SHADOW_IMPACT_THRESHOLD: float = 0.7
    
    # 模块 5：代码基因
    GENE_MAP_OUTPUT_FORMAT: str = "html"  # "html" | "json" | "markdown"
    
    # 模块 6：技能市场
    SKILLS_DIR: str = "~/.devflow/skills"
```

---

## 五、测试策略

### 5.1 单元测试
每个模块独立测试，Mock 外部依赖：

| 模块 | 测试文件 | 关键用例 |
|------|----------|----------|
| Token 透明化 | `test_cost_tracker.py` | 价格计算正确、节省金额准确 |
| 智能路由 | `test_smart_router.py` | 复杂度分析正确、模型选择合理 |
| 安全 Shell | `test_safe_shell.py` | 风险分级正确、模拟执行隔离 |
| 影子模式 | `test_shadow_mode.py` | 文件监听正常、影响分析准确 |
| 代码基因 | `test_code_gene.py` | 指标计算正确、HTML 生成正常 |
| 技能市场 | `test_skill_market.py` | 加载/安装/卸载正常、接口验证 |

### 5.2 集成测试
测试模块间的协作：
- 智能路由 + Token 透明化：路由选择后正确计算成本
- 影子模式 + RepoMap：文件变化后正确分析影响
- 技能市场 + Agent：Agent 正确调用自定义技能

---

## 六、风险与缓解

| 风险 | 等级 | 说明 | 缓解措施 |
|------|------|------|----------|
| 智能路由误判 | 中 | 把复杂任务分配给便宜模型，导致质量下降 | 允许用户覆盖路由结果（`--model gpt-4o`） |
| 影子模式性能 | 低 | 文件监听消耗 CPU | 使用 watchdog 的轮询模式，限制监听范围 |
| 技能安全 | 中 | 第三方技能可能执行恶意代码 | 技能安装前静态分析，禁止网络/系统调用 |
| 代码基因准确度 | 低 | AST 分析可能不准确 | 结合多种指标（复杂度+耦合+覆盖率），不依赖单一指标 |

---

## 七、交付标准

每个模块的交付必须满足：

1. ✅ 代码实现完整，无占位符
2. ✅ 单元测试覆盖率 > 80%
3. ✅ CLI 命令可用
4. ✅ Web UI 接口可用（如适用）
5. ✅ 文档完整（README + 使用示例）
6. ✅ 通过 Ruff lint 和 mypy 类型检查

---

*设计文档版本：v1.0*  
*下一步：基于本文档编写实现计划（Implementation Plan）*
