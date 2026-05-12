# OhMyOpenCode（oh-my-openagent）完全使用教程

> **适用版本**：OhMyOpenCode v1.x | **更新日期**：2026-05-11  
> **官方仓库**：[code-yeongyu/oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent)  
> **官方文档**：[ohmyopenagent.com/docs](https://ohmyopenagent.com/docs) | [ohmyopencode.org](https://ohmyopencode.org/en/docs)

---

## 目录

1. [什么是 OhMyOpenCode](#1-什么是-ohmyopencode)
2. [安装方法](#2-安装方法)
3. [架构总览](#3-架构总览)
4. [四大核心智能体](#4-四大核心智能体)
   - [Sisyphus（西西弗斯）— 总指挥](#41-sisyphus西西弗斯--总指挥)
   - [Prometheus（普罗米修斯）— 规划师](#42-prometheus普罗米修斯--规划师)
   - [Hephaestus（赫菲斯托斯）— 工匠](#43-hephaestus赫菲斯托斯--工匠)
   - [Atlas（阿特拉斯）— 研究者](#44-atlas阿特拉斯--研究者)
5. [辅助智能体](#5-辅助智能体)
6. [Category（执行分类）详解](#6-category执行分类详解)
7. [我的 Skill（技能）清单](#7-我的-skill技能清单)
8. [Slash 命令速查表](#8-slash-命令速查表)
9. [如何切换模式 / 智能体](#9-如何切换模式--智能体)
10. [配置文件说明](#10-配置文件说明)
11. [Sisyphus 调度逻辑解密](#11-sisyphus-调度逻辑解密)
12. [实战场景示例](#12-实战场景示例)
13. [高级技巧](#13-高级技巧)

---

## 1. 什么是 OhMyOpenCode

OhMyOpenCode（npm 包名 `oh-my-openagent`）是一个 **多智能体协作框架**，通过希腊神话命名的多个 AI 智能体协同工作，把一个复杂需求自动拆解、规划、执行和验收。

**核心理念：你不是在和"一个 AI"对话，而是在和一个 AI 团队合作。**

- 每次对话，你面对的是 **Sisyphus（总指挥）**
- Sisyphus 内部会自动调度：规划师（Prometheus）→ 研究员（Atlas）→ 工匠（Hephaestus）
- 你只需要说需求，不需要管"谁来做"

---

## 2. 安装方法

### 前提条件
- 已安装 [OpenCode](https://opencode.ai) 编辑器
- 配置好 API Key（如 DeepSeek）

### 安装步骤

```bash
# 在 OpenCode 配置目录下安装
cd ~/.config/opencode
npm install oh-my-openagent@latest
```

然后在 `opencode.json` 中添加插件声明：

```json
{
  "plugin": [
    "oh-my-openagent@latest"
  ]
}
```

安装成功后，`oh-my-openagent.json` 会自动生成在配置目录中。

---

## 3. 架构总览

```
你（用户）
  │
  └── 🔱 Sisyphus（总指挥）← 你始终对话的对象
         │
         ├── 理解需求阶段
         │   ├── Metis —— 预分析模糊需求
         │   └── Momus —— 审查计划质量
         │
         ├── 规划阶段
         │   └── 📋 Prometheus —— 出结构化工作计划
         │
         ├── 研究阶段
         │   ├── 📚 Librarian —— 搜索外部文档/开源代码
         │   ├── 🔍 Explore —— 搜索当前项目代码
         │   └── 🧠 Oracle —— 高难度架构/调试顾问
         │
         └── 执行阶段
             ├── ⚒️ Hephaestus 系列（Category 子代理）
             │   ├── deep —— 复杂任务自主执行
             │   ├── visual-engineering —— 前端/UI/样式
             │   ├── ultrabrain —— 高难度逻辑
             │   ├── quick —— 简单修改
             │   └── ...
             └── Sisyphus-Junior —— 单任务执行助手
```

---

## 4. 四大核心智能体

### 4.1 Sisyphus（西西弗斯）— 总指挥

| 属性 | 说明 |
|------|------|
| **角色定位** | 项目总指挥，你唯一的对话入口 |
| **核心职责** | 理解需求 → 拆解任务 → 分派子代理 → 验收结果 |
| **工作哲学** | "像推石头一样，把大任务碾碎，分给最擅长的人" |
| **默认模型** | `deepseek-v4-pro`（强推理模型） |

**Sisyphus 不是写代码的，是管写代码的人的。**

当你提出需求时，Sisyphus 会：

1. **Phase 0 - 意图识别**：判断你是要查资料、做规划、还是直接实现
2. **Phase 1 - 代码库评估**：了解项目风格、历史、约定
3. **Phase 2A - 探索研究**：派出 Atlas 系列搜集信息
4. **Phase 2B - 执行实现**：拆任务 → 派 Hephaestus 系列并行执行
5. **Phase 3 - 完成验收**：检查诊断、运行测试、确认通过

**如何与 Sisyphus 对话：**

```
# 默认模式 — 你已经在用
"帮我实现一个用户注册功能"
"这个项目里认证是怎么做的？"
"帮我查一下 React 19 的新特性"
```

---

### 4.2 Prometheus（普罗米修斯）— 规划师

| 属性 | 说明 |
|------|------|
| **角色定位** | 只读规划顾问，出结构化的执行蓝图 |
| **核心职责** | 分析需求 → 拆解步骤 → 识别依赖 → 输出可执行计划 |
| **何时触发** | Sisyphus 判断任务复杂时自动调用，或你主动要求 |

**触发方式：**

```
# 方式一：主动要求规划
"帮我规划一下用户认证系统的开发"
"先出个计划，别急着写代码"

# 方式二：使用 /start-work 命令
/start-work
```

**Prometheus 输出示例结构：**

```
工作计划：用户认证系统
├── Step 1: 数据库模型设计（User, Session 表）
├── Step 2: 注册接口（POST /api/auth/register）
├── Step 3: 登录接口（POST /api/auth/login）
├── Step 4: JWT 中间件
├── Step 5: 前端登录页面
├── Step 6: 集成测试
└── Step 7: 文档更新
```

> 💡 **建议**：复杂功能先让 Prometheus 出计划，确认无误后再执行，避免返工。

---

### 4.3 Hephaestus（赫菲斯托斯）— 工匠

| 属性 | 说明 |
|------|------|
| **角色定位** | 火神工匠，实际写代码的人 |
| **核心职责** | 代码实现、Bug 修复、重构、构建 |
| **何时触发** | Sisyphus 自动调度，你不需要手动切换 |

> ⚠️ **Hephaestus 不是一个可以手动切换的"模式"**，它是 Sisyphus 在执行阶段自动调用的工人团队。

**Hephaestus 团队（Category 子代理）见 [第 6 节](#6-category执行分类详解)。**

---

### 4.4 Atlas（阿特拉斯）— 研究者

| 属性 | 说明 |
|------|------|
| **角色定位** | 擎天巨人，信息收集与知识整合 |
| **核心职责** | 搜索文档、查阅源码、上下文分析 |
| **何时触发** | Sisyphus 在规划和执行前自动调度 |

**Atlas 团队包含：**

| 子代理 | 功能 | 触发场景 |
|--------|------|----------|
| **Librarian** | 搜索外部文档、GitHub 开源示例、Context7 官方 API 文档 | "这个库怎么用？" |
| **Explore** | 搜索你当前项目的代码（上下文 grep） | "项目中哪里用了 JWT？" |
| **Oracle** | 只读高智商顾问，架构评审和疑难调试 | 连续 3 次修复失败后 |

---

## 5. 辅助智能体

| 智能体 | 角色 | 用途 |
|--------|------|------|
| **Oracle** | 高智商顾问（只读） | 架构决策、复杂调试、安全审查 |
| **Momus** | 计划审查员 | 评估工作计划的清晰度和完整性 |
| **Metis** | 预分析顾问 | 分析模糊需求，找出隐藏意图和 AI 失败点 |
| **Sisyphus-Junior** | 任务执行助手 | 实现阶段被 Sisyphus 派去执行单个任务 |
| **Multimodal-Looker** | 多媒体分析 | 分析 PDF、图片、图表等内容 |

---

## 6. Category（执行分类）详解

当 Sisyphus 进入执行阶段，会根据任务类型选择对应的 Category。**Category 决定了子代理的能力配置和模型选择。**

### 高算力 Category（使用 `deepseek-v4-pro`）

| Category | 适用场景 | 举例 |
|----------|----------|------|
| **deep** | 复杂任务，需要自主深度研究和端到端实现 | 多文件重构、新功能开发 |
| **visual-engineering** | 前端、UI/UX、样式、动画 | 改页面布局、加动画效果 |
| **ultrabrain** | 真正的高难度逻辑问题 | 算法设计、架构决策 |
| **artistry** | 需要跳出框架的创造性方案 | 非常规设计问题 |
| **unspecified-high** | 不属以上类别的高难度任务 | 综合性强的工作 |

### 低算力 Category（使用 `deepseek-v4-flash`，更快更省）

| Category | 适用场景 | 举例 |
|----------|----------|------|
| **quick** | 简单任务，单文件修改 | 改 typo、小修小补 |
| **writing** | 文档、技术写作 | 写 README、注释 |
| **unspecified-low** | 不属以上类别的简单任务 | 轻量级修改 |

**如何指定 Category：**

你一般不需要手动指定，Sisyphus 会自动判断。但如果你想，可以这样：

```
# 强制指定某个 Category（高级用法，一般不推荐）
"用 visual-engineering 模式重新设计这个侧边栏"
```

---

## 7. 我的 Skill（技能）清单

Skill 是注入到子代理中的专业指令集，类似"技能书"——加载后子代理会获得该领域的专业知识。

### 项目级 Skill（D:\\.agents\skills\ 和 D:\\.claude\skills\）

| 技能 | 描述 | 触发词 |
|------|------|--------|
| **chinese-novelist** | 分章节创作中文小说 | "写小说"、"创作故事" |
| **diagnose** | 系统化调试循环（复现→精简→假设→检测→修复→回归） | "调试这个"、"diagnose this" |
| **grill-me** | 对你的计划/设计进行持续追问直到达成共识 | "grill me"、"追问我的方案" |
| **grill-with-docs** | 结合项目文档冲击你的方案，同步更新文档 | 需要结合文档做设计评审 |
| **improve-codebase-architecture** | 发现代码库中可优化的架构机会 | "优化架构"、"重构" |
| **setup-matt-pocock-skills** | 初始化工程技能所需的 issue 追踪器和标签体系 | 首次使用其他工程技能前 |
| **tdd** | 测试驱动开发（红-绿-重构循环） | "用 TDD 开发"、"测试驱动" |
| **to-issues** | 将计划/PRD 拆解为独立可认领的 issue | "拆成 issue" |
| **to-prd** | 将当前对话上下文转为 PRD | "生成 PRD" |
| **triage** | 按状态机流程处理 issue 分类 | "整理 issue" |
| **write-a-skill** | 创建新的 agent Skill | "创建 skill" |
| **zoom-out** | 拉远视角，理解代码的全局上下文 | "zoom out"、"大局观" |

### 用户级 Skill（C:\Users\lenovo\\.claude\skills\ 和 .agents\skills\）

| 技能 | 描述 |
|------|------|
| **caveman** | 极简输出模式，砍掉 ~75% 的 token |
| **prototype** | 快速原型开发（终端版/UI 多方案切换） |
| **lhl-novel-xp** | 成人小说写作约束与场景图鉴 |

### 内置 Skill

| 技能 | 描述 |
|------|------|
| **frontend-ui-ux** | 设计师转前端，无需设计稿也能出精美 UI |
| **git-master** | 所有 Git 操作的专家（commit、rebase、squash、blame 等） |
| **review-work** | 实现后的审查编排器，启动 5 个并行子代理全面审查 |
| **ai-slop-remover** | 去除 AI 生成的代码异味（单文件） |

---

## 8. Slash 命令速查表

### 工作模式切换

| 命令 | 功能 | 何时用 |
|------|------|--------|
| `/caveman` | 极简输出模式 | 想省 token、要简洁回复 |
| `/start-work` | 从 Prometheus 计划启动执行 | 先规划后执行 |
| `/ralph-loop` | 自主循环模式（持续工作直到完成） | 大任务不想反复确认 |
| `/ulw-loop` | UltraWork 循环模式 | 同上，高强度版本 |
| `/stop-continuation` | 停止所有循环和待办续行 | 中止自动任务 |

### 规划与设计

| 命令 | 功能 |
|------|------|
| `/hyperplan` | 多代理对抗式规划（5 个 agent 互怼后出最佳方案） |
| `/prototype` | 快速原型（终端版或 UI 多方案对比） |
| `/grill-me` | 追问式方案评审 |
| `/grill-with-docs` | 结合文档做设计评审 |

### 开发流程

| 命令 | 功能 |
|------|------|
| `/tdd` | 测试驱动开发 |
| `/refactor` | 智能重构（LSP + AST + TDD 验证） |
| `/code-review` | 代码审查 |
| `/remove-ai-slops` | 去除分支中所有 AI 代码异味 |
| `/build-fix` | 自动修复构建/类型错误 |

### 工程管理

| 命令 | 功能 |
|------|------|
| `/to-issues` | 计划/PRD → 独立 issue |
| `/to-prd` | 对话上下文 → PRD 文档 |
| `/triage` | Issue 分类管理 |
| `/handoff` | 生成交接文档（供新会话继续工作） |

### 知识管理

| 命令 | 功能 |
|------|------|
| `/zoom-out` | 拉远视角看代码全局 |
| `/improve-codebase-architecture` | 发现架构优化机会 |
| `/learn-codebase` | 通读整个代码库 |
| `/setup-matt-pocock-skills` | 初始化工程技能所需配置 |

---

## 9. 如何切换模式 / 智能体

### 核心原则：你不需要手动切换

OhMyOpenCode 的设计哲学是 **"你只管提需求，系统自动路由"**。Sisyphus 是你唯一的对话对象，其余智能体由它自动调度。

### 但你确实可以"引导"系统行为

| 你想达到的效果 | 操作方式 |
|----------------|----------|
| **切换输出风格** | `/caveman` → 极简模式 |
| **先规划再动手** | 说："先帮我规划一下…" 或 `/start-work` |
| **持续自主工作** | `/ralph-loop` 或 `/ulw-loop` |
| **审查已完成的代码** | `/code-review` 或 `/review-work` |
| **用 TDD 方式开发** | `/tdd` 或说"用 TDD 方式实现" |
| **快速原型验证** | `/prototype` |
| **想换个新模型配置** | 修改 `oh-my-openagent.json` 中的 `model` 字段，重启生效 |

### 如果你想手动切换模型的例子

编辑 `C:\Users\lenovo\.config\opencode\oh-my-openagent.json`：

```json
{
  "agents": {
    "sisyphus": {
      "model": "deepseek/deepseek-v4-pro"  // 改这里
    },
    "oracle": {
      "model": "deepseek/deepseek-v4-pro"  // 也可以给不同 agent 用不同模型
    }
  }
}
```

---

## 10. 配置文件说明

### opencode.json（插件入口）

```json
{
  "plugin": [
    "oh-my-openagent@latest"
  ]
}
```

### oh-my-openagent.json（核心配置）

```json
{
  // === 智能体配置 ===
  "agents": {
    "sisyphus":      { "model": "deepseek/deepseek-v4-pro" },   // 总指挥
    "hephaestus":    { "model": "deepseek/deepseek-v4-pro" },   // 工匠
    "oracle":        { "model": "deepseek/deepseek-v4-pro" },   // 高智商顾问
    "prometheus":    { "model": "deepseek/deepseek-v4-pro" },   // 规划师
    "momus":         { "model": "deepseek/deepseek-v4-pro" },   // 计划审查
    "metis":         { "model": "deepseek/deepseek-v4-pro" },   // 预分析
    "atlas":         { "model": "deepseek/deepseek-v4-pro" },   // 研究者
    "sisyphus-junior": { "model": "deepseek/deepseek-v4-pro" }, // 执行助手
    "multimodal-looker": { "model": "deepseek/deepseek-v4-pro" }, // 多媒体分析
    "librarian":     { "model": "deepseek/deepseek-v4-flash" }, // 文档搜索（轻量）
    "explore":       { "model": "deepseek/deepseek-v4-flash" }  // 代码搜索（轻量）
  },

  // === 执行分类配置 ===
  "categories": {
    "visual-engineering": { "model": "deepseek/deepseek-v4-pro" },
    "ultrabrain":         { "model": "deepseek/deepseek-v4-pro" },
    "deep":               { "model": "deepseek/deepseek-v4-pro" },
    "artistry":           { "model": "deepseek/deepseek-v4-pro" },
    "unspecified-high":   { "model": "deepseek/deepseek-v4-pro" },
    "unspecified-low":    { "model": "deepseek/deepseek-v4-flash" },
    "quick":              { "model": "deepseek/deepseek-v4-flash" },
    "writing":            { "model": "deepseek/deepseek-v4-flash" }
  }
}
```

> 💡 **省钱技巧**：把低频使用的 agent 改成 flash 模型（如 `explore`、`librarian` 已经是 flash），高频决策 agent 保持 pro 模型。

---

## 11. Sisyphus 调度逻辑解密

了解 Sisyphus 的内部决策流程，有助于你写出更高效的 prompt。

### Phase 0 — 意图识别（每条消息都执行）

Sisyphus 首先判断你的意图类型：

| 你的话 | Sisyphus 识别为 |
|--------|----------------|
| "解释一下 X 怎么工作" | **研究/理解** → 派出 explore/librarian → 综合回答 |
| "帮我实现 X" | **实现（明确）** → 进规划→执行流程 |
| "帮我看看 Y" | **调查** → explore 搜索 → 报告发现 |
| "你觉得 X 这样设计怎么样" | **评估** → 分析 → 提建议 → **等你确认** |
| "X 报错了" / "Y 坏了" | **修复** → 诊断 → 最小化修复 |

### Phase 1 — 代码库评估

- 检查 linter/formatter 配置
- 抽样 2-3 个类似文件了解风格
- 判断项目成熟度：**disciplined（规范）** / **transitional（过渡）** / **chaotic（混乱）**

### Phase 2A — 探索研究

自动触发规则：
- 提到外部库 → 触发 **librarian** 搜文档
- 涉及 2+ 模块 → 触发 **explore** 搜代码
- 模糊需求 → 先问 **Metis** 分析

### Phase 2B — 执行实现

**Sisyphus 的黄金法则：永远不亲自写代码，而是拆任务 + 并行派活。**

```
1. 拆解任务为 N 个独立工作单元
2. 同时对 N 个单元派出 N 个子代理（并行执行）
3. 验收每个子代理的结果
4. 汇总报告给你
```

---

## 12. 实战场景示例

### 场景一：开发新功能

```
你："帮我给这个项目加一个用户收藏功能"

Sisyphus 内部流程：
1. explore 搜索项目现有 CRUD 模式
2. Prometheus 出计划（数据库表 → API → 前端）
3. 确认后，并行派活：
   - deep → 数据库 migration
   - deep → API 路由
   - visual-engineering → 前端组件
4. 验收 → 运行测试 → 报告完成
```

### 场景二：调试 Bug

```
你："登录后页面白屏，帮我看看"

Sisyphus 内部流程：
1. explore 搜索登录相关代码
2. 尝试复现 → 缩小范围 → 假设原因
3. 如果 3 次修复失败 → 咨询 Oracle
4. 最小化修复 → 回归测试
```

### 场景三：学习代码库

```
你："这个项目的认证系统是怎么设计的？"

Sisyphus 内部流程：
1. explore 搜索 auth 相关文件
2. librarian 查相关库的文档
3. 综合回答：中间件结构、token 流程、错误处理
```

### 场景四：想省 Token（Caveman 模式）

```
你：/caveman
然后："加个暗色模式"

Sisyphus（极简回复）：
todo: 1) theme store 2) CSS vars 3) toggle btn
开始...
完成。暗色模式已加。
```

---

## 13. 高级技巧

### 技巧 1：善用"先规划"

对所有非 trivial 的需求，先让 Prometheus 出计划：

```
"先帮我规划一下重构支付模块的方案，不要动手写代码"
```

这样你可以审查计划，调整后再执行，避免浪费 token。

### 技巧 2：并行提需求

Sisyphus 会将多个独立任务并行处理：

```
"同时帮我做这三件事：
1. 把 README 更新到最新 API
2. 修复登录页的样式 bug
3. 给 User 模型加一个 avatar 字段"
```

### 技巧 3：给 Oracle 留好上下文

遇到复杂架构问题，直接问：

```
"当前项目用 Express + JWT，我想迁移到 Next.js + NextAuth。
帮我评估风险和迁移步骤。"
```

Sisyphus 会自动咨询 Oracle 来出深度分析。

### 技巧 4：用 Caveman 模式降低消耗

如果只是做简单修改，切换到 Caveman 模式可以省 ~75% token：

```
/caveman
"把 config.js 里 port 改成 8080"
```

### 技巧 5：自定义 Agent 模型

编辑 `oh-my-openagent.json`，给不同 agent 分配不同模型：

```json
{
  "agents": {
    "sisyphus": { "model": "deepseek/deepseek-v4-pro" },
    "oracle":   { "model": "deepseek/deepseek-v4-pro" },
    "explore":  { "model": "deepseek/deepseek-v4-flash" },
    "librarian": { "model": "deepseek/deepseek-v4-flash" }
  }
}
```

- **Pro 模型**：给需要强推理的 agent（Sisyphus、Oracle、Prometheus）
- **Flash 模型**：给搜索型 agent（Explore、Librarian），更快更省钱

---

## 附录：完整智能体/Category 对照表

| 类型 | 名称 | 模型 | 用途 |
|------|------|------|------|
| **核心 Agent** | Sisyphus | pro | 总指挥/调度 |
| **核心 Agent** | Prometheus | pro | 规划师 |
| **核心 Agent** | Hephaestus | pro | 工匠（Category 集合） |
| **核心 Agent** | Atlas | pro | 研究者（子代理集合） |
| **辅助 Agent** | Oracle | pro | 高智商顾问 |
| **辅助 Agent** | Momus | pro | 计划审查 |
| **辅助 Agent** | Metis | pro | 预分析 |
| **辅助 Agent** | Sisyphus-Junior | pro | 单任务执行 |
| **辅助 Agent** | Multimodal-Looker | pro | 多媒体分析 |
| **搜索 Agent** | Librarian | flash | 外部文档搜索 |
| **搜索 Agent** | Explore | flash | 项目代码搜索 |
| **Category** | deep | pro | 复杂自主执行 |
| **Category** | visual-engineering | pro | 前端/UI |
| **Category** | ultrabrain | pro | 高难度逻辑 |
| **Category** | artistry | pro | 创造性方案 |
| **Category** | unspecified-high | pro | 高难度综合 |
| **Category** | quick | flash | 简单修改 |
| **Category** | writing | flash | 文档写作 |
| **Category** | unspecified-low | flash | 简单综合 |

---

> **记住一句话：你是将军，Sisyphus 是你的参谋长。提需求就行，剩下的它来调度千军万马。**
