#!/usr/bin/env python3
"""Claude Code 托管代理 — FastAPI 主入口。

启动:
    cd backend
    source ../.venv/bin/activate
    uvicorn main:app --host 0.0.0.0 --port 8112
"""

import asyncio
import json
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from .api import claude as api_claude
from .api import database as api_database
from .db import get_zombie_projects, update_project
from .response import err as _err
from .response import ok as _ok


def _project_id_from_path(path: str) -> str:
    m = re.search(r"/projects/([0-9a-f]+)", path)
    return m.group(1) if m else ""

# ── 日志 ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger.remove()
logger.add(
    LOG_DIR / "server.log",
    rotation="10 MB", retention="7 days",
    level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    encoding="utf-8",
)
logger.add(
    LOG_DIR / "error.log",
    rotation="10 MB", retention="7 days",
    level="ERROR", format="{time:YYYY-MM-DD HH:mm:ss} | ERROR | {message}",
    encoding="utf-8",
)

# ── App ───────────────────────────────────────────────────
app = FastAPI(title="Claude Manager")

# wrap_response 必须在最外层（最后注册、最先执行），避免被中间件消耗 body
# CORSMiddleware 在 wrap 内部，不会被重复消费 body
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ── 静态文件 ──────────────────────────────────────────────
AVATAR_DIR = ROOT / "backend" / "static" / "avatars"
STATIC_DIR = ROOT / "backend" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ═══════════════════════════════════════════════════════════
#  中间件 & 异常处理
# ═══════════════════════════════════════════════════════════



@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    pid = _project_id_from_path(request.url.path)
    detail = exc.detail
    if isinstance(detail, str):
        return JSONResponse(content=_err(exc.status_code, pid, detail))
    if isinstance(detail, dict):
        return JSONResponse(content=_err(exc.status_code, pid, detail.get("error", json.dumps(detail, ensure_ascii=False))))
    return JSONResponse(content=_err(exc.status_code, pid, str(detail)))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    pid = _project_id_from_path(request.url.path)
    return JSONResponse(content=_err(422, pid, str(exc.errors())))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    pid = _project_id_from_path(request.url.path)
    logger.exception(f"unhandled: {request.method} {request.url.path}")
    return JSONResponse(content=_err(500, pid, str(exc)))


# ═══════════════════════════════════════════════════════════
#  Mount API Routers
# ═══════════════════════════════════════════════════════════

app.include_router(api_claude.router)
app.include_router(api_database.router)


# ═══════════════════════════════════════════════════════════
#  头像
# ═══════════════════════════════════════════════════════════

@app.get("/avatar/{avatar_type}/{num}.png")
def get_avatar(avatar_type: str, num: int):
    if avatar_type not in ("user", "session"):
        raise HTTPException(404, "Unknown avatar type")
    path = AVATAR_DIR / avatar_type / f"avatar_{num:03d}.png"
    if not path.exists():
        path = AVATAR_DIR / avatar_type / "avatar_001.png"
    from fastapi.responses import FileResponse
    return FileResponse(str(path), media_type="image/png")


# ═══════════════════════════════════════════════════════════
#  健康检查 & 启动
# ═══════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {"status": "ok"}


# ── 前端 SPA 兜底（必须放在所有路由之后） ──────────────
FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


@app.on_event("startup")
async def startup():
    asyncio.create_task(_pid_checker())
    logger.info("| component: pid_checker | status: started")


async def _pid_checker():
    """每分钟检查一次：subprocess_pid > 0 AND is_finished = 0 的项目，如果进程已死则清理。"""
    while True:
        await asyncio.sleep(60)
        try:
            projects = get_zombie_projects()
        except Exception:
            continue
        for proj in projects:
            project_id = proj["project_id"]
            pid = proj["subprocess_pid"]
            try:
                os.kill(pid, 0)
            except OSError:
                prefix = api_claude._log_claude(project_id)
                error = "PID KILLED"
                result = {"duration_ms":0,"num_turns":0,"result":error}
                update_project(project_id,
                    subprocess_pid=0,
                    claude_output=error,
                    claude_result=json.dumps(result, ensure_ascii=False),
                    status=4,
                    is_finished=1)
                logger.info(f"[CALLBACK] success=False data={{project_id={project_id}}} msg={error}")
                logger.exception(f"[{prefix}] FAIL :status=4({error})")

