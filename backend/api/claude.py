"""Claude 异步执行 & 心跳路由。"""

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import update_project, get_project
from ..response import ok as _ok

router = APIRouter()

_CLAUDE_CMD = [
    "claude", "-p",
    "--dangerously-skip-permissions",
    "--output-format", "json",
]

SUBPROCESS_TIMEOUT = 1200


class ClaudeRequest(BaseModel):
    user: str
    dir: str
    message: str


async def _get_sessionid(dir_path: str, message: str = "你好", timeout: int = 120) -> str:
    cmd = [*_CLAUDE_CMD, "--max-turns", "1", message]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        cwd=dir_path,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        stdout = stdout.decode() if isinstance(stdout, bytes) else stdout
        jr = json.loads(stdout or "{}")
        return jr.get("session_id", "")
    except Exception:
        return ""


# ── 日志统一前缀 ──

def _log_claude(project_id: str) -> str:
    return f"[{project_id[:8]}]"


# ── 核心 ──

async def _run_claude(project_id: str, dir_path: str, message: str, session_id: str | None):
    """异步执行 Claude：进程 -> PID -> await -> 解析写 DB。"""
    from loguru import logger
    try:
        prefix = _log_claude(project_id)
        cmd = [*_CLAUDE_CMD, "--resume", session_id, message]
        logger.info(f"[{prefix}] START :dir={dir_path} msg={message[:80]}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=dir_path,
        )
        pid = proc.pid
        update_project(project_id, subprocess_pid=pid)

        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=SUBPROCESS_TIMEOUT)
            stdout = stdout.decode() if isinstance(stdout, bytes) else stdout
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            update_project(project_id, subprocess_pid=0, claude_result=json.dumps({"error": "timeout"}, ensure_ascii=False), is_finished=1, status=4)
            logger.info(f"[CALLBACK] success=False project_id={project_id} msg=TIMEOUT")
            logger.error(f"[{prefix}] FAIL :status=4(TIMEOUT)")
            return

        update_project(project_id, subprocess_pid=0)

        try:
            jr = json.loads(stdout or "{}")
        except json.JSONDecodeError:
            update_project(project_id, claude_result=json.dumps({"error": "invalid json"}, ensure_ascii=False), is_finished=1, status=5)
            logger.info(f"[CALLBACK] success=False project_id={project_id} msg=json_parse_fail")
            logger.error(f"[{prefix}] FAIL :status=5(JSON parse fail) stdout={repr(stdout[:200])}")
            return

        usage = jr.get("usage", {})
        cur = get_project(project_id)
        prev_in = cur.get("total_inputTokens", 0) if cur else 0
        prev_out = cur.get("total_outputTokens", 0) if cur else 0

        is_error = jr.get("is_error", False)
        subtype = jr.get("subtype", "")
        stop_reason = jr.get("stop_reason", "")
        status = 0
        if subtype == "success" and not is_error and stop_reason == "end_turn":
            status = 0
        elif subtype == "success" and is_error and stop_reason == "stop_sequence":
            status = 1
        elif subtype == "error_max_turns" and is_error and stop_reason == "tool_use":
            status = 2
        else:
            status = 3

        update_project(
            project_id,
            session_id=jr.get("session_id", ""),
            claude_output=jr.get("result", ""),
            claude_result=json.dumps(jr, ensure_ascii=False),
            status=status,
            total_inputTokens=prev_in + usage.get("input_tokens", 0),
            total_outputTokens=prev_out + usage.get("output_tokens", 0),
            is_finished=1,
        )

        result = jr.get("result", "")

        if status == 0:
            logger.info(f"[{prefix}] SUCCESS :turns={jr.get('num_turns', 0)}")
            logger.info(f"[CALLBACK] success=True project_id={project_id} result={repr(result[:200])}")
        else:
            logger.warning(f"[{prefix}] FAIL :status={status}")
            logger.info(f"[CALLBACK] success=Flase project_id={project_id} result={repr(result[:200])}")

    except Exception as e:
        logger.exception(f"[{prefix}] FAIL :status=5(async crash)")
        logger.info(f"[CALLBACK] success=False project_id={project_id} msg={e}")
        update_project(project_id, subprocess_pid=0, is_finished=1, status=5)


@router.post("/api/claude")
async def api_claude(req: ClaudeRequest):
    """发送消息：查/建 user + 查/建 project + session + 异步执行。
    立即返回 {project_id}。
    """
    from loguru import logger
    from .. import db as database

    try:
        user = req.user
        dir_path = req.dir
        message = req.message

        logger.info(f"[API] user={user} dir={dir_path} msg={message[:50]}")

        if not message:
            raise HTTPException(400, "消息不能为空")

        db_user = database.get_user(user)
        if not db_user:
            db_user = database.add_user(user)
        if not db_user or "error" in db_user:
            raise HTTPException(500, f"用户处理失败: {db_user.get('error', '')}")

        project = database.get_project_by_path(db_user["user_id"], dir_path)
        if not project:
            project = database.add_project(db_user["user_id"], dir_path)
        if not project or "error" in project:
            raise HTTPException(500, f"项目处理失败: {project.get('error', '')}")

        project_id = project["project_id"]
        session_id = project.get("session_id", "")

        if not Path(dir_path).exists():
            Path(dir_path).mkdir(parents=True, exist_ok=True)

        if project.get("is_finished", 1) == 0:
            raise HTTPException(409, f"session 使用中，请勿重复发送 (project_id={project_id})")

        # 立即锁住，防止并发
        update_project(project_id, is_finished=0)

        if not session_id:
            for _ in range(3):
                new_sid = await _get_sessionid(dir_path, "你好")
                if new_sid:
                    update_project(project_id, session_id=new_sid)
                    session_id = new_sid
                    prefix = _log_claude(project_id)
                    logger.info(f"[{prefix}] NEW :session_id={session_id}")
                    break
            else:
                logger.info(f"[CALLBACK] success=False project_id={project_id} msg=session_create_failed")
                update_project(project_id, is_finished=1)
                raise HTTPException(500, "无法创建会话：未拿到 session_id")

        update_project(project_id, user_input=message, claude_output="", claude_result="")
        asyncio.create_task(
            _run_claude(project_id, dir_path, message, session_id),
            name=f"claude-{project_id[:8]}",
        )

        return _ok(200, {"project_id": project_id})

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[API] error: {e}")
        raise HTTPException(500, f"内部错误: {e}")


@router.get("/api/retry/{project_id}")
async def api_retry(project_id: str):
    """重试项目：用已有的 session_id 和 user_input 重新执行。"""
    from loguru import logger

    try:
        project = get_project(project_id)
        if not project:
            raise HTTPException(404, f"项目不存在: {project_id}")

        session_id = project.get("session_id", "")
        dir_path = project.get("folder_name", "")
        message = project.get("user_input", "") + "\n继续完成未完成的内容。"
        status = project.get("status", "")
        if status == 0:
            raise HTTPException(400, "项目已经执行成功，不需要重试")

        if not Path(dir_path).exists():
            Path(dir_path).mkdir(parents=True, exist_ok=True)

        if project.get("is_finished", 1) == 0:
            raise HTTPException(409, f"session 使用中，请勿重复发送 (project_id={project_id})")

        update_project(project_id, is_finished=0, user_input=message)
        asyncio.create_task(
            _run_claude(project_id, dir_path, message, session_id),
            name=f"retry-{project_id[:8]}",
        )

        return _ok(200, {"project_id": project_id})

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[API] error: {e}")
        raise HTTPException(500, f"内部错误: {e}")

