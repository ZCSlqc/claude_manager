#!/usr/bin/env python3
"""Claude Code 托管代理 — FastAPI 持续服务。

启动:
    source .venv/bin/activate
    uvicorn server:app --host 0.0.0.0 --port 8112
"""

import asyncio
import json
import os
import random
import subprocess
import sys
import threading
import re
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel

from data import db as database

# ── 根目录 ────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent

# ── 日志 ──────────────────────────────────────────────────
LOG_DIR = ROOT / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger.remove()
logger.add(
    LOG_DIR / "server.log",
    rotation="10 MB",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    encoding="utf-8",
)
logger.add(
    LOG_DIR / "error.log",
    rotation="10 MB",
    retention="7 days",
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | ERROR | {message}",
    encoding="utf-8",
)

# ── 配置 ──────────────────────────────────────────────────
SUBPROCESS_TIMEOUT = 3600
MAX_RETRIES = 1
PID_CHECK_INTERVAL = 60

# ── Pydantic 模型 ─────────────────────────────────────────

class InternalRequest(BaseModel):
    user: str
    dir: str
    message: str

class SessionResponse(BaseModel):
    session_id: str
    project_id: str = ""
    session_avatar_id: int = 1
    status: str  # success | failed | started
    output: str = ""
    error: str | None = None
    retries: int = 0
    claude_result: dict = {}

# ── 全局状态 ──────────────────────────────────────────────
app = FastAPI(title="Claude Code Proxy")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 核心: 解析 Claude JSON ───────────────────────────────

_CLAUDE_CMD = [
    "claude",
    "--dangerously-skip-permissions",
    "-p",
    "--output-format", "json",
]

# ── 异步调度状态 ─────────────────────────────────────────
# 防止同一项目并发发送: project_id -> bool
_busy_locks: dict[str, bool] = {}


def _parse_claude_json(stdout: str) -> dict:
    """解析 Claude --output-format json 的 stdout，提取子字段。"""
    jr = {}
    try:
        jr = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        pass
    return {
        "output": jr.get("result", ""),
        "session_id": jr.get("session_id", ""),
        "uuid": jr.get("uuid", ""),
        "num_turns": jr.get("num_turns", 0),
        "cost_usd": jr.get("total_cost_usd", 0),
        "subtype": jr.get("subtype", ""),
        "is_error": jr.get("is_error", False),
        "stop_reason": jr.get("stop_reason", ""),
        "terminal_reason": jr.get("terminal_reason", ""),
        "errors": jr.get("errors", []),
        "full": jr,
    }


def _determine_status(parsed: dict) -> int:
    """根据 Claude 返回的 JSON 推断 status 值。"""
    # /new 或 /clear 清空上下文
    if parsed["stop_reason"] is None and parsed["output"] == "" and parsed["num_turns"] == 0:
        return 0
    # 正常完成
    if parsed["subtype"] == "success" and not parsed["is_error"] and parsed["stop_reason"] in ("end_turn", None):
        return 0
    # API 临时错误
    if parsed["subtype"] == "success" and parsed["is_error"] and parsed["stop_reason"] == "stop_sequence":
        return 1
    # max_turns 超限
    if parsed["subtype"] == "error_max_turns" and parsed["is_error"] and parsed["stop_reason"] == "tool_use":
        return 2
    return 4


