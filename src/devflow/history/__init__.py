"""对话历史数据库模型

模块 1：数据库表设计
边界：只定义表结构，不实现业务逻辑
"""

import sqlite3
from pathlib import Path

SCHEMA = """
-- 会话表：每个 AI 编程任务对应一个会话
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,           -- UUID
    project TEXT NOT NULL,          -- 项目名/路径
    task TEXT NOT NULL,             -- 用户的原始任务描述
    status TEXT DEFAULT 'pending',  -- pending/running/completed/failed
    success BOOLEAN,                -- 最终是否成功
    error TEXT,                     -- 错误信息（如果有）
    total_tokens INTEGER DEFAULT 0, -- 总 Token 使用量
    files_modified TEXT,            -- JSON 数组：修改的文件列表
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 消息表：会话中的每条消息（用户输入、AI 回复、工具调用等）
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,             -- user/assistant/system/tool
    content TEXT,                   -- 消息内容
    metadata TEXT,                  -- JSON：tokens, latency, tool_name 等
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- 索引：加速查询
CREATE INDEX IF NOT EXISTS idx_messages_conv
    ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_project
    ON conversations(project);
CREATE INDEX IF NOT EXISTS idx_conversations_status
    ON conversations(status);
"""


def init_database(db_path: str | Path = ".devflow/conversations.db") -> sqlite3.Connection:
    """初始化数据库，创建表结构

    Args:
        db_path: 数据库文件路径（默认在项目目录的 .devflow/ 下）

    Returns:
        sqlite3.Connection: 数据库连接
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    # 执行建表语句
    conn.executescript(SCHEMA)
    conn.commit()

    return conn
