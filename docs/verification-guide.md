# DevFlow 新功能验证指南

> 验证本次检查中完成的 5 项功能：CostBudget、RepoMap、多语言支持、并行调度、流式输出

---

## 前置条件

```bash
# 确保在 devflow 虚拟环境中
conda activate devflow

# 设置 API Key
set DEEPSEEK_API_KEY=sk-your-key-here
```

---

## 1. 验证 CostBudget（预算上限）

### 1.1 查看预算状态

```bash
python -m devflow budget show
```

**预期输出**：
```
预算使用情况

周预算 (周一重置)
  限额:    $20.00
  已用:    $0.00000
  剩余:    $20.00000

5小时窗口预算
  限额:    $3.50
  已用:    $0.00000
  剩余:    $3.50000
  上次重置: 2026-05-18Txx:xx:xx

本次会话
  LLM 调用: 0 次
  Token 数: 0
  成本:     $0.00000
  节省:     $0.00000 (vs GPT-4o)
```

### 1.2 验证预算持久化

```bash
# 查看预算文件是否已创建
python -c "from pathlib import Path; print(Path.home() / '.devflow' / 'budget.json')"
# 应输出: C:\Users\<用户名>\.devflow\budget.json
```

### 1.3 验证预算超限拒绝（手动测试）

```bash
# 临时修改预算为极低值，测试拒绝逻辑
python -c "
from devflow.llm.cost_tracker import CostTracker

# 模拟已用 $20（达到周上限）
tracker = CostTracker(weekly_limit=20.0, per_5h_limit=3.5)
tracker._weekly_spent = 20.0

try:
    tracker.check_budget()
    print('错误: 应该被拒绝')
except Exception as e:
    print(f'正确: 预算超限被拒绝 - {e}')
"
```

---

## 2. 验证 RepoMap + 多语言支持

### 2.1 分析多语言项目

```bash
# 创建一个包含多种语言的测试项目
mkdir -p /tmp/test_project/src
cd /tmp/test_project

# 创建 Python 文件
cat > src/app.py << 'EOF'
import os
from models import User

def main():
    user = User(name="test")
    print(user.greet())

class App:
    def run(self):
        main()
EOF

# 创建 JavaScript 文件
cat > src/utils.js << 'EOF'
import { helper } from './helper';

function processData(data) {
    return helper(data);
}

class DataProcessor {
    constructor() {
        this.cache = new Map();
    }
    process(input) {
        return processData(input);
    }
}

module.exports = { DataProcessor };
EOF

# 创建 Go 文件
cat > src/server.go << 'EOF'
package main

import "fmt"

func main() {
    fmt.Println("Hello")
}

type Server struct {
    port int
}

func (s *Server) Start() error {
    return nil
}
EOF

# 运行分析
python -m devflow analyze /tmp/test_project
```

**预期输出**：
```
分析项目: /tmp/test_project

文件统计: 3 个文件
  .py: 1
  .js: 1
  .go: 1

文件树:
  src/
    app.py
    server.go
    utils.js
```

### 2.2 验证 RepoMap 符号提取

```bash
python -c "
from pathlib import Path
from devflow.repo.repomap import RepoMapBuilder

builder = RepoMapBuilder(Path('/tmp/test_project'))
repomap = builder.build()

print(f'文件数: {len(repomap.entries)}')
print(f'符号数: {repomap.total_symbols}')
for entry in repomap.entries:
    print(f'\n{entry.path} ({entry.language}):')
    if entry.summary:
        print(entry.summary)
"
```

**预期输出**（应包含各语言符号）：
```
文件数: 3
符号数: 6

src/app.py (python):
def main()
class App()
    def run(self)

src/utils.js (javascript):
function processData(data)
class DataProcessor()
    constructor()
    process(input)

src/server.go (go):
func main()
type Server struct
    func (s *Server) Start()
```

---

## 3. 验证 Planner 依赖关系

### 3.1 测试 Planner 生成 depends_on

```bash
python -c "
from devflow.config import load_config
from devflow.llm import create_llm_provider
from devflow.core.planner import Planner

# 使用 mock 或真实 LLM 测试
# 注意: 需要 DEEPSEEK_API_KEY
config = load_config()
llm = create_llm_provider(config.llm)
planner = Planner(llm)

task = '创建一个用户注册 API：读取现有路由文件，创建 users.py 实现注册端点，修改路由文件注册新路由，运行测试验证'
plan = planner.plan(task)

print(f'步骤数: {len(plan.steps)}')
for step in plan.steps:
    deps = f' (depends_on: {step.depends_on})' if step.depends_on else ''
    print(f'{step.index}. [{step.type.value}] {step.description}{deps}')
"
```