def _run_claude_sync(message: str, project_dir: str, session_id: str | None = None, project_id: str | None = None) -> dict:
    """同步执行 claude subprocess。返回 {success, output, error, parsed, raw_stdout}。

    时序：创建进程 → 立即 PID 写 DB → communicate → 解析
    """
    cmd = list(_CLAUDE_CMD)
    if session_id:
        cmd.extend(["--resume", session_id])
    cmd.append(message)

    logger.info(f'claude | session={"resume" if session_id else "new"} dir={project_dir} msg="{message[:80]}"')

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=project_dir
    )
    pid = proc.pid

    # 立即写 PID 到 DB（进程正在运行中，周期性检测器能抓到）
    if project_id:
        database.update_project(project_id, subprocess_pid=pid)

    # 超时处理
    try:
        stdout, stderr = proc.communicate(timeout=SUBPROCESS_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        logger.error(f'claude | TIMEOUT after {SUBPROCESS_TIMEOUT}s | session={session_id or "new"} pid={pid}')
        return {
            "success": False,
            "output": "",
            "error": f"Timeout after {SUBPROCESS_TIMEOUT}s (returncode={proc.returncode})",
            "pid": pid,
            "parsed": {"full": {}},
            "raw_stdout": "",
        }

    raw_stdout = stdout

    # JSON 解析失败
    try:
        parsed = _parse_claude_json(raw_stdout)
    except Exception:
        return {
            "success": False,
            "output": "",
            "error": "stdout JSON 解析失败",
            "pid": pid,
            "parsed": {"full": {}},
            "raw_stdout": raw_stdout[:500],
        }

    if parsed["is_error"]:
        logger.error(f'claude | error after {time.time():.1f}s | session={parsed["session_id"]} subtype={parsed["subtype"]}')
    else:
        logger.info(f'claude | OK | session={parsed["session_id"]} turns={parsed["num_turns"]}')

    return {
        "success": True,
        "output": parsed["output"],
        "error": None,
        "pid": pid,
        "parsed": parsed,
        "raw_stdout": raw_stdout,
    }


def _auto_retry(dir_path: str, session_id: str, status: int) -> tuple[bool, str]:
    """自动自愈。返回 (成功, 新输出)。结果不入库。"""
    retry_messages = {
        1: "Don't read too much once, continue your work.",
        2: "Continue.",
        3: "Too much time, give me a summary of what you have done.",
        4: "Repeat what you have done.",
    }
    msg = retry_messages.get(status)
    if not msg:
        return False, ""

    logger.warning(f"auto-retry: status={status}, msg=\"{msg}\"")

    cmd = list(_CLAUDE_CMD)
    cmd.extend(["--resume", session_id])
    cmd.append(msg)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=dir_path, timeout=SUBPROCESS_TIMEOUT)
        stdout = result.stdout
        parsed = _parse_claude_json(stdout)
        return True, parsed["output"]
    except Exception as e:
        logger.error(f"auto-retry failed: {e}")
        return False, ""


# ── 后台: 周期性 PID 健康检测 ─────────────────────────────

async def _periodic_pid_checker():
    """每 60 秒检查一次：is_finished=0 但进程已死的 zombie PID。"""
    while True:
        await asyncio.sleep(PID_CHECK_INTERVAL)
        try:
            conn = database._connect()
            rows = conn.execute(
                "SELECT project_id, user_id, folder_name, subprocess_pid FROM project "
                "WHERE is_finished=0 AND subprocess_pid > 0"
            ).fetchall()
            conn.close()

            for row in rows:
                pid = row["subprocess_pid"]
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    # 进程已死 → 标记 status=5
                    database.update_project(
                        row["project_id"],
                        is_finished=1,
                        status=5,
                        subprocess_pid=0,
                    )
                    logger.warning(
                        f"zombie_pid: user={row['user_id']}, dir={row['folder_name']}, pid={pid}"
                    )
                except PermissionError:
                    # 进程存在但跨用户，不做处理
                    pass
        except Exception as e:
            logger.error(f"pid_checker error: {e}")


# ── 内部路由: 实际业务逻辑 ─────────────────────────────

def _run_claude_async(project_id: str, dir_path: str, message: str, session_id: str | None):
    """后台线程：执行 Claude 调用并更新 DB。"""
    try:
        result = _run_claude_sync(
            message=message,
            project_dir=dir_path,
            session_id=session_id,
            project_id=project_id,
        )

        # 进程已结束，重置 PID
        database.update_project(project_id, subprocess_pid=0)

        # 超时
        if not result["success"] and "Timeout" in result.get("error", ""):
            database.update_project(
                project_id,
                claude_result=json.dumps({"error": "timeout"}, ensure_ascii=False),
                is_finished=1,
                status=3,
            )
            logger.error(f"async timeout: project={project_id}")
            return

        # JSON 解析失败
        if not result["parsed"]["full"] and result["error"] == "stdout JSON 解析失败":
            database.update_project(
                project_id,
                claude_result=json.dumps({"raw": result["raw_stdout"]}, ensure_ascii=False),
                is_finished=1,
                status=4,
            )
            logger.error(f"async json_parse_fail: project={project_id}")
            return

        parsed = result["parsed"]
        status = _determine_status(parsed)

        # 累加 token（从根级别 usage 读取）
        usage = parsed["full"].get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        current = database.get_project(project_id)
        prev_input = current.get("total_inputTokens", 0) if current else 0
        prev_output = current.get("total_outputTokens", 0) if current else 0

        # 自动自愈
        retries_done = 0
        if status in (1, 2, 3, 4) and parsed.get("session_id"):
            retry_success, _ = _auto_retry(dir_path, parsed["session_id"], status)
            if retry_success:
                retries_done = 1

        final_status = 0 if not result["error"] else status
        if status in (1, 2, 3, 4) and retries_done == 0:
            final_status = status

        database.update_project(
            project_id,
            session_id=parsed.get("session_id", ""),
            claude_result=json.dumps(parsed["full"], ensure_ascii=False),
            is_finished=1,
            status=final_status,
            total_inputTokens=prev_input + input_tokens,
            total_outputTokens=prev_output + output_tokens,
        )

        if final_status == 0:
            logger.info(
                f"async ok: project={project_id} "
                f"cost={parsed.get('cost_usd', 0):.4f} turns={parsed.get('num_turns', 0)}"
            )
        else:
            logger.warning(
                f"async finished: project={project_id} status={final_status} retries={retries_done}"
            )

    except Exception as e:
        logger.exception(f"async_claude error for project={project_id}: {e}")
        database.update_project(
            project_id,
            is_finished=1,
            status=5,
        )
    finally:
        _busy_locks.pop(project_id, None)


