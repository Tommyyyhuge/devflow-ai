# devflow-ai

> 🤖 低成本的 AI 编程助手 · DeepSeek V4 Flash · 内置预算保护
>
> ⚠️ **练习项目**：devflow-ai 是我学习 AI Agent 开发过程中的实践作品。通过与 AI 对话完成需求分析、架构设计、代码实现和迭代审查的全流程，探索「AI 辅助软件开发」的最佳实践。

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-25%20passed-brightgreen.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-70%25-yellow.svg)](tests/)

---

## 为什么用 devflow-ai？

| | devflow-ai | Aider + GPT-4o | Cline + Claude | Copilot |
|---|---|---|---|---|
| **单任务成本** | ~$0.005 | ~$0.50-2 | ~$1-5 | $10/月 |
| **模型** | DeepSeek V4 Flash | GPT-4o | Claude | GPT-4o |
| **开源** | ✅ MIT | ✅ Apache 2.0 | ✅ Apache 2.0 | ❌ |
| **预算保护** | ✅ | ❌ | ❌ | ❌ |
| **本地运行** | ✅ | ✅ | ✅ | ❌ |

---

## 特性

- 🤖 **自然语言编程** — 描述需求，Agent 自动规划→编写→验证
- 💰 **极低成本** — DeepSeek V4 Flash，单任务 < 1 美分
- 🛡️ **预算上限** — 内置 $20/周 + $3.5/5h 保护
- 🔧 **9 个工具** — 文件读写、精确编辑、Shell、搜索、Git
- 📊 **RepoMap** — Tree-sitter 解析项目结构，智能上下文
- 🌐 **CLI + Web UI** — 双界面，深色主题
- 🧪 **自动验证** — 语法检查、分层重试、卡住检测

---

## 安装

```bash
conda create -n devflow python=3.11 -y
conda activate devflow
git clone https://github.com/Tommyyyhuge/devflow-ai.git
cd devflow-ai
pip install -e ".[dev]"
```

## 配置

```bash
# 申请 Key: https://platform.deepseek.com
set DEEPSEEK_API_KEY=sk-your-key-here
```

## 使用

```bash
devflow analyze                    # 分析项目结构
devflow run "创建 hello.py"        # 执行编程任务
devflow web                        # 启动 Web UI
devflow config show                # 查看配置
```

---

## 项目结构

```
src/devflow/
├── core/           # Agent 引擎（规划→执行→验证）
├── tools/          # 9 个 LLM 工具
├── repo/           # Tree-sitter + RepoMap 代码理解
├── llm/            # DeepSeek 客户端
├── api/            # FastAPI + Web UI
└── main.py         # CLI 入口
```

## 开发历程

此项目通过 AI Agent 辅助完成全部需求分析、架构设计和代码实现：

- **11 轮独立 Agent 审查**（Momus 计划审查、Oracle 架构审查、Metis 模糊点审查）
- 累计修复 **30+ 个设计缺陷**
- 详细设计文档见 `.sisyphus/plans/devflow-plan.md`

## 许可证

MIT © 2026 — 练习项目，欢迎交流。
