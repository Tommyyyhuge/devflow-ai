"""新功能脚手架 — 任务模板 + 项目初始化 + 建议引擎

功能说明：
1. 内置任务模板库（API 端点、CLI 命令、新模块、测试等）
2. 根据项目上下文智能推荐最合适的模板
3. 生成新功能的实施计划（集成 Planner）
4. 提供脚手架代码生成（文件结构 + 样板代码）

使用示例：
    from devflow.new_feature import FeatureScaffold, TaskTemplate

    scaffold = FeatureScaffold(repo_path=".")
    templates = scaffold.suggest_templates(task="创建一个用户认证模块")
    plan = scaffold.generate_plan(templates[0], task="用户认证模块")
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class TemplateCategory(str, Enum):
    """任务模板分类"""
    API_ENDPOINT = "api_endpoint"       # 新增 API 路由
    CLI_COMMAND = "cli_command"         # 新增 CLI 命令
    NEW_MODULE = "new_module"           # 新增 Python 模块
    NEW_CLASS = "new_class"             # 新增类
    TEST = "test"                       # 添加测试
    CONFIG = "config"                   # 添加配置
    SCHEMA = "schema"                   # 添加数据模型/模式
    MIGRATION = "migration"             # 代码迁移/重构
    FIX = "fix"                         # 修复问题
    OTHER = "other"                     # 其他


@dataclass
class TemplateFile:
    """模板中的文件定义"""
    path: str                              # 相对项目根目录的路径
    content: str = ""                      # 文件内容（支持 {placeholder} 模板）
    template: str = ""                     # Jinja2 风格模板字符串（备选）
    overwrite: bool = False                # 是否允许覆写已有文件
    after_existing: str | None = None      # 如果文件已存在，在指定内容后追加


@dataclass
class TaskTemplate:
    """任务模板 — 描述一类常见开发任务的结构化信息"""
    id: str                                # 模板唯一标识
    name: str                              # 模板名称
    category: TemplateCategory             # 模板分类
    description: str                       # 模板描述
    keywords: list[str] = field(default_factory=list)  # 匹配关键词
    prerequisites: list[str] = field(default_factory=list)  # 前置条件检查
    files: list[TemplateFile] = field(default_factory=list)  # 要创建/修改的文件
    steps: list[str] = field(default_factory=list)       # 实施步骤
    requirements: list[str] = field(default_factory=list)  # 依赖/Python 包

    def match_score(self, task: str, project_context: str = "") -> float:
        """计算模板与任务的匹配度（0.0 ~ 1.0）"""
        score = 0.0
        task_lower = task.lower()

        # 关键词匹配
        for kw in self.keywords:
            if kw.lower() in task_lower:
                score += 0.3

        # 类别关键词额外匹配
        category_keywords = {
            TemplateCategory.API_ENDPOINT: ["api", "endpoint", "route", "rest", "http", "接口"],
            TemplateCategory.CLI_COMMAND: ["cli", "command", "命令行", "console"],
            TemplateCategory.NEW_MODULE: ["module", "模块", "package", "包"],
            TemplateCategory.NEW_CLASS: ["class", "对象", "component", "组件"],
            TemplateCategory.TEST: ["test", "测试", "unittest", "pytest"],
            TemplateCategory.CONFIG: ["config", "配置", "setting", "环境"],
            TemplateCategory.SCHEMA: ["schema", "model", "数据模型", "pydantic"],
            TemplateCategory.MIGRATION: ["migrate", "重构", "refactor", "升级"],
            TemplateCategory.FIX: ["fix", "修复", "bug", "issue", "错误"],
        }
        for ck in category_keywords.get(self.category, []):
            if ck in task_lower:
                score += 0.2

        # 项目上下文匹配（检测项目中已有的模式）
        if project_context:
            if self.category == TemplateCategory.API_ENDPOINT and "api" in project_context.lower():
                score += 0.15
            if self.category == TemplateCategory.TEST and "test" in project_context.lower():
                score += 0.15
            if self.category == TemplateCategory.CLI_COMMAND and "cli" in project_context.lower():
                score += 0.15

        return min(score, 1.0)


@dataclass
class ScaffoldPlan:
    """脚手架生成计划"""
    template: TaskTemplate
    task_description: str
    steps: list[str] = field(default_factory=list)
    files_to_create: list[TemplateFile] = field(default_factory=list)
    files_to_modify: list[TemplateFile] = field(default_factory=list)
    estimated_effort: str = "medium"       # "easy" | "medium" | "hard"
    warnings: list[str] = field(default_factory=list)


class TemplateRegistry:
    """内置模板注册表"""

    def __init__(self):
        self._templates: dict[str, TaskTemplate] = {}
        self._register_defaults()

    def _register_defaults(self):
        """注册内置模板"""
        defaults = [
            TaskTemplate(
                id="new_api_endpoint",
                name="新增 API 端点",
                category=TemplateCategory.API_ENDPOINT,
                description="在 FastAPI/Flask 项目中新增一个 REST API 端点",
                keywords=["api", "endpoint", "route", "rest", "接口", "路由"],
                prerequisites=["检测到 FastAPI 或 Flask 框架"],
                steps=[
                    "1. 创建路由处理函数文件",
                    "2. 在主路由注册文件中导入并注册新路由",
                    "3. 创建对应的 Pydantic 请求/响应模型（如需要）",
                    "4. 添加参数验证和错误处理",
                    "5. 运行服务并测试端点",
                ],
                files=[
                    TemplateFile(path="src/api/{module_name}.py", content=""),
                    TemplateFile(
                        path="src/api/__init__.py",
                        after_existing="# @@ROUTE_IMPORT@@",
                        content="from .{module_name} import router as {module_name}_router\n",
                    ),
                ],
            ),
            TaskTemplate(
                id="new_cli_command",
                name="新增 CLI 命令",
                category=TemplateCategory.CLI_COMMAND,
                description="在 Click/Typer CLI 应用中新增一个命令",
                keywords=["cli", "command", "命令行", "命令", "click"],
                prerequisites=["检测到 Click 或 Typer 框架"],
                steps=[
                    "1. 创建命令处理函数",
                    "2. 添加参数和选项",
                    "3. 添加到主命令组",
                ],
                files=[
                    TemplateFile(path="src/devflow/commands/{command_name}.py", content=""),
                ],
            ),
            TaskTemplate(
                id="new_python_module",
                name="新增 Python 模块",
                category=TemplateCategory.NEW_MODULE,
                description="在项目中创建一个新的 Python 模块（包）",
                keywords=["module", "模块", "package", "包", "新功能", "feature"],
                steps=[
                    "1. 创建模块目录和 __init__.py",
                    "2. 实现核心功能类/函数",
                    "3. 在模块 __init__.py 中导出公共 API",
                    "4. 编写模块文档字符串",
                ],
                files=[
                    TemplateFile(path="src/{module_path}/__init__.py", content="""\"\"\"{module_description}\"\"\"

