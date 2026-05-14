"""核心模块单元测试

覆盖 OpenAIProvider、ConversationStore、Git 工具、Scanner 四大模块。
所有外部依赖均使用 Mock 或临时文件替代，不依赖真实的 API 或 Git 仓库。
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.config import LLMConfig
from devflow.history.store import Conversation, ConversationStore, Message
from devflow.llm import ChatResponse, OpenAIProvider, TokenUsage
from devflow.repo.scanner import (
    FileInfo,
    GrepSearch,
    ProjectContext,
    ProjectScanner,
    SearchMatch,
)
from devflow.tools.base import ToolResult
from devflow.tools.git_ops import (
    GitBranchTool,
    GitCommitTool,
    GitDiffTool,
    GitLogTool,
    GitStatusTool,
)

# ─────────────────────────────────────────────
# TestLLMClient
# ─────────────────────────────────────────────

class TestLLMClient:
    """OpenAIProvider 单元测试 — Mock OpenAI 客户端"""

    @pytest.fixture
    def config(self):
        """创建测试用 LLMConfig"""
        return LLMConfig(
            api_key="sk-test1234", model="deepseek-v4-flash",
            max_tokens_per_request=8000,
        )

    @pytest.fixture
    def client(self, config):
        """创建 OpenAIProvider（不实际调用 API）"""
        return OpenAIProvider(config)

    @pytest.fixture
    def messages(self):
        return [{"role": "user", "content": "Hello"}]

    # --- test_chat_success ---

    def test_chat_success(self, client, messages):
        """Mock OpenAI 响应，验证成功返回 ChatResponse"""
        mock_data = {
            "id": "chatcmpl-123",
            "choices": [{"message": {"role": "assistant", "content": "Hi!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response = MagicMock()
        mock_response.model_dump.return_value = mock_data

        with patch.object(client.client.chat.completions, "create", return_value=mock_response):
            result = client.chat(messages)

        assert isinstance(result, ChatResponse)
        assert result.data == mock_data
        assert result.retry_count == 0
        assert result.latency_ms >= 0
        assert isinstance(result.tokens, TokenUsage)
        assert result.tokens.prompt_tokens == 10
        assert result.tokens.completion_tokens == 5
        assert result.tokens.total_tokens == 15

    # --- test_token_tracking ---

    def test_token_tracking(self, client, messages):
        """验证 Token 累计计算正确"""
        mock_data_1 = {
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_data_2 = {
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }
        resp1 = MagicMock()
        resp1.model_dump.return_value = mock_data_1
        resp2 = MagicMock()
        resp2.model_dump.return_value = mock_data_2

        with patch.object(client.client.chat.completions, "create", side_effect=[resp1, resp2]):
            client.chat(messages)
            client.chat(messages)

        assert client.get_total_tokens() == 45  # 15 + 30

    # --- test_rate_limit_retry ---

    def test_rate_limit_retry(self, client, messages):
        """Mock RateLimitError，验证指数退避重试"""
        from openai import RateLimitError

        mock_data = {
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        success_resp = MagicMock()
        success_resp.model_dump.return_value = mock_data

        # 前两次抛出 RateLimitError，第三次成功
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RateLimitError("rate limit exceeded", response=MagicMock(), body=None)
            return success_resp

        with patch.object(client.client.chat.completions, "create", side_effect=side_effect):
            with patch("time.sleep", return_value=None) as mock_sleep:
                result = client.chat(messages, max_retries=3)

        # 验证结果
        assert result.retry_count == 2  # 第3次成功（0-based，attempt=2）
        assert result.data == mock_data
        # 验证指数退避: attempt 0 → sleep(1), attempt 1 → sleep(2)
        assert mock_sleep.call_count >= 2
        assert mock_sleep.call_args_list[0][0][0] == 1  # 2^0
        assert mock_sleep.call_args_list[1][0][0] == 2  # 2^1

    # --- test_rate_limit_retry_exhausted ---

    def test_rate_limit_retry_exhausted(self, client, messages):
        """Mock 持续 RateLimitError，验证重试耗尽后返回错误"""
        from openai import RateLimitError

        rate_error = RateLimitError("rate limit exceeded", response=MagicMock(), body=None)

        with patch.object(client.client.chat.completions, "create", side_effect=rate_error):
            with patch("time.sleep", return_value=None):
                result = client.chat(messages, max_retries=3)

        # 重试耗尽，data 中应包含错误信息
        assert "error" in result.data
        assert "速率限制" in result.data["error"]

    # --- test_api_error ---

    def test_api_error(self, client, messages):
        """Mock APIError，验证错误处理"""
        from openai import APIError

        api_error = APIError("server error", request=MagicMock(), body=None)

        with patch.object(client.client.chat.completions, "create", side_effect=api_error):
            with patch("time.sleep", return_value=None):
                result = client.chat(messages, max_retries=2)

        assert "error" in result.data
        assert "API 错误" in result.data["error"]

    # --- test_sanitize_error ---

    def test_sanitize_error(self, client):
        """验证 API key 过滤"""
        raw = "Error with key sk-1234abcd5678 and Authorization: Bearer token123"
        sanitized = client._sanitize_error(raw)
        # API key 的前 7 位被替换为 sk-1234***
        assert "sk-1234abcd5678" not in sanitized
        assert "sk-1234***" in sanitized
        # Authorization: 后的第一个 token 被替换为 ***，但后续 token 保留
        assert "Authorization: ***" in sanitized

    # --- test_chat_with_thinking ---

    def test_chat_with_thinking(self, client, messages):
        """验证 thinking 模式参数传递"""
        mock_data = {"usage": {"total_tokens": 5}}
        mock_response = MagicMock()
        mock_response.model_dump.return_value = mock_data

        with patch.object(
            client.client.chat.completions, "create",
            return_value=mock_response,
        ) as mock_create:
            client.chat(messages, thinking=True)

        call_kwargs = mock_create.call_args[1]
        assert "extra_body" in call_kwargs
        assert call_kwargs["extra_body"] == {"thinking": {"type": "enabled"}}

    # --- test_chat_with_tools ---

    def test_chat_with_tools(self, client, messages):
        """验证 tools 参数传递"""
        mock_data = {"usage": {"total_tokens": 5}}
        mock_response = MagicMock()
        mock_response.model_dump.return_value = mock_data
        test_tools = [{"type": "function", "function": {"name": "test_tool"}}]

        with patch.object(
            client.client.chat.completions, "create",
            return_value=mock_response,
        ) as mock_create:
            client.chat(messages, tools=test_tools)

        call_kwargs = mock_create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] == test_tools

    # --- test_chat_for_planning ---

    def test_chat_for_planning(self, client):
        """验证 chat_for_planning 调用 chat 时传入 thinking=True"""
        messages = [{"role": "user", "content": "Plan something"}]
        mock_data = {"usage": {"total_tokens": 5}}
        mock_response = MagicMock()
        mock_response.model_dump.return_value = mock_data

        with patch.object(
            client.client.chat.completions, "create",
            return_value=mock_response,
        ) as mock_create:
            result = client.chat_for_planning(messages)

        assert isinstance(result, ChatResponse)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["temperature"] == 0.3
        assert "extra_body" in call_kwargs

    # --- test_chat_for_execution ---

    def test_chat_for_execution(self, client):
        """验证 chat_for_execution 调用 chat 时传入 tools 和 temperature=0.0"""
        messages = [{"role": "user", "content": "Execute"}]
        test_tools = [{"type": "function", "function": {"name": "run"}}]
        mock_data = {"usage": {"total_tokens": 5}}
        mock_response = MagicMock()
        mock_response.model_dump.return_value = mock_data

        with patch.object(
            client.client.chat.completions, "create",
            return_value=mock_response,
        ) as mock_create:
            result = client.chat_for_execution(messages, tools=test_tools)

        assert isinstance(result, ChatResponse)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["temperature"] == 0.0
        assert call_kwargs["tools"] == test_tools

    # --- test_chat_unknown_error ---

    def test_chat_unknown_error(self, client, messages):
        """验证未知异常被捕获并返回错误信息"""
        with patch.object(
            client.client.chat.completions, "create",
            side_effect=RuntimeError("unexpected crash"),
        ):
            result = client.chat(messages, max_retries=1)

        assert "error" in result.data
        assert "调用失败" in result.data["error"]


# ─────────────────────────────────────────────
# TestConversationStore
# ─────────────────────────────────────────────

class TestConversationStore:
    """ConversationStore 单元测试 — 使用临时 SQLite 数据库"""

    @pytest.fixture
    def store(self):
        """创建使用临时数据库的 ConversationStore"""
        tmp = tempfile.mkdtemp(prefix="devflow_test_")
        db_path = Path(tmp) / "test_conversations.db"
        s = ConversationStore(db_path=db_path)
        yield s
        # 清理
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # --- test_create_conversation ---

    def test_create_conversation(self, store):
        """创建会话，验证返回结构"""
        conv = store.create_conversation(project="test-proj", task="test task")

        assert isinstance(conv, Conversation)
        assert conv.project == "test-proj"
        assert conv.task == "test task"
        assert conv.status == "pending"
        assert len(conv.id) > 0

    # --- test_add_message ---

    def test_add_message(self, store):
        """添加消息，验证能读取"""
        conv = store.create_conversation(project="proj", task="task")
        msg = store.add_message(conv.id, role="user", content="Hello world")

        assert isinstance(msg, Message)
        assert msg.conversation_id == conv.id
        assert msg.role == "user"
        assert msg.content == "Hello world"
        assert msg.id > 0

        # 验证能读取到消息
        messages = store.get_messages(conv.id)
        assert len(messages) == 1
        assert messages[0].content == "Hello world"

    # --- test_add_message_with_metadata ---

    def test_add_message_with_metadata(self, store):
        """添加带元数据的消息"""
        conv = store.create_conversation(project="proj", task="task")
        meta = {"tokens": 100, "latency_ms": 500.0}
        msg = store.add_message(conv.id, role="assistant", content="ok", metadata=meta)

        assert msg.metadata == meta

        messages = store.get_messages(conv.id)
        assert messages[0].metadata == meta

    # --- test_get_conversation_exists ---

    def test_get_conversation_exists(self, store):
        """获取存在的会话"""
        conv = store.create_conversation(project="proj", task="task")
        fetched = store.get_conversation(conv.id)

        assert fetched is not None
        assert fetched.id == conv.id
        assert fetched.project == "proj"
        assert fetched.task == "task"

    # --- test_get_conversation_not_exists ---

    def test_get_conversation_not_exists(self, store):
        """获取不存在的会话，返回 None"""
        fetched = store.get_conversation("nonexistent")
        assert fetched is None

    # --- test_list_conversations ---

    def test_list_conversations(self, store):
        """列会话，验证返回列表"""
        store.create_conversation(project="proj-a", task="task 1")
        store.create_conversation(project="proj-a", task="task 2")
        store.create_conversation(project="proj-b", task="task 3")

        all_convs = store.list_conversations()
        assert len(all_convs) == 3
        assert isinstance(all_convs[0], Conversation)

    # --- test_list_conversations_filter_by_project ---

    def test_list_conversations_filter_by_project(self, store):
        """按项目过滤会话"""
        store.create_conversation(project="proj-a", task="task 1")
        store.create_conversation(project="proj-a", task="task 2")
        store.create_conversation(project="proj-b", task="task 3")

        convs_a = store.list_conversations(project="proj-a")
        assert len(convs_a) == 2
        assert all(c.project == "proj-a" for c in convs_a)

    # --- test_update_status ---

    def test_update_status(self, store):
        """更新会话状态"""
        conv = store.create_conversation(project="proj", task="task")
        store.update_status(conv.id, status="running", total_tokens=100)

        updated = store.get_conversation(conv.id)
        assert updated.status == "running"
        assert updated.total_tokens == 100

    # --- test_delete_conversation ---

    def test_delete_conversation(self, store):
        """删除会话（含级联删除消息）"""
        conv = store.create_conversation(project="proj", task="task")
        store.add_message(conv.id, role="user", content="test")
        store.delete_conversation(conv.id)

        assert store.get_conversation(conv.id) is None


# ─────────────────────────────────────────────
# TestGitTools
# ─────────────────────────────────────────────

class TestGitTools:
    """Git 工具单元测试 — Mock GitPython Repo"""

    @pytest.fixture
    def mock_repo(self):
        """创建 Mock GitPython Repo 对象"""
        repo = MagicMock()
        # 模拟 git 子命令
        repo.git.status.return_value = " M src/main.py\n?? new_file.py"
        repo.git.branch.return_value = "  feature-x\n* main\n  dev"
        repo.git.log.return_value = "abc123 feat: add feature\n"
        repo.git.diff.return_value = "diff --git a/file.py b/file.py"
        repo.is_dirty.return_value = True
        return repo

    @pytest.fixture
    def mock_git_module(self, mock_repo):
        """Mock git.Repo 构造"""
        with patch("git.Repo", return_value=mock_repo):
            yield

    # --- test_git_status ---

    def test_git_status(self, mock_git_module, mock_repo):
        """Mock git status 输出"""
        tool = GitStatusTool()
        result = tool.execute()

        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "src/main.py" in result.output
        assert "new_file.py" in result.output

    # --- test_git_status_clean ---

    def test_git_status_clean(self, mock_repo):
        """空 status 输出显示干净工作区"""
        mock_repo.git.status.return_value = ""
        with patch("git.Repo", return_value=mock_repo):
            tool = GitStatusTool()
            result = tool.execute()

        assert result.success
        assert "干净" in result.output

    # --- test_git_branch ---

    def test_git_branch(self, mock_git_module, mock_repo):
        """Mock git branch 输出"""
        tool = GitBranchTool()
        result = tool.execute(name="feature-x", create=False)

        assert result.success is True
        mock_repo.git.checkout.assert_called_once_with("feature-x")

    # --- test_git_branch_create ---

    def test_git_branch_create(self, mock_repo):
        """创建新分支"""
        mock_head = MagicMock()
        mock_repo.create_head.return_value = mock_head

        with patch("git.Repo", return_value=mock_repo):
            tool = GitBranchTool()
            result = tool.execute(name="feature-new", create=True)

        assert result.success
        mock_repo.create_head.assert_called_once_with("feature-new")
        mock_head.checkout.assert_called_once()

    # --- test_git_log ---

    def test_git_log(self, mock_git_module, mock_repo):
        """Mock git log 输出"""
        tool = GitLogTool()
        result = tool.execute(count=5)

        assert result.success is True
        mock_repo.git.log.assert_called_once_with("-5", "--oneline", "--decorate")

    # --- test_git_diff ---

    def test_git_diff(self, mock_repo):
        """Mock git diff 输出"""
        with patch("git.Repo", return_value=mock_repo):
            tool = GitDiffTool()
            result = tool.execute()

        assert result.success is True
        assert "diff --git" in result.output

    # --- test_git_commit ---

    def test_git_commit(self, mock_repo):
        """Mock 提交操作"""
        with patch("git.Repo", return_value=mock_repo):
            tool = GitCommitTool()
            result = tool.execute(message="feat: test commit")

        assert result.success is True
        mock_repo.git.add.assert_called_once_with(".")
        mock_repo.index.commit.assert_called_once_with("feat: test commit")

    # --- test_git_commit_no_changes ---

    def test_git_commit_no_changes(self, mock_repo):
        """无改动时拒绝提交"""
        mock_repo.is_dirty.return_value = False
        with patch("git.Repo", return_value=mock_repo):
            tool = GitCommitTool()
            result = tool.execute(message="empty commit")

        assert result.success is False
        assert "没有可提交的改动" in result.error

    # --- test_git_error_handling ---

    def test_git_status_error(self):
        """Git 操作异常时返回错误"""
        with patch("git.Repo", side_effect=ImportError("No git module")):
            tool = GitStatusTool()
            result = tool.execute()

        assert result.success is False
        assert "失败" in result.error


# ─────────────────────────────────────────────
# TestScanner
# ─────────────────────────────────────────────

class TestScanner:
    """Scanner 单元测试 — 使用临时目录"""

    @pytest.fixture
    def temp_project(self):
        """创建临时项目目录，包含测试文件"""
        with tempfile.TemporaryDirectory(prefix="devflow_scanner_") as tmp:
            root = Path(tmp)

            # 创建目录结构
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / ".git").mkdir()  # 应被排除

            # 创建测试文件
            (root / "README.md").write_text("# Test Project\nHello world", encoding="utf-8")
            (root / "src" / "main.py").write_text(
                "def hello():\n    print('Hello world')\n    return 42\n",
                encoding="utf-8",
            )
            (root / "src" / "utils.py").write_text(
                "def add(a, b):\n    return a + b\n\ndef subtract(a, b):\n    return a - b\n",
                encoding="utf-8",
            )
            (root / "tests" / "test_main.py").write_text(
                "import pytest\n\ndef test_hello():\n    assert True\n",
                encoding="utf-8",
            )
            # 二进制文件（应被跳过）
            (root / "data.bin").write_bytes(b"\x00\x01\x02\x03")

            yield root

    # --- test_project_scanner ---

    def test_project_scanner(self, temp_project):
        """验证项目文件扫描"""
        scanner = ProjectScanner(root=temp_project)
        ctx = scanner.scan()

        assert isinstance(ctx, ProjectContext)
        assert ctx.root == temp_project
        assert ctx.total_files > 0

        # 验证扫描到文本文件（规范化路径比较，兼容 Windows \）
        relative_paths = {f.relative.replace("\\", "/") for f in ctx.files}
        assert "src/main.py" in relative_paths
        assert "src/utils.py" in relative_paths
        assert "tests/test_main.py" in relative_paths
        assert "README.md" in relative_paths

        # .git 目录和 .bin 文件不应被扫描
        assert not any(".git" in f.relative for f in ctx.files)
        assert not any("data.bin" in f.relative for f in ctx.files)

        # 验证语言统计
        assert ".py" in ctx.languages
        assert ".md" in ctx.languages

        # 验证文件树
        assert ctx.structure != ""

    # --- test_project_scanner_excludes ---

    def test_project_scanner_excludes(self, temp_project):
        """验证自定义排除规则"""
        scanner = ProjectScanner(root=temp_project, excludes=["tests/*"])
        ctx = scanner.scan()

        relative_paths = {f.relative.replace("\\", "/") for f in ctx.files}
        assert "src/main.py" in relative_paths
        assert "tests/test_main.py" not in relative_paths

    # --- test_project_scanner_max_depth ---

    def test_project_scanner_max_depth(self, temp_project):
        """验证深度限制"""
        # 创建深层目录
        deep_dir = temp_project / "a" / "b" / "c" / "d" / "e" / "f"
        deep_dir.mkdir(parents=True)
        (deep_dir / "deep.py").write_text("x = 1", encoding="utf-8")

        scanner = ProjectScanner(root=temp_project, max_depth=3)
        ctx = scanner.scan()

        # 深度超过 max_depth=3 的文件不应被扫描
        relative_paths = {f.relative.replace("\\", "/") for f in ctx.files}
        assert "src/main.py" in relative_paths
        # 深层文件应被排除 (路径深度 > 3)
        assert not any("e" in p and "f" in p and "deep.py" in p for p in relative_paths)

    # --- test_grep_search ---

    def test_grep_search(self, temp_project):
        """在临时目录创建文件，验证搜索功能"""
        searcher = GrepSearch(root=temp_project)
        matches = searcher.search(pattern="hello", max_results=10)

        assert len(matches) >= 2  # README.md + src/main.py

        for m in matches:
            assert isinstance(m, SearchMatch)
            assert "hello" in m.content.lower()

    # --- test_grep_search_case_sensitive ---

    def test_grep_search_case_sensitive(self, temp_project):
        """验证区分大小写搜索"""
        searcher = GrepSearch(root=temp_project)

        # case_sensitive=True: 只有精确匹配 "Hello"
        matches_sensitive = searcher.search(pattern="Hello", case_sensitive=True)
        assert any(m.file == "README.md" for m in matches_sensitive)

        # case_sensitive=False (default): "hello" 也匹配 "Hello"
        matches_insensitive = searcher.search(pattern="hello", case_sensitive=False)
        assert any(m.file == "README.md" for m in matches_insensitive)

    # --- test_grep_search_include_glob ---

    def test_grep_search_include_glob(self, temp_project):
        """验证 include glob 过滤"""
        searcher = GrepSearch(root=temp_project)
        # 使用 fnmatch 模式，在 Windows 上 \ 和 / 都会被正确处理
        matches = searcher.search(pattern="def", include="src/*.py")

        for m in matches:
            assert m.file.replace("\\", "/").startswith("src/")

    # --- test_grep_search_max_results ---

    def test_grep_search_max_results(self, temp_project):
        """验证 max_results 限制"""
        # 创建多匹配文件
        (temp_project / "many.py").write_text(
            "match1\nmatch2\nmatch3\nmatch4\nmatch5\nmatch6\n",
            encoding="utf-8",
        )

        searcher = GrepSearch(root=temp_project)
        matches = searcher.search(pattern="match", max_results=3)
        assert len(matches) <= 3

    # --- test_grep_search_invalid_regex ---

    def test_grep_search_invalid_regex(self, temp_project):
        """验证无效正则返回错误信息"""
        searcher = GrepSearch(root=temp_project)
        matches = searcher.search(pattern="[invalid")

        assert len(matches) == 1
        assert "正则错误" in matches[0].content

    # --- test_grep_search_no_results ---

    def test_grep_search_no_results(self, temp_project):
        """验证无匹配时返回空列表"""
        searcher = GrepSearch(root=temp_project)
        matches = searcher.search(pattern="xyznonexistent123")

        assert matches == []

    # --- test_file_info_dataclass ---

    def test_file_info_dataclass(self):
        """验证 FileInfo 数据结构"""
        fi = FileInfo(
            path=Path("test.py"),
            relative="test.py",
            size=100,
            extension=".py",
            is_text=True,
        )
        assert fi.extension == ".py"
        assert fi.is_text is True

    # --- test_search_match_dataclass ---

    def test_search_match_dataclass(self):
        """验证 SearchMatch 数据结构"""
        sm = SearchMatch(file="src/main.py", line=10, content="def hello():")
        assert sm.file == "src/main.py"
        assert sm.line == 10
