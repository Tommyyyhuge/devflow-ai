"""对话历史存储层

模块 2：ConversationStore CRUD 操作
边界：只实现数据库操作，不连接 Web 或 Agent
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

from devflow.history import init_database

logger = structlog.get_logger()


@dataclass
class Conversation:
    """会话数据对象"""
    id: str
    project: str
    task: str
    status: str = "pending"  # pending/running/completed/failed
    success: Optional[bool] = None
    error: str = ""
    total_tokens: int = 0
    files_modified: list[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Message:
    """消息数据对象"""
    id: int = 0
    conversation_id: str = ""
    role: str = ""  # user/assistant/system/tool
    content: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: Optional[datetime] = None


class ConversationStore:
    """对话历史存储层"""

    def __init__(self, db_path: str | Path = ".devflow/conversations.db"):
        self.db_path = Path(db_path)
        self._ensure_db()

    def _ensure_db(self):
        """确保数据库已初始化"""
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            conn = init_database(self.db_path)
            conn.close()

    def _get_conn(self):
        """获取数据库连接"""
        import sqlite3
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def create_conversation(self, project: str, task: str) -> Conversation:
        """创建新会话"""
        conv = Conversation(
            id=str(uuid.uuid4())[:8],  # 短 ID，易读
            project=project,
            task=task,
            status="pending",
        )

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, project, task, status)
                VALUES (?, ?, ?, ?)
                """,
                (conv.id, conv.project, conv.task, conv.status),
            )
            conn.commit()

        logger.info("创建会话", conversation_id=conv.id, project=project, task=task[:50])
        return conv

    def add_message(self, conversation_id: str, role: str,
                    content: str, metadata: Optional[dict] = None) -> Message:
        """添加消息到会话"""
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata=metadata or {},
        )

        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO messages (conversation_id, role, content, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (msg.conversation_id, msg.role, msg.content,
                 json.dumps(msg.metadata, ensure_ascii=False)),
            )
            conn.commit()
            msg.id = cursor.lastrowid

        return msg

    def update_status(self, conversation_id: str, status: str,
                      success: Optional[bool] = None,
                      error: str = "",
                      total_tokens: int = 0,
                      files_modified: Optional[list[str]] = None):
        """更新会话状态"""
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE conversations
                SET status = ?, success = ?, error = ?,
                    total_tokens = ?, files_modified = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, success, error, total_tokens,
                 json.dumps(files_modified or [], ensure_ascii=False),
                 conversation_id),
            )
            conn.commit()

        logger.info("更新会话状态", conversation_id=conversation_id,
                   status=status, success=success)

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """获取会话详情"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()

        if not row:
            return None

        return self._row_to_conversation(row)

    def get_messages(self, conversation_id: str) -> list[Message]:
        """获取会话的所有消息"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at",
                (conversation_id,),
            ).fetchall()

        return [self._row_to_message(row) for row in rows]

    def list_conversations(self, project: Optional[str] = None,
                          limit: int = 50) -> list[Conversation]:
        """列会话（按时间倒序）"""
        query = "SELECT * FROM conversations"
        params = []

        if project:
            query += " WHERE project = ?"
            params.append(project)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_conversation(row) for row in rows]

    def delete_conversation(self, conversation_id: str):
        """删除会话（级联删除消息）"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()

        logger.info("删除会话", conversation_id=conversation_id)

    @staticmethod
    def _row_to_conversation(row) -> Conversation:
        """数据库行转 Conversation 对象"""
        return Conversation(
            id=row["id"],
            project=row["project"],
            task=row["task"],
            status=row["status"],
            success=row["success"],
            error=row["error"] or "",
            total_tokens=row["total_tokens"] or 0,
            files_modified=json.loads(row["files_modified"] or "[]"),
        )

    @staticmethod
    def _row_to_message(row) -> Message:
        """数据库行转 Message 对象"""
        return Message(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            metadata=json.loads(row["metadata"] or "{}"),
        )