from .{core_module} import *  # noqa: F401, F403

__all__: list[str] = []
"""),
                    TemplateFile(path="src/{module_path}/{core_module}.py", content="""\"\"\"{module_description} — 核心实现\"\"\"

from dataclasses import dataclass
from typing import Any


@dataclass
class {class_name}Config:
    \"\"\"{class_name} 配置\"\"\"
    enabled: bool = True
    verbose: bool = False


class {class_name}:
    \"\"\"{class_name} — 核心功能类\"\"\"

    def __init__(self, config: {class_name}Config | None = None):
        self.config = config or {class_name}Config()

    def run(self) -> str:
        \"\"\"执行核心逻辑\"\"\"
        return f"{class_name} 已就绪"
"""),
                ],
            ),
            TaskTemplate(
                id="add_tests",
                name="添加单元测试",
                category=TemplateCategory.TEST,
                description="为现有模块添加 pytest 单元测试",
                keywords=["test", "测试", "unittest", "pytest", "单元测试"],
                prerequisites=["检测到 pytest 依赖"],
                steps=[
                    "1. 创建测试文件",
                    "2. 导入被测试模块",
                    "3. 编写测试用例（正常路径 + 边界情况）",
                    "4. 运行测试验证",
                ],
                files=[
                    TemplateFile(path="tests/test_{module_name}.py", content="""\"\"\"{module_name} 单元测试\"\"\"

import pytest
from {import_path} import {class_name}


