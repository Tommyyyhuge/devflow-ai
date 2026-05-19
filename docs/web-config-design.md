# Web 端配置功能设计文档

## 1. 概述

在 Web UI 中添加完整的配置管理功能，支持用户在网页端设置和修改所有配置项。

## 2. 架构设计

### 2.1 数据流
```
用户修改配置 → 前端验证 → POST /api/config → 后端验证 → 加密敏感字段 → 
保存到 JSON 文件 → 更新内存配置 → 返回成功
```

### 2.2 存储方案
- **运行时**：内存中的 Pydantic 模型（与现有机制一致）
- **持久化**：JSON 文件（`~/.devflow/config.json`），API Key 加密存储
- **加密方式**：Fernet 对称加密（Python cryptography 库）

## 3. API 设计

### 3.1 获取配置
```
GET /api/config
```
**响应**：
```json
{
  "llm": {
    "name": "default",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-v4-flash",
    "max_tokens_per_request": 8000
  },
  "agent": {
    "context_budget": 140000,
    "code_context_budget": 60000,
    "auto_confirm": false,
    "ask_on_failure": true
  },
  "budget": {
    "weekly_budget": 20.0,
    "budget_per_5h": 3.5
  },
  "router": {
    "enabled": true,
    "strategy": "smart"
  },
  "log_level": "INFO"
}
```
**注意**：响应中不包含 API Key（安全考虑）

### 3.2 更新配置
```
POST /api/config
```
**请求体**：
```json
{
  "llm": {
    "api_key": "sk-...",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-v4-flash",
    "max_tokens_per_request": 8000
  },
  "agent": {
    "context_budget": 140000,
    "auto_confirm": false
  }
}
```
**说明**：只更新提供的字段，未提供的字段保持原值。

### 3.3 测试连接
```
POST /api/config/test
```
**请求体**：
```json
{
  "api_key": "sk-...",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-v4-flash"
}
```
**响应**：
```json
{
  "success": true,
  "message": "连接成功",
  "model": "deepseek-v4-flash",
  "balance": 100.00
}
```

## 4. 数据模型

### 4.1 配置存储格式（JSON）
```json
{
  "llm": {
    "name": "default",
    "api_key_encrypted": "gAAAAAB...",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-v4-flash",
    "max_tokens_per_request": 8000
  },
  "agent": {
    "context_budget": 140000,
    "code_context_budget": 60000,
    "auto_confirm": false,
    "ask_on_failure": true
  },
  "budget": {
    "weekly_budget": 20.0,
    "budget_per_5h": 3.5
  },
  "router": {
    "enabled": true,
    "strategy": "smart"
  },
  "log_level": "INFO",
  "version": "1.0"
}
```

### 4.2 加密密钥管理
- 加密密钥存储在：`~/.devflow/.encryption_key`
- 密钥生成：首次启动时自动生成 32 字节随机密钥
- 算法：Fernet（AES-128-CBC + HMAC）

## 5. 前端设计

### 5.1 设置页面布局
```
/settings
├── 页面标题：系统设置
├── LLM 配置卡片
│   ├── API Key（密码输入框 + 显示/隐藏按钮）
│   ├── API 端点（文本输入）
│   ├── 模型选择（下拉框）
│   └── Max Tokens（数字输入 + 滑块）
├── Agent 配置卡片
│   ├── 上下文预算（数字输入）
│   ├── 代码上下文预算（数字输入）
│   ├── 自动确认（开关）
│   └── 失败时询问（开关）
├── 预算配置卡片
│   ├── 周预算（数字输入）
│   └── 5小时预算（数字输入）
├── 日志配置卡片
│   └── 日志级别（下拉框：DEBUG/INFO/WARNING/ERROR）
└── 操作按钮栏
    ├── 测试连接（次要按钮）
    ├── 重置默认（次要按钮）
    └── 保存配置（主要按钮）
```

### 5.2 交互设计
1. **表单验证**：实时验证输入格式（URL、数字范围等）
2. **测试连接**：点击后显示加载状态，验证 API Key 有效性
3. **保存成功**：显示 Toast 提示，3 秒后自动消失
4. **未保存提示**：离开页面时如有未保存修改，弹出确认对话框

## 6. 安全考虑

1. **API Key 加密**：使用 Fernet 对称加密存储
2. **传输安全**：假设使用 HTTPS（生产环境）
3. **内存安全**：API Key 在内存中解密后使用，进程结束后清除
4. **访问控制**：当前无用户认证，配置对所有访问者可见（开发环境可接受）

## 7. 实现步骤

1. 添加 cryptography 依赖
2. 创建加密工具模块
3. 修改 Config 类支持保存和加载
4. 添加 API 端点（GET/POST /api/config, POST /api/config/test）
5. 创建前端设置页面
6. 添加测试用例

## 8. 回滚策略

- 保存前备份旧配置到 `config.json.bak`
- 加载失败时回退到 .env 文件配置
- 提供"重置默认"功能

## 9. 测试要点

1. 配置保存和加载
2. API Key 加密和解密
3. 字段验证（边界值、非法值）
4. 测试连接（成功/失败场景）
5. 并发修改处理
