# Web 文件夹上传功能设计

> 日期：2026-05-12 | 版本：v1

## 目标

用户在 Web UI 上拖拽/选择文件夹上传到 devflow-ai，Agent 在已上传的项目上执行编程任务。

## 架构

### 新增端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/upload` | POST | 接收 zip 压缩包，解压到持久目录 |
| `/api/projects` | GET | 列出已上传的项目 |
| `/api/projects/{name}` | DELETE | 删除已上传项目 |

### 修改端点

| 端点 | 变更 |
|------|------|
| `/api/run` | `repo_path` 改为可选的 `project` 参数，映射到 `./uploads/{project}` |

### 前端变更（PAGE HTML）

1. 新增拖拽上传区（虚线框 + 点击选择）
2. 前端用 JSZip 将文件夹打包为 zip → 上传
3. 上传进度条（文件名流水显示）
4. 项目选择器下拉框（从 `/api/projects` 获取列表）
5. 项目信息栏（文件数、最后修改时间）

### 存储

```
./uploads/              # 持久目录（加入 .gitignore）
├── project-a/          # 用户上传的项目
├── project-b/
└── ...
```

## 数据流

```
用户拖拽文件夹 → JSZip 打包 → POST /api/upload (zip)
→ 后端解压到 ./uploads/{name}/
→ 前端刷新项目列表 (GET /api/projects)
→ 用户选择项目 → 填写任务 → POST /api/run {project: "name", task: "..."}
→ Agent 在 ./uploads/{name}/ 上执行
```

## 实现计划

### 后端（server.py）
1. 新增 `/api/upload`：接收 zip，解压到 `./uploads/`，去重覆盖
2. 新增 `/api/projects`：扫描 `./uploads/` 返回项目列表
3. 修改 `TaskRequest`：增加 `project` 可选字段
4. 修改 `/api/run`：`project` 存在时映射路径

### 前端（PAGE HTML）
1. 上传区：虚线框 + 拖拽事件 + 隐藏的 `<input type="file" webkitdirectory>`
2. JSZip CDN 引入，打包文件夹为 zip
3. 上传进度：fetch + 文件名流水
4. 项目选择器：`<select>` 从 `/api/projects` 填充
5. 项目信息栏：文件数 + 修改时间

### 依赖

- 后端：已内置（`zipfile`, `shutil` 均为标准库）
- 前端：JSZip（CDN 引入，无 npm 依赖）

## 测试

1. 上传小文件夹（3-5 文件），验证解压正确
2. 上传同名项目，验证覆盖行为
3. 项目列表正确显示
4. 选择项目后执行 Agent 任务

## 风险

| 风险 | 应对 |
|------|------|
| 大文件夹上传超时 | 限制 50MB/100 文件 |
| zip 炸弹（压缩比极高） | 限制解压后总大小 <100MB |
| 项目名带特殊字符 | sanitize 文件名 |