class Test{class_name}:
    \"\"\"{class_name} 测试套件\"\"\"

    def setup_method(self):
        \"\"\"每个测试前的初始化\"\"\"
        self.instance = {class_name}()

    def test_initialization(self):
        \"\"\"测试初始化\"\"\"
        assert self.instance is not None
        assert self.instance.config.enabled is True

    def test_run(self):
        \"\"\"测试运行\"\"\"
        result = self.instance.run()
        assert isinstance(result, str)
        assert "就绪" in result

    @pytest.mark.parametrize("verbose", [True, False])
    def test_config_verbose(self, verbose: bool):
        \"\"\"测试详细模式配置\"\"\"
        from {import_path} import {class_name}Config
        config = {class_name}Config(verbose=verbose)
        instance = {class_name}(config)
        assert instance.config.verbose == verbose
"""),
                ],
            ),
            TaskTemplate(
                id="add_pydantic_schema",
                name="添加 Pydantic 数据模型",
                category=TemplateCategory.SCHEMA,
                description="创建 Pydantic 数据模型（请求/响应 Schema）",
                keywords=["schema", "model", "pydantic", "数据模型", "dto"],
                steps=[
                    "1. 创建 Schema 文件",
                    "2. 定义请求模型（继承 BaseModel）",
                    "3. 定义响应模型",
                    "4. 添加字段验证器（如需要）",
                ],
                files=[
                    TemplateFile(path="src/{module_path}/schemas.py", content="""\"\"\"数据模型 — 请求/响应 Schema\"\"\"

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class {name}CreateRequest(BaseModel):
    \"\"\"创建 {name_display} 请求\"\"\"
    name: str = Field(..., min_length=1, max_length=100, description="{name_display}名称")
    description: str = Field("", max_length=500, description="描述")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()


class {name}UpdateRequest(BaseModel):
    \"\"\"更新 {name_display} 请求\"\"\"
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class {name}Response(BaseModel):
    \"\"\"{name_display} 响应\"\"\"
    id: str
    name: str
    description: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
"""),
                ],
            ),
            TaskTemplate(
                id="fix_common_issue",
                name="修复常见代码问题",
                category=TemplateCategory.FIX,
                description="修复代码中的常见问题（类型错误、缺失导入、语法错误等）",
                keywords=["fix", "修复", "bug", "issue", "错误", "问题", "broken"],
                prerequisites=[],
                steps=[
                    "1. 定位问题文件",
                    "2. 分析问题根因",
                    "3. 应用修复",
                    "4. 验证修复",
                ],
                files=[],
            ),
            TaskTemplate(
                id="add_config_file",
                name="添加配置文件",
                category=TemplateCategory.CONFIG,
                description="添加或更新项目配置文件（.env, pyproject.toml, .gitignore 等）",
                keywords=["config", "配置", "setting", "环境变量", ".env"],
                steps=[
                    "1. 确定配置文件格式",
                    "2. 添加配置项",
                    "3. 更新配置加载逻辑",
                ],
                files=[
                    TemplateFile(path=".env.example", content="""# 环境配置示例（请复制为 .env 并填入实际值）
# API Keys
DEEPSEEK_API_KEY=your_api_key_here

# Agent 配置
DEVFLOW_AGENT_CONTEXT_BUDGET=140000
DEVFLOW_AGENT_AUTO_CONFIRM=false

# 预算
DEVFLOW_BUDGET_WEEKLY_BUDGET=20.0
DEVFLOW_BUDGET_BUDGET_PER_5H=3.5

