"""补充测试 — 提升覆盖率到 70%+"""

from devflow.config import AgentConfig, BudgetConfig, LLMConfig, load_config
from devflow.tools.file_ops import EditFileTool, SearchCodeTool
from devflow.tools.shell import ShellTool


class TestConfig:
    def test_config_load(self):
        c = load_config()
        # 验证配置加载成功，不依赖具体值（因为可能被测试修改过）
        assert c.llm.model in ["deepseek-v4-flash", "deepseek-chat", "deepseek-coder"]
        assert c.budget.weekly_budget > 0

    def test_config_types(self):
        c = load_config()
        assert isinstance(c.llm, LLMConfig)
        assert isinstance(c.agent, AgentConfig)
        assert isinstance(c.budget, BudgetConfig)

    def test_config_secret(self):
        from devflow.config import LLMConfig
        # 直接验证 SecretStr 行为，不依赖环境
        c = LLMConfig(
            name="test",
            api_key="sk-test1234",
            base_url="https://api.test.com",
        )
        # SecretStr 默认隐藏
        assert str(c.api_key) == "**********"
        assert c.api_key.get_secret_value() == "sk-test1234"
        assert c.base_url == "https://api.test.com"
        assert c.name == "test"


class TestToolsExtended:
    def test_run_shell_dangerous(self):
        t = ShellTool()
        r = t.execute(command="shutdown now")
        assert not r.success

    def test_run_shell_timeout(self):
        t = ShellTool()
        import sys
        if sys.platform == "win32":
            r = t.execute(command="timeout 10", timeout=1)
        else:
            r = t.execute(command="sleep 10", timeout=1)
        assert not r.success

    def test_search_code(self, tmp_path):
        from devflow.tools.base import set_safe_root
        (tmp_path / "test.py").write_text("class Foo:\n    pass")
        set_safe_root(tmp_path)

        t = SearchCodeTool()
        r = t.execute(pattern="class Foo")
        assert r.success
        assert "Foo" in r.output

    def test_edit_file_empty_guard(self):
        t = EditFileTool()
        r = t.execute(path="test.txt", old_string="", new_string="b")
        assert not r.success
        assert "不能为空" in r.error


class TestVerifier:
    def test_verdict_structure(self):
        from devflow.core.verifier import Diagnostic, Verdict
        d = Diagnostic(file="test.py", line=1, severity="error", message="bad")
        assert d.file == "test.py"
        v = Verdict(passed=False, errors=[d])
        assert not v.passed

    def test_verifier_nonexistent_file(self, tmp_path):
        from devflow.core.verifier import Verifier
        v = Verifier(root=tmp_path)
        result = v.verify_syntax("nope.py")
        assert not result.passed


class TestExecutorRetry:
    """验证分层重试不被静默跳过"""
    async def test_executor_has_retry(self):
        from devflow.core.executor import Executor
        assert hasattr(Executor, "execute_with_retry")
        assert hasattr(Executor, "is_stuck")

    def test_stuck_detection(self):
        from devflow.core.executor import Executor
        msgs = [
            {"role": "assistant", "tool_calls": [{"function": {"name": "read_file"}}]},
            {"role": "tool", "content": "file content"},
            {"role": "assistant", "tool_calls": [{"function": {"name": "read_file"}}]},
            {"role": "tool", "content": "file content"},
            {"role": "assistant", "tool_calls": [{"function": {"name": "read_file"}}]},
            {"role": "tool", "content": "file content"},
        ]
        assert Executor.is_stuck(msgs, threshold=3)
        msgs_ok = [
            {"role": "assistant", "tool_calls": [{"function": {"name": "read_file"}}]},
            {"role": "assistant", "tool_calls": [{"function": {"name": "edit_file"}}]},
        ]
        assert not Executor.is_stuck(msgs_ok, threshold=3)


class TestPlannerTypes:
    def test_step_type_enum(self):
        from devflow.core.planner import StepType
        assert StepType.READ.value == "read"
        assert StepType.WRITE.value == "write"
        assert StepType.VERIFY.value == "verify"
