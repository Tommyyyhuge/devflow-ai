"""FastAPI 集成测试 — 使用 TestClient 测试所有 API 端点

不依赖真实 API Key、不启动真实服务器、不污染 uploads/ 目录。
使用 unittest.mock.patch 覆盖 get_agent()、load_config()、UPLOADS、store。
"""

import io
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from devflow.api.server import app, get_agent
from devflow.history.store import ConversationStore

# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def temp_uploads(tmp_path: Path):
    """临时上传目录，避免污染真实 uploads/"""
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    with patch("devflow.api.server.UPLOADS", uploads_dir):
        yield uploads_dir


@pytest.fixture
def temp_store(tmp_path: Path):
    """使用临时 SQLite 数据库的 ConversationStore"""
    db_path = tmp_path / "conversations.db"
    test_store = ConversationStore(db_path=db_path)
    with patch("devflow.api.server.store", test_store):
        yield test_store


@pytest.fixture
def mock_agent():
    """Mock Agent 实例 — AsyncMock run() 返回成功结果"""
    agent = MagicMock()
    agent.run = AsyncMock()

    result = MagicMock()
    result.success = True
    result.error = ""
    result.plan = MagicMock()
    result.plan.steps = []
    result.step_results = []
    result.files_modified = []
    result.verify_result = MagicMock()
    result.verify_result.passed = True
    result.verify_result.errors = []

    agent.run.return_value = result
    return agent


@pytest.fixture
def client(temp_uploads, temp_store, mock_agent):
    """测试客户端 — 覆盖 get_agent() 依赖和所有模块级外部状态"""
    app.dependency_overrides[get_agent] = lambda: mock_agent

    # 同时 mock 掉 load_config 和 set_safe_root，防止副作用
    with patch("devflow.api.server.load_config") as mock_cfg:
        mock_cfg.return_value = MagicMock()
        with patch("devflow.api.server.set_safe_root"):
            tc = TestClient(app)
            yield tc

    app.dependency_overrides.clear()


# ─────────────────────────────────────────────
# 首页
# ─────────────────────────────────────────────


class TestIndex:
    """GET / — 首页"""

    def test_index_returns_html(self, client):
        response = client.get("/")
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type


# ─────────────────────────────────────────────
# 项目列表
# ─────────────────────────────────────────────


class TestProjects:
    """GET /api/projects — 列出上传的项目"""

    def test_list_projects_empty(self, client):
        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert data["projects"] == []

    def test_list_projects_with_data(self, client, temp_uploads):
        proj_dir = temp_uploads / "test-project"
        proj_dir.mkdir()
        (proj_dir / "main.py").write_text("print('hello')")
        (proj_dir / "utils.py").write_text("# utils")

        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert len(data["projects"]) == 1
        assert data["projects"][0]["name"] == "test-project"
        assert data["projects"][0]["file_count"] == 2

    def test_list_projects_ignores_files(self, client, temp_uploads):
        """验证只列出目录，忽略文件"""
        (temp_uploads / "orphan.txt").write_text("orphan")

        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert data["projects"] == []


# ─────────────────────────────────────────────
# 上传
# ─────────────────────────────────────────────


