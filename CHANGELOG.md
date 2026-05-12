# CHANGELOG

## v0.1.0 (2026-05-12)

### 🚀 核心功能

- Agent 引擎：ReAct + Plan-Execute 循环，自动规划→执行→验证
- 9 个 LLM 工具：文件读写、精确编辑、Shell 执行、代码搜索、Git 操作
- RepoMap：基于 Tree-sitter 的项目结构理解和智能上下文构建
- 分层重试 + 卡住检测：步骤失败自动换策略，兜圈子自动终止
- 预算保护：$20/周 + $3.5/5h 上限，超限自动拒绝

### 🌐 界面

- CLI：`devflow run` / `devflow analyze` / `devflow config show`
- Web UI：深色主题，任务模板快捷填入

### 🧪 质量

- 25 个测试用例，70% 覆盖率
- GitHub Actions CI：ruff + pytest
- 多轮 Agent 审查：Momus 计划审查、Oracle 架构审查、Metis 模糊点审查

### 📄 技术栈

- Python 3.11+ / DeepSeek V4 Flash / FastAPI / Gradio / Click / Rich
- Tree-sitter 代码解析 / GitPython / pydantic-settings
