# DevFlow 开发路线图

> 记录各阶段迭代决策与实现状态。历史注释已从代码中迁移至此。

---

## Week 1：MVP 核心（已完成 ✅）

**目标**：基础 ReAct + Plan-Execute-Verify，能读取项目 → 添加 REST 端点 → 运行测试通过

### 已实现

- **Agent 核心循环** (`core/agent.py`)：Planner → Executor → Verifier 三阶段架构
- **任务规划** (`core/planner.py`)：LLM JSON mode 拆解任务为 read/write/verify 步骤
- **ReAct 执行器** (`core/executor.py`)：Think → Act → Observe 循环，支持 tool calling
- **基础验证器** (`core/verifier.py`)：Python 语法检查（ast.parse）
- **文件扫描** (`repo/scanner.py`)：文件系统扫描 + grep 搜索 + 上下文构建
- **工具集** (`tools/`)
  - `read_file` / `write_file` / `list_dir` / `edit_file`（精确字符串替换）
  - `run_shell`（白名单 + 黑名单 + 风险分级 + 模拟执行）
  - `git_branch` / `git_commit` / `git_diff` / `git_status`
  - `search_code`（项目内正则搜索）
- **CLI 入口** (`main.py`)：`analyze`, `run`, `config show`, `web`
- **成本追踪** (`llm/cost_tracker.py`)：美元成本计算 + GPT-4o 对比

### 关键决策
- 使用简化版项目理解（文件列表+grep），Tree-sitter 推迟到 Week 2
- 统一模型：DeepSeek V4 Flash（OpenAI 兼容协议）
- CLI + Web UI 双界面，共享 core/ 层

---

## Week 2：增强理解 + 自动化（部分完成 ⚠️）

**目标**：完整 RepoMap、自动工具发现、Web UI 升级

### 已实现

- **Tree-sitter 解析** (`repo/parser.py`)：Python AST 符号提取（类/函数/导入）
- **RepoMap 索引** (`repo/repomap.py`)：结构化项目索引，支持增量缓存
- **工具自动发现** (`tools/__init__.py`)：扫描包自动注册 Tool 子类
- **Token 预算** (`core/agent.py`)：执行级 Token 上限检查（默认 140K），80% 预警
- **Web UI** (`api/server.py`)：FastAPI + Jinja2 模板，支持项目上传（ZIP）、任务提交
- **智能路由** (`llm/router.py`)：根据配置自动选择 Provider 创建方式

### 已完成 ✅

- [x] **RepoMap 与 Agent 的完整集成** (`core/agent.py`)：RepoMap 主路径 + scanner 兜底；基于符号和关键词匹配构建上下文
- [x] **多语言支持** (`repo/parser.py`)：`GenericTextProvider` 使用正则提取 JS/TS/Go/Rust 等语言的函数/类定义；`LanguageRegistry.detect()` 自动分派专用/通用 Provider
- [x] **增量缓存持久化** (`repo/repomap.py`)：`.devflow/repomap_cache.json` 缓存已验证的文件条目

---

## Week 3：质量 + 扩展（部分完成 ⚠️）

**目标**：结构化验证、响应流、预算上限真正生效

### 已实现

- **结构化验证器** (`core/verifier.py`)：Verdict + Diagnostic（LSP 兼容格式）
- **三层 Shell 安全** (`tools/shell.py`)：预测 → 模拟 → 执行，风险分级（LOW/MEDIUM/HIGH）
- **对话历史** (`history/store.py`)：会话创建、消息记录、持久化

### 已完成 ✅

- [x] **CostBudget 账户级上限** (`core/agent.py`, `llm/cost_tracker.py`)：`Agent.run()` 启动前检查预算；`~/.devflow/budget.json` 持久化累计；周/5小时双窗口重置
- [x] **响应流处理** (`api/server.py`, `core/agent.py`)：`/api/run/stream` SSE 端点；Agent 发射 plan/batch_start/step_start/step_complete/complete 事件
- [x] **分布式执行** (`core/agent.py`)：Planner 生成 `depends_on` 依赖关系；Agent `_execute_parallel()` 批处理调度；共享上下文追加

### 待完成

- [ ] **LSP 集成**：Diagnostic 结构已设计，但未对接实际 LSP 客户端

---

## 已知债务（TODO）

| 问题 | 位置 | 优先级 | 状态 |
|------|------|--------|------|
| ~~CostBudget 未接入 Agent~~ | ~~`core/agent.py`, `llm/cost_tracker.py`~~ | ~~🔴 高~~ | ✅ **已完成** |
| ~~RepoMap 未完全替代 scanner~~ | ~~`repo/repomap.py` vs `repo/scanner.py`~~ | ~~🟡 中~~ | ✅ **已完成** |
| ~~多语言 Tree-sitter 支持~~ | ~~`repo/parser.py`~~ | ~~🟡 中~~ | ✅ **已完成** |
| ~~响应流式输出~~ | ~~`api/server.py`, `core/agent.py`~~ | ~~🟢 低~~ | ✅ **已完成** |
| ~~分布式执行~~ | ~~`core/agent.py`~~ | ~~🟢 低~~ | ✅ **已完成** |
| LSP 集成 | `core/verifier.py` | 🟢 低 | ⏳ 待实现 |

---

*最后更新：2026-05-18*
