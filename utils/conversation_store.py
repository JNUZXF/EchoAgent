"""
会话数据库存储模块
文件路径: utils/conversation_store.py
功能: 提供基于 SQLite 的会话与消息持久化能力，作为文件存储的可选镜像或替代后端。

设计目标:
- 在不破坏现有 files/{user}/{agent}/{session}/conversations/* 文件存储的前提下，新增可选的 SQLite 存储
- 支持会话维度的文本快照(display/full/tool_execute/team_context)与逐条消息明细保存
- 默认与文件写入并行，便于调试与生产检索；后续可扩展到 PostgreSQL 等
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple


@dataclass
class SessionKey:
    """唯一标识一个会话的键。"""
    user_id: str
    agent_name: str
    session_id: str


class ConversationStore:
    """
    【模块化设计】【开闭原则】基于 SQLite 的会话存储实现。

    - 不依赖第三方 ORM，使用内置 sqlite3，零额外依赖
    - 自动建表；提供幂等的会话 upsert 与消息批量替换
    - 预留扩展点：未来可增加 PostgreSQL 实现并通过工厂选择
    """

    def __init__(self, db_path: str, logger: Optional[Any] = None) -> None:
        self.db_path = str(db_path)
        self.logger = logger
        self._ensure_schema()

    # ====== 基础: 连接与建表 ======
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _ensure_schema(self) -> None:
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        agent_name TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        UNIQUE(user_id, agent_name, session_id)
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_fk INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                        seq INTEGER NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        UNIQUE(session_fk, seq)
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversation_texts (
                        session_fk INTEGER PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
                        display_md TEXT,
                        full_md TEXT,
                        tool_conversations_json TEXT,
                        tool_execute_md TEXT,
                        team_context_json TEXT,
                        updated_at REAL NOT NULL
                    );
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_seq ON messages(session_fk, seq);")
                conn.commit()
        except Exception as e:
            if self.logger:
                try:
                    self.logger.exception("初始化会话数据库失败: %s", e)
                except Exception:
                    pass

    # ====== 会话与消息 API ======
    def upsert_session(self, key: SessionKey) -> int:
        """插入或获取已存在会话行的主键ID。"""
        now_ts = time.time()
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO sessions(user_id, agent_name, session_id, created_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(user_id, agent_name, session_id) DO NOTHING;
                """,
                (key.user_id, key.agent_name, key.session_id, now_ts),
            )
            conn.commit()
            cur.execute(
                "SELECT id FROM sessions WHERE user_id=? AND agent_name=? AND session_id=?;",
                (key.user_id, key.agent_name, key.session_id),
            )
            row = cur.fetchone()
            return int(row[0]) if row else -1

    def replace_messages(self, session_fk: int, messages: Sequence[dict]) -> None:
        """使用当前内存对话列表替换数据库中的消息，保证序号顺序一致。"""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM messages WHERE session_fk=?;", (session_fk,))
            if messages:
                payload: List[Tuple[int, int, str, str, float]] = []
                now_ts = time.time()
                for idx, m in enumerate(messages):
                    role = str(m.get("role", "assistant"))
                    content = str(m.get("content", ""))
                    payload.append((session_fk, idx, role, content, now_ts))
                cur.executemany(
                    "INSERT INTO messages(session_fk, seq, role, content, created_at) VALUES(?, ?, ?, ?, ?);",
                    payload,
                )
            conn.commit()

    def upsert_text_snapshot(
        self,
        session_fk: int,
        display_md: str,
        full_md: str,
        tool_conversations_json: str,
        tool_execute_md: str,
        team_context_json: str,
    ) -> None:
        now_ts = time.time()
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO conversation_texts(session_fk, display_md, full_md, tool_conversations_json, tool_execute_md, team_context_json, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_fk) DO UPDATE SET
                    display_md=excluded.display_md,
                    full_md=excluded.full_md,
                    tool_conversations_json=excluded.tool_conversations_json,
                    tool_execute_md=excluded.tool_execute_md,
                    team_context_json=excluded.team_context_json,
                    updated_at=excluded.updated_at;
                """,
                (
                    session_fk,
                    display_md,
                    full_md,
                    tool_conversations_json,
                    tool_execute_md,
                    team_context_json,
                    now_ts,
                ),
            )
            conn.commit()

    def save_snapshot(
        self,
        key: SessionKey,
        messages: Sequence[dict],
        display_md: str,
        full_md: str,
        tool_conversations: Sequence[dict],
        tool_execute_md: str,
        team_context: dict,
    ) -> None:
        """将当前会话的整体状态保存到数据库。"""
        try:
            session_fk = self.upsert_session(key)
            self.replace_messages(session_fk, messages)
            self.upsert_text_snapshot(
                session_fk=session_fk,
                display_md=display_md or "",
                full_md=full_md or "",
                tool_conversations_json=json.dumps(tool_conversations, ensure_ascii=False),
                tool_execute_md=tool_execute_md or "",
                team_context_json=json.dumps(team_context or {}, ensure_ascii=False),
            )
            if self.logger:
                try:
                    self.logger.info(
                        "数据库镜像保存完成",
                        extra={
                            "event": "db_snapshot_saved",
                            "rows": len(messages),
                            "db_path": self.db_path,
                        },
                    )
                except Exception:
                    pass
        except Exception as e:
            if self.logger:
                try:
                    self.logger.exception("保存数据库镜像失败: %s", e)
                except Exception:
                    pass


