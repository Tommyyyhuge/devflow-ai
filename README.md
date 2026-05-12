# devflow-ai

低成本的 AI 编程助手 — 基于 DeepSeek V4 Flash，内置预算上限。

## 特性

- 🤖 **AI 编程**：自然语言描述任务，自动规划→执行→验证
- 💰 **极低成本**：基于 DeepSeek V4 Flash，单任务 < $0.01
- 🛡️ **预算上限**：内置 $20/周 + $3.5/5h 预算保护
- 🔧 **9 个工具**：文件读写/编辑、Shell 执行、代码搜索、Git 操作
- 🌐 **双界面**：CLI + Web UI

## 安装

```bash
# 创建 conda 环境
conda create -n devflow python=3.11 -y
conda activate devflow

# 安装
pip install devflow-ai
```

或从源码：
```bash
git clone https://github.com/你的用户名/devflow-ai
cd devflow-ai
pip install -e ".[dev]"
```

## 配置

```bash
# 设置 DeepSeek API Key
export DEEPSEEK_API_KEY=sk-your-key-here
```

或创建 `.env` 文件。

## 使用

### CLI

```bash
# 分析项目
devflow analyze

# 执行编程任务
devflow run "在 src/api/ 下添加 /health 健康检查端点"

# 查看配置
devflow config show
```

### Web UI

```bash
devflow web
# 浏览器打开 http://localhost:8000
```

## 许可证

MIT