class TestUpload:
    """POST /api/upload — 上传 zip 项目"""

    def test_upload_valid_zip(self, client, temp_uploads):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("main.py", "print('hello')")
            zf.writestr("README.md", "# Test Project")
        zip_buffer.seek(0)

        response = client.post(
            "/api/upload",
            files={"file": ("my-project.zip", zip_buffer, "application/zip")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["name"] == "my-project"
        assert data["file_count"] == 2

        # 确认文件确实被解压
        assert (temp_uploads / "my-project" / "main.py").exists()
        assert (temp_uploads / "my-project" / "README.md").exists()

    def test_upload_non_zip(self, client):
        response = client.post(
            "/api/upload",
            files={"file": ("readme.txt", b"not a zip file", "text/plain")},
        )
        assert response.status_code == 400
        data = response.json()
        assert "zip" in data["error"].lower()

    def test_upload_no_extension(self, client):
        """没有扩展名的文件也应该被拒绝"""
        response = client.post(
            "/api/upload",
            files={"file": ("noextension", b"data", "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_upload_oversized(self, client):
        """上传超过 50MB 限制"""
        oversized = b"x" * (50 * 1024 * 1024 + 100)
        response = client.post(
            "/api/upload",
            files={"file": ("big.zip", oversized, "application/zip")},
        )
        assert response.status_code == 400
        data = response.json()
        assert "50MB" in data["error"]

    def test_upload_invalid_zip(self, client):
        """上传 .zip 扩展名但内容无效"""
        response = client.post(
            "/api/upload",
            files={"file": ("corrupt.zip", b"not a real zip", "application/zip")},
        )
        assert response.status_code == 400
        data = response.json()
        assert "无效" in data["error"] or "zip" in data["error"].lower()

    def test_upload_empty_name(self, client):
        """空文件名"""
        response = client.post(
            "/api/upload",
            files={"file": (".zip", b"x", "application/zip")},
        )
        assert response.status_code == 400
        data = response.json()
        assert "无效" in data["error"]

    def test_upload_special_chars_name(self, client):
        """包含特殊字符的项目名，清理后应可用"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("app.py", "# app")
        zip_buffer.seek(0)

        response = client.post(
            "/api/upload",
            files={"file": ("my project (v2)!@#.zip", zip_buffer, "application/zip")},
        )
        assert response.status_code == 200
        data = response.json()
        # 特殊字符被过滤
        # safe_name 过滤规则：只保留 alnum + ._-，空格和特殊符号被移除
        assert data["name"] == "myprojectv2"


# ─────────────────────────────────────────────
# 删除项目
# ─────────────────────────────────────────────


class TestDeleteProject:
    """DELETE /api/projects/{name} — 删除项目"""

    def test_delete_existing_project(self, client, temp_uploads):
        proj_dir = temp_uploads / "to-delete"
        proj_dir.mkdir()

        response = client.delete("/api/projects/to-delete")
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert not proj_dir.exists()

    def test_delete_nonexistent_project(self, client, temp_uploads):
        response = client.delete("/api/projects/ghost")
        assert response.status_code == 404
        assert "不存在" in response.json()["error"]


# ─────────────────────────────────────────────
# 运行任务（需 Mock Agent）
# ─────────────────────────────────────────────


class TestRunTask:
    """POST /api/run — 创建并执行任务"""

    def test_run_task_success(self, client, mock_agent, temp_uploads):
        proj_dir = temp_uploads / "myapp"
        proj_dir.mkdir()
        (proj_dir / "app.py").write_text("# app")

        response = client.post(
            "/api/run",
            json={"task": "add a README.md", "project": "myapp"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_agent.run.assert_called_once()

    def test_run_task_no_project(self, client, mock_agent):
        """不指定 project 时使用当前目录"""
        response = client.post(
            "/api/run",
            json={"task": "list files", "project": ""},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_agent.run.assert_called_once()

    def test_run_task_with_steps(self, client, mock_agent):
        """验证返回结果包含步骤信息"""
        # 构造包含步骤的结果
        step = MagicMock()
        step.index = 1
        step.description = "读取项目结构"
        step_result = MagicMock()
        step_result.step = step
        step_result.description = "读取项目结构"[:120]
        step_result.success = True
        step_result.output = "found 3 files"[:300]

        mock_agent.run.return_value.step_results = [step_result]
        mock_agent.run.return_value.files_modified = ["README.md"]
        mock_agent.run.return_value.verify_result.passed = True

        response = client.post(
            "/api/run",
            json={"task": "add readme"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["steps"]) == 1
        assert data["steps"][0]["index"] == 1
        assert data["files_modified"] == ["README.md"]
        assert data["verify"]["passed"] is True


# ─────────────────────────────────────────────
# 对话历史
# ─────────────────────────────────────────────


class TestConversations:
    """对话 CRUD API"""

    def test_list_conversations_empty(self, client, temp_store):
        response = client.get("/api/conversations")
        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data
        assert data["conversations"] == []

    def test_create_conversation(self, client, temp_store):
        response = client.post(
            "/api/conversations",
            json={"project": "test-project", "task": "add feature"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["project"] == "test-project"
        assert data["task"] == "add feature"

    def test_list_conversations_with_data(self, client, temp_store):
        client.post(
            "/api/conversations",
            json={"project": "proj-a", "task": "fix bug"},
        )
        response = client.get("/api/conversations")
        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 1
        conv = data["conversations"][0]
        assert conv["project"] == "proj-a"
        assert conv["status"] == "pending"

    def test_get_conversation(self, client, temp_store):
        create_resp = client.post(
            "/api/conversations",
            json={"project": "myapp", "task": "refactor utils"},
        )
        conv_id = create_resp.json()["id"]

        response = client.get(f"/api/conversations/{conv_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == conv_id
        assert data["project"] == "myapp"
        assert data["task"] == "refactor utils"
        assert "messages" in data
        assert isinstance(data["messages"], list)

    def test_get_conversation_not_found(self, client, temp_store):
        response = client.get("/api/conversations/nonexistent-id")
        assert response.status_code == 404
        assert "不存在" in response.json()["error"]

    def test_delete_conversation(self, client, temp_store):
        create_resp = client.post(
            "/api/conversations",
            json={"project": "tmp", "task": "cleanup"},
        )
        conv_id = create_resp.json()["id"]

        response = client.delete(f"/api/conversations/{conv_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # 确认已删除
        get_resp = client.get(f"/api/conversations/{conv_id}")
        assert get_resp.status_code == 404

    def test_filter_by_project(self, client, temp_store):
        client.post(
            "/api/conversations",
            json={"project": "alpha", "task": "t1"},
        )
        client.post(
            "/api/conversations",
            json={"project": "beta", "task": "t2"},
        )

        response = client.get("/api/conversations?project=alpha")
        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 1
        assert data["conversations"][0]["project"] == "alpha"

    def test_conversation_lifecycle(self, client, temp_store):
        """完整 CRUD 流程：创建 → 查询 → 删除"""
        # Create
        c1 = client.post(
            "/api/conversations",
            json={"project": "lifecycle", "task": "full test"},
        )
        assert c1.status_code == 200
        conv_id = c1.json()["id"]

        # Read (列表中有)
        c2 = client.get("/api/conversations")
        ids = [c["id"] for c in c2.json()["conversations"]]
        assert conv_id in ids

        # Read (详情)
        c3 = client.get(f"/api/conversations/{conv_id}")
        assert c3.status_code == 200

        # Delete
        c4 = client.delete(f"/api/conversations/{conv_id}")
        assert c4.status_code == 200

        # 删除后列表为空
        c5 = client.get("/api/conversations")
        assert c5.json()["conversations"] == []
