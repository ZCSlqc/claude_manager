#!/usr/bin/env python3
"""Claude Code 代理数据库存储（SQLite）。

表结构：
  user       — 对接人
  project    — 项目（含 claude_result 完整 JSON）

全表主键统一使用 32 位 UUID，摒弃数字自增 ID。
"""

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

DB_DIR = Path(os.path.expanduser('/data/openclaw/claude_manager/data'))
DB_PATH = DB_DIR / 'claude_manager.db'


def _uid() -> str:
    return uuid.uuid4().hex


def _connect() -> sqlite3.Connection:
    """获取数据库连接，自动建库建表。"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS user (
            user_id       TEXT PRIMARY KEY,
            name          TEXT    NOT NULL UNIQUE,
            user_avatar_id INTEGER NOT NULL DEFAULT 1,
            created_at    REAL   NOT NULL DEFAULT (strftime('%s','now')),
            updated_at    REAL   NOT NULL DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS project (
            project_id      TEXT PRIMARY KEY,
            user_id         TEXT    NOT NULL REFERENCES user(user_id),
            folder_name     TEXT    NOT NULL DEFAULT '',
            claude_path     TEXT    NOT NULL DEFAULT '',
            session_id      TEXT    NOT NULL DEFAULT '',
            user_input      TEXT    NOT NULL DEFAULT '',
            is_finished     INTEGER NOT NULL DEFAULT 1,
            subprocess_pid  INTEGER NOT NULL DEFAULT 0,
            status          INTEGER NOT NULL DEFAULT 0,
            claude_result   TEXT    NOT NULL DEFAULT '',
            claude_output   TEXT    NOT NULL DEFAULT '',
            session_avatar_id INTEGER NOT NULL DEFAULT 1,
            total_inputTokens   INTEGER NOT NULL DEFAULT 0,
            total_outputTokens  INTEGER NOT NULL DEFAULT 0,
            created_at      REAL   NOT NULL DEFAULT (strftime('%s','now')),
            updated_at      REAL   NOT NULL DEFAULT (strftime('%s','now')),
            UNIQUE(user_id, folder_name)
        );

        CREATE INDEX IF NOT EXISTS idx_project_user    ON project(user_id);
        CREATE INDEX IF NOT EXISTS idx_project_path    ON project(folder_name);
        CREATE INDEX IF NOT EXISTS idx_project_session  ON project(session_id);
        CREATE INDEX IF NOT EXISTS idx_project_finish   ON project(is_finished);
        CREATE INDEX IF NOT EXISTS idx_project_updated  ON project(updated_at);
    """)
    conn.commit()


# ── User ─────────────────────────────────────────────────

def add_user(name: str) -> dict:
    """添加对接人。返回 {user_id, name, user_avatar_id} 或 {error: ...}。"""
    conn = _connect()
    try:
        uid = _uid()
        avatar_id = uuid.uuid4().int % 33 + 1
        conn.execute(
            "INSERT INTO user (user_id, name, user_avatar_id) VALUES (?, ?, ?)",
            (uid, name, avatar_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM user WHERE user_id=?", (uid,)).fetchone()
        return dict(row) if row else {}
    except sqlite3.IntegrityError:
        return {'error': f'用户已存在: {name}'}
    finally:
        conn.close()


def list_users() -> list[dict]:
    """列出所有对接人。"""
    conn = _connect()
    rows = conn.execute("SELECT * FROM user ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user(name: str) -> dict | None:
    """按名称查找对接人。"""
    conn = _connect()
    row = conn.execute("SELECT * FROM user WHERE name=?", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    """按 ID 查找对接人。"""
    conn = _connect()
    row = conn.execute("SELECT * FROM user WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_user(user_id: str) -> dict:
    """删除对接人（级联删除关联项目）。"""
    conn = _connect()
    conn.execute("DELETE FROM project WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM user WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    return {'deleted': user_id}


# ── Project ───────────────────────────────────────────────

def add_project(user_id: str, folder_name: str) -> dict:
    """添加项目。返回 {project_id, ...} 或 {error: ...}。"""
    conn = _connect()
    try:
        pid = _uid()
        ts = time.time()
        avatar_id = int.from_bytes(folder_name.encode(), 'big') % 100 + 1
        # claude_path: ~/.claude/projects/{dir_with_dashes}
        claude_path = Path(os.path.expanduser('~/.claude/projects/' + folder_name.replace('/', '-'))).as_posix()
        conn.execute(
            "INSERT INTO project (project_id, user_id, folder_name, claude_path, session_avatar_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (pid, user_id, folder_name, claude_path, avatar_id, ts, ts),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM project WHERE project_id=?", (pid,)).fetchone()
        return dict(row) if row else {}
    except sqlite3.IntegrityError:
        return {'error': f'项目已存在: {folder_name}'}
    finally:
        conn.close()


def list_projects(user_id: str | None = None) -> list[dict]:
    """列出项目。可选按用户过滤。"""
    conn = _connect()
    if user_id:
        rows = conn.execute("SELECT * FROM project WHERE user_id=? ORDER BY updated_at DESC", (user_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM project ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_project(project_id: str) -> dict | None:
    """按 ID 查找项目。"""
    conn = _connect()
    row = conn.execute("SELECT * FROM project WHERE project_id=?", (project_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_project_by_path(user_id: str, folder_name: str) -> dict | None:
    """按用户 + 目录路径查找项目。"""
    conn = _connect()
    row = conn.execute("SELECT * FROM project WHERE user_id=? AND folder_name=?", (user_id, folder_name)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_project(project_id: str, **fields) -> dict | None:
    """更新项目信息。"""
    allowed = {'session_id', 'claude_result', 'claude_output', 'user_input', 'is_finished', 'subprocess_pid', 'status', 'session_avatar_id', 'total_inputTokens', 'total_outputTokens'}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return None
    conn = _connect()
    set_clause = ', '.join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [project_id]
    conn.execute(
        f"UPDATE project SET {set_clause}, updated_at=strftime('%s','now') WHERE project_id=?",
        values,
    )
    conn.commit()
    row = conn.execute("SELECT * FROM project WHERE project_id=?", (project_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_zombie_projects() -> list[dict]:
    """查找僵尸项目：subprocess_pid > 0 AND is_finished = 0。"""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM project WHERE subprocess_pid > 0 AND is_finished = 0"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_project(project_id: str) -> dict:
    """删除项目（DB）。"""
    conn = _connect()
    conn.execute("DELETE FROM project WHERE project_id=?", (project_id,))
    conn.commit()
    conn.close()
    return {'deleted': project_id}