@app.post("/api/claude")
def _internal_claude(req: InternalRequest):
    """核心入口：查/建 user + 查/建 project + 创建 session(如需要) + 后台执行 Claude。
    返回: {project_id}，后台线程后续更新 DB。
    """
    try:
        user = req.user
        dir_path = req.dir
        message = req.message

        # ── 步骤 0: dir 非路径处理 ──
        if not dir_path.startswith('/'):
            safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '', dir_path).strip() or 'untitled'
            dir_path = f'/data/test/{safe_name}'

        logger.info(f"api/claude | user={user} dir={dir_path} msg={message[:50]}")

        # ── 步骤 1: 查找/创建 user ──
        db_user = database.get_user(user)
        if not db_user:
            db_user = database.add_user(user)

        if not db_user or "error" in db_user:
            raise HTTPException(500, f"用户处理失败: {db_user.get('error', '')}")

        user_id = db_user["user_id"]

        # ── 步骤 2: 查找/创建 project ──
        project = database.get_project_by_path(user_id, dir_path)
        if not project:
            project = database.add_project(user_id, dir_path)
            if "error" in project:
                project = database.get_project_by_path(user_id, dir_path)

        if not project or "error" in project:
            raise HTTPException(500, f"项目处理失败: {project.get('error', '')}")

        project_id = project["project_id"]
        session_id = project.get("session_id", "")
        is_finished = project.get("is_finished", 1)

        # ── 步骤 3: 兜底创建目录（不管项目是否存在，目录必须在） ──
        if not Path(dir_path).exists():
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            logger.info(f"mkdir | created project dir: {dir_path}")

        # ── 步骤 4: 并发保护 ──
        if _busy_locks.get(project_id):
            raise HTTPException(409, {"status": "failed", "error": "session 使用中，请勿重复发送"})

        if is_finished == 0 and project.get("subprocess_pid", 0) > 0:
            _busy_locks[project_id] = True
            raise HTTPException(
                409,
                {"status": "failed", "error": "session 使用中，请勿重复发送", "retries": 0},
            )

        # 标记为忙碌
        _busy_locks[project_id] = True

        # ── 步骤 5: 首次创建 session（如果还没有） ──
        if not session_id:
            # 同步等待首次 session 创建（必须拿到 session_id）
            step_a = _run_claude_sync(
                message="你好",
                project_dir=dir_path,
                project_id=project_id,
            )
            new_sid = step_a["parsed"]["session_id"]
            if not new_sid:
                _busy_locks.pop(project_id, None)
                raise HTTPException(500, "无法创建会话：未拿到 session_id")

            # 只更新 session_id，不再标记 is_finished，避免前端误判为"已完成"
            database.update_project(project_id, session_id=new_sid)
            session_id = new_sid

        # ── 步骤 6: 标记为进行中，启动后台线程，立即返回 ──
        database.update_project(
            project_id,
            user_input=message,
            is_finished=0,
        )

        # 启动后台线程执行 Claude
        threading.Thread(
            target=_run_claude_async,
            args=(project_id, dir_path, message, session_id),
            daemon=True,
            name=f"claude-{project_id[:8]}",
        ).start()

        # 立即返回 project_id
        return {"state": "success", "project_id": project_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"_internal_claude error: {e}")
        raise HTTPException(500, f"内部错误: {e}")


# ── 项目 CRUD ─────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    """启动周期性 PID 检测。"""
    asyncio.create_task(_periodic_pid_checker())
    logger.info("PID health checker started")


@app.get("/health")
def health():
    return {"status": "ok"}


# ── 项目 CRUD ─────────────────────────────────────────────

@app.get("/projects")
def list_projects_endpoint(user_id: str | None = None):
    """列出项目（可选按用户过滤）。"""
    return database.list_projects(user_id)


@app.get("/projects/{project_id}")
def get_project_endpoint(project_id: str):
    """获取项目详情。"""
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(404, f"项目不存在: {project_id}")
    return project


