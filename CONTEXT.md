# DevFlow 项目语境

## 核心术语

| 术语 | 定义 |
|------|------|
| **可落地** | 可开源推广——具备完整文档、测试覆盖、CI/CD、pip install 即可用、GitHub 发布标准 |
| **DevFlow** | 项目代号。最终发布名：**devflow-ai**（PyPI + GitHub） |
| **低成本** | DevFlow 核心差异化——基于 DeepSeek V4 Flash，目标将 AI 编程助手的单任务成本降到远低于竞品。内置预算上限机制 |
| **预算上限** | 用户可配置的 Token 费用上限。默认：周上限 $20，5小时上限 $3.5。超出后 Agent 拒绝新任务 |

## 关键决策

- 验收标准：开源推广级别（非 Demo、非仅自用）
- CI/CD：Week 1 Day 1 引入 GitHub Actions，从第一天起跑 lint + test
- 许可证：MIT
- 模型策略：DeepSeek V4 Flash + thinking（MVP 统一模型）
- 语言：Python 3.11+（Conda 虚拟环境 devflow）
- 目标用户：开发者/技术团队
- Week 1 里程碑：L3——能读取现有项目结构 → 添加 REST 端点 → 运行测试通过
- 项目理解策略：Week 1 用简化版（文件列表+grep），Week 2 引入完整 Tree-sitter
- 接口形式：CLI + Web UI（FastAPI + 轻量前端）
