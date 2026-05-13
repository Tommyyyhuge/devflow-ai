"""Week 1 L3 里程碑验证 — Mock LLM 全链路测试

不依赖 DeepSeek API Key，验证 Agent 核心链路：Plan → Execute → Verify
"""

import asyncio
import json
from pathlib import Path

from devflow.core.agent import Agent
from devflow.core.planner import Planner, StepType
from devflow.llm import ChatResponse, TokenUsage
from devflow.tools import create_tool_registry
from devflow.tools.base import set_safe_root


class MockLLMClient:
    """模拟 DeepSeek 客户端，返回预定义的响应"""

    def __init__(self, plan_response: str = "", exec_responses: list[dict] | None = None):
        self.plan_response = plan_response
        self.exec_responses = exec_responses or []
        self.chat_calls: list[dict] = []
        self.exec_index = 0

    def _wrap_response(self, data: dict) -> ChatResponse:
        """包装为 ChatResponse"""
        return ChatResponse(
            data=data,
            tokens=TokenUsage(),
        )

    def chat_for_planning(self, messages: list[dict]) -> ChatResponse:
        self.chat_calls.append({"mode": "planning", "messages": messages})
        return self._wrap_response({
            "choices": [{
                "message": {
                    "content": self.plan_response,
                }
            }]
        })

    def chat_for_execution(self, messages: list[dict], tools: list[dict]) -> ChatResponse:
        self.chat_calls.append({"mode": "execution", "messages": messages, "tools": tools})
        if self.exec_index < len(self.exec_responses):
            resp = self.exec_responses[self.exec_index]
            self.exec_index += 1
            return self._wrap_response(resp)
        # 默认：最终回答
        return self._wrap_response({
            "choices": [{
                "message": {
                    "content": "任务完成。",
                }
            }]
        })


class TestAgentCoreLoop:
    """验证 Agent 核心循环"""

    def test_planner_parse_json(self):
        """验证 Planner 能从 JSON 解析步骤"""
        client = MockLLMClient()
        planner = Planner(client)

        response = '''{"steps": [
            {"index": 1, "type": "read", "description": "读取文件"},
            {"index": 2, "type": "write", "description": "创建文件"},
            {"index": 3, "type": "verify", "description": "验证"}
        ]}'''
        steps = planner._parse_steps_json(response)
        assert len(steps) == 3
        assert steps[0].type == StepType.READ
        assert steps[1].type == StepType.WRITE
        assert steps[2].type == StepType.VERIFY

    def test_planner_parse_steps_legacy(self):
        """验证 Planner 能正确解析旧版 LLM 响应"""
        client = MockLLMClient()
        planner = Planner(client)

        # LLM 返回的标准格式
        response = """1. [read] 读取 src/api/__init__.py 了解现有路由结构
2. [write] 创建 src/api/health.py 实现健康检查端点
3. [write] 修改 src/api/__init__.py 注册路由
4. [verify] 运行 curl 验证端点返回 status ok"""
        steps = planner._parse_steps_legacy(response)
        assert len(steps) == 4
        assert steps[0].type == StepType.READ
        assert steps[1].type == StepType.WRITE
        assert steps[3].type == StepType.VERIFY

    def test_planner_parse_fallback(self):
        """验证 Planner 在无结构化响应时的 fallback"""
        client = MockLLMClient()
        planner = Planner(client)
        steps = planner._parse_steps_legacy("some unstructured response without proper format")
        assert len(steps) == 1
        assert steps[0].type == StepType.WRITE

    def test_tool_registry(self):
        """验证 6 个工具全部注册且有正确的 OpenAI schema"""
        registry = create_tool_registry()
        schemas = registry.get_schemas()
        assert len(schemas) == 9

        expected_tools = {"read_file", "write_file", "list_dir",
                          "edit_file", "run_shell", "search_code",
                          "git_diff", "git_log", "git_status"}
        actual_tools = {s["function"]["name"] for s in schemas}
        assert actual_tools == expected_tools

        # 验证每个 schema 结构完整
        for s in schemas:
            assert s["type"] == "function"
            assert "name" in s["function"]
            assert "description" in s["function"]
            assert "parameters" in s["function"]

    def test_read_file_tool(self, tmp_path):
        """验证 read_file 工具正确读取文件"""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')\nprint('world')")

        set_safe_root(tmp_path)
        registry = create_tool_registry()
        tool = registry.get("read_file")
        result = tool.execute(path="test.py")
        assert result.success
        assert "hello" in result.output
        assert "world" in result.output

    def test_write_file_tool(self, tmp_path):
        """验证 write_file 工具正确创建文件"""
        set_safe_root(tmp_path)
        registry = create_tool_registry()
        tool = registry.get("write_file")
        result = tool.execute(path="new_file.py", content="# test")
        assert result.success
        assert (tmp_path / "new_file.py").exists()

    def test_safe_path_boundary(self, tmp_path):
        """验证安全路径边界——拒绝越界访问"""
        set_safe_root(tmp_path)
        registry = create_tool_registry()
        tool = registry.get("read_file")
        # 尝试读取安全目录外的文件
        result = tool.execute(path="../outside.txt")
        assert not result.success
        assert "越界" in result.error

    def test_edit_file_unique_match(self, tmp_path):
        """验证 edit_file 的精确匹配逻辑"""
        test_file = tmp_path / "config.py"
        test_file.write_text("DEBUG = False\nPORT = 8080\nHOST = 'localhost'")

        set_safe_root(tmp_path)
        registry = create_tool_registry()
        tool = registry.get("edit_file")

        # 成功：唯一匹配
        result = tool.execute(
            path="config.py",
            old_string="DEBUG = False",
            new_string="DEBUG = True",
        )
        assert result.success
        content = test_file.read_text()
        assert "DEBUG = True" in content

        # 失败：无匹配
        result = tool.execute(
            path="config.py",
            old_string="NOT_EXIST",
            new_string="REPLACED",
        )
        assert not result.success
        assert "未找到" in result.error

    def test_agent_full_pipeline(self, tmp_path):
        """端到端：Mock LLM 下 Agent 完整链路"""
        # 创建测试项目
        src = tmp_path / "src" / "api"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("from .users import users_router\n")
        (src / "users.py").write_text("from fastapi import APIRouter\n\nusers_router = APIRouter()\n")

        set_safe_root(tmp_path)

        # Mock LLM 响应
        client = MockLLMClient(
            plan_response="""1. [read] 读取 src/api/__init__.py
2. [write] 创建 src/api/health.py 实现 /health GET 端点返回 status ok
3. [write] 修改 src/api/__init__.py 注册 health_router
4. [verify] 检查语法""",
            exec_responses=[
                # Step 1: 读取文件
                {
                    "choices": [{
                        "message": {
                            "tool_calls": [{
                                "id": "call_1",
                                "function": {
                                    "name": "read_file",
                                    "arguments": json.dumps({"path": "src/api/__init__.py"}),
                                }
                            }]
                        }
                    }]
                },
                # Step 1 完成后最终回答
                {"choices": [{"message": {"content": "已读取路由结构"}}]},
                # Step 2: 创建文件
                {
                    "choices": [{
                        "message": {
                            "tool_calls": [{
                                "id": "call_2",
                                "function": {
                                    "name": "write_file",
                                    "arguments": json.dumps({
                                        "path": "src/api/health.py",
                                        "content": "from fastapi import APIRouter\n\nhealth_router = APIRouter()\n\n\n@health_router.get('/health')\ndef health():\n    return {'status': 'ok'}\n",
                                    }),
                                }
                            }]
                        }
                    }]
                },
                {"choices": [{"message": {"content": "已创建 health.py"}}]},
                # Step 3: 修改路由注册
                {
                    "choices": [{
                        "message": {
                            "tool_calls": [{
                                "id": "call_3",
                                "function": {
                                    "name": "edit_file",
                                    "arguments": json.dumps({
                                        "path": "src/api/__init__.py",
                                        "old_string": "from .users import users_router",
                                        "new_string": "from .users import users_router\nfrom .health import health_router",
                                    }),
                                }
                            }]
                        }
                    }]
                },
                {"choices": [{"message": {"content": "已注册路由"}}]},
                # Step 4: 验证
                {"choices": [{"message": {"content": "验证完成"}}]},
            ],
        )

        tools = create_tool_registry()
        agent = Agent(client, tools)

        result = asyncio.run(agent.run(
            task="添加 /health 端点",
            repo_path=tmp_path,
        ))

        # 验证
        assert result.success is True
        health_file = tmp_path / "src" / "api" / "health.py"
        assert health_file.exists()
        content = health_file.read_text()
        assert "health" in content
        assert "status" in content

        init_content = (tmp_path / "src" / "api" / "__init__.py").read_text()
        assert "health_router" in init_content