**预期输出**（可能因 LLM 输出略有不同）：
```
步骤数: 5
1. [read] 读取现有路由文件了解结构
2. [read] 读取 models.py 了解用户模型
3. [write] 创建 users.py 实现注册端点 (depends_on: [1])
4. [write] 修改路由文件注册新路由 (depends_on: [1])
5. [verify] 运行测试验证 (depends_on: [3, 4])
```

---

## 4. 验证 Agent 并行调度

### 4.1 手动构造带依赖的计划，测试并行执行

```bash
python -c "
import asyncio
from devflow.core.planner import Plan, Step, StepType
from devflow.core.agent import Agent
from devflow.tools import create_tool_registry
from devflow.llm import create_llm_provider
from devflow.config import load_config
from devflow.tools.base import set_safe_root
from pathlib import Path

# 创建带依赖的测试计划
plan = Plan(
    task='并行测试',
    steps=[
        Step(index=1, type=StepType.READ, description='读取文件 A'),
        Step(index=2, type=StepType.READ, description='读取文件 B'),
        Step(index=3, type=StepType.WRITE, description='修改文件 C', depends_on=[1]),
        Step(index=4, type=StepType.WRITE, description='修改文件 D', depends_on=[2]),
        Step(index=5, type=StepType.VERIFY, description='验证', depends_on=[3, 4]),
    ]
)

# 检查是否有依赖关系
has_deps = any(s.depends_on for s in plan.steps)
print(f'是否有依赖: {has_deps}')
print(f'步骤:')
for s in plan.steps:
    print(f'  {s.index}: {s.type.value} - depends_on={s.depends_on}')
"
```

### 4.2 完整 Agent 执行测试（需要 API Key）

```bash
# 在一个简单的项目上测试
mkdir -p /tmp/test_agent
cd /tmp/test_agent
git init

python -c "
import asyncio
from devflow.config import load_config
from devflow.core.agent import Agent
from devflow.tools import create_tool_registry
from devflow.llm import create_llm_provider
from devflow.tools.base import set_safe_root
from pathlib import Path

config = load_config()
llm = create_llm_provider(config.llm)
tools = create_tool_registry()
agent = Agent(llm, tools, config=config)

set_safe_root(Path('/tmp/test_agent'))

async def test():
    result = await agent.run('创建一个 hello.py 文件，输出 Hello World', '/tmp/test_agent')
    print(f'成功: {result.success}')
    print(f'步骤数: {len(result.step_results)}')
    print(f'修改文件: {result.files_modified}')
    print(f'总成本: \${result.total_cost_usd:.5f}')

asyncio.run(test())
"
```

---

## 5. 验证 SSE 流式输出

### 5.1 启动 Web UI

```bash
# 终端 1：启动服务器
python -m devflow web
# 应输出: Uvicorn running on http://0.0.0.0:8000
```

### 5.2 使用 curl 测试 SSE 端点

```bash
# 终端 2：发送流式请求
# 注意：需要先创建一个测试项目
curl -X POST http://localhost:8000/api/run/stream \
  -H "Content-Type: application/json" \
  -d '{"task": "创建一个 hello.py 输出 Hello World", "project": ""}'
```

**预期输出**（SSE 格式）：
```
event: plan
data: {"steps": [{"index": 1, "type": "write", "description": "..."}, ...]}

event: step_start
data: {"index": 1, "type": "write", "description": "..."}

event: step_complete
data: {"index": 1, "type": "write", "success": true, "output": "..."}

event: file_modified
data: {"path": "hello.py"}

event: complete
data: {"success": true, "total_steps": 1, "total_cost": 0.00001}

event: result
data: {"success": true, "files_modified": ["hello.py"], ...}
```

### 5.3 浏览器验证

1. 打开 http://localhost:8000
2. 在 Web UI 中输入任务
3. 检查浏览器 Network 面板，看是否有 EventSource 连接（需要前端实现）

---

## 快速一键验证

```bash
# 运行全部测试（最可靠的验证方式）
conda activate devflow
python -m pytest tests/ -v

# 预期: 137 passed, 0 failed
```

## 常见问题

**Q: Planner 不生成 depends_on？**
- LLM 可能不总是遵循新 prompt 格式
- 检查 `_parse_steps_json()` 是否正确解析
- 查看日志中的 plan 输出

**Q: RepoMap 只显示 Python 文件？**
- 确认 `GenericTextProvider` 已注册
- 检查文件扩展名是否在支持列表中

**Q: SSE 端点返回 500？**
- 确认 `DEEPSEEK_API_KEY` 已设置
- 检查服务器日志中的错误信息

**Q: 预算 show 显示乱码？**
- Windows 控制台编码问题，不影响功能
- 使用 `chcp 65001` 设置 UTF-8 编码