# 日志
DEVFLOW_LOG_LEVEL=INFO
"""),
                ],
            ),
        ]
        for t in defaults:
            self._templates[t.id] = t

    def get(self, template_id: str) -> TaskTemplate | None:
        """按 ID 获取模板"""
        return self._templates.get(template_id)

    def list(self, category: TemplateCategory | None = None) -> list[TaskTemplate]:
        """列出模板，可选按分类过滤"""
        if category:
            return [t for t in self._templates.values() if t.category == category]
        return list(self._templates.values())

    def search(self, query: str) -> list[TaskTemplate]:
        """搜索模板（匹配名称、描述、关键词）"""
        query_lower = query.lower()
        results = []
        for t in self._templates.values():
            if (query_lower in t.name.lower()
                    or query_lower in t.description.lower()
                    or any(query_lower in kw.lower() for kw in t.keywords)):
                results.append(t)
        return results

    def register(self, template: TaskTemplate):
        """注册自定义模板"""
        self._templates[template.id] = template


class FeatureScaffold:
    """新功能脚手架 — 分析项目、推荐模板、生成计划"""

    def __init__(self, repo_path: str | Path = "."):
        self.repo_path = Path(repo_path).resolve()
        self.registry = TemplateRegistry()

    def analyze_project(self) -> dict[str, Any]:
        """分析项目结构，返回项目特征字典"""
        features: dict[str, Any] = {
            "has_fastapi": False,
            "has_flask": False,
            "has_click": False,
            "has_typer": False,
            "has_pytest": False,
            "has_pydantic": False,
            "has_django": False,
            "has_sqlalchemy": False,
            "is_python_project": False,
            "framework": None,
            "test_framework": None,
            "top_level_modules": [],
            "has_tests_dir": False,
            "has_api_dir": False,
            "has_cli_dir": False,
        }

        # 检查关键文件/目录
        checks = {
            "has_fastapi": ["fastapi"],
            "has_flask": ["flask"],
            "has_click": ["click"],
            "has_typer": ["typer"],
            "has_pytest": ["pytest"],
            "has_pydantic": ["pydantic"],
            "has_django": ["django"],
            "has_sqlalchemy": ["sqlalchemy"],
        }

        # 检查方式：1) 依赖文件  2) 导入语句  3) 目录结构
        # 先尝试从 pyproject.toml / requirements.txt 读取依赖
        deps = self._detect_dependencies()
        for key, packages in checks.items():
            features[key] = any(pkg in deps for pkg in packages)

        # 目录结构检测
        src_dir = self.repo_path / "src"
        tests_dir = self.repo_path / "tests"
        features["has_tests_dir"] = tests_dir.is_dir()
        features["has_api_dir"] = (src_dir / "api").is_dir() if src_dir.is_dir() else False
        features["has_cli_dir"] = (src_dir / "cli").is_dir() if src_dir.is_dir() else False

        # 顶层模块
        if src_dir.is_dir():
            features["top_level_modules"] = [
                p.name for p in src_dir.iterdir()
                if p.is_dir() and not p.name.startswith(("_", "."))
            ]

        # 推断框架
        if features["has_fastapi"]:
            features["framework"] = "fastapi"
        elif features["has_flask"]:
            features["framework"] = "flask"
        elif features["has_django"]:
            features["framework"] = "django"

        features["is_python_project"] = self._is_python_project()

        return features

    def _detect_dependencies(self) -> set[str]:
        """从项目配置中检测依赖"""
        deps: set[str] = set()

        # pyproject.toml
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding="utf-8")
                # 简单解析依赖行
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith(('"', "'")):
                        pkg = line.strip('"').strip("'").strip(",")
                        if pkg:
                            deps.add(pkg.split(">")[0].split("=")[0].split("<")[0].strip().lower())
            except Exception:
                pass

        # requirements.txt
        req_file = self.repo_path / "requirements.txt"
        if req_file.exists():
            try:
                for line in req_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        deps.add(line.split(">")[0].split("=")[0].split("<")[0].strip().lower())
            except Exception:
                pass

        return deps

    def _is_python_project(self) -> bool:
        """判断是否为 Python 项目"""
        indicators = [
            self.repo_path / "pyproject.toml",
            self.repo_path / "setup.py",
            self.repo_path / "setup.cfg",
            self.repo_path / "requirements.txt",
            self.repo_path / "Pipfile",
        ]
        return any(p.exists() for p in indicators)

    def suggest_templates(
        self,
        task: str = "",
        top_k: int = 3,
    ) -> list[TaskTemplate]:
        """根据任务描述和项目上下文推荐最合适的模板"""
        project_features = self.analyze_project()
        project_summary = self._build_project_summary(project_features)

        # 为所有模板打分
        scored: list[tuple[float, TaskTemplate]] = []
        for template in self.registry.list():
            score = template.match_score(task, project_summary)

            # 项目特征加成
            if template.category == TemplateCategory.API_ENDPOINT and project_features["has_fastapi"]:
                score += 0.2
            if template.category == TemplateCategory.CLI_COMMAND and project_features["has_click"]:
                score += 0.2
            if template.category == TemplateCategory.TEST and project_features["has_pytest"]:
                score += 0.15
            if template.category == TemplateCategory.TEST and project_features["has_tests_dir"]:
                score += 0.1

            scored.append((score, template))

        # 按分数排序
        scored.sort(key=lambda x: x[0], reverse=True)

        # 返回 top_k
        return [t for _, t in scored[:top_k] if _ > 0]

    def generate_plan(
        self,
        template: TaskTemplate,
        task: str = "",
        params: dict[str, str] | None = None,
    ) -> ScaffoldPlan:
        """根据模板和参数生成具体实施计划"""
        params = params or {}

        # 自动推断参数
        inferred_params = self._infer_params(task, template)
        inferred_params.update(params)

        # 渲染文件内容（替换占位符）
        files_to_create: list[TemplateFile] = []
        files_to_modify: list[TemplateFile] = []

        for tf in template.files:
            rendered_path = self._render_template(tf.path, inferred_params)
            rendered_content = self._render_template(tf.content, inferred_params)

            rendered_tf = TemplateFile(
                path=rendered_path,
                content=rendered_content,
                after_existing=tf.after_existing,
                overwrite=tf.overwrite,
            )

            # 判断是新建还是修改
            target = self.repo_path / rendered_path
            if target.exists() and not tf.overwrite:
                files_to_modify.append(rendered_tf)
            else:
                files_to_create.append(rendered_tf)

        # 生成步骤说明
        all_steps = []
        for s in template.steps:
            rendered_step = self._render_template(s, inferred_params)
            all_steps.append(rendered_step)

        # 评估工作量
        effort = self._estimate_effort(template, files_to_create, files_to_modify)

        # 生成警告
        warnings = self._check_prerequisites(template)

        return ScaffoldPlan(
            template=template,
            task_description=task or template.description,
            steps=all_steps,
            files_to_create=files_to_create,
            files_to_modify=files_to_modify,
            estimated_effort=effort,
            warnings=warnings,
        )

    def _build_project_summary(self, features: dict[str, Any]) -> str:
        """构建项目特征的文本摘要"""
        parts = []
        if features["framework"]:
            parts.append(f"框架: {features['framework']}")
        if features["top_level_modules"]:
            parts.append("顶层模块: " + ", ".join(features["top_level_modules"]))
        if features["has_tests_dir"]:
            parts.append("已有测试目录")
        if features["has_api_dir"]:
            parts.append("已有 API 目录")
        if features["has_cli_dir"]:
            parts.append("已有 CLI 目录")
        return "; ".join(parts)

    def _infer_params(self, task: str, template: TaskTemplate) -> dict[str, str]:
        """从任务描述中推断模板参数"""
        params: dict[str, str] = {}

        # 提取模块/功能名称（驼峰、蛇形、或引号中的词）
        # 优先匹配引号中的词作为名称
        quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', task)
        if quoted:
            name = quoted[0][0] or quoted[0][1]
        else:
            # 提取有意义的词
            words = re.findall(r'[a-zA-Z_]\w*', task)
            # 过滤掉常见动词和停用词
            stopwords = {"create", "add", "new", "implement", "make", "build",
                        "the", "a", "an", "for", "in", "to", "of", "and", "src"}
            meaningful = [w for w in words if w.lower() not in stopwords and len(w) >= 2]
            name = meaningful[0] if meaningful else "Feature"

        # 生成各种命名风格
        snake = self._to_snake_case(name)
        pascal = self._to_pascal_case(name)
        camel = self._to_camel_case(name)

        params["module_name"] = snake
        params["module_path"] = snake
        params["core_module"] = "core"
        params["class_name"] = pascal
        params["name"] = snake
        params["name_display"] = pascal
        params["import_path"] = f"src.{snake}"
        params["command_name"] = snake
        params["module_description"] = f"{pascal} 功能模块"

        return params

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """转换为蛇形命名"""
        # 处理驼峰
        s1 = re.sub(r'([A-Z])', r'_\1', name)
        s1 = s1.lower().strip("_")
        # 替换非字母数字为下划线
        s1 = re.sub(r'[^a-z0-9_]', '_', s1)
        return re.sub(r'_+', '_', s1).strip("_") or "feature"

    @staticmethod
    def _to_pascal_case(name: str) -> str:
        """转换为帕斯卡命名"""
        snake = FeatureScaffold._to_snake_case(name)
        return "".join(word.capitalize() for word in snake.split("_"))

    @staticmethod
    def _to_camel_case(name: str) -> str:
        """转换为驼峰命名"""
        pascal = FeatureScaffold._to_pascal_case(name)
        return pascal[0].lower() + pascal[1:] if pascal else "feature"

    @staticmethod
    def _render_template(text: str, params: dict[str, str]) -> str:
        """渲染模板中的占位符 {key}"""
        result = text
        for key, value in params.items():
            result = result.replace(f"{{{key}}}", value)
        return result

    @staticmethod
    def _estimate_effort(
        template: TaskTemplate,
        files_to_create: list[TemplateFile],
        files_to_modify: list[TemplateFile],
    ) -> str:
        """估算实施工作量"""
        total_files = len(files_to_create) + len(files_to_modify)
        if total_files <= 1 and template.category in (TemplateCategory.FIX, TemplateCategory.CONFIG):
            return "easy"
        if total_files <= 3:
            return "medium"
        return "hard"

    def _check_prerequisites(self, template: TaskTemplate) -> list[str]:
        """检查前置条件，返回未满足的警告"""
        warnings: list[str] = []
        project_features = self.analyze_project()

        for prereq in template.prerequisites:
            if "FastAPI" in prereq and not project_features["has_fastapi"]:
                warnings.append("未检测到 FastAPI 框架，建议先安装 fastapi")
            if "Flask" in prereq and not project_features["has_flask"]:
                warnings.append("未检测到 Flask 框架")
            if "Click" in prereq and not project_features["has_click"]:
                warnings.append("未检测到 Click 依赖")
            if "pytest" in prereq and not project_features["has_pytest"]:
                warnings.append("未检测到 pytest 依赖，建议先安装 pytest")

        return warnings

    def scaffold(self, template: TaskTemplate, task: str = "",
                 params: dict[str, str] | None = None, dry_run: bool = True) -> ScaffoldPlan:
        """执行脚手架：生成文件结构（支持 dry_run 预览）"""
        plan = self.generate_plan(template, task, params)

        if dry_run:
            return plan

        # 实际写入文件
        for tf in plan.files_to_create:
            target = self.repo_path / tf.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(tf.content, encoding="utf-8")

        for tf in plan.files_to_modify:
            target = self.repo_path / tf.path
            if target.exists() and tf.after_existing:
                content = target.read_text(encoding="utf-8")
                if tf.after_existing in content:
                    # 在标记后插入
                    new_content = content.replace(tf.after_existing,
                                                  tf.after_existing + "\n" + tf.content)
                    target.write_text(new_content, encoding="utf-8")
                else:
                    # 追加到文件末尾
                    with target.open("a", encoding="utf-8") as f:
                        f.write("\n" + tf.content)
            elif not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(tf.content, encoding="utf-8")

        return plan


# 便捷函数

def suggest_templates(task: str, repo_path: str | Path = ".") -> list[TaskTemplate]:
    """快捷方式：根据任务推荐模板"""
    scaffold = FeatureScaffold(repo_path)
    return scaffold.suggest_templates(task)


def list_templates(category: TemplateCategory | None = None) -> list[TaskTemplate]:
    """快捷方式：列出所有可用模板"""
    return TemplateRegistry().list(category)


def scaffold_feature(template_id: str, task: str = "",
                     repo_path: str | Path = ".",
                     params: dict[str, str] | None = None,
                     dry_run: bool = True) -> ScaffoldPlan:
    """快捷方式：使用模板生成新功能脚手架"""
    scaffold = FeatureScaffold(repo_path)
    template = scaffold.registry.get(template_id)
    if not template:
        available = ", ".join(t.id for t in scaffold.registry.list())
        raise ValueError(f"未知模板 ID: {template_id}。可用: {available}")
    return scaffold.scaffold(template, task, params, dry_run=dry_run)
