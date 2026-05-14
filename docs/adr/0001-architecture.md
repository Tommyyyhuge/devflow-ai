# ADR-001: 使用 ReAct + Plan-Execute-Verify 架构

## 状态
已接受

## 背景
DevFlow 需要一个 AI Agent 架构来执行编程任务。需要平衡自动化程度和可控性。

## 决策
采用三层架构：
1. **Planner**: 将自然语言任务拆解为步骤（read/write/verify）
2. **Executor**: ReAct 循环执行每个步骤
3. **Verifier**: 验证执行结果，支持重试

## 替代方案
- **纯 ReAct**: 过于自由，步骤不透明
- **固定流水线**: 不够灵活，无法适应不同任务

## 后果
- ✅ 步骤可追踪、可验证
- ✅ 失败时可定位到具体步骤
- ⚠️ Planner 依赖 LLM 的 JSON 输出稳定性

---

# ADR-002: DeepSeek V4 Flash 作为统一模型

## 状态
已接受

## 背景
需要选择 LLM 提供商，平衡成本和性能。

## 决策
统一使用 DeepSeek V4 Flash：
- 成本远低于 GPT-4/Claude
- 支持 thinking 模式
- OpenAI 兼容协议

## 后果
- ✅ 单任务成本 <$0.01
- ✅ 无需维护多模型逻辑
- ⚠️ 需处理 API 稳定性问题（已实现重试）

---

# ADR-003: CLI + Web UI 双界面

## 状态
已接受

## 背景
目标用户包括命令行爱好者和偏好 GUI 的开发者。

## 决策
- CLI: Click + Rich（快速交互）
- Web UI: FastAPI + Jinja2（浏览器访问）
- 共享 core/ 层

## 后果
- ✅ 覆盖两种用户群体
- ✅ 核心业务逻辑复用
- ⚠️ 需要维护两套界面

---

# ADR-004: Tree-sitter 代码解析

## 状态
已接受

## 背景
需要理解项目结构来构建 LLM 上下文。

## 决策
使用 Tree-sitter：
- 比正则解析更精确
- 支持多语言（通过 LanguageProvider 抽象）
- 增量缓存减少重复解析

## 后果
- ✅ 准确的符号提取
- ✅ 可扩展多语言支持
- ⚠️ 增加了原生依赖（tree-sitter-python）

---

*创建于 2026-05-13*
*最后更新 2026-05-13*
