"""配置管理测试 — Web 端配置保存/加载/加密"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from pydantic import SecretStr

from devflow.config import (
    DevFlowConfig,
    get_config_dict,
    load_config,
    save_config,
)
from devflow.encryption import decrypt_value, encrypt_value, is_encrypted


class TestEncryption:
    """加密工具测试"""

    def test_encrypt_decrypt(self):
        """测试加密和解密"""
        original = "sk-test123456"
        encrypted = encrypt_value(original)

        # 加密后的值应该不同于原文
        assert encrypted != original
        # 加密后的值应该可被识别为加密格式
        assert is_encrypted(encrypted)

        # 解密后应该恢复原文
        decrypted = decrypt_value(encrypted)
        assert decrypted == original

    def test_encrypt_empty(self):
        """测试空值加密"""
        assert encrypt_value("") == ""
        assert decrypt_value("") == ""

    def test_decrypt_plaintext(self):
        """测试解密明文（向后兼容）"""
        plain = "sk-plaintext"
        # 明文应该直接返回
        assert decrypt_value(plain) == plain

    def test_is_encrypted(self):
        """测试加密检测"""
        assert is_encrypted("gAAAAAB...") is True
        assert is_encrypted("plaintext") is False
        assert is_encrypted("") is False


class TestConfigSaveLoad:
    """配置保存和加载测试"""

    @pytest.fixture(autouse=True)
    def clean_config(self, tmp_path):
        """每个测试前清理配置"""
        # 临时修改配置文件路径
        config_file = tmp_path / "config.json"
        with patch("devflow.config._get_config_file", return_value=config_file):
            yield config_file

    def test_save_and_load_config(self, clean_config):
        """测试保存和加载配置"""
        config = DevFlowConfig()
        config.llm.api_key = SecretStr("sk-test123")
        config.llm.model = "deepseek-chat"
        config.agent.context_budget = 100000
        config.budget.weekly_budget = 50.0

        # 保存
        save_config(config)
        assert clean_config.exists()

        # 加载
        loaded = load_config()
        assert loaded.llm.api_key.get_secret_value() == "sk-test123"
        assert loaded.llm.model == "deepseek-chat"
        assert loaded.agent.context_budget == 100000
        assert loaded.budget.weekly_budget == 50.0

    def test_api_key_encrypted_in_file(self, clean_config):
        """测试 API Key 在文件中加密存储"""
        config = DevFlowConfig()
        config.llm.api_key = SecretStr("sk-secret456")

        save_config(config)

        # 读取文件内容
        data = json.loads(clean_config.read_text())
        # API Key 应该被加密
        assert "api_key_encrypted" in data["llm"]
        assert is_encrypted(data["llm"]["api_key_encrypted"])
        # 不应有明文 api_key
        assert "api_key" not in data["llm"]

    def test_config_backup(self, clean_config):
        """测试配置备份"""
        config = DevFlowConfig()
        config.llm.model = "model-v1"

        # 第一次保存
        save_config(config)

        # 修改并再次保存
        config.llm.model = "model-v2"
        save_config(config)

        # 检查备份文件
        backup_file = clean_config.with_suffix(".json.bak")
        assert backup_file.exists()
        backup_data = json.loads(backup_file.read_text())
        assert backup_data["llm"]["model"] == "model-v1"

    def test_get_config_dict_exclude_api_key(self):
        """测试获取配置字典（不包含 API Key）"""
        config = DevFlowConfig()
        config.llm.api_key = SecretStr("sk-secret")

        # 默认不包含 API Key
        data = get_config_dict(config, include_api_key=False)
        assert "api_key" not in data["llm"]

        # 包含 API Key
        data_with_key = get_config_dict(config, include_api_key=True)
        assert data_with_key["llm"]["api_key"] == "sk-secret"

    def test_partial_update(self, clean_config):
        """测试部分更新配置"""
        # 初始配置
        config = DevFlowConfig()
        config.llm.model = "initial-model"
        config.agent.context_budget = 100000
        save_config(config)

        # 模拟部分更新（只更新 model）
        loaded = load_config()
        assert loaded.llm.model == "initial-model"
        assert loaded.agent.context_budget == 100000


class TestConfigValidation:
    """配置验证测试"""

    def test_invalid_max_tokens(self):
        """测试无效的 max_tokens"""
        from devflow.config import LLMConfig

        with pytest.raises(ValueError, match="必须大于 0"):
            LLMConfig(max_tokens_per_request=-1)

        with pytest.raises(ValueError, match="不能超过 128000"):
            LLMConfig(max_tokens_per_request=200000)

    def test_invalid_budget(self):
        """测试无效的预算"""
        from devflow.config import BudgetConfig

        with pytest.raises(ValueError, match="预算必须大于 0"):
            BudgetConfig(weekly_budget=-10)

        with pytest.raises(ValueError, match="预算不能超过 10000"):
            BudgetConfig(weekly_budget=20000)

    def test_invalid_base_url(self):
        """测试无效的 base_url"""
        from devflow.config import LLMConfig

        with pytest.raises(ValueError, match="必须以 http:// 或 https:// 开头"):
            LLMConfig(base_url="ftp://invalid.com")


class TestConfigAPI:
    """配置 API 测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from fastapi.testclient import TestClient
        from devflow.api.server import app
        return TestClient(app)

    def test_get_config_endpoint(self, client):
        """测试获取配置端点"""
        response = client.get("/api/config")
        assert response.status_code == 200

        data = response.json()
        assert "llm" in data
        assert "agent" in data
        assert "budget" in data
        # 不应包含 API Key
        assert "api_key" not in data["llm"]

    def test_update_config_endpoint(self, client):
        """测试更新配置端点"""
        config_data = {
            "llm": {
                "model": "deepseek-chat",
                "max_tokens_per_request": 16000,
            },
            "budget": {
                "weekly_budget": 100.0,
            },
        }

        response = client.post("/api/config", json=config_data)
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True

        # 验证配置已更新
        response = client.get("/api/config")
        data = response.json()
        assert data["llm"]["model"] == "deepseek-chat"
        assert data["llm"]["max_tokens_per_request"] == 16000
        assert data["budget"]["weekly_budget"] == 100.0

    def test_settings_page(self, client):
        """测试设置页面"""
        response = client.get("/settings")
        assert response.status_code == 200
        assert "系统设置" in response.text