class TestRepoMapAndParser:
    """Week 2: Tree-sitter 解析 + RepoMap 测试"""

    def test_python_parser_symbols(self):
        """验证 PythonProvider 正确提取函数和类"""
        from devflow.repo.parser import PythonProvider

        p = PythonProvider()
        result = p.parse_file(Path("D:/Aiagent/src/devflow/core/agent.py"))
        assert len(result.symbols) > 0
        assert any(s.kind == "class" for s in result.symbols)
        assert any(s.kind == "method" for s in result.symbols)
        assert result.language == "python"

    def test_python_parser_imports(self):
        """验证导入提取"""
        from devflow.repo.parser import PythonProvider

        p = PythonProvider()
        result = p.parse_file(Path("D:/Aiagent/src/devflow/core/agent.py"))
        assert len(result.imports) > 0

    def test_repomap_build(self):
        """验证 RepoMap 构建"""
        from devflow.repo.repomap import RepoMapBuilder

        b = RepoMapBuilder(Path("D:/Aiagent/src/devflow"))
        rm = b.build()
        assert len(rm.entries) >= 10  # 至少 10 个 Python 文件
        assert rm.total_symbols > 50
        assert all(e.summary for e in rm.entries if e.symbols)

    def test_repomap_context_for_task(self):
        """验证 RepoMap 为任务生成上下文"""
        from devflow.repo.repomap import RepoMapBuilder

        b = RepoMapBuilder(Path("D:/Aiagent/src/devflow"))
        context = b.get_context_for_task("agent execute step", max_files=5)
        assert len(context) > 100
        assert "devflow" in context.lower()

    def test_language_registry(self):
        """验证语言注册和检测"""
        from devflow.repo.parser import LanguageRegistry

        py_provider = LanguageRegistry.get("python")
        assert py_provider is not None

        # .py 文件应返回 Python provider
        provider = LanguageRegistry.detect(Path("test.py"))
        assert provider is not None

        # .txt 文件应返回 None
        provider = LanguageRegistry.detect(Path("test.txt"))
        assert provider is None