@app.patch("/projects/{project_id}")
def update_project_endpoint(project_id: str, body: dict):
    """更新项目（session_avatar_id、is_finished、status、session_id 等）。"""
    project = database.update_project(project_id, **body)
    if not project:
        raise HTTPException(404, f"项目不存在: {project_id}")
    return project


@app.delete("/projects/{project_id}")
def delete_project_endpoint(project_id: str):
    """删除项目（DB + Claude JSONL + session 目录 + 空项目目录）。"""
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(404, f"项目不存在: {project_id}")

    # 删除 Claude JSONL 文件
    session_id = project.get("session_id", "")
    claude_dir = Path(os.path.expanduser("~/.claude/projects"))
    if session_id:
        for p in claude_dir.rglob(f"{session_id}.jsonl"):
            p.unlink()
            logger.info(f'delete | Removed JSONL: {p}')
            break
        # 删除 session 目录 {session_id}/
        session_dir = claude_dir / session_id
        if session_dir.is_dir():
            shutil.rmtree(session_dir)
            logger.info(f'delete | Removed session dir: {session_dir}')

    # 删除用户项目目录（如果为空）
    folder_name = project.get("folder_name", "")
    if folder_name:
        folder_path = Path(folder_name)
        if folder_path.is_dir() and not any(folder_path.iterdir()):
            folder_path.rmdir()
            logger.info(f'delete | Removed empty project dir: {folder_path}')

    # 清理：如果 Claude projects 目录下只剩空 memory 目录，也删
    if claude_dir.is_dir():
        contents = list(claude_dir.iterdir())
        if all(c.name == 'memory' and c.is_dir() and not any(c.iterdir()) for c in contents):
            for c in contents:
                shutil.rmtree(c)
                logger.info(f'delete | Removed leftover empty dir: {c}')
        # 删完 memory 后目录为空，也删掉 claude projects 目录
        if claude_dir.is_dir() and not any(claude_dir.iterdir()):
            claude_dir.rmdir()
            logger.info(f'delete | Removed empty claude projects dir: {claude_dir}')

    database.delete_project(project_id)
    logger.info(f'delete | Project deleted: {project_id}')
    return {"deleted": project_id}


@app.post("/continue/{project_id}")
def continue_project(project_id: str):
    """向指定项目发送 Continue.（resume 方式）。"""
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(404, f"项目不存在: {project_id}")

    session_id = project.get("session_id", "")
    if not session_id:
        raise HTTPException(400, "项目没有活跃的 session_id")

    result = _run_claude_sync(
        message="Continue.",
        project_dir=project["folder_name"],
        session_id=session_id,
        project_id=project_id,
    )

    if result["success"] and result["parsed"]["full"]:
        database.update_project(
            project_id,
            claude_result=json.dumps(result["parsed"]["full"], ensure_ascii=False),
            is_finished=1,
            status=_determine_status(result["parsed"]),
        )

    return {
        "project_id": project_id,
        "status": "success" if result["success"] else "failed",
        "output": result["output"],
        "error": result["error"],
    }


# ── Heartbeat ─────────────────────────────────────────────

@app.post("/heartbeat/{project_id}")
def heartbeat(project_id: str):
    """心跳更新: 只更新 updated_at + is_finished=0, 让前端立刻感知。"""
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(404, f"项目不存在: {project_id}")

    database.update_project(
        project_id,
        is_finished=0,
    )
    updated = database.get_project(project_id)
    return updated


# ── 用户 CRUD ─────────────────────────────────────────────

@app.get("/users")
def list_users_endpoint():
    """列出所有对接人。"""
    return database.list_users()


# ── 兼容旧路由 ────────────────────────────────────────────

@app.get("/sessions")
def list_sessions_endpoint(limit: int = 50):
    """兼容旧名 GET /sessions?limit=50。"""
    return database.list_projects()


# ── 静态文件 ──────────────────────────────────────────────

# ── 头像 ──────────────────────────────────────────────────

AVATAR_DIR = ROOT / "backend" / "static" / "avatars"


@app.get("/avatar/{avatar_type}/{num}.png")
def get_avatar(avatar_type: str, num: int):
    """返回指定类型和编号的头像 PNG。"""
    if avatar_type not in ("user", "session"):
        raise HTTPException(404, "Unknown avatar type")
    path = AVATAR_DIR / avatar_type / f"avatar_{num:03d}.png"
    if not path.exists():
        path = AVATAR_DIR / avatar_type / "avatar_001.png"
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type="image/png")

STATIC_DIR = ROOT / "backend" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 前端构建产物（html=True 放最后，兜底匹配）
FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
